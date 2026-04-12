from pathlib import Path

import httpx

from hk_home_intel_connectors.srpe import SRPEAdapter
from hk_home_intel_domain.enums import DocumentType
from hk_home_intel_domain.normalization import enrich_development_payload, normalize_hk_address
from hk_home_intel_shared.settings import clear_settings_cache


def test_srpe_entrypoint_discovery_from_fixture() -> None:
    adapter = SRPEAdapter()
    html = adapter.load_homepage_fixture()
    entrypoints = adapter.discover_entrypoints_from_html(html)

    urls = {item["url"] for item in entrypoints}
    assert "https://www.srpe.gov.hk/opip/disclaimer_index_for_all_residential.htm" in urls
    assert "https://www.srpe.gov.hk/opip/searchmap.htm" in urls


def test_srpe_bundle_entrypoint_discovery_from_fixture() -> None:
    adapter = SRPEAdapter()
    text = adapter.load_bundle_fixture()
    entrypoints = adapter.extract_entrypoints_from_bundle(text)

    urls = {item["url"] for item in entrypoints}
    assert "https://www.srpe.gov.hk/opip/disclaimer_index_for_all_residential.htm" in urls
    assert "https://www.srpe.gov.hk/opip/searchmap.htm" in urls


def test_enrich_development_payload_adds_normalized_address_and_centroid() -> None:
    payload = enrich_development_payload(
        {
            "address_raw": "  Kai   Tak,   Kowloon ",
            "district": "Kowloon City",
        }
    )

    assert normalize_hk_address("  Kai   Tak,   Kowloon ") == "Kai Tak, Kowloon"
    assert payload["address_normalized"] == "Kai Tak, Kowloon"
    assert payload["lat"] is not None
    assert payload["lng"] is not None


def test_enrich_development_payload_prefers_address_hint() -> None:
    payload = enrich_development_payload(
        {
            "address_raw": "North Point, Hong Kong",
            "district": "Hong Kong East",
        }
    )

    assert payload["address_normalized"] == "North Point, Hong Kong"
    assert payload["lat"] == 22.2918
    assert payload["lng"] == 114.2007


def test_srpe_download_document_file_writes_pdf(tmp_path: Path, monkeypatch) -> None:
    adapter = SRPEAdapter()

    requests: list[tuple[str, dict, dict | None]] = []

    class FakeResponse:
        def __init__(self, *, content: bytes = b"", headers: dict[str, str] | None = None, status_code: int = 200):
            self.content = content
            self.headers = headers or {}
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http error {self.status_code}")

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict | None = None):
            requests.append((url, json, headers))
            if url.endswith("/Map/getMapDevResultById"):
                assert json["devId"] == "11365"
                return FakeResponse(content=b'{"resultData": {}}', headers={"content-type": "application/json"})
            if url.endswith("/download/downloadPrice"):
                assert json == {"id": "37888", "seq": "", "devId": "11365"}
                return FakeResponse(content=b"%PDF-1.7 test", headers={"content-type": "application/pdf"})
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("hk_home_intel_connectors.srpe.create_client", lambda **kwargs: FakeClient())

    result = adapter.download_document_file(
        document_type=DocumentType.PRICE_LIST,
        development_external_id="11365",
        document_metadata={
            "metadata_json": {
                "record": {
                    "id": "37888",
                },
                "file_name": "82080260305001PO.pdf",
            },
        },
        output_dir=tmp_path,
    )

    downloaded = tmp_path / "82080260305001PO.pdf"
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"%PDF-1.7 test"
    assert result["mime_type"] == "application/pdf"
    assert result["file_name"] == "82080260305001PO.pdf"
    assert len(requests) == 2
    assert requests[0][0] == "https://www.srpe.gov.hk/api/SrpeWebService/Map/getMapDevResultById"
    assert requests[1][0] == "https://www.srpe.gov.hk/api/SrpeWebService/download/downloadPrice"


def test_create_client_defaults_to_trusting_env(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("hk_home_intel_connectors.http.httpx.Client", FakeClient)
    monkeypatch.delenv("HHI_HTTP_TRUST_ENV", raising=False)
    clear_settings_cache()

    from hk_home_intel_connectors.http import create_client

    create_client()
    assert captured["trust_env"] is True
    clear_settings_cache()


def test_fetch_text_falls_back_to_curl_on_httpx_error(monkeypatch) -> None:
    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            raise httpx.ConnectError("ssl eof")

    class CurlResult:
        stdout = "<html>ok</html>"

    monkeypatch.setattr("hk_home_intel_connectors.http.create_client", lambda **kwargs: FailingClient())
    monkeypatch.setattr(
        "hk_home_intel_connectors.http.subprocess.run",
        lambda *args, **kwargs: CurlResult(),
    )

    from hk_home_intel_connectors.http import fetch_text

    assert fetch_text("https://example.com") == "<html>ok</html>"
