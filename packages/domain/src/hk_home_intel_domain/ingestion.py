from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hk_home_intel_connectors.base import RawRecord
from hk_home_intel_connectors.centanet import CentanetAdapter
from hk_home_intel_connectors.srpe import SRPEAdapter
from hk_home_intel_domain.enums import ListingStatus, ParseStatus, PriceEventType, SnapshotKind
from hk_home_intel_domain.normalization import enrich_development_payload
from hk_home_intel_domain.models import Development, Document, Listing, PriceEvent, SourceSnapshot, Transaction


@dataclass(slots=True)
class ImportSummary:
    source: str
    developments_created: int = 0
    developments_updated: int = 0
    documents_upserted: int = 0
    listings_upserted: int = 0
    transactions_upserted: int = 0
    price_events_created: int = 0
    snapshots_created: int = 0


@dataclass(slots=True)
class DocumentDownloadSummary:
    source: str
    development_id: str
    development_external_id: str
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    snapshots_created: int = 0


@dataclass(slots=True)
class CoordinateBackfillSummary:
    scanned: int = 0
    updated: int = 0
    unresolved: int = 0


def import_srpe_sample(session: Session, path: str | None = None) -> ImportSummary:
    adapter = SRPEAdapter()
    return _import_srpe_bundles(session, adapter, adapter.sample_development_bundle(path))


def import_centanet_sample(session: Session, path: str | None = None) -> ImportSummary:
    adapter = CentanetAdapter()
    return _import_listing_bundles(session, adapter, adapter.sample_listing_bundle(path))


def import_centanet_search_results(
    session: Session,
    *,
    url: str,
    html_path: str | None = None,
    limit: int | None = None,
) -> ImportSummary:
    adapter = CentanetAdapter()
    return _import_listing_bundles(
        session,
        adapter,
        adapter.search_results_listing_bundle(url=url, html_path=html_path, limit=limit),
    )


def import_srpe_all_developments(
    session: Session,
    *,
    language: str = "en",
    limit: int | None = None,
    offset: int = 0,
    include_details: bool = False,
) -> ImportSummary:
    adapter = SRPEAdapter()
    bundles = adapter.fetch_all_development_bundles(
        language=language,
        limit=limit,
        offset=offset,
        include_details=include_details,
    )
    return _import_srpe_bundles(session, adapter, bundles)


def download_srpe_documents_for_development(
    session: Session,
    *,
    development_external_id: str,
    output_root: Path,
    force: bool = False,
) -> DocumentDownloadSummary:
    adapter = SRPEAdapter()
    development = session.scalar(
        select(Development).where(
            and_(
                Development.source == adapter.source_name,
                Development.source_external_id == development_external_id,
            )
        ).limit(1)
    )
    if development is None:
        raise ValueError(f"srpe development not found: {development_external_id}")

    documents = session.scalars(
        select(Document)
        .where(Document.development_id == development.id)
        .order_by(Document.published_at.desc().nullslast(), Document.created_at.desc())
    ).all()
    summary = DocumentDownloadSummary(
        source=adapter.source_name,
        development_id=development.id,
        development_external_id=development_external_id,
    )
    base_dir = output_root / adapter.source_name / development_external_id

    for document in documents:
        if document.doc_type.value not in {
            "brochure",
            "price_list",
            "sales_arrangement",
            "transaction_record",
        }:
            summary.skipped += 1
            continue
        if document.file_path and not force:
            summary.skipped += 1
            continue

        metadata = document.metadata_json or {}
        file_name = metadata.get("file_name")
        output_dir = base_dir / document.doc_type.value
        try:
            result = adapter.download_document_file(
                document_type=document.doc_type,
                development_external_id=development_external_id,
                document_metadata=metadata,
                output_dir=output_dir,
            )
        except Exception:
            summary.failed += 1
            continue

        document.file_path = result["path"]
        document.mime_type = result["mime_type"]
        document.content_hash = result["content_hash"]
        session.add(
            SourceSnapshot(
                source=adapter.source_name,
                object_type="document_file",
                object_external_id=document.source_doc_id,
                source_url=document.source_url,
                snapshot_kind=SnapshotKind.PDF,
                file_path=result["path"],
                content_hash=result["content_hash"],
                http_status=result["http_status"],
                parse_status=ParseStatus.PENDING,
                metadata_json={
                    "document_id": document.id,
                    "development_id": development.id,
                    "development_external_id": development_external_id,
                    "downloaded_at": datetime.utcnow().isoformat(),
                    "bytes": result["bytes"],
                    "headers": result["headers"],
                    "file_name": result["file_name"],
                },
            )
        )
        session.commit()
        summary.downloaded += 1
        summary.snapshots_created += 1

    return summary


def backfill_development_coordinates(
    session: Session,
    *,
    limit: int | None = None,
) -> CoordinateBackfillSummary:
    stmt = select(Development).where(
        or_(
            Development.lat.is_(None),
            Development.lng.is_(None),
        )
    ).order_by(Development.updated_at.desc())
    if limit:
        stmt = stmt.limit(limit)

    developments = session.scalars(stmt).all()
    summary = CoordinateBackfillSummary(scanned=len(developments))
    for development in developments:
        enriched = enrich_development_payload(
            {
                "address_raw": development.address_raw,
                "district": development.district,
                "lat": development.lat,
                "lng": development.lng,
            }
        )
        if enriched.get("lat") is None or enriched.get("lng") is None:
            summary.unresolved += 1
            continue
        development.address_normalized = enriched.get("address_normalized")
        development.lat = enriched["lat"]
        development.lng = enriched["lng"]
        summary.updated += 1

    session.commit()
    return summary


def _import_srpe_bundles(
    session: Session,
    adapter: SRPEAdapter,
    bundles: Iterable[dict[str, Any]],
) -> ImportSummary:
    return _import_listing_bundles(session, adapter, bundles)


def _import_listing_bundles(
    session: Session,
    adapter,
    bundles: Iterable[dict[str, Any]],
) -> ImportSummary:
    summary = ImportSummary(source=adapter.source_name)

    for bundle in bundles:
        development_payload = adapter.normalize_development(bundle["development"])
        development, created = upsert_development(session, development_payload)
        if created:
            summary.developments_created += 1
        else:
            summary.developments_updated += 1

        summary.snapshots_created += create_snapshot(
            session=session,
            record=bundle["development"],
            object_type="development",
        )

        for raw_document in bundle["documents"]:
            document_payload = adapter.normalize_document(raw_document)
            document_payload["development_id"] = development.id
            upsert_document(session, document_payload)
            summary.documents_upserted += 1
            summary.snapshots_created += create_snapshot(
                session=session,
                record=raw_document,
                object_type="document",
            )

        for raw_listing in bundle["listings"]:
            listing_payload = adapter.normalize_listing(raw_listing)
            listing_payload["development_id"] = development.id
            summary.price_events_created += upsert_listing(session, listing_payload)
            summary.listings_upserted += 1
            summary.snapshots_created += create_snapshot(
                session=session,
                record=raw_listing,
                object_type="listing",
            )

        for raw_transaction in bundle["transactions"]:
            transaction_payload = adapter.normalize_transaction(raw_transaction)
            transaction_payload["development_id"] = development.id
            upsert_transaction(session, transaction_payload)
            summary.transactions_upserted += 1
            summary.snapshots_created += create_snapshot(
                session=session,
                record=raw_transaction,
                object_type="transaction",
            )

    session.commit()
    return summary


def upsert_development(session: Session, payload: dict[str, Any]) -> tuple[Development, bool]:
    existing = find_existing_development(session, payload)
    fields = {
        key: value
        for key, value in enrich_development_payload(payload).items()
        if key in {
            "source",
            "source_external_id",
            "source_url",
            "name_zh",
            "name_en",
            "name_translations_json",
            "aliases_json",
            "address_raw",
            "address_normalized",
            "address_translations_json",
            "district",
            "region",
            "lat",
            "lng",
            "developer_names_json",
            "completion_year",
            "listing_segment",
            "tags_json",
            "source_confidence",
        }
    }
    if existing is None:
        development = Development(**fields)
        session.add(development)
        session.flush()
        return development, True

    for key, value in fields.items():
        if value in (None, "", [], {}):
            continue
        setattr(existing, key, value)
    session.flush()
    return existing, False


def upsert_document(session: Session, payload: dict[str, Any]) -> Document:
    legacy_source_doc_id = _legacy_srpe_document_id(payload)
    document = session.scalar(
        select(Document).where(
            and_(
                Document.source == payload["source"],
                Document.source_doc_id == payload["source_doc_id"],
            )
        )
    )
    if document is None:
        if legacy_source_doc_id:
            document = session.scalar(
                select(Document).where(
                    and_(
                        Document.source == payload["source"],
                        Document.source_doc_id == legacy_source_doc_id,
                    )
                )
            )
    if document is None:
        document = Document(**payload)
        session.add(document)
    else:
        for key, value in payload.items():
            setattr(document, key, value)

    if legacy_source_doc_id and document.source_doc_id != legacy_source_doc_id:
        legacy_duplicate = session.scalar(
            select(Document).where(
                and_(
                    Document.source == payload["source"],
                    Document.source_doc_id == legacy_source_doc_id,
                )
            )
        )
        if legacy_duplicate is not None and legacy_duplicate.id != document.id:
            session.delete(legacy_duplicate)
    session.flush()
    return document


def upsert_listing(session: Session, payload: dict[str, Any]) -> int:
    event_count = 0
    listing = session.scalar(
        select(Listing).where(
            and_(
                Listing.source == payload["source"],
                Listing.source_listing_id == payload["source_listing_id"],
            )
        )
    )
    if listing is None:
        listing = Listing(**payload)
        session.add(listing)
        session.flush()
        create_price_event(
            session,
            source=listing.source,
            event_type=PriceEventType.NEW_LISTING,
            development_id=listing.development_id,
            listing_id=listing.id,
            old_price_hkd=None,
            new_price_hkd=listing.asking_price_hkd,
            old_status=None,
            new_status=listing.status.value,
            raw_payload_json=payload,
        )
        event_count += 1
    else:
        old_price = listing.asking_price_hkd
        old_status = listing.status.value if listing.status is not None else None
        for key, value in payload.items():
            setattr(listing, key, value)
        session.flush()
        new_price = listing.asking_price_hkd
        new_status = listing.status.value if listing.status is not None else None
        if old_price is not None and new_price is not None and old_price != new_price:
            event_type = PriceEventType.PRICE_DROP if new_price < old_price else PriceEventType.PRICE_RAISE
            create_price_event(
                session,
                source=listing.source,
                event_type=event_type,
                development_id=listing.development_id,
                listing_id=listing.id,
                old_price_hkd=old_price,
                new_price_hkd=new_price,
                old_status=old_status,
                new_status=new_status,
                raw_payload_json=payload,
            )
            event_count += 1
        if old_status != new_status:
            status_event_type = PriceEventType.STATUS_CHANGE
            if old_status == ListingStatus.WITHDRAWN.value and new_status == ListingStatus.ACTIVE.value:
                status_event_type = PriceEventType.RELIST
            elif new_status == ListingStatus.SOLD.value:
                status_event_type = PriceEventType.SOLD
            elif new_status == ListingStatus.WITHDRAWN.value:
                status_event_type = PriceEventType.WITHDRAWN
            create_price_event(
                session,
                source=listing.source,
                event_type=status_event_type,
                development_id=listing.development_id,
                listing_id=listing.id,
                old_price_hkd=old_price,
                new_price_hkd=new_price,
                old_status=old_status,
                new_status=new_status,
                raw_payload_json=payload,
            )
            event_count += 1
    session.flush()
    return event_count


def upsert_transaction(session: Session, payload: dict[str, Any]) -> Transaction:
    transaction = session.scalar(
        select(Transaction).where(
            and_(
                Transaction.source == payload["source"],
                Transaction.source_record_id == payload["source_record_id"],
            )
        )
    )
    if transaction is None:
        transaction = Transaction(**payload)
        session.add(transaction)
    else:
        for key, value in payload.items():
            setattr(transaction, key, value)
    session.flush()
    return transaction


def create_snapshot(session: Session, record: RawRecord, object_type: str) -> int:
    snapshot = SourceSnapshot(
        source=record.source,
        object_type=object_type,
        object_external_id=record.external_id,
        source_url=record.source_url,
        snapshot_kind="json",
        metadata_json=record.payload,
        parse_status="parsed",
    )
    session.add(snapshot)
    session.flush()
    return 1


def create_price_event(
    session: Session,
    *,
    source: str,
    event_type: PriceEventType,
    development_id: str,
    listing_id: str | None,
    old_price_hkd,
    new_price_hkd,
    old_status: str | None,
    new_status: str | None,
    raw_payload_json: dict[str, Any] | None,
) -> PriceEvent:
    event = PriceEvent(
        source=source,
        event_type=event_type,
        development_id=development_id,
        listing_id=listing_id,
        event_at=datetime.now(timezone.utc),
        old_price_hkd=old_price_hkd,
        new_price_hkd=new_price_hkd,
        old_status=old_status,
        new_status=new_status,
        raw_payload_json=_json_safe(raw_payload_json),
    )
    session.add(event)
    session.flush()
    return event


def find_existing_development(session: Session, payload: dict[str, Any]) -> Development | None:
    source = payload.get("source")
    source_external_id = payload.get("source_external_id")
    if source and source_external_id:
        existing = session.scalar(
            select(Development).where(
                and_(
                    Development.source == source,
                    Development.source_external_id == source_external_id,
                )
            ).limit(1)
        )
        if existing is not None:
            return existing

    name_conditions = []
    if payload.get("name_zh"):
        name_conditions.append(Development.name_zh == payload["name_zh"])
    if payload.get("name_en"):
        name_conditions.append(Development.name_en == payload["name_en"])

    if not name_conditions:
        return None

    stmt = select(Development).where(or_(*name_conditions))

    # Address alone is too weak for cross-source entity merging. Keep it only as a
    # tie-breaker after a name match when both sides provide a normalized address.
    if payload.get("address_raw"):
        stmt = stmt.order_by(Development.address_raw == payload["address_raw"])

    return session.scalar(stmt.limit(1))


def _legacy_srpe_document_id(payload: dict[str, Any]) -> str | None:
    if payload.get("source") != "srpe":
        return None
    source_doc_id = payload.get("source_doc_id")
    if not isinstance(source_doc_id, str) or ":" not in source_doc_id:
        return None
    _, legacy_id = source_doc_id.split(":", 1)
    return legacy_id or None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)
