from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.models import CommercialSearchMonitor, Development, Listing, PriceEvent, RefreshJobRun, SourceSnapshot


@dataclass(slots=True)
class CleanupSummary:
    refresh_jobs_deleted: int = 0
    snapshots_deleted: int = 0
    files_deleted: int = 0


@dataclass(slots=True)
class PreflightSummary:
    readiness_status: str
    notes: list[str]
    development_count: int
    development_with_coordinates_count: int
    commercial_listing_count: int
    price_event_count: int
    active_monitor_count: int
    attention_monitor_count: int
    latest_job_status: str | None


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


def compute_preflight_summary(session: Session) -> PreflightSummary:
    development_count = session.scalar(select(func.count()).select_from(Development)) or 0
    development_with_coordinates_count = session.scalar(
        select(func.count())
        .select_from(Development)
        .where(Development.lat.is_not(None), Development.lng.is_not(None))
    ) or 0
    commercial_listing_count = session.scalar(
        select(func.count()).select_from(Listing).where(Listing.source.in_(["centanet", "ricacorp"]))
    ) or 0
    price_event_count = session.scalar(select(func.count()).select_from(PriceEvent)) or 0
    latest_job = session.scalar(select(RefreshJobRun).order_by(RefreshJobRun.started_at.desc()).limit(1))
    latest_job_status = latest_job.status.value if latest_job is not None else None

    monitors = session.scalars(select(CommercialSearchMonitor)).all()
    active_monitors = [item for item in monitors if item.is_active]
    attention_monitor_count = 0
    for monitor in active_monitors:
        latest_run = session.scalar(
            select(RefreshJobRun)
            .where(RefreshJobRun.job_name == f"commercial_monitor:{monitor.id}")
            .order_by(RefreshJobRun.started_at.desc())
            .limit(1)
        )
        latest_success = session.scalar(
            select(RefreshJobRun)
            .where(
                RefreshJobRun.job_name == f"commercial_monitor:{monitor.id}",
                RefreshJobRun.status == "succeeded",
            )
            .order_by(RefreshJobRun.started_at.desc())
            .limit(1)
        )
        if _monitor_needs_attention(latest_run=latest_run, latest_success=latest_success):
            attention_monitor_count += 1

    notes: list[str] = []
    if development_count == 0:
        notes.append("No developments imported yet.")
    if development_with_coordinates_count == 0 and development_count > 0:
        notes.append("Development coordinates are still missing.")
    if not active_monitors:
        notes.append("No active commercial monitors configured.")
    if attention_monitor_count > 0:
        notes.append(f"{attention_monitor_count} commercial monitor(s) need attention.")
    if latest_job_status == "failed":
        notes.append("The latest refresh job failed.")
    if commercial_listing_count == 0:
        notes.append("No live commercial listings have been imported yet.")

    readiness_status = "ready" if not notes else "attention"
    return PreflightSummary(
        readiness_status=readiness_status,
        notes=notes,
        development_count=development_count,
        development_with_coordinates_count=development_with_coordinates_count,
        commercial_listing_count=commercial_listing_count,
        price_event_count=price_event_count,
        active_monitor_count=len(active_monitors),
        attention_monitor_count=attention_monitor_count,
        latest_job_status=latest_job_status,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _monitor_needs_attention(
    *,
    latest_run: RefreshJobRun | None,
    latest_success: RefreshJobRun | None,
) -> bool:
    if latest_run is None:
        return True
    if latest_run.status.value == "failed":
        return True
    latest_summary = latest_run.summary_json or {}
    if int(latest_summary.get("detail_failures", 0) or 0) > 0:
        return True
    if latest_success is None:
        return True
    latest_success_started_at = _ensure_utc(latest_success.started_at)
    return datetime.now(timezone.utc) - latest_success_started_at > timedelta(days=7)
