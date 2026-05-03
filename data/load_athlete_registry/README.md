# `data/load_athlete_registry/` — Athlete-registry seed loader

The athlete registry is the **source of truth for the NIL Redaction Layer**
(BUILD_SPEC §5.7). It is INTERNAL DATA ONLY. It never reaches user-facing
surfaces — the Layer scans against it.

## Run

```bash
# Produce a JSON snapshot + NDJSON, no BigQuery write:
python3 -m data.load_athlete_registry.cli --dry-run

# Produce + load to dev:
python3 -m data.load_athlete_registry.cli --dataset=storytellers_room_dev

# Produce + load to production (HoE only):
python3 -m data.load_athlete_registry.cli --dataset=storytellers_room

# Force-refresh the upstream caches:
python3 -m data.load_athlete_registry.cli --refresh
```

## What it does

1. Pulls public CSVs from a GitHub repo that pre-scraped Olympedia
   (1896-2022 Olympic Games), filters to NOC = USA.
2. Cross-references Wikidata SPARQL for variant names (nicknames, alternate
   spellings, native-language labels) and for Paralympic medalists (the gap
   in the Olympedia scrape).
3. Merges + dedupes on `(first_name, last_name, birth_year_if_known)`,
   prefers Olympedia on sport-conflict, unions `known_variants`.
4. Writes a JSON snapshot to `data/athlete_registry_snapshot/registry.YYYY-MM-DD.json`.
5. Writes NDJSON to `/tmp/athlete_registry.ndjson`.
6. (unless `--dry-run`) `bq load --replace` to the dev dataset.
7. Asserts >= 500 rows. Exit 1 otherwise (HOE-DEC-019 fail-closed contract).

## Source attribution

### Primary: Olympedia (via GitHub CSV scrape)

- **`KeithGalli/Olympics-Dataset`** (https://github.com/KeithGalli/Olympics-Dataset)
  - `clean-data/bios.csv` — 1 row per athlete with structured columns
    (`athlete_id`, `name`, `born_date`, `born_city`, `born_region`,
    `born_country`, `NOC`, `height_cm`, `weight_kg`, `died_date`).
  - `clean-data/results.csv` — 1 row per athlete-event-Games, used to
    enrich `sport` and `era`.
  - Filter: `NOC == 'United States'` OR `born_country == 'USA'`.
- Fallback: `chanronnie/Olympics` if the KeithGalli URL fails.
- License: Olympedia.org data is public-domain-derived. The GitHub repos
  re-host scraped CSVs; we treat them as research data, do NOT redistribute,
  cache only locally.

### Secondary: Wikidata SPARQL

- Endpoint: `https://query.wikidata.org/sparql`
- Custom `User-Agent: TheStorytellersRoom/0.1 (charliereagan@gmail.com) Hackathon-research-only`
- Two queries: US Olympic medalists + US Paralympic medalists.
  Both filter on `?p wdt:P31 wd:Q5 ; wdt:P27 wd:Q30 ; wdt:P166 ?medal`
  with `?medal` constrained to Olympic/Paralympic medal Q-IDs.
- Wikidata content is CC0; no redistribution restrictions.

### Optional: Team USA roster

- Skipped in v1. Olympedia + Wikidata cover historical athletes through 2022;
  the active 2024-2026 delta is layered on in Day-2/3 work if desired.
- Future scrape target: `https://www.teamusa.com/athletes` with
  `robots.txt` respect and aggressive caching.

### Test fixtures

- `merge.FALLBACK_FIXTURES` — 10 widely-known Olympic and Paralympic figures
  (named in `BUILD_SPEC §5.7` and `PROJECT_BRIEF §5` as NIL-redaction
  examples). Used ONLY when network sources are unreachable. Clearly tagged
  with `source_first_seen = "fixture"`. Names appear nowhere in user-facing
  output — the NIL Redaction Layer is supposed to redact exactly these
  names, so they're appropriate as internal seed data.

## Refresh cadence

The NIL Layer **refreshes its in-memory automaton every 6 hours** at runtime
(BUILD_SPEC §5.7). This loader populates the underlying BigQuery table; the
runtime reads from it. Recommended cadence:

- **Day 1 (now):** initial load.
- **Day 1-9 (build phase):** re-run only if the `athlete_registry` schema
  changes or a new source is added. The data set is essentially static for
  historical athletes.
- **Day 9 (pre-demo):** re-run to pick up any Wikidata variant-name updates
  in the lead-up to the demo.
- **Day 11 (post-submission):** stop re-running. The data must be destroyed
  at the conclusion of the hackathon per PROJECT_BRIEF §6.

The runtime's 6-hour in-memory refresh is independent of this loader. If
the loader produced fewer rows than the previous run, the runtime keeps
the prior automaton and logs a warning (BUILD_SPEC §5.7 step 1).

## Schema

Output rows match `data/bq_schemas/athlete_registry.json`:

| Field | Type | Notes |
|---|---|---|
| `athlete_id` | STRING (REQUIRED) | `ar_<10-hex>` — sha1 of canonical full_name + birth_year, stable across reruns |
| `full_name` | STRING (REQUIRED) | NFKD-folded, diacritic-stripped |
| `first_name` | STRING | All tokens before the last whitespace-separated token |
| `last_name` | STRING | The final whitespace-separated token |
| `known_variants` | STRING (REPEATED) | Diacritic original + nicknames + initials + hyphen splits + Wikidata native labels |
| `sport` | STRING | Olympedia preferred; Wikidata fallback |
| `olympic_or_paralympic` | STRING | `olympic` / `paralympic` / `both` |
| `era_or_decade` | STRING | `1990s`, `pre-1900`, etc. From birth year preferred, else earliest competition year |
| `hometown_state` | STRING | US state from `born_region` (Olympedia clean-data only) |
| `source_first_seen` | STRING | `olympedia` / `wikidata` / `team_usa_roster` / `fixture` |
| `last_updated` | TIMESTAMP | When this run produced the row |

## Directory layout

```
data/
  load_athlete_registry/
    __init__.py
    README.md              # this file
    cli.py                 # entrypoint
    fetch_olympedia.py     # primary
    fetch_wikidata.py      # secondary
    normalize.py           # name normalization + variant generation
    merge.py               # dedupe + canonical record assembly
    write_to_bigquery.py   # bq load wrapper
    tests/
      test_normalize.py
      test_merge.py
  athlete_registry_snapshot/
    .gitkeep
    # registry.YYYY-MM-DD.json snapshots (gitignored)
    # attribution.latest.json — provenance of the most-recent run
  cache/
    olympedia/             # gitignored CSV + JSON download cache
```

## Tests

```bash
# stdlib runner — no pytest required
python3 data/load_athlete_registry/tests/test_normalize.py
python3 data/load_athlete_registry/tests/test_merge.py

# or pytest
python3 -m pytest data/load_athlete_registry/tests/
```

## Anti-patterns

- Do not commit cached Olympedia CSVs (`data/cache/olympedia/`) or registry
  snapshots (`data/athlete_registry_snapshot/registry.*.json`). Both are
  gitignored.
- Do not default to `--dataset=storytellers_room`. The HoE handles the
  production load after reviewing the dev output.
- Do not skip the >= 500 row assertion. Per HOE-DEC-019 the Layer fails
  CLOSED — an empty registry would silently pass everything through, which
  is exactly the failure the Layer exists to prevent.
- Do not surface registry rows on any user-facing surface. Internal data
  only.
