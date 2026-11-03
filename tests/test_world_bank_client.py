import json
from urllib.error import HTTPError

import pytest

import src.data.trade_pipeline as trade_module
from src.data.trade_pipeline import WorldBankRESTClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_default_country_code():
    client = WorldBankRESTClient()

    assert client.country_code == "DZA"


def test_custom_country_code_is_normalized():
    client = WorldBankRESTClient(country_code=" fra ")

    assert client.country_code == "FRA"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": 0},
        {"timeout": -1},
        {"retries": -1},
        {"country_code": ""},
        {"country_code": "   "},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        WorldBankRESTClient(**kwargs)


def test_fetch_builds_correct_url_and_returns_records(monkeypatch):
    captured = {}

    payload = [
        {"page": 1, "pages": 1},
        [
            {"date": "2023", "value": 100},
            {"date": "2022", "value": 90},
        ],
    ]

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = request.headers
        return FakeResponse(payload)

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)

    client = WorldBankRESTClient(
        timeout=15,
        retries=0,
        country_code="FRA",
    )

    result = client.fetch(
        "NY.GDP.MKTP.CD",
        2022,
        2023,
    )

    assert result == payload[1]
    assert "/country/FRA/indicator/NY.GDP.MKTP.CD?" in captured["url"]
    assert "date=2022%3A2023" in captured["url"]
    assert "format=json" in captured["url"]
    assert "per_page=100" in captured["url"]
    assert captured["timeout"] == 15
    assert captured["headers"]["User-agent"] == trade_module.USER_AGENT


def test_fetch_returns_empty_list_when_records_are_null(monkeypatch):
    payload = [
        {"page": 1, "pages": 0},
        None,
    ]

    monkeypatch.setattr(
        trade_module,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    client = WorldBankRESTClient(retries=0)

    assert client.fetch(
        "NY.GDP.MKTP.CD",
        2022,
        2023,
    ) == []


@pytest.mark.parametrize(
    "payload, expected_exception",
    [
        ({}, ValueError),
        ([], ValueError),
        ([{"page": 1}], ValueError),
        (["invalid", []], TypeError),
        ([{"page": 1}, {}], TypeError),
    ],
)
def test_invalid_response_structure_is_rejected(
    monkeypatch,
    payload,
    expected_exception,
):
    monkeypatch.setattr(
        trade_module,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    client = WorldBankRESTClient(retries=0)

    with pytest.raises(expected_exception):
        client.fetch(
            "NY.GDP.MKTP.CD",
            2022,
            2023,
        )


def test_invalid_year_range_is_rejected():
    client = WorldBankRESTClient()

    with pytest.raises(ValueError, match="start_year"):
        client.fetch(
            "NY.GDP.MKTP.CD",
            2024,
            2022,
        )


def test_http_500_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    delays = []

    def fake_urlopen(request, timeout):
        calls["count"] += 1

        if calls["count"] == 1:
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                {},
                None,
            )

        return FakeResponse([
            {"page": 1, "pages": 1},
            [{"date": "2023", "value": 100}],
        ])

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        trade_module.time,
        "sleep",
        lambda delay: delays.append(delay),
    )

    client = WorldBankRESTClient(retries=1)

    result = client.fetch(
        "NY.GDP.MKTP.CD",
        2023,
        2023,
    )

    assert len(result) == 1
    assert calls["count"] == 2
    assert delays == [1]


def test_http_400_does_not_retry(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1

        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            None,
        )

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        trade_module.time,
        "sleep",
        lambda delay: None,
    )

    client = WorldBankRESTClient(retries=2)

    with pytest.raises(HTTPError):
        client.fetch(
            "NY.GDP.MKTP.CD",
            2023,
            2023,
        )

    assert calls["count"] == 1
