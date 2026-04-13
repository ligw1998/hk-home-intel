from __future__ import annotations

import time
import threading
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.enums import JobRunStatus
from hk_home_intel_domain.ingestion import import_centanet_search_results, import_srpe_all_developments
from hk_home_intel_domain.jobs import finish_job_run, start_job_run
from hk_home_intel_domain.models import RefreshJobRun
from hk_home_intel_shared.db import get_session_factory
from hk_home_intel_shared.scheduler import get_due_scheduler_plan_names, load_scheduler_plans


def execute_srpe_refresh(
    session: Session,
    *,
    language: str,
    limit: int | None,
    offset: int = 0,
    include_details: bool,
    trigger_kind: str = "manual",
    job_name: str = "srpe_refresh",
) -> dict[str, Any]:
    job = start_job_run(
        session,
        job_name=job_name,
        source="srpe",
        trigger_kind=trigger_kind,
    )
    try:
        summary = import_srpe_all_developments(
            session,
            language=language,
            limit=limit,
            offset=offset,
            include_details=include_details,
        )
    except Exception as exc:
        finish_job_run(
            session,
            job=job,
            status=JobRunStatus.FAILED,
            error_message=str(exc),
        )
        raise

    result = {
        "job_id": job.id,
        "source": summary.source,
        "language": language,
        "limit": limit,
        "offset": offset,
        "include_details": include_details,
        "developments_created": summary.developments_created,
        "developments_updated": summary.developments_updated,
        "documents_upserted": summary.documents_upserted,
        "listings_upserted": summary.listings_upserted,
        "transactions_upserted": summary.transactions_upserted,
        "price_events_created": summary.price_events_created,
        "snapshots_created": summary.snapshots_created,
    }
    finish_job_run(
        session,
        job=job,
        status=JobRunStatus.SUCCEEDED,
        summary=result,
    )
    return result


def execute_centanet_search_refresh(
    session: Session,
    *,
    url: str,
    limit: int | None,
    with_details: bool,
    detect_withdrawn: bool,
    trigger_kind: str = "manual",
    job_name: str = "centanet_search_refresh",
) -> dict[str, Any]:
    job = start_job_run(
        session,
        job_name=job_name,
        source="centanet",
        trigger_kind=trigger_kind,
    )
    try:
        summary = import_centanet_search_results(
            session,
            url=url,
            limit=limit,
            with_details=with_details,
            detect_withdrawn=detect_withdrawn,
        )
    except Exception as exc:
        finish_job_run(
            session,
            job=job,
            status=JobRunStatus.FAILED,
            error_message=str(exc),
        )
        raise

    result = {
        "job_id": job.id,
        "source": summary.source,
        "url": url,
        "limit": limit,
        "with_details": with_details,
        "detect_withdrawn": detect_withdrawn,
        "developments_created": summary.developments_created,
        "developments_updated": summary.developments_updated,
        "documents_upserted": summary.documents_upserted,
        "listings_upserted": summary.listings_upserted,
        "transactions_upserted": summary.transactions_upserted,
        "price_events_created": summary.price_events_created,
        "snapshots_created": summary.snapshots_created,
    }
    finish_job_run(
        session,
        job=job,
        status=JobRunStatus.SUCCEEDED,
        summary=result,
    )
    return result


def execute_refresh_plan(
    session: Session,
    *,
    plan_name: str,
    trigger_kind: str = "manual",
    plan_job_id: str | None = None,
) -> dict[str, Any]:
    plans = load_scheduler_plans(session=session)
    if plan_name not in plans:
        raise ValueError(f"unknown refresh plan: {plan_name}")

    plan = plans[plan_name]
    if plan_job_id is not None:
        plan_job = session.get(RefreshJobRun, plan_job_id)
        if plan_job is None:
            raise ValueError(f"refresh plan job not found: {plan_job_id}")
    else:
        plan_job = start_job_run(
            session,
            job_name=f"refresh_plan:{plan.name}",
            source=None,
            trigger_kind=trigger_kind,
        )
    results: list[dict[str, Any]] = []
    try:
        for task in plan.tasks:
            if task.command == "srpe_refresh":
                offset = _resolve_task_offset(
                    session,
                    plan_name=plan.name,
                    task_job_name=task.job_name,
                    limit=task.limit,
                    rotation_mode=task.rotation_mode,
                    rotation_step=task.rotation_step,
                )
                task_result = execute_srpe_refresh(
                    session,
                    language=task.language,
                    limit=task.limit,
                    offset=offset,
                    include_details=task.with_details,
                    trigger_kind="plan",
                    job_name=f"{plan.name}:{task.job_name}",
                )
                task_result["rotation_mode"] = task.rotation_mode
                task_result["rotation_step"] = task.rotation_step
            elif task.command == "centanet_search_refresh":
                if not task.url:
                    raise ValueError(f"centanet task missing url: {task.job_name}")
                task_result = execute_centanet_search_refresh(
                    session,
                    url=task.url,
                    limit=task.limit,
                    with_details=task.with_details,
                    detect_withdrawn=task.detect_withdrawn,
                    trigger_kind="plan",
                    job_name=f"{plan.name}:{task.job_name}",
                )
            else:
                raise ValueError(f"unsupported plan task command: {task.command}")
            task_result["job_name"] = task.job_name
            results.append(task_result)
    except Exception as exc:
        finish_job_run(
            session,
            job=plan_job,
            status=JobRunStatus.FAILED,
            error_message=str(exc),
        )
        raise

    result = {
        "plan": plan.name,
        "description": plan.description,
        "task_count": len(plan.tasks),
        "results": results,
    }
    finish_job_run(
        session,
        job=plan_job,
        status=JobRunStatus.SUCCEEDED,
        summary=result,
    )
    return result


def launch_refresh_plan(
    *,
    database_url: str,
    plan_name: str,
    trigger_kind: str = "api",
) -> dict[str, str]:
    plans = load_scheduler_plans()
    if plan_name not in plans:
        raise ValueError(f"unknown refresh plan: {plan_name}")

    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        plan_job = start_job_run(
            session,
            job_name=f"refresh_plan:{plan_name}",
            source=None,
            trigger_kind=trigger_kind,
        )
        job_id = plan_job.id

    def runner() -> None:
        with session_factory() as session:
            execute_refresh_plan(
                session,
                plan_name=plan_name,
                trigger_kind=trigger_kind,
                plan_job_id=job_id,
            )

    thread = threading.Thread(target=runner, name=f"hhi-refresh-plan-{plan_name}", daemon=True)
    thread.start()
    return {
        "job_id": job_id,
        "plan": plan_name,
    }


def launch_due_refresh_plans(
    *,
    database_url: str,
    trigger_kind: str = "api",
) -> dict[str, Any]:
    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        due_names = get_due_scheduler_plan_names(session)

    launched: list[dict[str, str]] = []
    for plan_name in due_names:
        launched.append(
            launch_refresh_plan(
                database_url=database_url,
                plan_name=plan_name,
                trigger_kind=trigger_kind,
            )
        )

    return {
        "due_plan_names": due_names,
        "run_count": len(launched),
        "launched": launched,
    }


def run_due_refresh_plans(
    session: Session,
    *,
    plan_names: list[str] | None = None,
) -> dict[str, Any]:
    plans = load_scheduler_plans()
    due_names = get_due_scheduler_plan_names(session, plans=plans)
    if plan_names is not None:
        allowed = set(plan_names)
        due_names = [name for name in due_names if name in allowed]

    results: list[dict[str, Any]] = []
    for plan_name in due_names:
        results.append(
            execute_refresh_plan(
                session,
                plan_name=plan_name,
                trigger_kind="scheduler",
            )
        )

    return {
        "due_plan_names": due_names,
        "run_count": len(results),
        "results": results,
    }


def start_local_scheduler_loop(
    *,
    database_url: str,
    poll_seconds: int = 60,
    max_cycles: int | None = None,
    run_on_start: bool = False,
) -> dict[str, Any]:
    session_factory = get_session_factory(database_url)
    cycles = 0
    executed_runs = 0

    while True:
        cycles += 1
        with session_factory() as session:
            if run_on_start or cycles > 1:
                result = run_due_refresh_plans(session)
                executed_runs += result["run_count"]

        if max_cycles is not None and cycles >= max_cycles:
            break
        time.sleep(poll_seconds)

    return {
        "poll_seconds": poll_seconds,
        "cycles": cycles,
        "executed_runs": executed_runs,
        "run_on_start": run_on_start,
    }


def _resolve_task_offset(
    session: Session,
    *,
    plan_name: str,
    task_job_name: str,
    limit: int | None,
    rotation_mode: str,
    rotation_step: int | None,
) -> int:
    if rotation_mode != "cycle":
        return 0
    step = rotation_step or limit or 0
    if step <= 0:
        return 0
    completed_runs = session.scalar(
        select(func.count())
        .select_from(RefreshJobRun)
        .where(
            RefreshJobRun.job_name == f"{plan_name}:{task_job_name}",
            RefreshJobRun.status == JobRunStatus.SUCCEEDED,
        )
    ) or 0
    return completed_runs * step
