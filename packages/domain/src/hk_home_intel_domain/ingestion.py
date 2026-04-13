from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
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
from hk_home_intel_shared.settings import get_settings


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


@dataclass(slots=True)
class ListingDetailBackfillSummary:
    source: str
    scanned: int = 0
    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    price_events_created: int = 0
    snapshots_created: int = 0


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
    with_details: bool = False,
    save_detail_snapshots: bool = False,
    detect_withdrawn: bool = False,
) -> ImportSummary:
    adapter = CentanetAdapter()
    html_text = Path(html_path).read_text(encoding="utf-8") if html_path else adapter.fetch_search_results_html(url)
    bundles = adapter.search_results_listing_bundle(url=url, html_text=html_text, limit=limit)
    summary = _import_listing_bundles(
        session,
        adapter,
        bundles,
    )
    summary.snapshots_created += create_text_snapshot(
        session,
        source=adapter.source_name,
        object_type="search_page",
        object_external_id=url,
        source_url=url,
        text=html_text,
        metadata_json={
            "url": url,
            "mode": "fixture" if html_path else "live",
            "html_path": html_path,
            "listing_count": len(bundles),
        },
        parse_status=ParseStatus.PARSED,
    )
    if detect_withdrawn:
        if limit is not None:
            raise ValueError("detect_withdrawn requires a full search result import; omit --limit.")
        current_listing_ids = {
            raw_listing.external_id
            for bundle in bundles
            for raw_listing in bundle["listings"]
        }
        development_external_id = None
        if bundles:
            development_external_id = bundles[0]["development"].external_id
        if development_external_id:
            summary.price_events_created += mark_missing_centanet_listings_withdrawn(
                session,
                development_external_id=development_external_id,
                current_source_listing_ids=current_listing_ids,
                search_url=url,
            )
    if with_details:
        listing_urls = [
            raw_listing.source_url
            for bundle in bundles
            for raw_listing in bundle["listings"]
            if raw_listing.source_url
        ]
        for listing_url in listing_urls:
            detail_summary = import_centanet_listing_detail(
                session,
                url=listing_url,
                save_snapshot=save_detail_snapshots,
            )
            summary.developments_created += detail_summary.developments_created
            summary.developments_updated += detail_summary.developments_updated
            summary.documents_upserted += detail_summary.documents_upserted
            summary.listings_upserted += detail_summary.listings_upserted
            summary.transactions_upserted += detail_summary.transactions_upserted
            summary.price_events_created += detail_summary.price_events_created
            summary.snapshots_created += detail_summary.snapshots_created
    session.commit()
    return summary


def import_centanet_listing_detail(
    session: Session,
    *,
    url: str,
    html_path: str | None = None,
    save_snapshot: bool = False,
) -> ImportSummary:
    adapter = CentanetAdapter()
    html_text = Path(html_path).read_text(encoding="utf-8") if html_path else adapter.fetch_listing_detail_html(url)
    bundles = adapter.detail_listing_bundle(url=url, html_text=html_text)
    summary = _import_listing_bundles(session, adapter, bundles)
    if save_snapshot:
        summary.snapshots_created += create_text_snapshot(
            session,
            source=adapter.source_name,
            object_type="detail_page",
            object_external_id=url,
            source_url=url,
            text=html_text,
            metadata_json={
                "url": url,
                "mode": "fixture" if html_path else "live",
                "html_path": html_path,
                "listing_count": len(bundles),
            },
            parse_status=ParseStatus.PARSED,
        )
    session.commit()
    return summary


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


def backfill_centanet_listing_details(
    session: Session,
    *,
    limit: int | None = None,
    only_missing_detail: bool = True,
    save_snapshots: bool = False,
) -> ListingDetailBackfillSummary:
    adapter = CentanetAdapter()
    stmt = (
        select(Listing)
        .where(Listing.source == adapter.source_name)
        .order_by(Listing.updated_at.desc())
    )
    if limit:
        stmt = stmt.limit(limit)

    listings = session.scalars(stmt).all()
    summary = ListingDetailBackfillSummary(source=adapter.source_name, scanned=len(listings))

    for listing in listings:
        if not listing.source_url:
            summary.skipped += 1
            continue
        detail = (listing.raw_payload_json or {}).get("detail") or {}
        has_detail = any(
            detail.get(key)
            for key in ("address", "update_date", "monthly_payment_hkd", "age_years", "orientation", "description")
        )
        if only_missing_detail and has_detail:
            summary.skipped += 1
            continue
        try:
            result = import_centanet_listing_detail(
                session,
                url=listing.source_url,
                save_snapshot=save_snapshots,
            )
        except Exception:
            summary.failed += 1
            continue
        summary.enriched += 1
        summary.price_events_created += result.price_events_created
        summary.snapshots_created += result.snapshots_created

    session.commit()
    return summary


def mark_missing_centanet_listings_withdrawn(
    session: Session,
    *,
    development_external_id: str,
    current_source_listing_ids: set[str],
    search_url: str,
) -> int:
    development = session.scalar(
        select(Development).where(
            and_(
                Development.source == "centanet",
                Development.source_external_id == development_external_id,
            )
        )
    )
    if development is None:
        return 0

    listings = session.scalars(
        select(Listing).where(
            and_(
                Listing.source == "centanet",
                Listing.development_id == development.id,
                Listing.status == ListingStatus.ACTIVE,
            )
        )
    ).all()

    event_count = 0
    for listing in listings:
        if listing.source_listing_id in current_source_listing_ids:
            continue
        event_count += _set_listing_status(
            session,
            listing,
            ListingStatus.WITHDRAWN,
            {
                "reason": "missing_from_search_page",
                "search_url": search_url,
                "development_external_id": development_external_id,
            },
        )
    session.flush()
    return event_count


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
    now = datetime.now(timezone.utc)
    normalized_payload = _json_safe(payload)
    field_hash = _listing_field_hash(payload)
    listing = session.scalar(
        select(Listing).where(
            and_(
                Listing.source == payload["source"],
                Listing.source_listing_id == payload["source_listing_id"],
            )
        )
    )
    if listing is None:
        payload = {
            **payload,
            "field_hash": field_hash,
            "first_seen_at": payload.get("first_seen_at") or now,
            "last_seen_at": payload.get("last_seen_at") or now,
        }
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
            raw_payload_json=normalized_payload,
        )
        event_count += 1
    else:
        payload = {
            **payload,
            "raw_payload_json": _merge_listing_payloads(listing.raw_payload_json, payload.get("raw_payload_json")),
        }
        old_price = listing.asking_price_hkd
        old_status = listing.status.value if listing.status is not None else None
        old_hash = listing.field_hash
        for key, value in payload.items():
            setattr(listing, key, value)
        if listing.first_seen_at is None:
            listing.first_seen_at = payload.get("first_seen_at") or now
        listing.last_seen_at = payload.get("last_seen_at") or now
        listing.field_hash = field_hash
        session.flush()
        new_price = listing.asking_price_hkd
        new_status = listing.status.value if listing.status is not None else None
        if old_hash == field_hash:
            session.flush()
            return event_count
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
                raw_payload_json=normalized_payload,
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
                raw_payload_json=normalized_payload,
            )
            event_count += 1
    session.flush()
    return event_count


def _set_listing_status(
    session: Session,
    listing: Listing,
    new_status: ListingStatus,
    raw_payload_json: dict[str, Any] | None = None,
) -> int:
    old_status = listing.status.value if listing.status is not None else None
    if old_status == new_status.value:
        return 0

    old_price = listing.asking_price_hkd
    listing.status = new_status
    listing.last_seen_at = datetime.now(timezone.utc)
    listing.field_hash = _listing_field_hash(
        {
            "source": listing.source,
            "source_listing_id": listing.source_listing_id,
            "title": listing.title,
            "listing_type": listing.listing_type,
            "asking_price_hkd": listing.asking_price_hkd,
            "price_per_sqft": listing.price_per_sqft,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "saleable_area_sqft": listing.saleable_area_sqft,
            "gross_area_sqft": listing.gross_area_sqft,
            "status": new_status,
            "source_url": listing.source_url,
        }
    )
    event_type = PriceEventType.STATUS_CHANGE
    if old_status == ListingStatus.WITHDRAWN.value and new_status == ListingStatus.ACTIVE:
        event_type = PriceEventType.RELIST
    elif new_status == ListingStatus.SOLD:
        event_type = PriceEventType.SOLD
    elif new_status == ListingStatus.WITHDRAWN:
        event_type = PriceEventType.WITHDRAWN
    create_price_event(
        session,
        source=listing.source,
        event_type=event_type,
        development_id=listing.development_id,
        listing_id=listing.id,
        old_price_hkd=old_price,
        new_price_hkd=listing.asking_price_hkd,
        old_status=old_status,
        new_status=new_status.value,
        raw_payload_json=raw_payload_json,
    )
    session.flush()
    return 1


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


def create_text_snapshot(
    session: Session,
    *,
    source: str,
    object_type: str,
    object_external_id: str | None,
    source_url: str | None,
    text: str,
    metadata_json: dict[str, Any] | None = None,
    parse_status: ParseStatus = ParseStatus.PENDING,
) -> int:
    settings = get_settings()
    content_bytes = text.encode("utf-8")
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = settings.data_root / "snapshots" / source / object_type
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{timestamp}-{content_hash[:12]}.html"
    path.write_text(text, encoding="utf-8")

    session.add(
        SourceSnapshot(
            source=source,
            object_type=object_type,
            object_external_id=object_external_id,
            source_url=source_url,
            snapshot_kind=SnapshotKind.HTML,
            file_path=str(path),
            content_hash=content_hash,
            http_status=200,
            parse_status=parse_status,
            metadata_json=_json_safe(metadata_json),
        )
    )
    session.flush()
    prune_text_snapshots(
        session,
        source=source,
        object_type=object_type,
        object_external_id=object_external_id,
        keep=5,
    )
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


def _listing_field_hash(payload: dict[str, Any]) -> str:
    fields = {
        "source": payload.get("source"),
        "source_listing_id": payload.get("source_listing_id"),
        "title": payload.get("title"),
        "listing_type": str(payload.get("listing_type")),
        "asking_price_hkd": payload.get("asking_price_hkd"),
        "price_per_sqft": payload.get("price_per_sqft"),
        "bedrooms": payload.get("bedrooms"),
        "bathrooms": payload.get("bathrooms"),
        "saleable_area_sqft": payload.get("saleable_area_sqft"),
        "gross_area_sqft": payload.get("gross_area_sqft"),
        "status": str(payload.get("status")),
        "source_url": payload.get("source_url"),
    }
    encoded = repr(_json_safe(fields)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _merge_listing_payloads(
    existing_payload: dict[str, Any] | None,
    new_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if existing_payload is None:
        return new_payload
    if new_payload is None:
        return existing_payload

    merged = dict(existing_payload)
    for key, value in new_payload.items():
        if value in (None, "", [], {}):
            continue
        if key == "detail" and isinstance(value, dict):
            existing_detail = merged.get("detail")
            if isinstance(existing_detail, dict):
                merged["detail"] = {
                    **existing_detail,
                    **{sub_key: sub_value for sub_key, sub_value in value.items() if sub_value not in (None, "", [], {})},
                }
            else:
                merged["detail"] = value
            continue
        if key == "development" and isinstance(value, dict):
            existing_development = merged.get("development")
            if isinstance(existing_development, dict):
                merged["development"] = {
                    **existing_development,
                    **{
                        sub_key: sub_value
                        for sub_key, sub_value in value.items()
                        if sub_value not in (None, "", [], {})
                    },
                }
            else:
                merged["development"] = value
            continue
        merged[key] = value
    return merged


def prune_text_snapshots(
    session: Session,
    *,
    source: str,
    object_type: str,
    object_external_id: str | None,
    keep: int,
) -> None:
    if keep <= 0:
        return
    snapshots = session.scalars(
        select(SourceSnapshot)
        .where(
            and_(
                SourceSnapshot.source == source,
                SourceSnapshot.object_type == object_type,
                SourceSnapshot.object_external_id == object_external_id,
            )
        )
        .order_by(SourceSnapshot.fetched_at.desc(), SourceSnapshot.id.desc())
    ).all()
    for snapshot in snapshots[keep:]:
        if snapshot.file_path:
            path = Path(snapshot.file_path)
            if path.exists():
                path.unlink()
        session.delete(snapshot)
