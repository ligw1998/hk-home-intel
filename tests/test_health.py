from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hk_home_intel_api.main import create_app
from hk_home_intel_domain.enums import (
    DocumentType,
    JobRunStatus,
    ListingSegment,
    ListingStatus,
    ListingType,
    ParseStatus,
    PriceEventType,
    SnapshotKind,
    SourceConfidence,
    TransactionType,
    WatchlistStage,
)
from hk_home_intel_domain.ingestion import backfill_development_geography
from hk_home_intel_domain.models import (
    CommercialSearchMonitor,
    Development,
    Document,
    LaunchWatchProject,
    Listing,
    PriceEvent,
    RefreshJobRun,
    SearchPreset,
    SourceSnapshot,
    Transaction,
    WatchlistItem,
)
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


def test_shortlist_returns_ranked_candidates_with_reasons(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        strong = Development(
            source="centanet",
            source_external_id="short-1",
            name_zh="理想候选盘",
            district="Kai Tak",
            region="Kowloon",
            completion_year=2022,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            lat=22.3,
            lng=114.2,
        )
        weak = Development(
            source="ricacorp",
            source_external_id="short-2",
            name_zh="偏弱候选盘",
            district="Tuen Mun",
            region="New Territories",
            completion_year=2005,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            lat=22.31,
            lng=114.21,
        )
        session.add_all([strong, weak])
        session.flush()
        session.add_all(
            [
                Listing(
                    development_id=strong.id,
                    source="centanet",
                    source_listing_id="short-listing-1",
                    listing_type=ListingType.SECOND_HAND,
                    asking_price_hkd=12_800_000,
                    price_per_sqft=18_000,
                    bedrooms=2,
                    saleable_area_sqft=700,
                    status=ListingStatus.ACTIVE,
                ),
                Listing(
                    development_id=weak.id,
                    source="ricacorp",
                    source_listing_id="short-listing-2",
                    listing_type=ListingType.SECOND_HAND,
                    asking_price_hkd=22_800_000,
                    price_per_sqft=14_000,
                    bedrooms=4,
                    saleable_area_sqft=1200,
                    status=ListingStatus.ACTIVE,
                ),
                PriceEvent(
                    source="centanet",
                    development_id=strong.id,
                    listing_id=None,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=12_800_000,
                ),
            ]
        )
        session.commit()

    response = isolated_app.get("/api/v1/shortlist")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["min_budget_hkd"] == 8000000
    assert payload["profile"]["max_budget_hkd"] == 18000000
    assert payload["profile"]["bedroom_values"] == [2, 3, 1, 0]
    assert payload["profile"]["min_saleable_area_sqft"] == 400
    assert payload["profile"]["max_saleable_area_sqft"] == 750
    assert payload["items"][0]["display_name"] == "理想候选盘"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["decision_reasons"]
    assert "最低在售价明显落在目标预算带内。" in payload["items"][0]["decision_reasons"]
    assert payload["items"][0]["estimated_stamp_duty_hkd"] is not None
    assert payload["items"][0]["estimated_total_acquisition_cost_hkd"] is not None
    assert payload["items"][0]["acquisition_gap_hkd"] is None or payload["items"][0]["acquisition_gap_hkd"] >= 0


def test_shortlist_keeps_unknown_age_candidate_when_other_signals_are_strong(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        candidate = Development(
            source="centanet",
            source_external_id="short-unknown-age",
            name_zh="年龄未知候选盘",
            district="Kai Tak",
            region="Kowloon",
            completion_year=None,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.HIGH,
            lat=22.32,
            lng=114.21,
        )
        session.add(candidate)
        session.flush()
        session.add(
            Listing(
                development_id=candidate.id,
                source="centanet",
                source_listing_id="short-unknown-age-1",
                listing_type=ListingType.SECOND_HAND,
                asking_price_hkd=12_000_000,
                price_per_sqft=17_500,
                bedrooms=2,
                saleable_area_sqft=650,
                status=ListingStatus.ACTIVE,
            )
        )
        session.add(
            PriceEvent(
                source="centanet",
                development_id=candidate.id,
                listing_id=None,
                event_type=PriceEventType.NEW_LISTING,
                new_price_hkd=12_000_000,
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/shortlist")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["display_name"] == "年龄未知候选盘" for item in payload["items"])


def test_tax_estimate_endpoint_returns_avd_breakdown(isolated_app: TestClient) -> None:
    response = isolated_app.get(
        "/api/v1/policies/tax-estimate?price_hkd=12800000&transaction_date=2026-04-16"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["price_hkd"] == 12800000.0
    assert payload["buyer_profile"] == "hk_individual_residential"
    assert payload["avd_hkd"] > 0
    assert payload["total_tax_hkd"] == payload["avd_hkd"]
    assert payload["total_acquisition_cost_hkd"] > payload["price_hkd"]
    assert payload["breakdown"][0]["name"] == "AVD"
    assert payload["source_urls"]


def test_backfill_development_geography_infers_region_from_district_and_coordinates(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        district_known = Development(
            source="ricacorp",
            source_external_id="geo-dev-1",
            name_zh="地理推断盤 A",
            district="九龍塘",
            region=None,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        coords_known = Development(
            source="centanet",
            source_external_id="geo-dev-2",
            name_zh="地理推断盤 B",
            district=None,
            region=None,
            lat=22.32624,
            lng=114.15498,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add_all([district_known, coords_known])
        session.commit()

        summary = backfill_development_geography(session)
        session.refresh(district_known)
        session.refresh(coords_known)

    assert summary.updated >= 2
    assert district_known.district == "Kowloon Tong"
    assert district_known.region == "Kowloon"
    assert coords_known.region == "Kowloon"


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
            saleable_area_sqft=650,
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
        session.add(
            Document(
                development_id=development.id,
                source="srpe",
                source_doc_id="SNAP-DOC-1",
                source_url="https://www.srpe.gov.hk/example-doc",
                doc_type=DocumentType.BROCHURE,
                title="快照樓書",
            )
        )
        session.add(
            Transaction(
                development_id=development.id,
                source="ricacorp",
                source_record_id="SNAP-TXN-1",
                source_url="https://www.ricacorp.com/example-txn",
                transaction_type=TransactionType.SECONDARY,
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
    coverage = {item["source"]: item for item in payload["source_coverage"]}
    assert coverage["centanet"]["has_development_record"] is True
    assert coverage["centanet"]["active_listing_count"] == 1
    assert coverage["srpe"]["document_count"] == 1
    assert coverage["ricacorp"]["transaction_count"] == 1
    assert payload["coverage_status"] == "rich"
    assert "Commercial coverage: centanet, ricacorp." in payload["coverage_notes"]
    assert payload["data_gap_flags"] == []


def test_development_price_history_endpoint_returns_grouped_points(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="centanet",
            source_external_id="trail-dev-1",
            name_zh="盤面軌跡測試盤",
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
        listing_a = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="TRAIL-A",
            title="盤面軌跡 A",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=12_500_000,
            status=ListingStatus.ACTIVE,
        )
        listing_b = Listing(
            development_id=development.id,
            source="centanet",
            source_listing_id="TRAIL-B",
            title="盤面軌跡 B",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=18_000_000,
            status=ListingStatus.ACTIVE,
        )
        session.add_all([listing_a, listing_b])
        session.flush()
        session.add_all(
            [
                PriceEvent(
                    source="centanet",
                    development_id=development.id,
                    listing_id=listing_a.id,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=12_800_000,
                    new_status="active",
                    event_at=datetime(2026, 4, 13, 9, 0),
                ),
                PriceEvent(
                    source="centanet",
                    development_id=development.id,
                    listing_id=listing_b.id,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=18_500_000,
                    new_status="active",
                    event_at=datetime(2026, 4, 13, 9, 0),
                ),
                PriceEvent(
                    source="centanet",
                    development_id=development.id,
                    listing_id=listing_a.id,
                    event_type=PriceEventType.PRICE_DROP,
                    old_price_hkd=12_800_000,
                    new_price_hkd=12_500_000,
                    old_status="active",
                    new_status="active",
                    event_at=datetime(2026, 4, 14, 11, 15),
                ),
            ]
        )
        session.commit()
        development_id = development.id

    response = isolated_app.get(f"/api/v1/developments/{development_id}/price-history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["development_id"] == development_id
    assert payload["point_count"] == 2
    assert payload["overall_min_price_hkd"] == 12500000.0
    assert payload["overall_max_price_hkd"] == 18500000.0
    assert payload["current_min_price_hkd"] == 12500000.0
    assert payload["current_max_price_hkd"] == 18000000.0
    assert payload["points"][0]["event_count"] == 2
    assert payload["points"][0]["listing_count"] == 2
    assert payload["points"][0]["min_price_hkd"] == 12800000.0
    assert payload["points"][0]["max_price_hkd"] == 18500000.0


def test_compare_endpoints_return_selected_items_and_suggestions(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        focus = Development(
            source="centanet",
            source_external_id="cmp-focus-1",
            name_zh="匯璽",
            district="Sham Shui Po",
            region="Kowloon",
            completion_year=2020,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            developer_names_json=["新鴻基"],
        )
        comparable = Development(
            source="ricacorp",
            source_external_id="cmp-near-1",
            name_zh="維港匯III",
            district="Sham Shui Po",
            region="Kowloon",
            completion_year=2021,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            developer_names_json=["會德豐"],
            aliases_json=["匯璽"],
        )
        distant = Development(
            source="srpe",
            source_external_id="cmp-far-1",
            name_zh="山頂盤",
            district="The Peak Area",
            region="Hong Kong Island",
            completion_year=2014,
            listing_segment=ListingSegment.NEW,
            source_confidence=SourceConfidence.HIGH,
            developer_names_json=["山頂發展商"],
        )
        session.add_all([focus, comparable, distant])
        session.flush()
        focus_listing = Listing(
            development_id=focus.id,
            source="centanet",
            source_listing_id="CMP-FOCUS-1",
            title="匯璽 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=12_800_000,
            bedrooms=2,
            status=ListingStatus.ACTIVE,
        )
        comparable_listing = Listing(
            development_id=comparable.id,
            source="ricacorp",
            source_listing_id="CMP-NEAR-1",
            title="維港匯 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=13_200_000,
            bedrooms=2,
            status=ListingStatus.ACTIVE,
        )
        distant_listing = Listing(
            development_id=distant.id,
            source="srpe",
            source_listing_id="CMP-FAR-1",
            title="山頂盤 4房",
            listing_type=ListingType.NEW,
            asking_price_hkd=42_000_000,
            bedrooms=4,
            status=ListingStatus.ACTIVE,
        )
        session.add_all([focus_listing, comparable_listing, distant_listing])
        session.flush()
        session.add_all(
            [
                PriceEvent(
                    source="centanet",
                    development_id=focus.id,
                    listing_id=focus_listing.id,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=12_800_000,
                    new_status="active",
                    event_at=datetime(2026, 4, 15, 9, 0),
                ),
                PriceEvent(
                    source="ricacorp",
                    development_id=comparable.id,
                    listing_id=comparable_listing.id,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=13_200_000,
                    new_status="active",
                    event_at=datetime(2026, 4, 15, 9, 30),
                ),
                PriceEvent(
                    source="srpe",
                    development_id=distant.id,
                    listing_id=distant_listing.id,
                    event_type=PriceEventType.NEW_LISTING,
                    new_price_hkd=42_000_000,
                    new_status="active",
                    event_at=datetime(2026, 4, 15, 10, 0),
                ),
            ]
        )
        session.commit()
        focus_id = focus.id
        comparable_id = comparable.id

    compare_response = isolated_app.get(
        f"/api/v1/compare/developments?development_id={focus_id}&development_id={comparable_id}"
    )
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["focus_development_id"] == focus_id
    assert len(compare_payload["items"]) == 2
    assert compare_payload["items"][0]["display_name"] == "匯璽"
    assert compare_payload["items"][1]["display_name"] == "維港匯III"

    suggestions_response = isolated_app.get(f"/api/v1/compare/developments/{focus_id}/suggestions")
    assert suggestions_response.status_code == 200
    suggestions_payload = suggestions_response.json()
    assert suggestions_payload["focus_development_id"] == focus_id
    assert suggestions_payload["items"][0]["development"]["display_name"] == "維港匯III"
    assert suggestions_payload["items"][0]["match_score"] > 0
    assert "same estate alias" in suggestions_payload["items"][0]["reasons"]


def test_compare_listing_comparables_returns_ranked_matches(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        focus_dev = Development(
            source="centanet",
            source_external_id="cmp-listing-dev-1",
            name_zh="匯璽",
            district="Sham Shui Po",
            region="Kowloon",
            completion_year=2020,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        near_dev = Development(
            source="ricacorp",
            source_external_id="cmp-listing-dev-2",
            name_zh="維港匯III",
            district="Sham Shui Po",
            region="Kowloon",
            completion_year=2021,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
            aliases_json=["匯璽"],
        )
        far_dev = Development(
            source="ricacorp",
            source_external_id="cmp-listing-dev-3",
            name_zh="御景園",
            district="Yuen Long",
            region="New Territories",
            completion_year=1998,
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add_all([focus_dev, near_dev, far_dev])
        session.flush()
        focus_listing = Listing(
            development_id=focus_dev.id,
            source="centanet",
            source_listing_id="CMP-LISTING-1",
            title="匯璽 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=8_800_000,
            saleable_area_sqft=391,
            bedrooms=2,
            status=ListingStatus.ACTIVE,
        )
        near_listing = Listing(
            development_id=near_dev.id,
            source="ricacorp",
            source_listing_id="CMP-LISTING-2",
            title="維港匯 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=9_100_000,
            saleable_area_sqft=405,
            bedrooms=2,
            status=ListingStatus.ACTIVE,
        )
        far_listing = Listing(
            development_id=far_dev.id,
            source="ricacorp",
            source_listing_id="CMP-LISTING-3",
            title="御景園 4房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=4_600_000,
            saleable_area_sqft=468,
            bedrooms=4,
            status=ListingStatus.ACTIVE,
        )
        session.add_all([focus_listing, near_listing, far_listing])
        session.commit()
        focus_listing_id = focus_listing.id

    response = isolated_app.get(f"/api/v1/compare/listings/{focus_listing_id}/comparables")
    assert response.status_code == 200
    payload = response.json()
    assert payload["focus_listing_id"] == focus_listing_id
    assert len(payload["items"]) == 1
    assert payload["items"][0]["development_name"] == "維港匯III"
    assert "same estate alias" in payload["items"][0]["reasons"]


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
    assert list_payload[0]["active_listing_count"] == 0
    assert list_payload[0]["recent_listing_event_count_7d"] == 0


def test_watchlist_includes_listing_market_snapshot(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="centanet",
            source_external_id="watch-dev-1",
            name_zh="收藏盤面測試盤",
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
            source_listing_id="WATCH-1",
            title="收藏盤面 2房",
            listing_type=ListingType.SECOND_HAND,
            asking_price_hkd=12_300_000,
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
                old_price_hkd=12_500_000,
                new_price_hkd=12_300_000,
                old_status="active",
                new_status="active",
                event_at=datetime.utcnow() - timedelta(days=1),
            )
        )
        session.add(
            WatchlistItem(
                development_id=development.id,
                decision_stage=WatchlistStage.SHORTLISTED,
                personal_score=8,
                note="Watch closely",
                tags_json=["mtr"],
            )
        )
        session.commit()
        development_id = development.id

    response = isolated_app.get(f"/api/v1/watchlist?development_id={development_id}")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["active_listing_count"] == 1
    assert payload[0]["active_listing_min_price_hkd"] == 12300000.0
    assert payload[0]["active_listing_max_price_hkd"] == 12300000.0
    assert payload[0]["recent_listing_event_count_7d"] == 1
    assert payload[0]["recent_price_move_count_7d"] == 1
    assert payload[0]["recent_status_move_count_7d"] == 0


def test_launch_watch_endpoint_returns_curated_projects(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        development = Development(
            source="srpe",
            source_external_id="launch-dev-1",
            name_zh="啟德海灣第2期",
            district="Kai Tak",
            region="Kowloon",
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
        )
        session.add(development)
        session.flush()
        session.add(
            LaunchWatchProject(
                source="centanet_news",
                project_name="啟德海灣第2期",
                project_name_en="KT Marina Phase 2",
                district="Kai Tak",
                region="Kowloon",
                expected_launch_window="near-term",
                launch_stage="launch_watch",
                source_url="https://example.com/launch-news",
                linked_development_id=development.id,
                is_active=True,
                tags_json=["primary-market"],
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/launch-watch")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["project_name"] == "啟德海灣第2期"
    assert payload["items"][0]["linked_development_name"] == "啟德海灣第2期"
    assert payload["items"][0]["launch_stage"] == "launch_watch"
    assert payload["items"][0]["signal_bucket"] == "other_watch"
    assert payload["items"][0]["signal_label"] == "Other Watch"


def test_launch_watch_endpoint_uses_new_district_centroid_for_approximate_position(
    isolated_app: TestClient,
) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            LaunchWatchProject(
                source="manual",
                project_name="啟德海灣第2期",
                project_name_en="KT Marina Phase 2",
                district="Kai Tak",
                region="Kowloon",
                expected_launch_window="near-term",
                launch_stage="launch_watch",
                source_url="https://example.com/launch-news",
                linked_development_id=None,
                is_active=True,
                tags_json=["primary-market"],
            )
        )
        session.commit()

    response = isolated_app.get("/api/v1/launch-watch")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["coordinate_mode"] == "approximate"
    assert item["lat"] == 22.3199
    assert item["lng"] == 114.2131


def test_search_preset_crud(isolated_app: TestClient) -> None:
    create_response = isolated_app.post(
        "/api/v1/search-presets",
        json={
            "name": "Buyer Focus",
            "scope": "development_map",
            "note": "800萬-1800萬、400-750呎、2房優先",
            "is_default": True,
            "criteria": {
                "listing_segments": ["new", "first_hand_remaining", "second_hand"],
                "min_budget_hkd": 8000000,
                "max_budget_hkd": 18000000,
                "bedroom_values": [2, 3, 1, 0],
                "min_saleable_area_sqft": 400,
                "max_saleable_area_sqft": 750,
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
    assert list_payload[0]["criteria"]["min_budget_hkd"] == 8000000
    assert list_payload[0]["criteria"]["max_budget_hkd"] == 18000000

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


def test_commercial_search_monitor_crud(isolated_app: TestClient) -> None:
    create_response = isolated_app.post(
        "/api/v1/commercial-search-monitors",
        json={
            "source": "centanet",
            "name": "Cullinan West Focus",
            "search_url": "https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            "scope_type": "development",
            "development_name_hint": "匯璽",
            "district": "Sham Shui Po",
            "region": "Kowloon",
            "note": "Primary test monitor.",
            "is_active": True,
            "with_details": True,
            "detect_withdrawn": False,
            "tags": ["buyer-focus"],
            "criteria": {
                "listing_segments": ["second_hand"],
                "max_budget_hkd": 16000000,
                "bedroom_values": [2, 3, 1],
                "max_age_years": 10,
            },
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["name"] == "Cullinan West Focus"
    assert create_payload["criteria"]["bedroom_values"] == [2, 3, 1]

    list_response = isolated_app.get("/api/v1/commercial-search-monitors?source=centanet")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["search_url"].startswith("https://hk.centanet.com/findproperty/list/buy/")

    update_response = isolated_app.patch(
        f"/api/v1/commercial-search-monitors/{create_payload['id']}",
        json={
            "source": "centanet",
            "name": "Cullinan West Focus Updated",
            "search_url": "https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            "scope_type": "development",
            "development_name_hint": "匯璽",
            "district": "Sham Shui Po",
            "region": "Kowloon",
            "note": "Updated monitor.",
            "is_active": True,
            "with_details": False,
            "detect_withdrawn": True,
            "tags": ["updated"],
            "criteria": {
                "listing_segments": ["second_hand"],
                "max_budget_hkd": 15000000,
                "bedroom_values": [2],
                "max_age_years": 15,
            },
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["name"] == "Cullinan West Focus Updated"
    assert update_payload["with_details"] is False
    assert update_payload["detect_withdrawn"] is True

    delete_response = isolated_app.delete(f"/api/v1/commercial-search-monitors/{create_payload['id']}")
    assert delete_response.status_code == 204

    final_response = isolated_app.get("/api/v1/commercial-search-monitors?source=centanet")
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
    assert "readiness_status" in overview_payload
    assert "commercial_listing_count" in overview_payload
    assert "development_missing_coordinates_count" in overview_payload
    assert "duplicate_development_name_group_count" in overview_payload
    assert "active_listing_missing_price_count" in overview_payload
    assert "commercial_canonical_with_official_artifact_count" in overview_payload
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


def test_system_overview_reports_preflight_data_quality_counts(isolated_app: TestClient) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        srpe_development = Development(
            source="srpe",
            source_external_id="srpe-duplicate",
            name_en="TEST ESTATE",
            aliases_json=["TEST ESTATE"],
            listing_segment=ListingSegment.FIRST_HAND_REMAINING,
            source_confidence=SourceConfidence.HIGH,
            lat=22.3,
            lng=114.2,
        )
        commercial_development = Development(
            source="centanet",
            source_external_id="centanet-duplicate",
            name_en="TEST ESTATE",
            aliases_json=["TEST ESTATE"],
            listing_segment=ListingSegment.SECOND_HAND,
            source_confidence=SourceConfidence.MEDIUM,
        )
        session.add_all([srpe_development, commercial_development])
        session.flush()
        session.add(
            Document(
                development_id=commercial_development.id,
                source="srpe",
                source_doc_id="srpe-doc-on-commercial",
                doc_type=DocumentType.BROCHURE,
                title="Official brochure",
            )
        )
        session.add(
            Listing(
                source="centanet",
                source_listing_id="missing-price",
                development_id=commercial_development.id,
                listing_type=ListingType.SECOND_HAND,
                status=ListingStatus.ACTIVE,
                asking_price_hkd=None,
            )
        )
        session.commit()

    overview_response = isolated_app.get("/api/v1/system/overview")
    assert overview_response.status_code == 200
    payload = overview_response.json()
    assert payload["development_missing_coordinates_count"] == 1
    assert payload["duplicate_development_name_group_count"] == 1
    assert payload["active_listing_missing_price_count"] == 1
    assert payload["commercial_canonical_with_official_artifact_count"] == 1
    assert any("cross-source duplicate" in note for note in payload["readiness_notes"])


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


def test_run_commercial_search_monitor_endpoint(isolated_app: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        monitor = CommercialSearchMonitor(
            source="centanet",
            name="Run Monitor",
            search_url="https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            scope_type="development",
            development_name_hint="匯璽",
            is_active=True,
            with_details=True,
            detect_withdrawn=False,
        )
        session.add(monitor)
        session.commit()
        monitor_id = monitor.id

    monkeypatch.setattr(
        "hk_home_intel_api.routes.commercial_search_monitors.launch_commercial_search_monitor_refresh",
        lambda database_url, monitor_id, limit_override=None, trigger_kind="api": {
            "job_id": "monitor-job-123",
            "monitor_id": monitor_id,
        },
    )

    response = isolated_app.post(
        f"/api/v1/commercial-search-monitors/{monitor_id}/run",
        json={"limit_override": 12},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["job_id"] == "monitor-job-123"
    assert payload["monitor_id"] == monitor_id


def test_run_commercial_search_monitor_batch_endpoint(isolated_app: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hk_home_intel_api.routes.commercial_search_monitors.launch_commercial_search_monitor_batch",
        lambda database_url, source="centanet", active_only=True, limit_override=None, trigger_kind="api": {
            "job_id": "batch-job-123",
            "source": source,
        },
    )

    response = isolated_app.post(
        "/api/v1/commercial-search-monitors/run-batch",
        json={"source": "centanet", "active_only": True, "limit_override": 8},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["job_id"] == "batch-job-123"
    assert payload["source"] == "centanet"


def test_discover_commercial_search_monitor_candidates_endpoint(
    isolated_app: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hk_home_intel_api.routes.commercial_search_monitors.run_commercial_monitor_discovery",
        lambda session, **kwargs: type(
            "Summary",
            (),
            {
                "source": kwargs["source"],
                "processed": 4,
                "generated": 2,
                "validated": 1,
                "created_monitors": 1,
                "candidates": [
                    type(
                        "Candidate",
                        (),
                        {
                            "source": kwargs["source"],
                            "development_id": "dev-1",
                            "development_name": "匯璽",
                            "district": "Sham Shui Po",
                            "region": "Kowloon",
                            "listing_segment": "second_hand",
                            "search_url": "https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
                            "development_name_hint": "匯璽",
                            "match_score": 88,
                            "reasons": ["Observed listing price band overlaps the target budget."],
                            "validated": True,
                            "validation_status": "validated",
                            "validation_message": "Matched page/development name: 匯璽",
                            "existing_monitor_id": None,
                            "created_monitor_id": "cm-1",
                        },
                    )(),
                ],
            },
        )(),
    )

    response = isolated_app.post(
        "/api/v1/commercial-search-monitors/discovery",
        json={
            "source": "centanet",
            "limit": 10,
            "validate": True,
            "create_monitors": True,
            "activate_created": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "centanet"
    assert payload["generated"] == 2
    assert payload["created_monitors"] == 1
    assert payload["candidates"][0]["validation_status"] == "validated"
    assert payload["candidates"][0]["created_monitor_id"] == "cm-1"


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


def test_run_scheduler_plan_endpoint_accepts_daily_local(isolated_app: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hk_home_intel_api.routes.system.launch_refresh_plan",
        lambda database_url, plan_name, trigger_kind="api": {
            "job_id": "job-daily-local",
            "plan": plan_name,
        },
    )

    response = isolated_app.post("/api/v1/system/run-plan", json={"plan_name": "daily_local"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["plan"] == "daily_local"
    assert payload["job_id"] == "job-daily-local"


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
            source_listing_id="TEST-MXL121",
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
