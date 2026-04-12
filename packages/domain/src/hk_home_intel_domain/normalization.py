from __future__ import annotations

import re
from typing import Any

from hk_home_intel_domain.geo import infer_coordinates


SPACE_RE = re.compile(r"\s+")


def normalize_hk_address(raw_address: str | None) -> str | None:
    if not raw_address:
        return None
    compact = SPACE_RE.sub(" ", raw_address).strip(" ,")
    return compact


def enrich_development_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["address_normalized"] = normalize_hk_address(payload.get("address_raw"))

    lat = payload.get("lat")
    lng = payload.get("lng")
    if lat is None or lng is None:
        inferred_lat, inferred_lng = infer_coordinates(
            address=normalized["address_normalized"],
            district=payload.get("district"),
        )
        normalized["lat"] = inferred_lat
        normalized["lng"] = inferred_lng
    else:
        normalized["lat"] = lat
        normalized["lng"] = lng

    return normalized
