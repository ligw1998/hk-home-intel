from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import CommercialSearchMonitor


@dataclass
class MonitorConfigSyncSummary:
    path: str
    processed: int
    created: int
    updated: int
    unchanged: int
    dry_run: bool


def _normalized_monitor_payload(item: dict[str, Any]) -> dict[str, Any]:
    criteria = dict(item.get("criteria") or {})
    return {
        "source": str(item.get("source") or "centanet"),
        "name": str(item["name"]),
        "search_url": str(item["search_url"]),
        "scope_type": str(item.get("scope_type") or "custom"),
        "development_name_hint": item.get("development_name_hint"),
        "district": item.get("district"),
        "region": item.get("region"),
        "note": item.get("note"),
        "is_active": bool(item.get("is_active", True)),
        "with_details": bool(item.get("with_details", True)),
        "detect_withdrawn": bool(item.get("detect_withdrawn", False)),
        "tags_json": list(item.get("tags") or []),
        "criteria_json": criteria,
    }


def sync_commercial_monitor_config(
    session: Session,
    *,
    path: str | Path,
    dry_run: bool = False,
) -> MonitorConfigSyncSummary:
    config_path = Path(path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    monitors = list(payload.get("monitor") or [])

    created = 0
    updated = 0
    unchanged = 0

    for raw_item in monitors:
        normalized = _normalized_monitor_payload(raw_item)
        existing = session.scalar(
            select(CommercialSearchMonitor)
            .where(
                CommercialSearchMonitor.source == normalized["source"],
                CommercialSearchMonitor.search_url == normalized["search_url"],
            )
            .limit(1)
        )

        if existing is None:
            created += 1
            if not dry_run:
                session.add(CommercialSearchMonitor(**normalized))
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

    return MonitorConfigSyncSummary(
        path=str(config_path),
        processed=len(monitors),
        created=created,
        updated=updated,
        unchanged=unchanged,
        dry_run=dry_run,
    )
