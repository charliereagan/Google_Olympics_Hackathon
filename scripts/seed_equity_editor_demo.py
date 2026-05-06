#!/usr/bin/env python3
"""Seed wire_events for demo moment #3 ("the Equity Editor caused the anchor story").

Writes a 10-event arc culminating in an Equity Editor INTERVENTION that
re-routes the room to a Paralympic-anchored Birmingham, Alabama lead.
Birmingham is the Floor's `INTERVENTION_NODE_ID` (web/lib/floor-fixture.ts),
so the agitos-red pulse fires on the right node.

Every Wire write goes through `agents.wire.emit.WireEmitter.emit` — never
direct `firestore.add('wire_events', ...)`. The proxy invokes the NIL
Redaction Layer in-process (HOE-DEC-018, CI-lint contract).

Usage
-----
    source .venv/bin/activate
    python scripts/seed_equity_editor_demo.py
    python scripts/seed_equity_editor_demo.py --purge   # delete and exit

Idempotent: each run purges prior `demo-equity-edit-001` events first.
Requires ADC and the BigQuery `athlete_registry` (>=500 rows).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.wire.emit import WireEmitter  # noqa: E402

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "predictive-fx-495200-j4")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
INVESTIGATION_ID = "demo-equity-edit-001"
STORY_UNIT_ID = "birmingham-al"  # matches floor-fixture.ts INTERVENTION_NODE_ID
logger = logging.getLogger("seed_equity_editor_demo")

# (agent, sub_agent, message_type, message). The clock advances 2s per emit.
ARC: list[tuple[str, str | None, str, str]] = [
    ("editor", None, "thinking",
     "Scanning the published feed. Last 4 places trend Olympic-heavy. "
     "Need a Paralympic-anchored lead to balance the run."),
    ("scout_desk", "hometown", "thinking",
     "Birmingham, Alabama keeps surfacing. Adaptive cycling and wheelchair "
     "rugby programs both rooted in the same metro since 1996."),
    ("investigator", None, "thinking",
     "Pulling sources on the Birmingham adaptive sports footprint — city "
     "parks records, university partnership filings, NGB program rosters."),
    ("equity_editor", None, "intervention",
     "Feed drift detected. Last 4 places Olympic-heavy. "
     "Promoting Paralympic-anchored lead next."),
    ("editor", None, "decision",
     "Re-routing. Investigator, dispatch on the Birmingham adaptive "
     "program lead. Ninety seconds."),
    ("investigator", None, "thinking",
     "Confirming the Birmingham adaptive program timeline against city "
     "records and the Alabama state athletic association archive."),
    ("investigator", None, "milestone",
     "Adaptive sport program founded 2004 in Birmingham. Three counties "
     "served. First Paralympian sent to Games in the 2020 cycle."),
    ("storyteller", None, "thinking",
     "Drafting opening on the Birmingham adaptive program. Anchoring on "
     "the place and the program continuity, not the individual."),
    ("publish_gate", None, "milestone",
     "Twelve claims checked. Zero redacted. NIL Layer cleared."),
    ("editor", None, "milestone",
     "Published. Queue updated. Birmingham adaptive program is the new anchor."),
]


def _build_async_firestore():
    from google.cloud import firestore  # type: ignore[import-untyped]
    return firestore.AsyncClient(project=PROJECT)


def _build_sync_firestore():
    from google.cloud import firestore  # type: ignore[import-untyped]
    return firestore.Client(project=PROJECT)


def _bootstrap_nil_layer():
    """Real NIL Layer from BigQuery `athlete_registry` (HOE-DEC-019)."""
    from google.cloud import bigquery  # type: ignore[import-untyped]

    from agents.publish_gate.nil_redaction_layer import NilRedactionLayer

    bq = bigquery.Client(project=PROJECT)
    return NilRedactionLayer.bootstrap(
        bq,
        dataset=os.environ.get("ATHLETE_REGISTRY_DATASET", "storytellers_room"),
        table=os.environ.get("ATHLETE_REGISTRY_TABLE", "athlete_registry"),
        min_rows=int(os.environ.get("ATHLETE_REGISTRY_MIN_ROWS", "500")),
    )


def _purge_existing(fs_sync, *, investigation_id: str) -> int:
    try:
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
        q = fs_sync.collection("wire_events").where(
            filter=FieldFilter("investigation_id", "==", investigation_id)
        )
    except ImportError:
        q = fs_sync.collection("wire_events").where(
            "investigation_id", "==", investigation_id
        )
    deleted = 0
    for snap in q.stream():
        try:
            snap.reference.delete()
            deleted += 1
        except Exception as e:  # pragma: no cover
            logger.warning("purge: delete failed for %s: %s", snap.id, e)
    return deleted


async def _seed(*, purge_only: bool) -> int:
    fs_sync = _build_sync_firestore()
    purged = _purge_existing(fs_sync, investigation_id=INVESTIGATION_ID)
    print(f"seed: purged {purged} prior event(s) for investigation_id={INVESTIGATION_ID}")
    if purge_only:
        return 0

    nil_layer = _bootstrap_nil_layer()
    print(f"seed: NIL Layer loaded ({getattr(nil_layer, 'registry_size', '?')} rows)")

    fs_async = _build_async_firestore()

    # Controllable clock — 2s steps so events sort deterministically.
    base = datetime.now(timezone.utc)
    step = timedelta(seconds=2)
    counter = {"i": 0}

    def clock() -> datetime:
        i = counter["i"]
        counter["i"] += 1
        return base + step * i

    emitter = WireEmitter(fs_async, nil_layer, clock=clock)

    for idx, (agent, sub_agent, msg_type, message) in enumerate(ARC, start=1):
        event: dict = {
            "agent": agent,
            "message": message,
            "message_type": msg_type,
            "mode": "live",
            "story_unit_id": STORY_UNIT_ID,
            "investigation_id": INVESTIGATION_ID,
        }
        if sub_agent is not None:
            event["sub_agent"] = sub_agent
        doc_id = await emitter.emit(event, investigation_id=INVESTIGATION_ID)
        print(
            f"  [{idx:2d}/{len(ARC)}] {msg_type:12s} {agent:14s} "
            f"sub={sub_agent or '-':9s} doc_id={doc_id}"
        )

    print(f"seed: wrote {len(ARC)} event(s) for investigation_id={INVESTIGATION_ID}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--purge", action="store_true", help="delete prior demo events and exit")
    args = p.parse_args(argv)
    return asyncio.run(_seed(purge_only=args.purge))


if __name__ == "__main__":
    sys.exit(main())
