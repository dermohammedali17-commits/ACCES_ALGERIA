"""Data models for P09 Sector Intelligence Engine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SectorCategory(str, Enum):
    LUXURY_AUTOMOTIVE = "LUXURY_AUTOMOTIVE"
    COMMERCIAL_VEHICLES = "COMMERCIAL_VEHICLES"
    AUTOMOTIVE_PARTS_AFTERMARKET = "AUTOMOTIVE_PARTS_AFTERMARKET"
    TOURISM_HOSPITALITY = "TOURISM_HOSPITALITY"
    RENEWABLE_ENERGY = "RENEWABLE_ENERGY"
    INDUSTRIAL_MANUFACTURING = "INDUSTRIAL_MANUFACTURING"


class MarketMaturityLevel(str, Enum):
    EMERGING = "EMERGING"
    REGULATED_TRANSITION = "REGULATED_TRANSITION"
    GROWTH = "GROWTH"
    SATURATED = "SATURATED"


class SectorProfile(BaseModel):
    """Structured macroeconomic and structural profile of an Algerian target sector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sector_id: str = Field(min_length=1)
    category: SectorCategory
    name: str = Field(min_length=1)
    maturity: MarketMaturityLevel
    estimated_market_size_usd: float | None = Field(default=None, ge=0.0)
    annual_growth_rate_pct: float | None = Field(default=None)
    local_content_requirement_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    provenance_reference: str = Field(min_length=1)
