from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
import re

from hk_home_intel_api.routes.developments import (
    _build_development_price_history,
    _build_listing_metrics,
    _development_age_years,
)
from hk_home_intel_domain.enums import ListingSegment, SourceConfidence
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import Development, Listing, ListingStatus
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/compare", tags=["compare"])


PHASE_PATTERNS = [
    re.compile(r"\s*-\s*phase\s*\d+$", re.I),
    re.compile(r"\s*phase\s*\d+$", re.I),
    re.compile(r"\s*the\s*\d+(st|nd|rd|th)\s*phase$", re.I),
    re.compile(r"\s*的第\d+期$"),
    re.compile(r"\s*第\d+期$"),
]


class CompareDevelopmentItem(BaseModel):
    id: str
    source: str | None
    source_url: str | None
    display_name: str | None
    alias_keys: list[str]
    district: str | None
    region: str | None
    listing_segment: ListingSegment
    source_confidence: SourceConfidence
    completion_year: int | None
    age_years: int | None
    developer_names: list[str]
    address: str | None
    active_listing_count: int
    active_listing_min_price_hkd: float | None
    active_listing_max_price_hkd: float | None
    active_listing_bedroom_options: list[int]
    active_listing_bedroom_mix: dict[str, int]
    active_listing_source_counts: dict[str, int]
    latest_listing_event_at: str | None
    current_min_price_hkd: float | None
    current_max_price_hkd: float | None
    overall_min_price_hkd: float | None
    overall_max_price_hkd: float | None
    price_history_point_count: int


class CompareSuggestionItem(BaseModel):
    development: CompareDevelopmentItem
    match_score: int
    reasons: list[str]


class CompareDevelopmentsResponse(BaseModel):
    focus_development_id: str | None
    items: list[CompareDevelopmentItem]


class CompareSuggestionsResponse(BaseModel):
    focus_development_id: str
    items: list[CompareSuggestionItem]


class ComparableListingItem(BaseModel):
    id: str
    source: str
    source_url: str | None
    development_id: str
    development_name: str | None
    district: str | None
    region: str | None
    title: str | None
    asking_price_hkd: float | None
    price_per_sqft: float | None
    bedrooms: int | None
    bathrooms: int | None
    saleable_area_sqft: float | None
    status: str
    match_score: int
    reasons: list[str]


class ComparableListingsResponse(BaseModel):
    focus_listing_id: str
    focus_development_id: str
    items: list[ComparableListingItem]


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip()
    for pattern in PHASE_PATTERNS:
        normalized = pattern.sub("", normalized)
    return "".join(ch.lower() for ch in normalized if ch.isalnum())


def _normalize_address(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value.strip() if ch.isalnum())


def _shared_developers(left: CompareDevelopmentItem, right: CompareDevelopmentItem) -> set[str]:
    left_keys = {_normalize_name(item) for item in left.developer_names if item}
    right_keys = {_normalize_name(item) for item in right.developer_names if item}
    return {item for item in left_keys & right_keys if item}


def _development_name_keys(development: Development | CompareDevelopmentItem) -> set[str]:
    values: list[str] = []
    if isinstance(development, Development):
        values.extend(
            [
                development.name_zh or "",
                development.name_en or "",
                *list(development.aliases_json or []),
            ]
        )
    else:
        values.extend([development.display_name or "", *list(development.alias_keys)])
    return {item for item in (_normalize_name(value) for value in values) if item}


def _serialize_compare_item(
    development: Development,
    preferred_language: str,
    listing_metrics: dict[str, dict[str, object]],
    session: Session,
) -> CompareDevelopmentItem:
    metrics = listing_metrics.get(development.id, {})
    price_history = _build_development_price_history(development, session=session)
    name_translations = development.name_translations_json or {}
    return CompareDevelopmentItem(
        id=development.id,
        source=development.source,
        source_url=development.source_url,
        display_name=localize_text(
            name_translations,
            preferred_language,
            default=development.name_zh or development.name_en,
        ),
        alias_keys=[
            item
            for item in (
                _normalize_name(development.name_zh),
                _normalize_name(development.name_en),
                *(_normalize_name(alias) for alias in (development.aliases_json or [])),
            )
            if item
        ],
        district=development.district,
        region=development.region,
        listing_segment=development.listing_segment,
        source_confidence=development.source_confidence,
        completion_year=development.completion_year,
        age_years=_development_age_years(development),
        developer_names=development.developer_names_json or [],
        address=development.address_normalized or development.address_raw,
        active_listing_count=int(metrics.get("active_listing_count", 0)),
        active_listing_min_price_hkd=(
            float(metrics["active_listing_min_price_hkd"])
            if metrics.get("active_listing_min_price_hkd") is not None
            else None
        ),
        active_listing_max_price_hkd=(
            float(metrics["active_listing_max_price_hkd"])
            if metrics.get("active_listing_max_price_hkd") is not None
            else None
        ),
        active_listing_bedroom_options=list(metrics.get("active_listing_bedroom_options", [])),
        active_listing_bedroom_mix=dict(metrics.get("active_listing_bedroom_mix", {})),
        active_listing_source_counts=dict(metrics.get("active_listing_source_counts", {})),
        latest_listing_event_at=(
            metrics["latest_listing_event_at"].isoformat()
            if metrics.get("latest_listing_event_at") is not None
            else None
        ),
        current_min_price_hkd=price_history.current_min_price_hkd,
        current_max_price_hkd=price_history.current_max_price_hkd,
        overall_min_price_hkd=price_history.overall_min_price_hkd,
        overall_max_price_hkd=price_history.overall_max_price_hkd,
        price_history_point_count=price_history.point_count,
    )


def _match_score(
    focus: CompareDevelopmentItem,
    candidate: CompareDevelopmentItem,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if _development_name_keys(focus) & _development_name_keys(candidate):
        score += 7
        reasons.append("same estate alias")
    if focus.source and candidate.source and focus.source != candidate.source:
        score += 1
        reasons.append("cross-source")
    if focus.listing_segment == candidate.listing_segment:
        score += 4
        reasons.append("same segment")
    if focus.district and focus.district == candidate.district:
        score += 5
        reasons.append("same district")
    elif focus.region and focus.region == candidate.region:
        score += 2
        reasons.append("same region")

    focus_address = _normalize_address(focus.address)
    candidate_address = _normalize_address(candidate.address)
    if focus_address and candidate_address:
        if focus_address == candidate_address:
            score += 5
            reasons.append("same normalized address")
        elif focus_address[:8] and candidate_address.startswith(focus_address[:8]):
            score += 2
            reasons.append("close address")

    developers = _shared_developers(focus, candidate)
    if developers:
        score += 2
        reasons.append("same developer")

    overlap = sorted(set(focus.active_listing_bedroom_options) & set(candidate.active_listing_bedroom_options))
    if overlap:
        score += 3
        reasons.append(f"bedroom overlap: {', '.join(str(item) for item in overlap)}")

    if focus.active_listing_min_price_hkd and candidate.active_listing_min_price_hkd:
        baseline = max(focus.active_listing_min_price_hkd, 1)
        delta_ratio = abs(candidate.active_listing_min_price_hkd - focus.active_listing_min_price_hkd) / baseline
        if delta_ratio <= 0.15:
            score += 3
            reasons.append("close price floor")
        elif delta_ratio <= 0.30:
            score += 1
            reasons.append("similar price floor")

    if focus.age_years is not None and candidate.age_years is not None:
        age_gap = abs(focus.age_years - candidate.age_years)
        if age_gap <= 3:
            score += 2
            reasons.append("close building age")
        elif age_gap <= 7:
            score += 1
            reasons.append("similar building age")

    if candidate.active_listing_count > 0:
        score += 1
        reasons.append("has active listings")
    return score, reasons


def _serialize_comparable_listing(
    listing: Listing,
    development: Development | None,
    preferred_language: str,
    match_score: int,
    reasons: list[str],
) -> ComparableListingItem:
    title = localize_text(listing.title_translations_json or {}, preferred_language, default=listing.title)
    development_name = None
    district = None
    region = None
    if development is not None:
        development_name = localize_text(
            development.name_translations_json or {},
            preferred_language,
            default=development.name_zh or development.name_en,
        )
        district = development.district
        region = development.region
    return ComparableListingItem(
        id=listing.id,
        source=listing.source,
        source_url=listing.source_url,
        development_id=listing.development_id,
        development_name=development_name,
        district=district,
        region=region,
        title=title,
        asking_price_hkd=float(listing.asking_price_hkd) if listing.asking_price_hkd is not None else None,
        price_per_sqft=float(listing.price_per_sqft) if listing.price_per_sqft is not None else None,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        saleable_area_sqft=float(listing.saleable_area_sqft) if listing.saleable_area_sqft is not None else None,
        status=listing.status.value,
        match_score=match_score,
        reasons=reasons,
    )


def _listing_match_score(
    focus_listing: Listing,
    focus_development: Development | None,
    candidate_listing: Listing,
    candidate_development: Development | None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    geographic_signal = False

    if focus_development is not None and candidate_development is not None:
        if _development_name_keys(focus_development) & _development_name_keys(candidate_development):
            score += 8
            reasons.append("same estate alias")
            geographic_signal = True
        if focus_development.district and focus_development.district == candidate_development.district:
            score += 5
            reasons.append("same district")
            geographic_signal = True
        elif focus_development.region and focus_development.region == candidate_development.region:
            score += 2
            reasons.append("same region")
            geographic_signal = True
        elif focus_development.region and candidate_development.region:
            score -= 2
        if focus_development.listing_segment == candidate_development.listing_segment:
            score += 2
            reasons.append("same segment")

    if focus_listing.source != candidate_listing.source:
        score += 1
        reasons.append("cross-source")

    if focus_listing.bedrooms is not None and candidate_listing.bedrooms is not None:
        if focus_listing.bedrooms == candidate_listing.bedrooms:
            score += 4
            reasons.append("same bedrooms")
        elif abs(focus_listing.bedrooms - candidate_listing.bedrooms) == 1:
            score += 1
            reasons.append("adjacent bedroom count")
        else:
            score -= 2

    if focus_listing.saleable_area_sqft is not None and candidate_listing.saleable_area_sqft is not None:
        focus_area = float(focus_listing.saleable_area_sqft)
        candidate_area = float(candidate_listing.saleable_area_sqft)
        if focus_area > 0:
            delta_ratio = abs(candidate_area - focus_area) / focus_area
            if delta_ratio <= 0.10:
                score += 4
                reasons.append("close area")
            elif delta_ratio <= 0.20:
                score += 2
                reasons.append("similar area")
            elif delta_ratio <= 0.35:
                score += 1
                reasons.append("usable area band")
            elif delta_ratio >= 0.60:
                score -= 2

    if focus_listing.asking_price_hkd is not None and candidate_listing.asking_price_hkd is not None:
        focus_price = float(focus_listing.asking_price_hkd)
        candidate_price = float(candidate_listing.asking_price_hkd)
        if focus_price > 0:
            delta_ratio = abs(candidate_price - focus_price) / focus_price
            if delta_ratio <= 0.15:
                score += 3
                reasons.append("close asking price")
            elif delta_ratio <= 0.30:
                score += 1
                reasons.append("similar asking price")
            elif delta_ratio >= 0.60:
                score -= 2

    if not geographic_signal and score < 8:
        return 0, []
    if score < 5:
        return 0, []

    return score, reasons


@router.get("/developments", response_model=CompareDevelopmentsResponse)
def compare_developments(
    development_id: list[str] = Query(default=[]),
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> CompareDevelopmentsResponse:
    development_ids = list(dict.fromkeys(item for item in development_id if item))
    if not development_ids:
        raise HTTPException(status_code=400, detail="at least one development_id is required")

    developments = session.scalars(
        select(Development)
        .where(Development.id.in_(development_ids), Development.source.is_not(None))
    ).all()
    found_by_id = {item.id: item for item in developments}
    ordered = [found_by_id[item_id] for item_id in development_ids if item_id in found_by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="no developments found")

    listing_metrics = _build_listing_metrics(session, [item.id for item in ordered])
    items = [_serialize_compare_item(item, lang, listing_metrics, session) for item in ordered]
    return CompareDevelopmentsResponse(
        focus_development_id=ordered[0].id if ordered else None,
        items=items,
    )


@router.get("/developments/{development_id}/suggestions", response_model=CompareSuggestionsResponse)
def compare_development_suggestions(
    development_id: str,
    lang: str = Query(default="zh-Hant"),
    limit: int = Query(default=5, ge=1, le=12),
    session: Session = Depends(get_db_session),
) -> CompareSuggestionsResponse:
    focus = session.get(Development, development_id)
    if focus is None or focus.source is None:
        raise HTTPException(status_code=404, detail="development not found")

    stmt = (
        select(Development)
        .where(
            Development.id != focus.id,
            Development.source.is_not(None),
        )
        .order_by(Development.updated_at.desc())
    )
    if focus.region is not None:
        stmt = stmt.where(Development.region == focus.region)
    candidate_rows = session.scalars(stmt).all()
    pool = candidate_rows[:60]
    listing_metrics = _build_listing_metrics(session, [focus.id, *[item.id for item in pool]])
    focus_item = _serialize_compare_item(focus, lang, listing_metrics, session)

    ranked: list[CompareSuggestionItem] = []
    for candidate in pool:
        item = _serialize_compare_item(candidate, lang, listing_metrics, session)
        score, reasons = _match_score(focus_item, item)
        if score <= 0:
            continue
        ranked.append(
            CompareSuggestionItem(
                development=item,
                match_score=score,
                reasons=reasons,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.match_score,
            item.development.active_listing_min_price_hkd
            if item.development.active_listing_min_price_hkd is not None
            else float("inf"),
            item.development.display_name or "",
        )
    )
    return CompareSuggestionsResponse(
        focus_development_id=focus.id,
        items=ranked[:limit],
    )


@router.get("/listings/{listing_id}/comparables", response_model=ComparableListingsResponse)
def compare_listing_comparables(
    listing_id: str,
    lang: str = Query(default="zh-Hant"),
    limit: int = Query(default=6, ge=1, le=20),
    include_same_development: bool = Query(default=False),
    session: Session = Depends(get_db_session),
) -> ComparableListingsResponse:
    focus_listing = session.get(Listing, listing_id)
    if focus_listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    focus_development = session.get(Development, focus_listing.development_id)

    candidate_rows = session.scalars(
        select(Listing)
        .where(
            Listing.id != focus_listing.id,
            Listing.status == ListingStatus.ACTIVE,
        )
        .order_by(Listing.updated_at.desc())
    ).all()

    primary_pool: list[Listing] = []
    fallback_pool: list[Listing] = []
    for candidate in candidate_rows:
        if candidate.development_id == focus_listing.development_id:
            if include_same_development:
                fallback_pool.append(candidate)
            continue
        primary_pool.append(candidate)

    combined_pool = primary_pool + fallback_pool
    scored: list[ComparableListingItem] = []
    for candidate in combined_pool:
        candidate_development = session.get(Development, candidate.development_id)
        score, reasons = _listing_match_score(
            focus_listing,
            focus_development,
            candidate,
            candidate_development,
        )
        if score <= 0:
            continue
        scored.append(
            _serialize_comparable_listing(
                candidate,
                candidate_development,
                lang,
                score,
                reasons,
            )
        )

    scored.sort(
        key=lambda item: (
            -item.match_score,
            abs((item.asking_price_hkd or 0) - float(focus_listing.asking_price_hkd or 0)),
            abs((item.saleable_area_sqft or 0) - float(focus_listing.saleable_area_sqft or 0)),
            item.development_name or "",
        )
    )
    return ComparableListingsResponse(
        focus_listing_id=focus_listing.id,
        focus_development_id=focus_listing.development_id,
        items=scored[:limit],
    )
