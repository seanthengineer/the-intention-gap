"""Publication checks for the descriptively mapped M10 panel."""

import unittest

from analysis import acs_housing, cdc_natality
from tools import m10_geography as atlas


class GeographyExportTests(unittest.TestCase):
    def test_published_keys_and_frozen_summary(self) -> None:
        rows = atlas.read_public()
        atlas.validate_public(rows)
        self.assertEqual(len(rows), 510)
        self.assertEqual(len({(row["state_fips"], row["year"]) for row in rows}), 510)
        self.assertEqual(len({row["state_fips"] for row in rows}), 51)
        self.assertEqual({row["year"] for row in rows}, {
            "2014", "2015", "2016", "2017", "2018", "2019", "2021", "2022", "2023", "2024",
        })
        self.assertTrue(all(row["birth_rate_20_24"] and row["birth_rate_25_29"] for row in rows))
        self.assertEqual(set(rows[0]), {
            "state_fips", "state_name", "year", "burden30_pct", "severe50_pct",
            "birth_rate_20_24", "birth_rate_25_29",
        })

    def test_rejects_duplicate_and_non_state_fips(self) -> None:
        rows = atlas.read_public()
        with self.assertRaisesRegex(ValueError, "50 states and DC"):
            atlas.validate_public(rows[:-1] + [rows[0]])
        rows[0]["state_fips"] = "72"
        with self.assertRaisesRegex(ValueError, "50 states and DC"):
            atlas.validate_public(rows)

    def test_rejects_a_rate_discrepant_with_frozen_summary(self) -> None:
        rows = atlas.read_public()
        rows[0]["birth_rate_20_24"] = "57.123"
        with self.assertRaisesRegex(ValueError, "frozen annual summary"):
            atlas.validate_public(rows)

    def test_does_not_publish_suppressed_or_small_cell_rates(self) -> None:
        source = {
            "births": "10", "births_status": "value", "female_population": "300",
            "female_population_status": "value", "rate_exported": "33.333",
            "rate_exported_status": "value",
        }
        self.assertEqual(atlas.publishable_rate(source), "33.333")
        for field in ("births_status", "female_population_status", "rate_exported_status"):
            with self.subTest(field=field):
                self.assertEqual(atlas.publishable_rate({**source, field: "Suppressed"}), "")
        self.assertEqual(atlas.publishable_rate({**source, "births": "9", "rate_exported": "30"}), "")
        with self.assertRaisesRegex(ValueError, "source counts"):
            atlas.publishable_rate({**source, "rate_exported": "99"})

    @unittest.skipUnless(
        (atlas.PROCESSED / "m10_panel_state_year_age.csv").is_file(),
        "local M10 panel not available in a source-only checkout",
    )
    def test_rebuild_matches_local_panel(self) -> None:
        self.assertEqual(atlas.derive(), atlas.read_public())

    @unittest.skipUnless(
        all(acs_housing.raw_path(year, "data").is_file() for year in acs_housing.YEARS)
        and all(source["path"].is_file() for source in cdc_natality.SOURCES.values()),
        "original source responses not available in a source-only checkout",
    )
    def test_published_values_match_saved_official_sources(self) -> None:
        housing, housing_report = acs_housing.build()
        natality, natality_report = cdc_natality.build()
        self.assertEqual(acs_housing.status(housing_report), "PASS")
        self.assertEqual(natality_report["status"], "PASS")
        published = {(row["state_fips"], int(row["year"])): row for row in atlas.read_public()}
        housing_fields = ["state_fips", "year", "burden30_pct", "severe50_pct"]
        for fips, year, burden, severe in housing[housing_fields].itertuples(index=False, name=None):
            row = published[fips, year]
            self.assertEqual(row["burden30_pct"], format(burden, ".10g"))
            self.assertEqual(row["severe50_pct"], format(severe, ".10g"))
        for source in natality.loc[natality["year"] != 2020].to_dict("records"):
            row = published[source["state_fips"], source["year"]]
            column = "birth_rate_" + source["age_group"].replace("-", "_")
            self.assertGreater(source["births"], 9)
            self.assertEqual(row[column], format(source["rate_exported"], ".10g"))


if __name__ == "__main__":
    unittest.main()
