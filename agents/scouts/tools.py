"""Scout-side tool surfaces.

Each sub-scout (Cinderella, Comeback, Hometown, Echo) gets the same four
runtime tools:

  - `wire_emit(message, ...)` — the in-process write-through proxy.
  - `query_candidates(filter_dict)` — read from BigQuery `candidates`.
  - `grounded_search(query)` — Gemini Google Search grounding.
  - `write_lead_report(...)` — persist a Lead Report to Firestore + feed
    the HND detector.

Voice differs only via the prompt file (CONSTITUTION Rule 1, Law 2). The
Python here contains zero voice text.

Tools are built as closures in `build_scout_tools(...)` so each call site
gets a fresh tool list with the runtime deps bound — analogous to the
Editor's `_bind_tools` (see `agents/editor/agent.py::_bind_tools`).

ADK's `LlmAgent.tools` accepts plain async callables; the Runner introspects
the function signature to build the JSONSchema the model sees. So the
docstrings ARE the LLM-facing spec — be careful when editing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.cost.counters import CostCeilingExceeded
from agents.wire.types import LeadReport, SubAgentId

logger = logging.getLogger(__name__)


# Cost axes used by the Scout tools.
_GROUNDING_AXIS = "grounding"


# --- Tool builder -------------------------------------------------------------


def build_scout_tools(
    *,
    scout: SubAgentId,
    wire: Any,
    bigquery: Any | None = None,
    firestore: Any | None = None,
    hnd: Any | None = None,
    cost_counter: Any | None = None,
    grounded_model: str = "gemini-3-flash-preview",
) -> list[Any]:
    """Build the four scout tools as closures over runtime deps.

    Each sub-scout calls this at construction time (see `cinderella.py`,
    `comeback.py`, `hometown.py`, `echo.py`). The closures keep Wire,
    BigQuery, Firestore, HND, and the cost counter out of the LLM-facing
    arg surface — the Runner only sees the explicit kwargs.

    `scout` is the sub-agent name; baked into Lead Reports + cost counter
    increments so HND attributes correctly.
    """
    return [
        _make_wire_emit(wire=wire, scout=scout),
        _make_query_candidates(bigquery=bigquery),
        _make_grounded_search(
            cost_counter=cost_counter,
            scout=scout,
            model=grounded_model,
        ),
        _make_write_lead_report(
            firestore=firestore,
            hnd=hnd,
            scout=scout,
        ),
    ]


# --- Individual closures ------------------------------------------------------


def _make_wire_emit(*, wire: Any, scout: SubAgentId):
    async def wire_emit(
        *,
        message: str,
        message_type: str = "thinking",
        confidence: float | None = None,
        story_unit_id: str | None = None,
    ) -> str:
        """Emit a single Wire event (the in-process write-through proxy).

        The proxy invokes the NIL Redaction Layer in-process before
        persistence; do not bypass.

        Args:
            message: the displayed text. Will be NIL-scanned. NEVER name an
                individual Team USA athlete.
            message_type: 'thinking' | 'milestone' | 'intervention' | 'decision'.
            confidence: optional 0.0-1.0.
            story_unit_id: optional id of the place / program / pattern.

        Returns:
            The Firestore doc id of the persisted Wire event.
        """
        event: dict = {
            "agent": "scout_desk",
            "sub_agent": scout,
            "message": message,
            "message_type": message_type,
            "mode": "live",
        }
        if confidence is not None:
            event["confidence"] = confidence
        if story_unit_id is not None:
            event["story_unit_id"] = story_unit_id
        return await wire.emit(event)

    return wire_emit


def _make_query_candidates(*, bigquery: Any | None):
    async def query_candidates(
        *,
        state: str | None = None,
        region: str | None = None,
        sport: str | None = None,
        story_unit_type: str | None = None,
        limit: int = 25,
    ) -> list[dict]:
        """Query the BigQuery `candidates` table for places / programs / patterns.

        The `candidates` schema (see `data/bq_schemas/candidates.json`) is
        the story-unit pool. Filterable columns:

        Args:
            state: optional 2-letter US state filter (e.g., 'IA').
            region: optional US region filter.
            sport: optional official sport name (e.g., 'Athletics'). Matches
                rows whose `primary_sports` array contains this sport.
            story_unit_type: optional 'place' | 'program' | 'pattern'.
            limit: max rows (capped at 50).

        Returns:
            A list of candidate story-unit dicts. Each is a place / program /
            pattern; never an individual.
        """
        capped_limit = max(1, min(50, int(limit)))
        if bigquery is None or not hasattr(bigquery, "query"):
            logger.debug("query_candidates: no bigquery client; returning []")
            return []

        # Build parameterised SQL. We do NOT interpolate user-supplied strings
        # into the SQL; ScalarQueryParameter handles the binding.
        clauses: list[str] = []
        params: list[Any] = []
        try:
            from google.cloud import bigquery as _bq  # type: ignore[import-untyped]

            if state is not None:
                clauses.append("state = @state")
                params.append(_bq.ScalarQueryParameter("state", "STRING", state))
            if region is not None:
                clauses.append("region = @region")
                params.append(_bq.ScalarQueryParameter("region", "STRING", region))
            if sport is not None:
                clauses.append("@sport IN UNNEST(primary_sports)")
                params.append(_bq.ScalarQueryParameter("sport", "STRING", sport))
            if story_unit_type is not None:
                clauses.append("story_unit_type = @story_unit_type")
                params.append(
                    _bq.ScalarQueryParameter("story_unit_type", "STRING", story_unit_type)
                )

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = (
                "SELECT story_unit_id, story_unit_title, story_unit_type, "
                "region, state, primary_sports, olympic_count, paralympic_count, "
                "representation_history, public_evidence_refs, aggregate_score, "
                "high_narrative_density "
                f"FROM `storytellers_room.candidates`{where} "
                f"ORDER BY aggregate_score DESC NULLS LAST LIMIT {capped_limit}"
            )
            job_config = _bq.QueryJobConfig(query_parameters=params)
            job = bigquery.query(sql, job_config=job_config)
            rows = list(job.result())
            return [dict(r) for r in rows]
        except ImportError:
            logger.debug(
                "query_candidates: google-cloud-bigquery not installed; "
                "returning []"
            )
            return []
        except Exception:
            logger.exception("query_candidates: BigQuery query failed")
            return []

    return query_candidates


def _make_grounded_search(*, cost_counter: Any | None, scout: SubAgentId, model: str):
    async def grounded_search(query: str) -> dict:
        """Run a Gemini Google Search grounding query.

        Uses `gemini-3-flash-preview` with `tools=[{"google_search": {}}]`
        per BUILD_SPEC §3.3. Each search the model executes within the
        single prompt counts as one billable use; we increment the
        `grounding` axis once per call to track daily burn.

        Args:
            query: a natural-language search query (must reference places /
                programs / patterns; NEVER a named individual).

        Returns:
            A dict `{"text": ..., "sources": [...], "queried_at": iso}`. On
            cost-ceiling breach OR runtime error, returns an empty result
            with `"error"` set so the model can keep working.
        """
        if cost_counter is not None:
            try:
                await cost_counter.assert_under_ceiling(
                    axis=_GROUNDING_AXIS, agent="scout_desk"
                )
            except CostCeilingExceeded:
                logger.info(
                    "grounded_search: ceiling reached for scout=%s; skipping", scout
                )
                return {
                    "text": "",
                    "sources": [],
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                    "error": "cost_ceiling",
                }

        text = ""
        sources: list[dict] = []
        try:
            # `google.genai` is what ADK uses internally; preferred path.
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]

            client = genai.Client()
            grounding_tool = genai_types.Tool(
                google_search=genai_types.GoogleSearch()
            )
            config = genai_types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=1.0,  # BUILD_SPEC §3.3 recommends 1.0 for grounding.
            )
            response = await client.aio.models.generate_content(
                model=model,
                contents=query,
                config=config,
            )
            text = getattr(response, "text", "") or ""
            # Extract grounding source URLs when present.
            try:
                candidates = getattr(response, "candidates", None) or []
                for cand in candidates:
                    gm = getattr(cand, "grounding_metadata", None)
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    for ch in chunks:
                        web = getattr(ch, "web", None)
                        if web is not None:
                            sources.append(
                                {
                                    "uri": getattr(web, "uri", None),
                                    "title": getattr(web, "title", None),
                                }
                            )
            except Exception:
                logger.debug("grounded_search: grounding metadata extract failed", exc_info=True)
        except ImportError:
            logger.debug(
                "grounded_search: google-genai not installed; returning empty"
            )
            return {
                "text": "",
                "sources": [],
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "error": "genai_not_installed",
            }
        except Exception:
            logger.exception("grounded_search: generate_content failed")
            return {
                "text": "",
                "sources": [],
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "error": "runtime_error",
            }

        # Increment counter AFTER the call (we have no token count for grounding;
        # one query = one billable use for budgeting purposes).
        if cost_counter is not None:
            try:
                await cost_counter.increment(
                    agent="scout_desk",
                    sub_agent=scout,
                    axis=_GROUNDING_AXIS,
                    model=model,
                    grounded_queries=1,
                )
            except Exception:
                logger.exception(
                    "grounded_search: cost_counter.increment failed"
                )

        return {
            "text": text,
            "sources": sources,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    return grounded_search


def _make_write_lead_report(*, firestore: Any | None, hnd: Any | None, scout: SubAgentId):
    async def write_lead_report(
        *,
        story_unit_id: str,
        story_unit_title: str,
        story_unit_type: str,
        signal_type: str,
        confidence: float,
        notes: str,
        evidence_refs: list[str] | None = None,
    ) -> str:
        """Persist a Scout Lead Report to Firestore `/lead_reports/{id}`.

        Schema follows BUILD_SPEC §8.3. The HND detector receives the
        report via `hnd.record_lead_report(...)` so the 3-of-4 milestone
        can fire independently of the Firestore listener (BUILD_SPEC §5.2,
        HOE-DEC-023).

        Args:
            story_unit_id: stable id (places/programs/patterns are the ONLY
                valid story units; NEVER an athlete id).
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
        created_at = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": report_id,
            "story_unit_id": story_unit_id,
            "story_unit_title": story_unit_title,
            "story_unit_type": story_unit_type,
            "scout": scout,
            "signal_type": signal_type,
            "confidence": float(confidence),
            "notes": notes,
            "evidence_refs": list(evidence_refs or []),
            "status": "investigating",
            "created_at": created_at,
            "updated_at": created_at,
        }
        # Persist to Firestore. Tolerate sync stubs and async clients.
        if firestore is not None and hasattr(firestore, "collection"):
            try:
                coll = firestore.collection("lead_reports")
                res = coll.add(doc)
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                logger.exception("write_lead_report: firestore write failed")
        # Forward to HND so the 3-of-4 detector sees it (HOE-DEC-023).
        if hnd is not None:
            try:
                await hnd.record_lead_report(
                    LeadReport(
                        id=report_id,
                        story_unit_id=story_unit_id,
                        story_unit_title=story_unit_title,
                        story_unit_type=story_unit_type,  # type: ignore[arg-type]
                        scout=scout,
                        signal_type=signal_type,
                        confidence=float(confidence),
                        notes=notes,
                        evidence_refs=list(evidence_refs or []),
                        created_at=created_at,
                    )
                )
            except Exception:
                logger.exception("write_lead_report: hnd.record_lead_report failed")
        return report_id

    return write_lead_report
