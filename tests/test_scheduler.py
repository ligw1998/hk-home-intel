from datetime import datetime, timezone
from pathlib import Path

from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.models import CommercialSearchMonitor, RefreshJobRun
from hk_home_intel_domain.refresh import (
    _resolve_task_offset,
    execute_commercial_search_monitor_batch,
    execute_commercial_search_monitor_refresh,
    execute_refresh_plan,
)
from hk_home_intel_shared.db import get_engine
from hk_home_intel_shared.models.base import Base
from hk_home_intel_shared.scheduler import get_due_scheduler_plan_names, get_scheduler_plan_statuses, load_scheduler_plans
from sqlalchemy.orm import Session


def test_load_scheduler_plans_reads_expected_tasks() -> None:
    plans = load_scheduler_plans(Path("configs/scheduler.toml"))

    assert "daily_local" in plans
    assert "watchlist_probe" in plans
    assert "centanet_probe" in plans
    assert plans["daily_local"].tasks[0].command == "srpe_refresh"
    assert plans["daily_local"].tasks[0].with_details is True
    assert plans["daily_local"].tasks[0].rotation_mode == "cycle"
    assert plans["daily_local"].tasks[0].rotation_step == 20
    assert plans["watchlist_probe"].tasks[0].limit == 5
    assert plans["centanet_probe"].tasks[0].command == "centanet_search_refresh"
    assert plans["centanet_probe"].tasks[0].url
    assert plans["centanet_probe"].tasks[0].with_details is True
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


def test_execute_refresh_plan_dispatches_centanet_probe(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'centanet-plan.db'}")
    Base.metadata.create_all(engine)

    def fake_centanet_refresh(
        session,
        *,
        url: str,
        limit: int | None,
        with_details: bool,
        detect_withdrawn: bool,
        trigger_kind: str = "manual",
        job_name: str = "centanet_search_refresh",
    ):
        return {
            "job_id": "job-centanet-test",
            "source": "centanet",
            "url": url,
            "limit": limit,
            "with_details": with_details,
            "detect_withdrawn": detect_withdrawn,
            "developments_created": 0,
            "developments_updated": 1,
            "documents_upserted": 0,
            "listings_upserted": 3,
            "transactions_upserted": 0,
            "price_events_created": 2,
            "snapshots_created": 1,
        }

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.execute_centanet_search_refresh",
        fake_centanet_refresh,
    )

    with Session(engine) as session:
        result = execute_refresh_plan(session, plan_name="centanet_probe", trigger_kind="manual")

    assert result["plan"] == "centanet_probe"
    assert result["task_count"] == 1
    assert result["results"][0]["source"] == "centanet"
    assert result["results"][0]["listings_upserted"] == 3


def test_execute_commercial_search_monitor_refresh_dispatches_centanet_import(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor.db'}")
    Base.metadata.create_all(engine)
    captured: dict[str, object] = {}

    def fake_import(
        session,
        *,
        url: str,
        html_path=None,
        limit=None,
        with_details=False,
        detail_limit=None,
        save_detail_snapshots=False,
        detect_withdrawn=False,
    ):
        captured.update(
            {
                "url": url,
                "limit": limit,
                "with_details": with_details,
                "detail_limit": detail_limit,
                "detect_withdrawn": detect_withdrawn,
            }
        )
        class Summary:
            source = "centanet"
            developments_created = 1
            developments_updated = 0
            documents_upserted = 0
            listings_upserted = 4
            transactions_upserted = 0
            price_events_created = 2
            snapshots_created = 3
            detail_failures = 0

        return Summary()

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.import_centanet_search_results",
        fake_import,
    )

    with Session(engine) as session:
        monitor = CommercialSearchMonitor(
            source="centanet",
            name="Cullinan West",
            search_url="https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            scope_type="development",
            development_name_hint="匯璽",
            is_active=True,
            with_details=True,
            detect_withdrawn=False,
            criteria_json={"default_limit": 20, "detail_limit": 8},
        )
        session.add(monitor)
        session.commit()
        result = execute_commercial_search_monitor_refresh(session, monitor_id=monitor.id, limit_override=None)

    assert result["source"] == "centanet"
    assert result["monitor_name"] == "Cullinan West"
    assert result["listings_upserted"] == 4
    assert result["limit"] == 20
    assert result["detail_limit"] == 8
    assert captured == {
        "url": "https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
        "limit": 20,
        "with_details": True,
        "detail_limit": 8,
        "detect_withdrawn": False,
    }


def test_execute_commercial_search_monitor_refresh_respects_priority_only_detail_policy(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor-priority.db'}")
    Base.metadata.create_all(engine)
    captured: dict[str, object] = {}

    def fake_import(
        session,
        *,
        url: str,
        html_path=None,
        limit=None,
        with_details=False,
        detail_limit=None,
        save_detail_snapshots=False,
        detect_withdrawn=False,
    ):
        captured.update(
            {
                "limit": limit,
                "with_details": with_details,
                "detail_limit": detail_limit,
            }
        )
        class Summary:
            source = "centanet"
            developments_created = 0
            developments_updated = 1
            documents_upserted = 0
            listings_upserted = 2
            transactions_upserted = 0
            price_events_created = 0
            snapshots_created = 1
            detail_failures = 0

        return Summary()

    monkeypatch.setattr("hk_home_intel_domain.refresh.import_centanet_search_results", fake_import)

    with Session(engine) as session:
        monitor = CommercialSearchMonitor(
            source="centanet",
            name="Low priority detail gate",
            search_url="https://example.test/priority",
            is_active=True,
            with_details=True,
            criteria_json={"default_limit": 15, "detail_limit": 5, "priority_level": 40, "detail_policy": "priority_only"},
        )
        session.add(monitor)
        session.commit()
        result = execute_commercial_search_monitor_refresh(session, monitor_id=monitor.id)

    assert result["with_details"] is False
    assert result["detail_limit"] is None
    assert result["detail_policy"] == "priority_only"
    assert captured == {"limit": 15, "with_details": False, "detail_limit": None}


def test_execute_commercial_search_monitor_refresh_dispatches_ricacorp_import(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor-ricacorp.db'}")
    Base.metadata.create_all(engine)

    def fake_import(
        session,
        *,
        url: str,
        html_path=None,
        limit=None,
    ):
        class Summary:
            source = "ricacorp"
            developments_created = 2
            developments_updated = 0
            documents_upserted = 0
            listings_upserted = 5
            transactions_upserted = 0
            price_events_created = 5
            snapshots_created = 1
            detail_failures = 0

        return Summary()

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.import_ricacorp_search_results",
        fake_import,
    )

    with Session(engine) as session:
        monitor = CommercialSearchMonitor(
            source="ricacorp",
            name="Ricacorp Buy Feed",
            search_url="https://www.ricacorp.com/zh-hk/property/list/buy",
            scope_type="district",
            district="Kowloon",
            is_active=True,
            with_details=False,
        )
        session.add(monitor)
        session.commit()
        result = execute_commercial_search_monitor_refresh(session, monitor_id=monitor.id, limit_override=5)

    assert result["source"] == "ricacorp"
    assert result["monitor_name"] == "Ricacorp Buy Feed"
    assert result["listings_upserted"] == 5


def test_execute_commercial_search_monitor_batch_runs_active_monitors(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor-batch.db'}")
    Base.metadata.create_all(engine)
    calls: list[str] = []

    def fake_execute(
        session,
        *,
        monitor_id: str,
        limit_override=None,
        trigger_kind="manual",
        job_name=None,
        job_id=None,
        allow_inactive=False,
    ):
        calls.append(monitor_id)
        return {
            "job_id": f"job-{monitor_id}",
            "source": "centanet",
            "monitor_id": monitor_id,
            "monitor_name": "test",
            "url": "https://example.test",
            "limit": limit_override,
            "with_details": True,
            "detect_withdrawn": False,
            "developments_created": 0,
            "developments_updated": 1,
            "documents_upserted": 0,
            "listings_upserted": 2,
            "transactions_upserted": 0,
            "price_events_created": 1,
            "snapshots_created": 1,
        }

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.execute_commercial_search_monitor_refresh",
        fake_execute,
    )

    with Session(engine) as session:
        session.add(
            CommercialSearchMonitor(
                source="centanet",
                name="Active A",
                search_url="https://example.test/a",
                is_active=True,
            )
        )
        session.add(
            CommercialSearchMonitor(
                source="centanet",
                name="Inactive B",
                search_url="https://example.test/b",
                is_active=False,
            )
        )
        session.commit()
        result = execute_commercial_search_monitor_batch(session, source="centanet", active_only=True)

    assert result["source"] == "centanet"
    assert result["monitor_count"] == 1
    assert len(calls) == 1
