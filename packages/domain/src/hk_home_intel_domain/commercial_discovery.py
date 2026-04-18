from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any
from urllib.parse import quote, unquote

from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_connectors.centanet import CentanetAdapter
from hk_home_intel_connectors.ricacorp import RicacorpAdapter
from hk_home_intel_domain.enums import ListingSegment, ListingStatus
from hk_home_intel_domain.models import CommercialSearchMonitor, Development, Listing, WatchlistItem


DEFAULT_MIN_BUDGET_HKD = 8_000_000
DEFAULT_MAX_BUDGET_HKD = 18_000_000
DEFAULT_MIN_SALEABLE_AREA_SQFT = 400
DEFAULT_MAX_SALEABLE_AREA_SQFT = 750
DEFAULT_BEDROOM_ORDER = [2, 3, 1, 0]
GENERIC_PHASE_PATTERNS = (
    r"^第[0-9a-zA-Z]+期$",
    r"^[0-9a-zA-Z]+期$",
    r"^phase\s*[0-9a-zA-Z]+$",
    r"^the\s*[0-9a-zA-Z]+(?:st|nd|rd|th)?\s*phase$",
)


@dataclass
class CommercialDiscoveryCandidate:
    source: str
    development_id: str
    development_name: str | None
    district: str | None
    region: str | None
    listing_segment: str
    search_url: str
    development_name_hint: str | None
    match_score: int
    reasons: list[str]
    validated: bool | None
    validation_status: str
    validation_message: str | None
    existing_monitor_id: str | None
    created_monitor_id: str | None = None


@dataclass
class CommercialDiscoverySummary:
    source: str
    processed: int
    generated: int
    validated: int
    created_monitors: int
    candidates: list[CommercialDiscoveryCandidate]


@dataclass
class _DevelopmentContext:
    development: Development
    active_listing_sources: set[str]
    active_listing_count: int
    active_listing_min_price_hkd: float | None
    active_listing_max_price_hkd: float | None
    active_listing_bedrooms: set[int]
    active_listing_saleable_areas: list[float]
    has_watchlist: bool


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char.lower() for char in value.strip() if char.isalnum())


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = _normalize_name(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _is_generic_phase_name(value: str) -> bool:
    normalized = value.strip()
    return any(re.match(pattern, normalized, re.IGNORECASE) for pattern in GENERIC_PHASE_PATTERNS)


def _development_names(item: Development) -> list[str]:
    raw_values = [
        item.name_zh,
        item.name_en,
        *(item.name_translations_json or {}).values(),
        *(item.aliases_json or []),
    ]
    cleaned = [
        str(value).strip()
        for value in raw_values
        if value and str(value).strip() and not _is_generic_phase_name(str(value).strip())
    ]
    return _dedupe_preserve(cleaned)


def _development_identity_keys(item: Development) -> set[str]:
    return {_normalize_name(value) for value in _development_names(item) if _normalize_name(value)}


def _rank_development(context: _DevelopmentContext) -> tuple[int, list[str]]:
    item = context.development
    score = 0
    reasons: list[str] = []

    if context.has_watchlist:
        score += 40
        reasons.append("Already in watchlist.")

    age_years = None
    if item.completion_year is not None:
        age_years = max(0, datetime.now().year - item.completion_year)

    if item.listing_segment == ListingSegment.NEW:
        score += 36
        reasons.append("Officially classified as new / primary sale.")
    elif item.listing_segment == ListingSegment.FIRST_HAND_REMAINING:
        score += 30
        reasons.append("Still has first-hand remaining stock.")
    elif item.listing_segment == ListingSegment.SECOND_HAND:
        if age_years is not None and age_years <= 10:
            score += 24
            reasons.append("Second-hand stock still within the <=10y target window.")
        elif age_years is not None and age_years <= 15:
            score += 16
            reasons.append("Second-hand stock still within the <=15y fallback window.")
        else:
            score += 4
    else:
        score += 10

    if context.active_listing_min_price_hkd is not None and context.active_listing_max_price_hkd is not None:
        if context.active_listing_max_price_hkd >= DEFAULT_MIN_BUDGET_HKD and context.active_listing_min_price_hkd <= DEFAULT_MAX_BUDGET_HKD:
            score += 22
            reasons.append("Observed listing price band overlaps the target budget.")
        elif context.active_listing_min_price_hkd < DEFAULT_MIN_BUDGET_HKD:
            score += 6
    else:
        score += 6

    preferred_bedroom_score = {2: 18, 3: 14, 1: 10, 0: 4}
    best_bedroom_score = 0
    best_bedroom_reason = None
    for bedroom in context.active_listing_bedrooms:
        candidate_score = preferred_bedroom_score.get(bedroom, 0)
        if candidate_score > best_bedroom_score:
            best_bedroom_score = candidate_score
            label = "studio" if bedroom == 0 else f"{bedroom}-bedroom"
            best_bedroom_reason = f"Observed active {label} listing signal."
    if best_bedroom_score > 0:
        score += best_bedroom_score
        if best_bedroom_reason:
            reasons.append(best_bedroom_reason)
    elif context.active_listing_count == 0:
        score += 4
    else:
        reasons.append("Bedroom signal is still incomplete.")

    if context.active_listing_saleable_areas:
        area_overlap = any(
            DEFAULT_MIN_SALEABLE_AREA_SQFT <= value <= DEFAULT_MAX_SALEABLE_AREA_SQFT
            for value in context.active_listing_saleable_areas
        )
        if area_overlap:
            score += 12
            reasons.append("Observed saleable area overlaps the 400-750 sqft target window.")
    elif context.active_listing_count == 0:
        score += 3

    if item.region in {"Hong Kong Island", "Kowloon"}:
        score += 6
        reasons.append("Falls inside a core urban region.")
    elif item.region:
        score += 3

    if item.lat is not None and item.lng is not None:
        score += 2

    return score, reasons


def _collect_development_contexts(session: Session) -> list[_DevelopmentContext]:
    active_listings = session.scalars(
        select(Listing).where(Listing.status == ListingStatus.ACTIVE)
    ).all()
    listing_by_development: dict[str, list[Listing]] = {}
    for listing in active_listings:
        listing_by_development.setdefault(listing.development_id, []).append(listing)

    watchlist_ids = {
        value
        for value in session.scalars(select(WatchlistItem.development_id)).all()
    }

    items = session.scalars(
        select(Development)
        .where(Development.source.is_not(None))
        .order_by(Development.updated_at.desc())
    ).all()

    contexts: list[_DevelopmentContext] = []
    for item in items:
        rows = listing_by_development.get(item.id, [])
        prices = [float(row.asking_price_hkd) for row in rows if row.asking_price_hkd is not None]
        areas = [float(row.saleable_area_sqft) for row in rows if row.saleable_area_sqft is not None]
        bedrooms = {int(row.bedrooms) for row in rows if row.bedrooms is not None}
        sources = {row.source for row in rows if row.source}
        contexts.append(
            _DevelopmentContext(
                development=item,
                active_listing_sources=sources,
                active_listing_count=len(rows),
                active_listing_min_price_hkd=min(prices) if prices else None,
                active_listing_max_price_hkd=max(prices) if prices else None,
                active_listing_bedrooms=bedrooms,
                active_listing_saleable_areas=sorted(set(areas)),
                has_watchlist=item.id in watchlist_ids,
            )
        )
    return contexts


def _already_has_source(context: _DevelopmentContext, source: str) -> bool:
    item = context.development
    return item.source == source or source in context.active_listing_sources


def _centanet_candidate_urls(item: Development) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for name in _development_names(item):
        url = f"https://hk.centanet.com/findproperty/list/buy/{quote(name, safe='')}"
        candidates.append((name, url))
    return candidates


def _extract_centanet_link_keys(html_text: str) -> set[str]:
    keys: set[str] = set()

    for href in re.findall(r'rel="canonical" href="([^"]+)"', html_text, re.IGNORECASE):
        if "/findproperty/list/buy/" not in href:
            continue
        slug = unquote(href.rsplit("/", 1)[-1])
        slug = slug.split("_", 1)[0].replace("-", " ").strip()
        normalized = _normalize_name(slug)
        if normalized:
            keys.add(normalized)

    for slug in re.findall(r'/findproperty/detail/([^"\'?<>]+)', html_text, re.IGNORECASE):
        decoded = unquote(slug)
        decoded = decoded.split("_", 1)[0].replace("-", " ").strip()
        normalized = _normalize_name(decoded)
        if normalized:
            keys.add(normalized)

    return keys


def _ricacorp_candidate_urls(item: Development) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for name in _development_names(item):
        url = f"https://www.ricacorp.com/zh-hk/property/list/buy/{quote(name, safe='')}-bigest-hk"
        candidates.append((name, url))
    return candidates


def _validate_centanet_candidate(item: Development, *, name_hint: str, url: str) -> tuple[bool, str]:
    adapter = CentanetAdapter()
    html_text = adapter.fetch_search_results_html(url)
    page_name = adapter._extract_page_development_name(html_text, url)
    page_keys = {_normalize_name(page_name)}
    link_keys = _extract_centanet_link_keys(html_text)
    try:
        bundles = adapter.search_results_listing_bundle(url=url, html_text=html_text, limit=5)
    except Exception:
        bundles = []
    parsed_keys: set[str] = set()
    for bundle in bundles:
        payload = bundle["development"].payload
        parsed_keys.update(
            {
                _normalize_name(payload.get("name_zh")),
                _normalize_name(payload.get("name_en")),
                *(_normalize_name(value) for value in (payload.get("name_translations") or {}).values()),
            }
        )
    expected_keys = _development_identity_keys(item)
    expected_keys.add(_normalize_name(name_hint))
    page_markers = ("網上搵樓" in html_text) or ("出售樓盤" in html_text) or ("屋苑專頁" in html_text)
    if page_markers and ((page_keys & expected_keys) or (parsed_keys & expected_keys) or (link_keys & expected_keys)):
        return True, f"Matched page/development name: {page_name or name_hint}"
    return False, "Fetched page but did not find a convincing development-name match."


def _validate_ricacorp_candidate(item: Development, *, name_hint: str, url: str) -> tuple[bool, str]:
    adapter = RicacorpAdapter()
    html_text = adapter.fetch_search_results_html(url)
    expected_keys = _development_identity_keys(item)
    expected_keys.add(_normalize_name(name_hint))
    body_key = _normalize_name(html_text)
    page_markers = ("物業編號" in html_text) or ("market-price-block" in html_text) or ("rc-property-listing-item-desktop" in html_text)
    body_match = any(key and key in body_key for key in expected_keys)
    if page_markers and body_match:
        return True, "Matched listing development names on Ricacorp results page."
    return False, "Fetched Ricacorp page but did not find a convincing development-name match."


def _monitor_defaults(source: str) -> tuple[bool, dict[str, Any]]:
    if source == "centanet":
        return True, {
            "default_limit": 20,
            "detail_limit": 8,
            "priority_level": 70,
            "detail_policy": "priority_only",
        }
    return False, {
        "default_limit": 30,
        "priority_level": 55,
        "detail_policy": "never",
    }


def _create_monitor_from_candidate(
    session: Session,
    *,
    source: str,
    context: _DevelopmentContext,
    candidate: CommercialDiscoveryCandidate,
    activate: bool,
) -> str:
    existing = session.scalar(
        select(CommercialSearchMonitor)
        .where(
            CommercialSearchMonitor.source == source,
            CommercialSearchMonitor.search_url == candidate.search_url,
        )
        .limit(1)
    )
    if existing is not None:
        return existing.id

    with_details, criteria_defaults = _monitor_defaults(source)
    criteria = {
        "listing_segments": [context.development.listing_segment.value],
        "min_budget_hkd": DEFAULT_MIN_BUDGET_HKD,
        "max_budget_hkd": DEFAULT_MAX_BUDGET_HKD,
        "bedroom_values": list(DEFAULT_BEDROOM_ORDER),
        "min_saleable_area_sqft": DEFAULT_MIN_SALEABLE_AREA_SQFT,
        "max_saleable_area_sqft": DEFAULT_MAX_SALEABLE_AREA_SQFT,
        **criteria_defaults,
    }
    if context.development.completion_year is not None:
        age_years = max(0, datetime.now().year - context.development.completion_year)
        criteria["max_age_years"] = 10 if age_years <= 10 else 15

    item = CommercialSearchMonitor(
        source=source,
        name=f"{candidate.development_name or candidate.development_name_hint or 'Development'} auto-discovered search",
        search_url=candidate.search_url,
        scope_type="development_auto",
        development_name_hint=candidate.development_name_hint,
        district=context.development.district,
        region=context.development.region,
        note="Auto-discovered from development pool.",
        is_active=activate,
        with_details=with_details,
        detect_withdrawn=False,
        tags_json=["auto-discovered", "buyer-focus"],
        criteria_json=criteria,
    )
    session.add(item)
    session.flush()
    return item.id


def discover_commercial_monitor_candidates(
    session: Session,
    *,
    source: str,
    limit: int = 20,
    validate: bool = False,
    create_monitors: bool = False,
    activate_created: bool = False,
    include_existing: bool = False,
    development_id: str | None = None,
) -> CommercialDiscoverySummary:
    if source not in {"centanet", "ricacorp"}:
        raise ValueError(f"unsupported commercial discovery source: {source}")

    contexts = _collect_development_contexts(session)
    ranked: list[tuple[int, list[str], _DevelopmentContext]] = []
    for context in contexts:
        item = context.development
        if development_id and item.id != development_id:
            continue
        if not include_existing and _already_has_source(context, source):
            continue
        score, reasons = _rank_development(context)
        if score <= 0:
            continue
        ranked.append((score, reasons, context))
    ranked.sort(key=lambda value: value[0], reverse=True)

    candidates: list[CommercialDiscoveryCandidate] = []
    created_count = 0
    validated_count = 0

    for score, reasons, context in ranked:
        item = context.development
        generator = _centanet_candidate_urls if source == "centanet" else _ricacorp_candidate_urls
        existing_urls = {
            value.search_url: value.id
            for value in session.scalars(
                select(CommercialSearchMonitor).where(CommercialSearchMonitor.source == source)
            ).all()
        }

        candidate_pairs = generator(item)
        for name_hint, url in candidate_pairs:
            existing_monitor_id = existing_urls.get(url)
            validated = None
            validation_status = "unvalidated"
            validation_message = None
            if validate:
                try:
                    if source == "centanet":
                        validated, validation_message = _validate_centanet_candidate(item, name_hint=name_hint, url=url)
                    else:
                        validated, validation_message = _validate_ricacorp_candidate(item, name_hint=name_hint, url=url)
                    validation_status = "validated" if validated else "no_match"
                except Exception as exc:
                    validated = False
                    validation_status = "fetch_failed"
                    validation_message = str(exc)

            candidate = CommercialDiscoveryCandidate(
                source=source,
                development_id=item.id,
                development_name=item.name_zh or item.name_en,
                district=item.district,
                region=item.region,
                listing_segment=item.listing_segment.value,
                search_url=url,
                development_name_hint=name_hint,
                match_score=score,
                reasons=reasons,
                validated=validated,
                validation_status=validation_status,
                validation_message=validation_message,
                existing_monitor_id=existing_monitor_id,
            )

            if validated:
                validated_count += 1
            if create_monitors and existing_monitor_id is None and (not validate or validated):
                candidate.created_monitor_id = _create_monitor_from_candidate(
                    session,
                    source=source,
                    context=context,
                    candidate=candidate,
                    activate=activate_created,
                )
                created_count += 1

            candidates.append(candidate)
            break
        if len(candidates) >= limit:
            break

    if create_monitors:
        session.commit()

    return CommercialDiscoverySummary(
        source=source,
        processed=len(ranked),
        generated=len(candidates),
        validated=validated_count,
        created_monitors=created_count,
        candidates=candidates[:limit],
    )


def serialize_commercial_discovery_summary(summary: CommercialDiscoverySummary) -> dict[str, Any]:
    return {
        "source": summary.source,
        "processed": summary.processed,
        "generated": summary.generated,
        "validated": summary.validated,
        "created_monitors": summary.created_monitors,
        "candidates": [asdict(item) for item in summary.candidates],
    }
