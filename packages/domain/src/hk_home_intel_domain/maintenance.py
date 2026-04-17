from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import RefreshJobRun, SourceSnapshot


@dataclass(slots=True)
class CleanupSummary:
    refresh_jobs_deleted: int = 0
    snapshots_deleted: int = 0
    files_deleted: int = 0


def cleanup_runtime_artifacts(
    session: Session,
    *,
    refresh_job_days: int = 30,
    keep_latest_jobs_per_name: int = 20,
    search_snapshot_days: int = 14,
    detail_snapshot_days: int = 7,
    keep_latest_snapshots_per_object: int = 5,
) -> CleanupSummary:
    summary = CleanupSummary()

    now = datetime.now(timezone.utc)
    refresh_cutoff = now - timedelta(days=refresh_job_days)
    search_cutoff = now - timedelta(days=search_snapshot_days)
    detail_cutoff = now - timedelta(days=detail_snapshot_days)

    jobs = session.scalars(
        select(RefreshJobRun).order_by(RefreshJobRun.job_name, RefreshJobRun.started_at.desc(), RefreshJobRun.id.desc())
    ).all()
    seen_counts: dict[str, int] = {}
    for job in jobs:
        seen_counts[job.job_name] = seen_counts.get(job.job_name, 0) + 1
        started_at = _ensure_utc(job.started_at)
        if seen_counts[job.job_name] <= keep_latest_jobs_per_name:
            continue
        if started_at >= refresh_cutoff:
            continue
        session.delete(job)
        summary.refresh_jobs_deleted += 1

    snapshots = session.scalars(
        select(SourceSnapshot).order_by(
            SourceSnapshot.source,
            SourceSnapshot.object_type,
            SourceSnapshot.object_external_id,
            SourceSnapshot.fetched_at.desc(),
            SourceSnapshot.id.desc(),
        )
    ).all()
    snapshot_counts: dict[tuple[str, str, str | None], int] = {}
    for snapshot in snapshots:
        if snapshot.source not in {"centanet", "ricacorp"}:
            continue
        if snapshot.object_type not in {"search_page", "detail_page"}:
            continue
        key = (snapshot.source, snapshot.object_type, snapshot.object_external_id)
        snapshot_counts[key] = snapshot_counts.get(key, 0) + 1
        fetched_at = _ensure_utc(snapshot.fetched_at)
        cutoff = detail_cutoff if snapshot.object_type == "detail_page" else search_cutoff
        if snapshot_counts[key] <= keep_latest_snapshots_per_object:
            continue
        if fetched_at >= cutoff:
            continue
        if snapshot.file_path:
            path = Path(snapshot.file_path)
            if path.exists():
                path.unlink()
                summary.files_deleted += 1
        session.delete(snapshot)
        summary.snapshots_deleted += 1

    session.commit()
    return summary


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
