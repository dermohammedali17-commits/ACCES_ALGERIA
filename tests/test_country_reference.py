import pytest

from src.data.reference.country_reference import CountryReference


def test_country_dataset_loads():
    reference = CountryReference()
    assert len(reference.all_countries()) == 5


def test_algeria_is_target_market():
    reference = CountryReference()
    algeria = reference.get_by_iso3("DZA")

    assert algeria is not None
    assert algeria["is_target_market"].lower() == "true"


def test_comtrade_code_lookup():
    reference = CountryReference()
    algeria = reference.get_by_comtrade_code("12")

    assert algeria is not None
    assert algeria["iso3"] == "DZA"


def test_unknown_country_returns_none():
    reference = CountryReference()
    assert reference.get_by_iso3("XXX") is None


def test_duplicate_iso3_is_rejected(tmp_path):
    csv_file = tmp_path / "countries.csv"
    csv_file.write_text(
        "country_name,iso2,iso3,comtrade_code,world_bank_code,"
        "region,is_target_market,is_active\n"
        "Algeria,DZ,DZA,12,DZA,North Africa,true,true\n"
        "Test,TS,DZA,999,TST,Other,false,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate ISO3"):
        CountryReference(csv_file)