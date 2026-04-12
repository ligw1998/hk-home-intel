from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tomllib

from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import RefreshJobRun, SchedulerPlanOverride
from hk_home_intel_shared.settings import get_settings


@dataclass(slots=True)
class RefreshTaskConfig:
    job_name: str
    source: str
    command: str
    language: str = "en"
    limit: int | None = None
    with_details: bool = False
    rotation_mode: str = "none"
    rotation_step: int | None = None


@dataclass(slots=True)
class RefreshPlanConfig:
    name: str
    description: str
    tasks: list[RefreshTaskConfig]
    auto_run: bool = False
    interval_minutes: int | None = None


@dataclass(slots=True)
class RefreshPlanStatus:
    plan: RefreshPlanConfig
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_status: str | None
    next_run_at: datetime | None
    due_now: bool


def load_scheduler_plans(path: Path | None = None, session: Session | None = None) -> dict[str, RefreshPlanConfig]:
    settings = get_settings()
    config_path = path or settings.config_root / "scheduler.toml"
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    result: dict[str, RefreshPlanConfig] = {}
    for plan_name, plan_payload in (payload.get("plans") or {}).items():
        tasks = [
            RefreshTaskConfig(
                job_name=item["job_name"],
                source=item["source"],
                command=item["command"],
                language=item.get("language", "en"),
                limit=item.get("limit"),
                with_details=bool(item.get("with_details", False)),
                rotation_mode=item.get("rotation_mode", "none"),
                rotation_step=item.get("rotation_step"),
            )
            for item in plan_payload.get("tasks", [])
        ]
        result[plan_name] = RefreshPlanConfig(
            name=plan_name,
            description=plan_payload.get("description", ""),
            tasks=tasks,
            auto_run=bool(plan_payload.get("auto_run", False)),
            interval_minutes=plan_payload.get("interval_minutes"),
        )
    if session is not None:
        _apply_scheduler_overrides(result, session)
    return result


def _apply_scheduler_overrides(
    plans: dict[str, RefreshPlanConfig],
    session: Session,
) -> None:
    overrides = session.scalars(select(SchedulerPlanOverride)).all()
    for override in overrides:
        plan = plans.get(override.plan_name)
        if plan is None:
            continue
        if override.auto_run is not None:
            plan.auto_run = override.auto_run
        if override.interval_minutes is not None:
            plan.interval_minutes = override.interval_minutes
        task_overrides = override.task_overrides_json or {}
        for task in plan.tasks:
            task_override = task_overrides.get(task.job_name) or {}
            if "limit" in task_override:
                task.limit = task_override["limit"]
            if "with_details" in task_override:
                task.with_details = bool(task_override["with_details"])
            if "rotation_mode" in task_override:
                task.rotation_mode = task_override["rotation_mode"]
            if "rotation_step" in task_override:
                task.rotation_step = task_override["rotation_step"]


def coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_scheduler_plan_statuses(
    session: Session,
    *,
    plans: dict[str, RefreshPlanConfig] | None = None,
    now: datetime | None = None,
) -> list[RefreshPlanStatus]:
    loaded_plans = plans or load_scheduler_plans()
    current_time = coerce_utc(now) or datetime.now(timezone.utc)
    statuses: list[RefreshPlanStatus] = []

    for plan in loaded_plans.values():
        latest_job = session.scalar(
            select(RefreshJobRun)
            .where(RefreshJobRun.job_name == f"refresh_plan:{plan.name}")
            .order_by(RefreshJobRun.started_at.desc())
            .limit(1)
        )
        last_started_at = coerce_utc(latest_job.started_at) if latest_job is not None else None
        last_finished_at = coerce_utc(latest_job.finished_at) if latest_job is not None else None
        next_run_at = None
        due_now = False
        if plan.auto_run and plan.interval_minutes is not None:
            if last_started_at is None:
                due_now = True
            else:
                next_run_at = last_started_at + timedelta(minutes=plan.interval_minutes)
                due_now = next_run_at <= current_time
        statuses.append(
            RefreshPlanStatus(
                plan=plan,
                last_started_at=last_started_at,
                last_finished_at=last_finished_at,
                last_status=latest_job.status.value if latest_job is not None else None,
                next_run_at=next_run_at,
                due_now=due_now,
            )
        )

    return statuses


def get_due_scheduler_plan_names(
    session: Session,
    *,
    plans: dict[str, RefreshPlanConfig] | None = None,
    now: datetime | None = None,
) -> list[str]:
    statuses = get_scheduler_plan_statuses(session, plans=plans, now=now)
    return [status.plan.name for status in statuses if status.due_now]
