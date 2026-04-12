from __future__ import annotations

import json
import mimetypes
from datetime import date, datetime
import hashlib
from pathlib import Path
import re
from urllib.parse import urljoin
from typing import Any

from hk_home_intel_connectors.base import RawRecord, SourceAdapter
from hk_home_intel_connectors.html import extract_assets, extract_links
from hk_home_intel_connectors.http import create_client, fetch_text, post_json
from hk_home_intel_domain.enums import (
    DocumentType,
    ListingSegment,
    ListingStatus,
    ListingType,
    SourceConfidence,
    TransactionType,
)
from hk_home_intel_domain.i18n import build_translation_map


class SRPEAdapter(SourceAdapter):
    source_name = "srpe"
    base_url = "https://www.srpe.gov.hk"
    homepage_url = "https://www.srpe.gov.hk/opip/index.htm"
    service_base_url = "https://www.srpe.gov.hk/api/SrpeWebService"
    service_prefix = "/api/SrpeWebService"
    sample_fixture_path = Path(__file__).with_name("fixtures").joinpath("srpe_sample.json")
    homepage_fixture_path = Path(__file__).with_name("fixtures").joinpath("srpe_homepage_sample.html")
    bundle_fixture_path = Path(__file__).with_name("fixtures").joinpath("srpe_bundle_sample.js")
    index_action_type = "Index For All Residential"
    index_from_path = "disclaimer_index_for_all_residential"
    detail_map_contexts = {
        "all_development",
        "selected_dev_all_development_t18m",
        "selected_dev_by_year_of_sb",
        "selected_dev_all_development",
        "selected_dev_newly_upload",
    }
    known_entrypoints = {
        "Index for Residential Developments": "/opip/disclaimer_index_for_all_residential.htm",
        "Search by Map": "/opip/searchmap.htm",
        "Newly Uploaded Sales Documents": "/opip/new_upload.htm",
        "Search for Residential Developments": "/opip/search.htm",
    }

    def discover_developments(self) -> list[RawRecord]:
        return []

    def discover_documents(self) -> list[RawRecord]:
        return []

    def load_sample_dataset(self, path: str | None = None) -> dict[str, Any]:
        fixture_path = Path(path) if path else self.sample_fixture_path
        return json.loads(fixture_path.read_text(encoding="utf-8"))

    def sample_development_bundle(self, path: str | None = None) -> list[dict[str, Any]]:
        dataset = self.load_sample_dataset(path)
        bundles: list[dict[str, Any]] = []
        for development in dataset.get("developments", []):
            development_id = str(development["external_id"])
            bundle = {
                "development": RawRecord(
                    source=self.source_name,
                    external_id=development_id,
                    payload=development,
                    source_url=development.get("source_url"),
                ),
                "documents": [
                    RawRecord(
                        source=self.source_name,
                        external_id=str(item["external_id"]),
                        payload=item,
                        source_url=item.get("source_url"),
                    )
                    for item in development.get("documents", [])
                ],
                "listings": [
                    RawRecord(
                        source=self.source_name,
                        external_id=str(item["external_id"]),
                        payload=item,
                        source_url=item.get("source_url"),
                    )
                    for item in development.get("listings", [])
                ],
                "transactions": [
                    RawRecord(
                        source=self.source_name,
                        external_id=str(item["external_id"]),
                        payload=item,
                        source_url=item.get("source_url"),
                    )
                    for item in development.get("transactions", [])
                ],
            }
            bundles.append(bundle)
        return bundles

    def fetch_homepage_html(self) -> str:
        return fetch_text(self.homepage_url)

    def load_homepage_fixture(self) -> str:
        return self.homepage_fixture_path.read_text(encoding="utf-8")

    def load_bundle_fixture(self) -> str:
        return self.bundle_fixture_path.read_text(encoding="utf-8")

    def fetch_all_development_bundles(
        self,
        *,
        language: str = "en",
        limit: int | None = None,
        offset: int = 0,
        include_details: bool = False,
    ) -> list[dict[str, Any]]:
        dataset = self.fetch_all_development_index(language=language)
        items = dataset.get("resultData", {}).get("list", [])
        if items and offset:
            normalized_offset = offset % len(items)
            items = items[normalized_offset:] + items[:normalized_offset]
        bundles: list[dict[str, Any]] = []
        for item in items[:limit] if limit else items:
            bundle = self.build_live_development_bundle(
                item,
                language=language,
                include_details=include_details,
            )
            if bundle is not None:
                bundles.append(bundle)
        return bundles

    def fetch_all_development_index(self, *, language: str = "en") -> dict[str, Any]:
        return self._post_service_json(
            "/DistrictAreaSearch/getDistrictAreaSearchResult",
            {
                "language": self._srpe_language(language),
                "fromPath": self.index_from_path,
                "planningAreaId": "",
                "planningAreaIds": [],
                "actionType": self.index_action_type,
                "page": None,
                "limit": None,
            },
        )

    def fetch_development_name_sort_keys_all(self, *, language: str = "en") -> dict[str, Any]:
        return self._post_service_json(
            "/DistrictAreaSearch/getDevelopmentNameSortKeysAll",
            {
                "language": self._srpe_language(language),
                "actionType": self.index_action_type,
            },
        )

    def fetch_district_area_search_filter(self, *, language: str = "en") -> dict[str, Any]:
        return self._post_service_json(
            "/DistrictAreaSearch/getDistrictAreaSearchFilter",
            {
                "language": self._srpe_language(language),
            },
        )

    def fetch_selected_development_result(
        self,
        *,
        development_id: str,
        language: str = "en",
        route_context: str = "selected_dev_all_development",
    ) -> dict[str, Any]:
        if route_context in self.detail_map_contexts:
            response = self._post_service_json(
                "/Map/getMapDevResultById",
                {
                    "language": self._srpe_language(language),
                    "timeStamp": int(datetime.now().timestamp() * 1000),
                    "devId": development_id,
                    "actionType": "developments details",
                },
            )
            return response.get("resultData", {})

        response = self._post_service_json(
            "/DevBldgSearch/getSelectedDevResult",
            {
                "language": self._srpe_language(language),
                "devId": development_id,
            },
        )
        return response.get("resultData", {}).get("devInfoResp", {})

    def download_document_file(
        self,
        *,
        document_type: DocumentType,
        development_external_id: str,
        document_metadata: dict[str, Any] | None,
        output_dir: Path,
    ) -> dict[str, Any]:
        metadata = self._unwrap_document_metadata(document_metadata or {})
        record = metadata.get("record") or {}
        file_name = metadata.get("file_name") or self._infer_document_file_name(record)
        if not file_name:
            raise ValueError("missing SRPE document file name")

        payload = self._build_document_download_payload(
            document_type=document_type,
            development_external_id=development_external_id,
            metadata=metadata,
        )
        endpoint = self._document_download_service_path(document_type)
        with create_client(
            timeout=60.0,
            headers={"Accept": "application/json, application/octet-stream, */*;q=0.8"},
        ) as client:
            # SRPE document endpoints require the session established by the
            # selected development detail call made from the same cookie jar.
            self._prime_document_download_session(
                client=client,
                development_external_id=development_external_id,
            )
            response = client.post(
                self._service_url(endpoint),
                json=payload,
                headers={"Accept": "application/octet-stream, */*"},
            )
            response.raise_for_status()
            content = response.content
            headers = dict(response.headers)
            http_status = response.status_code

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / file_name
        destination.write_bytes(content)
        content_hash = hashlib.sha256(content).hexdigest()
        mime_type = headers.get("content-type") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        return {
            "path": str(destination),
            "content_hash": content_hash,
            "mime_type": mime_type,
            "bytes": len(content),
            "http_status": http_status,
            "headers": headers,
            "file_name": file_name,
        }

    def discover_entrypoints_from_html(self, html: str) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()
        keywords = (
            "residential developments",
            "newly uploaded",
            "search by map",
            "search",
            "price list",
            "transaction",
        )
        for item in extract_links(html):
            href = item["href"].strip()
            text = item["text"].strip()
            if not href:
                continue
            absolute = urljoin(self.homepage_url, href)
            haystack = f"{href} {text}".lower()
            if "srpe.gov.hk/opip" not in absolute:
                continue
            if not any(keyword in haystack for keyword in keywords):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            candidates.append({"label": text or href, "url": absolute})

        if candidates:
            return candidates

        # Live SRPE homepage is now a JS shell. Fall back to known stable routes.
        for label, route in self.known_entrypoints.items():
            absolute = urljoin(self.homepage_url, route)
            if absolute in seen:
                continue
            seen.add(absolute)
            candidates.append({"label": label, "url": absolute})
        return candidates

    def discover_asset_urls_from_html(self, html: str) -> list[str]:
        assets = []
        seen: set[str] = set()
        for asset in extract_assets(html):
            absolute = urljoin(self.homepage_url, asset)
            if "srpe.gov.hk/opip/" not in absolute:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            assets.append(absolute)
        return assets

    def extract_entrypoints_from_bundle(self, text: str) -> list[dict[str, str]]:
        matches = re.findall(r"/opip/[A-Za-z0-9_./-]+\.htm", text)
        route_matches = re.findall(r'path:"(/[^"]+)"', text)
        seen: set[str] = set()
        results: list[dict[str, str]] = []
        for route in matches:
            absolute = urljoin(self.homepage_url, route)
            if absolute in seen:
                continue
            seen.add(absolute)
            results.append({"label": Path(route).name, "url": absolute})

        interesting_route_keywords = (
            "development",
            "search",
            "map",
            "upload",
            "brochure",
            "district",
            "lot",
            "selected_dev",
        )
        for route in route_matches:
            lowered = route.lower()
            if not any(keyword in lowered for keyword in interesting_route_keywords):
                continue
            absolute = self._opip_route_url(route)
            if absolute in seen:
                continue
            seen.add(absolute)
            results.append({"label": route.strip("/"), "url": absolute})
        return results

    def normalize_development(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        name_zh = payload.get("name_zh") or payload.get("name_zh_hant")
        name_en = payload.get("name_en")
        aliases = [value for value in [name_en, name_zh] if value]

        return {
            "source": payload.get("source") or self.source_name,
            "source_external_id": payload.get("source_external_id") or record.external_id,
            "source_url": payload.get("source_url") or record.source_url or self.base_url,
            "name_zh": name_zh,
            "name_en": name_en,
            "name_translations_json": build_translation_map(
                zh_hant=payload.get("name_zh_hant") or name_zh,
                zh_hans=payload.get("name_zh_hans") or name_zh,
                en=name_en,
                existing=payload.get("name_translations"),
            ),
            "aliases_json": aliases,
            "address_raw": payload.get("address"),
            "address_translations_json": build_translation_map(
                zh_hant=payload.get("address_zh_hant"),
                zh_hans=payload.get("address_zh_hans"),
                en=payload.get("address_en"),
                existing=payload.get("address_translations"),
            ),
            "district": payload.get("district"),
            "subdistrict": payload.get("subdistrict"),
            "region": payload.get("region"),
            "lat": payload.get("lat"),
            "lng": payload.get("lng"),
            "developer_names_json": payload.get("developers", []),
            "completion_year": payload.get("completion_year"),
            "listing_segment": ListingSegment(payload.get("listing_segment", "first_hand_remaining")),
            "tags_json": payload.get("tags", []),
            "source_confidence": SourceConfidence(payload.get("source_confidence", "high")),
        }

    def normalize_document(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        metadata = self._unwrap_document_metadata(payload)

        return {
            "source": self.source_name,
            "source_doc_id": record.external_id,
            "title": payload.get("title", record.external_id),
            "title_translations_json": build_translation_map(
                zh_hant=payload.get("title_zh_hant"),
                zh_hans=payload.get("title_zh_hans"),
                en=payload.get("title_en"),
                existing=payload.get("title_translations"),
            ),
            "doc_type": self._classify_document(payload.get("doc_type")),
            "source_url": record.source_url or self.base_url,
            "published_at": self._parse_datetime(payload.get("published_at")),
            "metadata_json": metadata,
        }

    def normalize_listing(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        return {
            "source": self.source_name,
            "source_listing_id": record.external_id,
            "source_url": record.source_url or self.base_url,
            "title": payload.get("title"),
            "title_translations_json": build_translation_map(
                zh_hant=payload.get("title_zh_hant"),
                zh_hans=payload.get("title_zh_hans"),
                en=payload.get("title_en"),
                existing=payload.get("title_translations"),
            ),
            "listing_type": ListingType(payload.get("listing_type", "first_hand_remaining")),
            "asking_price_hkd": payload.get("asking_price_hkd"),
            "price_per_sqft": payload.get("price_per_sqft"),
            "bedrooms": payload.get("bedrooms"),
            "bathrooms": payload.get("bathrooms"),
            "saleable_area_sqft": payload.get("saleable_area_sqft"),
            "gross_area_sqft": payload.get("gross_area_sqft"),
            "status": ListingStatus(payload.get("status", "active")),
            "first_seen_at": self._parse_datetime(payload.get("first_seen_at")),
            "last_seen_at": self._parse_datetime(payload.get("last_seen_at")),
            "raw_payload_json": payload,
        }

    def normalize_transaction(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        return {
            "source": self.source_name,
            "source_record_id": record.external_id,
            "source_url": record.source_url or self.base_url,
            "transaction_date": self._parse_date(payload.get("transaction_date")),
            "registration_date": self._parse_date(payload.get("registration_date")),
            "price_hkd": payload.get("price_hkd"),
            "price_per_sqft": payload.get("price_per_sqft"),
            "transaction_type": TransactionType(payload.get("transaction_type", "primary")),
            "doc_ref": payload.get("doc_ref"),
            "raw_payload_json": payload,
        }

    def _classify_document(self, raw_value: str | None) -> DocumentType:
        normalized = (raw_value or "").strip().lower()
        mapping = {
            "brochure": DocumentType.BROCHURE,
            "price_list": DocumentType.PRICE_LIST,
            "sales_arrangement": DocumentType.SALES_ARRANGEMENT,
            "transaction_record": DocumentType.TRANSACTION_RECORD,
            "floor_plan": DocumentType.FLOOR_PLAN,
        }
        return mapping.get(normalized, DocumentType.OTHER)

    def _parse_datetime(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
            return None
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))

    def _parse_date(self, raw_value: str | None) -> date | None:
        if not raw_value:
            return None
        return date.fromisoformat(raw_value)

    def _opip_route_url(self, route: str) -> str:
        return urljoin(self.homepage_url, route.lstrip("/"))

    def build_live_development_bundle(
        self,
        item: dict[str, Any],
        *,
        language: str = "en",
        include_details: bool = False,
    ) -> dict[str, Any] | None:
        development_payload = self._map_live_index_item_to_development_payload(item)
        if not development_payload.get("source_external_id"):
            return None

        development_id = str(development_payload["source_external_id"])
        source_url = development_payload.get("source_url")
        documents_payload = self._map_live_index_item_to_documents(item, development_payload)

        if include_details:
            detail_result = self.fetch_selected_development_result(
                development_id=development_id,
                language=language,
                route_context="selected_dev_all_development",
            )
            detail_payload = self._map_live_detail_result_to_development_payload(detail_result)
            development_payload = self._merge_payload_values(development_payload, detail_payload)
            documents_payload = self._dedupe_document_payloads(
                documents_payload + self._map_live_detail_result_to_documents(detail_result, development_payload)
            )

        return {
            "development": RawRecord(
                source=self.source_name,
                external_id=development_id,
                payload=development_payload,
                source_url=source_url,
            ),
            "documents": [
                RawRecord(
                    source=self.source_name,
                    external_id=str(document["external_id"]),
                    payload=document,
                    source_url=document.get("source_url"),
                )
                for document in documents_payload
            ],
            "listings": [],
            "transactions": [],
        }

    def _map_live_index_item_to_development_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        development_id = str(item.get("developmentId") or item.get("id") or "")
        eng_name, chn_name = self._compose_live_names(item)
        zh_hans_name = item.get("schnName") or chn_name
        addresses = item.get("addresses") or []
        address_en = "; ".join(part.get("engAddress") for part in addresses if part.get("engAddress")) or None
        address_zh = "; ".join(part.get("chnAddress") for part in addresses if part.get("chnAddress")) or None
        planning_area_1 = item.get("planningArea1") or {}
        planning_area_2 = item.get("planningArea2") or {}
        broad_district = item.get("broadDistrict") or {}
        tags = ["srpe", "first_hand"]
        if item.get("active") == "Y":
            tags.append("sales_active")
            listing_segment = ListingSegment.FIRST_HAND_REMAINING.value
        else:
            tags.append("sales_inactive")
            listing_segment = ListingSegment.MIXED.value

        return {
            "source": self.source_name,
            "source_external_id": development_id,
            "source_url": self._selected_development_url(development_id),
            "name_en": eng_name,
            "name_zh_hant": chn_name,
            "name_zh_hans": zh_hans_name,
            "name_translations": build_translation_map(
                zh_hant=chn_name,
                zh_hans=zh_hans_name,
                en=eng_name,
            ),
            "address": address_en or address_zh,
            "address_en": address_en,
            "address_zh_hant": address_zh,
            "address_zh_hans": address_zh,
            "district": planning_area_1.get("planningAreaNameEng") or item.get("engDistrict"),
            "subdistrict": planning_area_2.get("planningAreaNameEng"),
            "region": broad_district.get("broadDistrictNameEng"),
            "lat": self._parse_float(item.get("latitude")),
            "lng": self._parse_float(item.get("longtitude")),
            "developers": [],
            "completion_year": None,
            "listing_segment": listing_segment,
            "tags": tags,
            "source_confidence": SourceConfidence.HIGH.value,
        }

    def _map_live_index_item_to_documents(
        self,
        item: dict[str, Any],
        development_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        brochure = item.get("brochure")
        if not brochure or not brochure.get("id"):
            return []

        display_en = development_payload.get("name_en")
        display_zh = development_payload.get("name_zh_hant")
        display_zh_hans = development_payload.get("name_zh_hans") or display_zh
        base_title_en = "Sales Brochure"
        base_title_zh_hant = "售楼说明书"
        base_title_zh_hans = "售楼说明书"

        return [
            self._build_live_document_payload(
                external_id=f"brochure:{brochure['id']}",
                doc_type=DocumentType.BROCHURE,
                development_payload=development_payload,
                published_at=brochure.get("dateOfPrint") or development_payload.get("published_at"),
                raw_item=brochure,
                file_info=self._extract_brochure_file_info(brochure),
            )
        ]

    def _map_live_detail_result_to_development_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        dev = result.get("dev") or {}
        if not dev:
            return {}

        eng_name, chn_name = self._compose_live_names(dev)
        zh_hans_name = dev.get("schnName") or chn_name
        addresses = dev.get("addresses") or []
        address_en = "; ".join(part.get("engAddress") for part in addresses if part.get("engAddress")) or None
        address_zh = "; ".join(part.get("chnAddress") for part in addresses if part.get("chnAddress")) or None
        planning_area_1 = dev.get("planningArea1") or {}
        planning_area_2 = dev.get("planningArea2") or {}
        broad_district = dev.get("broadDistrict") or {}
        tags = ["srpe", "first_hand"]
        if dev.get("active") == "Y":
            tags.append("sales_active")
            listing_segment = ListingSegment.FIRST_HAND_REMAINING.value
        else:
            tags.append("sales_inactive")
            listing_segment = ListingSegment.MIXED.value
        if dev.get("dateSuspendSales"):
            tags.append("sales_suspended")
        if dev.get("dateCompleteSales"):
            tags.append("sales_completed")

        return {
            "source": self.source_name,
            "source_external_id": str(dev.get("id") or ""),
            "source_url": self._selected_development_url(str(dev.get("id") or "")),
            "name_en": eng_name,
            "name_zh_hant": chn_name,
            "name_zh_hans": zh_hans_name,
            "name_translations": build_translation_map(
                zh_hant=chn_name,
                zh_hans=zh_hans_name,
                en=eng_name,
            ),
            "address": address_en or address_zh,
            "address_en": address_en,
            "address_zh_hant": address_zh,
            "address_zh_hans": address_zh,
            "district": planning_area_1.get("planningAreaNameEng") or dev.get("engDistrict"),
            "subdistrict": planning_area_2.get("planningAreaNameEng"),
            "region": broad_district.get("broadDistrictNameEng"),
            "lat": self._parse_float(dev.get("latitude")),
            "lng": self._parse_float(dev.get("longtitude")),
            "completion_year": None,
            "listing_segment": listing_segment,
            "tags": tags,
            "source_confidence": SourceConfidence.HIGH.value,
        }

    def _map_live_detail_result_to_documents(
        self,
        result: dict[str, Any],
        development_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        brochure_list = result.get("brochureList") or ([result["brochure"]] if result.get("brochure") else [])
        for brochure in brochure_list:
            documents.append(
                self._build_live_document_payload(
                    external_id=f"brochure:{brochure['id']}",
                    doc_type=DocumentType.BROCHURE,
                    development_payload=development_payload,
                    published_at=brochure.get("dateOfPrint"),
                    raw_item=brochure,
                    file_info=self._extract_brochure_file_info(brochure),
                )
            )

        for price in result.get("prices") or []:
            documents.append(
                self._build_live_document_payload(
                    external_id=f"price_list:{price['id']}",
                    doc_type=DocumentType.PRICE_LIST,
                    development_payload=development_payload,
                    published_at=price.get("dateOfPrinting"),
                    raw_item=price,
                    serial_no=price.get("serialNo"),
                    file_info=self._extract_file_info(price.get("file")),
                )
            )

        for arrangement in result.get("salesArrangements") or []:
            documents.append(
                self._build_live_document_payload(
                    external_id=f"sales_arrangement:{arrangement['id']}",
                    doc_type=DocumentType.SALES_ARRANGEMENT,
                    development_payload=development_payload,
                    published_at=arrangement.get("dateOfPrinting"),
                    raw_item=arrangement,
                    serial_no=arrangement.get("serialNo"),
                    file_info=self._extract_file_info(arrangement.get("file")),
                )
            )

        for transaction in result.get("transactions") or []:
            documents.append(
                self._build_live_document_payload(
                    external_id=f"transaction_record:{transaction['id']}",
                    doc_type=DocumentType.TRANSACTION_RECORD,
                    development_payload=development_payload,
                    published_at=transaction.get("updateDateTime") or transaction.get("updateTime"),
                    raw_item=transaction,
                    file_info=self._extract_file_info(transaction.get("file")),
                )
            )

        return self._dedupe_document_payloads(documents)

    def _build_live_document_payload(
        self,
        *,
        external_id: str,
        doc_type: DocumentType,
        development_payload: dict[str, Any],
        raw_item: dict[str, Any],
        published_at: str | None,
        serial_no: str | None = None,
        file_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        title_en, title_zh_hant, title_zh_hans = self._document_titles(
            doc_type=doc_type,
            development_payload=development_payload,
            serial_no=serial_no,
        )
        metadata = {
            "record": raw_item,
            **(file_info or {}),
        }
        return {
            "external_id": external_id,
            "title": title_en,
            "title_en": title_en,
            "title_zh_hant": title_zh_hant,
            "title_zh_hans": title_zh_hans,
            "doc_type": doc_type.value,
            "published_at": published_at,
            "source_url": development_payload.get("source_url"),
            "metadata_json": metadata,
        }

    def _document_titles(
        self,
        *,
        doc_type: DocumentType,
        development_payload: dict[str, Any],
        serial_no: str | None = None,
    ) -> tuple[str, str, str]:
        display_en = development_payload.get("name_en")
        display_zh_hant = development_payload.get("name_zh_hant") or development_payload.get("name_zh")
        display_zh_hans = development_payload.get("name_zh_hans") or display_zh_hant
        labels = {
            DocumentType.BROCHURE: ("Sales Brochure", "售樓說明書", "售楼说明书"),
            DocumentType.PRICE_LIST: ("Price List", "價單", "价单"),
            DocumentType.SALES_ARRANGEMENT: ("Sales Arrangement", "銷售安排", "销售安排"),
            DocumentType.TRANSACTION_RECORD: ("Register of Transactions", "成交紀錄冊", "成交纪录册"),
            DocumentType.FLOOR_PLAN: ("Floor Plan", "平面圖", "平面图"),
            DocumentType.OTHER: ("Document", "文件", "文件"),
        }
        label_en, label_zh_hant, label_zh_hans = labels[doc_type]
        if serial_no:
            label_en = f"{label_en} {serial_no}"
            label_zh_hant = f"{label_zh_hant} {serial_no}"
            label_zh_hans = f"{label_zh_hans} {serial_no}"

        return (
            f"{label_en} - {display_en}" if display_en else label_en,
            f"{label_zh_hant} - {display_zh_hant}" if display_zh_hant else label_zh_hant,
            f"{label_zh_hans} - {display_zh_hans}" if display_zh_hans else label_zh_hans,
        )

    def _extract_brochure_file_info(self, brochure: dict[str, Any]) -> dict[str, Any]:
        part_files = brochure.get("partFiles") or []
        preferred = next((item for item in part_files if item.get("fullVersionInd") == "Y"), None)
        return self._extract_file_info(preferred or (part_files[0] if part_files else None))

    def _extract_file_info(self, file_record: dict[str, Any] | None) -> dict[str, Any]:
        if not file_record:
            return {}
        return {
            "file_id": file_record.get("id"),
            "file_name": file_record.get("fileName"),
            "file_size": file_record.get("fileSize"),
            "submission_time": file_record.get("submissionTime"),
            "seq": file_record.get("seq"),
            "part_no": file_record.get("partNo"),
            "full_version_ind": file_record.get("fullVersionInd"),
        }

    def _merge_payload_values(
        self,
        base: dict[str, Any],
        overlay: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(base)
        for key, value in overlay.items():
            if value in (None, "", [], {}):
                continue
            merged[key] = value
        return merged

    def _dedupe_document_payloads(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for document in documents:
            external_id = str(document.get("external_id") or "")
            if not external_id:
                continue
            deduped[external_id] = document
        return list(deduped.values())

    def _document_download_service_path(self, document_type: DocumentType) -> str:
        mapping = {
            DocumentType.BROCHURE: "/download/downloadBrochure",
            DocumentType.PRICE_LIST: "/download/downloadPrice",
            DocumentType.SALES_ARRANGEMENT: "/download/downloadSalesArrangement",
            DocumentType.TRANSACTION_RECORD: "/download/downloadTrx",
        }
        if document_type not in mapping:
            raise ValueError(f"unsupported SRPE document download type: {document_type.value}")
        return mapping[document_type]

    def _build_document_download_payload(
        self,
        *,
        document_type: DocumentType,
        development_external_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        record = metadata.get("record") or {}
        payload: dict[str, Any] = {
            "id": record.get("id") or metadata.get("file_id"),
            "seq": metadata.get("seq") or "",
            "devId": development_external_id,
        }
        if document_type is DocumentType.BROCHURE:
            if metadata.get("part_no") not in (None, ""):
                payload["partNo"] = metadata.get("part_no")
        return payload

    def _prime_document_download_session(
        self,
        *,
        client: Any,
        development_external_id: str,
        language: str = "en",
    ) -> None:
        response = client.post(
            self._service_url("/Map/getMapDevResultById"),
            json={
                "language": self._srpe_language(language),
                "timeStamp": int(datetime.now().timestamp() * 1000),
                "devId": development_external_id,
                "actionType": "developments details",
            },
        )
        response.raise_for_status()

    def _infer_document_file_name(self, record: dict[str, Any]) -> str | None:
        part_files = record.get("partFiles") or []
        if part_files:
            preferred = next((item for item in part_files if item.get("fullVersionInd") == "Y"), None)
            target = preferred or part_files[0]
            return target.get("fileName")
        file_record = record.get("file") or {}
        return file_record.get("fileName")

    def _unwrap_document_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata_json")
        if isinstance(metadata, dict):
            return metadata
        return payload

    def _compose_live_names(self, item: dict[str, Any]) -> tuple[str | None, str | None]:
        eng_name = item.get("engName")
        chn_name = item.get("chnName")
        eng_phase_name = item.get("engPhaseName")
        chn_phase_name = item.get("chnPhaseName")
        eng_phase_no = item.get("engPhaseNo")
        chn_phase_no = item.get("chnPhaseNo")

        if eng_phase_name:
            eng_name = self._join_name_parts(eng_name, eng_phase_name)
        elif eng_phase_no:
            eng_name = self._join_name_parts(eng_name, f"Phase {eng_phase_no}")

        if chn_phase_name:
            chn_name = self._join_name_parts(chn_name, chn_phase_name)
        elif chn_phase_no:
            chn_name = self._join_name_parts(chn_name, chn_phase_no)

        return eng_name, chn_name

    def _join_name_parts(self, base: str | None, suffix: str | None) -> str | None:
        parts = [value.strip() for value in [base, suffix] if value and value.strip()]
        if not parts:
            return None
        if len(parts) == 2 and parts[0] == parts[1]:
            return parts[0]
        return " - ".join(parts)

    def _post_service_json(self, service_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return post_json(self._service_url(service_path), payload)

    def _service_url(self, service_path: str) -> str:
        normalized_path = service_path if service_path.startswith("/") else f"/{service_path}"
        return f"{self.service_base_url}{normalized_path}"

    def _selected_development_url(self, development_id: str) -> str:
        return urljoin(
            self.homepage_url,
            f"selected_dev_all_development?devId={development_id}",
        )

    def _srpe_language(self, language: str) -> str:
        normalized = language.strip().lower()
        if normalized in {"zh-hant", "zhhk", "tc"}:
            return "tc"
        if normalized in {"zh-hans", "zhcn", "sc"}:
            return "sc"
        return "en"

    def _parse_float(self, raw_value: str | float | int | None) -> float | None:
        if raw_value in (None, ""):
            return None
        return float(raw_value)
