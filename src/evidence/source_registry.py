"""P07 Source Registry for ACCESS ALGERIA.

Defines programmatic metadata and verification standards for official government
sources, international economic institutions, trade databases, and statistical publishers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceCategory(str, Enum):
    OFFICIAL_GOVERNMENT = "OFFICIAL_GOVERNMENT"
    INTERNATIONAL_ECONOMIC = "INTERNATIONAL_ECONOMIC"
    TRADE_DATABASE = "TRADE_DATABASE"
    STATISTICAL_INSTITUTION = "STATISTICAL_INSTITUTION"
    INDUSTRY_REPORT = "INDUSTRY_REPORT"
    COMPANY_DISCLOSURE = "COMPANY_DISCLOSURE"
    MARKET_RESEARCH = "MARKET_RESEARCH"


class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class SourceMetadataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    category: SourceCategory
    publisher: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    data_domain: str = Field(min_length=1)
    publication_date: str | None = None
    last_verification_date: str
    status: SourceStatus = SourceStatus.ACTIVE
    license_conditions: str = Field(default="Public / Restricted Access")


class SourceRegistry:
    """Registry maintaining verified intelligence sources for Access Algeria."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceMetadataRecord] = {}
        self._register_default_sources()

    def _register_default_sources(self) -> None:
        defaults = [
            SourceMetadataRecord(
                source_id="COMTRADE_API",
                source_name="UN Comtrade Database",
                category=SourceCategory.TRADE_DATABASE,
                publisher="United Nations Statistics Division",
                official_url="https://comtradeapi.un.org",
                geography="GLOBAL",
                data_domain="International Merchandise Trade",
                last_verification_date=datetime.now(UTC).date().isoformat(),
                status=SourceStatus.ACTIVE,
                license_conditions="UN Comtrade Terms of Service",
            ),
            SourceMetadataRecord(
                source_id="WORLD_BANK_WDI",
                source_name="World Bank World Development Indicators",
                category=SourceCategory.INTERNATIONAL_ECONOMIC,
                publisher="The World Bank",
                official_url="https://api.worldbank.org",
                geography="GLOBAL",
                data_domain="Macroeconomic and Development Indicators",
                last_verification_date=datetime.now(UTC).date().isoformat(),
                status=SourceStatus.ACTIVE,
                license_conditions="World Bank Open Data License",
            ),
        ]
        for src in defaults:
            self._sources[src.source_id] = src

    def get_source(self, source_id: str) -> SourceMetadataRecord | None:
        return self._sources.get(source_id)

    def register_source(self, record: SourceMetadataRecord) -> None:
        self._sources[record.source_id] = record

    @property
    def registered_sources(self) -> tuple[SourceMetadataRecord, ...]:
        return tuple(self._sources.values())
