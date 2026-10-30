"""Unit tests for Model B. Expected values are hand-calculated (spreadsheet-style benchmarks)."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.scoring.opportunity_scorer_b import (
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    Confidence,
    DimensionInput,
    OpportunityInput,
    Priority,
    classify_priority,
    score_from_dict,
    score_opportunity,
    validate_weights,
)

ROOT = Path(__file__).resolve().parents[1]


def all_dims(value: float) -> dict:
    return {d: value for d in DIMENSIONS}


# --- framework integrity ---------------------------------------------------


def test_weights_sum_to_one_and_cover_nine_dimensions():
    assert len(DIMENSIONS) == 9
    validate_weights(DEFAULT_WEIGHTS)
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_default_weights_match_repository_methodology_document():
    """Guards against drift between code and 04_OPPORTUNITY_SCORING/SCORING_METHODOLOGY.md."""
    text = (ROOT / "04_OPPORTUNITY_SCORING" / "SCORING_METHODOLOGY.md").read_text(encoding="utf-8")
    doc_weights = [int(m) for m in re.findall(r"^## [A-I]\. .*?— (\d+)%", text, flags=re.M)]
    assert doc_weights == [round(DEFAULT_WEIGHTS[d] * 100) for d in DIMENSIONS]


def test_invalid_weights_rejected():
    bad = dict(DEFAULT_WEIGHTS, market_attractiveness=0.5)
    with pytest.raises(ValueError):
        validate_weights(bad)
    with pytest.raises(ValueError):
        validate_weights({"market_attractiveness": 1.0})


# --- score arithmetic ------------------------------------------------------


def test_all_tens_is_100():
    r = score_from_dict("x", all_dims(10), Confidence.HIGH)
    assert r.score == 100.0
    assert r.priority == Priority.A
    assert r.confidence == Confidence.HIGH
    assert r.missing == []


def test_all_fives_is_50_watchlist():
    r = score_from_dict("x", all_dims(5))
    assert r.score == 50.0
    assert r.priority == Priority.WATCHLIST


def test_hand_calculated_benchmark():
    # 0.20*8 + 0.15*7 + 0.15*9 + 0.10*6 + 0.15*5 + 0.05*4 + 0.10*7 + 0.05*8 + 0.05*6 = 6.95 -> 69.5
    scores = dict(
        market_attractiveness=8, brand_market_fit=7, demand_potential=9,
        competitive_gap=6, regulatory_feasibility=5, entry_complexity=4,
        partner_availability=7, economic_potential=8, strategic_timing=6,
    )
    r = score_from_dict("benchmark", scores)
    assert r.score == pytest.approx(69.5)
    assert r.priority == Priority.C  # 69.5 is below the B band (70)
    assert r.breakdown["market_attractiveness"] == pytest.approx(16.0)
    assert sum(r.breakdown.values()) == pytest.approx(69.5)


def test_deterministic_same_input_same_output():
    a = score_from_dict("x", all_dims(7))
    b = score_from_dict("x", all_dims(7))
    assert a == b


# --- priority bands --------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (100, Priority.A), (85, Priority.A), (84.99, Priority.B),
        (70, Priority.B), (69.99, Priority.C), (55, Priority.C),
        (54.99, Priority.WATCHLIST), (40, Priority.WATCHLIST),
        (39.99, Priority.LOW_PRIORITY), (0, Priority.LOW_PRIORITY),
    ],
)
def test_priority_bands(score, expected):
    assert classify_priority(score) == expected


# --- missing evidence / confidence ----------------------------------------


def test_missing_dimensions_are_not_invented():
    opp = OpportunityInput(
        name="partial",
        dimensions={"market_attractiveness": DimensionInput(score=10, reliability=Confidence.HIGH)},
    )
    r = score_opportunity(opp)
    assert r.score == 20.0            # only A (20%) counted, rest 0
    assert r.score_max == 100.0       # if all missing dims were 10
    assert r.coverage == pytest.approx(0.2)
    assert len(r.missing) == 8
    assert r.confidence == Confidence.LOW  # >25% of weight missing
    assert "INCOMPLETE_EVIDENCE" in r.flags


def test_none_score_counts_as_missing():
    dims = {d: DimensionInput(score=8, reliability=Confidence.HIGH) for d in DIMENSIONS}
    dims["partner_availability"] = DimensionInput(score=None)
    r = score_opportunity(OpportunityInput(name="x", dimensions=dims))
    assert r.missing == ["partner_availability"]
    assert r.coverage == pytest.approx(0.9)
    assert r.score == pytest.approx(72.0)       # 80 * 0.9
    assert r.score_max == pytest.approx(82.0)   # 72 + 0.10*10*10
    assert r.confidence == Confidence.HIGH      # missing weight 10% <= 25%, index 0.9


@pytest.mark.parametrize(
    "reliability,expected",
    [(Confidence.HIGH, Confidence.HIGH), (Confidence.MEDIUM, Confidence.MEDIUM),
     (Confidence.LOW, Confidence.LOW)],
)
def test_confidence_follows_evidence_reliability(reliability, expected):
    assert score_from_dict("x", all_dims(6), reliability).confidence == expected


def test_high_score_with_low_confidence_requires_validation():
    r = score_from_dict("hype", all_dims(9), Confidence.LOW)
    assert r.priority == Priority.A
    assert r.confidence == Confidence.LOW
    assert "REQUIRES_VALIDATION" in r.flags


def test_high_score_with_high_confidence_has_no_validation_flag():
    r = score_from_dict("solid", all_dims(9), Confidence.HIGH)
    assert "REQUIRES_VALIDATION" not in r.flags


def test_extreme_score_without_reason_is_flagged():
    dims = {d: DimensionInput(score=5, reliability=Confidence.HIGH) for d in DIMENSIONS}
    dims["demand_potential"] = DimensionInput(score=10, reliability=Confidence.HIGH)
    r = score_opportunity(OpportunityInput(name="x", dimensions=dims))
    assert "REASON_REQUIRED:demand_potential" in r.flags
    dims["demand_potential"] = DimensionInput(score=10, reliability=Confidence.HIGH,
                                              reason="Verified registrations data")
    r2 = score_opportunity(OpportunityInput(name="x", dimensions=dims))
    assert "REASON_REQUIRED:demand_potential" not in r2.flags


# --- input validation ------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.1, 10.1, 11, -5])
def test_score_out_of_range_rejected(bad):
    with pytest.raises(ValidationError):
        DimensionInput(score=bad)


def test_unknown_dimension_rejected():
    with pytest.raises(ValidationError):
        OpportunityInput(name="x", dimensions={"vibes": DimensionInput(score=5)})
