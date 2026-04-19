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
class CommercialMonitorRebalanceSummary:
    source: str | None
    scanned: int
    updated: int
    unchanged: int
    unmatched: int
    monitors: list[dict[str, Any]]


@dataclass
class CommercialMonitorActivationSummary:
    source: str | None
    scope_type: str | None
    target_active: bool
    scanned: int
    updated: int
    unchanged: int
    monitors: list[dict[str, Any]]


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


@dataclass
class _ListingSignalSummary:
    score: int
    reasons: list[str]
    has_buyer_focus_signal: bool


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


def _ricacorp_name_hints(item: Development) -> list[str]:
    hints = _development_names(item)
    expanded: list[str] = list(hints)

    for value in hints:
        raw_value = value.strip()
        expanded.extend(segment.strip() for segment in re.split(r"\s{2,}", raw_value) if segment.strip())

        normalized_spaces = re.sub(r"\s+", " ", raw_value).strip()
        if normalized_spaces and normalized_spaces != value:
            expanded.append(normalized_spaces)

        compact_parts = [segment.strip() for segment in re.split(r"\s+-\s+|\s{2,}", raw_value) if segment.strip()]
        expanded.extend(compact_parts)

        chinese_parts = [segment.strip() for segment in re.split(r"[‧・/]", normalized_spaces) if segment.strip()]
        expanded.extend(chinese_parts)

        phase_trimmed = re.sub(
            r"\s+(?:phase\s+)?phase\s+[0-9a-zA-Z]+$",
            "",
            normalized_spaces,
            flags=re.IGNORECASE,
        ).strip()
        if phase_trimmed and phase_trimmed != normalized_spaces:
            expanded.append(phase_trimmed)

        simple_phase_trimmed = re.sub(r"\s+[0-9]+[a-zA-Z]?$", "", normalized_spaces).strip()
        if simple_phase_trimmed and simple_phase_trimmed != normalized_spaces:
            expanded.append(simple_phase_trimmed)

    cleaned = [value for value in _dedupe_preserve(expanded) if len(_normalize_name(value)) >= 2]
    return cleaned


def _ricacorp_identity_keys(item: Development, *, name_hint: str | None = None) -> set[str]:
    values = _ricacorp_name_hints(item)
    if name_hint:
        values.append(name_hint)
    return {_normalize_name(value) for value in values if _normalize_name(value)}


def _listing_signal_summary(context: _DevelopmentContext) -> _ListingSignalSummary:
    score = 0
    reasons: list[str] = []
    has_focus_signal = False

    if context.active_listing_min_price_hkd is not None and context.active_listing_max_price_hkd is not None:
        if context.active_listing_max_price_hkd >= DEFAULT_MIN_BUDGET_HKD and context.active_listing_min_price_hkd <= DEFAULT_MAX_BUDGET_HKD:
            score += 16
            reasons.append("Observed listing price band overlaps the target budget.")
            has_focus_signal = True
        elif context.active_listing_min_price_hkd < DEFAULT_MIN_BUDGET_HKD:
            score += 4
    elif context.active_listing_count == 0:
        score += 4
        reasons.append("No active listing signal yet, so this stays in development coverage mode.")

    preferred_bedroom_score = {2: 14, 3: 11, 1: 8, 0: 4}
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
        has_focus_signal = True
        if best_bedroom_reason:
            reasons.append(best_bedroom_reason)
    elif context.active_listing_count > 0:
        reasons.append("Bedroom signal is still incomplete.")

    if context.active_listing_saleable_areas:
        area_overlap = any(
            DEFAULT_MIN_SALEABLE_AREA_SQFT <= value <= DEFAULT_MAX_SALEABLE_AREA_SQFT
            for value in context.active_listing_saleable_areas
        )
        if area_overlap:
            score += 10
            has_focus_signal = True
            reasons.append("Observed saleable area overlaps the 400-750 sqft target window.")
    elif context.active_listing_count == 0:
        score += 2

    return _ListingSignalSummary(score=score, reasons=reasons, has_buyer_focus_signal=has_focus_signal)


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
            score += 2
            reasons.append("Second-hand stock is older than the preferred <=15y window.")
    else:
        score += 10

    if item.region in {"Hong Kong Island", "Kowloon"}:
        score += 6
        reasons.append("Falls inside a core urban region.")
    elif item.region:
        score += 3

    if item.lat is not None and item.lng is not None:
        score += 2

    if context.active_listing_sources:
        score += 6
        reasons.append("Already has commercial listing coverage to expand from.")

    signal_summary = _listing_signal_summary(context)
    score += signal_summary.score
    reasons.extend(signal_summary.reasons)

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
    for name in _ricacorp_name_hints(item):
        url = f"https://www.ricacorp.com/zh-hk/property/estate/{quote(name, safe='')}"
        candidates.append((name, url))
    return candidates


def _resolve_ricacorp_candidate_pairs(
    adapter: RicacorpAdapter,
    item: Development,
    *,
    estate_entries: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    expected_keys = _ricacorp_identity_keys(item)
    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for entry in estate_entries:
        entry_values = [
            entry.get("display_name"),
            entry.get("alt_name"),
            entry.get("alias_name"),
        ]
        entry_keys = {_normalize_name(value) for value in entry_values if _normalize_name(value)}
        if not entry_keys or not (entry_keys & expected_keys):
            continue
        candidate_url = str(entry.get("buy_list_url") or entry.get("estate_url") or "").strip()
        if not candidate_url or candidate_url in seen_urls:
            continue
        seen_urls.add(candidate_url)
        name_hint = next((value for value in entry_values if value), item.name_zh or item.name_en or candidate_url)
        results.append((name_hint, candidate_url))

    if results or estate_entries:
        return results
    return _ricacorp_candidate_urls(item)


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


def _validate_ricacorp_candidate(item: Development, *, name_hint: str, url: str) -> tuple[bool, str, str | None]:
    adapter = RicacorpAdapter()
    html_text = adapter.fetch_search_results_html(url)
    expected_keys = _ricacorp_identity_keys(item, name_hint=name_hint)
    if "/property/list/buy/" in url:
        listing_page_name = adapter.extract_listing_page_name(html_text)
        listing_page_keys = {_normalize_name(listing_page_name)} if _normalize_name(listing_page_name) else set()
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
        if listing_page_keys & expected_keys:
            return True, f"Matched Ricacorp listing page: {listing_page_name or name_hint}", url
        if bundles and (parsed_keys & expected_keys):
            return True, f"Matched Ricacorp listing page: {name_hint}", url
        return False, "Fetched Ricacorp listing page but did not find a convincing development-name match.", None
    page_name = adapter.extract_estate_page_name(html_text)
    page_keys = {_normalize_name(page_name)} if _normalize_name(page_name) else set()
    buy_list_url = adapter.extract_estate_buy_list_url(html_text, estate_url=url)
    page_markers = ("屋苑專頁" in html_text) or ("rc-estate-post-listing" in html_text) or ("post-total-count" in html_text)

    if page_markers and (page_keys & expected_keys) and buy_list_url:
        return True, f"Matched Ricacorp estate page: {page_name or name_hint}", buy_list_url
    if page_markers and not buy_list_url:
        return False, "Fetched Ricacorp estate page but could not resolve the linked sale listing page.", None
    return False, "Fetched Ricacorp page but did not find a convincing development-name match.", None


def _monitor_defaults(source: str, *, context: _DevelopmentContext) -> tuple[bool, dict[str, Any]]:
    signal_summary = _listing_signal_summary(context)
    if source == "centanet":
        if signal_summary.has_buyer_focus_signal:
            return True, {
                "default_limit": 20,
                "detail_limit": 8,
                "priority_level": 70,
                "detail_policy": "priority_only",
            }
        return False, {
            "default_limit": 20,
            "priority_level": 58,
            "detail_policy": "never",
        }
    if signal_summary.has_buyer_focus_signal:
        return False, {
            "default_limit": 30,
            "priority_level": 58,
            "detail_policy": "never",
        }
    return False, {
        "default_limit": 24,
        "priority_level": 46,
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

    with_details, criteria_defaults = _monitor_defaults(source, context=context)
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


def _monitor_identity_key(monitor: CommercialSearchMonitor) -> str:
    if monitor.development_name_hint:
        return _normalize_name(monitor.development_name_hint)
    slug = unquote(monitor.search_url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1])
    slug = slug.split("_", 1)[0].replace("-", " ").strip()
    return _normalize_name(slug)


def _choose_context_for_monitor(
    contexts: list[_DevelopmentContext],
    *,
    identity_key: str,
    district: str | None,
    region: str | None,
) -> _DevelopmentContext | None:
    candidates = [
        context
        for context in contexts
        if identity_key and identity_key in _development_identity_keys(context.development)
    ]
    if not candidates:
        return None

    exact = [
        context
        for context in candidates
        if (not district or context.development.district == district)
        and (not region or context.development.region == region)
    ]
    if exact:
        candidates = exact

    ranked = sorted(candidates, key=lambda context: _rank_development(context)[0], reverse=True)
    return ranked[0] if ranked else None


def _rebalance_monitor_defaults(monitor: CommercialSearchMonitor, *, context: _DevelopmentContext) -> bool:
    with_details, criteria_defaults = _monitor_defaults(monitor.source, context=context)
    next_criteria = dict(monitor.criteria_json or {})
    next_criteria.update(
        {
            "listing_segments": [context.development.listing_segment.value],
            "min_budget_hkd": DEFAULT_MIN_BUDGET_HKD,
            "max_budget_hkd": DEFAULT_MAX_BUDGET_HKD,
            "bedroom_values": list(DEFAULT_BEDROOM_ORDER),
            "min_saleable_area_sqft": DEFAULT_MIN_SALEABLE_AREA_SQFT,
            "max_saleable_area_sqft": DEFAULT_MAX_SALEABLE_AREA_SQFT,
            **criteria_defaults,
        }
    )

    if context.development.completion_year is not None:
        age_years = max(0, datetime.now().year - context.development.completion_year)
        next_criteria["max_age_years"] = 10 if age_years <= 10 else 15
    else:
        next_criteria.pop("max_age_years", None)

    changed = False
    if monitor.with_details != with_details:
        monitor.with_details = with_details
        changed = True
    if monitor.criteria_json != next_criteria:
        monitor.criteria_json = next_criteria
        changed = True
    return changed


def rebalance_auto_discovered_monitors(
    session: Session,
    *,
    source: str | None = None,
) -> CommercialMonitorRebalanceSummary:
    contexts = _collect_development_contexts(session)
    query = select(CommercialSearchMonitor).where(CommercialSearchMonitor.scope_type == "development_auto")
    if source:
        query = query.where(CommercialSearchMonitor.source == source)
    monitors = session.scalars(query.order_by(CommercialSearchMonitor.updated_at.desc())).all()

    updated = 0
    unchanged = 0
    unmatched = 0
    details: list[dict[str, Any]] = []

    for monitor in monitors:
        identity_key = _monitor_identity_key(monitor)
        context = _choose_context_for_monitor(
            contexts,
            identity_key=identity_key,
            district=monitor.district,
            region=monitor.region,
        )
        if context is None:
            unmatched += 1
            details.append(
                {
                    "monitor_id": monitor.id,
                    "name": monitor.name,
                    "search_url": monitor.search_url,
                    "status": "unmatched",
                }
            )
            continue

        changed = _rebalance_monitor_defaults(monitor, context=context)
        if changed:
            updated += 1
            status = "updated"
        else:
            unchanged += 1
            status = "unchanged"
        details.append(
            {
                "monitor_id": monitor.id,
                "name": monitor.name,
                "search_url": monitor.search_url,
                "status": status,
                "with_details": monitor.with_details,
                "detail_policy": (monitor.criteria_json or {}).get("detail_policy"),
                "priority_level": (monitor.criteria_json or {}).get("priority_level"),
            }
        )

    session.commit()
    return CommercialMonitorRebalanceSummary(
        source=source,
        scanned=len(monitors),
        updated=updated,
        unchanged=unchanged,
        unmatched=unmatched,
        monitors=details,
    )


def set_commercial_monitors_active_state(
    session: Session,
    *,
    source: str | None = None,
    scope_type: str | None = None,
    target_active: bool,
    limit: int | None = None,
) -> CommercialMonitorActivationSummary:
    query = select(CommercialSearchMonitor)
    if source:
        query = query.where(CommercialSearchMonitor.source == source)
    if scope_type:
        query = query.where(CommercialSearchMonitor.scope_type == scope_type)
    monitors = session.scalars(query.order_by(CommercialSearchMonitor.updated_at.desc())).all()
    if limit is not None:
        monitors = monitors[:limit]

    updated = 0
    unchanged = 0
    details: list[dict[str, Any]] = []

    for monitor in monitors:
        changed = monitor.is_active != target_active
        if changed:
            monitor.is_active = target_active
            updated += 1
            status = "updated"
        else:
            unchanged += 1
            status = "unchanged"
        details.append(
            {
                "monitor_id": monitor.id,
                "name": monitor.name,
                "search_url": monitor.search_url,
                "scope_type": monitor.scope_type,
                "is_active": monitor.is_active,
                "status": status,
            }
        )

    session.commit()
    return CommercialMonitorActivationSummary(
        source=source,
        scope_type=scope_type,
        target_active=target_active,
        scanned=len(monitors),
        updated=updated,
        unchanged=unchanged,
        monitors=details,
    )


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
    if source == "ricacorp" and create_monitors and not validate:
        validate = True

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

    ricacorp_estate_entries: list[dict[str, Any]] | None = None
    if source == "ricacorp":
        ricacorp_estate_entries = RicacorpAdapter().estate_index_entries()

    candidates: list[CommercialDiscoveryCandidate] = []
    created_count = 0
    validated_count = 0
    existing_urls = {
        value.search_url: value.id
        for value in session.scalars(
            select(CommercialSearchMonitor).where(CommercialSearchMonitor.source == source)
        ).all()
    }
    selected_urls: set[str] = set()

    for score, reasons, context in ranked:
        item = context.development
        if source == "centanet":
            candidate_pairs = _centanet_candidate_urls(item)
        else:
            candidate_pairs = _resolve_ricacorp_candidate_pairs(
                RicacorpAdapter(),
                item,
                estate_entries=ricacorp_estate_entries or [],
            )
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
                        validated, validation_message, resolved_url = _validate_ricacorp_candidate(item, name_hint=name_hint, url=url)
                        if validated and resolved_url:
                            url = resolved_url
                            existing_monitor_id = existing_urls.get(url)
                    validation_status = "validated" if validated else "no_match"
                except Exception as exc:
                    validated = False
                    validation_status = "fetch_failed"
                    validation_message = str(exc)

            if url in selected_urls:
                continue

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
                if candidate.created_monitor_id:
                    existing_urls[url] = candidate.created_monitor_id
                created_count += 1

            candidates.append(candidate)
            selected_urls.add(url)
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
