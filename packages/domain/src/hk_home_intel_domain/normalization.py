from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from hk_home_intel_domain.geo import infer_coordinates, infer_region_from_coordinates


SPACE_RE = re.compile(r"\s+")


DISTRICT_REGION_MAP = {
    "hongkongeast": "Hong Kong Island",
    "centralandwestern": "Hong Kong Island",
    "southern": "Hong Kong Island",
    "wanchai": "Hong Kong Island",
    "thepeakarea": "Hong Kong Island",
    "kowlooncity": "Kowloon",
    "kwuntong": "Kowloon",
    "shamshuipo": "Kowloon",
    "wongtaisin": "Kowloon",
    "yautsimmong": "Kowloon",
    "kaitak": "Kowloon",
    "kowloonstation": "Kowloon",
    "kowloontong": "Kowloon",
    "tseungkwano": "New Territories",
    "baolin": "New Territories",
    "tsingyi": "New Territories",
    "yuenlong": "New Territories",
    "yuenlongsoutheast": "New Territories",
    "yuenlongtowncentre": "New Territories",
    "siukhong": "New Territories",
    "tuenmunnorth": "New Territories",
    "tuenmunsanhuen": "New Territories",
    "kamtin": "New Territories",
}


def _normalize_key(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def normalize_hk_address(raw_address: str | None) -> str | None:
    if not raw_address:
        return None
    compact = SPACE_RE.sub(" ", unquote(raw_address)).strip(" ,")
    return compact


def canonicalize_district(value: str | None) -> str | None:
    normalized = normalize_hk_address(value)
    if not normalized:
        return None
    mapping = {
        "南昌站": "Sham Shui Po",
        "九龍站": "Kowloon Station",
        "九龍塘": "Kowloon Tong",
        "寶琳": "Baolin",
        "兆康": "Siu Hong",
        "屯門新墟": "Tuen Mun San Hui",
        "屯門北": "Tuen Mun North",
        "元朗市中心": "Yuen Long Town Centre",
        "元朗東南": "Yuen Long Southeast",
        "青衣": "Tsing Yi",
        "將軍澳": "Tseung Kwan O",
    }
    return mapping.get(normalized, normalized)


def infer_region_from_district(district: str | None) -> str | None:
    if not district:
        return None
    return DISTRICT_REGION_MAP.get(_normalize_key(district))


def enrich_development_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["address_normalized"] = normalize_hk_address(payload.get("address_raw"))
    normalized["district"] = canonicalize_district(payload.get("district"))
    normalized["region"] = payload.get("region") or infer_region_from_district(normalized["district"])

    lat = payload.get("lat")
    lng = payload.get("lng")
    if lat is None or lng is None:
        inferred_lat, inferred_lng = infer_coordinates(
            address=normalized["address_normalized"],
            district=normalized["district"],
        )
        normalized["lat"] = inferred_lat
        normalized["lng"] = inferred_lng
    else:
        normalized["lat"] = lat
        normalized["lng"] = lng

    if not normalized.get("region"):
        normalized["region"] = infer_region_from_coordinates(
            lat=normalized.get("lat"),
            lng=normalized.get("lng"),
        )

    return normalized
