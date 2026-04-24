from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.geo import infer_coordinates
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.launch_watch import (
    LANDSD_ASSIGN_ISSUED_SOURCE,
    LANDSD_ISSUED_SOURCE,
    LANDSD_PRESALE_ISSUED_SOURCE,
    LANDSD_PRESALE_PENDING_SOURCE,
    SRPE_ACTIVE_FIRST_HAND_SOURCE,
    SRPE_RECENT_DOCS_SOURCE,
    ensure_launch_watch_table,
)
from hk_home_intel_domain.models import Development, LaunchWatchProject
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/launch-watch", tags=["launch-watch"])


class LaunchWatchItem(BaseModel):
    id: str
    source: str
    project_name: str
    project_name_en: str | None
    display_name: str
    district: str | None
    region: str | None
    expected_launch_window: str | None
    launch_stage: str
    official_site_url: str | None
    source_url: str | None
    srpe_url: str | None
    linked_development_id: str | None
    linked_development_name: str | None
    note: str | None
    tags: list[str]
    signal_bucket: str
    signal_label: str
    signal_rank: int
    is_active: bool
    lat: float | None
    lng: float | None
    coordinate_mode: str
    updated_at: str


def _extract_address_hint(note: str | None) -> str | None:
    if not note:
        return None
    for marker in ("Address ", "at "):
        start = note.find(marker)
        if start != -1:
            fragment = note[start + len(marker) :]
            return fragment.split(".", 1)[0].strip() or None
    return None


class LaunchWatchListResponse(BaseModel):
    items: list[LaunchWatchItem]
    total: int


def _launch_watch_signal(row: LaunchWatchProject) -> tuple[str, str, int]:
    tags = set(row.tags_json or [])
    if row.source == LANDSD_PRESALE_PENDING_SOURCE:
        return ("landsd_pending", "LandsD Pending", 0)
    if row.source in {LANDSD_ISSUED_SOURCE, LANDSD_PRESALE_ISSUED_SOURCE, LANDSD_ASSIGN_ISSUED_SOURCE}:
        return ("landsd_issued", "LandsD Issued", 1)
    if row.source == SRPE_RECENT_DOCS_SOURCE and "pricing-signal" in tags:
        return ("recent_pricing", "Recent Pricing", 2)
    if row.source == SRPE_RECENT_DOCS_SOURCE and "brochure-signal" in tags:
        return ("recent_brochure", "Recent Brochure", 3)
    if row.source == SRPE_ACTIVE_FIRST_HAND_SOURCE:
        return ("srpe_active", "SRPE Active", 4)
    if row.source in {"centanet_news", "spacious_new_home"} or "commercial-launch" in tags:
        return ("commercial_launch", "Commercial Launch", 5)
    if row.source == "manual":
        return ("manual_watch", "Manual Watch", 6)
    return ("other_watch", "Other Watch", 7)


@router.get("", response_model=LaunchWatchListResponse)
def list_launch_watch_projects(
    q: str | None = Query(default=None),
    district: str | None = Query(default=None),
    region: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> LaunchWatchListResponse:
    ensure_launch_watch_table(session)
    stmt = select(LaunchWatchProject).order_by(
        LaunchWatchProject.is_active.desc(),
        LaunchWatchProject.updated_at.desc(),
    )
    if active_only:
        stmt = stmt.where(LaunchWatchProject.is_active.is_(True))
    if district:
        stmt = stmt.where(LaunchWatchProject.district == district)
    if region:
        stmt = stmt.where(LaunchWatchProject.region == region)

    rows = session.scalars(stmt).all()
    linked_development_ids = list(
        dict.fromkeys(row.linked_development_id for row in rows if row.linked_development_id)
    )
    linked_developments = {}
    if linked_development_ids:
        linked_developments = {
            development.id: development
            for development in session.scalars(
                select(Development).where(Development.id.in_(linked_development_ids))
            ).all()
        }
    items: list[LaunchWatchItem] = []
    for row in rows:
        linked_development_name = None
        linked_development = linked_developments.get(row.linked_development_id) if row.linked_development_id else None
        if linked_development is not None:
            linked_development_name = localize_text(
                linked_development.name_translations_json or {},
                lang,
                default=linked_development.name_zh or linked_development.name_en or row.project_name,
            )

        lat = linked_development.lat if linked_development is not None else None
        lng = linked_development.lng if linked_development is not None else None
        coordinate_mode = "exact" if lat is not None and lng is not None else "missing"
        if lat is None or lng is None:
            address_hint = _extract_address_hint(row.note)
            lat, lng = infer_coordinates(
                address=address_hint,
                district=row.district,
                region=row.region,
            )
            if lat is not None and lng is not None:
                coordinate_mode = "approximate"

        display_name = row.project_name_en if lang == "en" and row.project_name_en else row.project_name
        signal_bucket, signal_label, signal_rank = _launch_watch_signal(row)
        item = LaunchWatchItem(
            id=row.id,
            source=row.source,
            project_name=row.project_name,
            project_name_en=row.project_name_en,
            display_name=display_name,
            district=row.district or (linked_development.district if linked_development is not None else None),
            region=row.region or (linked_development.region if linked_development is not None else None),
            expected_launch_window=row.expected_launch_window,
            launch_stage=row.launch_stage,
            official_site_url=row.official_site_url,
            source_url=row.source_url,
            srpe_url=row.srpe_url,
            linked_development_id=row.linked_development_id,
            linked_development_name=linked_development_name,
            note=row.note,
            tags=list(dict.fromkeys(row.tags_json or [])),
            signal_bucket=signal_bucket,
            signal_label=signal_label,
            signal_rank=signal_rank,
            is_active=row.is_active,
            lat=lat,
            lng=lng,
            coordinate_mode=coordinate_mode,
            updated_at=row.updated_at.isoformat(),
        )
        if q:
            haystack = " ".join(
                value
                for value in [
                    item.project_name,
                    item.project_name_en,
                    item.display_name,
                    item.linked_development_name,
                    item.district,
                    item.region,
                    item.launch_stage,
                    item.expected_launch_window,
                ]
                if value
            ).lower()
            if q.strip().lower() not in haystack:
                continue
        items.append(item)
    items.sort(
        key=lambda item: (
            0 if item.is_active else 1,
            item.signal_rank,
            item.expected_launch_window or "9999",
            item.display_name,
        )
    )
    return LaunchWatchListResponse(items=items, total=len(items))
