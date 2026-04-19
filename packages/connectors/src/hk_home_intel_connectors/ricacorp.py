from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from hk_home_intel_connectors.base import RawRecord, SourceAdapter
from hk_home_intel_connectors.http import fetch_text
from hk_home_intel_domain.enums import ListingStatus, ListingType, SourceConfidence
from hk_home_intel_domain.i18n import build_translation_map


class RicacorpAdapter(SourceAdapter):
    source_name = "ricacorp"
    base_url = "https://www.ricacorp.com"
    estate_list_url = "https://www.ricacorp.com/zh-hk/property/list/estate"
    sample_search_results_html_path = Path(__file__).with_name("fixtures").joinpath("ricacorp_search_results_sample.html")

    def discover_developments(self) -> list[RawRecord]:
        return []

    def discover_documents(self) -> list[RawRecord]:
        return []

    def fetch_search_results_html(self, url: str) -> str:
        return fetch_text(url)

    def fetch_estate_list_html(self) -> str:
        return fetch_text(self.estate_list_url)

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

        listings = self._parse_search_result_cards(html_text, page_url=url)
        if limit is not None:
            listings = listings[:limit]

        bundles: list[dict[str, Any]] = []
        for listing in listings:
            development_payload = listing["development"]
            development = {
                "source": self.source_name,
                "source_external_id": development_payload["external_id"],
                "source_url": development_payload.get("source_url") or url,
                "name_zh": development_payload.get("name_zh"),
                "name_en": development_payload.get("name_en"),
                "name_translations": development_payload.get("name_translations"),
                "address": development_payload.get("address"),
                "district": development_payload.get("district"),
                "region": development_payload.get("region"),
                "listing_segment": "second_hand",
                "source_confidence": "medium",
            }
            bundles.append(
                {
                    "development": RawRecord(
                        source=self.source_name,
                        external_id=str(development_payload["external_id"]),
                        payload=development,
                        source_url=development_payload.get("source_url") or url,
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

    def estate_index_entries(
        self,
        *,
        html_text: str | None = None,
        html_path: str | None = None,
    ) -> list[dict[str, Any]]:
        if html_text is None:
            if html_path:
                html_text = Path(html_path).read_text(encoding="utf-8")
            else:
                html_text = self.fetch_estate_list_html()

        soup = BeautifulSoup(html_text, "html.parser")
        entries_by_url: dict[str, dict[str, Any]] = {}
        for href_node in soup.select("a[href*='/property/estate/']"):
            href = href_node.get("href")
            if not href:
                continue
            estate_url = urljoin(self.base_url, href)
            display_name = self._clean_text(
                (href_node.select_one(".location-text") or href_node.select_one(".display-text") or href_node.select_one(".location-name"))
                and (href_node.select_one(".location-text") or href_node.select_one(".display-text") or href_node.select_one(".location-name")).get_text(" ", strip=True)
            )
            zone_text = self._clean_text(
                href_node.select_one(".zone-text").get_text(" ", strip=True)
                if href_node.select_one(".zone-text")
                else None
            )
            alt_name = self._clean_text(
                href_node.select_one("img").get("alt")
                if href_node.select_one("img") and href_node.select_one("img").get("alt")
                else None
            )
            entries_by_url.setdefault(
                estate_url,
                {
                    "estate_url": estate_url,
                    "display_name": display_name,
                    "alt_name": alt_name,
                    "zone_text": zone_text,
                    "alias": None,
                    "alias_name": None,
                    "buy_list_url": None,
                    "sales_count": None,
                },
            )
        for entry in self._extract_estate_index_entries_from_state(html_text):
            estate_url = str(entry.get("estate_url") or "").strip()
            if not estate_url:
                continue
            existing = entries_by_url.get(estate_url)
            if existing is None:
                entries_by_url[estate_url] = entry
                continue
            for key, value in entry.items():
                if existing.get(key) in {None, ""} and value not in {None, ""}:
                    existing[key] = value
        return list(entries_by_url.values())

    def extract_estate_page_name(self, html_text: str) -> str | None:
        soup = BeautifulSoup(html_text, "html.parser")
        location_name = soup.select_one("rc-estate-post-listing .location-name")
        if location_name is not None:
            cleaned = self._clean_text(location_name.get_text(" ", strip=True))
            if cleaned:
                return cleaned

        title = soup.title.get_text(" ", strip=True) if soup.title else None
        title = self._clean_text(title)
        if title:
            return title.split(" - ")[0].strip()
        return None

    def extract_estate_buy_list_url(self, html_text: str, *, estate_url: str) -> str | None:
        soup = BeautifulSoup(html_text, "html.parser")
        post_count_link = soup.select_one("a.post-total-count[href*='list/buy/']")
        if post_count_link is not None:
            href = post_count_link.get("href")
            if href:
                return self._resolve_property_href(href, current_url=estate_url)

        direct_link = soup.select_one("a[href*='/property/list/buy/']")
        if direct_link is not None:
            href = direct_link.get("href")
            if href:
                return self._resolve_property_href(href, current_url=estate_url)

        state_fallback = self._extract_estate_buy_list_url_from_state(html_text, estate_url=estate_url)
        if state_fallback:
            return state_fallback

        return None

    def extract_listing_page_alias(self, html_text: str) -> str | None:
        match = re.search(
            r"&q;SEARCHFILTER&q;:\{[^{}]*?&q;alias&q;:&q;([^&]+?)&q;",
            html_text,
            re.DOTALL,
        )
        if not match:
            return None
        return self._clean_text(match.group(1))

    def extract_listing_page_name(self, html_text: str) -> str | None:
        alias = self.extract_listing_page_alias(html_text)
        if not alias:
            return None
        return self._alias_name(alias)

    def _extract_estate_index_entries_from_state(self, html_text: str) -> list[dict[str, Any]]:
        state_match = re.search(
            r'<script[^>]+id="serverApp-state"[^>]*>(.*?)</script>',
            html_text,
            re.IGNORECASE | re.DOTALL,
        )
        state_text = state_match.group(1) if state_match else html_text
        alias_matches = list(re.finditer(r"&q;alias&q;:&q;([^&]+?)&q;", state_text))
        entries: list[dict[str, Any]] = []

        for index, match in enumerate(alias_matches):
            alias = self._clean_text(match.group(1))
            if not alias:
                continue
            next_start = alias_matches[index + 1].start() if index + 1 < len(alias_matches) else len(state_text)
            segment = state_text[match.start():next_start]
            sales_counts = [
                int(value)
                for value in re.findall(r"&q;itemId&q;:&q;post\.sales&q;,&q;count&q;:(\d+)", segment)
            ]
            buy_list_url = self._buy_list_url_from_alias(alias, current_url=self._estate_url_from_alias(alias))
            entries.append(
                {
                    "estate_url": self._estate_url_from_alias(alias),
                    "display_name": self._first_state_text(segment, "locationText", "displayText", "address1", "name"),
                    "alt_name": self._first_state_text(segment, "displayText", "locationText"),
                    "zone_text": self._first_state_text(segment, "zoneText", "address2", "areaName", "district"),
                    "alias": alias,
                    "alias_name": self._alias_name(alias),
                    "buy_list_url": buy_list_url,
                    "sales_count": max(sales_counts) if sales_counts else None,
                }
            )
        return entries

    def _extract_estate_buy_list_url_from_state(self, html_text: str, *, estate_url: str) -> str | None:
        state_match = re.search(
            r'<script[^>]+id="serverApp-state"[^>]*>(.*?)</script>',
            html_text,
            re.IGNORECASE | re.DOTALL,
        )
        state_text = state_match.group(1) if state_match else html_text
        sales_counts = [
            int(value)
            for value in re.findall(r"&q;itemId&q;:&q;post\.sales&q;,&q;count&q;:(\d+)", state_text)
        ]
        if not any(count > 0 for count in sales_counts):
            return None

        alias_candidates = re.findall(r"&q;alias&q;:&q;([^&]+?)&q;", state_text)
        alias_candidates.extend(
            re.findall(r"&q;aliases&q;:\{[^{}]*?&q;hk&q;:&q;([^&]+?)&q;", state_text, re.DOTALL)
        )
        for alias in alias_candidates:
            cleaned_alias = self._clean_text(alias)
            if not cleaned_alias:
                continue
            resolved_url = self._buy_list_url_from_alias(cleaned_alias, current_url=estate_url)
            if resolved_url:
                return resolved_url
        return None

    def _estate_url_from_alias(self, alias: str) -> str:
        encoded_alias = quote(alias, safe="-")
        return f"{self.base_url}/zh-hk/property/estate/{encoded_alias}"

    def _buy_list_url_from_alias(self, alias: str, *, current_url: str) -> str | None:
        cleaned_alias = self._clean_text(alias)
        if not cleaned_alias:
            return None
        buy_alias = cleaned_alias.replace("-estate-", "-bigest-")
        if "-bigest-" not in buy_alias:
            return None
        encoded_alias = quote(buy_alias, safe="-")
        return self._resolve_property_href(f"list/buy/{encoded_alias}", current_url=current_url)

    def _alias_name(self, alias: str) -> str | None:
        cleaned_alias = self._clean_text(alias)
        if not cleaned_alias:
            return None
        stem = re.split(r"-(?:estate|bigest)-", cleaned_alias, maxsplit=1, flags=re.IGNORECASE)[0]
        stem = stem.replace("-", " ")
        return self._clean_text(stem)

    def _first_state_text(self, state_text: str, *keys: str) -> str | None:
        for key in keys:
            match = re.search(rf"&q;{re.escape(key)}&q;:&q;([^&]+?)&q;", state_text)
            if match:
                cleaned = self._clean_text(match.group(1))
                if cleaned:
                    return cleaned
        return None

    def _resolve_property_href(self, href: str, *, current_url: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return urljoin(self.base_url, href)
        if href.startswith("list/"):
            locale_root_match = re.match(
                r"^(https://www\.ricacorp\.com/(?:zh-hk|zh-cn|en-hk)/property)/",
                current_url,
                re.IGNORECASE,
            )
            if locale_root_match:
                return f"{locale_root_match.group(1)}/{href}"
        return urljoin(current_url, href)

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
            "developer_names_json": payload.get("developer_names") or [],
            "listing_segment": "second_hand",
            "source_confidence": SourceConfidence.MEDIUM,
        }

    def normalize_document(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError("ricacorp adapter does not normalize documents yet")

    def normalize_listing(self, record: RawRecord) -> dict[str, Any]:
        payload = record.payload
        detail = payload.get("detail") or {}
        return {
            "source": self.source_name,
            "source_listing_id": payload.get("source_listing_id") or record.external_id,
            "source_url": payload.get("source_url") or record.source_url,
            "title": payload.get("title"),
            "title_translations_json": build_translation_map(
                zh_hant=payload.get("title"),
                zh_hans=payload.get("title"),
                en=None,
            ),
            "listing_type": ListingType.SECOND_HAND,
            "asking_price_hkd": payload.get("asking_price_hkd"),
            "price_per_sqft": payload.get("price_per_sqft"),
            "bedrooms": payload.get("bedrooms"),
            "bathrooms": payload.get("bathrooms"),
            "saleable_area_sqft": payload.get("saleable_area_sqft"),
            "gross_area_sqft": payload.get("gross_area_sqft"),
            "status": ListingStatus.ACTIVE,
            "raw_payload_json": {
                **payload,
                "detail": detail,
            },
        }

    def normalize_transaction(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError("ricacorp adapter does not normalize transactions yet")

    def _parse_search_result_cards(self, html_text: str, *, page_url: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html_text, "html.parser")
        cards = soup.select("rc-property-listing-item-desktop")
        results: list[dict[str, Any]] = []
        for card in cards:
            href_node = card.select_one("a[href*='/property/detail/']")
            if href_node is None:
                continue
            href = href_node.get("href")
            if not href:
                continue
            source_url = urljoin(self.base_url, href)

            title_block = card.select_one("h3.address")
            if title_block is None:
                continue
            title = self._clean_text(title_block.get_text(" ", strip=True))
            if not title:
                continue

            code_match = re.search(r"物業編號\s*([A-Z]{2}\d+)", card.get_text(" ", strip=True))
            source_listing_id = code_match.group(1) if code_match else self._derive_listing_id_from_href(href)
            if not source_listing_id:
                continue

            asking_price_hkd = self._extract_current_price_hkd(card)
            price_per_sqft = self._extract_decimal(card.select_one(".unit-price"))
            saleable_area_sqft = self._extract_area_sqft(card)
            bedrooms = self._extract_bedrooms(title_block)
            age_years = self._extract_int_after_label(card, "樓齡")
            update_date = self._extract_text_after_label(card, "廣告日期")
            monthly_payment_hkd = self._extract_monthly_payment_hkd(card)
            feature_tags = [self._clean_text(tag.get_text(" ", strip=True)) for tag in card.select(".postTag .tag-text")]
            feature_tags = [tag for tag in feature_tags if tag]

            development_name = self._extract_development_name(title)
            district = self._extract_district_from_href(href)
            development_external_id = f"estate:{development_name}"
            development_payload = {
                "external_id": development_external_id,
                "source_url": page_url,
                "name_zh": development_name,
                "name_translations": {"zh-Hant": development_name, "zh-Hans": development_name},
                "district": district,
                "region": None,
                "address": None,
            }
            listing_payload = {
                "source_listing_id": source_listing_id,
                "title": title,
                "source_url": source_url,
                "listing_type": "second_hand",
                "asking_price_hkd": asking_price_hkd,
                "price_per_sqft": price_per_sqft,
                "bedrooms": bedrooms,
                "bathrooms": None,
                "saleable_area_sqft": saleable_area_sqft,
                "gross_area_sqft": None,
                "status": "active",
                "development": development_payload,
                "detail": {
                    "address": None,
                    "update_date": update_date,
                    "monthly_payment_hkd": monthly_payment_hkd,
                    "age_years": age_years,
                    "orientation": None,
                    "feature_tags": feature_tags,
                    "description": None,
                },
            }
            results.append(
                {
                    "external_id": source_listing_id,
                    "source_url": source_url,
                    "development": development_payload,
                    **listing_payload,
                }
            )
        return results

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned or None

    def _extract_development_name(self, title: str) -> str:
        match = re.match(r"^(.*?)(?:\s+\d+座|\s+\d+[AB]?期|\s+[高低中極].*)", title)
        if match and match.group(1).strip():
            return match.group(1).strip()
        return title.split()[0].strip()

    def _extract_district_from_href(self, href: str) -> str | None:
        parts = href.strip("/").split("/")
        if len(parts) < 4:
            return None
        slug = parts[-1]
        segments = slug.split("-")
        if not segments:
            return None
        district = segments[0]
        return district or None

    def _derive_listing_id_from_href(self, href: str) -> str | None:
        slug = href.rstrip("/").split("/")[-1]
        match = re.search(r"-([a-z]{2}\d+)-\d+-hk$", slug, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _extract_current_price_hkd(self, card) -> float | None:
        block = card.select_one(".market-price-block")
        if block is None:
            return None
        containers = block.select(".price-container")
        if not containers:
            return None
        value = self._clean_text(containers[-1].get_text(" ", strip=True))
        if not value:
            return None
        match = re.search(r"\$?\s*([\d,.]+)", value)
        if not match:
            return None
        return float(match.group(1).replace(",", "")) * 10000

    def _extract_decimal(self, node) -> float | None:
        if node is None:
            return None
        text = self._clean_text(node.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(r"([\d,.]+)", text)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))

    def _extract_area_sqft(self, card) -> float | None:
        text = self._clean_text(card.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(r"實用\s*([\d,]+)\s*呎", text)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))

    def _extract_bedrooms(self, title_block) -> int | None:
        text = self._clean_text(title_block.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(r"(\d+)\s*房", text)
        if match:
            return int(match.group(1))
        return None

    def _extract_int_after_label(self, card, label: str) -> int | None:
        text = self._clean_text(card.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(rf"{label}\s*(\d+)", text)
        if not match:
            return None
        return int(match.group(1))

    def _extract_text_after_label(self, card, label: str) -> str | None:
        text = self._clean_text(card.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(rf"{label}\s*([0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}})", text)
        if not match:
            return None
        return match.group(1)

    def _extract_monthly_payment_hkd(self, card) -> float | None:
        text = self._clean_text(card.get_text(" ", strip=True))
        if not text:
            return None
        match = re.search(r"月供\s*\$([\d,]+)", text)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))
