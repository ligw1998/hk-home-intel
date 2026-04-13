from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from hk_home_intel_connectors.base import RawRecord, SourceAdapter
from hk_home_intel_connectors.http import fetch_text
from hk_home_intel_domain.enums import ListingStatus, ListingType, SourceConfidence
from hk_home_intel_domain.i18n import build_translation_map


class CentanetAdapter(SourceAdapter):
    source_name = "centanet"
    base_url = "https://hk.centanet.com"
    sample_fixture_path = Path(__file__).with_name("fixtures").joinpath("centanet_sample.json")
    sample_search_results_html_path = Path(__file__).with_name("fixtures").joinpath("centanet_search_results_sample.html")
    sample_detail_html_path = Path(__file__).with_name("fixtures").joinpath("centanet_detail_sample.html")

    def discover_developments(self) -> list[RawRecord]:
        return []

    def discover_documents(self) -> list[RawRecord]:
        return []

    def load_sample_dataset(self, path: str | None = None) -> dict[str, Any]:
        fixture_path = Path(path) if path else self.sample_fixture_path
        return json.loads(fixture_path.read_text(encoding="utf-8"))

    def sample_listing_bundle(self, path: str | None = None) -> list[dict[str, Any]]:
        dataset = self.load_sample_dataset(path)
        bundles: list[dict[str, Any]] = []
        for listing in dataset.get("listings", []):
            development = {
                "source": self.source_name,
                "source_external_id": listing["development"]["external_id"],
                "source_url": listing["development"].get("source_url"),
                "name_zh": listing["development"].get("name_zh"),
                "name_en": listing["development"].get("name_en"),
                "name_translations": listing["development"].get("name_translations"),
                "address": listing["development"].get("address"),
                "district": listing["development"].get("district"),
                "region": listing["development"].get("region"),
                "lat": listing["development"].get("lat"),
                "lng": listing["development"].get("lng"),
                "listing_segment": "second_hand",
                "source_confidence": "medium",
            }
            bundles.append(
                {
                    "development": RawRecord(
                        source=self.source_name,
                        external_id=str(development["source_external_id"]),
                        payload=development,
                        source_url=development.get("source_url"),
                    ),
                    "documents": [],
                    "listings": [
                        RawRecord(
                            source=self.source_name,
                            external_id=str(listing["external_id"]),
                            payload=listing,
                            source_url=listing.get("source_url"),
                        )
                    ],
                    "transactions": [],
                }
            )
        return bundles

    def fetch_search_results_html(self, url: str) -> str:
        return fetch_text(url)

    def fetch_listing_detail_html(self, url: str) -> str:
        return fetch_text(url)

    def search_results_listing_bundle(
        self,
        *,
        url: str,
        html_text: str | None = None,
        html_path: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if html_text is None:
            if html_path:
                html_text = Path(html_path).read_text(encoding="utf-8")
            else:
                html_text = self.fetch_search_results_html(url)

        development_name = self._extract_page_development_name(html_text, url)
        development_external_id = f"estate:{self._extract_page_slug(url, development_name)}"
        listings = self._parse_search_result_cards(html_text, page_url=url, development_name=development_name)
        if limit is not None:
            listings = listings[:limit]

        bundles: list[dict[str, Any]] = []
        for listing in listings:
            development = {
                "source": self.source_name,
                "source_external_id": development_external_id,
                "source_url": url,
                "name_zh": development_name,
                "name_en": None,
                "name_translations": {
                    "zh-Hant": development_name,
                    "zh-Hans": development_name,
                },
                "address": None,
                "district": None,
                "region": None,
                "lat": None,
                "lng": None,
                "listing_segment": "second_hand",
                "source_confidence": "medium",
            }
            bundles.append(
                {
                    "development": RawRecord(
                        source=self.source_name,
                        external_id=development_external_id,
                        payload=development,
                        source_url=url,
                    ),
                    "documents": [],
                    "listings": [
                        RawRecord(
                            source=self.source_name,
                            external_id=str(listing["external_id"]),
                            payload=listing,
                            source_url=listing.get("source_url"),
                        )
                    ],
                    "transactions": [],
                }
            )
        return bundles

    def detail_listing_bundle(
        self,
        *,
        url: str,
        html_text: str | None = None,
        html_path: str | None = None,
    ) -> list[dict[str, Any]]:
        if html_text is None:
            if html_path:
                html_text = Path(html_path).read_text(encoding="utf-8")
            else:
                html_text = self.fetch_listing_detail_html(url)

        listing = self._parse_detail_page(html_text, url=url)
        development = listing["development"]
        return [
            {
                "development": RawRecord(
                    source=self.source_name,
                    external_id=str(development["external_id"]),
                    payload={
                        "source": self.source_name,
                        "source_external_id": development["external_id"],
                        "source_url": development.get("source_url"),
                        "name_zh": development.get("name_zh"),
                        "name_en": development.get("name_en"),
                        "name_translations": development.get("name_translations"),
                        "address": development.get("address"),
                        "district": development.get("district"),
                        "region": development.get("region"),
                        "lat": development.get("lat"),
                        "lng": development.get("lng"),
                        "developer_names": development.get("developer_names"),
                        "listing_segment": "second_hand",
                        "source_confidence": "medium",
                    },
                    source_url=development.get("source_url"),
                ),
                "documents": [],
                "listings": [
                    RawRecord(
                        source=self.source_name,
                        external_id=str(listing["external_id"]),
                        payload=listing,
                        source_url=listing.get("source_url"),
                    )
                ],
                "transactions": [],
            }
        ]

    def normalize_development(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        return {
            "source": self.source_name,
            "source_external_id": payload.get("source_external_id") or record.external_id,
            "source_url": payload.get("source_url") or record.source_url,
            "name_zh": payload.get("name_zh"),
            "name_en": payload.get("name_en"),
            "name_translations_json": build_translation_map(
                zh_hant=(payload.get("name_translations") or {}).get("zh-Hant") or payload.get("name_zh"),
                zh_hans=(payload.get("name_translations") or {}).get("zh-Hans") or payload.get("name_zh"),
                en=(payload.get("name_translations") or {}).get("en") or payload.get("name_en"),
            ),
            "aliases_json": [value for value in [payload.get("name_zh"), payload.get("name_en")] if value],
            "address_raw": payload.get("address"),
            "district": payload.get("district"),
            "region": payload.get("region"),
            "lat": payload.get("lat"),
            "lng": payload.get("lng"),
            "developer_names_json": payload.get("developer_names") or [],
            "listing_segment": "second_hand",
            "source_confidence": SourceConfidence.MEDIUM,
        }

    def normalize_document(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError("centanet sample adapter does not normalize documents yet")

    def normalize_listing(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        title = payload.get("title")
        return {
            "source": self.source_name,
            "source_listing_id": str(payload.get("external_id") or record.external_id),
            "source_url": payload.get("source_url") or record.source_url,
            "title": title,
            "title_translations_json": build_translation_map(
                zh_hant=(payload.get("title_translations") or {}).get("zh-Hant") or title,
                zh_hans=(payload.get("title_translations") or {}).get("zh-Hans") or title,
                en=(payload.get("title_translations") or {}).get("en"),
            ),
            "listing_type": ListingType.SECOND_HAND,
            "asking_price_hkd": payload.get("asking_price_hkd"),
            "price_per_sqft": payload.get("price_per_sqft"),
            "bedrooms": payload.get("bedrooms"),
            "bathrooms": payload.get("bathrooms"),
            "saleable_area_sqft": payload.get("saleable_area_sqft"),
            "gross_area_sqft": payload.get("gross_area_sqft"),
            "status": self._normalize_status(payload.get("status")),
            "first_seen_at": None,
            "last_seen_at": None,
            "raw_payload_json": payload,
        }

    def normalize_transaction(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError("centanet sample adapter does not normalize transactions yet")

    def _normalize_status(self, value: str | None) -> ListingStatus:
        normalized = (value or "").strip().lower()
        if normalized in {"active", "available"}:
            return ListingStatus.ACTIVE
        if normalized in {"sold"}:
            return ListingStatus.SOLD
        if normalized in {"withdrawn", "off market"}:
            return ListingStatus.WITHDRAWN
        if normalized in {"pending"}:
            return ListingStatus.PENDING
        return ListingStatus.UNKNOWN

    def _extract_page_development_name(self, html_text: str, url: str) -> str:
        title_match = re.search(r"<title>.*?最新(?P<name>.+?)樓盤\s*-\s*中原地產</title>", html_text, re.S)
        if title_match:
            return self._clean_text(title_match.group("name"))
        slug = self._extract_page_slug(url, "")
        return slug.replace("-", " ").replace("_", " ").strip() or "Centanet Search"

    def _extract_page_slug(self, url: str, fallback: str) -> str:
        path = url.split("?", 1)[0].rstrip("/")
        slug = path.rsplit("/", 1)[-1]
        if slug:
            return slug
        return fallback

    def _parse_detail_page(self, html_text: str, *, url: str) -> dict[str, Any]:
        headline = self._extract_first_match(
            html_text,
            r'<div class="mobile-head-info".*?<p[^>]*>(?P<value>[^<]+)</p>',
        ) or self._extract_page_title_name(html_text)
        address = self._extract_first_match(
            html_text,
            r'<p class="font-mbl-15 flex info-address"[^>]*>.*?<span[^>]*>(?P<value>[^<]+)</span>',
        )
        developer_name = self._extract_first_match(
            html_text,
            r'<div class="developerName"[^>]*>(?P<value>[^<]+)</div>',
        )
        update_date = self._extract_first_match(
            html_text,
            r"物業編號：(?P<id>[A-Z0-9]+)\s*·\s*更新日期：(?P<date>\d{4}-\d{2}-\d{2})",
            group="date",
        )
        listing_code = self._extract_first_match(
            html_text,
            r"物業編號：(?P<id>[A-Z0-9]+)\s*·\s*更新日期：(?P<date>\d{4}-\d{2}-\d{2})",
            group="id",
        ) or self._extract_listing_external_id(url) or "unknown"
        mortgage = self._extract_first_match(html_text, r"月供：\$(?P<value>[\d,]+)")
        usable_area = self._extract_first_match(
            html_text,
            r'<p class="fs24 a-row"[^>]*>.*?<span class="area"[^>]*>(?P<value>[\d,]+)</span>',
        )
        price_per_sqft = self._extract_first_match(html_text, r"\$(?P<value>[\d,]+)\/呎")
        listing_price = self._extract_offer_price(html_text)
        bedrooms = self._extract_info_num_value(html_text, "間隔")
        age_years = self._extract_info_num_value(html_text, "樓齡")
        orientation = self._extract_info_num_value(html_text, "座向")
        feature_tags = re.findall(r'<div class="property-tag"[^>]*>.*?<span[^>]*>([^<]+)</span>', html_text, re.S)
        description = self._extract_first_match(
            html_text,
            r'<div class="desc-jx"[^>]*>.*?<p class="desc-content"[^>]*>(?P<value>.*?)</p>',
        )
        estate_url = self._extract_first_match(
            html_text,
            r'<a href="(?P<value>https://hk\.centanet\.com/estate/[^"]+)" target="_blank" class="hos-button"',
        )
        estate_name = self._extract_estate_name(headline or "", estate_url)
        development_external_id = estate_url.rsplit("/", 1)[-1] if estate_url else f"estate:{estate_name}"

        title = self._clean_text(headline or estate_name or listing_code)
        development_name = self._clean_text(estate_name or title)

        raw_detail = {
            "headline": title,
            "address": address,
            "developer_name": developer_name,
            "update_date": update_date,
            "monthly_payment_hkd": self._parse_int(mortgage),
            "age_years": self._parse_int(age_years),
            "orientation": orientation,
            "feature_tags": [self._clean_text(tag) for tag in feature_tags if self._clean_text(tag)],
            "description": self._clean_text(description) if description else None,
            "estate_url": estate_url,
        }

        return {
            "external_id": listing_code,
            "source_url": url,
            "title": title,
            "title_translations": {
                "zh-Hant": title,
                "zh-Hans": title,
            },
            "asking_price_hkd": listing_price,
            "price_per_sqft": self._parse_int(price_per_sqft),
            "bedrooms": self._extract_bedrooms(bedrooms),
            "bathrooms": self._extract_bathrooms(title),
            "saleable_area_sqft": self._parse_int(usable_area),
            "gross_area_sqft": None,
            "status": "active",
            "development": {
                "external_id": development_external_id,
                "source_url": estate_url or url,
                "name_zh": development_name,
                "name_en": None,
                "name_translations": {
                    "zh-Hant": development_name,
                    "zh-Hans": development_name,
                },
                "address": address,
                "district": None,
                "region": None,
                "lat": None,
                "lng": None,
                "developer_names": [part.strip() for part in (developer_name or "").split("/") if part.strip()],
            },
            "detail": raw_detail,
        }

    def _parse_search_result_cards(
        self,
        html_text: str,
        *,
        page_url: str,
        development_name: str,
    ) -> list[dict[str, Any]]:
        pattern = re.compile(
            r'<a[^>]+href="(?P<href>/findproperty/detail/[^"]+)"[^>]+class="property-text"[^>]*>(?P<body>.*?)</a>',
            re.S,
        )
        listings: list[dict[str, Any]] = []
        for match in pattern.finditer(html_text):
            href = match.group("href")
            body = match.group("body")
            title_lg = self._extract_class_text(body, "title-lg")
            title_sm = self._extract_class_text(body, "title-sm")
            title = " ".join(part for part in [title_lg, title_sm] if part).strip() or development_name
            saleable_area_sqft = self._extract_area_sqft(body)
            price_per_sqft = self._extract_price_per_sqft(body)
            price_hkd = self._extract_current_price_hkd(body)
            listing_id = self._extract_listing_external_id(href)
            if listing_id is None or price_hkd is None:
                continue

            listings.append(
                {
                    "external_id": listing_id,
                    "source_url": self._absolute_url(href),
                    "title": title,
                    "title_translations": {
                        "zh-Hant": title,
                        "zh-Hans": title,
                    },
                    "asking_price_hkd": price_hkd,
                    "price_per_sqft": price_per_sqft,
                    "bedrooms": self._extract_bedrooms(title_sm),
                    "bathrooms": self._extract_bathrooms(title_sm),
                    "saleable_area_sqft": saleable_area_sqft,
                    "gross_area_sqft": None,
                    "status": "active",
                    "development": {
                        "external_id": f"estate:{self._extract_page_slug(page_url, development_name)}",
                        "source_url": page_url,
                        "name_zh": development_name,
                        "name_en": None,
                        "name_translations": {
                            "zh-Hant": development_name,
                            "zh-Hans": development_name,
                        },
                        "address": None,
                        "district": None,
                        "region": None,
                        "lat": None,
                        "lng": None,
                    },
                    "raw_meta": {
                        "title_lg": title_lg,
                        "title_sm": title_sm,
                    },
                }
            )
        return listings

    def _extract_class_text(self, body: str, class_name: str) -> str | None:
        match = re.search(rf'<span class="{re.escape(class_name)}"[^>]*>(?P<value>.*?)</span>', body, re.S)
        if not match:
            return None
        text = self._clean_text(match.group("value"))
        return text or None

    def _extract_area_sqft(self, body: str) -> int | None:
        match = re.search(r'usable-area.*?(\d[\d,]*)呎', body, re.S)
        if not match:
            return None
        return self._parse_int(match.group(1))

    def _extract_price_per_sqft(self, body: str) -> int | None:
        match = re.search(r'@\s*\$?\s*([\d,]+)\s*<span[^>]*class="hidden-xs-only"[^>]*>/呎</span>', body, re.S)
        if not match:
            match = re.search(r'@\s*\$?\s*([\d,]+)\s*/呎', self._clean_text(body))
        if not match:
            return None
        return self._parse_int(match.group(1))

    def _extract_current_price_hkd(self, body: str) -> int | None:
        match = re.search(r'<div class="price"[^>]*>.*?<span class="price-info"[^>]*>(?P<value>.*?)</span>', body, re.S)
        if not match:
            return None
        value = self._clean_text(match.group("value"))
        number_match = re.search(r'([\d,]+(?:\.\d+)?)', value)
        if not number_match:
            return None
        return int(float(number_match.group(1).replace(",", "")) * 10000)

    def _extract_offer_price(self, html_text: str) -> int | None:
        script_match = re.search(r'"offers":\{"@type":"Offer","priceCurrency":"HKD","price":(?P<price>\d+)\}', html_text)
        if script_match:
            return int(script_match.group("price"))
        return self._extract_current_price_hkd(html_text)

    def _extract_listing_external_id(self, href: str) -> str | None:
        match = re.search(r'_([A-Z0-9]+)(?:\?|$)', href)
        if match:
            return match.group(1)
        return None

    def _extract_page_title_name(self, html_text: str) -> str | None:
        return self._extract_first_match(
            html_text,
            r"<title>[^｜]+\｜(?P<value>.+?)\s*｜買樓\s*-\s*中原地產</title>",
        )

    def _extract_estate_name(self, headline: str, estate_url: str | None) -> str:
        if estate_url:
            estate_slug = estate_url.split("/estate/", 1)[-1].split("/", 1)[0]
            estate_slug = estate_slug.split("-", 1)[0]
            if estate_slug:
                return self._clean_text(estate_slug)
        match = re.match(r"(?P<estate>.+?)\s+\d+期", headline)
        if match:
            return self._clean_text(match.group("estate"))
        return self._clean_text(headline)

    def _extract_info_num_value(self, html_text: str, label: str) -> str | None:
        pattern = rf"<p class=\"info-tag\"[^>]*>{re.escape(label)}</p>\s*<p[^>]*>(?P<value>[^<]+)</p>"
        return self._extract_first_match(html_text, pattern)

    def _extract_first_match(self, html_text: str, pattern: str, group: str = "value") -> str | None:
        match = re.search(pattern, html_text, re.S)
        if not match:
            return None
        value = match.group(group)
        cleaned = self._clean_text(value)
        return cleaned or None

    def _extract_bedrooms(self, title_sm: str | None) -> int | None:
        if not title_sm:
            return None
        if "開放式" in title_sm:
            return 0
        match = re.search(r"(\d+)房", title_sm)
        if not match:
            return None
        return int(match.group(1))

    def _extract_bathrooms(self, title_sm: str | None) -> int | None:
        if not title_sm:
            return None
        match = re.search(r"\((\d+)套房\)", title_sm)
        if not match:
            return 1 if "房" in title_sm else None
        return max(1, int(match.group(1)))

    def _parse_int(self, value: str | None) -> int | None:
        if not value:
            return None
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        number_match = re.search(r"\d+", cleaned)
        if number_match and number_match.group(0) != cleaned:
            cleaned = number_match.group(0)
        return int(cleaned)

    def _absolute_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.base_url}{href}"

    def _clean_text(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = html.unescape(text)
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()
