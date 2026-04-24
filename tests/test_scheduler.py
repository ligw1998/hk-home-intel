from datetime import datetime, timezone
from pathlib import Path

from hk_home_intel_domain.commercial_discovery import (
    DEFAULT_BEDROOM_ORDER,
    DEFAULT_MAX_BUDGET_HKD,
    DEFAULT_MAX_SALEABLE_AREA_SQFT,
    DEFAULT_MIN_BUDGET_HKD,
    DEFAULT_MIN_SALEABLE_AREA_SQFT,
    _has_name_key_match,
    _ricacorp_name_hints,
    discover_commercial_monitor_candidates,
    rebalance_auto_discovered_monitors,
    set_commercial_monitors_active_state,
)
from hk_home_intel_connectors.ricacorp import RicacorpAdapter
from hk_home_intel_domain.launch_watch import (
    parse_landsd_issued_pdf_text,
    parse_landsd_pending_approval_pdf_text,
    sync_launch_watch_config,
    sync_launch_watch_landsd_issued,
    sync_launch_watch_landsd_pending_approval,
    sync_launch_watch_srpe_active_first_hand,
    sync_launch_watch_srpe_recent_documents,
)
from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.models import CommercialSearchMonitor, Development, LaunchWatchProject, RefreshJobRun
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
from hk_home_intel_shared.db import get_session_factory, reset_db_caches
from hk_home_intel_shared.settings import clear_settings_cache
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_load_scheduler_plans_reads_expected_tasks() -> None:
    plans = load_scheduler_plans(Path("configs/scheduler.toml"))

    assert "daily_local" in plans
    assert "watchlist_probe" in plans
    assert "centanet_probe" in plans
    assert "commercial_daily" in plans
    assert "launch_watch_daily" in plans
    assert "ricacorp_probe" in plans
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
    assert plans["commercial_daily"].tasks[0].command == "commercial_monitor_batch"
    assert plans["commercial_daily"].tasks[1].source == "ricacorp"
    assert plans["launch_watch_daily"].tasks[0].command == "launch_watch_official"
    assert plans["ricacorp_probe"].tasks[0].command == "ricacorp_search_refresh"


def test_sync_launch_watch_config_creates_projects(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "launch-watch.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Development(
                id="dev-test-launch",
                source="srpe",
                source_external_id="11365",
                source_url="https://www.srpe.gov.hk/test-launch",
                name_zh="測試新盤",
                name_en="Test Launch",
                aliases_json=["Test Launch"],
                source_confidence="high",
            )
        )
        session.commit()

    config_path = tmp_path / "launch_watch.toml"
    config_path.write_text(
        """
[[project]]
source = "manual"
project_name = "測試新盤"
project_name_en = "Test Launch"
district = "Kai Tak"
region = "Kowloon"
expected_launch_window = "2026-2027"
launch_stage = "launch_watch"
source_url = "https://example.com/watch"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "hk_home_intel_domain.launch_watch.SRPEAdapter.fetch_selected_development_result",
        lambda self, development_id, language="en": {"dev": {"website": "https://www.test-launch.example"}},
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = sync_launch_watch_config(session, path=config_path, dry_run=False)
        created = session.scalar(select(func.count()).select_from(LaunchWatchProject))
        project = session.scalar(select(LaunchWatchProject).limit(1))

    assert summary.processed == 1
    assert summary.created == 1
    assert created == 1
    assert project is not None
    assert project.linked_development_id == "dev-test-launch"
    assert project.srpe_url == "https://www.srpe.gov.hk/test-launch"
    assert project.official_site_url == "https://www.test-launch.example"

    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_parse_landsd_pending_approval_pdf_text_extracts_project_rows() -> None:
    sample_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
1
Lands Department
Lot No.
Address
Development
Name
Vendor
CWIL 178
No. 99 Sheung
On Street,
Chai Wan,
Hong Kong
(Provisional)
Phase 2 of
THE
HEADLAND
RESIDENCES
Joyful Sincere
Limited
28/02/2027 258 --
Lot 385 RP
in DD 352
& Exts
Pending Phase 19-2A of
Discovery Bay
City
Hong Kong
Resort
Company
Limited
31/07/2027 170 --
    """.strip()

    rows = parse_landsd_pending_approval_pdf_text(sample_text)

    assert len(rows) == 2
    assert rows[0]["project_name"] == "Phase 2 of THE HEADLAND RESIDENCES"
    assert rows[0]["unit_count"] == 258
    assert rows[0]["estimated_completion_date"].isoformat() == "2027-02-28"
    assert rows[1]["project_name"] == "Pending Phase 19-2A of Discovery Bay City"
    assert rows[1]["unit_count"] == 170


def test_parse_landsd_pending_approval_pdf_text_dedupes_repeated_control_rows() -> None:
    sample_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
NKIL 6458 RP
Pending
(Phase 1)
Vendor Limited
30/11/2026 361 --
NKIL 6458 RP
Pending NKIL 6458 RP
Vendor Limited
30/11/2026 361 --
RBL 1211
No. 2 Mansfield Road,
Hong Kong
Pending
(Phase 2)
Vendor Limited
31/12/2027 22 --
RBL 1211
No. 2 Mansfield Road,
Hong Kong
Pending RBL 1211
Vendor Limited
31/12/2027 22 --
    """.strip()

    rows = parse_landsd_pending_approval_pdf_text(sample_text)

    assert len(rows) == 2
    assert {row["unit_count"] for row in rows} == {361, 22}


def test_parse_landsd_pending_approval_pdf_text_handles_page_header_after_row() -> None:
    sample_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
CWIL 178
No. 99 Sheung On Street,
Chai Wan,
Hong Kong
(Provisional)
Phase 2 of THE HEADLAND RESIDENCES
Joyful Sincere Limited
28/02/2027 258 --Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
Lot 1071 in DD 103
No. 1A Ying Ho Road,
New Territories
(Provisional)
Pending
Ease Gold Development Limited
30/04/2027 566 --
    """.strip()

    rows = parse_landsd_pending_approval_pdf_text(sample_text)

    assert len(rows) == 2
    assert rows[0]["unit_count"] == 258
    assert rows[1]["unit_count"] == 566


def test_parse_landsd_pending_approval_pdf_text_handles_split_date_and_units() -> None:
    sample_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
CWIL 178
No. 99 Sheung On Street,
Chai Wan,
Hong Kong
(Provisional)
Phase 2 of THE HEADLAND RESIDENCES
Joyful Sincere Limited
28/02/2027
258 --
Lot 1071 in DD 103
No. 1A Ying Ho Road,
New Territories
(Provisional)
Pending
Ease Gold Development Limited
30/04/2027
566 --
    """.strip()

    rows = parse_landsd_pending_approval_pdf_text(sample_text)

    assert len(rows) == 2
    assert rows[0]["unit_count"] == 258
    assert rows[1]["unit_count"] == 566


def test_parse_landsd_pending_approval_pdf_text_handles_prefixed_date_units() -> None:
    sample_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
YTIL 46 RP
Pending
(Phase 1)
Charm Smart Development Limited
-- Industrial Bank Co., Ltd.
-- 30/12/2028 617 --
YTIL 47 RP
Pending
(Phase 2)
Charm Smart Development Limited
-- China CITIC Bank International Limited
-- 30/12/2028 617 --Particulars of applications for Presale Consent and Consent to Assign pending approval
    """.strip()

    rows = parse_landsd_pending_approval_pdf_text(sample_text)

    assert len(rows) == 2
    assert [row["unit_count"] for row in rows] == [617, 617]


def test_parse_landsd_issued_pdf_text_extracts_presale_and_assign_rows() -> None:
    sample_text = """
Particulars of Presale Consent and Consent to Assign issued
for the period from 01/03/2026 to 31/03/2026
Presale Consent for Residential Development
NKIL 6638
No. 79 Broadcast Drive,
Kowloon Tong,
Kowloon
Pending
Gainful Limited
(a) 19/03/2026
(b) 19/03/2026
(c) 30/09/2026
195 46 --
Presale Consent for Non-Residential Development
NIL
Consent to Assign for Residential / Non-Residential Development
AIL 467
No. 11 Heung Yip Road,
Hong Kong
(Provisional)
THE SOUTHSIDE
(Phase 3C – BLUE COAST II)
MTR Corporation Limited
(a) 23/03/2026
(b) 23/03/2026
(c) 558
(d) --
(e) --
(f) --
--
TKOTL 70 RP
No. 1 Lohas Park Road,
Tseung Kwan O,
New Territories
Phase XIIC of LOHAS Park
– GRAND SEASONS
MTR Corporation Limited
(a) 25/03/2026
(b) 25/03/2026
(c) 650
(d) --
(e) --
(f) --
--
    """.strip()

    rows = parse_landsd_issued_pdf_text(sample_text)

    assert len(rows) == 3
    assert rows[0]["source"] == "landsd_presale_issued"
    assert rows[0]["project_name"].startswith("Pending")
    assert rows[0]["unit_count"] == 46
    assert rows[1]["source"] == "landsd_assign_issued"
    assert rows[1]["project_name"] == "THE SOUTHSIDE (Phase 3C – BLUE COAST II)"
    assert rows[1]["unit_count"] == 558
    assert rows[2]["project_name"] == "Phase XIIC of LOHAS Park – GRAND SEASONS"


def test_sync_launch_watch_landsd_issued_creates_projects(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "launch-watch-issued.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    current_year = datetime.now().year

    session_factory = get_session_factory()
    with session_factory() as session:
        session.add_all(
            [
                Development(
                    id="dev-blue-coast-2",
                    source="srpe",
                    source_external_id="10001",
                    name_en="BLUE COAST II",
                    aliases_json=["THE SOUTHSIDE (Phase 3C – BLUE COAST II)"],
                    source_url="https://www.srpe.gov.hk/the-southside-blue-coast-2",
                ),
                Development(
                    id="dev-grand-seasons",
                    source="srpe",
                    source_external_id="10002",
                    name_en="GRAND SEASONS",
                    aliases_json=["Phase XIIC of LOHAS Park – GRAND SEASONS"],
                    source_url="https://www.srpe.gov.hk/grand-seasons",
                ),
            ]
        )
        session.commit()

    index_html = """
    <a href="/en/resources/land-info-stat/dev-control-compliance/consent/presale/202603.html">March 2026</a>
    """.strip()
    report_html = """
    <a href="/doc/en/consent/monthly/t1_2603.pdf">Table 1</a>
    """.strip()
    pdf_text = """
Particulars of Presale Consent and Consent to Assign issued
for the period from 01/03/2026 to 31/03/2026
Presale Consent for Residential Development
NKIL 6638
No. 79 Broadcast Drive,
Kowloon Tong,
Kowloon
Pending
Gainful Limited
(a) 19/03/2026
(b) 19/03/2026
(c) 30/09/2026
195 46 --
Presale Consent for Non-Residential Development
NIL
Consent to Assign for Residential / Non-Residential Development
AIL 467
No. 11 Heung Yip Road,
Hong Kong
(Provisional)
THE SOUTHSIDE
(Phase 3C – BLUE COAST II)
MTR Corporation Limited
(a) 23/03/2026
(b) 23/03/2026
(c) 558
(d) --
(e) --
(f) --
--
TKOTL 70 RP
No. 1 Lohas Park Road,
Tseung Kwan O,
New Territories
Phase XIIC of LOHAS Park
– GRAND SEASONS
MTR Corporation Limited
(a) 25/03/2026
(b) 25/03/2026
(c) 650
(d) --
(e) --
(f) --
--
    """.strip()

    def fake_fetch_text(url: str, timeout: float = 20.0) -> str:
        if url.endswith("presale.html"):
            return index_html
        if url.endswith("202603.html"):
            return report_html
        raise AssertionError(url)

    monkeypatch.setattr("hk_home_intel_domain.launch_watch.fetch_text", fake_fetch_text)
    monkeypatch.setattr("hk_home_intel_domain.launch_watch._extract_pdf_text_from_url", lambda url: pdf_text)
    monkeypatch.setattr(
        "hk_home_intel_domain.launch_watch.SRPEAdapter.fetch_selected_development_result",
        lambda self, development_id, language="en": {
            "dev": {
                "website": {
                    "10001": "www.bluecoast2.example",
                    "10002": "www.grandseasons.example",
                }.get(str(development_id))
            }
        },
    )

    with session_factory() as session:
        summary = sync_launch_watch_landsd_issued(session, dry_run=False)
        created = session.scalar(select(func.count()).select_from(LaunchWatchProject))
        projects = session.scalars(select(LaunchWatchProject).order_by(LaunchWatchProject.project_name)).all()

    assert summary.source == "landsd_issued"
    assert summary.processed == 3
    assert summary.created == 3
    assert created == 3
    assert any(project.source == "landsd_presale_issued" for project in projects)
    assert any(project.linked_development_id == "dev-blue-coast-2" for project in projects)
    assert any(project.linked_development_id == "dev-grand-seasons" for project in projects)
    blue_coast = next(project for project in projects if project.linked_development_id == "dev-blue-coast-2")
    grand_seasons = next(project for project in projects if project.linked_development_id == "dev-grand-seasons")
    assert blue_coast.official_site_url == "https://www.bluecoast2.example"
    assert blue_coast.srpe_url == "https://www.srpe.gov.hk/the-southside-blue-coast-2"
    assert grand_seasons.official_site_url == "https://www.grandseasons.example"
    assert grand_seasons.srpe_url == "https://www.srpe.gov.hk/grand-seasons"

    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_sync_launch_watch_landsd_pending_approval_creates_projects(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "launch-watch-official.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    current_year = datetime.now().year

    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            Development(
                id="dev-headland",
                source="srpe",
                source_external_id="10003",
                name_zh="海德園",
                name_en="THE HEADLAND RESIDENCES",
                source_url="https://www.srpe.gov.hk/the-headland",
            )
        )
        session.commit()

    index_html = """
    <a href="/en/resources/land-info-stat/dev-control-compliance/consent/presale/202603.html">March 2026</a>
    """.strip()
    report_html = """
    <a href="/doc/en/consent/monthly/t2_2603.pdf">Table 2</a>
    """.strip()
    pdf_text = """
Particulars of applications for Presale Consent and Consent to Assign pending approval
as at 31/03/2026
CWIL 178
No. 99 Sheung On Street,
Chai Wan,
Hong Kong
(Provisional)
Phase 2 of THE HEADLAND RESIDENCES
Joyful Sincere Limited
28/02/2027 258 --
    """.strip()

    def fake_fetch_text(url: str, timeout: float = 20.0) -> str:
        if url.endswith("presale.html"):
            return index_html
        if url.endswith("202603.html"):
            return report_html
        raise AssertionError(url)

    monkeypatch.setattr("hk_home_intel_domain.launch_watch.fetch_text", fake_fetch_text)
    monkeypatch.setattr("hk_home_intel_domain.launch_watch._extract_pdf_text_from_url", lambda url: pdf_text)
    monkeypatch.setattr(
        "hk_home_intel_domain.launch_watch.SRPEAdapter.fetch_selected_development_result",
        lambda self, development_id, language="en": {
            "dev": {
                "website": "www.headland.example" if str(development_id) == "10003" else None,
            }
        },
    )

    with session_factory() as session:
        summary = sync_launch_watch_landsd_pending_approval(session, dry_run=False)
        created = session.scalar(select(func.count()).select_from(LaunchWatchProject))
        project = session.scalar(select(LaunchWatchProject).limit(1))

    assert summary.processed == 1
    assert summary.created == 1
    assert created == 1
    assert project is not None
    assert project.project_name == "Phase 2 of THE HEADLAND RESIDENCES"
    assert project.linked_development_id == "dev-headland"
    assert project.source == "landsd_presale_pending"
    assert project.district == "Hong Kong East"
    assert project.region == "Hong Kong Island"
    assert "pending" in project.tags_json
    assert "issued" not in project.tags_json
    assert project.official_site_url == "https://www.headland.example"
    assert project.srpe_url == "https://www.srpe.gov.hk/the-headland"

    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_sync_launch_watch_srpe_active_first_hand_creates_projects(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "launch-watch-srpe-active.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    current_year = datetime.now().year

    session_factory = get_session_factory()
    with session_factory() as session:
        session.add_all(
            [
                Development(
                    id="dev-srpe-active-1",
                    source="srpe",
                    source_external_id="10011",
                    source_url="https://www.srpe.gov.hk/project-one",
                    name_zh="項目一",
                    name_en="Project One",
                    district="Kai Tak",
                    region="Kowloon",
                    completion_year=2026,
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-active-2",
                    source="srpe",
                    source_external_id="10012",
                    source_url="https://www.srpe.gov.hk/project-two",
                    name_zh="項目二",
                    name_en="Project Two",
                    district="Tseung Kwan O",
                    region="New Territories",
                    completion_year=2028,
                    listing_segment="new",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-remaining-too-far",
                    source="srpe",
                    source_external_id="10016",
                    source_url="https://www.srpe.gov.hk/project-four",
                    name_zh="太遠余貨項目",
                    name_en="Too Far Remaining Project",
                    district="Kai Tak",
                    region="Kowloon",
                    completion_year=2028,
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-secondary",
                    source="srpe",
                    source_external_id="10013",
                    source_url="https://www.srpe.gov.hk/project-three",
                    name_zh="項目三",
                    name_en="Project Three",
                    listing_segment="second_hand",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-old-first-hand",
                    source="srpe",
                    source_external_id="10014",
                    source_url="https://www.srpe.gov.hk/project-old",
                    name_zh="舊一手項目",
                    name_en="Old First-hand Project",
                    completion_year=2022,
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-no-year",
                    source="srpe",
                    source_external_id="10015",
                    source_url="https://www.srpe.gov.hk/project-no-year",
                    name_zh="無年份項目",
                    name_en="No Year Project",
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(
        "hk_home_intel_domain.launch_watch.SRPEAdapter.fetch_selected_development_result",
        lambda self, development_id, language="en": {
            "dev": {
                "website": {
                    "10011": "www.project-one.example",
                    "10012": "www.project-two.example",
                }.get(str(development_id))
            }
        },
    )

    with session_factory() as session:
        summary = sync_launch_watch_srpe_active_first_hand(session, dry_run=False)
        created = session.scalar(select(func.count()).select_from(LaunchWatchProject))
        projects = session.scalars(select(LaunchWatchProject).order_by(LaunchWatchProject.project_name)).all()

    assert summary.source == "srpe_active_first_hand"
    assert summary.processed == 2
    assert summary.created == 2
    assert created == 2
    assert all(project.source == "srpe_active_first_hand" for project in projects)
    assert all(project.linked_development_id in {"dev-srpe-active-1", "dev-srpe-active-2"} for project in projects)
    project_one = next(project for project in projects if project.linked_development_id == "dev-srpe-active-1")
    project_two = next(project for project in projects if project.linked_development_id == "dev-srpe-active-2")
    assert project_one.official_site_url == "https://www.project-one.example"
    assert project_one.srpe_url == "https://www.srpe.gov.hk/project-one"
    assert project_one.expected_launch_window == "2026"
    assert project_one.launch_stage == "watch_selling"
    assert "near-term first-hand window" in (project_one.note or "")
    assert project_two.official_site_url == "https://www.project-two.example"
    assert project_two.launch_stage == "launch_watch"
    assert "new-project watch window" in (project_two.note or "")
    assert summary.report_url == "https://www.srpe.gov.hk"

    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_sync_launch_watch_srpe_recent_documents_creates_projects(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "launch-watch-srpe-recent-docs.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    current_year = datetime.now().year

    session_factory = get_session_factory()
    with session_factory() as session:
        session.add_all(
            [
                Development(
                    id="dev-srpe-recent-1",
                    source="srpe",
                    source_external_id="20011",
                    source_url="https://www.srpe.gov.hk/recent-one",
                    name_zh="近期價單項目",
                    name_en="Recent Pricing Project",
                    district="Kai Tak",
                    region="Kowloon",
                    completion_year=2027,
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-recent-2",
                    source="srpe",
                    source_external_id="20012",
                    source_url="https://www.srpe.gov.hk/recent-two",
                    name_zh="近期樓書項目",
                    name_en="Recent Brochure Project",
                    district="Tseung Kwan O",
                    region="New Territories",
                    completion_year=2028,
                    listing_segment="new",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-stale",
                    source="srpe",
                    source_external_id="20013",
                    source_url="https://www.srpe.gov.hk/stale",
                    name_zh="過期訊號項目",
                    name_en="Stale Signal Project",
                    district="Tuen Mun",
                    region="New Territories",
                    completion_year=2026,
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    id="dev-srpe-recent-too-far",
                    source="srpe",
                    source_external_id="20014",
                    source_url="https://www.srpe.gov.hk/recent-too-far",
                    name_zh="太遠新盤項目",
                    name_en="Too Far New Project",
                    district="Kai Tak",
                    region="Kowloon",
                    completion_year=current_year + 4,
                    listing_segment="new",
                    source_confidence="high",
                ),
            ]
        )
        session.commit()

    recent_price_date = f"{current_year}-03-10T00:00:00.000+08:00"
    recent_brochure_date = f"{current_year}-03-01T00:00:00.000+08:00"
    stale_price_date = f"{current_year - 2}-02-01T00:00:00.000+08:00"

    monkeypatch.setattr(
        "hk_home_intel_domain.launch_watch.SRPEAdapter.fetch_selected_development_result",
        lambda self, development_id, language="en": {
            "dev": {
                "website": {
                    "20011": "www.recent-pricing.example",
                    "20012": "www.recent-brochure.example",
                    "20013": "www.stale.example",
                    "20014": "www.too-far.example",
                }.get(str(development_id))
            },
            "prices": [{"dateOfPrinting": recent_price_date}] if str(development_id) == "20011" else [],
            "salesArrangements": [],
            "brochureList": (
                [{"dateOfPrint": recent_brochure_date}]
                if str(development_id) == "20012"
                else (
                    [{"dateOfPrint": stale_price_date}]
                    if str(development_id) == "20013"
                    else ([{"dateOfPrint": recent_brochure_date}] if str(development_id) == "20014" else [])
                )
            ),
        },
    )

    with session_factory() as session:
        summary = sync_launch_watch_srpe_recent_documents(session, dry_run=False)
        created = session.scalar(select(func.count()).select_from(LaunchWatchProject))
        projects = session.scalars(select(LaunchWatchProject).order_by(LaunchWatchProject.project_name)).all()

    assert summary.source == "srpe_recent_docs"
    assert summary.processed == 2
    assert summary.created == 2
    assert created == 2
    assert all(project.source == "srpe_recent_docs" for project in projects)
    pricing_project = next(project for project in projects if project.linked_development_id == "dev-srpe-recent-1")
    brochure_project = next(project for project in projects if project.linked_development_id == "dev-srpe-recent-2")
    assert pricing_project.official_site_url == "https://www.recent-pricing.example"
    assert pricing_project.launch_stage == "watch_selling"
    assert "pricing/sales-arrangement update" in (pricing_project.note or "")
    assert "recent-docs watch window" in (pricing_project.note or "")
    assert brochure_project.official_site_url == "https://www.recent-brochure.example"
    assert brochure_project.launch_stage == "launch_watch"
    assert "brochure update" in (brochure_project.note or "")

    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


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


def test_execute_refresh_plan_dispatches_ricacorp_probe(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'ricacorp-plan.db'}")
    Base.metadata.create_all(engine)

    def fake_ricacorp_refresh(
        session,
        *,
        url: str,
        limit: int | None,
        trigger_kind: str = "manual",
        job_name: str = "ricacorp_search_refresh",
    ):
        return {
            "job_id": "job-ricacorp-test",
            "source": "ricacorp",
            "url": url,
            "limit": limit,
            "developments_created": 0,
            "developments_updated": 1,
            "documents_upserted": 0,
            "listings_upserted": 2,
            "transactions_upserted": 0,
            "price_events_created": 1,
            "snapshots_created": 1,
        }

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.execute_ricacorp_search_refresh",
        fake_ricacorp_refresh,
    )

    with Session(engine) as session:
        result = execute_refresh_plan(session, plan_name="ricacorp_probe", trigger_kind="manual")

    assert result["plan"] == "ricacorp_probe"
    assert result["task_count"] == 1
    assert result["results"][0]["source"] == "ricacorp"
    assert result["results"][0]["listings_upserted"] == 2


def test_execute_refresh_plan_dispatches_commercial_monitor_batch(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-batch-plan.db'}")
    Base.metadata.create_all(engine)
    captured: list[dict[str, object]] = []

    def fake_batch(
        session,
        *,
        source: str = "centanet",
        active_only: bool = True,
        limit_override: int | None = None,
        trigger_kind: str = "manual",
        job_name: str | None = None,
        job_id: str | None = None,
    ):
        captured.append({"source": source, "active_only": active_only, "limit_override": limit_override})
        return {
            "source": source,
            "active_only": active_only,
            "limit_override": limit_override,
            "monitor_count": 1,
            "failed_monitor_count": 0,
            "results": [],
        }

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.execute_commercial_search_monitor_batch",
        fake_batch,
    )

    with Session(engine) as session:
        result = execute_refresh_plan(session, plan_name="commercial_daily", trigger_kind="manual")

    assert result["plan"] == "commercial_daily"
    assert result["task_count"] == 2
    assert captured == [
        {"source": "centanet", "active_only": True, "limit_override": 20},
        {"source": "ricacorp", "active_only": True, "limit_override": 30},
    ]


def test_execute_refresh_plan_dispatches_launch_watch_official(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'launch-watch-plan.db'}")
    Base.metadata.create_all(engine)
    captured: list[str] = []

    def fake_launch_watch(
        session,
        *,
        source: str,
        trigger_kind: str = "manual",
        job_name: str = "launch_watch_official_refresh",
    ):
        captured.append(source)
        return {
            "job_id": f"job-{source}",
            "source": source,
            "processed": 1,
            "created": 1,
            "updated": 0,
            "unchanged": 0,
            "results": [],
        }

    monkeypatch.setattr(
        "hk_home_intel_domain.refresh.execute_launch_watch_official_refresh",
        fake_launch_watch,
    )

    with Session(engine) as session:
        result = execute_refresh_plan(session, plan_name="launch_watch_daily", trigger_kind="manual")

    assert result["plan"] == "launch_watch_daily"
    assert result["task_count"] == 2
    assert captured == ["landsd-all", "srpe-recent-docs"]


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
    buy_results_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;SEARCHFILTER&q;:{&q;alias&q;:&q;逸瓏-bigest-九龍塘-hma-hk&q;,&q;page&q;:1}}
        </script>
        <rc-property-listing-item-desktop>
          <a href="/zh-hk/property/detail/%E4%B9%9D%E9%BE%8D%E5%A1%98/%E9%80%B8%E7%93%8F-abc123-1-hk"></a>
          <h3 class="address">逸瓏 2房</h3>
          <div class="market-price-block"><div class="price-container">$950</div></div>
          <span class="unit-price">$14,615/呎</span>
          <span>實用 650 呎</span>
          <span>物業編號 ABC123</span>
        </rc-property-listing-item-desktop>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )
    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_search_results_html",
        lambda self, url: buy_results_html,
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
        assert summary.candidates[0].search_url.endswith("/property/list/buy/%E9%80%B8%E7%93%8F-bigest-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk")


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


def test_ricacorp_name_hints_strip_repeated_phase_and_the_prefix() -> None:
    item = Development(
        source="srpe",
        source_external_id="dummy-phase",
        source_url="https://example.test",
        name_en="THE RICHMOND Phase PHASE 1",
        aliases_json=["THE RICHMOND Phase PHASE 1"],
    )

    hints = _ricacorp_name_hints(item)

    assert "THE RICHMOND" in hints
    assert "RICHMOND" in hints


def test_has_name_key_match_allows_long_containment_only() -> None:
    assert _has_name_key_match({"21borrettroad"}, {"21borrettroadphase1"})
    assert not _has_name_key_match({"the"}, {"therichmond"})


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


def test_ricacorp_estate_index_entries_can_derive_buy_url_from_anchor_alias() -> None:
    adapter = RicacorpAdapter()
    html_text = """
    <html>
      <body>
        <a href="/zh-hk/property/estate/%E5%8F%88%E4%B8%80%E5%B1%85-estate-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk">
          <span class="location-text">又一居</span>
          <span class="zone-text">九龍塘</span>
        </a>
      </body>
    </html>
    """

    entries = adapter.estate_index_entries(html_text=html_text)

    assert len(entries) == 1
    assert entries[0]["alias"] == "又一居-estate-九龍塘-hma-hk"
    assert entries[0]["alias_name"] == "又一居"
    assert entries[0]["buy_list_url"] == "https://www.ricacorp.com/zh-hk/property/list/buy/%E5%8F%88%E4%B8%80%E5%B1%85-bigest-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk"


def test_ricacorp_estate_index_entries_skip_generic_scope_type_aliases() -> None:
    adapter = RicacorpAdapter()
    html_text = """
    <html>
      <body>
        <a href="/zh-hk/property/estate/%E4%B9%9D%E9%BE%8D-scope-%E4%BD%8F%E5%AE%85-type-hk">
          <span class="location-text">九龍</span>
          <span class="zone-text">住宅</span>
        </a>
      </body>
    </html>
    """

    entries = adapter.estate_index_entries(html_text=html_text)

    assert entries == []


def test_ricacorp_extract_estate_buy_list_url_can_fallback_to_estate_url_alias() -> None:
    adapter = RicacorpAdapter()
    html_text = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:8}]}
        </script>
      </body>
    </html>
    """

    buy_list_url = adapter.extract_estate_buy_list_url(
        html_text,
        estate_url="https://www.ricacorp.com/zh-hk/property/estate/%E5%8F%88%E4%B8%80%E5%B1%85-estate-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk",
    )

    assert buy_list_url == "https://www.ricacorp.com/zh-hk/property/list/buy/%E5%8F%88%E4%B8%80%E5%B1%85-bigest-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk"


def test_discover_ricacorp_monitor_candidates_can_use_estate_index_state_buy_url(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp-state.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;alias&q;:&q;又一居-estate-九龍塘-hma-hk&q;,&q;locationText&q;:&q;又一居&q;,&q;zoneText&q;:&q;九龍塘&q;,&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:12}]}
        </script>
      </body>
    </html>
    """
    buy_results_html = """
    <html>
      <body>
        <rc-property-listing-item-desktop>
          <a href="/zh-hk/property/detail/%E4%B9%9D%E9%BE%8D%E5%A1%98/%E5%8F%88%E4%B8%80%E5%B1%85-yy123-1-hk"></a>
          <h3 class="address">又一居 2房</h3>
          <div class="market-price-block"><div class="price-container">$950</div></div>
          <span class="unit-price">$14,615/呎</span>
          <span>實用 650 呎</span>
          <span>物業編號 YY123</span>
        </rc-property-listing-item-desktop>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )
    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_search_results_html",
        lambda self, url: buy_results_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-rica-state-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="又一居",
                name_translations_json={"zh-Hant": "又一居", "zh-Hans": "又一居"},
                aliases_json=["又一居"],
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
        assert summary.candidates[0].validated is True
        assert summary.candidates[0].search_url.endswith("/property/list/buy/%E5%8F%88%E4%B8%80%E5%B1%85-bigest-%E4%B9%9D%E9%BE%8D%E5%A1%98-hma-hk")


def test_discover_ricacorp_monitor_candidates_skips_generic_scope_type_state_entries(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp-scope-type.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;alias&q;:&q;九龍-scope-住宅-type-hk&q;,&q;locationText&q;:&q;日出康城&q;,&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:12}]}
        </script>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-rica-scope-type-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="日出康城 - 海瑅灣I",
                aliases_json=["日出康城 - 海瑅灣I"],
                district="TSEUNG KWAN O",
                region="SAI KUNG AND ISLANDS",
                listing_segment="first_hand_remaining",
                source_confidence="high",
            )
        )
        session.commit()

        summary = discover_commercial_monitor_candidates(
            session,
            source="ricacorp",
            limit=5,
            validate=False,
            create_monitors=False,
        )

        assert summary.generated == 0
        assert summary.candidates == []


def test_discover_ricacorp_monitor_candidates_skips_unindexed_guess_urls(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp-unindexed.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <a href="/zh-hk/property/estate/%E5%98%89%E4%BA%A8%E7%81%A3-estate-%E8%A5%BF%E7%81%A3%E6%B2%B3-hma-hk">
          <span class="location-text">嘉亨灣</span>
          <span class="zone-text">西灣河 | 筲箕灣 | 柴灣</span>
        </a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-rica-unindexed-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="又一居",
                name_translations_json={"zh-Hant": "又一居", "zh-Hans": "又一居"},
                aliases_json=["又一居"],
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
            validate=False,
            create_monitors=False,
        )

        assert summary.generated == 0
        assert summary.validated == 0
        assert summary.candidates == []


def test_discover_ricacorp_monitor_candidates_dedupes_resolved_urls(tmp_path: Path, monkeypatch) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp-dedupe.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;alias&q;:&q;港島南岸-bigest-黃竹坑-hma-hk&q;,&q;locationText&q;:&q;港島南岸&q;,&q;zoneText&q;:&q;山頂 | 南區&q;,&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:28}]}
        </script>
      </body>
    </html>
    """
    buy_results_html = """
    <html>
      <body>
        <rc-property-listing-item-desktop>
          <a href="/zh-hk/property/detail/%E9%BB%83%E7%AB%B9%E5%9D%91/%E6%B8%AF%E5%B3%B6%E5%8D%97%E5%B2%B8-aa123-1-hk"></a>
          <h3 class="address">港島南岸 2房</h3>
          <div class="market-price-block"><div class="price-container">$990</div></div>
          <span class="unit-price">$28,863/呎</span>
          <span>實用 343 呎</span>
          <span>物業編號 AA123</span>
        </rc-property-listing-item-desktop>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )
    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_search_results_html",
        lambda self, url: buy_results_html,
    )

    with Session(engine) as session:
        session.add_all(
            [
                Development(
                    source="srpe",
                    source_external_id="srpe-rica-dedupe-001",
                    source_url="https://www.srpe.gov.hk/",
                    name_zh="港島南岸 - 3C",
                    aliases_json=["港島南岸 - 3C"],
                    district="ABERDEEN & AP LEI CHAU",
                    region="HONG KONG",
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
                Development(
                    source="srpe",
                    source_external_id="srpe-rica-dedupe-002",
                    source_url="https://www.srpe.gov.hk/",
                    name_zh="港島南岸 - 滶晨",
                    aliases_json=["港島南岸 - 滶晨"],
                    district="ABERDEEN & AP LEI CHAU",
                    region="HONG KONG",
                    listing_segment="first_hand_remaining",
                    source_confidence="high",
                ),
            ]
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
        assert len(summary.candidates) == 1
        assert summary.candidates[0].search_url.endswith(
            "/property/list/buy/%E6%B8%AF%E5%B3%B6%E5%8D%97%E5%B2%B8-bigest-%E9%BB%83%E7%AB%B9%E5%9D%91-hma-hk"
        )


def test_discover_ricacorp_monitor_candidates_validates_listing_page_via_searchfilter_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-discovery-ricacorp-searchfilter.db'}")
    Base.metadata.create_all(engine)
    estate_list_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;alias&q;:&q;明翹匯-bigest-青衣-hma-hk&q;,&q;locationText&q;:&q;明翹匯&q;,&q;zoneText&q;:&q;青衣&q;,&q;others&q;:[{&q;itemId&q;:&q;post.sales&q;,&q;count&q;:11}]}
        </script>
      </body>
    </html>
    """
    buy_results_html = """
    <html>
      <body>
        <script id="serverApp-state" type="application/json">
          {&q;SEARCHFILTER&q;:{&q;alias&q;:&q;明翹匯-bigest-青衣-hma-hk&q;,&q;page&q;:1}}
        </script>
        <rc-property-listing-item-desktop>
          <a href="/zh-hk/property/detail/%E5%B1%AF%E9%96%80/%E5%B1%AF%E9%96%80%E5%B8%82%E5%BB%A3%E5%A0%B4-cp58276468-3-hk"></a>
          <h3 class="address">屯門市廣場 3期 8座</h3>
          <div class="market-price-block"><div class="price-container">$430</div></div>
          <span class="unit-price">$9,159/呎</span>
          <span>實用 470 呎</span>
          <span>物業編號 CP58276468</span>
        </rc-property-listing-item-desktop>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_estate_list_html",
        lambda self: estate_list_html,
    )
    monkeypatch.setattr(
        "hk_home_intel_domain.commercial_discovery.RicacorpAdapter.fetch_search_results_html",
        lambda self, url: buy_results_html,
    )

    with Session(engine) as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="srpe-rica-searchfilter-001",
                source_url="https://www.srpe.gov.hk/",
                name_zh="明翹匯",
                name_translations_json={"zh-Hant": "明翹匯", "zh-Hans": "明翹汇"},
                aliases_json=["明翹匯"],
                district="Tsing Yi",
                region="New Territories",
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
        assert summary.candidates[0].validated is True
        assert summary.candidates[0].validation_message == "Matched Ricacorp listing page: 明翹匯"


def test_set_commercial_monitors_active_state_can_filter_auto_discovered(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'commercial-monitor-activation.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                CommercialSearchMonitor(
                    source="ricacorp",
                    name="Auto discovered one",
                    search_url="https://example.test/1",
                    scope_type="development_auto",
                    is_active=False,
                ),
                CommercialSearchMonitor(
                    source="ricacorp",
                    name="Auto discovered two",
                    search_url="https://example.test/2",
                    scope_type="development_auto",
                    is_active=False,
                ),
                CommercialSearchMonitor(
                    source="ricacorp",
                    name="Generic buy feed",
                    search_url="https://example.test/3",
                    scope_type="district",
                    is_active=False,
                ),
            ]
        )
        session.commit()

        summary = set_commercial_monitors_active_state(
            session,
            source="ricacorp",
            scope_type="development_auto",
            target_active=True,
        )

        assert summary.scanned == 2
        assert summary.updated == 2
        monitors = session.scalars(select(CommercialSearchMonitor).order_by(CommercialSearchMonitor.search_url)).all()
        assert monitors[0].is_active is True
        assert monitors[1].is_active is True
        assert monitors[2].is_active is False
