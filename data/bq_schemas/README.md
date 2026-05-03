# BigQuery schemas

Schemas for the seven BigQuery tables in `storytellers_room` (production) and `storytellers_room_dev` (local dev mirror). Both datasets live in `US` multi-region in project `predictive-fx-495200-j4`.

| Table | Purpose |
|---|---|
| `candidates.json` | Story unit pool — places, programs, patterns. Aggregate counts only; `contributing_athlete_ids` is INTERNAL and never reaches user-facing surfaces. |
| `athlete_registry.json` | The NIL Redaction Layer's source of truth. Loaded from Olympedia public CSVs (filtered NOC=USA) + Wikidata SPARQL cross-reference + Team USA roster. ≥500 rows asserted on agent runtime startup or runtime exits 1 (HOE-DEC-019). |
| `historical_athletes.json` | Team USA-only athlete records. Placement (1, 2, 3) + medal allowed. **NO finish times, NO scoring data per PROJECT_BRIEF §6.** |
| `geography.json` | Hometown city/state/region/population/lat/lon for the place stories. |
| `championships.json` | Championship placement counts only. Same finish-time / scoring prohibition as `historical_athletes`. |
| `agent_call_counters.json` | Per-day per-axis call/token/cost tracking. Per-axis ceilings enforced by tool wrappers (BUILD_SPEC §15.3). |
| `agent_errors.json` | Failure-mode logging (BUILD_SPEC §17). Each retry / fallback path writes one row. |

## Recreate / re-apply

```bash
PROJECT=predictive-fx-495200-j4
DS=storytellers_room
for TABLE in candidates athlete_registry historical_athletes geography championships agent_call_counters agent_errors; do
  bq --project_id=$PROJECT mk --table --schema=$TABLE.json $DS.$TABLE
done
```

## Schema changes

Edit the JSON file in this directory, then run:

```bash
bq update --project_id=$PROJECT --schema=$TABLE.json $DS.$TABLE
```

Note: BigQuery only allows additive schema changes (adding nullable fields). Field removal or type changes require a new table + migration.
