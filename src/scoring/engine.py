from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

WEIGHTS = {
    "d1": Decimal("0.20"), "d2": Decimal("0.15"), "d3": Decimal("0.15"),
    "d4": Decimal("0.15"), "d5": Decimal("0.10"), "d6": Decimal("0.10"),
    "d7": Decimal("0.05"), "d8": Decimal("0.05"), "d9": Decimal("0.05"),
}

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

@dataclass(frozen=True)
class ScoringResult:
    weighted_total: float | None
    confidence: Confidence
    supplied_dimensions: int
    missing_dimensions: tuple[str, ...]
    is_complete: bool

class OpportunityScorerB:
    """Deterministic Model B scorer. Confidence measures completeness only."""
    def score(self, *, d1=None, d2=None, d3=None, d4=None, d5=None,
              d6=None, d7=None, d8=None, d9=None) -> ScoringResult:
        values = {f"d{i}": v for i, v in enumerate(
            [d1,d2,d3,d4,d5,d6,d7,d8,d9], start=1)}
        valid = {}
        missing = []
        for key, value in values.items():
            if value is None:
                missing.append(key)
                continue
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
            if not number.is_finite() or not Decimal(0) <= number <= Decimal(100):
                raise ValueError(f"{key} must be between 0 and 100")
            valid[key] = number
        count = len(valid)
        confidence = Confidence.HIGH if count == 9 else (
            Confidence.MEDIUM if count >= 7 else Confidence.LOW)
        total = None
        if count == 9:
            total = float(sum(valid[k] * WEIGHTS[k] for k in WEIGHTS))
        return ScoringResult(total, confidence, count, tuple(missing), count == 9)
