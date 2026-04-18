import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from hk_home_intel_connectors.http import fetch_text
from hk_home_intel_connectors.srpe import SRPEAdapter
from hk_home_intel_domain.ingestion import (
    backfill_development_coordinates,
    backfill_development_geography,
    backfill_centanet_listing_details,
    import_centanet_listing_detail,
    download_srpe_documents_for_development,
    import_centanet_search_results,
    import_ricacorp_search_results,
    import_centanet_sample,
    import_srpe_all_developments,
    import_srpe_sample,
)
from hk_home_intel_domain.maintenance import cleanup_runtime_artifacts
from hk_home_intel_domain.maintenance import compute_preflight_summary
from hk_home_intel_domain.commercial_discovery import (
    discover_commercial_monitor_candidates,
    rebalance_auto_discovered_monitors,
    serialize_commercial_discovery_summary,
)
from hk_home_intel_domain.monitor_sync import sync_commercial_monitor_config
from hk_home_intel_domain.refresh import (
    execute_commercial_search_monitor_batch,
    execute_commercial_search_monitor_refresh,
    execute_refresh_plan,
    execute_srpe_refresh,
    run_due_refresh_plans,
    start_local_scheduler_loop,
)
from hk_home_intel_shared.db import get_session_factory
from hk_home_intel_shared.runtime import ensure_runtime_dirs
from hk_home_intel_shared.scheduler import load_scheduler_plans
from hk_home_intel_shared.settings import get_settings


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "import-srpe-sample":
        run_import_srpe_sample(args.path)
        return
    if args.command == "import-centanet-sample":
        run_import_centanet_sample(args.path)
        return
    if args.command == "import-centanet-search":
        run_import_centanet_search(
            args.url,
            args.html_path,
            args.limit,
            args.with_details,
            args.save_detail_snapshots,
            args.detect_withdrawn,
        )
        return
    if args.command == "import-centanet-detail":
        run_import_centanet_detail(args.url, args.html_path, args.save_snapshot)
        return
    if args.command == "import-ricacorp-search":
        run_import_ricacorp_search(args.url, args.html_path, args.limit)
        return
    if args.command == "run-commercial-search-monitor":
        run_commercial_search_monitor(args.monitor_id, args.limit_override)
        return
    if args.command == "run-commercial-search-monitors":
        run_commercial_search_monitors(args.source, args.limit_override, args.include_inactive)
        return
    if args.command == "import-srpe-index":
        run_import_srpe_index(args.lang, args.limit, args.offset, args.with_details)
        return
    if args.command == "run-srpe-refresh":
        run_srpe_refresh(args.lang, args.limit, args.offset, args.with_details)
        return
    if args.command == "run-refresh-plan":
        run_refresh_plan(args.plan)
        return
    if args.command == "run-due-refresh-plans":
        run_due_plans(args.plan)
        return
    if args.command == "start-local-scheduler":
        run_local_scheduler(args.poll_seconds, args.max_cycles, args.run_on_start)
        return
    if args.command == "backfill-development-coordinates":
        run_backfill_development_coordinates(args.limit)
        return
    if args.command == "backfill-development-geography":
        run_backfill_development_geography(args.limit)
        return
    if args.command == "backfill-centanet-details":
        run_backfill_centanet_details(args.limit, args.all, args.save_snapshots)
        return
    if args.command == "cleanup-runtime-artifacts":
        run_cleanup_runtime_artifacts(
            args.refresh_job_days,
            args.keep_latest_jobs_per_name,
            args.search_snapshot_days,
            args.detail_snapshot_days,
            args.keep_latest_snapshots_per_object,
        )
        return
    if args.command == "sync-commercial-monitor-config":
        run_sync_commercial_monitor_config(args.path, args.dry_run)
        return
    if args.command == "discover-commercial-monitor-candidates":
        run_discover_commercial_monitor_candidates(
            args.source,
            args.limit,
            args.validate,
            args.create_monitors,
            args.activate_created,
            args.include_existing,
            args.development_id,
        )
        return
    if args.command == "rebalance-commercial-monitors":
        run_rebalance_commercial_monitors(args.source)
        return
    if args.command == "preflight-check":
        run_preflight_check()
        return
    if args.command == "download-srpe-documents":
        run_download_srpe_documents(args.source_external_id, args.force)
        return
    if args.command == "fetch-srpe-homepage":
        run_fetch_srpe_homepage(args.use_fixture)
        return
    if args.command == "discover-srpe-entrypoints":
        run_discover_srpe_entrypoints(args.use_fixture)
        return
    if args.command == "discover-srpe-assets":
        run_discover_srpe_assets(args.use_fixture)
        return
    if args.command == "discover-srpe-bundle-entrypoints":
        run_discover_srpe_bundle_entrypoints(args.use_fixture, args.asset_url)
        return

    settings = get_settings()
    ensure_runtime_dirs()

    summary = {
        "worker": "hk-home-intel",
        "status": "ready",
        "environment": settings.environment,
        "database_url": settings.database_url,
        "data_root": str(settings.data_root),
        "next_step": "Implement schedulers and source adapters in Phase 1.",
    }
    print(json.dumps(summary, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hhi-worker")
    subparsers = parser.add_subparsers(dest="command")

    import_parser = subparsers.add_parser("import-srpe-sample")
    import_parser.add_argument("--path", dest="path", default=None)

    centanet_parser = subparsers.add_parser("import-centanet-sample")
    centanet_parser.add_argument("--path", dest="path", default=None)

    centanet_search_parser = subparsers.add_parser("import-centanet-search")
    centanet_search_parser.add_argument("--url", dest="url", required=True)
    centanet_search_parser.add_argument("--html-path", dest="html_path", default=None)
    centanet_search_parser.add_argument("--limit", dest="limit", type=int, default=None)
    centanet_search_parser.add_argument("--with-details", dest="with_details", action="store_true")
    centanet_search_parser.add_argument("--save-detail-snapshots", dest="save_detail_snapshots", action="store_true")
    centanet_search_parser.add_argument("--detect-withdrawn", dest="detect_withdrawn", action="store_true")

    centanet_detail_parser = subparsers.add_parser("import-centanet-detail")
    centanet_detail_parser.add_argument("--url", dest="url", required=True)
    centanet_detail_parser.add_argument("--html-path", dest="html_path", default=None)
    centanet_detail_parser.add_argument("--save-snapshot", dest="save_snapshot", action="store_true")

    ricacorp_search_parser = subparsers.add_parser("import-ricacorp-search")
    ricacorp_search_parser.add_argument("--url", dest="url", required=True)
    ricacorp_search_parser.add_argument("--html-path", dest="html_path", default=None)
    ricacorp_search_parser.add_argument("--limit", dest="limit", type=int, default=None)

    monitor_parser = subparsers.add_parser("run-commercial-search-monitor")
    monitor_parser.add_argument("--monitor-id", dest="monitor_id", required=True)
    monitor_parser.add_argument("--limit-override", dest="limit_override", type=int, default=None)

    monitor_batch_parser = subparsers.add_parser("run-commercial-search-monitors")
    monitor_batch_parser.add_argument("--source", dest="source", default="centanet")
    monitor_batch_parser.add_argument("--limit-override", dest="limit_override", type=int, default=None)
    monitor_batch_parser.add_argument("--include-inactive", dest="include_inactive", action="store_true")

    import_index_parser = subparsers.add_parser("import-srpe-index")
    import_index_parser.add_argument("--lang", dest="lang", default="en")
    import_index_parser.add_argument("--limit", dest="limit", type=int, default=None)
    import_index_parser.add_argument("--offset", dest="offset", type=int, default=0)
    import_index_parser.add_argument("--with-details", dest="with_details", action="store_true")

    refresh_parser = subparsers.add_parser("run-srpe-refresh")
    refresh_parser.add_argument("--lang", dest="lang", default="en")
    refresh_parser.add_argument("--limit", dest="limit", type=int, default=None)
    refresh_parser.add_argument("--offset", dest="offset", type=int, default=0)
    refresh_parser.add_argument("--with-details", dest="with_details", action="store_true")

    plan_parser = subparsers.add_parser("run-refresh-plan")
    plan_parser.add_argument("--plan", dest="plan", default="daily_local")

    due_parser = subparsers.add_parser("run-due-refresh-plans")
    due_parser.add_argument("--plan", dest="plan", action="append", default=None)

    scheduler_parser = subparsers.add_parser("start-local-scheduler")
    scheduler_parser.add_argument("--poll-seconds", dest="poll_seconds", type=int, default=60)
    scheduler_parser.add_argument("--max-cycles", dest="max_cycles", type=int, default=None)
    scheduler_parser.add_argument("--run-on-start", dest="run_on_start", action="store_true")

    backfill_parser = subparsers.add_parser("backfill-development-coordinates")
    backfill_parser.add_argument("--limit", dest="limit", type=int, default=None)

    geography_backfill_parser = subparsers.add_parser("backfill-development-geography")
    geography_backfill_parser.add_argument("--limit", dest="limit", type=int, default=None)

    centanet_backfill_parser = subparsers.add_parser("backfill-centanet-details")
    centanet_backfill_parser.add_argument("--limit", dest="limit", type=int, default=None)
    centanet_backfill_parser.add_argument("--all", dest="all", action="store_true")
    centanet_backfill_parser.add_argument("--save-snapshots", dest="save_snapshots", action="store_true")

    cleanup_parser = subparsers.add_parser("cleanup-runtime-artifacts")
    cleanup_parser.add_argument("--refresh-job-days", dest="refresh_job_days", type=int, default=30)
    cleanup_parser.add_argument("--keep-latest-jobs-per-name", dest="keep_latest_jobs_per_name", type=int, default=20)
    cleanup_parser.add_argument("--search-snapshot-days", dest="search_snapshot_days", type=int, default=14)
    cleanup_parser.add_argument("--detail-snapshot-days", dest="detail_snapshot_days", type=int, default=7)
    cleanup_parser.add_argument(
        "--keep-latest-snapshots-per-object",
        dest="keep_latest_snapshots_per_object",
        type=int,
        default=5,
    )

    monitor_sync_parser = subparsers.add_parser("sync-commercial-monitor-config")
    monitor_sync_parser.add_argument("--path", dest="path", default="configs/commercial_monitors.toml")
    monitor_sync_parser.add_argument("--dry-run", dest="dry_run", action="store_true")

    discovery_parser = subparsers.add_parser("discover-commercial-monitor-candidates")
    discovery_parser.add_argument("--source", dest="source", default="centanet")
    discovery_parser.add_argument("--limit", dest="limit", type=int, default=20)
    discovery_parser.add_argument("--validate", dest="validate", action="store_true")
    discovery_parser.add_argument("--create-monitors", dest="create_monitors", action="store_true")
    discovery_parser.add_argument("--activate-created", dest="activate_created", action="store_true")
    discovery_parser.add_argument("--include-existing", dest="include_existing", action="store_true")
    discovery_parser.add_argument("--development-id", dest="development_id", default=None)

    rebalance_parser = subparsers.add_parser("rebalance-commercial-monitors")
    rebalance_parser.add_argument("--source", dest="source", default=None)

    subparsers.add_parser("preflight-check")

    download_parser = subparsers.add_parser("download-srpe-documents")
    download_parser.add_argument("--source-external-id", dest="source_external_id", required=True)
    download_parser.add_argument("--force", dest="force", action="store_true")

    homepage_parser = subparsers.add_parser("fetch-srpe-homepage")
    homepage_parser.add_argument("--use-fixture", action="store_true")

    entrypoint_parser = subparsers.add_parser("discover-srpe-entrypoints")
    entrypoint_parser.add_argument("--use-fixture", action="store_true")

    asset_parser = subparsers.add_parser("discover-srpe-assets")
    asset_parser.add_argument("--use-fixture", action="store_true")

    bundle_parser = subparsers.add_parser("discover-srpe-bundle-entrypoints")
    bundle_parser.add_argument("--use-fixture", action="store_true")
    bundle_parser.add_argument("--asset-url", dest="asset_url", default=None)

    return parser


def run_import_srpe_sample(path: str | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_srpe_sample(session, path)

    print(
        json.dumps(
            {
                "source": summary.source,
                "developments_created": summary.developments_created,
                "developments_updated": summary.developments_updated,
                "documents_upserted": summary.documents_upserted,
                "listings_upserted": summary.listings_upserted,
                "transactions_upserted": summary.transactions_upserted,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
                "detail_failures": summary.detail_failures,
            },
            indent=2,
        )
    )


def run_import_centanet_sample(path: str | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_centanet_sample(session, path)

    print(
        json.dumps(
            {
                "source": summary.source,
                "developments_created": summary.developments_created,
                "developments_updated": summary.developments_updated,
                "documents_upserted": summary.documents_upserted,
                "listings_upserted": summary.listings_upserted,
                "transactions_upserted": summary.transactions_upserted,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
                "detail_failures": summary.detail_failures,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_import_centanet_search(
    url: str,
    html_path: str | None,
    limit: int | None,
    with_details: bool,
    save_detail_snapshots: bool,
    detect_withdrawn: bool,
) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_centanet_search_results(
            session,
            url=url,
            html_path=html_path,
            limit=limit,
            with_details=with_details,
            save_detail_snapshots=save_detail_snapshots,
            detect_withdrawn=detect_withdrawn,
        )

    print(
        json.dumps(
            {
                "source": summary.source,
                "url": url,
                "html_path": html_path,
                "limit": limit,
                "with_details": with_details,
                "save_detail_snapshots": save_detail_snapshots,
                "detect_withdrawn": detect_withdrawn,
                "developments_created": summary.developments_created,
                "developments_updated": summary.developments_updated,
                "documents_upserted": summary.documents_upserted,
                "listings_upserted": summary.listings_upserted,
                "transactions_upserted": summary.transactions_upserted,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_import_centanet_detail(url: str, html_path: str | None, save_snapshot: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_centanet_listing_detail(session, url=url, html_path=html_path, save_snapshot=save_snapshot)

    print(
        json.dumps(
            {
                "source": summary.source,
                "url": url,
                "html_path": html_path,
                "save_snapshot": save_snapshot,
                "developments_created": summary.developments_created,
                "developments_updated": summary.developments_updated,
                "documents_upserted": summary.documents_upserted,
                "listings_upserted": summary.listings_upserted,
                "transactions_upserted": summary.transactions_upserted,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_import_ricacorp_search(url: str, html_path: str | None, limit: int | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_ricacorp_search_results(
            session,
            url=url,
            html_path=html_path,
            limit=limit,
        )

    print(
        json.dumps(
            {
                "source": summary.source,
                "url": url,
                "html_path": html_path,
                "limit": limit,
                "developments_created": summary.developments_created,
                "developments_updated": summary.developments_updated,
                "documents_upserted": summary.documents_upserted,
                "listings_upserted": summary.listings_upserted,
                "transactions_upserted": summary.transactions_upserted,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_commercial_search_monitor(monitor_id: str, limit_override: int | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        result = execute_commercial_search_monitor_refresh(
            session,
            monitor_id=monitor_id,
            limit_override=limit_override,
            trigger_kind="manual",
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_commercial_search_monitors(source: str, limit_override: int | None, include_inactive: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        result = execute_commercial_search_monitor_batch(
            session,
            source=source,
            active_only=not include_inactive,
            limit_override=limit_override,
            trigger_kind="manual",
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_import_srpe_index(language: str, limit: int | None, offset: int, include_details: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = import_srpe_all_developments(
            session,
            language=language,
            limit=limit,
            offset=offset,
            include_details=include_details,
        )

    print(
        json.dumps(
            {
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
            },
            indent=2,
        )
    )


def run_srpe_refresh(language: str, limit: int | None, offset: int, include_details: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        result = execute_srpe_refresh(
            session,
            language=language,
            limit=limit,
            offset=offset,
            include_details=include_details,
        )

    print(json.dumps(result, indent=2))


def run_refresh_plan(plan_name: str) -> None:
    ensure_runtime_dirs()
    plans = load_scheduler_plans()
    if plan_name not in plans:
        raise ValueError(f"unknown refresh plan: {plan_name}")

    session_factory = get_session_factory()
    with session_factory() as session:
        result = execute_refresh_plan(session, plan_name=plan_name)

    print(json.dumps(result, indent=2))


def run_due_plans(plan_names: list[str] | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        result = run_due_refresh_plans(session, plan_names=plan_names)

    print(json.dumps(result, indent=2))


def run_local_scheduler(poll_seconds: int, max_cycles: int | None, run_on_start: bool) -> None:
    ensure_runtime_dirs()
    settings = get_settings()
    result = start_local_scheduler_loop(
        database_url=settings.database_url,
        poll_seconds=poll_seconds,
        max_cycles=max_cycles,
        run_on_start=run_on_start,
    )
    print(json.dumps(result, indent=2))


def run_backfill_development_coordinates(limit: int | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = backfill_development_coordinates(session, limit=limit)

    print(
        json.dumps(
            {
                "scanned": summary.scanned,
                "updated": summary.updated,
                "unresolved": summary.unresolved,
                "limit": limit,
            },
            indent=2,
        )
    )


def run_backfill_development_geography(limit: int | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = backfill_development_geography(session, limit=limit)

    print(
        json.dumps(
            {
                "scanned": summary.scanned,
                "updated": summary.updated,
                "unchanged": summary.unchanged,
                "limit": limit,
            },
            indent=2,
        )
    )


def run_backfill_centanet_details(limit: int | None, process_all: bool, save_snapshots: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = backfill_centanet_listing_details(
            session,
            limit=limit,
            only_missing_detail=not process_all,
            save_snapshots=save_snapshots,
        )

    print(
        json.dumps(
            {
                "source": summary.source,
                "limit": limit,
                "only_missing_detail": not process_all,
                "save_snapshots": save_snapshots,
                "scanned": summary.scanned,
                "enriched": summary.enriched,
                "skipped": summary.skipped,
                "failed": summary.failed,
                "price_events_created": summary.price_events_created,
                "snapshots_created": summary.snapshots_created,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_cleanup_runtime_artifacts(
    refresh_job_days: int,
    keep_latest_jobs_per_name: int,
    search_snapshot_days: int,
    detail_snapshot_days: int,
    keep_latest_snapshots_per_object: int,
) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = cleanup_runtime_artifacts(
            session,
            refresh_job_days=refresh_job_days,
            keep_latest_jobs_per_name=keep_latest_jobs_per_name,
            search_snapshot_days=search_snapshot_days,
            detail_snapshot_days=detail_snapshot_days,
            keep_latest_snapshots_per_object=keep_latest_snapshots_per_object,
        )

    print(
        json.dumps(
            {
                "refresh_job_days": refresh_job_days,
                "keep_latest_jobs_per_name": keep_latest_jobs_per_name,
                "search_snapshot_days": search_snapshot_days,
                "detail_snapshot_days": detail_snapshot_days,
                "keep_latest_snapshots_per_object": keep_latest_snapshots_per_object,
                "refresh_jobs_deleted": summary.refresh_jobs_deleted,
                "snapshots_deleted": summary.snapshots_deleted,
                "files_deleted": summary.files_deleted,
            },
            indent=2,
        )
    )


def run_sync_commercial_monitor_config(path: str, dry_run: bool) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = sync_commercial_monitor_config(session, path=path, dry_run=dry_run)

    print(
        json.dumps(
            {
                "path": summary.path,
                "processed": summary.processed,
                "created": summary.created,
                "updated": summary.updated,
                "unchanged": summary.unchanged,
                "dry_run": summary.dry_run,
            },
            indent=2,
        )
    )


def run_discover_commercial_monitor_candidates(
    source: str,
    limit: int,
    validate: bool,
    create_monitors: bool,
    activate_created: bool,
    include_existing: bool,
    development_id: str | None,
) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = discover_commercial_monitor_candidates(
            session,
            source=source,
            limit=limit,
            validate=validate,
            create_monitors=create_monitors,
            activate_created=activate_created,
            include_existing=include_existing,
            development_id=development_id,
        )

    print(json.dumps(serialize_commercial_discovery_summary(summary), indent=2, ensure_ascii=False))


def run_rebalance_commercial_monitors(source: str | None) -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = rebalance_auto_discovered_monitors(session, source=source)
    print(
        json.dumps(
            {
                "source": summary.source,
                "scanned": summary.scanned,
                "updated": summary.updated,
                "unchanged": summary.unchanged,
                "unmatched": summary.unmatched,
                "monitors": summary.monitors,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_preflight_check() -> None:
    ensure_runtime_dirs()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = compute_preflight_summary(session)

    print(
        json.dumps(
            {
                "readiness_status": summary.readiness_status,
                "notes": summary.notes,
                "development_count": summary.development_count,
                "development_with_coordinates_count": summary.development_with_coordinates_count,
                "commercial_listing_count": summary.commercial_listing_count,
                "price_event_count": summary.price_event_count,
                "active_monitor_count": summary.active_monitor_count,
                "attention_monitor_count": summary.attention_monitor_count,
                "latest_job_status": summary.latest_job_status,
            },
            indent=2,
        )
    )


def run_download_srpe_documents(source_external_id: str, force: bool) -> None:
    ensure_runtime_dirs()
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = download_srpe_documents_for_development(
            session,
            development_external_id=source_external_id,
            output_root=settings.data_root / "documents",
            force=force,
        )

    print(
        json.dumps(
            {
                "source": summary.source,
                "development_id": summary.development_id,
                "development_external_id": summary.development_external_id,
                "downloaded": summary.downloaded,
                "skipped": summary.skipped,
                "failed": summary.failed,
                "snapshots_created": summary.snapshots_created,
                "force": force,
            },
            indent=2,
        )
    )


def run_fetch_srpe_homepage(use_fixture: bool) -> None:
    settings = get_settings()
    adapter = SRPEAdapter()
    html = adapter.load_homepage_fixture() if use_fixture else adapter.fetch_homepage_html()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = settings.data_root / "snapshots" / "srpe"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"homepage-{timestamp}.html"
    path.write_text(html, encoding="utf-8")

    print(
        json.dumps(
            {
                "source": adapter.source_name,
                "snapshot_path": str(path),
                "bytes": len(html.encode("utf-8")),
                "mode": "fixture" if use_fixture else "live",
            },
            indent=2,
        )
    )


def run_discover_srpe_entrypoints(use_fixture: bool) -> None:
    adapter = SRPEAdapter()
    html = adapter.load_homepage_fixture() if use_fixture else adapter.fetch_homepage_html()
    entrypoints = adapter.discover_entrypoints_from_html(html)
    print(
        json.dumps(
            {
                "source": adapter.source_name,
                "mode": "fixture" if use_fixture else "live",
                "entrypoints": entrypoints,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_discover_srpe_assets(use_fixture: bool) -> None:
    adapter = SRPEAdapter()
    html = adapter.load_homepage_fixture() if use_fixture else adapter.fetch_homepage_html()
    assets = adapter.discover_asset_urls_from_html(html)
    print(
        json.dumps(
            {
                "source": adapter.source_name,
                "mode": "fixture" if use_fixture else "live",
                "assets": assets,
            },
            indent=2,
        )
    )


def run_discover_srpe_bundle_entrypoints(use_fixture: bool, asset_url: str | None) -> None:
    adapter = SRPEAdapter()
    mode = "fixture"
    source_assets: list[str] = []
    if use_fixture:
        text = adapter.load_bundle_fixture()
    elif asset_url:
        text = fetch_text(asset_url)
        mode = "live"
        source_assets = [asset_url]
    else:
        html = adapter.fetch_homepage_html()
        assets = adapter.discover_asset_urls_from_html(html)
        script_assets = [asset for asset in assets if asset.endswith(".js")]
        source_assets = script_assets[:2]
        text = "\n".join(fetch_text(asset) for asset in source_assets)
        mode = "live"

    entrypoints = adapter.extract_entrypoints_from_bundle(text)
    print(
        json.dumps(
            {
                "source": adapter.source_name,
                "mode": mode,
                "asset_urls": source_assets,
                "entrypoints": entrypoints,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
