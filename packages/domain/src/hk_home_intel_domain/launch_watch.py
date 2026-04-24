from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
import tomllib
import re
from urllib.parse import urljoin

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_connectors.html import extract_links
from hk_home_intel_connectors.http import create_client, fetch_text
from hk_home_intel_connectors.srpe import SRPEAdapter
from hk_home_intel_domain.enums import ListingSegment
from hk_home_intel_domain.geo import infer_coordinates, infer_region_from_coordinates
from hk_home_intel_domain.models import Development, LaunchWatchProject
from hk_home_intel_domain.normalization import infer_region_from_district, normalize_hk_address

LANDSD_PRESALE_INDEX_URL = (
    "https://www.landsd.gov.hk/en/resources/land-info-stat/dev-control-compliance/consent/presale.html"
)
LANDSD_PRESALE_PENDING_SOURCE = "landsd_presale_pending"
LANDSD_ISSUED_SOURCE = "landsd_issued"
LANDSD_PRESALE_ISSUED_SOURCE = "landsd_presale_issued"
LANDSD_ASSIGN_ISSUED_SOURCE = "landsd_assign_issued"
SRPE_ACTIVE_FIRST_HAND_SOURCE = "srpe_active_first_hand"
SRPE_RECENT_DOCS_SOURCE = "srpe_recent_docs"
SRPE_ACTIVE_NEW_MIN_PROXY_YEAR_OFFSET = -1
SRPE_ACTIVE_NEW_MAX_PROXY_YEAR_OFFSET = 3
SRPE_ACTIVE_REMAINING_MIN_PROXY_YEAR_OFFSET = -1
SRPE_ACTIVE_REMAINING_MAX_PROXY_YEAR_OFFSET = 1
SRPE_RECENT_PRICE_SIGNAL_DAYS = 120
SRPE_RECENT_BROCHURE_SIGNAL_DAYS = 90
SRPE_RECENT_DOCS_NEW_MIN_PROXY_YEAR_OFFSET = -1
SRPE_RECENT_DOCS_NEW_MAX_PROXY_YEAR_OFFSET = 2
SRPE_RECENT_DOCS_REMAINING_MIN_PROXY_YEAR_OFFSET = -1
SRPE_RECENT_DOCS_REMAINING_MAX_PROXY_YEAR_OFFSET = 1
LANDSD_MONTHLY_REPORT_PATTERN = re.compile(r"/presale/(?P<stamp>\d{6})\.html$")
LANDSD_ISSUED_PDF_PATTERN = re.compile(r"/doc/en/consent/monthly/t1_(?P<stamp>\d{4})\.pdf$")
LANDSD_PENDING_PDF_PATTERN = re.compile(r"/doc/en/consent/monthly/t2_(?P<stamp>\d{4})\.pdf$")
LANDSD_COMPANY_TOKENS = (
    "limited",
    "corporation",
    "company",
    "properties",
    "property",
    "investments",
    "investment",
    "enterprises",
    "management",
    "authority",
    "bank",
    "solicitors",
    "law firm",
    "master",
    "deacons",
    "grandall",
    "johnson",
    "stokes",
    "master",
    "woo, kwan",
)
LANDSD_LINE_SKIP_PREFIXES = (
    "Particulars of Presale Consent and Consent to Assign issued",
    "Particulars of applications for Presale Consent and Consent to Assign pending approval",
    "for the period from ",
    "as at ",
    "Lands Department",
    "Presale Consent for Residential Development",
    "Presale Consent for Non-Residential Development",
    "Consent to Assign for Residential / Non-Residential Development",
    "Lot No.",
    "Address",
    "Development",
    "Name",
    "Vendor",
    "Holding",
    "Company",
    "Solicitors",
    "Authorized",
    "Person and",
    "his/her",
    "Building",
    "Contractor",
    "Mortgagee",
    "Undertaking",
    "Bank",
    "Financier",
    "Estimated",
    "Completion",
    "Date2",
    "No. of",
    "before",
    "Effective",
    "Date",
    "(c) – (b)",
    "Residential",
    "Units3",
    "Remarks",
    "Summary",
    "Explanatory Notes",
    "Total no. of",
)
LANDSD_DATE_UNITS_PATTERN = re.compile(r"^.*?(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<units>\d+)\s+--(?:\s*.*)?$")
LANDSD_DATE_ONLY_PATTERN = re.compile(r"^(?P<date>\d{2}/\d{2}/\d{4})$")
LANDSD_UNITS_ONLY_PATTERN = re.compile(r"^(?P<units>\d+)\s+--(?:\s*.*)?$")
LANDSD_TRAILING_DATE_PATTERN = re.compile(r"^\((?P<label>[a-f])\)\s+(?P<value>.+)$")
LANDSD_LOCATION_FRAGMENTS: tuple[tuple[str, str], ...] = (
    ("Kowloon Tong", "Kowloon Tong"),
    ("Broadcast Drive", "Kowloon Tong"),
    ("Kai Tak", "Kai Tak"),
    ("Chai Wan", "Hong Kong East"),
    ("Wong Chuk Hang", "Wong Chuk Hang"),
    ("Heung Yip Road", "Wong Chuk Hang"),
    ("Tseung Kwan O", "Tseung Kwan O"),
    ("Lohas Park", "Lohas Park"),
    ("Tsuen Wan", "Tsuen Wan"),
    ("Sha Tin", "Sha Tin"),
    ("Tai Po", "Tai Po"),
    ("Sai Kung", "Sai Kung"),
    ("Hiram", "Sai Kung"),
    ("Tuen Mun", "Tuen Mun"),
    ("Yuen Long", "Yuen Long"),
    ("Fanling", "North"),
    ("Heung Tsz Road", "North"),
    ("Mansfield Road", "The Peak Area"),
    ("Discovery Bay", "Islands"),
)


@dataclass
class LaunchWatchConfigSyncSummary:
    path: str
    processed: int
    created: int
    updated: int
    unchanged: int
    dry_run: bool


@dataclass
class LaunchWatchOfficialSyncSummary:
    source: str
    report_url: str
    pdf_url: str | None
    processed: int
    created: int
    updated: int
    unchanged: int
    dry_run: bool


def ensure_launch_watch_table(session: Session) -> None:
    LaunchWatchProject.__table__.create(bind=session.get_bind(), checkfirst=True)


def _normalized_launch_watch_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(item.get("source") or "manual"),
        "source_project_id": item.get("source_project_id"),
        "project_name": str(item["project_name"]),
        "project_name_en": item.get("project_name_en"),
        "district": item.get("district"),
        "region": item.get("region"),
        "expected_launch_window": item.get("expected_launch_window"),
        "launch_stage": str(item.get("launch_stage") or "watching"),
        "official_site_url": item.get("official_site_url"),
        "source_url": item.get("source_url"),
        "srpe_url": item.get("srpe_url"),
        "linked_development_id": item.get("linked_development_id"),
        "note": item.get("note"),
        "tags_json": list(item.get("tags") or []),
        "is_active": bool(item.get("is_active", True)),
    }


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char.lower() for char in value.strip() if char.isalnum())


def _collapse_spaces(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _is_landsd_header_line(line: str) -> bool:
    if not line:
        return True
    if line.isdigit():
        return True
    if any(line.startswith(prefix) for prefix in LANDSD_LINE_SKIP_PREFIXES):
        return True
    return False


def _looks_like_lot_line(line: str) -> bool:
    normalized = _collapse_spaces(line)
    return bool(
        re.match(r"^[A-Z]{2,8}\s+\d+[A-Z0-9]*$", normalized)
        or re.match(r"^[A-Z]{2,8}\s+\d+\s+RP$", normalized)
        or normalized in {"RP", "& Exts"}
        or normalized.startswith("Lot ")
        or normalized.startswith("DD ")
        or normalized.startswith("in DD ")
    )


def _looks_like_address_line(line: str) -> bool:
    if line == "(Provisional)":
        return True
    if line.startswith("No. "):
        return True
    return any(
        marker in line
        for marker in (
            "Road",
            "Street",
            "Highway",
            "Drive",
            "Lane",
            "Avenue",
            "Territories",
            "Hong Kong",
            "Kowloon",
            "Lantau Island",
            "Tseung Kwan O",
            "Sai Kung",
            "Tsuen Wan",
            "Tai Po",
            "Chai Wan",
            "Wong Chuk Hang",
            "Kai Tak",
            "Tuen Mun",
            "Sha Tin",
            "Yuen Long",
            "Fanling",
            "Lohas Park Road",
            "Broadcast Drive",
            "Heung Tsz Road",
            "Hiram’s Highway",
            "Hoi Ying Road",
            "Ying Ho Road",
        )
    )


def _looks_like_company_line(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in LANDSD_COMPANY_TOKENS)


def _looks_like_project_name_line(line: str) -> bool:
    if not line or _looks_like_lot_line(line) or _looks_like_address_line(line):
        return False
    if line.startswith("Phase ") or line.startswith("Pending "):
        return True
    if line.startswith("(Phase ") or line.startswith("(Stage ") or line.startswith("– ") or line.startswith("- "):
        return True
    if re.fullmatch(r"[A-Z0-9][A-Z0-9\s&()\-]+", line):
        return True
    return any(
        token in line
        for token in (
            "RESIDENCES",
            "SOUTHSIDE",
            "HEADLAND",
            "DISCOVERY",
            "LOHAS",
            "SEASONS",
            "HARBOUR",
            "BAY",
            "COAST",
            "CITY",
        )
    )


def _join_meaningful_lines(lines: list[str]) -> str:
    return _collapse_spaces(" ".join(line for line in lines if line))


def _cleanup_landsd_project_name(value: str) -> str:
    cleaned = _collapse_spaces(value)
    cleaned = cleaned.replace("Pending Pending", "Pending")
    return cleaned


def _stabilize_landsd_project_name(project_name: str, *, lot_no: str | None, address: str | None) -> str:
    cleaned = _cleanup_landsd_project_name(project_name)
    if cleaned and not _looks_like_project_name_line(cleaned):
        if address:
            cleaned = _collapse_spaces(f"{address} {cleaned}")
        elif lot_no:
            cleaned = _collapse_spaces(f"{cleaned} {lot_no}")
    if _normalize_name(cleaned) == "pending":
        cleaned = _collapse_spaces(f"Pending {lot_no or address or ''}")
    if cleaned.startswith("Pending ") and len(cleaned.split()) <= 2 and (lot_no or address):
        cleaned = _collapse_spaces(f"{cleaned} {lot_no or address}")
    return cleaned


def _launch_watch_match_candidates(project_name: str) -> list[str]:
    candidates = [project_name]
    pending_trimmed = re.sub(r"^Pending\s+", "", project_name).strip()
    if pending_trimmed and pending_trimmed != project_name:
        candidates.append(pending_trimmed)
    phase_trimmed = re.sub(r"^Phase\s+[0-9A-Za-z()\-]+\s+of\s+", "", project_name).strip()
    if phase_trimmed and phase_trimmed != project_name:
        candidates.append(phase_trimmed)
    pending_phase_trimmed = re.sub(r"^Pending\s+Phase\s+[0-9A-Za-z()\-]+\s+of\s+", "", project_name).strip()
    if pending_phase_trimmed and pending_phase_trimmed != project_name:
        candidates.append(pending_phase_trimmed)
    return [_collapse_spaces(value) for value in candidates if _collapse_spaces(value)]


def _launch_window_label(completion_date: date) -> str:
    today = date.today()
    months = (completion_date.year - today.year) * 12 + (completion_date.month - today.month)
    if months <= 6:
        band = "0-6m"
    elif months <= 12:
        band = "6-12m"
    elif months <= 24:
        band = "12-24m"
    elif months <= 36:
        band = "24-36m"
    else:
        band = "36m+"
    return f"{completion_date:%Y-%m} ({band})"


def _normalize_public_website_url(value: str | None) -> str | None:
    normalized = _collapse_spaces(value)
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"


def _parse_srpe_datetime_date(value: str | None) -> date | None:
    normalized = _collapse_spaces(value)
    if not normalized:
        return None
    iso_candidate = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def _latest_srpe_signal_dates(detail_result: dict[str, Any]) -> dict[str, date | None]:
    brochure_dates = [
        _parse_srpe_datetime_date(brochure.get("dateOfPrint"))
        for brochure in (detail_result.get("brochureList") or ([detail_result["brochure"]] if detail_result.get("brochure") else []))
    ]
    price_dates = [
        _parse_srpe_datetime_date(price.get("dateOfPrinting"))
        for price in (detail_result.get("prices") or [])
    ]
    arrangement_dates = [
        _parse_srpe_datetime_date(arrangement.get("dateOfPrinting"))
        for arrangement in (detail_result.get("salesArrangements") or [])
    ]
    brochure_latest = max((value for value in brochure_dates if value), default=None)
    price_latest = max((value for value in price_dates if value), default=None)
    arrangement_latest = max((value for value in arrangement_dates if value), default=None)
    pricing_latest = max((value for value in [price_latest, arrangement_latest] if value), default=None)
    return {
        "brochure_latest": brochure_latest,
        "price_latest": price_latest,
        "arrangement_latest": arrangement_latest,
        "pricing_latest": pricing_latest,
    }


def _build_development_name_index(session: Session) -> dict[str, str]:
    rows = session.scalars(select(Development)).all()
    index: dict[str, str] = {}
    for development in rows:
        for value in [
            development.name_zh,
            development.name_en,
            development.address_raw,
            development.address_normalized,
            *((development.name_translations_json or {}).values()),
            *((development.aliases_json or [])),
        ]:
            key = _normalize_name(str(value) if value else None)
            if key and key not in index:
                index[key] = development.id
    return index


def _infer_launch_watch_location(*values: str | None) -> tuple[str | None, str | None]:
    text = " ".join(_collapse_spaces(value) for value in values if _collapse_spaces(value))
    if not text:
        return None, None
    lowered = text.lower()
    for fragment, district in LANDSD_LOCATION_FRAGMENTS:
        if fragment.lower() in lowered:
            return district, infer_region_from_district(district)

    normalized_address = normalize_hk_address(text)
    lat, lng = infer_coordinates(address=normalized_address, district=None)
    return None, infer_region_from_coordinates(lat=lat, lng=lng)


def _official_landsd_tags(source: str) -> list[str]:
    tags = ["official", "landsd"]
    if source == LANDSD_PRESALE_PENDING_SOURCE:
        tags.extend(["pre-sale-consent", "pending"])
    elif source == LANDSD_PRESALE_ISSUED_SOURCE:
        tags.extend(["pre-sale-consent", "issued"])
    elif source == LANDSD_ASSIGN_ISSUED_SOURCE:
        tags.extend(["consent-to-assign", "issued"])
    else:
        tags.append("official-signal")
    return tags


def _build_srpe_project_link_index(
    session: Session,
    *,
    development_ids: set[str] | None = None,
) -> dict[str, dict[str, str | None]]:
    query = select(Development).where(
        Development.source == "srpe",
        Development.source_external_id.is_not(None),
    )
    if development_ids is not None:
        if not development_ids:
            return {}
        query = query.where(Development.id.in_(sorted(development_ids)))
    rows = session.scalars(query).all()
    if not rows:
        return {}

    adapter = SRPEAdapter()
    index: dict[str, dict[str, str | None]] = {}
    for development in rows:
        official_site_url = None
        try:
            detail_result = adapter.fetch_selected_development_result(
                development_id=str(development.source_external_id),
                language="en",
            )
            official_site_url = _normalize_public_website_url((detail_result.get("dev") or {}).get("website"))
        except Exception:
            official_site_url = None
        index[development.id] = {
            "srpe_url": development.source_url,
            "official_site_url": official_site_url,
        }
    return index


def _extract_landsd_project_identity(lines: list[str]) -> tuple[str | None, str | None, str | None]:
    filtered = [_collapse_spaces(line) for line in lines if line and not _is_landsd_header_line(_collapse_spaces(line))]
    if not filtered:
        return None, None, None

    lot_lines: list[str] = []
    index = 0
    while index < len(filtered) and _looks_like_lot_line(filtered[index]):
        lot_lines.append(filtered[index])
        index += 1

    address_lines: list[str] = []
    while index < len(filtered) and _looks_like_address_line(filtered[index]):
        address_lines.append(filtered[index])
        index += 1

    development_lines: list[str] = []
    cursor = index
    while cursor < len(filtered):
        if _looks_like_company_start(filtered, cursor):
            break
        development_lines.append(filtered[cursor])
        cursor += 1

    lot_no = _join_meaningful_lines(lot_lines) or None
    address = _join_meaningful_lines(address_lines) or None
    project_name = _cleanup_landsd_project_name(_join_meaningful_lines(development_lines))
    if not project_name:
        project_name = address or lot_no or ""
    if not project_name:
        return lot_no, address, None
    project_name = _stabilize_landsd_project_name(project_name, lot_no=lot_no, address=address)
    return lot_no, address, project_name


def _looks_like_company_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    if _looks_like_company_line(line) and not _looks_like_project_name_line(line):
        return True
    if index + 1 < len(lines):
        combined = _collapse_spaces(f"{line} {lines[index + 1]}")
        if _looks_like_company_line(combined) and not _looks_like_project_name_line(line):
            return True
    if index + 2 < len(lines):
        combined = _collapse_spaces(f"{line} {lines[index + 1]} {lines[index + 2]}")
        if _looks_like_company_line(combined) and not _looks_like_project_name_line(line):
            return True
    return False


def _extract_pdf_text_from_url(url: str) -> str:
    with create_client(timeout=60.0, headers={"Accept": "application/pdf, */*;q=0.8"}) as client:
        response = client.get(url)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _latest_landsd_monthly_report_url(index_html: str) -> str:
    candidates: list[tuple[str, str]] = []
    for link in extract_links(index_html):
        href = link.get("href") or ""
        matched = LANDSD_MONTHLY_REPORT_PATTERN.search(href)
        if matched:
            stamp = matched.group("stamp")
            candidates.append((stamp, urljoin(LANDSD_PRESALE_INDEX_URL, href)))
    if not candidates:
        raise ValueError("Could not find any LandsD monthly pre-sale report links.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_landsd_pending_pdf_url(report_html: str, report_url: str) -> str:
    candidates: list[tuple[str, str]] = []
    for link in extract_links(report_html):
        href = link.get("href") or ""
        matched = LANDSD_PENDING_PDF_PATTERN.search(href)
        if matched:
            candidates.append((matched.group("stamp"), urljoin(report_url, href)))
    if not candidates:
        raise ValueError("Could not find a LandsD pending-approval PDF link on the monthly report page.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_landsd_issued_pdf_url(report_html: str, report_url: str) -> str:
    candidates: list[tuple[str, str]] = []
    for link in extract_links(report_html):
        href = link.get("href") or ""
        matched = LANDSD_ISSUED_PDF_PATTERN.search(href)
        if matched:
            candidates.append((matched.group("stamp"), urljoin(report_url, href)))
    if not candidates:
        raise ValueError("Could not find a LandsD issued-consent PDF link on the monthly report page.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_landsd_section_lines(report_text: str, start_marker: str, end_marker: str | None = None) -> list[str]:
    start_index = report_text.find(start_marker)
    if start_index == -1:
        return []
    start_index += len(start_marker)
    if end_marker:
        end_index = report_text.find(end_marker, start_index)
        section_text = report_text[start_index:end_index if end_index != -1 else None]
    else:
        section_text = report_text[start_index:]
    return [_collapse_spaces(line) for line in section_text.splitlines()]


def _split_embedded_landsd_control_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        current = _collapse_spaces(line)
        while True:
            matched = re.search(r"\s(\([a-f]\)\s+.+)$", current)
            if not matched:
                break
            head = _collapse_spaces(current[: matched.start(1)])
            tail = _collapse_spaces(matched.group(1))
            if head:
                normalized.append(head)
            current = tail
        if current:
            normalized.append(current)
    return normalized


def _parse_landsd_date(value: str) -> date | None:
    collapsed = _collapse_spaces(value)
    if not collapsed or collapsed == "--" or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", collapsed):
        return None
    return datetime.strptime(collapsed, "%d/%m/%Y").date()


def _parse_landsd_optional_int(value: str) -> int | None:
    collapsed = _collapse_spaces(value)
    if not collapsed or collapsed == "--" or not re.fullmatch(r"\d+", collapsed):
        return None
    return int(collapsed)


def _parse_landsd_pending_record(lines: list[str], completion_date: date, unit_count: int) -> dict[str, Any] | None:
    lot_no, address, project_name = _extract_landsd_project_identity(lines)
    if not project_name:
        return None

    if project_name.startswith("Pending ") and address:
        note = f"Unnamed or provisional project under LandsD pending approval at {address}."
    else:
        note = None

    return {
        "project_name": project_name,
        "lot_no": lot_no,
        "address": address,
        "estimated_completion_date": completion_date,
        "unit_count": unit_count,
        "expected_launch_window": _launch_window_label(completion_date),
        "launch_stage": "launch_watch",
        "note": note,
    }


def parse_landsd_pending_approval_pdf_text(report_text: str) -> list[dict[str, Any]]:
    normalized_lines = [_collapse_spaces(line) for line in report_text.splitlines()]
    records: list[dict[str, Any]] = []
    current_lines: list[str] = []
    pending_completion_date: date | None = None

    for line in normalized_lines:
        if not line:
            continue
        matched = LANDSD_DATE_UNITS_PATTERN.match(line)
        if matched:
            completion_date = datetime.strptime(matched.group("date"), "%d/%m/%Y").date()
            unit_count = int(matched.group("units"))
            record = _parse_landsd_pending_record(current_lines, completion_date, unit_count)
            if record is not None:
                records.append(record)
            current_lines = []
            pending_completion_date = None
            continue
        date_only_matched = LANDSD_DATE_ONLY_PATTERN.match(line)
        if date_only_matched:
            pending_completion_date = datetime.strptime(date_only_matched.group("date"), "%d/%m/%Y").date()
            continue
        if pending_completion_date is not None:
            units_only_matched = LANDSD_UNITS_ONLY_PATTERN.match(line)
            if units_only_matched:
                record = _parse_landsd_pending_record(
                    current_lines,
                    pending_completion_date,
                    int(units_only_matched.group("units")),
                )
                if record is not None:
                    records.append(record)
                current_lines = []
                pending_completion_date = None
                continue
            current_lines.append(pending_completion_date.strftime("%d/%m/%Y"))
            pending_completion_date = None
        current_lines.append(line)

    deduped: list[dict[str, Any]] = []
    for item in records:
        if not _normalize_name(item.get("lot_no") or item.get("address") or item["project_name"]):
            continue
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(deduped)
                if _is_duplicate_pending_record(existing, item)
            ),
            None,
        )
        if duplicate_index is None:
            deduped.append(item)
            continue
        if _pending_record_name_score(item) > _pending_record_name_score(deduped[duplicate_index]):
            deduped[duplicate_index] = item
    return deduped


def _pending_record_location_key(item: dict[str, Any]) -> str:
    return _normalize_name(item.get("lot_no") or item.get("address") or item["project_name"])


def _pending_record_phase_key(item: dict[str, Any]) -> str | None:
    matched = re.search(r"phase\s+([0-9a-z()\-]+)", _collapse_spaces(item.get("project_name") or ""), re.IGNORECASE)
    return _normalize_name(matched.group(1)) if matched else None


def _is_duplicate_pending_record(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if _pending_record_location_key(left) != _pending_record_location_key(right):
        return False
    if left["estimated_completion_date"] != right["estimated_completion_date"]:
        return False
    if left["unit_count"] != right["unit_count"]:
        return False
    left_phase = _pending_record_phase_key(left)
    right_phase = _pending_record_phase_key(right)
    return left_phase == right_phase or left_phase is None or right_phase is None


def _pending_record_name_score(item: dict[str, Any]) -> tuple[int, int]:
    project_name = _collapse_spaces(item.get("project_name") or "")
    normalized = _normalize_name(project_name)
    score = 0
    if normalized and not normalized.startswith("pending"):
        score += 5
    if "phase" in project_name.lower():
        score += 2
    if item.get("address") and item["address"] in project_name:
        score += 1
    return score, len(project_name)


def _parse_landsd_issued_presale_record(
    lines: list[str],
    *,
    issue_date: date,
    completion_date: date | None,
    unit_count: int,
) -> dict[str, Any] | None:
    lot_no, address, project_name = _extract_landsd_project_identity(lines)
    normalized_lines = [_collapse_spaces(line) for line in lines if _collapse_spaces(line)]
    if any(line.startswith("Pending") for line in normalized_lines):
        project_name = _collapse_spaces(f"Pending {address or lot_no or project_name or ''}")
    if not project_name:
        return None
    note_parts = ["LandsD pre-sale consent issued."]
    if completion_date:
        note_parts.append(f"Estimated completion {completion_date:%Y-%m-%d}.")
    note_parts.append(f"{unit_count} residential units.")
    if lot_no:
        note_parts.append(f"Lot {lot_no}.")
    if address:
        note_parts.append(f"Address {address}.")
    return {
        "source": LANDSD_PRESALE_ISSUED_SOURCE,
        "project_name": project_name,
        "lot_no": lot_no,
        "address": address,
        "issue_date": issue_date,
        "estimated_completion_date": completion_date,
        "unit_count": unit_count,
        "expected_launch_window": f"{issue_date:%Y-%m} (issued)",
        "launch_stage": "watch_selling",
        "note": " ".join(note_parts),
    }


def _parse_landsd_assign_record(
    lines: list[str],
    *,
    issue_date: date,
    residential_unit_count: int | None,
) -> dict[str, Any] | None:
    if not residential_unit_count or residential_unit_count <= 0:
        return None
    lot_no, address, project_name = _extract_landsd_project_identity(lines)
    if not project_name:
        return None
    note_parts = [
        "LandsD consent to assign issued.",
        f"{residential_unit_count} residential units.",
    ]
    if lot_no:
        note_parts.append(f"Lot {lot_no}.")
    if address:
        note_parts.append(f"Address {address}.")
    return {
        "source": LANDSD_ASSIGN_ISSUED_SOURCE,
        "project_name": project_name,
        "lot_no": lot_no,
        "address": address,
        "issue_date": issue_date,
        "estimated_completion_date": None,
        "unit_count": residential_unit_count,
        "expected_launch_window": f"{issue_date:%Y-%m} (issued)",
        "launch_stage": "watch_ballot",
        "note": " ".join(note_parts),
    }


def parse_landsd_issued_pdf_text(report_text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    presale_lines = _split_embedded_landsd_control_lines(_extract_landsd_section_lines(
        report_text,
        "Presale Consent for Residential Development",
        "Presale Consent for Non-Residential Development",
    ))
    current_lines: list[str] = []
    issue_date: date | None = None
    completion_date: date | None = None
    for line in presale_lines:
        if not line:
            continue
        matched = LANDSD_TRAILING_DATE_PATTERN.match(line)
        if matched:
            label = matched.group("label")
            value = matched.group("value")
            if label == "a":
                issue_date = _parse_landsd_date(value)
            elif label == "c":
                completion_date = _parse_landsd_date(value)
            continue
        if issue_date and re.match(r"^\d+\s+\d+\s+--(?:\s*.*)?$", line):
            unit_count = int(_collapse_spaces(line).split()[1])
            record = _parse_landsd_issued_presale_record(
                current_lines,
                issue_date=issue_date,
                completion_date=completion_date,
                unit_count=unit_count,
            )
            if record is not None:
                records.append(record)
            current_lines = []
            issue_date = None
            completion_date = None
            continue
        current_lines.append(line)

    assign_lines = _split_embedded_landsd_control_lines(_extract_landsd_section_lines(
        report_text,
        "Consent to Assign for Residential / Non-Residential Development",
    ))
    current_lines = []
    issue_date = None
    residential_unit_count: int | None = None
    for line in assign_lines:
        if not line:
            continue
        matched = LANDSD_TRAILING_DATE_PATTERN.match(line)
        if matched:
            label = matched.group("label")
            value = matched.group("value")
            if label == "a":
                issue_date = _parse_landsd_date(value)
            elif label == "c":
                residential_unit_count = _parse_landsd_optional_int(value)
            continue
        if line == "--" and issue_date:
            record = _parse_landsd_assign_record(
                current_lines,
                issue_date=issue_date,
                residential_unit_count=residential_unit_count,
            )
            if record is not None:
                records.append(record)
            current_lines = []
            issue_date = None
            residential_unit_count = None
            continue
        current_lines.append(line)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, date | None, int]] = set()
    for item in records:
        key = (
            item["source"],
            _normalize_name(item["project_name"]),
            item.get("issue_date"),
            int(item["unit_count"]),
        )
        if key in seen or not key[1]:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sync_launch_watch_official_records(
    session: Session,
    *,
    report_url: str,
    pdf_url: str,
    parsed_records: list[dict[str, Any]],
    dry_run: bool,
    summary_source: str,
) -> LaunchWatchOfficialSyncSummary:
    development_index = _build_development_name_index(session)
    created = 0
    updated = 0
    unchanged = 0
    seen_names: set[tuple[str, str]] = set()
    normalized_records: list[dict[str, Any]] = []

    for item in parsed_records:
        project_name = item["project_name"]
        source = item["source"]
        normalized_name = _normalize_name(project_name)
        dedupe_key = (source, normalized_name)
        if dedupe_key in seen_names:
            suffix_parts = [
                item.get("lot_no") or item.get("address"),
                (item.get("issue_date") or item.get("estimated_completion_date")).isoformat()
                if item.get("issue_date") or item.get("estimated_completion_date")
                else None,
                f"{item['unit_count']}u",
            ]
            suffix = " | ".join(part for part in suffix_parts if part)
            project_name = _collapse_spaces(f"{project_name} [{suffix}]")
            normalized_name = _normalize_name(project_name)
            dedupe_key = (source, normalized_name)
        seen_names.add(dedupe_key)

        linked_development_id = None
        match_candidates = [
            *_launch_watch_match_candidates(project_name),
            item.get("address"),
            item.get("lot_no"),
        ]
        for candidate in match_candidates:
            if not candidate:
                continue
            matched_id = development_index.get(_normalize_name(candidate))
            if matched_id:
                linked_development_id = matched_id
                break

        district, region = _infer_launch_watch_location(
            item.get("address"),
            project_name,
            item.get("lot_no"),
            item.get("note"),
        )

        issue_date = item.get("issue_date")
        date_token = issue_date.strftime("%Y%m") if issue_date else "unknown"
        normalized_records.append(
            {
                "source": source,
                "source_project_id": f"{date_token}:{_normalize_name(project_name)}",
                "project_name": project_name,
                "project_name_en": project_name,
                "district": district,
                "region": region,
                "expected_launch_window": item["expected_launch_window"],
                "launch_stage": item["launch_stage"],
                "source_url": report_url,
                "linked_development_id": linked_development_id,
                "note": item["note"],
                "tags": _official_landsd_tags(source),
                "is_active": True,
            },
        )

    srpe_project_links = _build_srpe_project_link_index(
        session,
        development_ids={
            str(item["linked_development_id"])
            for item in normalized_records
            if item.get("linked_development_id")
        },
    )
    active_source_project_ids = {
        (str(item["source"]), str(item["source_project_id"]))
        for item in normalized_records
        if item.get("source_project_id")
    }
    active_sources = {source for source, _ in active_source_project_ids}

    for item in normalized_records:
        linked_development_id = item.get("linked_development_id")
        srpe_links = srpe_project_links.get(str(linked_development_id or "")) or {}
        normalized = _normalized_launch_watch_payload(
            {
                **item,
                "official_site_url": srpe_links.get("official_site_url"),
                "srpe_url": srpe_links.get("srpe_url"),
            }
        )

        existing = session.scalar(
            select(LaunchWatchProject)
            .where(
                LaunchWatchProject.source == normalized["source"],
                LaunchWatchProject.project_name == normalized["project_name"],
            )
            .limit(1)
        )
        if existing is None:
            created += 1
            if not dry_run:
                session.add(LaunchWatchProject(**normalized))
            continue

        changed = False
        for field, value in normalized.items():
            if getattr(existing, field) != value:
                changed = True
                if not dry_run:
                    setattr(existing, field, value)
        if changed:
            updated += 1
        else:
            unchanged += 1

    for existing in session.scalars(
        select(LaunchWatchProject).where(
            LaunchWatchProject.source.in_(sorted(active_sources)),
            LaunchWatchProject.is_active.is_(True),
        )
    ).all():
        if not existing.source_project_id:
            continue
        if (existing.source, existing.source_project_id) in active_source_project_ids:
            continue
        updated += 1
        if not dry_run:
            existing.is_active = False

    if not dry_run:
        session.commit()

    return LaunchWatchOfficialSyncSummary(
        source=summary_source,
        report_url=report_url,
        pdf_url=pdf_url,
        processed=len(parsed_records),
        created=created,
        updated=updated,
        unchanged=unchanged,
        dry_run=dry_run,
    )


def sync_launch_watch_landsd_pending_approval(
    session: Session,
    *,
    dry_run: bool = False,
) -> LaunchWatchOfficialSyncSummary:
    ensure_launch_watch_table(session)
    index_html = fetch_text(LANDSD_PRESALE_INDEX_URL)
    report_url = _latest_landsd_monthly_report_url(index_html)
    report_html = fetch_text(report_url)
    pdf_url = _extract_landsd_pending_pdf_url(report_html, report_url)
    report_text = _extract_pdf_text_from_url(pdf_url)
    parsed_records = parse_landsd_pending_approval_pdf_text(report_text)
    for item in parsed_records:
        note_parts = [
            "LandsD pre-sale consent pending approval.",
            f"Estimated completion {item['estimated_completion_date']:%Y-%m-%d}.",
            f"{item['unit_count']} residential units.",
        ]
        if item.get("lot_no"):
            note_parts.append(f"Lot {item['lot_no']}.")
        if item.get("address"):
            note_parts.append(f"Address {item['address']}.")
        if item.get("note"):
            note_parts.append(item["note"])
        item["source"] = LANDSD_PRESALE_PENDING_SOURCE
        item["issue_date"] = item["estimated_completion_date"]
        item["note"] = " ".join(note_parts)

    return _sync_launch_watch_official_records(
        session,
        report_url=report_url,
        pdf_url=pdf_url,
        parsed_records=parsed_records,
        dry_run=dry_run,
        summary_source=LANDSD_PRESALE_PENDING_SOURCE,
    )


def sync_launch_watch_landsd_issued(
    session: Session,
    *,
    dry_run: bool = False,
) -> LaunchWatchOfficialSyncSummary:
    ensure_launch_watch_table(session)
    index_html = fetch_text(LANDSD_PRESALE_INDEX_URL)
    report_url = _latest_landsd_monthly_report_url(index_html)
    report_html = fetch_text(report_url)
    pdf_url = _extract_landsd_issued_pdf_url(report_html, report_url)
    report_text = _extract_pdf_text_from_url(pdf_url)
    parsed_records = parse_landsd_issued_pdf_text(report_text)
    return _sync_launch_watch_official_records(
        session,
        report_url=report_url,
        pdf_url=pdf_url,
        parsed_records=parsed_records,
        dry_run=dry_run,
        summary_source=LANDSD_ISSUED_SOURCE,
    )


def sync_launch_watch_srpe_active_first_hand(
    session: Session,
    *,
    dry_run: bool = False,
) -> LaunchWatchOfficialSyncSummary:
    ensure_launch_watch_table(session)
    current_year = datetime.now().year
    min_proxy_year = current_year + min(SRPE_ACTIVE_NEW_MIN_PROXY_YEAR_OFFSET, SRPE_ACTIVE_REMAINING_MIN_PROXY_YEAR_OFFSET)
    max_proxy_year = current_year + max(SRPE_ACTIVE_NEW_MAX_PROXY_YEAR_OFFSET, SRPE_ACTIVE_REMAINING_MAX_PROXY_YEAR_OFFSET)
    candidate_developments = session.scalars(
        select(Development)
        .where(
            Development.source == "srpe",
            Development.listing_segment.in_([ListingSegment.NEW, ListingSegment.FIRST_HAND_REMAINING]),
            Development.completion_year.is_not(None),
            Development.completion_year >= min_proxy_year,
            Development.completion_year <= max_proxy_year,
        )
        .order_by(Development.updated_at.desc())
    ).all()
    developments: list[Development] = []
    for development in candidate_developments:
        completion_year = development.completion_year
        if completion_year is None:
            continue
        if development.listing_segment == ListingSegment.NEW:
            if not (
                current_year + SRPE_ACTIVE_NEW_MIN_PROXY_YEAR_OFFSET
                <= completion_year
                <= current_year + SRPE_ACTIVE_NEW_MAX_PROXY_YEAR_OFFSET
            ):
                continue
        elif development.listing_segment == ListingSegment.FIRST_HAND_REMAINING:
            if not (
                current_year + SRPE_ACTIVE_REMAINING_MIN_PROXY_YEAR_OFFSET
                <= completion_year
                <= current_year + SRPE_ACTIVE_REMAINING_MAX_PROXY_YEAR_OFFSET
            ):
                continue
        else:
            continue
        developments.append(development)

    srpe_project_links = _build_srpe_project_link_index(
        session,
        development_ids={development.id for development in developments},
    )

    created = 0
    updated = 0
    unchanged = 0

    for development in developments:
        srpe_links = srpe_project_links.get(development.id) or {}
        project_name = development.name_zh or development.name_en or development.id
        expected_launch_window = str(development.completion_year) if development.completion_year else None
        launch_stage = "watch_selling" if development.listing_segment == ListingSegment.FIRST_HAND_REMAINING else "launch_watch"
        note_parts = ["SRPE active first-hand signal."]
        if development.listing_segment == ListingSegment.FIRST_HAND_REMAINING:
            note_parts.append("Still marked as first-hand remaining.")
            note_parts.append(
                "Filtered into near-term first-hand window "
                f"{current_year + SRPE_ACTIVE_REMAINING_MIN_PROXY_YEAR_OFFSET}-"
                f"{current_year + SRPE_ACTIVE_REMAINING_MAX_PROXY_YEAR_OFFSET}."
            )
        elif development.listing_segment == ListingSegment.NEW:
            note_parts.append("Officially classified as new.")
            note_parts.append(
                "Filtered into new-project watch window "
                f"{current_year + SRPE_ACTIVE_NEW_MIN_PROXY_YEAR_OFFSET}-"
                f"{current_year + SRPE_ACTIVE_NEW_MAX_PROXY_YEAR_OFFSET}."
            )
        if development.completion_year:
            note_parts.append(f"Document-date proxy year {development.completion_year}.")

        normalized = _normalized_launch_watch_payload(
            {
                "source": SRPE_ACTIVE_FIRST_HAND_SOURCE,
                "source_project_id": f"srpe:{development.source_external_id or development.id}",
                "project_name": project_name,
                "project_name_en": development.name_en,
                "district": development.district,
                "region": development.region,
                "expected_launch_window": expected_launch_window,
                "launch_stage": launch_stage,
                "official_site_url": srpe_links.get("official_site_url"),
                "source_url": development.source_url,
                "srpe_url": srpe_links.get("srpe_url"),
                "linked_development_id": development.id,
                "note": " ".join(note_parts),
                "tags": ["official", "srpe", "vendor-site", development.listing_segment.value],
                "is_active": True,
            }
        )

        existing = session.scalar(
            select(LaunchWatchProject)
            .where(
                LaunchWatchProject.source == normalized["source"],
                LaunchWatchProject.project_name == normalized["project_name"],
            )
            .limit(1)
        )
        if existing is None:
            created += 1
            if not dry_run:
                session.add(LaunchWatchProject(**normalized))
            continue

        changed = False
        for field, value in normalized.items():
            if getattr(existing, field) != value:
                changed = True
                if not dry_run:
                    setattr(existing, field, value)
        if changed:
            updated += 1
        else:
            unchanged += 1

    if not dry_run:
        session.commit()

    return LaunchWatchOfficialSyncSummary(
        source=SRPE_ACTIVE_FIRST_HAND_SOURCE,
        report_url=SRPEAdapter.base_url,
        pdf_url=None,
        processed=len(developments),
        created=created,
        updated=updated,
        unchanged=unchanged,
        dry_run=dry_run,
    )


def sync_launch_watch_srpe_recent_documents(
    session: Session,
    *,
    dry_run: bool = False,
) -> LaunchWatchOfficialSyncSummary:
    ensure_launch_watch_table(session)
    adapter = SRPEAdapter()
    today = date.today()
    current_year = today.year
    candidate_developments = session.scalars(
        select(Development)
        .where(
            Development.source == "srpe",
            Development.listing_segment.in_([ListingSegment.NEW, ListingSegment.FIRST_HAND_REMAINING]),
            Development.completion_year.is_not(None),
        )
        .order_by(Development.updated_at.desc())
    ).all()

    processed = 0
    created = 0
    updated = 0
    unchanged = 0

    for development in candidate_developments:
        completion_year = development.completion_year
        if completion_year is None:
            continue
        if development.listing_segment == ListingSegment.NEW:
            if not (
                current_year + SRPE_RECENT_DOCS_NEW_MIN_PROXY_YEAR_OFFSET
                <= completion_year
                <= current_year + SRPE_RECENT_DOCS_NEW_MAX_PROXY_YEAR_OFFSET
            ):
                continue
        elif development.listing_segment == ListingSegment.FIRST_HAND_REMAINING:
            if not (
                current_year + SRPE_RECENT_DOCS_REMAINING_MIN_PROXY_YEAR_OFFSET
                <= completion_year
                <= current_year + SRPE_RECENT_DOCS_REMAINING_MAX_PROXY_YEAR_OFFSET
            ):
                continue
        try:
            detail_result = adapter.fetch_selected_development_result(
                development_id=str(development.source_external_id),
                language="en",
            )
        except Exception:
            continue

        signal_dates = _latest_srpe_signal_dates(detail_result)
        brochure_latest = signal_dates["brochure_latest"]
        pricing_latest = signal_dates["pricing_latest"]
        has_recent_pricing = (
            pricing_latest is not None and (today - pricing_latest).days <= SRPE_RECENT_PRICE_SIGNAL_DAYS
        )
        has_recent_brochure = (
            brochure_latest is not None and (today - brochure_latest).days <= SRPE_RECENT_BROCHURE_SIGNAL_DAYS
        )
        if not has_recent_pricing and not has_recent_brochure:
            continue

        processed += 1
        project_name = development.name_zh or development.name_en or development.id
        official_site_url = _normalize_public_website_url((detail_result.get("dev") or {}).get("website"))
        tags = ["official", "srpe", "recent-docs", development.listing_segment.value]
        note_parts = ["SRPE recent document activity signal."]
        if has_recent_pricing:
            tags.append("pricing-signal")
            note_parts.append(f"Recent pricing/sales-arrangement update on {pricing_latest:%Y-%m-%d}.")
        if has_recent_brochure:
            tags.append("brochure-signal")
            note_parts.append(f"Recent brochure update on {brochure_latest:%Y-%m-%d}.")
        note_parts.append(
            "Filtered into recent-docs watch window "
            f"{current_year + SRPE_RECENT_DOCS_REMAINING_MIN_PROXY_YEAR_OFFSET}-"
            f"{current_year + SRPE_RECENT_DOCS_NEW_MAX_PROXY_YEAR_OFFSET}."
        )
        launch_stage = "watch_selling" if has_recent_pricing else "launch_watch"

        normalized = _normalized_launch_watch_payload(
            {
                "source": SRPE_RECENT_DOCS_SOURCE,
                "source_project_id": f"srpe:{development.source_external_id or development.id}",
                "project_name": project_name,
                "project_name_en": development.name_en,
                "district": development.district,
                "region": development.region,
                "expected_launch_window": str(development.completion_year) if development.completion_year else None,
                "launch_stage": launch_stage,
                "official_site_url": official_site_url,
                "source_url": development.source_url,
                "srpe_url": development.source_url,
                "linked_development_id": development.id,
                "note": " ".join(note_parts),
                "tags": tags,
                "is_active": True,
            }
        )

        existing = session.scalar(
            select(LaunchWatchProject)
            .where(
                LaunchWatchProject.source == normalized["source"],
                LaunchWatchProject.project_name == normalized["project_name"],
            )
            .limit(1)
        )
        if existing is None:
            created += 1
            if not dry_run:
                session.add(LaunchWatchProject(**normalized))
            continue

        changed = False
        for field, value in normalized.items():
            if getattr(existing, field) != value:
                changed = True
                if not dry_run:
                    setattr(existing, field, value)
        if changed:
            updated += 1
        else:
            unchanged += 1

    if not dry_run:
        session.commit()

    return LaunchWatchOfficialSyncSummary(
        source=SRPE_RECENT_DOCS_SOURCE,
        report_url=SRPEAdapter.base_url,
        pdf_url=None,
        processed=processed,
        created=created,
        updated=updated,
        unchanged=unchanged,
        dry_run=dry_run,
    )


def sync_launch_watch_config(
    session: Session,
    *,
    path: str | Path,
    dry_run: bool = False,
) -> LaunchWatchConfigSyncSummary:
    ensure_launch_watch_table(session)
    config_path = Path(path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    projects = list(payload.get("project") or [])
    development_index = _build_development_name_index(session)

    normalized_projects: list[dict[str, Any]] = []
    for raw_item in projects:
        linked_development_id = raw_item.get("linked_development_id")
        if not linked_development_id:
            for candidate in _launch_watch_match_candidates(str(raw_item.get("project_name") or "")):
                linked_development_id = development_index.get(_normalize_name(candidate))
                if linked_development_id:
                    break
            if not linked_development_id and raw_item.get("project_name_en"):
                for candidate in _launch_watch_match_candidates(str(raw_item.get("project_name_en") or "")):
                    linked_development_id = development_index.get(_normalize_name(candidate))
                    if linked_development_id:
                        break
        normalized_projects.append(
            {
                **raw_item,
                "linked_development_id": linked_development_id,
            }
        )

    srpe_project_links = _build_srpe_project_link_index(
        session,
        development_ids={
            str(item["linked_development_id"])
            for item in normalized_projects
            if item.get("linked_development_id")
        },
    )

    created = 0
    updated = 0
    unchanged = 0

    for raw_item in normalized_projects:
        srpe_links = srpe_project_links.get(str(raw_item.get("linked_development_id") or "")) or {}
        normalized = _normalized_launch_watch_payload(
            {
                **raw_item,
                "official_site_url": raw_item.get("official_site_url") or srpe_links.get("official_site_url"),
                "srpe_url": raw_item.get("srpe_url") or srpe_links.get("srpe_url"),
            }
        )
        existing = session.scalar(
            select(LaunchWatchProject)
            .where(
                LaunchWatchProject.source == normalized["source"],
                LaunchWatchProject.project_name == normalized["project_name"],
            )
            .limit(1)
        )

        if existing is None:
            created += 1
            if not dry_run:
                session.add(LaunchWatchProject(**normalized))
            continue

        changed = False
        for field, value in normalized.items():
            if getattr(existing, field) != value:
                changed = True
                if not dry_run:
                    setattr(existing, field, value)

        if changed:
            updated += 1
        else:
            unchanged += 1

    if not dry_run:
        session.commit()

    return LaunchWatchConfigSyncSummary(
        path=str(config_path),
        processed=len(projects),
        created=created,
        updated=updated,
        unchanged=unchanged,
        dry_run=dry_run,
    )
