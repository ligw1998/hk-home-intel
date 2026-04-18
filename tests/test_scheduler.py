from datetime import datetime, timezone
from pathlib import Path

from hk_home_intel_domain.commercial_discovery import (
    DEFAULT_BEDROOM_ORDER,
    DEFAULT_MAX_BUDGET_HKD,
    DEFAULT_MAX_SALEABLE_AREA_SQFT,
    DEFAULT_MIN_BUDGET_HKD,
    DEFAULT_MIN_SALEABLE_AREA_SQFT,
    _ricacorp_name_hints,
    discover_commercial_monitor_candidates,
    rebalance_auto_discovered_monitors,
)
from hk_home_intel_connectors.ricacorp import RicacorpAdapter
from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.models import CommercialSearchMonitor, Development, RefreshJobRun
from hk_home_intel_domain.monitor_sync import sync_commercial_monitor_config
from hk_home_intel_domain.refresh import (
    _resolve_task_offset,
    execute_commercial_search_monitor_batch,
    execute_commercial_search_monitor_refresh,
    execute_refresh_plan,
)
from hk_home_intel_shared.db import get_engine
from hk_home_intel_shared.models.base import Base
from hk_home_intel_shared.scheduler import get_due_scheduler_plan_names, get_scheduler_plan_statuses, load_scheduler_plans
from sqlalchemy import select
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


def test_sync_commercial_monitor_config_creates_and_updates(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'monitor-sync.db'}")
    Base.metadata.create_all(engine)
    config_path = tmp_path / "commercial_monitors.toml"
    config_path.write_text(
        """
[[monitor]]
source = "centanet"
name = "Sync Test"
search_url = "https://example.com/centanet-search"
scope_type = "development"
development_name_hint = "測試盤"
district = "Kai Tak"
region = "Kowloon"
note = "initial"
is_active = true
with_details = true
detect_withdrawn = false
tags = ["buyer-focus"]

[monitor.criteria]
listing_segments = ["second_hand"]
min_budget_hkd = 8000000
max_budget_hkd = 18000000
bedroom_values = [2, 3, 1, 0]
min_saleable_area_sqft = 400
max_saleable_area_sqft = 750
max_age_years = 10
default_limit = 20
detail_limit = 8
priority_level = 70
detail_policy = "priority_only"
""",
        encoding="utf-8",
    )

    with Session(engine) as session:
        summary = sync_commercial_monitor_config(session, path=config_path)
        assert summary.created == 1
        assert summary.updated == 0
        monitor = session.scalar(select(CommercialSearchMonitor).limit(1))
        assert monitor is not None
        assert monitor.name == "Sync Test"
        assert monitor.criteria_json["max_saleable_area_sqft"] == 750

    config_path.write_text(
        """
[[monitor]]
source = "centanet"
name = "Sync Test Updated"
search_url = "https://example.com/centanet-search"
scope_type = "development"
development_name_hint = "測試盤"
district = "Kai Tak"
region = "Kowloon"
note = "updated"
is_active = true
with_details = false
detect_withdrawn = false
tags = ["buyer-focus", "starter"]

[monitor.criteria]
listing_segments = ["second_hand"]
min_budget_hkd = 8000000
max_budget_hkd = 18000000
bedroom_values = [2, 3, 1, 0]
min_saleable_area_sqft = 400
max_saleable_area_sqft = 750
max_age_years = 15
default_limit = 30
priority_level = 55
detail_policy = "never"
""",
        encoding="utf-8",
    )

    with Session(engine) as session:
        summary = sync_commercial_monitor_config(session, path=config_path)
        assert summary.created == 0
        assert summary.updated == 1
        monitor = session.scalar(select(CommercialSearchMonitor).limit(1))
        assert monitor is not None
        assert monitor.name == "Sync Test Updated"
        assert monitor.with_details is False
        assert monitor.criteria_json["detail_policy"] == "never"


def test_discover_centanet_monitor_candidates_can_validate_and_create(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-centanet.db'}")
    Base.metadata.create_all(engine)
    fixture_html = """
    <html>
      <head><title>買樓｜最新匯璽樓盤 - 中原地產</title></head>
      <body>
        <div>網上搵樓</div>
        <div>出售樓盤 共 0 個</div>
        <div>匯璽 5期 匯璽III 8座 2房</div>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.CentanetAdapter.fetch_search_results_html",
        lambda self, url: fixture_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="匯璽",
                name_en="Cullinan West",
                name_translations_json={"zh-Hant": "匯璽", "zh-Hans": "汇玺", "en": "Cullinan West"},
                aliases_json=["匯璽", "汇玺", "Cullinan West"],
                district="Sham Shui Po",
                region="Kowloon",
                listing_segment="second_hand",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="centanet",
            limit=5,
            validate=True,
            create_monitors=True,
            activate_created=False,
        )

        assert summary.generated == 1
        assert summary.validated == 1
        assert summary.created_monitors == 1
        assert summary.candidates[0].validated is True
        assert summary.candidates[0].search_url.endswith("%E5%8C%AF%E7%92%BD")

        monitor = session.scalar(select(CommercialSearchMonitor).limit(1))
        assert monitor is not None
        assert monitor.source == "centanet"
        assert monitor.is_active is False
        assert monitor.criteria_json["default_limit"] == 20
        assert monitor.criteria_json["detail_policy"] == "never"
        assert monitor.with_details is False


def test_discover_centanet_monitor_candidates_validates_via_page_text(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-centanet-page-text.db'}")
    Base.metadata.create_all(engine)
    html = """
    <html>
      <head><title>買樓｜最新藍塘傲樓盤 - 中原地產</title></head>
      <body>
        <div>網上搵樓</div>
        <div>出售樓盤 共 0 個</div>
        <div>藍塘傲 8座 2房 將軍澳</div>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.CentanetAdapter.fetch_search_results_html",
        lambda self, url: html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-002",
                source_url="https://www.srpe.gov.hk/",
                name_zh="藍塘傲",
                aliases_json=["藍塘傲"],
                district="Tseung Kwan O",
                region="New Territories",
                listing_segment="second_hand",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="centanet",
            limit=3,
            validate=True,
            create_monitors=False,
        )

        assert summary.generated == 1
        assert summary.validated == 1
        assert summary.candidates[0].validated is True


def test_discover_centanet_monitor_candidates_validates_via_canonical_and_detail_links(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-centanet-link-signals.db'}")
    Base.metadata.create_all(engine)
    html = """
    <html>
      <head>
        <title>買樓｜最新樓盤 - 中原地產</title>
        <link rel="canonical" href="/findproperty/list/buy/NOVO%20LAND">
      </head>
      <body>
        <div>網上搵樓</div>
        <div>出售樓盤 共 12 個</div>
        <a href="https://hk.centanet.com/findproperty/detail/NOVO-LAND_CZH123">Open detail</a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.CentanetAdapter.fetch_search_results_html",
        lambda self, url: html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-003",
                source_url="https://www.srpe.gov.hk/",
                name_en="NOVO LAND",
                aliases_json=["NOVO LAND"],
                district="Tuen Mun",
                region="New Territories",
                listing_segment="first_hand_remaining",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="centanet",
            limit=3,
            validate=True,
            create_monitors=False,
        )

        assert summary.generated == 1
        assert summary.validated == 1
        assert summary.candidates[0].validated is True


def test_discover_centanet_monitor_candidates_create_search_only_monitor_without_listing_signal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-centanet-search-only.db'}")
    Base.metadata.create_all(engine)
    html = """
    <html>
      <head>
        <title>買樓｜最新樓盤 - 中原地產</title>
        <link rel="canonical" href="/findproperty/list/buy/THE%20RICHMOND">
      </head>
      <body>
        <div>網上搵樓</div>
        <div>出售樓盤 共 8 個</div>
        <a href="https://hk.centanet.com/findproperty/detail/THE-RICHMOND_CZH123">Open detail</a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.CentanetAdapter.fetch_search_results_html",
        lambda self, url: html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-004",
                source_url="https://www.srpe.gov.hk/",
                name_en="THE RICHMOND",
                aliases_json=["THE RICHMOND"],
                district="Mid-Levels West",
                region="Hong Kong Island",
                listing_segment="first_hand_remaining",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="centanet",
            limit=3,
            validate=True,
            create_monitors=True,
            activate_created=False,
        )

        assert summary.generated == 1
        assert summary.validated == 1
        monitor = session.scalar(select(CommercialSearchMonitor).limit(1))
        assert monitor is not None
        assert monitor.with_details is False
        assert monitor.criteria_json["detail_policy"] == "never"
        assert monitor.criteria_json["priority_level"] == 58


def test_rebalance_auto_discovered_monitors_updates_existing_centanet_monitor_without_listing_signal(
    tmp_path: Path,
) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor-rebalance.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        development = Development(
            source="srpe",
            source_external_id="srpe-005",
            source_url="https://www.srpe.gov.hk/",
            name_en="THE RICHMOND",
            aliases_json=["THE RICHMOND"],
            district="Mid-Levels West",
            region="Hong Kong Island",
            listing_segment="first_hand_remaining",
            source_confidence="high",
        )
        session.add(development)
        session.flush()
        session.add(
            CommercialSearchMonitor(
                source="centanet",
                name="THE RICHMOND auto-discovered search",
                search_url="https://hk.centanet.com/findproperty/list/buy/THE%20RICHMOND",
                scope_type="development_auto",
                development_name_hint="THE RICHMOND",
                district="Mid-Levels West",
                region="Hong Kong Island",
                note="Auto-discovered from development pool.",
                is_active=False,
                with_details=True,
                detect_withdrawn=False,
                tags_json=["auto-discovered", "buyer-focus"],
                criteria_json={
                    "listing_segments": ["first_hand_remaining"],
                    "min_budget_hkd": DEFAULT_MIN_BUDGET_HKD,
                    "max_budget_hkd": DEFAULT_MAX_BUDGET_HKD,
                    "bedroom_values": list(DEFAULT_BEDROOM_ORDER),
                    "min_saleable_area_sqft": DEFAULT_MIN_SALEABLE_AREA_SQFT,
                    "max_saleable_area_sqft": DEFAULT_MAX_SALEABLE_AREA_SQFT,
                    "default_limit": 20,
                    "detail_limit": 8,
                    "priority_level": 70,
                    "detail_policy": "priority_only",
                },
            )
        )
        session.commit()

        summary = rebalance_auto_discovered_monitors(session, source="centanet")

        assert summary.scanned == 1
        assert summary.updated == 1
        monitor = session.scalar(select(CommercialSearchMonitor).limit(1))
        assert monitor is not None
        assert monitor.with_details is False
        assert monitor.criteria_json["detail_policy"] == "never"
        assert monitor.criteria_json["priority_level"] == 58


def test_discover_ricacorp_monitor_candidates_can_validate(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <a href="/zh-hk/property/estate/%E9%80%B8%E7%93%8F-estate-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk">
          <img alt="逸瓏" />
          <span class="location-text">逸瓏</span>
          <span class="zone-text">九龍塘</span>
        </a>
      </body>
    </html>
    """
    estate_page_html = """
    <html>
      <head>
        <title>逸瓏 - 屋苑專頁 | 真盤源 - 利嘉閣地產</title>
      </head>
      <body>
        <rc-estate-post-listing>
          <span class="location-name">逸瓏</span>
        </rc-estate-post-listing>
        <a class="post-total-count" href="list/buy/%E9%80%B8%E7%93%8F-estate-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk">售盤</a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )
    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_search_results_html",
        lambda self, url: estate_page_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-rica-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="逸瓏",
                name_translations_json={"zh-Hant": "逸瓏", "zh-Hans": "逸珑"},
                aliases_json=["逸瓏", "逸珑"],
                district="Kowloon Tong",
                region="Kowloon",
                listing_segment="second_hand",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="ricacorp",
            limit=5,
            validate=True,
            create_monitors=False,
        )

        assert summary.generated == 1
        assert summary.validated == 1
        assert summary.created_monitors == 0
        assert summary.candidates[0].validated is True
        assert summary.candidates[0].search_url.endswith("/property/list/buy/%E9%80%B8%E7%93%8F-estate-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk")


def test_ricacorp_name_hints_include_parent_estate_candidates() -> None:
    item = Development(
        source="centanet",
        source_external_id="dummy",
        source_url="https://example.test",
        name_zh="港島南岸   3B",
        name_en="THE SOUTHSIDE - BLUE COAST",
        aliases_json=["港島南岸   3B"],
    )

    hints = _ricacorp_name_hints(item)

    assert "港島南岸" in hints
    assert "THE SOUTHSIDE" in hints


def test_ricacorp_extract_estate_buy_list_url_can_fallback_to_server_state() -> None:
    adapter = RicacorpAdapter()
    html_text = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;alias&q;:&q;又一居-estate-九龍塘-hma-hk&q;,&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:12}]}
        </script>
      </body>
    </html>
    """

    buy_list_url = adapter.extract_estate_buy_list_url(
        html_text,
        estate_url="https://www.ricacorp.com/zh-hk/property/estate/%E5%8F%88%E4%B8%80%E5%B1%85",
    )

    assert buy_list_url == "https://www.ricacorp.com/zh-hk/property/list/buy/%E5%8F%88%E4%B8%80%E5%B1%85-bigest-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk"
