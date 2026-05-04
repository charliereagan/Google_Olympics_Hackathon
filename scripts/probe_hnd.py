#!/usr/bin/env python3
"""Probe: artificially fire HND by writing 3 lead reports + verify milestone.

Why this exists
---------------
Day-3 closed out with the Editor -> Scout Desk -> wire.emit cycle live against
GCP, but production logs do NOT yet contain evidence that an HND fire actually
emits a milestone Wire event when the threshold (HOE-DEC-023: >=3 of 4 Scouts
on the same `story_unit_id` within a 10-min window with each >=0.7 confidence)
is crossed.

This probe is the operational check the HoE runs after a deploy to confirm
HND firing end-to-end against the real Firestore + the running agent-runtime.

What it does
------------
1. Generates a unique synthetic `story_unit_id` (e.g. `hnd-probe-abc12345`)
   so the candidate space is never polluted with probe data.
2. Writes 3 Lead Reports to `lead_reports`, each from a different scout
   (cinderella, comeback, hometown) with confidence 0.8.
3. Polls `wire_events` (filtered to `message_type='milestone'` AND message
   containing 'High Narrative Density' AND matching `story_unit_id`) for up
   to ~30 seconds; the running agent-runtime's HND `on_snapshot` listener
   should observe the lead reports and emit the milestone via `wire.emit`.
4. Prints PASS/FAIL with timing.
5. Best-effort cleanup: deletes the 3 lead reports and the milestone wire
   event. Cleanup failures are logged but never fail the probe.

Importantly, this script does NOT call `wire.emit()` directly (which would
require booting the runtime in-process and running the NIL Layer locally).
It writes to `lead_reports` and lets the running agent-runtime's HND
listener do its job — that's the whole point of the probe.

Prerequisites
-------------
- The agent-runtime must be running (locally via `python -m agents.runtime`
  or deployed on Cloud Run); without it, the HND `on_snapshot` listener
  isn't observing `lead_reports` and the milestone never lands.
- `GOOGLE_CLOUD_PROJECT` env var set (default: predictive-fx-495200-j4).
- ADC available (`gcloud auth application-default login`).
- `google-cloud-firestore` installed.

Usage
-----
    python3 scripts/probe_hnd.py
    python3 scripts/probe_hnd.py --dry-run          # write nothing, just plan
    python3 scripts/probe_hnd.py --timeout 60       # poll wire_events longer
    python3 scripts/probe_hnd.py --skip-cleanup     # leave probe docs behind
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("probe_hnd")


# Same scout names the production HND detector recognizes.
_PROBE_SCOUTS: list[str] = ["cinderella", "comeback", "hometown"]
_PROBE_CONFIDENCE: float = 0.8

# Default probe budget: 30s poll for the milestone.
_DEFAULT_TIMEOUT_SECONDS: float = 30.0
_POLL_INTERVAL_SECONDS: float = 1.0


def _build_firestore_client() -> object:
    """Construct a Firestore sync client. Exits 1 on import/auth failure."""
    try:
        from google.cloud import firestore  # type: ignore[import-untyped]
    except ImportError:
        print(
            "FAIL: google-cloud-firestore not installed; pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return firestore.Client()
    except Exception as e:
        print(f"FAIL: Firestore client construction failed: {e}", file=sys.stderr)
        sys.exit(1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_lead_reports(
    fs: object, story_unit_id: str, *, dry_run: bool
) -> list[str]:
    """Write 3 Lead Reports to /lead_reports/. Returns the doc ids written.

    Schema follows BUILD_SPEC §8.3 / agents.wire.types.LeadReport — the same
    shape Scouts produce in production.
    """
    written_ids: list[str] = []
    for scout in _PROBE_SCOUTS:
        doc = {
            "id": f"{story_unit_id}-{scout}-{uuid.uuid4().hex[:6]}",
            "story_unit_id": story_unit_id,
            "story_unit_title": f"HND probe synthetic place ({story_unit_id})",
            "story_unit_type": "place",
            "scout": scout,
            "signal_type": "probe",
            "confidence": _PROBE_CONFIDENCE,
            "notes": (
                "synthetic HND probe lead report — NOT a real candidate. "
                f"probe_run_id={story_unit_id}"
            ),
            "evidence_refs": [],
            "status": "investigating",
            "created_at": _now_iso(),
            # Mark the doc so cleanup can identify probe writes unambiguously.
            "probe": True,
            "probe_run_id": story_unit_id,
        }
        if dry_run:
            print(f"  [dry-run] would write lead_reports/<auto> scout={scout}")
            written_ids.append(f"<dry-run-{scout}>")
            continue
        _, doc_ref = fs.collection("lead_reports").add(doc)  # type: ignore[attr-defined]
        written_ids.append(doc_ref.id)
        print(f"  wrote lead_reports/{doc_ref.id} scout={scout}")
    return written_ids


def _poll_for_milestone(
    fs: object, story_unit_id: str, *, timeout_seconds: float
) -> tuple[bool, float, str | None]:
    """Poll `wire_events` for the milestone HND event for this story_unit_id.

    Returns `(found, elapsed_seconds, wire_event_doc_id_or_None)`.
    """
    deadline = time.monotonic() + timeout_seconds
    started = time.monotonic()
    while time.monotonic() < deadline:
        # Filter as narrowly as possible to keep the read cheap. The Firestore
        # Python SDK's Query.where API has had a few iterations; we use the
        # FieldFilter form when available and fall back to the legacy form.
        try:
            from google.cloud.firestore_v1.base_query import (  # type: ignore[import-untyped]
                FieldFilter,
            )
            q = (
                fs.collection("wire_events")  # type: ignore[attr-defined]
                .where(filter=FieldFilter("story_unit_id", "==", story_unit_id))
                .where(filter=FieldFilter("message_type", "==", "milestone"))
            )
        except ImportError:
            q = (
                fs.collection("wire_events")  # type: ignore[attr-defined]
                .where("story_unit_id", "==", story_unit_id)
                .where("message_type", "==", "milestone")
            )
        for snap in q.stream():
            d = snap.to_dict() or {}
            msg = d.get("message", "")
            if "High Narrative Density" in msg:
                return True, time.monotonic() - started, snap.id
        time.sleep(_POLL_INTERVAL_SECONDS)
    return False, time.monotonic() - started, None


def _cleanup(
    fs: object,
    *,
    story_unit_id: str,
    lead_report_ids: list[str],
    milestone_id: str | None,
) -> None:
    """Best-effort cleanup. Logs but never raises."""
    for lid in lead_report_ids:
        try:
            fs.collection("lead_reports").document(lid).delete()  # type: ignore[attr-defined]
        except Exception as e:
            print(f"  cleanup: lead_reports/{lid} delete failed: {e}", file=sys.stderr)
    if milestone_id is not None:
        try:
            fs.collection("wire_events").document(milestone_id).delete()  # type: ignore[attr-defined]
        except Exception as e:
            print(
                f"  cleanup: wire_events/{milestone_id} delete failed: {e}",
                file=sys.stderr,
            )
    # Also clean up any /hnd_fires/ paper-trail rows for this probe.
    try:
        from google.cloud.firestore_v1.base_query import (  # type: ignore[import-untyped]
            FieldFilter,
        )
        fires_q = fs.collection("hnd_fires").where(  # type: ignore[attr-defined]
            filter=FieldFilter("story_unit_id", "==", story_unit_id)
        )
    except ImportError:
        fires_q = fs.collection("hnd_fires").where(  # type: ignore[attr-defined]
            "story_unit_id", "==", story_unit_id
        )
    try:
        for snap in fires_q.stream():
            try:
                snap.reference.delete()
            except Exception as e:
                print(
                    f"  cleanup: hnd_fires/{snap.id} delete failed: {e}",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"  cleanup: hnd_fires query failed: {e}", file=sys.stderr)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="do not write to Firestore — just print what would happen",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT_SECONDS,
        help=f"seconds to poll wire_events for the milestone (default: {_DEFAULT_TIMEOUT_SECONDS})",
    )
    p.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="leave the 3 lead_reports + milestone wire_event in place",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = _parse_args(argv)

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "predictive-fx-495200-j4")
    print(f"probe_hnd: project={project}")
    if args.dry_run:
        print("probe_hnd: DRY-RUN (no Firestore writes)")

    story_unit_id = f"hnd-probe-{uuid.uuid4().hex[:8]}"
    print(f"probe_hnd: story_unit_id={story_unit_id}")
    print(f"probe_hnd: scouts={_PROBE_SCOUTS} confidence={_PROBE_CONFIDENCE}")
    print(
        "probe_hnd: NOTE — requires the agent-runtime to be running so the HND "
        "on_snapshot listener can observe the lead_reports writes."
    )

    fs = _build_firestore_client() if not args.dry_run else None
    if args.dry_run:
        # Stage one (writes) only, then exit cleanly.
        _write_lead_reports(object(), story_unit_id, dry_run=True)
        print("probe_hnd: dry-run complete; no polling, no cleanup.")
        return 0

    # 1. Write 3 Lead Reports.
    t0 = time.monotonic()
    print("probe_hnd: writing 3 lead reports...")
    try:
        lead_ids = _write_lead_reports(fs, story_unit_id, dry_run=False)
    except Exception as e:
        print(f"FAIL: lead_reports writes failed: {e}", file=sys.stderr)
        return 2

    # 2. Poll wire_events for the milestone.
    print(f"probe_hnd: polling wire_events for milestone (timeout={args.timeout:.0f}s)...")
    found, elapsed, milestone_id = _poll_for_milestone(
        fs, story_unit_id, timeout_seconds=args.timeout
    )
    total_elapsed = time.monotonic() - t0

    # 3. Cleanup (best-effort).
    if not args.skip_cleanup:
        print("probe_hnd: cleaning up probe documents...")
        _cleanup(
            fs,
            story_unit_id=story_unit_id,
            lead_report_ids=lead_ids,
            milestone_id=milestone_id,
        )
    else:
        print("probe_hnd: --skip-cleanup set; leaving probe docs behind")

    # 4. Report.
    if found:
        print(
            f"PASS: HND milestone landed in {elapsed:.2f}s "
            f"(total probe runtime: {total_elapsed:.2f}s, wire_event_id={milestone_id})"
        )
        return 0
    else:
        print(
            f"FAIL: no HND milestone observed within {args.timeout:.0f}s "
            f"(total probe runtime: {total_elapsed:.2f}s) — is agent-runtime running?",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
