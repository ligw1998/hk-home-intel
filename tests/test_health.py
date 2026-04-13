from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hk_home_intel_api.main import create_app
from hk_home_intel_domain.enums import (
    JobRunStatus,
    ListingSegment,
    ListingStatus,
    ListingType,
    ParseStatus,
    PriceEventType,
    SnapshotKind,
    SourceConfidence,
    WatchlistStage,
)
from hk_home_intel_domain.models import Development, Listing, PriceEvent, RefreshJobRun, SearchPreset, SourceSnapshot, WatchlistItem
from hk_home_intel_shared.db import get_engine, get_session_factory, reset_db_caches
from hk_home_intel_shared.models.base import Base
from hk_home_intel_shared.settings import clear_settings_cache


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["healthy"] is True


def test_cors_preflight_for_local_web() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.fixture()
def isolated_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    app = create_app()
    client = TestClient(app)
    yield client

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_list_developments_returns_seeded_rows(isolated_app: TestClient, tmp_path: Path) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            Development(
                source="srpe",
                source_external_id="seed-dev-1",
                name_zh="测试楼盘",
                name_en="Test Development",
                district="Hong Kong East",
                region="Hong Kong Island",
                listing_segment=ListingSegment.NEW,
                source_confidence=SourceConfidence.HIGH,
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/developments")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name_zh"] == "测试楼盘"


def test_list_developments_excludes_rows_without_source(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            Development(
                source=None,
                name_zh="历史残留盘",
                district="Hong Kong East",
                region="Hong Kong Island",
                listing_segment=ListingSegment.NEW,
                source_confidence=SourceConfidence.HIGH,
            )
        )
        session.add(
            Development(
                source="srpe",
                source_external_id="live-dev-1",
                name_zh="Live 盘",
                district="Hong Kong East",
                region="Hong Kong Island",
                listing_segment=ListingSegment.NEW,
                source_confidence=SourceConfidence.HIGH,
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/developments")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name_zh"] == "Live 盘"


def test_list_developments_supports_preference_filters(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        preferred = Development(
            source="centanet",
            source_external_id="pref-dev-1",
            name_zh="優先測試盤",
            district="Kai Tak",
            region="Kowloon",
            completion_year=2022,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            lat=22.3,
            lng=114.2,
        )
        expensive = Development(
            source="srpe",
            source_external_id="exp-dev-1",
            name_zh="超預算測試盤",
            district="Kai Tak",
            region="Kowloon",
            completion_year=2024,
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
            lat=22.31,
            lng=114.21,
        )
        old_stock = Development(
            source="centanet",
            source_external_id="old-dev-1",
            name_zh="樓齡過高測試盤",
            district="Tseung Kwan O",
            region="New Territories",
            completion_year=2001,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            lat=22.32,
            lng=114.22,
        )
        session.add_all([preferred, expensive, old_stock])
        session.flush()
        session.add_all(
            [
                Listing(
                    development_id=preferred.id,
                    source="centanet",
                    source_listing_id="PREF-1",
                    title="優先測試盤 2房",
                    listing_type=ListingType.SECOND_HAND,
                    asking_price_hkd=12_800_000,
                    bedrooms=2,
                    status=ListingStatus.ACTIVE,
                ),
                Listing(
                    development_id=expensive.id,
                    source="srpe",
                    source_listing_id="EXP-1",
                    title="超預算測試盤 2房",
                    listing_type=ListingType.FIRST_HAND_REMAINING,
                    asking_price_hkd=18_500_000,
                    bedrooms=2,
                    status=ListingStatus.ACTIVE,
                ),
                Listing(
                    development_id=old_stock.id,
                    source="centanet",
                    source_listing_id="OLD-1",
                    title="樓齡過高測試盤 3房",
                    listing_type=ListingType.SECOND_HAND,
                    asking_price_hkd=13_500_000,
                    bedrooms=3,
                    status=ListingStatus.ACTIVE,
                ),
            ]
        )
        session.commit()

    response = isolated_app.get(
        "/api/v1/developments?has_coordinates=true&max_budget_hkd=16000000&bedroom_values=2,3,1&max_age_years=10"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["display_name"] == "優先測試盤"
    assert payload["items"][0]["active_listing_min_price_hkd"] == 12800000.0
    assert payload["items"][0]["active_listing_max_price_hkd"] == 12800000.0
    assert payload["items"][0]["active_listing_bedroom_options"] == [2]
    assert payload["items"][0]["active_listing_bedroom_mix"] == {"2": 1}
    assert payload["items"][0]["active_listing_source_counts"] == {"centanet": 1}


def test_development_detail_exposes_market_snapshot(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="centanet",
            source_external_id="snap-dev-1",
            name_zh="盤面快照測試盤",
            district="Kai Tak",
            region="Kowloon",
            completion_year=2023,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            lat=22.3,
            lng=114.2,
        )
        session.add(development)
        session.flush()
        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="SNAP-1",
            title="盤面快照測試盤 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=13_500_000,
            bedrooms=2,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()
        session.add(
            PriceEvent(
                source="centanet",
                development_id=development.id,
                listing_id=listing.id,
                event_type=PriceEventType.NEW_LISTING,
                new_price_hkd=13_500_000,
                new_status="active",
                event_at=datetime(2026, 4, 14, 10, 30),
            )
        )
        session.commit()
        development_id = development.id

    response = isolated_app.get(f"/api/v1/developments/{development_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_listing_count"] == 1
    assert payload["active_listing_min_price_hkd"] == 13500000.0
    assert payload["active_listing_max_price_hkd"] == 13500000.0
    assert payload["active_listing_bedroom_mix"] == {"2": 1}
    assert payload["active_listing_source_counts"] == {"centanet": 1}
    assert payload["latest_listing_event_at"] == "2026-04-14T10:30:00"


def test_watchlist_upsert_and_list(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            name_zh="收藏测试盘",
            name_en="Watchlist House",
            district="Hong Kong East",
            region="Hong Kong Island",
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
        )
        session.add(development)
        session.commit()
        session.refresh(development)
        development_id = development.id

    create_response = isolated_app.post(
        "/api/v1/watchlist",
        json={
            "development_id": development_id,
            "decision_stage": "shortlisted",
            "note": "Need to compare against nearby stock.",
            "tags": ["harbour", "new"],
        },
    )

    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["development_id"] == development_id
    assert create_payload["decision_stage"] == "shortlisted"

    list_response = isolated_app.get(f"/api/v1/watchlist?development_id={development_id}")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["development_name"] == "收藏测试盘"


def test_search_preset_crud(isolated_app: TestClient) -> None:
    create_response = isolated_app.post(
        "/api/v1/search-presets",
        json={
            "name": "Buyer Focus",
            "scope": "development_map",
            "note": "1600萬內、2房優先",
            "is_default": True,
            "criteria": {
                "listing_segments": ["new", "first_hand_remaining", "second_hand"],
                "max_budget_hkd": 16000000,
                "bedroom_values": [2, 3, 1],
                "max_age_years": 10,
                "watchlist_only": False,
            },
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["name"] == "Buyer Focus"
    assert create_payload["is_default"] is True

    list_response = isolated_app.get("/api/v1/search-presets?scope=development_map")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["criteria"]["max_budget_hkd"] == 16000000

    update_response = isolated_app.patch(
        f"/api/v1/search-presets/{create_payload['id']}",
        json={
            "name": "Buyer Focus Updated",
            "scope": "development_map",
            "note": "放寬到15年內",
            "is_default": True,
            "criteria": {
                "listing_segments": ["new", "first_hand_remaining", "second_hand"],
                "max_budget_hkd": 16000000,
                "bedroom_values": [2, 3, 1],
                "max_age_years": 15,
                "watchlist_only": False,
            },
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["name"] == "Buyer Focus Updated"
    assert update_payload["criteria"]["max_age_years"] == 15

    delete_response = isolated_app.delete(f"/api/v1/search-presets/{create_payload['id']}")
    assert delete_response.status_code == 204

    final_response = isolated_app.get("/api/v1/search-presets?scope=development_map")
    assert final_response.status_code == 200
    assert final_response.json() == []


def test_system_overview_and_refresh_jobs(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            RefreshJobRun(
                job_name="srpe_refresh",
                source="srpe",
                trigger_kind="manual",
                status=JobRunStatus.SUCCEEDED,
                summary_json={"developments_created": 2},
            )
        )
        session.commit()

    overview_response = isolated_app.get("/api/v1/system/overview")
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert "development_count" in overview_payload
    assert overview_payload["latest_job"]["job_name"] == "srpe_refresh"

    jobs_response = isolated_app.get("/api/v1/system/refresh-jobs")
    assert jobs_response.status_code == 200
    jobs_payload = jobs_response.json()
    assert len(jobs_payload) == 1
    assert jobs_payload[0]["status"] == "succeeded"

    plans_response = isolated_app.get("/api/v1/system/scheduler-plans")
    assert plans_response.status_code == 200
    plans_payload = plans_response.json()
    assert any(item["name"] == "daily_local" for item in plans_payload)
    assert any(item["name"] == "centanet_probe" for item in plans_payload)
    assert any("due_now" in item for item in plans_payload)
    assert any("has_override" in item for item in plans_payload)
    centanet_plan = next(item for item in plans_payload if item["name"] == "centanet_probe")
    assert centanet_plan["tasks"][0]["command"] == "centanet_search_refresh"
    assert centanet_plan["tasks"][0]["url"]
    assert centanet_plan["tasks"][0]["detect_withdrawn"] is False


def test_run_scheduler_plan_endpoint(isolated_app: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hk_home_intel_api.routes.system.launch_refresh_plan",
        lambda database_url, plan_name, trigger_kind="api": {
            "job_id": "job-123",
            "plan": plan_name,
        },
    )

    response = isolated_app.post("/api/v1/system/run-plan", json={"plan_name": "watchlist_probe"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["job_id"] == "job-123"
    assert payload["plan"] == "watchlist_probe"


def test_run_due_scheduler_plans_endpoint(isolated_app: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hk_home_intel_api.routes.system.launch_due_refresh_plans",
        lambda database_url, trigger_kind="api": {
            "due_plan_names": ["daily_local"],
            "run_count": 1,
            "launched": [{"job_id": "job-456", "plan": "daily_local"}],
        },
    )

    response = isolated_app.post("/api/v1/system/run-due-plans")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["due_plan_names"] == ["daily_local"]
    assert payload["run_count"] == 1
    assert payload["job_ids"] == ["job-456"]


def test_run_scheduler_plan_endpoint_real_launch_does_not_500(isolated_app: TestClient) -> None:
    response = isolated_app.post("/api/v1/system/run-plan", json={"plan_name": "daily_local"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["plan"] == "daily_local"
    assert payload["job_id"]


def test_listings_feed_filters_by_source_and_includes_links(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            name_zh="測試屋苑",
            district="Kowloon City",
            region="Kowloon",
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            source_url="https://hk.centanet.com/example/dev",
        )
        session.add(development)
        session.flush()

        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="MXL121",
            source_url="https://hk.centanet.com/example/listing",
            title="測試盤",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=8_700_000,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()

        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=8_900_000,
                new_price_hkd=8_700_000,
                old_status="active",
                new_status="active",
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/listings/feed?source=centanet&event_type=price_drop")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["development_source_url"] == "https://hk.centanet.com/example/dev"
    assert payload[0]["listing_source_url"] == "https://hk.centanet.com/example/listing"
    assert payload[0]["price_delta_hkd"] == -200000.0


def test_listings_feed_changes_only_excludes_new_listing(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            name_zh="變化測試屋苑",
            district="Kowloon City",
            region="Kowloon",
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add(development)
        session.flush()

        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="MXL777",
            title="變化測試盤",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=7_800_000,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()

        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.NEW_LISTING,
                development_id=development.id,
                listing_id=listing.id,
                new_price_hkd=7_800_000,
                new_status="active",
            )
        )
        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=8_000_000,
                new_price_hkd=7_800_000,
                old_status="active",
                new_status="active",
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/listings/feed?source=centanet&changes_only=true")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_type"] == "price_drop"


def test_listings_feed_days_filter_excludes_old_events(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="centanet",
            source_external_id="days-dev-1",
            name_zh="時間窗測試屋苑",
            district="Kai Tak",
            region="Kowloon",
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add(development)
        session.flush()

        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="MXL-DAYS-1",
            title="時間窗測試盤",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=9_800_000,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()

        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.NEW_LISTING,
                development_id=development.id,
                listing_id=listing.id,
                new_price_hkd=10_100_000,
                new_status="active",
                event_at=datetime.utcnow() - timedelta(days=10),
            )
        )
        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=10_100_000,
                new_price_hkd=9_800_000,
                old_status="active",
                new_status="active",
                event_at=datetime.utcnow() - timedelta(hours=12),
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/listings/feed?source=centanet&days=1")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_type"] == "price_drop"


def test_listings_feed_q_search_matches_development_and_listing_text(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            name_zh="海盈山",
            district="Aberdeen",
            region="Hong Kong Island",
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add(development)
        session.flush()

        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="MXL555",
            title="海盈山 2房調整叫價",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=12_300_000,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()

        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_RAISE,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=12_000_000,
                new_price_hkd=12_300_000,
                old_status="active",
                new_status="active",
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/listings/feed?q=%E6%B5%B7%E7%9B%88%E5%B1%B1")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["development_name"] == "海盈山"


def test_listing_price_history_endpoint_returns_ordered_points(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            name_zh="價格歷史盤",
            district="Kai Tak",
            region="Kowloon",
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add(development)
        session.flush()

        listing = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="MXL900",
            title="價格歷史 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=10_800_000,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()

        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.NEW_LISTING,
                development_id=development.id,
                listing_id=listing.id,
                new_price_hkd=11_200_000,
                new_status="active",
            )
        )
        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=11_200_000,
                new_price_hkd=10_900_000,
                old_status="active",
                new_status="active",
            )
        )
        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=10_900_000,
                new_price_hkd=10_800_000,
                old_status="active",
                new_status="active",
            )
        )
        session.commit()
        listing_id = listing.id

    response = isolated_app.get(f"/api/v1/listings/{listing_id}/price-history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["listing_id"] == listing_id
    assert payload["current_price_hkd"] == 10800000.0
    assert payload["previous_price_hkd"] == 10900000.0
    assert payload["lowest_price_hkd"] == 10800000.0
    assert payload["highest_price_hkd"] == 11200000.0
    assert payload["point_count"] == 3
    assert [point["event_type"] for point in payload["points"]] == [
        "new_listing",
        "price_drop",
        "price_drop",
    ]


def test_scheduler_plan_override_update_and_reset(isolated_app: TestClient) -> None:
    update_response = isolated_app.patch(
        "/api/v1/system/scheduler-plans/daily_local",
        json={
            "auto_run": False,
            "interval_minutes": 720,
            "task_overrides": [
                {
                    "job_name": "srpe_refresh",
                    "limit": 8,
                    "with_details": False,
                    "detect_withdrawn": False,
                    "rotation_mode": "none",
                    "rotation_step": 8,
                }
            ],
        },
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["name"] == "daily_local"
    assert update_payload["auto_run"] is False
    assert update_payload["interval_minutes"] == 720
    assert update_payload["has_override"] is True
    assert update_payload["tasks"][0]["limit"] == 8
    assert update_payload["tasks"][0]["rotation_mode"] == "none"

    list_response = isolated_app.get("/api/v1/system/scheduler-plans")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["name"] == "daily_local")
    assert listed["interval_minutes"] == 720
    assert listed["tasks"][0]["limit"] == 8
    assert listed["has_override"] is True

    reset_response = isolated_app.delete("/api/v1/system/scheduler-plans/daily_local/override")
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["has_override"] is False
    assert reset_payload["auto_run"] is True
    assert reset_payload["interval_minutes"] == 1440
    assert reset_payload["tasks"][0]["limit"] == 20


def test_recent_activity_endpoint(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="srpe",
            source_external_id="dev-1",
            source_url="https://example.test/development",
            name_zh="活动测试盘",
            name_translations_json={"zh-Hant": "活動測試盤", "zh-Hans": "活动测试盘"},
            district="Hong Kong East",
            region="Hong Kong Island",
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
        )
        session.add(development)
        session.flush()

        session.add(
            SourceSnapshot(
                source="srpe",
                object_type="development",
                object_external_id="dev-1",
                source_url="https://example.test/development",
                snapshot_kind=SnapshotKind.JSON,
                parse_status=ParseStatus.PARSED,
                metadata_json={"name": "activity"},
            )
        )
        session.add(
            WatchlistItem(
                development_id=development.id,
                decision_stage=WatchlistStage.SHORTLISTED,
                note="Keep watching recent updates.",
            )
        )
        session.add(
            RefreshJobRun(
                job_name="srpe_refresh",
                source="srpe",
                trigger_kind="manual",
                status=JobRunStatus.SUCCEEDED,
                summary_json={"developments_updated": 1, "documents_upserted": 2, "snapshots_created": 3},
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/activity/recent?limit=10&lang=zh-Hant")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_items"] == 3
    assert {item["kind"] for item in payload["items"]} == {"refresh_job", "source_snapshot", "watchlist_update"}
    assert any(item["development_name"] == "活動測試盤" for item in payload["items"] if item["kind"] != "refresh_job")


def test_listings_feed_returns_seeded_price_events(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="srpe",
            source_external_id="dev-feed",
            name_zh="事件测试盘",
            name_translations_json={"zh-Hant": "事件測試盤", "zh-Hans": "事件测试盘"},
            district="Hong Kong East",
            region="Hong Kong Island",
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
        )
        session.add(development)
        session.flush()
        listing = Listing(
            source="centanet",
            source_listing_id="listing-1",
            development_id=development.id,
            title="Price adjusted listing",
            listing_type=ListingType.SECOND_HAND,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()
        session.add(
            PriceEvent(
                source="centanet",
                event_type=PriceEventType.PRICE_DROP,
                development_id=development.id,
                listing_id=listing.id,
                old_price_hkd=10000000,
                new_price_hkd=9500000,
                old_status="active",
                new_status="active",
            )
        )
        session.commit()

    feed_response = isolated_app.get("/api/v1/listings/feed?lang=zh-Hant")
    assert feed_response.status_code == 200
    feed_payload = feed_response.json()
    assert len(feed_payload) == 1
    assert feed_payload[0]["event_type"] == "price_drop"
    assert feed_payload[0]["development_name"] == "事件測試盤"
    assert feed_payload[0]["new_price_hkd"] == 9500000.0

    events_response = isolated_app.get(f"/api/v1/listings/{feed_payload[0]['listing_id']}/events?lang=zh-Hant")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert len(events_payload) == 1
    assert events_payload[0]["old_price_hkd"] == 10000000.0
