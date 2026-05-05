#!/usr/bin/env python3
"""Probe: full Editor → Investigator → Storyteller → Publish Gate → Narrator
chain against live infrastructure.

Costs ~$0.50–1.00 per run (Pro deliberation + grounded search +
multiple Pro / Flash-Lite calls + image generation + TTS audio for
~25 sentences). **Skip on $300 budget alert.** The HoE runs this
post-deploy; workers must NOT run this script.

What it does
------------
1. POSTs `/api/investigate` with `{prompt, compression_factor=1.0,
   source='probe'}` to a running uvicorn (default
   `http://localhost:8080`; override via `--url`). Captures the
   `investigation_id` returned by the API.
2. Polls Firestore every 30s for the four chain milestones:
     - `lead_reports`           — first lead within 60s
     - `investigation_packets`  — first packet within 5min
     - `story_drafts`           — first draft within 7min
     - `publish_audits`         — first audit within 9min
   plus narrator-rendered audio in
   `gs://storytellers-room-audio/{story_id}/`.
3. Prints a chronological timeline with absolute timestamps and
   elapsed seconds since the POST.
4. Final report:
     - PASS if all 4 stages produced docs within the budget.
     - FAIL with the specific stage that didn't complete.
5. Cleanup (`--cleanup`, default OFF): delete the synthetic
   investigation's docs from Firestore + GCS.

This script does NOT modify production data outside the investigation
namespace produced by `/api/investigate`. The `investigation_id` is
the boundary; cleanup uses it.

Prerequisites
-------------
- The agent-runtime must be running (locally via
  `python -m agents.runtime` or deployed on Cloud Run).
- `GOOGLE_CLOUD_PROJECT` env var set (default
  `predictive-fx-495200-j4`).
- ADC available (`gcloud auth application-default login`).
- `google-cloud-firestore` + `google-cloud-storage` + `httpx` installed.

Usage
-----
    python3 scripts/probe_full_chain.py
    python3 scripts/probe_full_chain.py --dry-run
    python3 scripts/probe_full_chain.py --url http://my-cloud-run/...
    python3 scripts/probe_full_chain.py --timeout-min 12 --cleanup

Exit codes
----------
    0 — all four stages green
    1 — partial completion (one or more stages timed out)
    2 — POST /api/investigate failed (4xx/5xx)
    3 — runtime not reachable (connection error)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("probe_full_chain")


# --- Defaults & constants ---------------------------------------------------

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "predictive-fx-495200-j4")
DEFAULT_URL = "http://localhost:8080"
DEFAULT_PROMPT = "Find me a Team USA hometown story I have not heard before"
DEFAULT_TIMEOUT_MIN = 10
DEFAULT_AUDIO_BUCKET = "storytellers-room-audio"

# Polling cadence + per-stage budgets (seconds since POST).
POLL_INTERVAL_S = 30
TIMEOUT_LEAD_S = 60
TIMEOUT_PACKET_S = 300
TIMEOUT_DRAFT_S = 420
TIMEOUT_AUDIT_S = 540
# The audio check uses the same budget as the audit; once the audit
# clears, the narrator typically renders within 30-60s.
TIMEOUT_AUDIO_S = 600


# --- POST /api/investigate --------------------------------------------------


async def post_investigate(
    url: str,
    prompt: str,
    *,
    timeout_s: float = 30.0,
    compression_factor: float = 1.0,
) -> dict:
    """POST /api/investigate. Returns the JSON body or raises.

    The agent-runtime returns 202 with `{investigation_id, ...}`.
    """
    try:
        import httpx  # type: ignore[import-untyped]
    except ImportError as e:
        raise RuntimeError(
            "httpx not installed; pip install -r requirements.txt"
        ) from e

    payload = {
        "prompt": prompt,
        "compression_factor": compression_factor,
        "source": "probe",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            resp = await client.post(f"{url.rstrip('/')}/api/investigate", json=payload)
        except httpx.ConnectError as e:
            raise ConnectionError(f"agent-runtime not reachable at {url}: {e}") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"http error posting to {url}: {e}") from e

    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"POST /api/investigate failed: status={resp.status_code} body={resp.text[:300]}"
        )
    try:
        body = resp.json()
    except Exception as e:  # pragma: no cover — defensive
        raise RuntimeError(f"invalid JSON response from /api/investigate: {e}") from e

    if not isinstance(body, dict) or not body.get("investigation_id"):
        raise RuntimeError(
            f"missing investigation_id in /api/investigate response: {body!r}"
        )
    return body


# --- Firestore polling ------------------------------------------------------


def _build_firestore_client() -> Any:
    """Construct a sync Firestore client, exit 1 on import/auth failure."""
    try:
        from google.cloud import firestore  # type: ignore[import-untyped]
    except ImportError:
        print(
            "FAIL: google-cloud-firestore not installed; pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return firestore.Client(project=PROJECT)
    except Exception as e:
        print(f"FAIL: Firestore client construction failed: {e}", file=sys.stderr)
        sys.exit(1)


def _build_storage_client() -> Any:
    """Construct a sync Storage client. Returns None if not available
    (audio listing is best-effort)."""
    try:
        from google.cloud import storage  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        return storage.Client(project=PROJECT)
    except Exception as e:
        logger.warning("storage client construction failed: %s", e)
        return None


def _query_first_doc(
    fs: Any,
    collection: str,
    *,
    investigation_id: str | None,
) -> dict | None:
    """One-shot query: any doc matching investigation_id (or any doc if
    None), return its dict or None.

    Falls back to a stream when filtering isn't supported by the
    collection (defensive — the production schema does have
    investigation_id on lead_reports / packets / drafts).
    """
    try:
        from google.cloud.firestore_v1.base_query import (  # type: ignore[import-untyped]
            FieldFilter,
        )
    except ImportError:
        FieldFilter = None  # type: ignore[assignment]

    coll = fs.collection(collection)
    docs: list[Any] = []
    try:
        if investigation_id is not None and FieldFilter is not None:
            q = coll.where(filter=FieldFilter("investigation_id", "==", investigation_id))
            try:
                q = q.limit(1)
            except Exception:
                pass
            docs = list(q.stream())
        elif investigation_id is not None:
            q = coll.where("investigation_id", "==", investigation_id)
            docs = list(q.stream())
        else:
            docs = list(coll.limit(1).stream())
    except Exception as e:
        logger.debug("firestore query failed for %s: %s", collection, e)
        return None

    if not docs:
        return None
    snap = docs[0]
    try:
        d = snap.to_dict() or {}
    except Exception:
        return None
    d.setdefault("__doc_id__", getattr(snap, "id", None))
    return d


async def poll_for_doc(
    fs: Any,
    collection: str,
    *,
    investigation_id: str | None,
    timeout_s: int,
    started_at: float,
    poll_interval_s: int = POLL_INTERVAL_S,
) -> tuple[bool, dict | None, float]:
    """Poll until a matching doc shows up or `timeout_s` elapses.

    Returns `(found, doc_dict, elapsed_seconds_since_started_at)`.
    """
    deadline = started_at + timeout_s
    while True:
        doc = _query_first_doc(fs, collection, investigation_id=investigation_id)
        elapsed = time.monotonic() - started_at
        if doc is not None:
            return True, doc, elapsed
        if time.monotonic() >= deadline:
            return False, None, elapsed
        # Sleep until the next interval or the deadline, whichever comes
        # first.
        sleep_s = min(poll_interval_s, max(0.1, deadline - time.monotonic()))
        await asyncio.sleep(sleep_s)


def _list_audio_blobs(
    storage_client: Any,
    *,
    bucket_name: str,
    story_id: str,
) -> list[str]:
    """Return the names of any blobs under `gs://{bucket}/{story_id}/`.

    Empty list = nothing rendered yet (or storage_client unavailable).
    """
    if storage_client is None:
        return []
    try:
        bucket = storage_client.bucket(bucket_name)
        prefix = f"{story_id}/"
        return [b.name for b in bucket.list_blobs(prefix=prefix, max_results=10)]
    except Exception as e:
        logger.debug("storage list failed for %s/%s: %s", bucket_name, story_id, e)
        return []


# --- Cleanup ----------------------------------------------------------------


def _cleanup(
    fs: Any,
    storage_client: Any,
    *,
    investigation_id: str,
    story_ids: list[str],
    audio_bucket: str,
) -> None:
    """Best-effort cleanup. Logs failures; never raises."""
    print(f"probe_full_chain: cleaning up investigation_id={investigation_id} ...")
    for collection in (
        "lead_reports",
        "investigation_packets",
        "story_drafts",
        "publish_audits",
        "wire_events",
    ):
        try:
            from google.cloud.firestore_v1.base_query import (  # type: ignore[import-untyped]
                FieldFilter,
            )
            q = fs.collection(collection).where(
                filter=FieldFilter("investigation_id", "==", investigation_id)
            )
        except ImportError:
            q = fs.collection(collection).where(
                "investigation_id", "==", investigation_id
            )
        try:
            for snap in q.stream():
                try:
                    snap.reference.delete()
                except Exception as e:
                    logger.warning("cleanup: %s/%s delete failed: %s", collection, snap.id, e)
        except Exception as e:
            logger.warning("cleanup: %s query failed: %s", collection, e)

    if storage_client is not None:
        for sid in story_ids:
            try:
                bucket = storage_client.bucket(audio_bucket)
                for blob in bucket.list_blobs(prefix=f"{sid}/", max_results=50):
                    try:
                        blob.delete()
                    except Exception as e:
                        logger.warning("cleanup: gs://%s/%s delete failed: %s",
                                       audio_bucket, blob.name, e)
            except Exception as e:
                logger.warning("cleanup: storage list-or-delete failed: %s", e)


# --- Stage timeline ---------------------------------------------------------


@dataclass
class StageResult:
    name: str
    found: bool
    elapsed_s: float
    doc: dict | None = None


def _print_stage(stage: StageResult, *, started_iso: str) -> None:
    status = "OK" if stage.found else "TIMEOUT"
    line = (
        f"  [{status}] stage={stage.name:<22s} elapsed={stage.elapsed_s:6.1f}s "
        f"(since POST @ {started_iso})"
    )
    if stage.found and stage.doc is not None:
        doc_id = stage.doc.get("__doc_id__") or stage.doc.get("id")
        story = stage.doc.get("story_unit_id") or stage.doc.get("story_id")
        line += f" doc_id={doc_id} story_unit_id={story}"
    print(line)


# --- argparse ---------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"target uvicorn URL (default: {DEFAULT_URL})",
    )
    p.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help=f"seed prompt (default: {DEFAULT_PROMPT!r})",
    )
    p.add_argument(
        "--timeout-min",
        type=float,
        default=DEFAULT_TIMEOUT_MIN,
        help=f"total budget in minutes (default: {DEFAULT_TIMEOUT_MIN})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="only POST, don't poll Firestore or print a final report",
    )
    p.add_argument(
        "--cleanup",
        action="store_true",
        help="delete probe artifacts on exit (lead_reports, "
        "investigation_packets, story_drafts, publish_audits, wire_events, audio)",
    )
    p.add_argument(
        "--audio-bucket",
        default=DEFAULT_AUDIO_BUCKET,
        help=f"GCS bucket for narration audio (default: {DEFAULT_AUDIO_BUCKET})",
    )
    p.add_argument(
        "--compression-factor",
        type=float,
        default=1.0,
        help="compression factor for the synthetic investigation (default: 1.0)",
    )
    return p.parse_args(argv)


# --- main entrypoint --------------------------------------------------------


async def _async_main(args: argparse.Namespace) -> int:
    print(f"probe_full_chain: project={PROJECT} url={args.url}")
    print(f"probe_full_chain: prompt={args.prompt!r}")
    print(f"probe_full_chain: timeout_min={args.timeout_min}  cleanup={args.cleanup}")
    print(
        "probe_full_chain: NOTE — costs roughly $0.50-$1.00 per run "
        "(Pro + grounded search + Flash-Lite + image gen + TTS). "
        "Skip on $300 budget alert."
    )

    started_at = time.monotonic()
    started_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1. POST /api/investigate.
    try:
        body = await post_investigate(
            args.url,
            args.prompt,
            compression_factor=args.compression_factor,
        )
    except ConnectionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 3
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    investigation_id = body["investigation_id"]
    print(f"probe_full_chain: investigation_id={investigation_id}")

    if args.dry_run:
        print("probe_full_chain: --dry-run set; skipping polling + report.")
        return 0

    # 2. Build clients for polling.
    fs = _build_firestore_client()
    storage_client = _build_storage_client()

    # 3. Poll each stage in turn. Each stage's budget runs from the
    # POST time so a slow earlier stage doesn't extend later budgets
    # arbitrarily.
    stages: list[StageResult] = []

    timeout_total_s = int(args.timeout_min * 60)
    # Cap each per-stage budget at the user-supplied total.
    per_stage = (
        ("lead_reports", min(TIMEOUT_LEAD_S, timeout_total_s)),
        ("investigation_packets", min(TIMEOUT_PACKET_S, timeout_total_s)),
        ("story_drafts", min(TIMEOUT_DRAFT_S, timeout_total_s)),
        ("publish_audits", min(TIMEOUT_AUDIT_S, timeout_total_s)),
    )

    for collection, timeout_s in per_stage:
        print(f"probe_full_chain: polling {collection} (budget {timeout_s}s) ...")
        found, doc, elapsed = await poll_for_doc(
            fs,
            collection,
            investigation_id=investigation_id,
            timeout_s=timeout_s,
            started_at=started_at,
        )
        result = StageResult(name=collection, found=found, elapsed_s=elapsed, doc=doc)
        stages.append(result)
        _print_stage(result, started_iso=started_iso)
        if not found:
            # No point polling later stages — they depend on this one.
            break

    # 4. If the audit landed, also check audio. Best-effort; not pass-
    # gating because the audio path is independent of the audit.
    audio_blobs: list[str] = []
    story_ids: list[str] = []
    audit_stage = next(
        (s for s in stages if s.name == "publish_audits" and s.found),
        None,
    )
    if audit_stage is not None and audit_stage.doc is not None:
        story_id = (
            audit_stage.doc.get("story_id")
            or audit_stage.doc.get("__doc_id__")
        )
        if story_id:
            story_ids.append(story_id)
            audio_blobs = _list_audio_blobs(
                storage_client,
                bucket_name=args.audio_bucket,
                story_id=story_id,
            )
            if audio_blobs:
                print(
                    f"  [OK] stage=audio_render          "
                    f"audio_blobs={len(audio_blobs)} story_id={story_id}"
                )
            else:
                print(
                    f"  [INFO] stage=audio_render        "
                    f"no audio yet under gs://{args.audio_bucket}/{story_id}/"
                )

    # 5. Final report.
    print()
    all_green = all(s.found for s in stages) and len(stages) == 4
    if all_green:
        print(
            f"PASS: full chain green — investigation_id={investigation_id} "
            f"total_elapsed={time.monotonic() - started_at:.1f}s"
        )
        rc = 0
    else:
        first_fail = next((s for s in stages if not s.found), None)
        print(
            f"FAIL: chain stalled at stage="
            f"{first_fail.name if first_fail else '<unknown>'} "
            f"investigation_id={investigation_id} "
            f"total_elapsed={time.monotonic() - started_at:.1f}s",
            file=sys.stderr,
        )
        rc = 1

    # 6. Cleanup.
    if args.cleanup:
        _cleanup(
            fs,
            storage_client,
            investigation_id=investigation_id,
            story_ids=story_ids,
            audio_bucket=args.audio_bucket,
        )

    return rc


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = _parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nprobe_full_chain: interrupted", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
