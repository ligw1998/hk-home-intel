from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import LaunchWatchProject


@dataclass
class LaunchWatchConfigSyncSummary:
    path: str
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

    created = 0
    updated = 0
    unchanged = 0

    for raw_item in projects:
        normalized = _normalized_launch_watch_payload(raw_item)
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
