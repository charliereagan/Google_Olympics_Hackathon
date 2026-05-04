"""Scout-side tool surfaces.

The ADK FunctionTool decorator turns these into LLM-callable tools. We keep
the Python signatures compact: each tool is a thin wrapper around a real
implementation (BigQuery, Wire emit, Firestore) so the docstrings end up as
the LLM-facing spec.

If `google.adk` is not importable on this machine (dev box), the file still
loads — `_tool` becomes a passthrough decorator and the tools work as plain
async functions for unit tests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.wire.types import LeadReport, SubAgentId

logger = logging.getLogger(__name__)


# --- ADK FunctionTool adapter -------------------------------------------------


def _tool(_fn=None, **_kwargs):
    """Pass-through decorator that becomes a real ADK FunctionTool when ADK is on the host.

    Day-2 design: agents that wrap these tools at construction time pass them
    to ADK separately; the decorator itself is best-effort. Lazy ADK import.
    """
    def _wrap(fn):
        try:
            from google.adk.tools import FunctionTool  # type: ignore[import-untyped]
            return FunctionTool(fn)
        except ImportError:
            return fn

    if _fn is not None:
        return _wrap(_fn)
    return _wrap


# --- Tools --------------------------------------------------------------------


@_tool
async def grounded_search(
    query: str,
    *,
    bigquery: Any | None = None,  # noqa: ARG001 — Day 3 wires real grounding
) -> dict:
    """Run a Gemini Google Search grounding query.

    Day-2: stub returning an empty result set. Day-3 wires the real grounded
    search tool against `gemini-3-flash-preview` per BUILD_SPEC §3.3.

    Args:
        query: a natural-language search query (must reference places /
            programs / patterns; never a named individual).

    Returns:
        `{"matches": [...], "queried_at": iso_timestamp}`. Empty in Day-2.
    """
    logger.info("grounded_search stub called: query=%r", query)
    return {
        "matches": [],
        "queried_at": datetime.now(timezone.utc).isoformat(),
    }


@_tool
async def query_candidates(
    *,
    region: str | None = None,
    sport: str | None = None,
    bigquery: Any | None = None,  # noqa: ARG001 — Day 3 wires real BQ query
    limit: int = 25,
) -> list[dict]:
    """Query the BigQuery `candidates` table for places / programs / patterns.

    Day-2: stub returning an empty list. Day-3 issues `SELECT ... FROM
    storytellers_room.candidates WHERE ...` per BUILD_SPEC §8.1 schema.

    Args:
        region: optional US region or state filter.
        sport: optional sport name filter (use OFFICIAL sport names, not NGB).
        limit: max rows.

    Returns:
        A list of candidate story-unit dicts. Each is a place / program /
        pattern; never an individual.
    """
    logger.info("query_candidates stub called: region=%r sport=%r limit=%d", region, sport, limit)
    return []


@_tool
async def write_lead_report(
    *,
    scout: SubAgentId,
    story_unit_id: str,
    story_unit_title: str,
    story_unit_type: str,
    signal_type: str,
    confidence: float,
    notes: str,
    evidence_refs: list[str] | None = None,
    firestore: Any | None = None,
    hnd_detector: Any | None = None,
) -> str:
    """Persist a Scout Lead Report to Firestore `/lead_reports/{id}`.

    Args:
        scout: which sub-scout authored this report.
        story_unit_id: stable id (places/programs/patterns are the ONLY
            valid story units; never an athlete id).
        story_unit_title: short human title for the place / program / pattern.
        story_unit_type: 'place' | 'program' | 'pattern'.
        signal_type: short label describing the signal that produced this
            lead (e.g., 'cinderella-disproportionate', 'comeback-return').
        confidence: 0.0-1.0.
        notes: text body, NEVER names an individual athlete.
        evidence_refs: optional source URLs / corpus refs.

    Returns:
        The Firestore doc id.
    """
    report_id = str(uuid4())
    doc = {
        "id": report_id,
        "story_unit_id": story_unit_id,
        "story_unit_title": story_unit_title,
        "story_unit_type": story_unit_type,
        "scout": scout,
        "signal_type": signal_type,
        "confidence": confidence,
        "notes": notes,
        "evidence_refs": list(evidence_refs or []),
        "status": "investigating",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if firestore is not None and hasattr(firestore, "collection"):
        try:
            res = firestore.collection("lead_reports").add(doc)
            # Some clients return awaitable; some return tuple directly.
            if hasattr(res, "__await__"):
                await res
        except Exception:
            logger.exception("write_lead_report: firestore write failed")
    if hnd_detector is not None:
        try:
            await hnd_detector.record_lead_report(LeadReport(
                id=report_id,
                story_unit_id=story_unit_id,
                story_unit_title=story_unit_title,
                story_unit_type=story_unit_type,  # type: ignore[arg-type]
                scout=scout,
                signal_type=signal_type,
                confidence=confidence,
                notes=notes,
                evidence_refs=list(evidence_refs or []),
            ))
        except Exception:
            logger.exception("write_lead_report: hnd_detector record failed")
    return report_id
