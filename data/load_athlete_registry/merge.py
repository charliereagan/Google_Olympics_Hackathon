"""Merge + dedupe + canonicalize athlete records from multiple sources.

Inputs:
  - Olympedia stream (`OlympediaAthlete` from `fetch_olympedia.py`)
  - Wikidata stream (`WikidataAthlete` from `fetch_wikidata.py`)
  - Optional fallback fixtures stream (test data labeled with source="fixture")

Output: a list of registry records matching ``data/bq_schemas/athlete_registry.json``.

Dedup key: (canonical_first_name, canonical_last_name, birth_year_if_known).
When two sources disagree on ``sport``, Olympedia wins. When two sources
contribute different ``known_variants``, lists are unioned.
"""

from __future__ import annotations

import hashlib
import time
from typing import Iterable

from . import normalize


# ---------------------------------------------------------------------------
# Dedup key
# ---------------------------------------------------------------------------


def _dedup_key(first: str | None, last: str | None, birth_year: int | None) -> tuple:
    f = (first or "").lower().strip()
    l = (last or "").lower().strip()
    # Only the first given-name token contributes to the key — middle names
    # are common cause of false-different-record bugs.
    f_head = f.split(" ")[0] if f else ""
    return (f_head, l, birth_year or 0)


def _athlete_id(canonical_full: str, birth_year: int | None) -> str:
    """Stable across reloads: hash of canonical full name + birth year (or 0).

    Format: ``ar_<10-char-hex>`` so the IDs sort lexicographically and are
    easy to grep in logs without colliding with BigQuery RECORD-id
    expectations.
    """
    payload = f"{canonical_full}|{birth_year or 0}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"ar_{digest[:10]}"


# ---------------------------------------------------------------------------
# Per-source intermediate records
# ---------------------------------------------------------------------------


def _from_olympedia(rec) -> dict:
    """Convert an OlympediaAthlete to a registry-shape intermediate dict."""
    norm = normalize.normalize_record(full_name_raw=rec.full_name_raw)
    birth_year = rec.born_year
    games_types = getattr(rec, "games_types", set()) or set()
    # Coarse era: prefer birth-decade; fall back to earliest games year.
    era_year = birth_year
    if era_year is None and getattr(rec, "games_years", None):
        try:
            era_year = min(rec.games_years)
        except ValueError:
            era_year = None
    return {
        "athlete_id": _athlete_id(norm["_canonical"], birth_year),
        "full_name": norm["full_name"],
        "first_name": norm["first_name"],
        "last_name": norm["last_name"],
        "known_variants": norm["known_variants"],
        "sport": rec.sport,
        "olympic_or_paralympic": rec.olympic_or_paralympic or "olympic",
        "era_or_decade": normalize.era_for_year(era_year),
        "hometown_state": rec.born_region,
        "source_first_seen": "olympedia",
        "_canonical": norm["_canonical"],
        "_birth_year": birth_year,
    }


def _from_wikidata(rec) -> dict:
    norm = normalize.normalize_record(
        full_name_raw=rec.full_name_raw,
        extra_variants=rec.native_labels,
    )
    return {
        "athlete_id": _athlete_id(norm["_canonical"], rec.born_year),
        "full_name": norm["full_name"],
        "first_name": norm["first_name"],
        "last_name": norm["last_name"],
        "known_variants": norm["known_variants"],
        "sport": rec.sport,
        "olympic_or_paralympic": rec.olympic_or_paralympic or "olympic",
        "era_or_decade": normalize.era_for_year(rec.born_year),
        "hometown_state": None,
        "source_first_seen": "wikidata",
        "_canonical": norm["_canonical"],
        "_birth_year": rec.born_year,
    }


def _from_fixture(name: str, sport: str | None, kind: str) -> dict:
    norm = normalize.normalize_record(full_name_raw=name)
    return {
        "athlete_id": _athlete_id(norm["_canonical"], None),
        "full_name": norm["full_name"],
        "first_name": norm["first_name"],
        "last_name": norm["last_name"],
        "known_variants": norm["known_variants"],
        "sport": sport,
        "olympic_or_paralympic": kind,
        "era_or_decade": None,
        "hometown_state": None,
        "source_first_seen": "fixture",
        "_canonical": norm["_canonical"],
        "_birth_year": None,
    }


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


# Source-precedence: lower index = more authoritative. Used for sport-conflict
# resolution. Olympedia wins per spec.
_SOURCE_RANK = {
    "olympedia": 0,
    "wikidata": 1,
    "team_usa_roster": 2,
    "fixture": 99,
}


def _merge_two(primary: dict, secondary: dict) -> dict:
    """Merge ``secondary`` into ``primary`` in place, returning ``primary``."""
    # Variant union.
    pv = {v.lower(): v for v in primary["known_variants"]}
    for v in secondary.get("known_variants") or []:
        pv.setdefault(v.lower(), v)
    primary["known_variants"] = sorted(pv.values(), key=lambda x: x.lower())

    # Sport: keep primary unless primary is empty.
    if not primary.get("sport") and secondary.get("sport"):
        primary["sport"] = secondary["sport"]

    # Hometown state: same — keep primary unless empty.
    if not primary.get("hometown_state") and secondary.get("hometown_state"):
        primary["hometown_state"] = secondary["hometown_state"]

    # Birth year / era: pick whichever is non-None.
    if primary.get("_birth_year") is None and secondary.get("_birth_year") is not None:
        primary["_birth_year"] = secondary["_birth_year"]
        primary["era_or_decade"] = normalize.era_for_year(secondary["_birth_year"])

    # Olympic vs Paralympic: if sources disagree, escalate to "both".
    p_kind = primary.get("olympic_or_paralympic")
    s_kind = secondary.get("olympic_or_paralympic")
    if p_kind and s_kind and p_kind != s_kind:
        primary["olympic_or_paralympic"] = "both"
    elif not p_kind and s_kind:
        primary["olympic_or_paralympic"] = s_kind

    # source_first_seen: keep the more authoritative one.
    p_rank = _SOURCE_RANK.get(primary.get("source_first_seen") or "fixture", 99)
    s_rank = _SOURCE_RANK.get(secondary.get("source_first_seen") or "fixture", 99)
    if s_rank < p_rank:
        primary["source_first_seen"] = secondary["source_first_seen"]
        # Sport precedence flips with source rank.
        if secondary.get("sport"):
            primary["sport"] = secondary["sport"]

    return primary


def merge(
    olympedia_records: Iterable,
    wikidata_records: Iterable,
    *,
    fixtures: Iterable[dict] | None = None,
) -> list[dict]:
    """Merge all sources into a deduplicated registry list.

    ``fixtures`` is a list of dicts with at least ``name`` and optional
    ``sport`` + ``kind``. Used only when a network source fails (see CLI).
    """
    by_key: dict[tuple, dict] = {}

    # 1. Olympedia (primary, ranked 0)
    for src in olympedia_records:
        rec = _from_olympedia(src)
        key = _dedup_key(rec["first_name"], rec["last_name"], rec["_birth_year"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = rec
        else:
            by_key[key] = _merge_two(existing, rec)

    # Helper: locate an existing key that matches a (first, last, year)
    # tuple either strictly or — if the new record has no year OR the
    # incumbent has no year — loosely on (first, last) alone. Returns the
    # incumbent's key, or None if no match.
    def _find_match(first: str | None, last: str | None, year: int | None) -> tuple | None:
        strict = _dedup_key(first, last, year)
        if strict in by_key:
            return strict
        # Loose: scan for same (first_head, last) regardless of year. Only
        # accept loose match if at least one side is missing the birth year
        # — otherwise two athletes with different DOBs would collide.
        target_first = strict[0]
        target_last = strict[1]
        for existing_key, existing_rec in by_key.items():
            if existing_key[0] != target_first or existing_key[1] != target_last:
                continue
            existing_year = existing_rec.get("_birth_year")
            if year is None or existing_year is None or year == existing_year:
                return existing_key
        return None

    # 2. Wikidata (secondary, variant-name source)
    for src in wikidata_records:
        rec = _from_wikidata(src)
        match_key = _find_match(rec["first_name"], rec["last_name"], rec["_birth_year"])
        if match_key is not None:
            by_key[match_key] = _merge_two(by_key[match_key], rec)
        else:
            by_key[_dedup_key(rec["first_name"], rec["last_name"], rec["_birth_year"])] = rec

    # 3. Fixtures (fallback, only used if previous sources failed)
    for fx in fixtures or []:
        name = fx.get("name") if isinstance(fx, dict) else None
        if not name:
            continue
        rec = _from_fixture(
            name,
            fx.get("sport"),
            fx.get("kind", "olympic"),
        )
        match_key = _find_match(rec["first_name"], rec["last_name"], rec["_birth_year"])
        if match_key is None:
            by_key[_dedup_key(rec["first_name"], rec["last_name"], rec["_birth_year"])] = rec
        # else: skip — incumbent (real record) wins.

    # Stamp last_updated; strip internal keys.
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    output: list[dict] = []
    for rec in by_key.values():
        clean = {k: v for k, v in rec.items() if not k.startswith("_")}
        clean["last_updated"] = now
        # Athlete IDs may collide if two records merge — recompute deterministically.
        clean["athlete_id"] = _athlete_id(
            normalize.canonical_form(clean["full_name"]),
            rec.get("_birth_year"),
        )
        output.append(clean)
    # Stable sort: by last name then full name for review-friendliness.
    output.sort(key=lambda r: ((r.get("last_name") or "").lower(), (r.get("full_name") or "").lower()))
    return output


# ---------------------------------------------------------------------------
# Test fixtures (used only when network sources fail)
# ---------------------------------------------------------------------------


# Public Olympic figures named in BUILD_SPEC §5.7 + PROJECT_BRIEF §5 as
# examples of NIL targets. Used ONLY as test fixtures so the registry has
# something for the NIL Layer to find when networks are down. These names
# appear in the example block of BUILD_SPEC.md and are public-domain
# historical figures; they are exactly the names the NIL Redaction Layer is
# supposed to redact, so seeding them as test data is the right behavior.
FALLBACK_FIXTURES = [
    {"name": "Wilma Rudolph", "sport": "Athletics", "kind": "olympic"},
    {"name": "Jesse Owens", "sport": "Athletics", "kind": "olympic"},
    {"name": "Jim Thorpe", "sport": "Athletics", "kind": "olympic"},
    {"name": "Kerri Strug", "sport": "Gymnastics", "kind": "olympic"},
    {"name": "Michael Phelps", "sport": "Swimming", "kind": "olympic"},
    {"name": "Simone Biles", "sport": "Gymnastics", "kind": "olympic"},
    {"name": "Katie Ledecky", "sport": "Swimming", "kind": "olympic"},
    {"name": "Tatyana McFadden", "sport": "Athletics", "kind": "paralympic"},
    {"name": "Trischa Zorn", "sport": "Swimming", "kind": "paralympic"},
    {"name": "Oksana Masters", "sport": "Cross-Country Skiing", "kind": "paralympic"},
]
