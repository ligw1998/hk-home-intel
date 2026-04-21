from __future__ import annotations


def _normalize_geo_key(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    _normalize_geo_key("Kai Tak"): (22.3199, 114.2131),
    _normalize_geo_key("Hong Kong East"): (22.2849, 114.2242),
    _normalize_geo_key("Central and Western"): (22.2867, 114.1456),
    _normalize_geo_key("Southern"): (22.2475, 114.1602),
    _normalize_geo_key("Wong Chuk Hang"): (22.2477, 114.1696),
    _normalize_geo_key("Wan Chai"): (22.2760, 114.1751),
    _normalize_geo_key("Kowloon City"): (22.3286, 114.1913),
    _normalize_geo_key("Kwun Tong"): (22.3104, 114.2250),
    _normalize_geo_key("South West Kowloon"): (22.3047, 114.1623),
    _normalize_geo_key("Sham Shui Po"): (22.3302, 114.1595),
    _normalize_geo_key("Wong Tai Sin"): (22.3420, 114.1953),
    _normalize_geo_key("Yau Tsim Mong"): (22.3215, 114.1719),
    _normalize_geo_key("Islands"): (22.2611, 113.9466),
    _normalize_geo_key("Kwai Tsing"): (22.3600, 114.1278),
    _normalize_geo_key("North"): (22.4966, 114.1286),
    _normalize_geo_key("Sai Kung"): (22.3814, 114.2705),
    _normalize_geo_key("Lohas Park"): (22.2951, 114.2682),
    _normalize_geo_key("Sha Tin"): (22.3872, 114.1953),
    _normalize_geo_key("Pak Shek Kok"): (22.4298, 114.2095),
    _normalize_geo_key("Pak Shek Kok (East)"): (22.4298, 114.2095),
    _normalize_geo_key("Tai Po"): (22.4509, 114.1688),
    _normalize_geo_key("Tsuen Wan"): (22.3714, 114.1131),
    _normalize_geo_key("Tuen Mun"): (22.3916, 113.9771),
    _normalize_geo_key("Yuen Long"): (22.4445, 114.0222),
    _normalize_geo_key("Fanling North"): (22.4942, 114.1435),
    _normalize_geo_key("Quarry Bay"): (22.2871, 114.2138),
    _normalize_geo_key("North Point"): (22.2918, 114.2007),
    _normalize_geo_key("Ma On Shan"): (22.4258, 114.2311),
    _normalize_geo_key("Tin Shui Wai"): (22.4627, 113.9991),
}

REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    _normalize_geo_key("Hong Kong"): (22.2819, 114.1589),
    _normalize_geo_key("Hong Kong Island"): (22.2819, 114.1589),
    _normalize_geo_key("Kowloon"): (22.3193, 114.1694),
    _normalize_geo_key("New Territories"): (22.3916, 114.1170),
    _normalize_geo_key("Tuen Mun and Yuen Long West"): (22.4180, 114.0010),
}

ADDRESS_CENTROIDS: dict[str, tuple[float, float]] = {
    _normalize_geo_key("North Point, Hong Kong"): (22.2918, 114.2007),
    _normalize_geo_key("Kai Tak, Kowloon"): (22.3199, 114.2131),
}

ADDRESS_FRAGMENT_CENTROIDS: tuple[tuple[str, tuple[float, float]], ...] = (
    ("Kowloon Tong", (22.3369, 114.1793)),
    ("Wong Chuk Hang", (22.2477, 114.1696)),
    ("Tseung Kwan O", (22.3073, 114.2592)),
    ("Tai Po", (22.4509, 114.1688)),
    ("Kai Tak", (22.3199, 114.2131)),
    ("Chai Wan", (22.2647, 114.2361)),
    ("Lohas Park", (22.2951, 114.2682)),
    ("Broadcast Drive", (22.3347, 114.1834)),
    ("Hoi Ying Road", (22.4302, 114.2452)),
)


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
    normalized = _normalize_geo_key(address)
    coords = ADDRESS_CENTROIDS.get(normalized)
    if not coords:
        lowered = address.lower()
        for fragment, fragment_coords in ADDRESS_FRAGMENT_CENTROIDS:
            if fragment.lower() in lowered:
                return fragment_coords
        return None, None
    return coords


def region_centroid(region: str | None) -> tuple[float | None, float | None]:
    if not region:
        return None, None
    coords = REGION_CENTROIDS.get(_normalize_geo_key(region))
    if not coords:
        return None, None
    return coords


def infer_coordinates(
    *,
    address: str | None,
    district: str | None,
    region: str | None = None,
) -> tuple[float | None, float | None]:
    lat, lng = address_centroid(address)
    if lat is not None and lng is not None:
        return lat, lng
    lat, lng = district_centroid(district)
    if lat is not None and lng is not None:
        return lat, lng
    return region_centroid(region)


def infer_region_from_coordinates(
    *,
    lat: float | None,
    lng: float | None,
) -> str | None:
    if lat is None or lng is None:
        return None
    if lat < 22.30 and 114.10 <= lng <= 114.25:
        return "Hong Kong Island"
    if 22.285 <= lat <= 22.37 and 114.10 <= lng <= 114.25:
        return "Kowloon"
    return "New Territories"
