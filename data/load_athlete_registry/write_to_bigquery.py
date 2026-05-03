"""Write the merged registry to BigQuery via subprocess ``bq load``.

Default target dataset is ``storytellers_room_dev``. The HoE explicitly
performs the production load against ``storytellers_room`` after reviewing
the dev output. This module never defaults to production.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "data" / "bq_schemas" / "athlete_registry.json"
PROJECT_ID = "predictive-fx-495200-j4"


def write_ndjson(records: Iterable[dict], out_path: Path) -> int:
    """Serialize ``records`` to NEWLINE_DELIMITED_JSON. Returns row count."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def bq_load(
    *,
    dataset: str,
    table: str = "athlete_registry",
    ndjson_path: Path,
    project_id: str = PROJECT_ID,
    schema_path: Path | None = None,
) -> tuple[int, str]:
    """Invoke ``bq load`` with REPLACE semantics. Returns (returncode, stderr_tail)."""
    if shutil.which("bq") is None:
        return (127, "bq not found on PATH")
    if schema_path is None:
        schema_path = SCHEMA_PATH
    cmd = [
        "bq",
        "load",
        f"--project_id={project_id}",
        "--source_format=NEWLINE_DELIMITED_JSON",
        "--replace",
        f"{dataset}.{table}",
        str(ndjson_path),
        str(schema_path),
    ]
    print(f"  [bq] {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
    else:
        sys.stdout.write(proc.stdout)
    return (proc.returncode, (proc.stderr or "")[-2000:])


def bq_count(
    *,
    dataset: str,
    table: str = "athlete_registry",
    project_id: str = PROJECT_ID,
) -> int | None:
    """Run ``bq query`` for COUNT(*). Returns int on success, None on failure."""
    if shutil.which("bq") is None:
        return None
    cmd = [
        "bq",
        "query",
        f"--project_id={project_id}",
        "--use_legacy_sql=false",
        "--format=csv",
        "--quiet",
        f"SELECT COUNT(*) AS n FROM {dataset}.{table}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return None
    out = (proc.stdout or "").strip().splitlines()
    # Output looks like:  n\n12345
    if len(out) >= 2:
        try:
            return int(out[-1])
        except ValueError:
            return None
    return None
