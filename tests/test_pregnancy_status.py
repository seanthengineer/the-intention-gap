"""Tests for the Round 13 pregnancy classification, using synthetic codes.

Run with:  python -m unittest -v
"""

import math
import unittest

import pandas as pd

from analysis import pregnancy_status as ps
from analysis import supplement_extract as se

SKIP, REFUSAL, DONT_KNOW, NONINTERVIEW = -4, -1, -2, -5


class ClassificationTests(unittest.TestCase):
    def check(self, codes, status, reason):
        self.assertEqual(ps.classify_pregnancy(*codes), (status, reason))

    def test_reported_pregnant(self):
        self.check((1, SKIP, 1), ps.PREGNANT, ps.REPORTED_PREGNANT)
        self.check((SKIP, 1, 1), ps.PREGNANT, ps.REPORTED_PREGNANT)

    def test_reported_not_pregnant_now(self):
        self.check((SKIP, 1, 0), ps.NOT_PREGNANT, ps.REPORTED_NOT_PREGNANT)

    def test_explicit_no_at_entry_item_skips_current_item(self):
        self.check((0, SKIP, SKIP), ps.NOT_PREGNANT, ps.NEVER_PREGNANT)
        self.check((SKIP, 0, SKIP), ps.NOT_PREGNANT, ps.NONE_SINCE_LAST)

    def test_skipping_the_whole_block_is_unknown_not_negative(self):
        self.check((SKIP, SKIP, SKIP), ps.UNKNOWN, ps.SKIPPED_BLOCK)

    def test_nonresponse_is_unknown(self):
        self.check((REFUSAL, SKIP, SKIP), ps.UNKNOWN, ps.ENTRY_NONRESPONSE)
        self.check((SKIP, DONT_KNOW, SKIP), ps.UNKNOWN, ps.ENTRY_NONRESPONSE)
        self.check((SKIP, 1, DONT_KNOW), ps.UNKNOWN, ps.CURRENT_NONRESPONSE)
        self.check((SKIP, 1, REFUSAL), ps.UNKNOWN, ps.CURRENT_NONRESPONSE)

    def test_routing_violations_are_unknown(self):
        self.check((0, SKIP, 1), ps.UNKNOWN, ps.INCONSISTENT_ROUTING)
        self.check((1, 0, SKIP), ps.UNKNOWN, ps.INCONSISTENT_ROUTING)
        self.check((SKIP, 1, SKIP), ps.UNKNOWN, ps.INCONSISTENT_ROUTING)
        self.check((SKIP, SKIP, 0), ps.UNKNOWN, ps.INCONSISTENT_ROUTING)
        self.check((REFUSAL, SKIP, 1), ps.UNKNOWN, ps.INCONSISTENT_ROUTING)

    def test_noninterview_is_unknown(self):
        self.check((NONINTERVIEW, NONINTERVIEW, NONINTERVIEW), ps.UNKNOWN, ps.NOT_INTERVIEWED)

    def test_weeks_only_for_pregnant_women_in_range(self):
        self.assertEqual(ps.weeks_pregnant(ps.PREGNANT, 22), 22.0)
        self.assertTrue(math.isnan(ps.weeks_pregnant(ps.PREGNANT, DONT_KNOW)))
        self.assertTrue(math.isnan(ps.weeks_pregnant(ps.PREGNANT, 45)))
        self.assertTrue(math.isnan(ps.weeks_pregnant(ps.NOT_PREGNANT, SKIP)))


class TableTests(unittest.TestCase):
    def test_pregnancy_table_and_gestation_agreement(self):
        eligible = pd.DataFrame({
            "R0000100": [1, 2, 3, 4],
            se.EVER_PREGNANT: [SKIP, SKIP, 0, SKIP],
            se.PREGNANT_SINCE_LAST: [1, 1, SKIP, SKIP],
            se.PREGNANT_NOW: [1, 1, SKIP, SKIP],
            se.WEEKS_PREGNANT: [36, 10, SKIP, SKIP],
        })
        table = ps.pregnancy_table(eligible)
        self.assertEqual(list(table["pregnancy_status"]),
                         [ps.PREGNANT, ps.PREGNANT, ps.NOT_PREGNANT, ps.UNKNOWN])
        frame = table.assign(outcome=[1.0, 1.0, 0.0, None])
        timing = pd.DataFrame({"first_birth_month": [1, 20]}, index=[1, 2])
        agreement = ps.gestation_agreement(frame, timing)
        self.assertEqual(agreement["birth_in_window"], 2)
        self.assertEqual(agreement["first_birth_within_tolerance"], 1)
        self.assertEqual(agreement["first_birth_later_than_expected"], 1)


if __name__ == "__main__":
    unittest.main()
