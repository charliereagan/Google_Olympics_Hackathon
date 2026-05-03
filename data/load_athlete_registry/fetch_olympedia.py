"""Olympedia (via public CSV scrape) fetcher for the athlete registry.

Per BUILD_SPEC §5.7 + PROJECT_BRIEF §6: pulls public CSVs from a GitHub repo
that pre-scraped Olympedia (1896-2022 Summer + Winter Olympics). We do NOT
hit olympedia.org directly — the GitHub-hosted CSVs are the polite,
ToS-friendly source.

Primary repo: KeithGalli/Olympics-Dataset
  - clean-data/bios.csv     -> athlete biographical records (1 row per athlete)
  - clean-data/results.csv  -> per-event placements (1 row per athlete-event)

Fallback: chanronnie/Olympics — only used if KeithGalli HEAD probe fails.

Filtering rule (PROJECT_BRIEF §6 hard requirement): only emit US athletes.
The KeithGalli ``noc`` column in clean-data/bios.csv is the 3-letter NOC code
(``USA``); the country-name column is ``NOC`` (with full names like
``United States``). We accept both.
"""

from __future__ import annotations

import csv
import io
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "cache" / "olympedia"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "TheStorytellersRoom/0.1 (charliereagan@gmail.com) Hackathon-research-only"
)

# Order matters: first that responds wins.
SOURCES = [
    {
        "name": "KeithGalli/Olympics-Dataset (clean-data)",
        "bios_url": "https://raw.githubusercontent.com/KeithGalli/Olympics-Dataset/master/clean-data/bios.csv",
        "results_url": "https://raw.githubusercontent.com/KeithGalli/Olympics-Dataset/master/clean-data/results.csv",
        "bios_cache": CACHE_DIR / "keithgalli_bios.csv",
        "results_cache": CACHE_DIR / "keithgalli_results.csv",
        "kind": "keithgalli_clean",
    },
    {
        "name": "KeithGalli/Olympics-Dataset (raw athletes/bios.csv)",
        "bios_url": "https://raw.githubusercontent.com/KeithGalli/Olympics-Dataset/master/athletes/bios.csv",
        "results_url": "https://raw.githubusercontent.com/KeithGalli/Olympics-Dataset/master/results/results.csv",
        "bios_cache": CACHE_DIR / "keithgalli_bios_raw.csv",
        "results_cache": CACHE_DIR / "keithgalli_results_raw.csv",
        "kind": "keithgalli_raw",
    },
    {
        "name": "chanronnie/Olympics",
        # chanronnie hosts the Kaggle 1896-2022 dump in CSV form.
        "bios_url": "https://raw.githubusercontent.com/chanronnie/Olympics/main/datasets/Olympic_Athletes.csv",
        "results_url": None,
        "bios_cache": CACHE_DIR / "chanronnie_athletes.csv",
        "results_cache": None,
        "kind": "chanronnie",
    },
]


@dataclass
class OlympediaAthlete:
    """One athlete record extracted from the Olympedia scrape."""

    olympedia_id: str  # the source's athlete_id; not the registry's athlete_id
    full_name_raw: str  # may include diacritics
    born_date: str | None = None  # ISO yyyy-mm-dd or None
    born_year: int | None = None
    born_city: str | None = None
    born_region: str | None = None  # for USA, this is the state
    born_country: str | None = None  # 3-letter NOC code
    sport: str | None = None
    olympic_or_paralympic: str = "olympic"  # this source is Olympic only
    games_years: set[int] = field(default_factory=set)
    games_types: set[str] = field(default_factory=set)  # Summer / Winter


def _download(url: str, cache: Path, force: bool = False) -> bytes:
    """Download ``url`` to ``cache`` with politeness. Returns bytes.

    Cached read on subsequent runs; ``force=True`` to refetch.
    """
    if cache.exists() and not force and cache.stat().st_size > 0:
        return cache.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    cache.write_bytes(body)
    return body


def _try_source(source: dict, force_refresh: bool = False) -> dict | None:
    """Probe + cache a source. Returns the source dict on success, None on
    network failure (so the caller can fall back).
    """
    try:
        bios_bytes = _download(source["bios_url"], source["bios_cache"], force=force_refresh)
        if len(bios_bytes) < 1024:
            return None
        if source.get("results_url"):
            try:
                _download(source["results_url"], source["results_cache"], force=force_refresh)
            except urllib.error.URLError:
                # results.csv is optional for sport-enrichment; don't fail
                # the source on results-only network errors.
                pass
        return source
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  [olympedia] source {source['name']!r} failed: {exc}", file=sys.stderr)
        return None


def _parse_year(date_or_year: str | None) -> int | None:
    if not date_or_year:
        return None
    s = date_or_year.strip()
    if not s:
        return None
    # ISO date "1976-08-30"
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    # Free-text "30 August 1976 in ..."
    for token in s.split():
        if token.isdigit() and len(token) == 4 and 1850 <= int(token) <= 2050:
            return int(token)
    return None


def _is_usa(noc_code: str | None, country_name: str | None) -> bool:
    """Both ``noc`` (3-letter) and ``NOC`` (full name) columns appear across
    KeithGalli versions. Filter on either."""
    if noc_code:
        if noc_code.strip().upper() == "USA":
            return True
    if country_name:
        if "United States" in country_name:
            return True
    return False


def _parse_keithgalli_clean(bios_bytes: bytes) -> Iterator[OlympediaAthlete]:
    """Parse clean-data/bios.csv. Schema:
    athlete_id,name,born_date,born_city,born_region,born_country,NOC,height_cm,weight_kg,died_date
    """
    text = bios_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        if not _is_usa(row.get("born_country"), row.get("NOC")):
            # The clean-data file uses born_country as 3-letter; sometimes
            # NOC carries multi-NOC strings ("People's Republic of China United States")
            # for athletes who switched. We accept those too via the NOC check.
            if not _is_usa(None, row.get("NOC")):
                continue
        full_name = (row.get("name") or "").strip()
        if not full_name:
            continue
        yield OlympediaAthlete(
            olympedia_id=str(row.get("athlete_id") or "").strip() or full_name,
            full_name_raw=full_name,
            born_date=(row.get("born_date") or "").strip() or None,
            born_year=_parse_year(row.get("born_date")),
            born_city=(row.get("born_city") or "").strip() or None,
            born_region=(row.get("born_region") or "").strip() or None,
            born_country=(row.get("born_country") or "").strip() or None,
            sport=None,  # filled in from results.csv
        )


def _parse_keithgalli_raw(bios_bytes: bytes) -> Iterator[OlympediaAthlete]:
    """Parse athletes/bios.csv. Schema:
    Roles,Sex,Full name,Used name,Born,Died,NOC,athlete_id,...
    Names use a "•" separator between first/last in Used name; we use Used
    name preferentially (it's the source's display form) and fall back to
    Full name.
    """
    text = bios_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        if not _is_usa(None, row.get("NOC")):
            continue
        used = (row.get("Used name") or "").replace("•", " ").strip()
        full = (row.get("Full name") or "").replace("•", " ").strip()
        full_name = used or full
        if not full_name:
            continue
        # Born is "30 August 1976 in San Mateo, California (USA)"
        born = (row.get("Born") or "").strip()
        born_year = _parse_year(born)
        born_city = None
        born_region = None
        if " in " in born:
            loc = born.split(" in ", 1)[1]
            # Strip trailing "(USA)"
            loc = loc.split(" (")[0]
            parts = [p.strip() for p in loc.split(",")]
            if len(parts) >= 2:
                born_city = parts[0] or None
                born_region = parts[1] or None
            elif len(parts) == 1:
                born_city = parts[0] or None
        yield OlympediaAthlete(
            olympedia_id=str(row.get("athlete_id") or "").strip() or full_name,
            full_name_raw=full_name,
            born_date=None,
            born_year=born_year,
            born_city=born_city,
            born_region=born_region,
            born_country="USA",
        )


def _parse_chanronnie(bios_bytes: bytes) -> Iterator[OlympediaAthlete]:
    """chanronnie schema is 1896-2022 Kaggle-format Olympic_Athletes.csv.
    Columns vary; we accept whatever has Name + NOC + Year."""
    text = bios_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    seen_ids: set[str] = set()
    for row in reader:
        noc = (row.get("NOC") or row.get("noc") or row.get("Country") or "").strip()
        if "USA" not in noc.upper() and "United States" not in noc:
            continue
        full_name = (row.get("Name") or row.get("name") or row.get("Athlete") or "").strip()
        if not full_name:
            continue
        # chanronnie has multiple rows per athlete (1 per Games). Dedup here
        # since merge.py expects 1-row-per-athlete from this fetcher.
        key = full_name.lower()
        if key in seen_ids:
            continue
        seen_ids.add(key)
        sport = (row.get("Sport") or row.get("sport") or "").strip() or None
        year_str = (row.get("Year") or row.get("year") or "").strip()
        born_year = None
        try:
            if year_str.isdigit():
                # We only have competition year here, not birth year. Don't
                # invent a birth year — leave None.
                pass
        except Exception:
            pass
        yield OlympediaAthlete(
            olympedia_id=full_name,
            full_name_raw=full_name,
            born_year=born_year,
            sport=sport,
            born_country="USA",
        )


def _enrich_with_results(
    athletes: dict[str, OlympediaAthlete], results_bytes: bytes
) -> None:
    """Populate ``sport`` + ``games_years`` + ``games_types`` from results.csv.

    Mutates ``athletes`` in place. Ignores rows whose athlete_id isn't in our
    USA-filtered set.
    """
    text = results_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    sport_counts: dict[str, dict[str, int]] = {}
    for row in reader:
        athlete_id = str(row.get("athlete_id") or "").strip()
        if not athlete_id or athlete_id not in athletes:
            continue
        a = athletes[athlete_id]
        # ``discipline`` like "Athletics" or "Artistic Gymnastics (Gymnastics)".
        # Prefer the parenthetical sport family if present.
        disc = (row.get("discipline") or "").strip()
        sport_clean = disc
        if "(" in disc and disc.endswith(")"):
            inside = disc[disc.rfind("(") + 1 : -1].strip()
            if inside:
                sport_clean = inside
        if sport_clean:
            bucket = sport_counts.setdefault(athlete_id, {})
            bucket[sport_clean] = bucket.get(sport_clean, 0) + 1
        year_str = (row.get("year") or "").strip()
        try:
            if year_str:
                year = int(float(year_str))
                a.games_years.add(year)
                if not a.born_year and 1850 <= year <= 2050:
                    # If bios had no birth year, record the earliest games
                    # year as a coarse fallback for era_or_decade. We mark
                    # this in merge by checking born_date; here we just
                    # avoid clobbering a real birth year.
                    pass
        except (ValueError, TypeError):
            pass
        type_ = (row.get("type") or "").strip()
        if type_:
            a.games_types.add(type_)
    # Pick the most common sport per athlete.
    for athlete_id, counts in sport_counts.items():
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        athletes[athlete_id].sport = best


def fetch(force_refresh: bool = False) -> tuple[list[OlympediaAthlete], dict]:
    """Fetch + parse the Olympedia source.

    Returns (records, attribution). Attribution describes which repo + URLs
    were used so the README can cite them.
    """
    chosen: dict | None = None
    for source in SOURCES:
        chosen = _try_source(source, force_refresh=force_refresh)
        if chosen:
            print(f"  [olympedia] using source: {chosen['name']}")
            break
    if not chosen:
        return ([], {"source": None, "note": "All Olympedia sources failed; using fixtures."})

    bios_bytes = chosen["bios_cache"].read_bytes()
    if chosen["kind"] == "keithgalli_clean":
        athletes_iter = _parse_keithgalli_clean(bios_bytes)
    elif chosen["kind"] == "keithgalli_raw":
        athletes_iter = _parse_keithgalli_raw(bios_bytes)
    elif chosen["kind"] == "chanronnie":
        athletes_iter = _parse_chanronnie(bios_bytes)
    else:
        return ([], {"source": chosen["name"], "note": "Unknown kind"})

    by_id: dict[str, OlympediaAthlete] = {}
    for a in athletes_iter:
        by_id[a.olympedia_id] = a

    # Enrich sport from results.csv if present.
    if chosen.get("results_cache") and chosen["results_cache"].exists():
        try:
            results_bytes = chosen["results_cache"].read_bytes()
            _enrich_with_results(by_id, results_bytes)
        except Exception as exc:
            print(f"  [olympedia] results enrichment failed (non-fatal): {exc}", file=sys.stderr)

    records = list(by_id.values())
    attribution = {
        "source": chosen["name"],
        "bios_url": chosen["bios_url"],
        "results_url": chosen.get("results_url"),
        "license": "Olympedia data is public-domain-derived; these GitHub repos host scraped CSVs.",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "row_count": len(records),
    }
    return records, attribution


if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    recs, attr = fetch(force_refresh=refresh)
    print(f"Fetched {len(recs)} USA records from {attr.get('source')}")
    for r in recs[:5]:
        print(f"  - {r.full_name_raw} | sport={r.sport} | yr={r.born_year} | st={r.born_region}")
