import csv
from pathlib import Path
from typing import ClassVar

DATA_FILE = Path(__file__).with_name("countries.csv")


class CountryReference:
    """Loads and validates the ACCESS ALGERIA country reference dataset."""

    REQUIRED_FIELDS: ClassVar[set[str]] = {
        "country_name",
        "iso2",
        "iso3",
        "comtrade_code",
        "world_bank_code",
        "region",
        "is_target_market",
        "is_active",
    }

    BOOLEAN_FIELDS: ClassVar[set[str]] = {
        "is_target_market",
        "is_active",
    }

    VALID_BOOLEAN_VALUES: ClassVar[set[str]] = {"true", "false"}

    def __init__(self, file_path: Path = DATA_FILE):
        self.file_path = Path(file_path)
        self.countries = self._load()

    def _load(self):
        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Country dataset not found: {self.file_path}"
            )

        with self.file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if not self.REQUIRED_FIELDS.issubset(
                reader.fieldnames or []
            ):
                raise ValueError(
                    "Country dataset has missing columns."
                )

            countries = list(reader)

        self._validate(countries)
        return countries

    def _validate(self, countries):
        if not countries:
            raise ValueError("Country dataset is empty.")

        iso2_codes = set()
        iso3_codes = set()
        comtrade_codes = set()
        wb_codes = set()

        for country in countries:
            for field in self.REQUIRED_FIELDS:
                value = country.get(field)

                if value is None or not value.strip():
                    raise ValueError(
                        f"Missing value for {field} in country record."
                    )

                country[field] = value.strip()

            for field in self.BOOLEAN_FIELDS:
                value = country[field].lower()

                if value not in self.VALID_BOOLEAN_VALUES:
                    raise ValueError(
                        f"Invalid boolean value for {field}: {value}"
                    )

                country[field] = value

            iso2 = country["iso2"].upper()
            iso3 = country["iso3"].upper()

            if iso2 in iso2_codes:
                raise ValueError(f"Duplicate ISO2 code: {iso2}")

            if iso3 in iso3_codes:
                raise ValueError(f"Duplicate ISO3 code: {iso3}")

            iso2_codes.add(iso2)
            iso3_codes.add(iso3)

            comtrade = country["comtrade_code"]

            if comtrade in comtrade_codes:
                raise ValueError(
                    f"Duplicate Comtrade code: {comtrade}"
                )

            comtrade_codes.add(comtrade)

            wb_code = country["world_bank_code"].upper()

            if wb_code in wb_codes:
                raise ValueError(
                    f"Duplicate World Bank code: {wb_code}"
                )

            wb_codes.add(wb_code)

            country["iso2"] = iso2
            country["iso3"] = iso3
            country["world_bank_code"] = wb_code

    def get_by_iso3(self, iso3: str):
        code = iso3.strip().upper()

        return next(
            (
                country
                for country in self.countries
                if country["iso3"] == code
            ),
            None,
        )

    def get_by_comtrade_code(self, code: str):
        code = str(code).strip()

        return next(
            (
                country
                for country in self.countries
                if country["comtrade_code"] == code
            ),
            None,
        )

    def get_target_markets(self):
        return [
            country
            for country in self.countries
            if country["is_target_market"] == "true"
        ]

    def get_active_countries(self):
        return [
            country
            for country in self.countries
            if country["is_active"] == "true"
        ]

    def all_countries(self):
        return list(self.countries)
