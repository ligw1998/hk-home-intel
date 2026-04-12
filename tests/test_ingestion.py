from pathlib import Path

from fastapi.testclient import TestClient

from hk_home_intel_api.main import create_app
from hk_home_intel_connectors.srpe import SRPEAdapter
from hk_home_intel_domain.ingestion import (
    import_centanet_sample,
    import_centanet_search_results,
    import_srpe_all_developments,
    import_srpe_sample,
)
from hk_home_intel_shared.db import get_engine, get_session_factory, reset_db_caches
from hk_home_intel_shared.models.base import Base
from hk_home_intel_shared.settings import clear_settings_cache


def test_import_srpe_sample_exposes_developments(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "import.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_srpe_sample(session)

    assert summary.developments_created == 2
    assert summary.documents_upserted == 4
    assert summary.listings_upserted == 3
    assert summary.transactions_upserted == 2

    client = TestClient(create_app())
    response = client.get("/api/v1/developments")
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 2
    assert payload["items"][0]["listing_segment"] == "first_hand_remaining"
    assert payload["items"][0]["display_name"] in {"海璇 II", "啟德海灣"}

    development_id = payload["items"][0]["id"]
    detail = client.get(f"/api/v1/developments/{development_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert "documents" in detail_payload
    assert "listings" in detail_payload
    assert "transactions" in detail_payload

    simplified = client.get("/api/v1/developments?lang=zh-Hans")
    assert simplified.status_code == 200
    simplified_payload = simplified.json()
    assert any(item["display_name"] == "启德海湾" for item in simplified_payload["items"])

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_import_srpe_live_index_maps_official_payload(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "live-index.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    sample_live_row = {
        "id": "11365",
        "developmentId": "11365",
        "engName": "ZENDO HOUSE",
        "chnName": "瑜意",
        "engPhaseName": None,
        "chnPhaseName": None,
        "engPhaseNo": None,
        "chnPhaseNo": None,
        "addresses": [
            {
                "engAddress": "8 TAK HING STREET",
                "chnAddress": "德興街 8號",
            }
        ],
        "planningArea1": {
            "planningAreaNameEng": "TSIM SHA TSUI",
            "planningAreaNameChn": "尖沙咀",
        },
        "planningArea2": None,
        "broadDistrict": {
            "broadDistrictNameEng": "TSUEN WAN AND WEST KOWLOON",
            "broadDistrictNameChn": "荃灣 及 西九龍",
        },
        "active": "N",
        "website": "www.zendohouse.com.hk",
        "latitude": "22.304603858356046",
        "longtitude": "114.17239421591539",
        "brochure": {
            "id": "28436",
            "dateOfPrint": "2026-02-12T00:00:00.000+08:00",
            "partFiles": [
                {
                    "id": "28436",
                    "seq": "1",
                    "partNo": "0",
                    "fileName": "8208026022700100.pdf",
                    "fullVersionInd": "Y",
                }
            ],
        },
    }

    monkeypatch.setattr(
        SRPEAdapter,
        "fetch_all_development_index",
        lambda self, language="en": {
            "code": 0,
            "resultData": {
                "total": 1,
                "list": [sample_live_row],
            },
        },
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_srpe_all_developments(session, language="en")

    assert summary.developments_created == 1
    assert summary.documents_upserted == 1
    assert summary.snapshots_created == 2

    client = TestClient(create_app())
    response = client.get("/api/v1/developments?lang=zh-Hant")
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["display_name"] == "瑜意"
    assert payload["items"][0]["district"] == "TSIM SHA TSUI"

    detail = client.get(f"/api/v1/developments/{payload['items'][0]['id']}?lang=en")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["display_name"] == "ZENDO HOUSE"
    assert detail_payload["documents"][0]["doc_type"] == "brochure"

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_import_srpe_live_index_with_details_adds_official_documents(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "live-detail.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    sample_live_row = {
        "id": "11365",
        "developmentId": "11365",
        "engName": "ZENDO HOUSE",
        "chnName": "瑜意",
        "addresses": [
            {
                "engAddress": "8 TAK HING STREET",
                "chnAddress": "德興街 8號",
            }
        ],
        "planningArea1": {
            "planningAreaNameEng": "TSIM SHA TSUI",
            "planningAreaNameChn": "尖沙咀",
        },
        "planningArea2": None,
        "broadDistrict": {
            "broadDistrictNameEng": "TSUEN WAN AND WEST KOWLOON",
            "broadDistrictNameChn": "荃灣 及 西九龍",
        },
        "active": "N",
        "website": "www.zendohouse.com.hk",
        "latitude": "22.304603858356046",
        "longtitude": "114.17239421591539",
        "brochure": None,
    }
    detail_result = {
        "dev": {
            "id": "11365",
            "engName": "ZENDO HOUSE",
            "chnName": "瑜意",
            "schnName": "瑜意",
            "addresses": [
                {
                    "engAddress": "8 TAK HING STREET",
                    "chnAddress": "德興街 8號",
                }
            ],
            "planningArea1": None,
            "planningArea2": None,
            "broadDistrict": None,
            "active": "N",
            "website": "www.zendohouse.com.hk",
            "latitude": "22.304603858356046",
            "longtitude": "114.17239421591539",
            "dateSuspendSales": "2026-03-25T08:00:00.000+08:00",
        },
        "brochureList": [
            {
                "id": "28436",
                "dateOfPrint": "2026-02-12T00:00:00.000+08:00",
                "partFiles": [
                    {
                        "id": "28436",
                        "seq": "1",
                        "partNo": "0",
                        "fileName": "8208026022700100.pdf",
                        "fullVersionInd": "Y",
                        "fileSize": 8455781,
                        "submissionTime": "2026-02-27T17:22:55.000+08:00",
                    }
                ],
            }
        ],
        "prices": [
            {
                "id": "37888",
                "serialNo": "1",
                "dateOfPrinting": "2026-03-05T00:00:00.000+08:00",
                "file": {
                    "id": "37888",
                    "fileName": "82080260305001PO.pdf",
                    "fileSize": 686437,
                    "submissionTime": "2026-03-05T12:53:15.000+08:00",
                },
            }
        ],
        "salesArrangements": [
            {
                "id": "25370",
                "dateOfPrinting": "2026-03-10T00:00:00.000+08:00",
                "file": {
                    "id": "25370",
                    "fileName": "82080260310002SA.pdf",
                    "fileSize": 861702,
                    "submissionTime": "2026-03-10T16:18:26.000+08:00",
                },
            }
        ],
        "transactions": [
            {
                "id": "99740",
                "updateDateTime": "2026-03-24T18:30:00.000+08:00",
                "file": {
                    "id": "99740",
                    "fileName": "82080260324007RT.pdf",
                    "fileSize": 1740018,
                    "submissionTime": "2026-03-24T18:35:45.000+08:00",
                },
            }
        ],
    }

    monkeypatch.setattr(
        SRPEAdapter,
        "fetch_all_development_index",
        lambda self, language="en": {
            "code": 0,
            "resultData": {
                "total": 1,
                "list": [sample_live_row],
            },
        },
    )
    monkeypatch.setattr(
        SRPEAdapter,
        "fetch_selected_development_result",
        lambda self, development_id, language="en", route_context="selected_dev_all_development": detail_result,
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_srpe_all_developments(session, language="en", include_details=True)

    assert summary.developments_created == 1
    assert summary.documents_upserted == 4
    assert summary.snapshots_created == 5

    client = TestClient(create_app())
    response = client.get("/api/v1/developments?lang=en")
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["district"] == "TSIM SHA TSUI"

    detail = client.get(f"/api/v1/developments/{payload['items'][0]['id']}?lang=en")
    assert detail.status_code == 200
    detail_payload = detail.json()
    document_types = {item["doc_type"] for item in detail_payload["documents"]}
    assert document_types == {
        "brochure",
        "price_list",
        "sales_arrangement",
        "transaction_record",
    }
    assert any(item["display_title"] == "Price List 1 - ZENDO HOUSE" for item in detail_payload["documents"])

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_import_centanet_sample_creates_listing_events(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "centanet.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_centanet_sample(session)

    assert summary.developments_created == 2
    assert summary.listings_upserted == 2
    assert summary.price_events_created == 2

    client = TestClient(create_app())
    feed = client.get("/api/v1/listings/feed?lang=zh-Hant")
    assert feed.status_code == 200
    feed_payload = feed.json()
    assert len(feed_payload) == 2
    assert {item["event_type"] for item in feed_payload} == {"new_listing"}
    assert any(item["development_name"] == "維港匯" for item in feed_payload)

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_import_centanet_search_results_html_creates_live_like_events(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "centanet-live.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "packages"
        / "connectors"
        / "src"
        / "hk_home_intel_connectors"
        / "fixtures"
        / "centanet_search_results_sample.html"
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_centanet_search_results(
            session,
            url="https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            html_path=str(fixture_path),
        )

    assert summary.developments_created == 1
    assert summary.listings_upserted == 2
    assert summary.price_events_created == 2

    client = TestClient(create_app())
    feed = client.get("/api/v1/listings/feed?lang=zh-Hant")
    assert feed.status_code == 200
    feed_payload = feed.json()
    assert len(feed_payload) == 2
    assert all(item["development_name"] == "匯璽" for item in feed_payload)
    assert {item["listing_id"] for item in feed_payload}

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_commercial_import_does_not_merge_by_generic_address_only(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "merge-safety.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory()
    with session_factory() as session:
        srpe_summary = import_srpe_sample(session)
        centanet_summary = import_centanet_sample(session)

        assert srpe_summary.developments_created == 2
        assert centanet_summary.developments_created == 2

    client = TestClient(create_app())
    response = client.get("/api/v1/developments?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert any(item["display_name"] == "MONACO ONE" for item in payload["items"])
    assert any(item["display_name"] == "啟德海灣" for item in payload["items"])

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()


def test_reimport_centanet_search_results_creates_price_change_events(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "centanet-price-change.db"
    monkeypatch.setenv("HHI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("HHI_ENV", "test")

    clear_settings_cache()
    reset_db_caches()

    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    fixture_dir = (
        Path(__file__).resolve().parents[1]
        / "packages"
        / "connectors"
        / "src"
        / "hk_home_intel_connectors"
        / "fixtures"
    )
    initial_fixture = fixture_dir / "centanet_search_results_sample.html"
    changed_fixture = fixture_dir / "centanet_search_results_price_change_sample.html"

    session_factory = get_session_factory()
    with session_factory() as session:
        first_summary = import_centanet_search_results(
            session,
            url="https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            html_path=str(initial_fixture),
        )
        second_summary = import_centanet_search_results(
            session,
            url="https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS",
            html_path=str(changed_fixture),
        )

        assert first_summary.price_events_created == 2
        assert second_summary.price_events_created == 2

    client = TestClient(create_app())
    feed = client.get("/api/v1/listings/feed?lang=zh-Hant&limit=10")
    assert feed.status_code == 200
    feed_payload = feed.json()
    assert any(item["event_type"] == "price_drop" and item["new_price_hkd"] == 8500000.0 for item in feed_payload)
    assert any(item["event_type"] == "price_raise" and item["new_price_hkd"] == 33000000.0 for item in feed_payload)

    client.close()
    engine.dispose()
    clear_settings_cache()
    reset_db_caches()
