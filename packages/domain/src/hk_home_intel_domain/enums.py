from enum import StrEnum


class ListingSegment(StrEnum):
    NEW = "new"
    FIRST_HAND_REMAINING = "first_hand_remaining"
    SECOND_HAND = "second_hand"
    MIXED = "mixed"


class SourceConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ListingType(StrEnum):
    NEW = "new"
    FIRST_HAND_REMAINING = "first_hand_remaining"
    SECOND_HAND = "second_hand"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class PriceEventType(StrEnum):
    NEW_LISTING = "new_listing"
    PRICE_DROP = "price_drop"
    PRICE_RAISE = "price_raise"
    STATUS_CHANGE = "status_change"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    RELIST = "relist"


class TransactionType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class WatchlistStage(StrEnum):
    WATCHING = "watching"
    SHORTLISTED = "shortlisted"
    VISIT_PLANNED = "visit_planned"
    NEGOTIATING = "negotiating"
    PASSED = "passed"


class JobRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DocumentType(StrEnum):
    BROCHURE = "brochure"
    PRICE_LIST = "price_list"
    SALES_ARRANGEMENT = "sales_arrangement"
    TRANSACTION_RECORD = "transaction_record"
    FLOOR_PLAN = "floor_plan"
    OTHER = "other"


class SnapshotKind(StrEnum):
    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    IMAGE = "image"


class ParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
