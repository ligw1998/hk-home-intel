from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.enums import PriceEventType
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import Development, Listing, PriceEvent
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/listings", tags=["listings"])


class ListingFeedItemResponse(BaseModel):
    id: str
    event_type: str
    event_at: str
    source: str
    development_id: str
    development_name: str | None
    development_source_url: str | None
    listing_id: str | None
    listing_title: str | None
    listing_source_url: str | None
    old_price_hkd: float | None
    new_price_hkd: float | None
    price_delta_hkd: float | None
    old_status: str | None
    new_status: str | None


class ListingDetailResponse(BaseModel):
    id: str
    source: str
    source_listing_id: str
    source_url: str | None
    development_id: str
    development_name: str | None
    development_source_url: str | None
    title: str | None
    asking_price_hkd: float | None
    price_per_sqft: float | None
    bedrooms: int | None
    bathrooms: int | None
    saleable_area_sqft: float | None
    gross_area_sqft: float | None
    status: str
    first_seen_at: str | None
    last_seen_at: str | None
    address: str | None
    update_date: str | None
    monthly_payment_hkd: float | None
    age_years: int | None
    orientation: str | None
    feature_tags: list[str]
    description: str | None
    developer_names: list[str]


class ListingPricePointResponse(BaseModel):
    event_id: str | None
    event_type: str
    recorded_at: str
    price_hkd: float


class ListingPriceHistoryResponse(BaseModel):
    listing_id: str
    current_price_hkd: float | None
    previous_price_hkd: float | None
    lowest_price_hkd: float | None
    highest_price_hkd: float | None
    point_count: int
    first_seen_at: str | None
    last_seen_at: str | None
    points: list[ListingPricePointResponse]


def _serialize_event(item: PriceEvent, preferred_language: str, session: Session) -> ListingFeedItemResponse:
    development = session.get(Development, item.development_id)
    listing = session.get(Listing, item.listing_id) if item.listing_id else None
    development_name = None
    if development is not None:
        development_name = localize_text(
            development.name_translations_json or {},
            preferred_language,
            default=development.name_zh or development.name_en,
        )
    listing_title = None
    if listing is not None:
        listing_title = localize_text(
            listing.title_translations_json or {},
            preferred_language,
            default=listing.title,
        )
    return ListingFeedItemResponse(
        id=item.id,
        event_type=item.event_type.value,
        event_at=item.event_at.isoformat(),
        source=item.source,
        development_id=item.development_id,
        development_name=development_name,
        development_source_url=development.source_url if development is not None else None,
        listing_id=item.listing_id,
        listing_title=listing_title,
        listing_source_url=listing.source_url if listing is not None else None,
        old_price_hkd=float(item.old_price_hkd) if item.old_price_hkd is not None else None,
        new_price_hkd=float(item.new_price_hkd) if item.new_price_hkd is not None else None,
        price_delta_hkd=(
            float(item.new_price_hkd - item.old_price_hkd)
            if item.old_price_hkd is not None and item.new_price_hkd is not None
            else None
        ),
        old_status=item.old_status,
        new_status=item.new_status,
    )


def _serialize_listing_detail(item: Listing, preferred_language: str, session: Session) -> ListingDetailResponse:
    development = session.get(Development, item.development_id)
    development_name = None
    development_source_url = None
    developer_names: list[str] = []
    if development is not None:
        development_name = localize_text(
            development.name_translations_json or {},
            preferred_language,
            default=development.name_zh or development.name_en,
        )
        development_source_url = development.source_url
        developer_names = development.developer_names_json or []

    detail = (item.raw_payload_json or {}).get("detail") or {}
    return ListingDetailResponse(
        id=item.id,
        source=item.source,
        source_listing_id=item.source_listing_id,
        source_url=item.source_url,
        development_id=item.development_id,
        development_name=development_name,
        development_source_url=development_source_url,
        title=localize_text(item.title_translations_json or {}, preferred_language, default=item.title),
        asking_price_hkd=float(item.asking_price_hkd) if item.asking_price_hkd is not None else None,
        price_per_sqft=float(item.price_per_sqft) if item.price_per_sqft is not None else None,
        bedrooms=item.bedrooms,
        bathrooms=item.bathrooms,
        saleable_area_sqft=float(item.saleable_area_sqft) if item.saleable_area_sqft is not None else None,
        gross_area_sqft=float(item.gross_area_sqft) if item.gross_area_sqft is not None else None,
        status=item.status.value,
        first_seen_at=item.first_seen_at.isoformat() if item.first_seen_at is not None else None,
        last_seen_at=item.last_seen_at.isoformat() if item.last_seen_at is not None else None,
        address=detail.get("address"),
        update_date=detail.get("update_date"),
        monthly_payment_hkd=float(detail["monthly_payment_hkd"]) if detail.get("monthly_payment_hkd") is not None else None,
        age_years=detail.get("age_years"),
        orientation=detail.get("orientation"),
        feature_tags=detail.get("feature_tags") or [],
        description=detail.get("description"),
        developer_names=developer_names,
    )


def _build_listing_price_history(item: Listing, session: Session) -> ListingPriceHistoryResponse:
    events = session.scalars(
        select(PriceEvent)
        .where(PriceEvent.listing_id == item.id)
        .order_by(PriceEvent.event_at.asc(), PriceEvent.created_at.asc())
    ).all()

    points: list[ListingPricePointResponse] = []
    for event in events:
        if event.new_price_hkd is None:
            continue
        points.append(
            ListingPricePointResponse(
                event_id=event.id,
                event_type=event.event_type.value,
                recorded_at=event.event_at.isoformat(),
                price_hkd=float(event.new_price_hkd),
            )
        )

    if not points and item.asking_price_hkd is not None:
        recorded_at = item.last_seen_at or item.updated_at or item.created_at
        points.append(
            ListingPricePointResponse(
                event_id=None,
                event_type="current_snapshot",
                recorded_at=recorded_at.isoformat(),
                price_hkd=float(item.asking_price_hkd),
            )
        )

    prices = [point.price_hkd for point in points]
    return ListingPriceHistoryResponse(
        listing_id=item.id,
        current_price_hkd=float(item.asking_price_hkd) if item.asking_price_hkd is not None else None,
        previous_price_hkd=points[-2].price_hkd if len(points) >= 2 else None,
        lowest_price_hkd=min(prices) if prices else None,
        highest_price_hkd=max(prices) if prices else None,
        point_count=len(points),
        first_seen_at=item.first_seen_at.isoformat() if item.first_seen_at is not None else None,
        last_seen_at=item.last_seen_at.isoformat() if item.last_seen_at is not None else None,
        points=points,
    )


@router.get("/feed", response_model=list[ListingFeedItemResponse])
def list_listing_feed(
    lang: str = Query(default="zh-Hant"),
    development_id: str | None = Query(default=None),
    listing_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    event_type: PriceEventType | None = Query(default=None),
    q: str | None = Query(default=None),
    changes_only: bool = Query(default=False),
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[ListingFeedItemResponse]:
    stmt = (
        select(PriceEvent)
        .outerjoin(Listing, PriceEvent.listing_id == Listing.id)
        .outerjoin(Development, PriceEvent.development_id == Development.id)
    )
    if development_id:
        stmt = stmt.where(PriceEvent.development_id == development_id)
    if listing_id:
        stmt = stmt.where(PriceEvent.listing_id == listing_id)
    if source:
        stmt = stmt.where(PriceEvent.source == source)
    if event_type:
        stmt = stmt.where(PriceEvent.event_type == event_type)
    if changes_only:
        stmt = stmt.where(PriceEvent.event_type != PriceEventType.NEW_LISTING)
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = stmt.where(PriceEvent.event_at >= cutoff)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Listing.title.ilike(pattern),
                Development.name_zh.ilike(pattern),
                Development.name_en.ilike(pattern),
                Development.district.ilike(pattern),
                PriceEvent.source.ilike(pattern),
            )
        )
    stmt = stmt.order_by(PriceEvent.event_at.desc()).limit(limit)
    items = session.scalars(stmt).all()
    return [_serialize_event(item, lang, session) for item in items]


@router.get("/{listing_id}/events", response_model=list[ListingFeedItemResponse])
def get_listing_events(
    listing_id: str,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> list[ListingFeedItemResponse]:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    items = session.scalars(
        select(PriceEvent)
        .where(PriceEvent.listing_id == listing_id)
        .order_by(PriceEvent.event_at.desc())
    ).all()
    return [_serialize_event(item, lang, session) for item in items]


@router.get("/{listing_id}", response_model=ListingDetailResponse)
def get_listing_detail(
    listing_id: str,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> ListingDetailResponse:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return _serialize_listing_detail(listing, lang, session)


@router.get("/{listing_id}/price-history", response_model=ListingPriceHistoryResponse)
def get_listing_price_history(
    listing_id: str,
    session: Session = Depends(get_db_session),
) -> ListingPriceHistoryResponse:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return _build_listing_price_history(listing, session)
