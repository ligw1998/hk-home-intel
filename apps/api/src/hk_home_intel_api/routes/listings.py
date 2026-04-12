from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
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
    listing_id: str | None
    listing_title: str | None
    old_price_hkd: float | None
    new_price_hkd: float | None
    old_status: str | None
    new_status: str | None


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
        listing_id=item.listing_id,
        listing_title=listing_title,
        old_price_hkd=float(item.old_price_hkd) if item.old_price_hkd is not None else None,
        new_price_hkd=float(item.new_price_hkd) if item.new_price_hkd is not None else None,
        old_status=item.old_status,
        new_status=item.new_status,
    )


@router.get("/feed", response_model=list[ListingFeedItemResponse])
def list_listing_feed(
    lang: str = Query(default="zh-Hant"),
    development_id: str | None = Query(default=None),
    event_type: PriceEventType | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[ListingFeedItemResponse]:
    stmt = select(PriceEvent).order_by(PriceEvent.event_at.desc()).limit(limit)
    if development_id:
        stmt = stmt.where(PriceEvent.development_id == development_id)
    if event_type:
        stmt = stmt.where(PriceEvent.event_type == event_type)
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
