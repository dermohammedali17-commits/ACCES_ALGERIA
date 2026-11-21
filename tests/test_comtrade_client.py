import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

import src.data.trade_pipeline as trade_module
from src.data.trade_pipeline import ComtradeRESTClient
from src.infrastructure.adapters.comtrade_adapter import ComtradeAdapter


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_preview_mode_builds_request_without_api_key(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse({"data": [{"period": "2023"}]})

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    client = ComtradeRESTClient(timeout=17, retries=0)

    records = client.fetch(12, 0, 2023, "M", commodity="8703")

    assert records == [{"period": "2023"}]
    assert client.mode == "PREVIEW"
    assert urlparse(captured["request"].full_url).path.startswith(
        "/public/v1/preview/"
    )
    assert parse_qs(urlparse(captured["request"].full_url).query) == {
        "reporterCode": ["12"],
        "partnerCode": ["0"],
        "period": ["2023"],
        "flowCode": ["M"],
        "cmdCode": ["8703"],
        "motCode": ["0"],
        "partner2Code": ["0"],
        "breakdownMode": ["classic"],
    }
    assert captured["request"].get_header("Ocp-apim-subscription-key") is None
    assert captured["request"].get_header("User-agent") == trade_module.USER_AGENT
    assert captured["timeout"] == 17


def test_api_key_selects_authenticated_endpoint(monkeypatch):
    monkeypatch.setenv("COMTRADE_API_KEY", "test-key")
    client = ComtradeRESTClient(retries=0)

    assert client.mode == "AUTHENTICATED"
    assert client.base_url == trade_module.COMTRADE_DATA_URL
    captured = {}

    def capture_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse({"data": []})

    monkeypatch.setattr(trade_module, "urlopen", capture_urlopen)
    client.fetch(12, 0, 2023, "M")

    assert captured["request"].get_header("Ocp-apim-subscription-key") == "test-key"
    assert urlparse(captured["request"].full_url).path.startswith("/data/v1/get/")


@pytest.mark.parametrize(
    "payload, expected_exception",
    [
        ([], TypeError),
        ({"data": None}, TypeError),
        ({"error": "invalid request"}, ValueError),
    ],
)
def test_invalid_comtrade_response_is_rejected(
    monkeypatch,
    payload,
    expected_exception,
):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    monkeypatch.setattr(
        trade_module,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    with pytest.raises(expected_exception):
        ComtradeRESTClient(retries=0).fetch(12, 0, 2023, "M")


def test_http_500_retries_then_succeeds(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    calls = {"count": 0}
    delays = []

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                {"Retry-After": "0"},
                None,
            )
        return FakeResponse({"data": [{"period": "2023"}]})

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        trade_module.time,
        "sleep",
        lambda delay: delays.append(delay),
    )

    records = ComtradeRESTClient(retries=1).fetch(12, 0, 2023, "M")

    assert records == [{"period": "2023"}]
    assert calls["count"] == 2
    assert delays == [0]


def test_http_400_does_not_retry(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        raise HTTPError(request.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(trade_module.time, "sleep", lambda delay: None)

    with pytest.raises(HTTPError):
        ComtradeRESTClient(retries=2).fetch(12, 0, 2023, "M")

    assert calls["count"] == 1


def test_connection_failure_retries_then_succeeds(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    calls = {"count": 0}
    delays = []

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("temporary network issue")
        return FakeResponse({"data": []})

    monkeypatch.setattr(trade_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        trade_module.time,
        "sleep",
        lambda delay: delays.append(delay),
    )

    assert ComtradeRESTClient(retries=1).fetch(12, 0, 2023, "M") == []
    assert calls["count"] == 2
    assert delays == [1]


@pytest.mark.parametrize(
    "retry_after, expected",
    [
        ("120", 60),
        ("-5", 0),
        ("not-a-date", 4),
    ],
)
def test_retry_delay_handles_numeric_and_invalid_values(
    retry_after,
    expected,
):
    assert trade_module._retry_delay(2, retry_after) == expected


def test_retry_delay_handles_http_date(monkeypatch):
    fixed_now = datetime(2025, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(trade_module, "utc_now", lambda: fixed_now)

    assert trade_module._retry_delay(
        0,
        "Wed, 01 Jan 2025 00:00:10 GMT",
    ) == 10


def test_mie_adapter_diagnostics_cover_data_empty_and_error_states(tmp_path):
    data = pd.DataFrame([{"refYear": 2023, "cmdCode": "8703", "primaryValue": 10}])
    data.attrs.update(http_status=200, totalRecords=1, page=1, pages=1)
    adapter = ComtradeAdapter(lambda **params: data, cache_dir=tmp_path,
                              min_interval_s=0, max_retries=1, use_cache=False)
    result = adapter.fetch_flows("12", "M", [2023], ["8703", "8704"], "0")
    assert len(result) == 1
    assert adapter.last_diagnostics["http_status"] == 200
    assert adapter.last_diagnostics["total_count"] == 1
    assert adapter.last_diagnostics["parameters"]["reporterCode"] == "12"
    assert adapter.last_diagnostics["parameters"]["partnerCode"] == "0"
    assert adapter.last_diagnostics["parameters"]["flowCode"] == "M"
    assert adapter.last_diagnostics["parameters"]["cmdCode"] == "8703,8704"
    assert adapter.last_diagnostics["parameters"]["period"] == "2023"

    empty = pd.DataFrame()
    empty.attrs.update(http_status=200, total_count=0)
    empty_adapter = ComtradeAdapter(lambda **params: empty, cache_dir=tmp_path,
                                    min_interval_s=0, max_retries=1, use_cache=False)
    assert empty_adapter.fetch_flows("12", "M", [2023], ["8703", "8704"], "0").empty
    assert empty_adapter.last_diagnostics["total_count"] == 0

    def api_error(**params):
        exc = ValueError("provider rejected request")
        exc.code = 400
        exc.payload = {"error": "bad query", "api_key": "never persist"}
        raise exc

    error_adapter = ComtradeAdapter(api_error, cache_dir=tmp_path, min_interval_s=0,
                                    max_retries=1, use_cache=False)
    with pytest.raises(RuntimeError, match="ValueError"):
        error_adapter.fetch_flows("12", "M", [2023], ["8703", "8704"], "0")
    assert error_adapter.last_diagnostics["http_status"] == 400
    assert "never persist" not in str(error_adapter.last_diagnostics)
    assert "REDACTED" in str(error_adapter.last_diagnostics["provider_error"])

    transport_adapter = ComtradeAdapter(
        lambda **params: (_ for _ in ()).throw(URLError("connection refused")),
        cache_dir=tmp_path, min_interval_s=0, max_retries=1, use_cache=False,
    )
    with pytest.raises(RuntimeError, match="URLError"):
        transport_adapter.fetch_flows("12", "M", [2023], ["8703", "8704"], "0")
    assert transport_adapter.last_diagnostics["response"] == "ERROR"
    assert transport_adapter.last_diagnostics["error_type"] == "URLError"


def test_mie_adapter_preserves_each_preview_years_pagination_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)

    def fetch(**params):
        frame = pd.DataFrame([{"period": params["period"], "primaryValue": 1}])
        frame.attrs.update(http_status=200, total_count=int(params["period"]),
                           page=1, pages=int(params["period"]) - 2020)
        return frame

    adapter = ComtradeAdapter(fetch, cache_dir=tmp_path, min_interval_s=0,
                              max_retries=1, use_cache=False)
    frame = adapter.fetch_flows("12", "M", [2021, 2022], ["8703", "8704"], "0")
    requests = adapter.last_diagnostics["requests"]
    assert len(frame) == 2
    assert [item["parameters"]["period"] for item in requests] == ["2021", "2022"]
    assert [item["total_count"] for item in requests] == [2021, 2022]
    assert [item["pages"] for item in requests] == [1, 2]
