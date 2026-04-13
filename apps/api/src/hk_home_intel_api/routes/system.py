from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import Development, Document, RefreshJobRun, SchedulerPlanOverride, WatchlistItem
from hk_home_intel_domain.refresh import launch_due_refresh_plans, launch_refresh_plan
from hk_home_intel_shared.db import get_db_session
from hk_home_intel_shared.scheduler import get_scheduler_plan_statuses, load_scheduler_plans
from hk_home_intel_shared.settings import get_settings

router = APIRouter(prefix="/system", tags=["system"])


class RefreshJobRunSummary(BaseModel):
    id: str
    job_name: str
    source: str | None
    trigger_kind: str
    status: str
    started_at: str
    finished_at: str | None
    summary: dict | None
    error_message: str | None


class SystemOverviewResponse(BaseModel):
    development_count: int
    development_with_coordinates_count: int
    document_count: int
    watchlist_count: int
    latest_job: RefreshJobRunSummary | None


class SchedulerTaskResponse(BaseModel):
    job_name: str
    source: str
    command: str
    url: str | None
    language: str
    limit: int | None
    with_details: bool
    detect_withdrawn: bool
    rotation_mode: str
    rotation_step: int | None


class SchedulerPlanResponse(BaseModel):
    name: str
    description: str
    guideline: str
    auto_run: bool
    interval_minutes: int | None
    last_started_at: str | None
    last_finished_at: str | None
    last_status: str | None
    next_run_at: str | None
    due_now: bool
    has_override: bool
    tasks: list[SchedulerTaskResponse]


class RunPlanRequest(BaseModel):
    plan_name: str


class RunPlanResponse(BaseModel):
    status: str
    job_id: str
    plan: str
    message: str


class RunDuePlansResponse(BaseModel):
    status: str
    due_plan_names: list[str]
    run_count: int
    job_ids: list[str]


class SchedulerTaskOverrideRequest(BaseModel):
    job_name: str
    limit: int | None = None
    with_details: bool | None = None
    detect_withdrawn: bool | None = None
    rotation_mode: str | None = None
    rotation_step: int | None = None


class SchedulerPlanOverrideRequest(BaseModel):
    auto_run: bool | None = None
    interval_minutes: int | None = None
    task_overrides: list[SchedulerTaskOverrideRequest] = []


def _serialize_job(item: RefreshJobRun) -> RefreshJobRunSummary:
    started_at = item.started_at
    finished_at = item.finished_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if finished_at is not None and finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=timezone.utc)
    return RefreshJobRunSummary(
        id=item.id,
        job_name=item.job_name,
        source=item.source,
        trigger_kind=item.trigger_kind,
        status=item.status.value,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat() if finished_at else None,
        summary=item.summary_json,
        error_message=item.error_message,
    )


def _plan_guideline(name: str, auto_run: bool, interval_minutes: int | None) -> str:
    if name == "daily_local":
        cadence = f"every {interval_minutes} minutes" if interval_minutes else "on its configured interval"
        return (
            "Daily local is the low-frequency baseline refresh. It currently fetches one rotating "
            f"window of SRPE developments {cadence}, so repeated runs gradually cover more of the "
            "official index instead of re-reading the same first batch every time."
        )
    if name == "watchlist_probe":
        return (
            "Watchlist probe is a lighter manual verification plan. It keeps the request cost low "
            "and is intended for quick checks while developing or validating the ingest chain."
        )
    if name == "centanet_probe":
        return (
            "Centanet probe is a manual, low-frequency commercial-source refresh for one monitored "
            "search result page. Use it to keep a specific second-hand cluster current without turning "
            "commercial source refresh into a broad crawler."
        )
    return "This plan executes the configured task list with the parameters shown below."


@router.get("/refresh-jobs", response_model=list[RefreshJobRunSummary])
def list_refresh_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[RefreshJobRunSummary]:
    items = session.scalars(
        select(RefreshJobRun).order_by(RefreshJobRun.started_at.desc()).limit(limit)
    ).all()
    return [_serialize_job(item) for item in items]


@router.get("/overview", response_model=SystemOverviewResponse)
def system_overview(session: Session = Depends(get_db_session)) -> SystemOverviewResponse:
    latest_job = session.scalar(
        select(RefreshJobRun).order_by(RefreshJobRun.started_at.desc()).limit(1)
    )
    return SystemOverviewResponse(
        development_count=session.scalar(select(func.count()).select_from(Development)) or 0,
        development_with_coordinates_count=session.scalar(
            select(func.count())
            .select_from(Development)
            .where(Development.lat.is_not(None), Development.lng.is_not(None))
        )
        or 0,
        document_count=session.scalar(select(func.count()).select_from(Document)) or 0,
        watchlist_count=session.scalar(select(func.count()).select_from(WatchlistItem)) or 0,
        latest_job=_serialize_job(latest_job) if latest_job is not None else None,
    )


@router.get("/scheduler-plans", response_model=list[SchedulerPlanResponse])
def list_scheduler_plans(session: Session = Depends(get_db_session)) -> list[SchedulerPlanResponse]:
    plans = load_scheduler_plans(session=session)
    statuses = {item.plan.name: item for item in get_scheduler_plan_statuses(session, plans=plans)}
    overrides = {
        item.plan_name
        for item in session.scalars(select(SchedulerPlanOverride)).all()
    }
    return [
        SchedulerPlanResponse(
            name=item.name,
            description=item.description,
            guideline=_plan_guideline(item.name, item.auto_run, item.interval_minutes),
            auto_run=item.auto_run,
            interval_minutes=item.interval_minutes,
            last_started_at=(
                statuses[item.name].last_started_at.isoformat() if statuses[item.name].last_started_at else None
            ),
            last_finished_at=(
                statuses[item.name].last_finished_at.isoformat() if statuses[item.name].last_finished_at else None
            ),
            last_status=statuses[item.name].last_status,
            next_run_at=statuses[item.name].next_run_at.isoformat() if statuses[item.name].next_run_at else None,
            due_now=statuses[item.name].due_now,
            has_override=item.name in overrides,
            tasks=[
                SchedulerTaskResponse(
                    job_name=task.job_name,
                    source=task.source,
                    command=task.command,
                    url=task.url,
                    language=task.language,
                    limit=task.limit,
                    with_details=task.with_details,
                    detect_withdrawn=task.detect_withdrawn,
                    rotation_mode=task.rotation_mode,
                    rotation_step=task.rotation_step,
                )
                for task in item.tasks
            ],
        )
        for item in plans.values()
    ]


@router.post("/run-plan", response_model=RunPlanResponse)
def run_scheduler_plan(
    payload: RunPlanRequest,
) -> RunPlanResponse:
    try:
        result = launch_refresh_plan(
            database_url=get_settings().database_url,
            plan_name=payload.plan_name,
            trigger_kind="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RunPlanResponse(
        status="accepted",
        job_id=result["job_id"],
        plan=result["plan"],
        message="Refresh plan started in background.",
    )


@router.post("/run-due-plans", response_model=RunDuePlansResponse)
def run_scheduler_due_plans() -> RunDuePlansResponse:
    result = launch_due_refresh_plans(
        database_url=get_settings().database_url,
        trigger_kind="api",
    )
    return RunDuePlansResponse(
        status="ok",
        due_plan_names=result["due_plan_names"],
        run_count=result["run_count"],
        job_ids=[item["job_id"] for item in result["launched"]],
    )


@router.patch("/scheduler-plans/{plan_name}", response_model=SchedulerPlanResponse)
def update_scheduler_plan(
    plan_name: str,
    payload: SchedulerPlanOverrideRequest,
    session: Session = Depends(get_db_session),
) -> SchedulerPlanResponse:
    base_plans = load_scheduler_plans()
    if plan_name not in base_plans:
        raise HTTPException(status_code=404, detail="scheduler plan not found")

    override = session.scalar(
        select(SchedulerPlanOverride).where(SchedulerPlanOverride.plan_name == plan_name).limit(1)
    )
    if override is None:
        override = SchedulerPlanOverride(plan_name=plan_name, task_overrides_json={})
        session.add(override)

    override.auto_run = payload.auto_run
    override.interval_minutes = payload.interval_minutes
    override.task_overrides_json = {
        item.job_name: {
            key: value
            for key, value in {
                "limit": item.limit,
                "with_details": item.with_details,
                "detect_withdrawn": item.detect_withdrawn,
                "rotation_mode": item.rotation_mode,
                "rotation_step": item.rotation_step,
            }.items()
            if value is not None
        }
        for item in payload.task_overrides
    }
    session.commit()

    merged_plans = load_scheduler_plans(session=session)
    statuses = {item.plan.name: item for item in get_scheduler_plan_statuses(session, plans=merged_plans)}
    plan = merged_plans[plan_name]
    status = statuses[plan_name]
    return SchedulerPlanResponse(
        name=plan.name,
        description=plan.description,
        guideline=_plan_guideline(plan.name, plan.auto_run, plan.interval_minutes),
        auto_run=plan.auto_run,
        interval_minutes=plan.interval_minutes,
        last_started_at=status.last_started_at.isoformat() if status.last_started_at else None,
        last_finished_at=status.last_finished_at.isoformat() if status.last_finished_at else None,
        last_status=status.last_status,
        next_run_at=status.next_run_at.isoformat() if status.next_run_at else None,
        due_now=status.due_now,
        has_override=True,
        tasks=[
            SchedulerTaskResponse(
                job_name=task.job_name,
                source=task.source,
                command=task.command,
                url=task.url,
                language=task.language,
                limit=task.limit,
                with_details=task.with_details,
                detect_withdrawn=task.detect_withdrawn,
                rotation_mode=task.rotation_mode,
                rotation_step=task.rotation_step,
            )
            for task in plan.tasks
        ],
    )


@router.delete("/scheduler-plans/{plan_name}/override", response_model=SchedulerPlanResponse)
def reset_scheduler_plan_override(
    plan_name: str,
    session: Session = Depends(get_db_session),
) -> SchedulerPlanResponse:
    base_plans = load_scheduler_plans()
    if plan_name not in base_plans:
        raise HTTPException(status_code=404, detail="scheduler plan not found")

    override = session.scalar(
        select(SchedulerPlanOverride).where(SchedulerPlanOverride.plan_name == plan_name).limit(1)
    )
    if override is not None:
        session.delete(override)
        session.commit()

    merged_plans = load_scheduler_plans(session=session)
    statuses = {item.plan.name: item for item in get_scheduler_plan_statuses(session, plans=merged_plans)}
    plan = merged_plans[plan_name]
    status = statuses[plan_name]
    return SchedulerPlanResponse(
        name=plan.name,
        description=plan.description,
        guideline=_plan_guideline(plan.name, plan.auto_run, plan.interval_minutes),
        auto_run=plan.auto_run,
        interval_minutes=plan.interval_minutes,
        last_started_at=status.last_started_at.isoformat() if status.last_started_at else None,
        last_finished_at=status.last_finished_at.isoformat() if status.last_finished_at else None,
        last_status=status.last_status,
        next_run_at=status.next_run_at.isoformat() if status.next_run_at else None,
        due_now=status.due_now,
        has_override=False,
        tasks=[
            SchedulerTaskResponse(
                job_name=task.job_name,
                source=task.source,
                command=task.command,
                url=task.url,
                language=task.language,
                limit=task.limit,
                with_details=task.with_details,
                detect_withdrawn=task.detect_withdrawn,
                rotation_mode=task.rotation_mode,
                rotation_step=task.rotation_step,
            )
            for task in plan.tasks
        ],
    )
