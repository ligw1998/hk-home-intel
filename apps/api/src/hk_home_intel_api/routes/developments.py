from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hk_home_intel_domain.enums import ListingSegment, SourceConfidence
from hk_home_intel_domain.i18n import localize_text
from hk_home_intel_domain.models import Development, Document, Listing, Transaction
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/developments", tags=["developments"])


class DevelopmentSummary(BaseModel):
    id: str
    source_url: str | None
    name_zh: str | None
    name_en: str | None
    name_translations: dict[str, str]
    display_name: str | None
    district: str | None
    subdistrict: str | None
    region: str | None
    completion_year: int | None
    listing_segment: ListingSegment
    source_confidence: SourceConfidence
    lat: float | None
    lng: float | None


class DevelopmentListResponse(BaseModel):
    items: list[DevelopmentSummary]
    total: int


class DocumentSummary(BaseModel):
    id: str
    source: str
    source_doc_id: str
    title: str
    title_translations: dict[str, str]
    display_title: str
    doc_type: str
    source_url: str | None
    published_at: str | None
    file_path: str | None
    mime_type: str | None
    content_hash: str | None


class ListingSummary(BaseModel):
    id: str
    source: str
    source_listing_id: str
    title: str | None
    title_translations: dict[str, str]
    display_title: str | None
    listing_type: str
    asking_price_hkd: float | None
    price_per_sqft: float | None
    bedrooms: int | None
    bathrooms: int | None
    saleable_area_sqft: float | None
    status: str
    source_url: str | None


class TransactionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    source_record_id: str
    transaction_date: str | None
    registration_date: str | None
    price_hkd: float | None
    price_per_sqft: float | None
    transaction_type: str
    source_url: str | None


class DevelopmentDetail(DevelopmentSummary):
    active_listing_count: int
    document_count: int
    transaction_count: int
    listings: list[ListingSummary]
    documents: list[DocumentSummary]
    transactions: list[TransactionSummary]


def _apply_filters(
    stmt,
    district: str | None,
    region: str | None,
    listing_segment: ListingSegment | None,
    has_coordinates: bool | None,
):
    if district:
        stmt = stmt.where(Development.district == district)
    if region:
        stmt = stmt.where(Development.region == region)
    if listing_segment:
        stmt = stmt.where(Development.listing_segment == listing_segment)
    if has_coordinates is True:
        stmt = stmt.where(Development.lat.is_not(None), Development.lng.is_not(None))
    return stmt


def _serialize_development(item: Development, preferred_language: str) -> DevelopmentSummary:
    name_translations = item.name_translations_json or {}
    return DevelopmentSummary(
        id=item.id,
        source_url=item.source_url,
        name_zh=item.name_zh,
        name_en=item.name_en,
        name_translations=name_translations,
        display_name=localize_text(
            name_translations,
            preferred_language,
            default=item.name_zh or item.name_en,
        ),
        district=item.district,
        subdistrict=item.subdistrict,
        region=item.region,
        completion_year=item.completion_year,
        listing_segment=item.listing_segment,
        source_confidence=item.source_confidence,
        lat=item.lat,
        lng=item.lng,
    )


def _serialize_listing(item: Listing, preferred_language: str) -> ListingSummary:
    title_translations = item.title_translations_json or {}
    return ListingSummary(
        id=item.id,
        source=item.source,
        source_listing_id=item.source_listing_id,
        title=item.title,
        title_translations=title_translations,
        display_title=localize_text(
            title_translations,
            preferred_language,
            default=item.title,
        ),
        listing_type=item.listing_type.value,
        asking_price_hkd=float(item.asking_price_hkd) if item.asking_price_hkd is not None else None,
        price_per_sqft=float(item.price_per_sqft) if item.price_per_sqft is not None else None,
        bedrooms=item.bedrooms,
        bathrooms=item.bathrooms,
        saleable_area_sqft=float(item.saleable_area_sqft) if item.saleable_area_sqft is not None else None,
        status=item.status.value,
        source_url=item.source_url,
    )


def _serialize_transaction(item: Transaction) -> TransactionSummary:
    return TransactionSummary(
        id=item.id,
        source=item.source,
        source_record_id=item.source_record_id,
        transaction_date=item.transaction_date.isoformat() if item.transaction_date else None,
        registration_date=item.registration_date.isoformat() if item.registration_date else None,
        price_hkd=float(item.price_hkd) if item.price_hkd is not None else None,
        price_per_sqft=float(item.price_per_sqft) if item.price_per_sqft is not None else None,
        transaction_type=item.transaction_type.value,
        source_url=item.source_url,
    )


def _serialize_document(item: Document, preferred_language: str) -> DocumentSummary:
    title_translations = item.title_translations_json or {}
    return DocumentSummary(
        id=item.id,
        source=item.source,
        source_doc_id=item.source_doc_id,
        title=item.title,
        title_translations=title_translations,
        display_title=localize_text(
            title_translations,
            preferred_language,
            default=item.title,
        )
        or item.title,
        doc_type=item.doc_type.value,
        source_url=item.source_url,
        published_at=item.published_at.isoformat() if item.published_at else None,
        file_path=item.file_path,
        mime_type=item.mime_type,
        content_hash=item.content_hash,
    )


@router.get("", response_model=DevelopmentListResponse)
def list_developments(
    district: str | None = None,
    region: str | None = None,
    listing_segment: ListingSegment | None = None,
    has_coordinates: bool | None = None,
    lang: str = Query(default="zh-Hant"),
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
) -> DevelopmentListResponse:
    base_stmt = select(Development)
    filtered_stmt = _apply_filters(base_stmt, district, region, listing_segment, has_coordinates)

    total = session.scalar(
        select(func.count()).select_from(
            _apply_filters(
                select(Development),
                district,
                region,
                listing_segment,
                has_coordinates,
            ).subquery()
        )
    ) or 0
    developments = session.scalars(
        filtered_stmt.order_by(Development.updated_at.desc()).offset(offset).limit(limit)
    ).all()
    return DevelopmentListResponse(items=[_serialize_development(item, lang) for item in developments], total=total)


@router.get("/{development_id}", response_model=DevelopmentDetail)
def get_development(
    development_id: str,
    lang: str = Query(default="zh-Hant"),
    session: Session = Depends(get_db_session),
) -> DevelopmentDetail:
    development = session.get(Development, development_id)
    if development is None:
        raise HTTPException(status_code=404, detail="development not found")

    listings = session.scalars(
        select(Listing)
        .where(Listing.development_id == development.id)
        .order_by(Listing.asking_price_hkd.asc().nullslast())
    ).all()
    documents = session.scalars(
        select(Document)
        .where(Document.development_id == development.id)
        .order_by(Document.published_at.desc().nullslast())
    ).all()
    transactions = session.scalars(
        select(Transaction)
        .where(Transaction.development_id == development.id)
        .order_by(Transaction.transaction_date.desc().nullslast())
    ).all()

    return DevelopmentDetail(
        **_serialize_development(development, lang).model_dump(),
        active_listing_count=sum(1 for item in listings if item.status.value == "active"),
        document_count=len(documents),
        transaction_count=len(transactions),
        listings=[_serialize_listing(item, lang) for item in listings],
        documents=[_serialize_document(item, lang) for item in documents],
        transactions=[_serialize_transaction(item) for item in transactions],
    )
