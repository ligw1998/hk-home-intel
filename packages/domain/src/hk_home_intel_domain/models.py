from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from hk_home_intel_domain.enums import (
    DocumentType,
    JobRunStatus,
    ListingSegment,
    ListingStatus,
    ListingType,
    ParseStatus,
    PriceEventType,
    SnapshotKind,
    SourceConfidence,
    TransactionType,
    WatchlistStage,
)
from hk_home_intel_shared.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Development(TimestampMixin, Base):
    __tablename__ = "development"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str | None] = mapped_column(String(80))
    source_external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    name_zh: Mapped[str | None] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_translations_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    address_raw: Mapped[str | None] = mapped_column(String(500))
    address_normalized: Mapped[str | None] = mapped_column(String(500))
    address_translations_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    district: Mapped[str | None] = mapped_column(String(120))
    subdistrict: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    developer_names_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    completion_year: Mapped[int | None]
    listing_segment: Mapped[ListingSegment] = mapped_column(
        Enum(ListingSegment, native_enum=False),
        default=ListingSegment.MIXED,
        nullable=False,
    )
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_confidence: Mapped[SourceConfidence] = mapped_column(
        Enum(SourceConfidence, native_enum=False),
        default=SourceConfidence.MEDIUM,
        nullable=False,
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="development", cascade="all, delete-orphan")
    price_events: Mapped[list["PriceEvent"]] = relationship(
        back_populates="development",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="development", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="development", cascade="all, delete-orphan")
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="development",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_development_source_external", "source", "source_external_id"),
        Index("ix_development_district_segment", "district", "listing_segment"),
        Index("ix_development_name_zh", "name_zh"),
        Index("ix_development_name_en", "name_en"),
    )


class Listing(TimestampMixin, Base):
    __tablename__ = "listing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_listing_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    development_id: Mapped[str] = mapped_column(ForeignKey("development.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    title_translations_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    listing_type: Mapped[ListingType] = mapped_column(
        Enum(ListingType, native_enum=False),
        nullable=False,
    )
    asking_price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    price_per_sqft: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bedrooms: Mapped[int | None]
    bathrooms: Mapped[int | None]
    saleable_area_sqft: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    gross_area_sqft: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, native_enum=False),
        default=ListingStatus.UNKNOWN,
        nullable=False,
    )
    field_hash: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    development: Mapped[Development] = relationship(back_populates="listings")
    price_events: Mapped[list["PriceEvent"]] = relationship(back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source", "source_listing_id", name="uq_listing_source_external"),
        Index("ix_listing_development_status", "development_id", "status"),
        Index("ix_listing_type_status", "listing_type", "status"),
    )


class Transaction(TimestampMixin, Base):
    __tablename__ = "transaction"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    development_id: Mapped[str] = mapped_column(ForeignKey("development.id", ondelete="CASCADE"), nullable=False)
    transaction_date: Mapped[date | None] = mapped_column(Date)
    registration_date: Mapped[date | None] = mapped_column(Date)
    price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    price_per_sqft: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False),
        nullable=False,
    )
    doc_ref: Mapped[str | None] = mapped_column(String(255))
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    development: Mapped[Development] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("source", "source_record_id", name="uq_transaction_source_external"),
        Index("ix_transaction_development_date", "development_id", "transaction_date"),
    )


class Document(TimestampMixin, Base):
    __tablename__ = "document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    development_id: Mapped[str | None] = mapped_column(ForeignKey("development.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_doc_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_translations_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parsed_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    development: Mapped[Development | None] = relationship(back_populates="documents")

    __table_args__ = (
        UniqueConstraint("source", "source_doc_id", name="uq_document_source_external"),
        Index("ix_document_development_type", "development_id", "doc_type"),
    )


class SourceSnapshot(Base):
    __tablename__ = "source_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    snapshot_kind: Mapped[SnapshotKind] = mapped_column(
        Enum(SnapshotKind, native_enum=False),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None]
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, native_enum=False),
        default=ParseStatus.PENDING,
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (
        Index("ix_snapshot_source_object", "source", "object_type"),
        Index("ix_snapshot_fetched_at", "fetched_at"),
    )


class WatchlistItem(TimestampMixin, Base):
    __tablename__ = "watchlist_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    development_id: Mapped[str] = mapped_column(ForeignKey("development.id", ondelete="CASCADE"), nullable=False)
    decision_stage: Mapped[WatchlistStage] = mapped_column(
        Enum(WatchlistStage, native_enum=False),
        default=WatchlistStage.WATCHING,
        nullable=False,
    )
    personal_score: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    development: Mapped[Development] = relationship(back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint("development_id", name="uq_watchlist_item_development"),
        Index("ix_watchlist_stage", "decision_stage"),
    )


class RefreshJobRun(Base):
    __tablename__ = "refresh_job_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str | None] = mapped_column(String(80))
    trigger_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    status: Mapped[JobRunStatus] = mapped_column(
        Enum(JobRunStatus, native_enum=False),
        default=JobRunStatus.RUNNING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_refresh_job_run_started_at", "started_at"),
        Index("ix_refresh_job_run_job_status", "job_name", "status"),
    )


class PriceEvent(TimestampMixin, Base):
    __tablename__ = "price_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[PriceEventType] = mapped_column(
        Enum(PriceEventType, native_enum=False),
        nullable=False,
    )
    development_id: Mapped[str] = mapped_column(ForeignKey("development.id", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[str | None] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    old_price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    new_price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    old_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str | None] = mapped_column(String(40))
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    development: Mapped[Development] = relationship(back_populates="price_events")
    listing: Mapped[Listing | None] = relationship(back_populates="price_events")

    __table_args__ = (
        Index("ix_price_event_development_event_at", "development_id", "event_at"),
        Index("ix_price_event_listing_event_type", "listing_id", "event_type"),
        Index("ix_price_event_source_event_at", "source", "event_at"),
    )


class SchedulerPlanOverride(TimestampMixin, Base):
    __tablename__ = "scheduler_plan_override"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    auto_run: Mapped[bool | None] = mapped_column(Boolean)
    interval_minutes: Mapped[int | None]
    task_overrides_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_scheduler_plan_override_plan_name", "plan_name"),
    )


class SearchPreset(TimestampMixin, Base):
    __tablename__ = "search_preset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(String(60), nullable=False, default="development_map")
    note: Mapped[str | None] = mapped_column(Text)
    criteria_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("scope", "name", name="uq_search_preset_scope_name"),
        Index("ix_search_preset_scope_updated", "scope", "updated_at"),
    )


class CommercialSearchMonitor(TimestampMixin, Base):
    __tablename__ = "commercial_search_monitor"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    search_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, default="custom", server_default="custom")
    development_name_hint: Mapped[str | None] = mapped_column(String(255))
    district: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    with_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    detect_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    criteria_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "search_url", name="uq_commercial_search_monitor_source_url"),
        Index("ix_commercial_search_monitor_source_active", "source", "is_active", "updated_at"),
    )
