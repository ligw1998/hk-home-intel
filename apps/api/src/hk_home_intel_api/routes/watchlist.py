from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.enums import ListingStatus, PriceEventType, WatchlistStage
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import Development, Listing, PriceEvent, WatchlistItem
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistUpsertRequest(BaseModel):
    development_id: str
    decision_stage: WatchlistStage = WatchlistStage.WATCHING
    personal_score: int | None = None
    note: str | None = None
    tags: list[str] = Field(default_factory=list)


class WatchlistUpdateRequest(BaseModel):
    decision_stage: WatchlistStage | None = None
    personal_score: int | None = None
    note: str | None = None
    tags: list[str] | None = None


class WatchlistItemResponse(BaseModel):
    id: str
    development_id: str
    development_name: str | None
    source_url: str | None
    district: str | None
    region: str | None
    completion_year: int | None
    listing_segment: str | None
    decision_stage: WatchlistStage
    personal_score: int | None
    note: str | None
    tags: list[str]
    updated_at: str
    active_listing_count: int
    active_listing_min_price_hkd: float | None
    active_listing_max_price_hkd: float | None
    latest_listing_event_at: str | None
    recent_listing_event_count_7d: int
    recent_price_move_count_7d: int
    recent_status_move_count_7d: int


def _build_watchlist_market_snapshot(
    session: Session,
    development_id: str,
) -> dict[str, object]:
    active_listing_rows = session.scalars(
        select(Listing)
        .where(
            Listing.development_id == development_id,
            Listing.status == ListingStatus.ACTIVE,
        )
        .order_by(Listing.asking_price_hkd.asc().nullslast())
    ).all()
    min_price = None
    max_price = None
    if active_listing_rows:
        prices = [float(item.asking_price_hkd) for item in active_listing_rows if item.asking_price_hkd is not None]
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None

    latest_event_at = session.scalar(
        select(func.max(PriceEvent.event_at)).where(PriceEvent.development_id == development_id)
    )
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_events = session.scalars(
        select(PriceEvent).where(
            PriceEvent.development_id == development_id,
            PriceEvent.event_at >= cutoff,
        )
    ).all()
    recent_price_move_count = sum(
        1 for item in recent_events if item.event_type in {PriceEventType.PRICE_DROP, PriceEventType.PRICE_RAISE}
    )
    recent_status_move_count = sum(
        1 for item in recent_events if item.event_type in {PriceEventType.WITHDRAWN, PriceEventType.RELIST, PriceEventType.SOLD}
    )
    return {
        "active_listing_count": len(active_listing_rows),
        "active_listing_min_price_hkd": min_price,
        "active_listing_max_price_hkd": max_price,
        "latest_listing_event_at": latest_event_at.isoformat() if latest_event_at is not None else None,
        "recent_listing_event_count_7d": len(recent_events),
        "recent_price_move_count_7d": recent_price_move_count,
        "recent_status_move_count_7d": recent_status_move_count,
    }


def _serialize_watchlist_item(item: WatchlistItem, preferred_language: str, session: Session) -> WatchlistItemResponse:
    development = item.development
    development_name = None
    source_url = None
    district = None
    region = None
    completion_year = None
    listing_segment = None
    market_snapshot = _build_watchlist_market_snapshot(session, item.development_id)
    if development is not None:
        development_name = localize_text(
            development.name_translations_json or {},
            preferred_language,
            default=development.name_zh or development.name_en,
        )
        source_url = development.source_url
        district = development.district
        region = development.region
        completion_year = development.completion_year
        listing_segment = development.listing_segment.value

    return WatchlistItemResponse(
        id=item.id,
        development_id=item.development_id,
        development_name=development_name,
        source_url=source_url,
        district=district,
        region=region,
        completion_year=completion_year,
        listing_segment=listing_segment,
        decision_stage=item.decision_stage,
        personal_score=item.personal_score,
        note=item.note,
        tags=item.tags_json or [],
        updated_at=item.updated_at.isoformat(),
        active_listing_count=int(market_snapshot["active_listing_count"]),
        active_listing_min_price_hkd=market_snapshot["active_listing_min_price_hkd"],  # type: ignore[arg-type]
        active_listing_max_price_hkd=market_snapshot["active_listing_max_price_hkd"],  # type: ignore[arg-type]
        latest_listing_event_at=market_snapshot["latest_listing_event_at"],  # type: ignore[arg-type]
        recent_listing_event_count_7d=int(market_snapshot["recent_listing_event_count_7d"]),
        recent_price_move_count_7d=int(market_snapshot["recent_price_move_count_7d"]),
        recent_status_move_count_7d=int(market_snapshot["recent_status_move_count_7d"]),
    )


@router.get("", response_model=list[WatchlistItemResponse])
def list_watchlist(
    development_id: str | None = Query(default=None),
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> list[WatchlistItemResponse]:
    stmt = select(WatchlistItem).order_by(WatchlistItem.updated_at.desc())
    if development_id:
        stmt = stmt.where(WatchlistItem.development_id == development_id)
    items = session.scalars(stmt).all()
    return [_serialize_watchlist_item(item, lang, session) for item in items]


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def upsert_watchlist_item(
    payload: WatchlistUpsertRequest,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> WatchlistItemResponse:
    development = session.get(Development, payload.development_id)
    if development is None:
        raise HTTPException(status_code=404, detail="development not found")

    item = session.scalar(
        select(WatchlistItem).where(WatchlistItem.development_id == payload.development_id).limit(1)
    )
    created = item is None
    if created:
        item = WatchlistItem(
            development_id=payload.development_id,
            decision_stage=payload.decision_stage,
            personal_score=payload.personal_score,
            note=payload.note,
            tags_json=payload.tags,
        )
        session.add(item)
    else:
        item.decision_stage = payload.decision_stage
        item.personal_score = payload.personal_score
        item.note = payload.note
        item.tags_json = payload.tags

    session.commit()
    session.refresh(item)
    if created:
        session.refresh(development)
    return _serialize_watchlist_item(item, lang, session)


@router.patch("/{watchlist_item_id}", response_model=WatchlistItemResponse)
def update_watchlist_item(
    watchlist_item_id: str,
    payload: WatchlistUpdateRequest,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> WatchlistItemResponse:
    item = session.get(WatchlistItem, watchlist_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="watchlist item not found")

    if payload.decision_stage is not None:
        item.decision_stage = payload.decision_stage
    if payload.personal_score is not None or payload.personal_score == 0:
        item.personal_score = payload.personal_score
    if payload.note is not None:
        item.note = payload.note
    if payload.tags is not None:
        item.tags_json = payload.tags

    session.commit()
    session.refresh(item)
    return _serialize_watchlist_item(item, lang, session)


@router.delete("/{watchlist_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    watchlist_item_id: str,
    session: Session = Depends(get_db_session),
) -> None:
    item = session.get(WatchlistItem, watchlist_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="watchlist item not found")

    session.delete(item)
    session.commit()
