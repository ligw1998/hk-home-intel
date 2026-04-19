from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.launch_watch import ensure_launch_watch_table
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
    is_active: bool
    updated_at: str


class LaunchWatchListResponse(BaseModel):
    items: list[LaunchWatchItem]
    total: int


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
        LaunchWatchProject.expected_launch_window.asc().nullslast(),
        LaunchWatchProject.updated_at.desc(),
    )
    if active_only:
        stmt = stmt.where(LaunchWatchProject.is_active.is_(True))
    if district:
        stmt = stmt.where(LaunchWatchProject.district == district)
    if region:
        stmt = stmt.where(LaunchWatchProject.region == region)

    rows = session.scalars(stmt).all()
    items: list[LaunchWatchItem] = []
    for row in rows:
        linked_development_name = None
        if row.linked_development_id:
            development = session.get(Development, row.linked_development_id)
            if development is not None:
                linked_development_name = localize_text(
                    development.name_translations_json or {},
                    lang,
                    default=development.name_zh or development.name_en or row.project_name,
                )

        display_name = row.project_name_en if lang == "en" and row.project_name_en else row.project_name
        item = LaunchWatchItem(
            id=row.id,
            source=row.source,
            project_name=row.project_name,
            project_name_en=row.project_name_en,
            display_name=display_name,
            district=row.district,
            region=row.region,
            expected_launch_window=row.expected_launch_window,
            launch_stage=row.launch_stage,
            official_site_url=row.official_site_url,
            source_url=row.source_url,
            srpe_url=row.srpe_url,
            linked_development_id=row.linked_development_id,
            linked_development_name=linked_development_name,
            note=row.note,
            tags=list(row.tags_json or []),
            is_active=row.is_active,
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
    return LaunchWatchListResponse(items=items, total=len(items))
