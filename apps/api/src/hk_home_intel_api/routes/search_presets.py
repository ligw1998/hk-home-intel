from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import SearchPreset
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/search-presets", tags=["search-presets"])


class SearchPresetCriteria(BaseModel):
    region: str | None = None
    district: str | None = None
    search: str | None = None
    listing_segments: list[str] = Field(default_factory=list)
    min_budget_hkd: float | None = None
    max_budget_hkd: float | None = None
    bedroom_values: list[int] = Field(default_factory=list)
    min_saleable_area_sqft: float | None = None
    max_saleable_area_sqft: float | None = None
    max_age_years: int | None = None
    watchlist_only: bool = False


class SearchPresetUpsertRequest(BaseModel):
    name: str
    scope: str = "development_map"
    note: str | None = None
    is_default: bool = False
    criteria: SearchPresetCriteria


class SearchPresetResponse(BaseModel):
    id: str
    name: str
    scope: str
    note: str | None
    is_default: bool
    criteria: SearchPresetCriteria
    updated_at: str


def _serialize_preset(item: SearchPreset) -> SearchPresetResponse:
    return SearchPresetResponse(
        id=item.id,
        name=item.name,
        scope=item.scope,
        note=item.note,
        is_default=item.is_default,
        criteria=SearchPresetCriteria(**(item.criteria_json or {})),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("", response_model=list[SearchPresetResponse])
def list_search_presets(
    scope: str = Query(default="development_map"),
    session: Session = Depends(get_db_session),
) -> list[SearchPresetResponse]:
    items = session.scalars(
        select(SearchPreset)
        .where(SearchPreset.scope == scope)
        .order_by(SearchPreset.is_default.desc(), SearchPreset.updated_at.desc())
    ).all()
    return [_serialize_preset(item) for item in items]


@router.post("", response_model=SearchPresetResponse, status_code=status.HTTP_201_CREATED)
def create_search_preset(
    payload: SearchPresetUpsertRequest,
    session: Session = Depends(get_db_session),
) -> SearchPresetResponse:
    existing = session.scalar(
        select(SearchPreset)
        .where(SearchPreset.scope == payload.scope, SearchPreset.name == payload.name)
        .limit(1)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="search preset with this name already exists")
    if payload.is_default:
        _clear_default_for_scope(session, payload.scope)
    item = SearchPreset(
        name=payload.name,
        scope=payload.scope,
        note=payload.note,
        is_default=payload.is_default,
        criteria_json=payload.criteria.model_dump(),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _serialize_preset(item)


@router.patch("/{preset_id}", response_model=SearchPresetResponse)
def update_search_preset(
    preset_id: str,
    payload: SearchPresetUpsertRequest,
    session: Session = Depends(get_db_session),
) -> SearchPresetResponse:
    item = session.get(SearchPreset, preset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="search preset not found")
    duplicate = session.scalar(
        select(SearchPreset)
        .where(
            SearchPreset.scope == payload.scope,
            SearchPreset.name == payload.name,
            SearchPreset.id != preset_id,
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="search preset with this name already exists")
    if payload.is_default:
        _clear_default_for_scope(session, payload.scope, exclude_id=preset_id)
    item.name = payload.name
    item.scope = payload.scope
    item.note = payload.note
    item.is_default = payload.is_default
    item.criteria_json = payload.criteria.model_dump()
    session.commit()
    session.refresh(item)
    return _serialize_preset(item)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search_preset(
    preset_id: str,
    session: Session = Depends(get_db_session),
) -> None:
    item = session.get(SearchPreset, preset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="search preset not found")
    session.delete(item)
    session.commit()


def _clear_default_for_scope(session: Session, scope: str, exclude_id: str | None = None) -> None:
    items = session.scalars(select(SearchPreset).where(SearchPreset.scope == scope)).all()
    for item in items:
        if exclude_id and item.id == exclude_id:
            continue
        item.is_default = False
