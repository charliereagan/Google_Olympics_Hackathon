"""Stdlib unit tests for normalize.py.

Run as either:
    python3 data/load_athlete_registry/tests/test_normalize.py
    python3 -m pytest data/load_athlete_registry/tests/test_normalize.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from data.load_athlete_registry import normalize  # noqa: E402


class TestFolding(unittest.TestCase):
    def test_fold_strips_diacritics(self):
        self.assertEqual(normalize.fold_diacritics("Renée"), "Renee")
        self.assertEqual(normalize.fold_diacritics("Müller"), "Muller")
        self.assertEqual(normalize.fold_diacritics("Plain"), "Plain")

    def test_canonical_form_lowercases_and_collapses(self):
        self.assertEqual(normalize.canonical_form("  Renée  Müller  "), "renee muller")
        self.assertEqual(normalize.canonical_form("Joyner-Kersee"), "joyner-kersee")

    def test_display_form_keeps_case(self):
        self.assertEqual(normalize.display_form("Renée Müller"), "Renee Muller")


class TestSplit(unittest.TestCase):
    def test_two_token_name(self):
        first, last = normalize.split_first_last("Michael Phelps")
        self.assertEqual((first, last), ("Michael", "Phelps"))

    def test_middle_name_joins_first(self):
        first, last = normalize.split_first_last("Mary Lou Retton")
        self.assertEqual((first, last), ("Mary Lou", "Retton"))

    def test_single_token_is_last(self):
        first, last = normalize.split_first_last("Madonna")
        self.assertEqual((first, last), (None, "Madonna"))

    def test_empty(self):
        self.assertEqual(normalize.split_first_last(""), (None, None))


class TestVariants(unittest.TestCase):
    def test_includes_self(self):
        v = normalize.generate_variants("Michael Phelps")
        self.assertIn("Michael Phelps", v)

    def test_initial_forms(self):
        v = normalize.generate_variants("Michael Phelps")
        self.assertIn("M. Phelps", v)
        self.assertIn("M Phelps", v)

    def test_first_and_last_alone(self):
        v = normalize.generate_variants("Michael Phelps")
        self.assertIn("Michael", v)
        self.assertIn("Phelps", v)

    def test_michael_to_mike(self):
        v = normalize.generate_variants("Michael Phelps")
        v_lower = [x.lower() for x in v]
        self.assertIn("mike phelps", v_lower)

    def test_robert_expansions(self):
        v = [x.lower() for x in normalize.generate_variants("Robert Smith")]
        self.assertIn("bob smith", v)
        self.assertIn("rob smith", v)
        self.assertIn("bobby smith", v)

    def test_hyphenated_last_name(self):
        v = [x.lower() for x in normalize.generate_variants("Jackie Joyner-Kersee")]
        self.assertIn("jackie joyner-kersee", v)
        self.assertIn("jackie joyner kersee", v)
        self.assertIn("jackie joynerkersee", v)

    def test_diacritic_original_kept(self):
        v = normalize.generate_variants(
            "Renee Muller",
            original_with_diacritics="Renée Müller",
        )
        self.assertIn("Renée Müller", v)
        self.assertIn("Renee Muller", v)

    def test_extras_included(self):
        v = normalize.generate_variants(
            "Maria Rodriguez",
            extra=["Maria Rodriguez Smith", "M. Rodriguez-Smith"],
        )
        v_lower = [x.lower() for x in v]
        self.assertIn("maria rodriguez smith", v_lower)
        self.assertIn("m. rodriguez-smith", v_lower)

    def test_dedup_within_variants(self):
        v = normalize.generate_variants(
            "Michael Phelps",
            extra=["Michael Phelps", "michael phelps", "MICHAEL PHELPS"],
        )
        # All three "Michael Phelps" cases should collapse into one.
        lowered = [x.lower() for x in v]
        self.assertEqual(lowered.count("michael phelps"), 1)

    def test_multi_middle_name_uses_only_first_for_nick(self):
        v = [x.lower() for x in normalize.generate_variants("Michael John Phelps")]
        # Should expand Michael -> Mike, keep "John" middle, last "Phelps".
        self.assertIn("mike john phelps", v)


class TestNormalizeRecord(unittest.TestCase):
    def test_full_shape(self):
        rec = normalize.normalize_record(full_name_raw="Renée Joyner-Kersee")
        self.assertEqual(rec["full_name"], "Renee Joyner-Kersee")
        self.assertEqual(rec["first_name"], "Renee")
        self.assertEqual(rec["last_name"], "Joyner-Kersee")
        self.assertIn("Renée Joyner-Kersee", rec["known_variants"])  # original kept
        self.assertIn("Renee Joyner Kersee", rec["known_variants"])  # split form
        self.assertEqual(rec["_canonical"], "renee joyner-kersee")


class TestEra(unittest.TestCase):
    def test_decades(self):
        self.assertEqual(normalize.era_for_year(1976), "1970s")
        self.assertEqual(normalize.era_for_year(2024), "2020s")
        self.assertEqual(normalize.era_for_year(1899), "pre-1900")
        self.assertIsNone(normalize.era_for_year(None))


if __name__ == "__main__":
    unittest.main()
