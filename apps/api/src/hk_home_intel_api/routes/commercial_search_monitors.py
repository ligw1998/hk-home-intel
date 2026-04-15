from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import CommercialSearchMonitor, RefreshJobRun
from hk_home_intel_domain.refresh import (
    launch_commercial_search_monitor_batch,
    launch_commercial_search_monitor_refresh,
)
from hk_home_intel_shared.db import get_db_session
from hk_home_intel_shared.settings import get_settings

router = APIRouter(prefix="/commercial-search-monitors", tags=["commercial-search-monitors"])


class MonitorCriteria(BaseModel):
    listing_segments: list[str] = Field(default_factory=list)
    max_budget_hkd: float | None = None
    bedroom_values: list[int] = Field(default_factory=list)
    max_age_years: int | None = None
    default_limit: int | None = Field(default=None, ge=1, le=200)
    detail_limit: int | None = Field(default=None, ge=1, le=100)


class CommercialSearchMonitorUpsertRequest(BaseModel):
    source: str = "centanet"
    name: str
    search_url: str
    scope_type: str = "custom"
    development_name_hint: str | None = None
    district: str | None = None
    region: str | None = None
    note: str | None = None
    is_active: bool = True
    with_details: bool = True
    detect_withdrawn: bool = False
    tags: list[str] = Field(default_factory=list)
    criteria: MonitorCriteria = Field(default_factory=MonitorCriteria)


class CommercialSearchMonitorRunRequest(BaseModel):
    limit_override: int | None = Field(default=None, ge=1, le=200)


class CommercialSearchMonitorBatchRunRequest(BaseModel):
    source: str = "centanet"
    active_only: bool = True
    limit_override: int | None = Field(default=None, ge=1, le=200)


class CommercialSearchMonitorRunResponse(BaseModel):
    status: str
    job_id: str
    monitor_id: str | None = None
    source: str | None = None
    message: str


class MonitorLatestRunResponse(BaseModel):
    id: str
    status: str
    started_at: str
    finished_at: str | None
    summary: dict | None
    error_message: str | None


class CommercialSearchMonitorResponse(BaseModel):
    id: str
    source: str
    name: str
    search_url: str
    scope_type: str
    development_name_hint: str | None
    district: str | None
    region: str | None
    note: str | None
    is_active: bool
    with_details: bool
    detect_withdrawn: bool
    tags: list[str]
    criteria: MonitorCriteria
    updated_at: str
    latest_run: MonitorLatestRunResponse | None


def _serialize_latest_run(item: RefreshJobRun | None) -> MonitorLatestRunResponse | None:
    if item is None:
        return None
    started_at = item.started_at
    finished_at = item.finished_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if finished_at is not None and finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=timezone.utc)
    return MonitorLatestRunResponse(
        id=item.id,
        status=item.status.value,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat() if finished_at else None,
        summary=item.summary_json,
        error_message=item.error_message,
    )


def _serialize_monitor(item: CommercialSearchMonitor, session: Session) -> CommercialSearchMonitorResponse:
    latest_run = session.scalar(
        select(RefreshJobRun)
        .where(RefreshJobRun.job_name == f"commercial_monitor:{item.id}")
        .order_by(RefreshJobRun.started_at.desc())
        .limit(1)
    )
    return CommercialSearchMonitorResponse(
        id=item.id,
        source=item.source,
        name=item.name,
        search_url=item.search_url,
        scope_type=item.scope_type,
        development_name_hint=item.development_name_hint,
        district=item.district,
        region=item.region,
        note=item.note,
        is_active=item.is_active,
        with_details=item.with_details,
        detect_withdrawn=item.detect_withdrawn,
        tags=item.tags_json or [],
        criteria=MonitorCriteria(**(item.criteria_json or {})),
        updated_at=item.updated_at.isoformat(),
        latest_run=_serialize_latest_run(latest_run),
    )


@router.get("", response_model=list[CommercialSearchMonitorResponse])
def list_commercial_search_monitors(
    source: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    session: Session = Depends(get_db_session),
) -> list[CommercialSearchMonitorResponse]:
    query = select(CommercialSearchMonitor)
    if source:
        query = query.where(CommercialSearchMonitor.source == source)
    if active_only:
        query = query.where(CommercialSearchMonitor.is_active.is_(True))
    items = session.scalars(query.order_by(CommercialSearchMonitor.updated_at.desc())).all()
    return [_serialize_monitor(item, session) for item in items]


@router.post("", response_model=CommercialSearchMonitorResponse, status_code=status.HTTP_201_CREATED)
def create_commercial_search_monitor(
    payload: CommercialSearchMonitorUpsertRequest,
    session: Session = Depends(get_db_session),
) -> CommercialSearchMonitorResponse:
    existing = session.scalar(
        select(CommercialSearchMonitor)
        .where(
            CommercialSearchMonitor.source == payload.source,
            CommercialSearchMonitor.search_url == payload.search_url,
        )
        .limit(1)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="commercial search monitor with this URL already exists")
    item = CommercialSearchMonitor(
        source=payload.source,
        name=payload.name,
        search_url=payload.search_url,
        scope_type=payload.scope_type,
        development_name_hint=payload.development_name_hint,
        district=payload.district,
        region=payload.region,
        note=payload.note,
        is_active=payload.is_active,
        with_details=payload.with_details,
        detect_withdrawn=payload.detect_withdrawn,
        tags_json=payload.tags,
        criteria_json=payload.criteria.model_dump(),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _serialize_monitor(item, session)


@router.patch("/{monitor_id}", response_model=CommercialSearchMonitorResponse)
def update_commercial_search_monitor(
    monitor_id: str,
    payload: CommercialSearchMonitorUpsertRequest,
    session: Session = Depends(get_db_session),
) -> CommercialSearchMonitorResponse:
    item = session.get(CommercialSearchMonitor, monitor_id)
    if item is None:
        raise HTTPException(status_code=404, detail="commercial search monitor not found")
    duplicate = session.scalar(
        select(CommercialSearchMonitor)
        .where(
            CommercialSearchMonitor.source == payload.source,
            CommercialSearchMonitor.search_url == payload.search_url,
            CommercialSearchMonitor.id != monitor_id,
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="commercial search monitor with this URL already exists")
    item.source = payload.source
    item.name = payload.name
    item.search_url = payload.search_url
    item.scope_type = payload.scope_type
    item.development_name_hint = payload.development_name_hint
    item.district = payload.district
    item.region = payload.region
    item.note = payload.note
    item.is_active = payload.is_active
    item.with_details = payload.with_details
    item.detect_withdrawn = payload.detect_withdrawn
    item.tags_json = payload.tags
    item.criteria_json = payload.criteria.model_dump()
    session.commit()
    session.refresh(item)
    return _serialize_monitor(item, session)


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_commercial_search_monitor(
    monitor_id: str,
    session: Session = Depends(get_db_session),
) -> None:
    item = session.get(CommercialSearchMonitor, monitor_id)
    if item is None:
        raise HTTPException(status_code=404, detail="commercial search monitor not found")
    session.delete(item)
    session.commit()


@router.post("/{monitor_id}/run", response_model=CommercialSearchMonitorRunResponse)
def run_commercial_search_monitor(
    monitor_id: str,
    payload: CommercialSearchMonitorRunRequest,
) -> CommercialSearchMonitorRunResponse:
    try:
        result = launch_commercial_search_monitor_refresh(
            database_url=get_settings().database_url,
            monitor_id=monitor_id,
            limit_override=payload.limit_override,
            trigger_kind="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CommercialSearchMonitorRunResponse(
        status="accepted",
        job_id=result["job_id"],
        monitor_id=result["monitor_id"],
        message="Commercial search monitor started in background.",
    )


@router.post("/run-batch", response_model=CommercialSearchMonitorRunResponse)
def run_commercial_search_monitor_batch(
    payload: CommercialSearchMonitorBatchRunRequest,
) -> CommercialSearchMonitorRunResponse:
    try:
        result = launch_commercial_search_monitor_batch(
            database_url=get_settings().database_url,
            source=payload.source,
            active_only=payload.active_only,
            limit_override=payload.limit_override,
            trigger_kind="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CommercialSearchMonitorRunResponse(
        status="accepted",
        job_id=result["job_id"],
        source=result["source"],
        message="Commercial search monitor batch started in background.",
    )
