from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawRecord:
    source: str
    external_id: str
    payload: dict[str, Any]
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def discover_developments(self) -> list[RawRecord]:
        raise NotImplementedError

    @abstractmethod
    def discover_documents(self) -> list[RawRecord]:
        raise NotImplementedError

    def discover_listings(self) -> list[RawRecord]:
        return []

    def discover_transactions(self) -> list[RawRecord]:
        return []

    @abstractmethod
    def normalize_development(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def normalize_document(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError

    def normalize_listing(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError

    def normalize_transaction(self, record: RawRecord) -> dict[str, Any]:
        raise NotImplementedError
