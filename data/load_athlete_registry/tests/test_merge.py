"""Stdlib unit tests for merge.py — dedup + variant union + sport precedence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from data.load_athlete_registry import merge  # noqa: E402
from data.load_athlete_registry.fetch_olympedia import OlympediaAthlete  # noqa: E402
from data.load_athlete_registry.fetch_wikidata import WikidataAthlete  # noqa: E402


def _olympedia(name, year=None, sport=None, region=None, kind="olympic"):
    return OlympediaAthlete(
        olympedia_id=name,
        full_name_raw=name,
        born_year=year,
        sport=sport,
        born_region=region,
        olympic_or_paralympic=kind,
    )


def _wikidata(name, year=None, sport=None, kind="olympic", natives=None):
    return WikidataAthlete(
        qid="Q-" + name.replace(" ", "_"),
        full_name_raw=name,
        born_year=year,
        sport=sport,
        olympic_or_paralympic=kind,
        native_labels=natives or [],
    )


class TestMergeBasic(unittest.TestCase):
    def test_olympedia_only(self):
        out = merge.merge(
            [_olympedia("Anna Smith", year=1990, sport="Swimming", region="California")],
            [],
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["full_name"], "Anna Smith")
        self.assertEqual(out[0]["sport"], "Swimming")
        self.assertEqual(out[0]["era_or_decade"], "1990s")
        self.assertEqual(out[0]["hometown_state"], "California")
        self.assertEqual(out[0]["source_first_seen"], "olympedia")
        self.assertTrue(out[0]["athlete_id"].startswith("ar_"))

    def test_wikidata_only(self):
        out = merge.merge(
            [],
            [_wikidata("Beth Lee", year=1985, sport="Cycling")],
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source_first_seen"], "wikidata")

    def test_dedup_by_first_last_year(self):
        # Same person from both sources; should dedup to 1 row.
        out = merge.merge(
            [_olympedia("Carlos Reyes", year=1992, sport="Athletics", region="Texas")],
            [_wikidata("Carlos Reyes", year=1992, sport="Football", natives=["Carlitos Reyes"])],
        )
        self.assertEqual(len(out), 1)
        rec = out[0]
        # Olympedia wins on sport conflict.
        self.assertEqual(rec["sport"], "Athletics")
        # Variant from Wikidata native label is preserved.
        v_lower = [v.lower() for v in rec["known_variants"]]
        self.assertIn("carlitos reyes", v_lower)
        # Source-of-record stays Olympedia (lower rank).
        self.assertEqual(rec["source_first_seen"], "olympedia")

    def test_dedup_loose_when_birth_year_missing_one_side(self):
        # Olympedia has DOB; Wikidata doesn't. Should still dedup.
        out = merge.merge(
            [_olympedia("Dana Park", year=2000, sport="Swimming")],
            [_wikidata("Dana Park", year=None, sport=None, natives=["D. Park-Lee"])],
        )
        self.assertEqual(len(out), 1)
        v_lower = [v.lower() for v in out[0]["known_variants"]]
        self.assertIn("d. park-lee", v_lower)

    def test_olympic_paralympic_escalates_to_both(self):
        out = merge.merge(
            [_olympedia("Eve Brown", year=1980, kind="olympic")],
            [_wikidata("Eve Brown", year=1980, kind="paralympic")],
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["olympic_or_paralympic"], "both")

    def test_athlete_id_stable_across_runs(self):
        out1 = merge.merge([_olympedia("Frank Hill", year=1975)], [])
        out2 = merge.merge([_olympedia("Frank Hill", year=1975)], [])
        self.assertEqual(out1[0]["athlete_id"], out2[0]["athlete_id"])

    def test_athlete_id_changes_with_birth_year(self):
        out1 = merge.merge([_olympedia("Gail Ito", year=1980)], [])
        out2 = merge.merge([_olympedia("Gail Ito", year=1981)], [])
        self.assertNotEqual(out1[0]["athlete_id"], out2[0]["athlete_id"])

    def test_diacritic_dedup(self):
        # "René" and "Rene" should collapse — canonical_form folds diacritics.
        out = merge.merge(
            [_olympedia("René Soto", year=1995)],
            [_wikidata("Rene Soto", year=1995)],
        )
        self.assertEqual(len(out), 1)

    def test_fixtures_filled_when_no_records(self):
        out = merge.merge([], [], fixtures=merge.FALLBACK_FIXTURES)
        self.assertEqual(len(out), len(merge.FALLBACK_FIXTURES))
        for rec in out:
            self.assertEqual(rec["source_first_seen"], "fixture")

    def test_fixture_does_not_clobber_real_record(self):
        # A real Olympedia record with the same name as a fixture should NOT
        # be replaced by the fixture data.
        out = merge.merge(
            [_olympedia("Wilma Rudolph", year=1940, sport="Athletics", region="Tennessee")],
            [],
            fixtures=merge.FALLBACK_FIXTURES,
        )
        wilmas = [r for r in out if r["full_name"] == "Wilma Rudolph"]
        self.assertEqual(len(wilmas), 1)
        self.assertEqual(wilmas[0]["source_first_seen"], "olympedia")
        self.assertEqual(wilmas[0]["hometown_state"], "Tennessee")

    def test_required_schema_fields_present(self):
        out = merge.merge(
            [_olympedia("Hank Yu", year=1992, sport="Swimming", region="Hawaii")],
            [],
        )
        for required in ["athlete_id", "full_name", "known_variants", "last_updated"]:
            self.assertIn(required, out[0])
        self.assertIsInstance(out[0]["known_variants"], list)
        self.assertGreater(len(out[0]["known_variants"]), 0)


if __name__ == "__main__":
    unittest.main()
