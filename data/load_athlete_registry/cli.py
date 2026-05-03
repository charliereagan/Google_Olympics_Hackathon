"""CLI entry point for the athlete-registry loader.

Usage:
    python3 -m data.load_athlete_registry.cli --dry-run
    python3 -m data.load_athlete_registry.cli --dataset=storytellers_room_dev
    python3 -m data.load_athlete_registry.cli --dataset=storytellers_room_dev --refresh

Behavior:
    1. Fetch Olympedia (primary) + Wikidata (secondary) + (optional) Team USA roster.
    2. Merge + dedupe + canonicalize.
    3. Save JSON snapshot to ``data/athlete_registry_snapshot/registry.YYYY-MM-DD.json``.
    4. Write NDJSON to ``/tmp/athlete_registry.ndjson``.
    5. If ``--dry-run`` is NOT set, ``bq load`` to ``<dataset>.athlete_registry`` (REPLACE).
    6. Verify row count via ``bq query`` and print sample of 3 rows.
    7. Assert >=500 rows. Exit 1 if fewer (HOE-DEC-019 fail-closed contract).

Never defaults to ``storytellers_room`` (production). HoE handles production load.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from . import fetch_olympedia, fetch_wikidata, merge, write_to_bigquery


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "data" / "athlete_registry_snapshot"
NDJSON_PATH = Path("/tmp/athlete_registry.ndjson")
ATTRIBUTION_PATH = REPO_ROOT / "data" / "athlete_registry_snapshot" / "attribution.latest.json"

MIN_ROWS = 500  # HOE-DEC-019 fail-closed threshold


def _log(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load athlete registry to BigQuery")
    parser.add_argument(
        "--dataset",
        default="storytellers_room_dev",
        choices=["storytellers_room_dev", "storytellers_room"],
        help="BigQuery dataset (default: storytellers_room_dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the bq load step. Produce snapshot + NDJSON only.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download of Olympedia + Wikidata caches.",
    )
    parser.add_argument(
        "--allow-fallback-only",
        action="store_true",
        help="If set and Olympedia+Wikidata both return <500 rows, allow the "
        "fixture fallback to be the sole source. Will still fail the >=500 "
        "threshold; intended for offline testing.",
    )
    args = parser.parse_args(argv)

    if args.dataset == "storytellers_room":
        _log("WARNING: --dataset=storytellers_room targets PRODUCTION.")
        _log("         Per worker contract, the HoE runs the production load.")
        _log("         If this isn't the HoE, abort with Ctrl-C now.")
        # Don't sleep — just print the warning. HoE script can pipe `yes`.

    started_at = time.time()

    # ------------------------------------------------------------------
    # 1. Fetch
    # ------------------------------------------------------------------
    _log("[1/6] Fetching Olympedia (KeithGalli/Olympics-Dataset)...")
    olympedia_records, olympedia_attr = fetch_olympedia.fetch(force_refresh=args.refresh)
    _log(f"      -> {len(olympedia_records)} USA records")

    _log("[2/6] Fetching Wikidata SPARQL...")
    wikidata_records, wikidata_attr = fetch_wikidata.fetch(force_refresh=args.refresh)
    _log(
        f"      -> {wikidata_attr.get('olympic_count', 0)} olympic + "
        f"{wikidata_attr.get('paralympic_count', 0)} paralympic"
    )

    # ------------------------------------------------------------------
    # 2. Merge
    # ------------------------------------------------------------------
    use_fixtures = (
        len(olympedia_records) + len(wikidata_records) < MIN_ROWS
        or args.allow_fallback_only
    )
    fixtures = merge.FALLBACK_FIXTURES if use_fixtures else None
    if use_fixtures:
        _log("      [merge] both network sources thin; including FALLBACK_FIXTURES")

    _log("[3/6] Merging + deduping...")
    records = merge.merge(olympedia_records, wikidata_records, fixtures=fixtures)
    _log(f"      -> {len(records)} unique athletes after dedup")

    # ------------------------------------------------------------------
    # 3. Snapshot + 4. NDJSON
    # ------------------------------------------------------------------
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    snapshot_path = SNAPSHOT_DIR / f"registry.{today}.json"
    _log(f"[4/6] Writing snapshot: {snapshot_path}")
    snapshot_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    attribution = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "row_count": len(records),
        "olympedia": olympedia_attr,
        "wikidata": wikidata_attr,
        "used_fallback_fixtures": use_fixtures,
    }
    ATTRIBUTION_PATH.write_text(
        json.dumps(attribution, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _log(f"      Writing NDJSON: {NDJSON_PATH}")
    n = write_to_bigquery.write_ndjson(records, NDJSON_PATH)
    _log(f"      -> {n} rows in {NDJSON_PATH}")

    # ------------------------------------------------------------------
    # 5. bq load (unless --dry-run)
    # ------------------------------------------------------------------
    if not args.dry_run:
        _log(f"[5/6] bq load --replace -> {args.dataset}.athlete_registry")
        if n < MIN_ROWS:
            _log(
                f"      ABORT: row count {n} is below MIN_ROWS={MIN_ROWS}. "
                "Refusing to load — would put dataset in fail-closed state. "
                "(HOE-DEC-019)"
            )
            return 1
        rc, stderr_tail = write_to_bigquery.bq_load(
            dataset=args.dataset,
            ndjson_path=NDJSON_PATH,
        )
        if rc != 0:
            _log(f"      bq load FAILED (rc={rc}). Stderr tail:\n{stderr_tail}")
            return 1
        _log(f"      bq load OK")

        loaded = write_to_bigquery.bq_count(dataset=args.dataset)
        if loaded is None:
            _log("      [warn] bq query for row count failed; skipping verification")
        else:
            _log(f"      Verified: {loaded} rows in {args.dataset}.athlete_registry")
    else:
        _log("[5/6] --dry-run: skipping bq load")

    # ------------------------------------------------------------------
    # 6. Sample + assert
    # ------------------------------------------------------------------
    _log("[6/6] Sample (3 random records):")
    rng = random.Random(0)
    sample = rng.sample(records, k=min(3, len(records)))
    for s in sample:
        _log(
            f"      - {s['athlete_id']} | {s['full_name']!r} | "
            f"sport={s.get('sport')!r} | kind={s.get('olympic_or_paralympic')!r} | "
            f"era={s.get('era_or_decade')!r} | state={s.get('hometown_state')!r} | "
            f"variants={len(s.get('known_variants', []))}"
        )

    elapsed = time.time() - started_at
    _log(f"\nElapsed: {elapsed:.1f}s")

    if n < MIN_ROWS:
        _log(
            f"\nFAIL-CLOSED ASSERTION: produced {n} rows; need >={MIN_ROWS}. "
            "Per HOE-DEC-019 the agent runtime would refuse to boot. Exit 1."
        )
        return 1

    _log(f"OK: registry has {n} rows (>= {MIN_ROWS}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
