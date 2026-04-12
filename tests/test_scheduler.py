from datetime import datetime, timezone
from pathlib import Path

from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.models import RefreshJobRun
from hk_home_intel_domain.refresh import _resolve_task_offset
from hk_home_intel_shared.db import get_engine
from hk_home_intel_shared.models.base import Base
from hk_home_intel_shared.scheduler import get_due_scheduler_plan_names, get_scheduler_plan_statuses, load_scheduler_plans
from sqlalchemy.orm import Session


def test_load_scheduler_plans_reads_expected_tasks() -> None:
    plans = load_scheduler_plans(Path("configs/scheduler.toml"))

    assert "daily_local" in plans
    assert "watchlist_probe" in plans
    assert plans["daily_local"].tasks[0].command == "srpe_refresh"
    assert plans["daily_local"].tasks[0].with_details is True
    assert plans["daily_local"].tasks[0].rotation_mode == "cycle"
    assert plans["daily_local"].tasks[0].rotation_step == 20
    assert plans["watchlist_probe"].tasks[0].limit == 5
    assert plans["daily_local"].auto_run is True
    assert plans["daily_local"].interval_minutes == 1440


def test_scheduler_status_marks_daily_plan_due_without_history(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)
    plans = load_scheduler_plans(Path("configs/scheduler.toml"))

    with Session(engine) as session:
        statuses = get_scheduler_plan_statuses(session, plans=plans)

    status_by_name = {item.plan.name: item for item in statuses}
    assert status_by_name["daily_local"].due_now is True
    assert status_by_name["watchlist_probe"].due_now is False


def test_scheduler_due_names_skip_recent_daily_run(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'scheduler-history.db'}")
    Base.metadata.create_all(engine)
    plans = load_scheduler_plans(Path("configs/scheduler.toml"))

    with Session(engine) as session:
        session.add(
            RefreshJobRun(
                job_name="refresh_plan:daily_local",
                source=None,
                trigger_kind="scheduler",
                status=JobRunStatus.SUCCEEDED,
                started_at=datetime(2026, 4, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 4, 12, 0, 5, tzinfo=timezone.utc),
            )
        )
        session.commit()
        due_names = get_due_scheduler_plan_names(
            session,
            plans=plans,
            now=datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc),
        )

    assert due_names == []


def test_rotation_offset_advances_with_successful_task_runs(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'rotation.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            RefreshJobRun(
                job_name="daily_local:srpe_refresh",
                source="srpe",
                trigger_kind="plan",
                status=JobRunStatus.SUCCEEDED,
            )
        )
        session.add(
            RefreshJobRun(
                job_name="daily_local:srpe_refresh",
                source="srpe",
                trigger_kind="plan",
                status=JobRunStatus.SUCCEEDED,
            )
        )
        session.commit()

        offset = _resolve_task_offset(
            session,
            plan_name="daily_local",
            task_job_name="srpe_refresh",
            limit=20,
            rotation_mode="cycle",
            rotation_step=20,
        )

    assert offset == 40
