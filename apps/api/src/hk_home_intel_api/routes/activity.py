from datetime import timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import (
    Development,
    Document,
    Listing,
    RefreshJobRun,
    SourceSnapshot,
    Transaction,
    WatchlistItem,
)
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityItemResponse(BaseModel):
    id: str
    kind: str
    timestamp: str
    title: str
    subtitle: str | None
    detail: str | None
    status: str | None
    source: str | None
    development_id: str | None
    development_name: str | None
    source_url: str | None
    file_path: str | None


class ActivitySummaryResponse(BaseModel):
    total_items: int
    refresh_job_count: int
    source_snapshot_count: int
    watchlist_update_count: int


class ActivityFeedResponse(BaseModel):
    items: list[ActivityItemResponse]
    summary: ActivitySummaryResponse


def _serialize_timestamp(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _display_development_name(development: Development | None, preferred_language: str) -> str | None:
    if development is None:
        return None
    return localize_text(
        development.name_translations_json or {},
        preferred_language,
        default=development.name_zh or development.name_en,
    )


def _resolve_snapshot_context(
    session: Session,
    snapshot: SourceSnapshot,
) -> tuple[Development | None, str | None, str | None]:
    if snapshot.object_type == "development":
        development = session.scalar(
            select(Development)
            .where(
                Development.source == snapshot.source,
                Development.source_external_id == snapshot.object_external_id,
            )
            .limit(1)
        )
        return development, None, snapshot.source_url

    if snapshot.object_type in {"document", "document_file"}:
        document = session.scalar(
            select(Document)
            .where(
                Document.source == snapshot.source,
                Document.source_doc_id == snapshot.object_external_id,
            )
            .limit(1)
        )
        if document is None:
            return None, None, snapshot.source_url
        development = session.get(Development, document.development_id) if document.development_id else None
        return development, document.title, document.source_url or snapshot.source_url

    if snapshot.object_type == "listing":
        listing = session.scalar(
            select(Listing)
            .where(
                Listing.source == snapshot.source,
                Listing.source_listing_id == snapshot.object_external_id,
            )
            .limit(1)
        )
        if listing is None:
            return None, None, snapshot.source_url
        development = session.get(Development, listing.development_id)
        return development, listing.title, listing.source_url or snapshot.source_url

    if snapshot.object_type == "transaction":
        transaction = session.scalar(
            select(Transaction)
            .where(
                Transaction.source == snapshot.source,
                Transaction.source_record_id == snapshot.object_external_id,
            )
            .limit(1)
        )
        if transaction is None:
            return None, None, snapshot.source_url
        development = session.get(Development, transaction.development_id)
        return development, transaction.doc_ref, transaction.source_url or snapshot.source_url

    return None, None, snapshot.source_url


def _snapshot_title(snapshot: SourceSnapshot, label: str | None) -> str:
    if snapshot.object_type == "development":
        return f"Development snapshot updated: {label or snapshot.object_external_id or 'unknown'}"
    if snapshot.object_type == "document":
        return f"Document metadata updated: {label or snapshot.object_external_id or 'unknown'}"
    if snapshot.object_type == "document_file":
        return f"Document file downloaded: {label or snapshot.object_external_id or 'unknown'}"
    if snapshot.object_type == "listing":
        return f"Listing snapshot updated: {label or snapshot.object_external_id or 'unknown'}"
    if snapshot.object_type == "transaction":
        return f"Transaction snapshot updated: {label or snapshot.object_external_id or 'unknown'}"
    return f"Snapshot updated: {snapshot.object_type}"


@router.get("/recent", response_model=ActivityFeedResponse)
def list_recent_activity(
    lang: str = Query(default="zh-Hant"),
    kind: str | None = Query(default=None),
    source: str | None = Query(default=None),
    development_id: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> ActivityFeedResponse:
    jobs = session.scalars(
        select(RefreshJobRun)
        .where(~RefreshJobRun.job_name.startswith("refresh_plan:"))
        .order_by(RefreshJobRun.started_at.desc())
        .limit(limit)
    ).all()
    snapshots = session.scalars(
        select(SourceSnapshot).order_by(SourceSnapshot.fetched_at.desc()).limit(limit)
    ).all()
    watchlist_items = session.scalars(
        select(WatchlistItem).order_by(WatchlistItem.updated_at.desc()).limit(limit)
    ).all()

    activity: list[ActivityItemResponse] = []

    for item in jobs:
        detail = None
        if item.summary_json:
            summary = item.summary_json
            detail = ", ".join(
                [
                    f"developments {summary.get('developments_created', 0) + summary.get('developments_updated', 0)}",
                    f"documents {summary.get('documents_upserted', 0)}",
                    f"snapshots {summary.get('snapshots_created', 0)}",
                ]
            )
        activity.append(
            ActivityItemResponse(
                id=item.id,
                kind="refresh_job",
                timestamp=_serialize_timestamp(item.started_at),
                title=f"{item.job_name} / {item.status.value}",
                subtitle=f"{item.source or 'unknown source'} / {item.trigger_kind}",
                detail=detail,
                status=item.status.value,
                source=item.source,
                development_id=None,
                development_name=None,
                source_url=None,
                file_path=None,
            )
        )

    for snapshot in snapshots:
        development, object_label, resolved_source_url = _resolve_snapshot_context(session, snapshot)
        development_name = _display_development_name(development, lang)
        subtitle_bits = [snapshot.source, snapshot.object_type, snapshot.snapshot_kind.value]
        if development_name:
            subtitle_bits.append(development_name)

        activity.append(
            ActivityItemResponse(
                id=snapshot.id,
                kind="source_snapshot",
                timestamp=_serialize_timestamp(snapshot.fetched_at),
                title=_snapshot_title(snapshot, object_label or development_name),
                subtitle=" / ".join(bit for bit in subtitle_bits if bit),
                detail=f"parse {snapshot.parse_status.value}",
                status=snapshot.parse_status.value,
                source=snapshot.source,
                development_id=development.id if development is not None else None,
                development_name=development_name,
                source_url=resolved_source_url,
                file_path=snapshot.file_path,
            )
        )

    for item in watchlist_items:
        development = item.development
        development_name = _display_development_name(development, lang)
        activity.append(
            ActivityItemResponse(
                id=item.id,
                kind="watchlist_update",
                timestamp=_serialize_timestamp(item.updated_at),
                title=f"Watchlist updated: {development_name or item.development_id}",
                subtitle=f"stage {item.decision_stage.value}",
                detail=item.note,
                status=item.decision_stage.value,
                source=development.source if development is not None else None,
                development_id=item.development_id,
                development_name=development_name,
                source_url=development.source_url if development is not None else None,
                file_path=None,
            )
        )

    if kind:
        activity = [item for item in activity if item.kind == kind]
    if source:
        activity = [item for item in activity if item.source == source]
    if development_id:
        activity = [item for item in activity if item.development_id == development_id]

    activity.sort(key=lambda item: item.timestamp, reverse=True)
    items = activity[:limit]
    return ActivityFeedResponse(
        items=items,
        summary=ActivitySummaryResponse(
            total_items=len(items),
            refresh_job_count=sum(1 for item in items if item.kind == "refresh_job"),
            source_snapshot_count=sum(1 for item in items if item.kind == "source_snapshot"),
            watchlist_update_count=sum(1 for item in items if item.kind == "watchlist_update"),
        ),
    )
