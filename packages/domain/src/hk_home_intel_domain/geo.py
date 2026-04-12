from __future__ import annotations


def _normalize_geo_key(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    _normalize_geo_key("Hong Kong East"): (22.2849, 114.2242),
    _normalize_geo_key("Central and Western"): (22.2867, 114.1456),
    _normalize_geo_key("Southern"): (22.2475, 114.1602),
    _normalize_geo_key("Wan Chai"): (22.2760, 114.1751),
    _normalize_geo_key("Kowloon City"): (22.3286, 114.1913),
    _normalize_geo_key("Kwun Tong"): (22.3104, 114.2250),
    _normalize_geo_key("Sham Shui Po"): (22.3302, 114.1595),
    _normalize_geo_key("Wong Tai Sin"): (22.3420, 114.1953),
    _normalize_geo_key("Yau Tsim Mong"): (22.3215, 114.1719),
    _normalize_geo_key("Islands"): (22.2611, 113.9466),
    _normalize_geo_key("Kwai Tsing"): (22.3600, 114.1278),
    _normalize_geo_key("North"): (22.4966, 114.1286),
    _normalize_geo_key("Sai Kung"): (22.3814, 114.2705),
    _normalize_geo_key("Sha Tin"): (22.3872, 114.1953),
    _normalize_geo_key("Tai Po"): (22.4509, 114.1688),
    _normalize_geo_key("Tsuen Wan"): (22.3714, 114.1131),
    _normalize_geo_key("Tuen Mun"): (22.3916, 113.9771),
    _normalize_geo_key("Yuen Long"): (22.4445, 114.0222),
}

ADDRESS_CENTROIDS: dict[str, tuple[float, float]] = {
    _normalize_geo_key("North Point, Hong Kong"): (22.2918, 114.2007),
    _normalize_geo_key("Kai Tak, Kowloon"): (22.3199, 114.2131),
}


def district_centroid(district: str | None) -> tuple[float | None, float | None]:
    if not district:
        return None, None
    coords = DISTRICT_CENTROIDS.get(_normalize_geo_key(district))
    if not coords:
        return None, None
    return coords


def address_centroid(address: str | None) -> tuple[float | None, float | None]:
    if not address:
        return None, None
    coords = ADDRESS_CENTROIDS.get(_normalize_geo_key(address))
    if not coords:
        return None, None
    return coords


def infer_coordinates(
    *,
    address: str | None,
    district: str | None,
) -> tuple[float | None, float | None]:
    lat, lng = address_centroid(address)
    if lat is not None and lng is not None:
        return lat, lng
    return district_centroid(district)
