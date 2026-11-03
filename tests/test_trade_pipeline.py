import pandas as pd
import pytest

from src.data.reference.country_reference import CountryReference
from src.data.trade_pipeline import (
    TradeMacroPipeline,
    audit_trade_duplicates,
)


class FakeComtradeClient:
    mode = "PREVIEW"

    def __init__(self, responses=None, failures=None):
        self.responses = responses or {}
        self.failures = failures or {}

    def fetch(self, reporter, partner, year, flow, commodity="87"):
        key = (reporter, partner, year, flow)

        if key in self.failures:
            raise TimeoutError("Simulated connection failure")

        return self.responses.get(key, [])


class FakeWorldBankClient:
    def __init__(self, responses=None, failures=None):
        self.responses = responses or {}
        self.failures = failures or {}

    def fetch(self, indicator, start_year, end_year):
        if indicator in self.failures:
            raise ConnectionError("Simulated World Bank failure")

        return self.responses.get(indicator, [])


@pytest.fixture
def trade_row():
    return {
        "reporterCode": 156,
        "partnerCode": 12,
        "period": 2023,
        "flowCode": "X",
        "cmdCode": "87",
        "primaryValue": 1000000,
        "netWgt": 500,
        "reporterDesc": "China",
        "partnerDesc": "Algeria",
    }


def test_direct_import_success(trade_row, monkeypatch):
    monkeypatch.setattr(
        "src.data.trade_pipeline.time.sleep",
        lambda _: None
    )

    direct_row = {
        **trade_row,
        "reporterCode": 12,
        "partnerCode": 0,
        "flowCode": "M",
    }
    client = FakeComtradeClient({
        (12, 0, 2023, "M"): [direct_row]
    })

    pipeline = TradeMacroPipeline(client=client)

    df, report = pipeline.fetch_trade_with_report([2023])

    assert len(df) == 1
    assert df.iloc[0]["is_mirror_estimate"] == False
    assert report["status"] == "SUCCESS"
    assert report["retrieved_years"] == [2023]
    assert df.iloc[0]["source_url"].startswith("https://comtradeapi.un.org/")


def test_direct_import_keeps_valid_rows_when_one_is_invalid(monkeypatch):
    monkeypatch.setattr("src.data.trade_pipeline.time.sleep", lambda _: None)
    good_row = {
        "reporterCode": 12,
        "partnerCode": 0,
        "period": 2023,
        "flowCode": "M",
        "cmdCode": "87",
        "primaryValue": 100,
    }
    bad_row = {**good_row, "reporterCode": 156}
    client = FakeComtradeClient({(12, 0, 2023, "M"): [good_row, bad_row]})

    dataframe, report = TradeMacroPipeline(client=client).fetch_trade_with_report([2023])

    assert len(dataframe) == 1
    assert report["years"][0]["status"] == "PARTIAL"
    assert report["years"][0]["rejected_records"] == 1


def test_mirror_estimate_fallback(trade_row, monkeypatch):
    monkeypatch.setattr(
        "src.data.trade_pipeline.time.sleep",
        lambda _: None
    )

    client = FakeComtradeClient({
        (156, 12, 2023, "X"): [trade_row]
    })

    pipeline = TradeMacroPipeline(client=client)

    df, report = pipeline.fetch_trade_with_report([2023])

    assert len(df) == 1
    assert df.iloc[0]["is_mirror_estimate"] == True
    assert report["status"] == "PARTIAL"
    assert report["years"][0]["source_type"] == "MIRROR_ESTIMATE"


def test_mirror_query_uses_configured_target_country_code(tmp_path, monkeypatch):
    monkeypatch.setattr("src.data.trade_pipeline.time.sleep", lambda _: None)
    countries_file = tmp_path / "countries.csv"
    countries_file.write_text(
        "country_name,iso2,iso3,comtrade_code,world_bank_code,region,"
        "is_target_market,is_active\n"
        "France,FR,FRA,251,FRA,Europe,true,true\n"
        "China,CN,CHN,156,CHN,Asia,false,true\n",
        encoding="utf-8",
    )
    france_row = {
        "reporterCode": 156,
        "partnerCode": 251,
        "period": 2023,
        "flowCode": "X",
        "cmdCode": "87",
        "primaryValue": 100,
    }
    client = FakeComtradeClient({(156, 251, 2023, "X"): [france_row]})
    pipeline = TradeMacroPipeline(
        client=client,
        country_reference=CountryReference(countries_file),
    )

    dataframe, report = pipeline.fetch_trade_with_report([2023])

    assert len(dataframe) == 1
    assert int(dataframe.iloc[0]["partner_code"]) == 251
    assert report["years"][0]["source_type"] == "MIRROR_ESTIMATE"


def test_trade_failure_report(monkeypatch):
    monkeypatch.setattr(
        "src.data.trade_pipeline.time.sleep",
        lambda _: None
    )

    client = FakeComtradeClient(
        failures={
            (12, 0, 2023, "M"): True,
            (156, 12, 2023, "X"): True,
            (792, 12, 2023, "X"): True,
            (251, 12, 2023, "X"): True,
            (276, 12, 2023, "X"): True,
        }
    )

    pipeline = TradeMacroPipeline(client=client)

    df, report = pipeline.fetch_trade_with_report([2023])

    assert df.empty
    assert report["status"] == "FAILED"
    assert report["missing_years"] == [2023]


def test_world_bank_success():
    responses = {
        "NY.GDP.MKTP.CD": [
            {"date": "2023", "value": 100.5},
            {"date": "2022", "value": 90.5},
        ]
    }

    client = FakeWorldBankClient(responses=responses)

    pipeline = TradeMacroPipeline(world_bank_client=client)

    df, report = pipeline.fetch_macro_with_report(2022, 2023)

    assert len(df) == 2
    assert report["indicators"][0]["status"] == "SUCCESS"
    assert df.iloc[0]["source_url"].startswith("https://api.worldbank.org/v2/country/DZA/")


def test_world_bank_missing_year():
    responses = {
        "NY.GDP.MKTP.CD": [
            {"date": "2023", "value": 100.5},
        ]
    }

    client = FakeWorldBankClient(responses=responses)

    pipeline = TradeMacroPipeline(world_bank_client=client)

    _, report = pipeline.fetch_macro_with_report(2022, 2023)

    indicator = report["indicators"][0]

    assert indicator["status"] == "PARTIAL"
    assert indicator["missing_years"] == [2022]


def test_world_bank_null_observation():
    responses = {
        "NY.GDP.MKTP.CD": [
            {"date": "2023", "value": None},
            {"date": "2022", "value": 90.5},
        ]
    }

    client = FakeWorldBankClient(responses=responses)

    pipeline = TradeMacroPipeline(world_bank_client=client)

    df, report = pipeline.fetch_macro_with_report(2022, 2023)

    assert len(df) == 1
    assert report["indicators"][0]["missing_years"] == [2023]


def test_world_bank_connection_failure():
    client = FakeWorldBankClient(
        failures={"NY.GDP.MKTP.CD": True}
    )

    pipeline = TradeMacroPipeline(world_bank_client=client)

    _, report = pipeline.fetch_macro_with_report(2022, 2023)

    assert report["indicators"][0]["status"] == "FAILED"


def test_invalid_year_range():
    pipeline = TradeMacroPipeline(
        world_bank_client=FakeWorldBankClient()
    )

    with pytest.raises(ValueError):
        pipeline.fetch_macro_with_report(2024, 2020)

def test_invalid_direct_record_falls_back_to_mirror(monkeypatch):
    monkeypatch.setattr(
        "src.data.trade_pipeline.time.sleep",
        lambda _: None
    )

    invalid_direct_row = {
        "reporterCode": "INVALID",
        "partnerCode": 12,
        "period": 2023,
        "flowCode": "M",
        "cmdCode": "87",
        "primaryValue": 1000000,
    }

    valid_mirror_row = {
        "reporterCode": 156,
        "partnerCode": 12,
        "period": 2023,
        "flowCode": "X",
        "cmdCode": "87",
        "primaryValue": 2000000,
    }

    client = FakeComtradeClient({
        (12, 0, 2023, "M"): [invalid_direct_row],
        (156, 12, 2023, "X"): [valid_mirror_row],
    })

    pipeline = TradeMacroPipeline(client=client)

    df, report = pipeline.fetch_trade_with_report([2023])

    assert len(df) == 1
    assert bool(df.iloc[0]["is_mirror_estimate"]) is True
    assert report["status"] == "PARTIAL"
    assert report["years"][0]["source_type"] == "MIRROR_ESTIMATE"

def test_mirror_keeps_valid_records_when_one_record_is_invalid(monkeypatch):
    monkeypatch.setattr(
        "src.data.trade_pipeline.time.sleep",
        lambda _: None
    )

    valid_mirror_row = {
        "reporterCode": 156,
        "partnerCode": 12,
        "period": 2023,
        "flowCode": "X",
        "cmdCode": "87",
        "primaryValue": 2000000,
    }

    invalid_mirror_row = {
        "reporterCode": "INVALID",
        "partnerCode": 12,
        "period": 2023,
        "flowCode": "X",
        "cmdCode": "87",
        "primaryValue": 1000000,
    }

    client = FakeComtradeClient({
        (12, 0, 2023, "M"): [],
        (156, 12, 2023, "X"): [
            valid_mirror_row,
            invalid_mirror_row,
        ],
    })

    pipeline = TradeMacroPipeline(client=client)

    df, report = pipeline.fetch_trade_with_report([2023])

    year_report = report["years"][0]

    assert len(df) == 1
    assert bool(df.iloc[0]["is_mirror_estimate"]) is True
    assert year_report["status"] == "PARTIAL"
    assert year_report["records"] == 1
    assert year_report["rejected_records"] == 1
    assert len(year_report["mirror_errors"]) == 1


def test_duplicate_audit_detects_exact_duplicates(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())
    record = pipeline._normalize(trade_row, mirror=False).model_dump()

    dataframe = pd.DataFrame([record, record.copy()])
    report = audit_trade_duplicates(dataframe)

    assert report["total_records"] == 2
    assert report["exact_duplicate_groups"] == 1
    assert report["exact_duplicate_records"] == 1
    assert report["direct_duplicates"] == 1
    assert report["mirror_duplicates"] == 0


def test_duplicate_audit_detects_dimensional_collisions(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())
    first = pipeline._normalize(trade_row, mirror=False).model_dump()

    second = first.copy()
    second["trade_value_usd"] = 2500000

    report = audit_trade_duplicates(pd.DataFrame([first, second]))

    assert report["exact_duplicate_groups"] == 0
    assert report["dimensional_collision_groups"] == 1
    assert report["exact_duplicate_records"] == 0


def test_duplicate_audit_respects_record_provenance(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())
    first = pipeline._normalize(trade_row, mirror=False).model_dump()
    second = first.copy()
    second["source"] = "Different UN Comtrade endpoint"

    report = audit_trade_duplicates(pd.DataFrame([first, second]))

    assert report["exact_duplicate_groups"] == 0
    assert report["dimensional_collision_groups"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "not-a-number"])
def test_trade_record_rejects_non_finite_values(trade_row, value):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())
    row = {**trade_row, "primaryValue": value}

    with pytest.raises(ValueError, match="finite number"):
        pipeline._normalize(row, mirror=True)


def test_trade_normalization_rejects_query_mismatch(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())

    with pytest.raises(ValueError, match="reporterCode"):
        pipeline._normalize(
            trade_row,
            mirror=False,
            expected_reporter=12,
            expected_partner=0,
            expected_period=2023,
            expected_flow="M",
        )


def test_duplicate_audit_separates_direct_and_mirror(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())

    direct = pipeline._normalize(trade_row, mirror=False).model_dump()
    mirror = pipeline._normalize(trade_row, mirror=True).model_dump()

    report = audit_trade_duplicates(pd.DataFrame([direct, mirror]))

    assert report["exact_duplicate_groups"] == 0
    assert report["cross_source_match_groups"] == 1
    assert report["exact_duplicate_records"] == 0


def test_duplicate_audit_does_not_modify_dataframe(trade_row):
    pipeline = TradeMacroPipeline(client=FakeComtradeClient())
    record = pipeline._normalize(trade_row, mirror=False).model_dump()

    dataframe = pd.DataFrame([record, record.copy()])
    original = dataframe.copy(deep=True)

    audit_trade_duplicates(dataframe)

    pd.testing.assert_frame_equal(dataframe, original)


def test_duplicate_audit_empty_dataframe():
    report = audit_trade_duplicates(pd.DataFrame())

    assert report["total_records"] == 0
    assert report["exact_duplicate_groups"] == 0
    assert report["exact_duplicate_records"] == 0


def test_duplicate_audit_rejects_unknown_source_classification():
    dataframe = pd.DataFrame([{
        "reporter_code": 1,
        "partner_code": 2,
        "period": "2023",
        "flow_code": "M",
        "commodity_code": "87",
        "trade_value_usd": 1,
        "fob_value_usd": None,
        "cif_value_usd": None,
        "net_weight_kg": None,
        "is_mirror_estimate": None,
        "is_reported": True,
        "is_aggregate": False,
    }])

    with pytest.raises(ValueError, match="boolean values"):
        audit_trade_duplicates(dataframe)


def test_duplicate_audit_rejects_string_source_classification():
    dataframe = pd.DataFrame([{
        "reporter_code": 1,
        "partner_code": 2,
        "period": "2023",
        "flow_code": "M",
        "commodity_code": "87",
        "trade_value_usd": 1,
        "fob_value_usd": None,
        "cif_value_usd": None,
        "net_weight_kg": None,
        "is_mirror_estimate": "False",
        "is_reported": True,
        "is_aggregate": False,
    }])

    with pytest.raises(ValueError, match="boolean values"):
        audit_trade_duplicates(dataframe)
