from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from datetime import datetime

from hk_home_intel_domain.enums import ListingSegment, ListingStatus, SourceConfidence
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import Development, Document, Listing, PriceEvent, Transaction
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/developments", tags=["developments"])


class DevelopmentSummary(BaseModel):
    id: str
    source_url: str | None
    name_zh: str | None
    name_en: str | None
    name_translations: dict[str, str]
    display_name: str | None
    district: str | None
    subdistrict: str | None
    region: str | None
    completion_year: int | None
    age_years: int | None
    listing_segment: ListingSegment
    source_confidence: SourceConfidence
    lat: float | None
    lng: float | None
    active_listing_count: int
    active_listing_min_price_hkd: float | None
    active_listing_max_price_hkd: float | None
    active_listing_bedroom_options: list[int]
    active_listing_bedroom_mix: dict[str, int]
    active_listing_source_counts: dict[str, int]
    latest_listing_event_at: str | None


class DevelopmentListResponse(BaseModel):
    items: list[DevelopmentSummary]
    total: int


class DocumentSummary(BaseModel):
    id: str
    source: str
    source_doc_id: str
    title: str
    title_translations: dict[str, str]
    display_title: str
    doc_type: str
    source_url: str | None
    published_at: str | None
    file_path: str | None
    mime_type: str | None
    content_hash: str | None


class ListingSummary(BaseModel):
    id: str
    source: str
    source_listing_id: str
    title: str | None
    title_translations: dict[str, str]
    display_title: str | None
    listing_type: str
    asking_price_hkd: float | None
    price_per_sqft: float | None
    bedrooms: int | None
    bathrooms: int | None
    saleable_area_sqft: float | None
    status: str
    source_url: str | None


class TransactionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    source_record_id: str
    transaction_date: str | None
    registration_date: str | None
    price_hkd: float | None
    price_per_sqft: float | None
    transaction_type: str
    source_url: str | None


class DevelopmentDetail(DevelopmentSummary):
    active_listing_count: int
    document_count: int
    transaction_count: int
    listings: list[ListingSummary]
    documents: list[DocumentSummary]
    transactions: list[TransactionSummary]


def _apply_filters(
    stmt,
    district: str | None,
    region: str | None,
    listing_segments: set[ListingSegment] | None,
    has_coordinates: bool | None,
):
    if district:
        stmt = stmt.where(Development.district == district)
    if region:
        stmt = stmt.where(Development.region == region)
    if listing_segments:
        stmt = stmt.where(Development.listing_segment.in_(listing_segments))
    if has_coordinates is True:
        stmt = stmt.where(Development.lat.is_not(None), Development.lng.is_not(None))
    return stmt


def _development_age_years(item: Development) -> int | None:
    if item.completion_year is None:
        return None
    current_year = datetime.now().year
    return max(0, current_year - item.completion_year)


def _serialize_development(
    item: Development,
    preferred_language: str,
    listing_metrics: dict[str, dict[str, object]] | None = None,
) -> DevelopmentSummary:
    name_translations = item.name_translations_json or {}
    metrics = (listing_metrics or {}).get(item.id, {})
    return DevelopmentSummary(
        id=item.id,
        source_url=item.source_url,
        name_zh=item.name_zh,
        name_en=item.name_en,
        name_translations=name_translations,
        display_name=localize_text(
            name_translations,
            preferred_language,
            default=item.name_zh or item.name_en,
        ),
        district=item.district,
        subdistrict=item.subdistrict,
        region=item.region,
        completion_year=item.completion_year,
        age_years=_development_age_years(item),
        listing_segment=item.listing_segment,
        source_confidence=item.source_confidence,
        lat=item.lat,
        lng=item.lng,
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
    )


def _serialize_listing(item: Listing, preferred_language: str) -> ListingSummary:
    title_translations = item.title_translations_json or {}
    return ListingSummary(
        id=item.id,
        source=item.source,
        source_listing_id=item.source_listing_id,
        title=item.title,
        title_translations=title_translations,
        display_title=localize_text(
            title_translations,
            preferred_language,
            default=item.title,
        ),
        listing_type=item.listing_type.value,
        asking_price_hkd=float(item.asking_price_hkd) if item.asking_price_hkd is not None else None,
        price_per_sqft=float(item.price_per_sqft) if item.price_per_sqft is not None else None,
        bedrooms=item.bedrooms,
        bathrooms=item.bathrooms,
        saleable_area_sqft=float(item.saleable_area_sqft) if item.saleable_area_sqft is not None else None,
        status=item.status.value,
        source_url=item.source_url,
    )


def _serialize_transaction(item: Transaction) -> TransactionSummary:
    return TransactionSummary(
        id=item.id,
        source=item.source,
        source_record_id=item.source_record_id,
        transaction_date=item.transaction_date.isoformat() if item.transaction_date else None,
        registration_date=item.registration_date.isoformat() if item.registration_date else None,
        price_hkd=float(item.price_hkd) if item.price_hkd is not None else None,
        price_per_sqft=float(item.price_per_sqft) if item.price_per_sqft is not None else None,
        transaction_type=item.transaction_type.value,
        source_url=item.source_url,
    )


def _serialize_document(item: Document, preferred_language: str) -> DocumentSummary:
    title_translations = item.title_translations_json or {}
    return DocumentSummary(
        id=item.id,
        source=item.source,
        source_doc_id=item.source_doc_id,
        title=item.title,
        title_translations=title_translations,
        display_title=localize_text(
            title_translations,
            preferred_language,
            default=item.title,
        )
        or item.title,
        doc_type=item.doc_type.value,
        source_url=item.source_url,
        published_at=item.published_at.isoformat() if item.published_at else None,
        file_path=item.file_path,
        mime_type=item.mime_type,
        content_hash=item.content_hash,
    )


def _parse_listing_segments(raw: str | None) -> set[ListingSegment] | None:
    if not raw:
        return None
    values: set[ListingSegment] = set()
    for item in raw.split(","):
        normalized = item.strip()
        if not normalized:
            continue
        values.add(ListingSegment(normalized))
    return values or None


def _parse_bedroom_values(raw: str | None) -> list[int]:
    if not raw:
        return []
    result: list[int] = []
    for item in raw.split(","):
        normalized = item.strip()
        if not normalized:
            continue
        result.append(int(normalized))
    return result


def _build_listing_metrics(session: Session, development_ids: list[str]) -> dict[str, dict[str, object]]:
    if not development_ids:
        return {}
    rows = session.scalars(
        select(Listing)
        .where(
            Listing.development_id.in_(development_ids),
            Listing.status == ListingStatus.ACTIVE,
        )
        .order_by(Listing.asking_price_hkd.asc().nullslast())
    ).all()
    metrics: dict[str, dict[str, object]] = {
        development_id: {
            "active_listing_count": 0,
            "active_listing_min_price_hkd": None,
            "active_listing_max_price_hkd": None,
            "active_listing_bedroom_options": [],
            "active_listing_bedroom_mix": {},
            "active_listing_source_counts": {},
            "latest_listing_event_at": None,
        }
        for development_id in development_ids
    }
    bedroom_sets: dict[str, set[int]] = {development_id: set() for development_id in development_ids}
    for row in rows:
        item = metrics[row.development_id]
        item["active_listing_count"] = int(item["active_listing_count"]) + 1
        current_min_price = item["active_listing_min_price_hkd"]
        current_max_price = item["active_listing_max_price_hkd"]
        if row.asking_price_hkd is not None and (
            current_min_price is None or row.asking_price_hkd < current_min_price
        ):
            item["active_listing_min_price_hkd"] = row.asking_price_hkd
        if row.asking_price_hkd is not None and (
            current_max_price is None or row.asking_price_hkd > current_max_price
        ):
            item["active_listing_max_price_hkd"] = row.asking_price_hkd
        if row.bedrooms is not None:
            bedroom_sets[row.development_id].add(row.bedrooms)
            bedroom_mix = dict(item["active_listing_bedroom_mix"])
            bedroom_key = str(row.bedrooms)
            bedroom_mix[bedroom_key] = bedroom_mix.get(bedroom_key, 0) + 1
            item["active_listing_bedroom_mix"] = bedroom_mix
        source_counts = dict(item["active_listing_source_counts"])
        source_counts[row.source] = source_counts.get(row.source, 0) + 1
        item["active_listing_source_counts"] = source_counts
    for development_id, values in bedroom_sets.items():
        metrics[development_id]["active_listing_bedroom_options"] = sorted(values)
    latest_event_rows = session.execute(
        select(PriceEvent.development_id, func.max(PriceEvent.event_at))
        .where(PriceEvent.development_id.in_(development_ids))
        .group_by(PriceEvent.development_id)
    ).all()
    for development_id, latest_event_at in latest_event_rows:
        metrics[development_id]["latest_listing_event_at"] = latest_event_at
    return metrics


def _matches_preference_filters(
    item: DevelopmentSummary,
    *,
    q: str | None,
    max_budget_hkd: float | None,
    bedroom_values: list[int],
    max_age_years: int | None,
) -> bool:
    if q:
        haystack = " ".join(
            value
            for value in [
                item.display_name,
                item.name_zh,
                item.name_en,
                item.district,
                item.region,
            ]
            if value
        ).lower()
        if q.strip().lower() not in haystack:
            return False
    if max_budget_hkd is not None:
        if item.active_listing_min_price_hkd is None or item.active_listing_min_price_hkd > max_budget_hkd:
            return False
    if bedroom_values:
        if not any(value in item.active_listing_bedroom_options for value in bedroom_values):
            return False
    if max_age_years is not None:
        if item.age_years is None:
            if item.listing_segment == ListingSegment.SECOND_HAND:
                return False
        elif item.age_years > max_age_years:
            return False
    return True


def _bedroom_preference_rank(item: DevelopmentSummary, bedroom_values: list[int]) -> int:
    if not bedroom_values:
        return 999
    for index, bedroom_value in enumerate(bedroom_values):
        if bedroom_value in item.active_listing_bedroom_options:
            return index
    return 999


@router.get("", response_model=DevelopmentListResponse)
def list_developments(
    district: str | None = None,
    region: str | None = None,
    listing_segment: ListingSegment | None = None,
    listing_segments: str | None = Query(default=None),
    has_coordinates: bool | None = None,
    q: str | None = Query(default=None),
    max_budget_hkd: float | None = Query(default=None, ge=0),
    bedroom_values: str | None = Query(default=None),
    max_age_years: int | None = Query(default=None, ge=0),
    lang: str = Query(default="zh-Hant"),
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
) -> DevelopmentListResponse:
    parsed_listing_segments = _parse_listing_segments(listing_segments)
    if listing_segment is not None:
        parsed_listing_segments = {listing_segment}
    parsed_bedroom_values = _parse_bedroom_values(bedroom_values)
    base_stmt = select(Development).where(Development.source.is_not(None))
    filtered_stmt = _apply_filters(base_stmt, district, region, parsed_listing_segments, has_coordinates)
    developments = session.scalars(filtered_stmt.order_by(Development.updated_at.desc())).all()
    listing_metrics = _build_listing_metrics(session, [item.id for item in developments])
    serialized = [
        _serialize_development(item, lang, listing_metrics)
        for item in developments
    ]
    filtered_serialized = [
        item
        for item in serialized
        if _matches_preference_filters(
            item,
            q=q,
            max_budget_hkd=max_budget_hkd,
            bedroom_values=parsed_bedroom_values,
            max_age_years=max_age_years,
        )
    ]
    filtered_serialized.sort(
        key=lambda item: (
            _bedroom_preference_rank(item, parsed_bedroom_values),
            item.active_listing_min_price_hkd if item.active_listing_min_price_hkd is not None else float("inf"),
            item.age_years if item.age_years is not None else 999,
            item.display_name or "",
        )
    )
    total = len(filtered_serialized)
    return DevelopmentListResponse(items=filtered_serialized[offset : offset + limit], total=total)


@router.get("/{development_id}", response_model=DevelopmentDetail)
def get_development(
    development_id: str,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> DevelopmentDetail:
    development = session.get(Development, development_id)
    if development is None or development.source is None:
        raise HTTPException(status_code=404, detail="development not found")

    listings = session.scalars(
        select(Listing)
        .where(Listing.development_id == development.id)
        .order_by(Listing.asking_price_hkd.asc().nullslast())
    ).all()
    documents = session.scalars(
        select(Document)
        .where(Document.development_id == development.id)
        .order_by(Document.published_at.desc().nullslast())
    ).all()
    transactions = session.scalars(
        select(Transaction)
        .where(Transaction.development_id == development.id)
        .order_by(Transaction.transaction_date.desc().nullslast())
    ).all()

    return DevelopmentDetail(
        **_serialize_development(
            development,
            lang,
            _build_listing_metrics(session, [development.id]),
        ).model_dump(),
        document_count=len(documents),
        transaction_count=len(transactions),
        listings=[_serialize_listing(item, lang) for item in listings],
        documents=[_serialize_document(item, lang) for item in documents],
        transactions=[_serialize_transaction(item) for item in transactions],
    )
