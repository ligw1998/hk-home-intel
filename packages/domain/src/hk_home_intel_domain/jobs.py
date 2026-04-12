from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.models import RefreshJobRun


def start_job_run(
    session: Session,
    *,
    job_name: str,
    source: str | None,
    trigger_kind: str = "manual",
) -> RefreshJobRun:
    job = RefreshJobRun(
        job_name=job_name,
        source=source,
        trigger_kind=trigger_kind,
        status=JobRunStatus.RUNNING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def finish_job_run(
    session: Session,
    *,
    job: RefreshJobRun,
    status: JobRunStatus,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> RefreshJobRun:
    job.status = status
    job.finished_at = datetime.now(timezone.utc)
    job.summary_json = summary
    job.error_message = error_message
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
