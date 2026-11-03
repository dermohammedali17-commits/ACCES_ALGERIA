import pytest

from src.scoring.engine import Confidence, OpportunityScorerB


def test_all_100():
    r = OpportunityScorerB().score(**{f"d{i}": 100 for i in range(1,10)})
    assert r.weighted_total == 100.0 and r.confidence is Confidence.HIGH

def test_all_zero():
    assert OpportunityScorerB().score(**{f"d{i}": 0 for i in range(1,10)}).weighted_total == 0

def test_exact_model_b_weights():
    r = OpportunityScorerB().score(d1=100,d2=80,d3=60,d4=40,d5=20,d6=0,d7=100,d8=100,d9=100)
    assert r.weighted_total == pytest.approx(64.0)

@pytest.mark.parametrize("count,expected", [
    (0,Confidence.LOW),(6,Confidence.LOW),(7,Confidence.MEDIUM),
    (8,Confidence.MEDIUM),(9,Confidence.HIGH)])
def test_confidence(count, expected):
    values = {f"d{i}": 50 for i in range(1,count+1)}
    assert OpportunityScorerB().score(**values).confidence is expected

def test_missing_does_not_renormalize():
    r = OpportunityScorerB().score(d1=100,d2=100,d3=100,d4=100,d5=100,d6=100,d7=100)
    assert r.weighted_total is None and r.missing_dimensions == ("d8","d9")

@pytest.mark.parametrize("value", [-1,100.1,float("nan"),float("inf"),"high"])
def test_invalid_scores(value):
    with pytest.raises(ValueError):
        OpportunityScorerB().score(d1=value)
