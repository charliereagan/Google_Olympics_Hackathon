"""Investigator tool surface — closure-bound implementations.

The Investigator's Pro-tier `LlmAgent` decides WHEN to call which tool
(CONSTITUTION Law 1). Python here defines the physics: read Lead Reports,
ground searches, query BigQuery, write Investigation Packets. No
orchestration sequences.

Each tool below is built as a closure in `build_investigator_tools(...)` so
runtime deps (Firestore, BigQuery, the WireEmitter, the cost counter) are
captured once and the LLM-facing surface stays clean. Mirrors the Scout
pattern at `agents/scouts/tools.py::build_scout_tools`.

Voice text lives in `/prompts/investigator.md`. This file contains zero
voice text and zero decision logic.

CRITICAL — Place over Person (CONSTITUTION Law 4 + PROJECT_BRIEF §5):
  - `query_historical_athletes` MUST aggregate before returning. The
    BigQuery `historical_athletes` table contains athlete names; the tool's
    return value MUST NOT carry those names out of this function. The
    Investigator's wire emits and the Investigation Packet's user-facing
    fields (`narrative_spine`, `historical_context.era_parallel`,
    `historical_context.pattern_notes`) MUST NOT contain names.
  - `read_lead_report` returns the raw Lead Report; Lead Reports are
    already enforced name-free at write time (PROJECT_BRIEF §5).
  - `grounded_search` may surface athlete names in `text` — the Wire
    proxy's NIL Redaction Layer is the structural backstop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.cost.counters import CostCeilingExceeded

logger = logging.getLogger(__name__)


# Cost axes used by Investigator tools.
_GROUNDING_AXIS = "grounding"
_DEEP_RESEARCH_AXIS = "deep_research"


# --- Tool builder -------------------------------------------------------------


def build_investigator_tools(
    *,
    wire: Any,
    firestore: Any | None = None,
    bigquery: Any | None = None,
    cost_counter: Any | None = None,
    grounded_model: str = "gemini-3.1-pro-preview",
    deep_research_model: str = "gemini-3.1-pro-preview",
    deep_research_timeout_s: float = 90.0,
    bq_dataset: str = "storytellers_room",
) -> list[Any]:
    """Build the Investigator's six tools as closures over runtime deps.

    Returns a list ready for `LlmAgent(tools=...)`. Tool docstrings are the
    LLM-facing spec — be careful when editing. ADK's Runner introspects the
    function signature to build the JSONSchema the model sees.

    Args:
        wire: WireEmitter instance — for `call_deep_research`'s "stalled"
            thinking event and any internal Wire writes.
        firestore: Firestore async-capable client. Used by
            `read_lead_report` and `write_investigation_packet`.
        bigquery: BigQuery client. Used by `query_historical_athletes` and
            `query_geography`.
        cost_counter: per-axis cost counter (see `agents/cost/counters.py`).
            Required for grounding + deep_research ceiling enforcement.
        grounded_model: model id for grounded search calls.
        deep_research_model: model id for the Deep Research wrapper.
        deep_research_timeout_s: hard timeout per BUILD_SPEC §3.2 (90s).
        bq_dataset: BigQuery dataset name.
    """
    return [
        _make_read_lead_report(firestore=firestore),
        _make_grounded_search(
            cost_counter=cost_counter, model=grounded_model
        ),
        _make_query_historical_athletes(
            bigquery=bigquery, dataset=bq_dataset
        ),
        _make_query_geography(bigquery=bigquery, dataset=bq_dataset),
        _make_call_deep_research(
            wire=wire,
            cost_counter=cost_counter,
            model=deep_research_model,
            timeout_s=deep_research_timeout_s,
        ),
        _make_write_investigation_packet(firestore=firestore),
    ]


# --- read_lead_report ---------------------------------------------------------


def _make_read_lead_report(*, firestore: Any | None):
    async def read_lead_report(lead_report_id: str) -> dict:
        """Read a Scout Lead Report from Firestore (`/lead_reports/{id}`).

        Args:
            lead_report_id: id of the Lead Report (the Scout's
                `write_lead_report` returns this).

        Returns:
            The Lead Report dict per BUILD_SPEC §8.3:
            `{id, story_unit_id, story_unit_title, story_unit_type, scout,
              signal_type, confidence, notes, evidence_refs, status,
              created_at, ...}`. Lead Reports are guaranteed name-free
            (Scout discipline).

        Raises:
            LeadReportNotFoundError: if no doc with `id == lead_report_id`
            exists in `/lead_reports/`. Use this signal to short-circuit
            the investigation — the Editor will see the failure dict.
        """
        if firestore is None or not hasattr(firestore, "collection"):
            raise LeadReportNotFoundError(
                f"firestore unavailable; cannot read lead_report {lead_report_id!r}"
            )
        try:
            coll = firestore.collection("lead_reports")
        except Exception as e:
            raise LeadReportNotFoundError(
                f"lead_reports collection unavailable: {e}"
            ) from e

        # Try direct doc-id lookup first (fastest + canonical).
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(lead_report_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        if data:
                            data.setdefault("id", lead_report_id)
                            return data
        except Exception:
            logger.debug("read_lead_report: doc-id lookup failed; falling back to scan", exc_info=True)

        # Fallback: scan the collection looking for a matching `id` field.
        # Stubs in unit tests typically don't implement `.document(...)`.
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == lead_report_id:
                        return data
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == lead_report_id:
                        return data
        except Exception as e:
            raise LeadReportNotFoundError(
                f"lead_report scan failed: {e}"
            ) from e

        raise LeadReportNotFoundError(
            f"lead_report not found: {lead_report_id!r}"
        )

    return read_lead_report


# --- grounded_search ----------------------------------------------------------


def _make_grounded_search(*, cost_counter: Any | None, model: str):
    async def grounded_search(query: str) -> dict:
        """Run a Gemini Google Search grounding query (BUILD_SPEC §3.3).

        Each search the model executes within a single prompt counts as one
        billable use; the `grounding` axis increments once per call.

        Args:
            query: a natural-language search query. NEVER reference an
                individual Team USA athlete by name — query places /
                programs / patterns / sports / eras instead.

        Returns:
            `{summary, citations, query, queried_at}`:
              - `summary`: model-synthesized text from the grounded search.
              - `citations`: list of `{uri, title}` for each grounded source.
              - `query`: echoed query string (for the Investigator's notes).
              - `queried_at`: ISO timestamp.

            On cost-ceiling breach OR runtime error, returns an empty
            result with `error` set so the model can keep working.
        """
        if cost_counter is not None:
            try:
                await cost_counter.assert_under_ceiling(
                    axis=_GROUNDING_AXIS, agent="investigator"
                )
            except CostCeilingExceeded:
                logger.info("grounded_search: ceiling reached; skipping")
                return {
                    "summary": "",
                    "citations": [],
                    "query": query,
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                    "error": "cost_ceiling",
                }

        summary = ""
        citations: list[dict] = []
        try:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]

            client = genai.Client()
            grounding_tool = genai_types.Tool(
                google_search=genai_types.GoogleSearch()
            )
            config = genai_types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=1.0,
            )
            response = await client.aio.models.generate_content(
                model=model,
                contents=query,
                config=config,
            )
            summary = getattr(response, "text", "") or ""
            try:
                candidates = getattr(response, "candidates", None) or []
                for cand in candidates:
                    gm = getattr(cand, "grounding_metadata", None)
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    for ch in chunks:
                        web = getattr(ch, "web", None)
                        if web is not None:
                            citations.append(
                                {
                                    "uri": getattr(web, "uri", None),
                                    "title": getattr(web, "title", None),
                                }
                            )
            except Exception:
                logger.debug("grounded_search: citation extract failed", exc_info=True)
        except ImportError:
            logger.debug("grounded_search: google-genai not installed; returning empty")
            return {
                "summary": "",
                "citations": [],
                "query": query,
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "error": "genai_not_installed",
            }
        except Exception:
            logger.exception("grounded_search: generate_content failed")
            return {
                "summary": "",
                "citations": [],
                "query": query,
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "error": "runtime_error",
            }

        if cost_counter is not None:
            try:
                await cost_counter.increment(
                    agent="investigator",
                    sub_agent=None,
                    axis=_GROUNDING_AXIS,
                    model=model,
                    grounded_queries=1,
                )
            except Exception:
                logger.exception("grounded_search: cost_counter.increment failed")

        return {
            "summary": summary,
            "citations": citations,
            "query": query,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    return grounded_search


# --- query_historical_athletes (AGGREGATE-ONLY OUTPUT) ------------------------


def _make_query_historical_athletes(*, bigquery: Any | None, dataset: str):
    async def query_historical_athletes(
        sport: str | None = None,
        decade: str | None = None,
        hometown_state: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Query `historical_athletes` for parallel ERAS and PATTERNS.

        CRITICAL: this tool's return value contains AGGREGATE COUNTS ONLY.
        Even though the BigQuery row contains `athlete_id`, the tool
        filters those out before returning. The Investigator's user-facing
        outputs (Wire messages, narrative_spine, historical_context) NEVER
        contain athlete names. (CONSTITUTION Law 4 + PROJECT_BRIEF §5.)

        Args:
            sport: official sport name (e.g., "Athletics", "Swimming").
                NEVER an NGB name (no "USA Swimming", "USATF").
            decade: e.g., "1960s", "1990s", "pre-1900". Decade label maps
                to a BETWEEN clause on `games_year`.
            hometown_state: 2-letter US state filter (e.g., "IA").
            limit: max underlying rows to scan (capped at 200).

        Returns:
            `{count, by_decade, by_sport, by_state, by_games_type,
              era_summary}`:
              - `count`: total matching rows.
              - `by_decade`: `{"1960s": 12, "1970s": 8, ...}`.
              - `by_sport`: `{"Athletics": 9, ...}` for cross-sport context.
              - `by_state`: `{"IA": 4, "NY": 11, ...}`.
              - `by_games_type`: `{"summer_olympic": ..., "summer_paralympic": ...}`
                so parity context is one query away.
              - `era_summary`: short label like "1960s Athletics era" the
                Investigator may quote in the Investigation Packet's
                `historical_context.era_parallel` (without naming athletes).

            NEVER returns athlete_ids, athlete names, finish times, or
            scoring results.
        """
        capped_limit = max(1, min(200, int(limit)))
        if bigquery is None or not hasattr(bigquery, "query"):
            logger.debug(
                "query_historical_athletes: no bigquery client; returning empty aggregate"
            )
            return _empty_athlete_aggregate(sport=sport, decade=decade, hometown_state=hometown_state)

        clauses: list[str] = ["noc = 'USA'"]
        params: list[Any] = []
        try:
            from google.cloud import bigquery as _bq  # type: ignore[import-untyped]

            if sport is not None:
                clauses.append("LOWER(sport) = LOWER(@sport)")
                params.append(_bq.ScalarQueryParameter("sport", "STRING", sport))
            if hometown_state is not None:
                clauses.append("UPPER(hometown_state) = UPPER(@state)")
                params.append(_bq.ScalarQueryParameter("state", "STRING", hometown_state))
            year_lo, year_hi = _decade_bounds(decade)
            if year_lo is not None and year_hi is not None:
                clauses.append("games_year BETWEEN @year_lo AND @year_hi")
                params.append(_bq.ScalarQueryParameter("year_lo", "INT64", year_lo))
                params.append(_bq.ScalarQueryParameter("year_hi", "INT64", year_hi))

            where = " WHERE " + " AND ".join(clauses)
            # Project ONLY aggregation-ready columns. We deliberately do NOT
            # SELECT athlete_id even though we're scanning a names-bearing
            # table — Place-over-Person at the SQL boundary.
            sql = (
                "SELECT sport, games_year, hometown_state, games_type "
                f"FROM `{dataset}.historical_athletes`{where} "
                f"LIMIT {capped_limit}"
            )
            job_config = _bq.QueryJobConfig(query_parameters=params)
            job = bigquery.query(sql, job_config=job_config)
            rows = list(job.result())
        except ImportError:
            logger.debug(
                "query_historical_athletes: google-cloud-bigquery not installed; returning empty"
            )
            return _empty_athlete_aggregate(sport=sport, decade=decade, hometown_state=hometown_state)
        except Exception:
            logger.exception("query_historical_athletes: BigQuery query failed")
            return _empty_athlete_aggregate(sport=sport, decade=decade, hometown_state=hometown_state)

        # Aggregate in-process — cheap given LIMIT 200.
        by_decade: dict[str, int] = {}
        by_sport: dict[str, int] = {}
        by_state: dict[str, int] = {}
        by_games_type: dict[str, int] = {}
        for r in rows:
            r_sport = _safe_get(r, "sport") or "unknown"
            r_year = _safe_get(r, "games_year")
            r_state = _safe_get(r, "hometown_state") or "unknown"
            r_type = _safe_get(r, "games_type") or "unknown"
            d_label = _decade_label(r_year)
            by_decade[d_label] = by_decade.get(d_label, 0) + 1
            by_sport[r_sport] = by_sport.get(r_sport, 0) + 1
            by_state[r_state] = by_state.get(r_state, 0) + 1
            by_games_type[r_type] = by_games_type.get(r_type, 0) + 1

        return {
            "count": len(rows),
            "by_decade": by_decade,
            "by_sport": by_sport,
            "by_state": by_state,
            "by_games_type": by_games_type,
            "era_summary": _era_summary(sport=sport, decade=decade),
            "filter": {
                "sport": sport,
                "decade": decade,
                "hometown_state": hometown_state,
            },
        }

    return query_historical_athletes


def _empty_athlete_aggregate(
    *, sport: str | None, decade: str | None, hometown_state: str | None
) -> dict:
    return {
        "count": 0,
        "by_decade": {},
        "by_sport": {},
        "by_state": {},
        "by_games_type": {},
        "era_summary": _era_summary(sport=sport, decade=decade),
        "filter": {
            "sport": sport,
            "decade": decade,
            "hometown_state": hometown_state,
        },
    }


# --- query_geography ----------------------------------------------------------


def _make_query_geography(*, bigquery: Any | None, dataset: str):
    async def query_geography(
        place: str | None = None,
        state: str | None = None,
        region: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query `geography` for place / region context.

        Args:
            place: city name (case-insensitive partial match).
            state: 2-letter US state filter.
            region: region label (e.g., "Midwest").
            limit: max rows (capped at 50).

        Returns:
            A list of place dicts:
            `{place_id, city, state, region, population, latitude,
              longitude, regional_sport_infrastructure_notes}`. No athlete
            data on this table — safe to surface verbatim.
        """
        capped_limit = max(1, min(50, int(limit)))
        if bigquery is None or not hasattr(bigquery, "query"):
            logger.debug("query_geography: no bigquery client; returning []")
            return []

        clauses: list[str] = []
        params: list[Any] = []
        try:
            from google.cloud import bigquery as _bq  # type: ignore[import-untyped]

            if place is not None:
                clauses.append("LOWER(city) LIKE LOWER(@place)")
                params.append(
                    _bq.ScalarQueryParameter("place", "STRING", f"%{place}%")
                )
            if state is not None:
                clauses.append("UPPER(state) = UPPER(@state)")
                params.append(_bq.ScalarQueryParameter("state", "STRING", state))
            if region is not None:
                clauses.append("LOWER(region) = LOWER(@region)")
                params.append(_bq.ScalarQueryParameter("region", "STRING", region))

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = (
                "SELECT place_id, city, state, region, population, latitude, "
                "longitude, regional_sport_infrastructure_notes "
                f"FROM `{dataset}.geography`{where} "
                f"LIMIT {capped_limit}"
            )
            job_config = _bq.QueryJobConfig(query_parameters=params)
            job = bigquery.query(sql, job_config=job_config)
            rows = list(job.result())
            return [dict(r) for r in rows]
        except ImportError:
            logger.debug("query_geography: google-cloud-bigquery not installed; returning []")
            return []
        except Exception:
            logger.exception("query_geography: BigQuery query failed")
            return []

    return query_geography


# --- call_deep_research (BUILD_SPEC §3.2) -------------------------------------


def _make_call_deep_research(
    *,
    wire: Any,
    cost_counter: Any | None,
    model: str,
    timeout_s: float,
):
    async def call_deep_research(
        question: str,
        max_seconds: int = 90,
    ) -> dict | None:
        """Call Gemini Deep Research with a 90s timeout (BUILD_SPEC §3.2).

        Deep Research is multi-minute by design. The Investigator wraps it
        in a 90s timeout and falls back to grounded search on timeout.
        Daily cap of 10 calls (BUILD_SPEC §15.3).

        Args:
            question: a high-priority research question. NEVER reference an
                individual Team USA athlete by name.
            max_seconds: per-call timeout in seconds. Default 90; capped at
                300 to respect the BUILD_SPEC ceiling.

        Returns:
            `{report, citations, question, returned_at}` on success.
            `None` on timeout, daily cap, or any runtime error — the
            Investigator should treat None as "Deep Research unavailable;
            continue with grounded_search".

        Side effect on timeout: emits a Wire `thinking` event
        ("*deep research stalled, switching to grounded search*") via the
        bound WireEmitter. This is good Wire texture per BUILD_SPEC §3.2.
        """
        # Daily cap pre-check.
        if cost_counter is not None:
            try:
                await cost_counter.assert_under_ceiling(
                    axis=_DEEP_RESEARCH_AXIS, agent="investigator"
                )
            except CostCeilingExceeded:
                logger.info("call_deep_research: daily cap reached; skipping")
                return None

        timeout = float(min(max(0.0, float(max_seconds)), 300.0)) or timeout_s

        try:
            result = await asyncio.wait_for(
                _invoke_deep_research_api(question=question, model=model),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await _safe_emit_thinking(
                wire,
                "*deep research stalled, switching to grounded search*",
            )
            if cost_counter is not None:
                try:
                    # Count the timeout as a use against the daily cap; it
                    # represents real spend on Vertex AI's side.
                    await cost_counter.increment(
                        agent="investigator",
                        sub_agent=None,
                        axis=_DEEP_RESEARCH_AXIS,
                        model=model,
                        calls=1,
                    )
                except Exception:
                    logger.exception("call_deep_research: cost_counter.increment failed")
            return None
        except _DeepResearchUnavailable:
            # Surface available is not implemented yet; emit the same Wire
            # texture so the room behaves identically to the timeout case.
            await _safe_emit_thinking(
                wire,
                "*deep research stalled, switching to grounded search*",
            )
            return None
        except Exception:
            logger.exception("call_deep_research: failed")
            return None

        if cost_counter is not None:
            try:
                await cost_counter.increment(
                    agent="investigator",
                    sub_agent=None,
                    axis=_DEEP_RESEARCH_AXIS,
                    model=model,
                    calls=1,
                )
            except Exception:
                logger.exception("call_deep_research: cost_counter.increment failed")

        return result

    return call_deep_research


class _DeepResearchUnavailable(RuntimeError):
    """Raised when the Gemini Deep Research surface isn't reachable.

    Day-4 ships a stub: the `google-genai` SDK does not (as of 2026-05-02)
    expose a stable Deep Research tool / model id surface in the published
    Python SDK. The Investigator must work without it — `grounded_search`
    is the workhorse. Day-7 backlog item: revisit when Vertex AI publishes
    the Deep Research tool surface.
    """


async def _invoke_deep_research_api(*, question: str, model: str) -> dict:
    """Stub for the actual Gemini Deep Research API call.

    Currently raises `_DeepResearchUnavailable` so the wrapper falls back
    to the "stalled" Wire texture. Future replacement: call the live API
    when the `google-genai` SDK exposes it (see `_DeepResearchUnavailable`
    docstring). When that lands, this function should return:
        `{report: str, citations: list[{uri, title}], question, returned_at}`.
    """
    raise _DeepResearchUnavailable(
        "Gemini Deep Research SDK surface not yet stable; using grounded_search fallback"
    )


async def _safe_emit_thinking(wire: Any, message: str) -> None:
    """Emit a Wire `thinking` event without raising into the tool caller."""
    if wire is None:
        return
    try:
        await wire.emit(
            {
                "agent": "investigator",
                "message": message,
                "message_type": "thinking",
                "mode": "live",
            }
        )
    except Exception:
        logger.exception("call_deep_research: failed to emit Wire thinking event")


# --- write_investigation_packet -----------------------------------------------


def _make_write_investigation_packet(*, firestore: Any | None):
    async def write_investigation_packet(
        story_unit_id: str,
        story_unit_title: str,
        story_unit_type: str,
        narrative_spine: str,
        geography: dict,
        historical_context: dict,
        trend_signals: dict,
        sources: list[dict],
        paralympic_depth_score: float = 0.0,
        ready_for_storyteller: bool = False,
    ) -> str:
        """Persist an Investigation Packet to Firestore (`/investigation_packets/{auto_id}`).

        Schema follows BUILD_SPEC §8.4. NEVER include athlete names in any
        user-facing field — `narrative_spine`, `historical_context.*`, and
        `geography.notes` are surfaced to the Storyteller and reach the
        Broadcast page.

        Args:
            story_unit_id: stable id of the place / program / pattern.
            story_unit_title: short human title.
            story_unit_type: 'place' | 'program' | 'pattern'.
            narrative_spine: 2-3 sentences. NEVER names athletes. NEVER
                uses forbidden Storyteller words ("inspirational", "hero",
                "overcame", "warrior", "former Olympian", etc.). Use
                conditional phrasing for forward-looking claims.
            geography: `{state, region, population, notes}`.
            historical_context: `{era_parallel, pattern_notes}`. Both
                describe ERAS and PATTERNS, never named athletes.
            trend_signals: `{olympic_count_history, paralympic_count_history}`.
                Each is a list of `{year, count}` dicts. Aggregate counts
                only.
            sources: list of `{url, outlet, relevance_note}`.
            paralympic_depth_score: 0.0-1.0 — Equity Editor input.
            ready_for_storyteller: True only when all fields are populated
                and Paralympic depth equals Olympic depth.

        Returns:
            The Firestore doc id (string).
        """
        packet_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": packet_id,
            "story_unit_id": story_unit_id,
            "story_unit_title": story_unit_title,
            "story_unit_type": story_unit_type,
            "narrative_spine": narrative_spine,
            "geography": dict(geography or {}),
            "historical_context": dict(historical_context or {}),
            "trend_signals": dict(trend_signals or {}),
            "sources": list(sources or []),
            "paralympic_depth_score": float(paralympic_depth_score),
            "ready_for_storyteller": bool(ready_for_storyteller),
            "created_at": now,
            "updated_at": now,
        }
        if firestore is not None and hasattr(firestore, "collection"):
            try:
                coll = firestore.collection("investigation_packets")
                res = coll.add(doc)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    res = await res
                # Some clients return (write_result, doc_ref). Prefer that
                # doc_ref.id over our generated id — but keep our id in the
                # doc body so reads are stable.
                if isinstance(res, tuple) and len(res) >= 2:
                    doc_ref = res[1]
                    return getattr(doc_ref, "id", packet_id)
                if hasattr(res, "id"):
                    return str(res.id)
            except Exception:
                logger.exception(
                    "write_investigation_packet: firestore write failed"
                )
        return packet_id

    return write_investigation_packet


# --- Errors -------------------------------------------------------------------


class LeadReportNotFoundError(RuntimeError):
    """Raised by `read_lead_report` when the doc isn't in Firestore.

    The Investigator catches this in `investigate(...)` and emits a Wire
    thinking event, then returns `{action: 'error', reason: 'lead_report_not_found'}`.
    """


# --- Helpers ------------------------------------------------------------------


def _decade_bounds(decade: str | None) -> tuple[int | None, int | None]:
    """Map a decade label to inclusive year bounds, or (None, None)."""
    if not decade:
        return (None, None)
    label = decade.strip().lower().rstrip("s")
    # Accept "1960s" / "1960" / "pre-1900" / "1900s".
    if label.startswith("pre-"):
        try:
            cap = int(label.split("-", 1)[1])
            return (1880, cap - 1)
        except ValueError:
            return (None, None)
    try:
        start = int(label)
    except ValueError:
        return (None, None)
    if start < 100:
        # Two-digit year -> assume 1900s for backward compatibility.
        start = 1900 + start
    if start % 10 != 0:
        # If they passed "1962", round to "1960".
        start = (start // 10) * 10
    return (start, start + 9)


def _decade_label(year: Any) -> str:
    try:
        y = int(year)
    except (TypeError, ValueError):
        return "unknown"
    return f"{(y // 10) * 10}s"


def _era_summary(*, sport: str | None, decade: str | None) -> str:
    """Compose a name-free era label (e.g., '1960s Athletics era')."""
    parts: list[str] = []
    if decade:
        parts.append(decade if decade.endswith("s") else f"{decade}s")
    if sport:
        parts.append(sport)
    parts.append("era")
    return " ".join(parts)


def _safe_get(row: Any, key: str) -> Any:
    """BigQuery Row-or-dict access."""
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "get"):
        try:
            return row.get(key)
        except Exception:
            pass
    if hasattr(row, key):
        return getattr(row, key)
    try:
        return row[key]  # type: ignore[index]
    except Exception:
        return None


def _doc_to_dict(doc: Any) -> dict:
    """Coerce a Firestore doc snapshot (or dict) to a plain dict."""
    if isinstance(doc, dict):
        return doc
    if hasattr(doc, "to_dict"):
        try:
            d = doc.to_dict() or {}
            if "id" not in d and hasattr(doc, "id"):
                d = dict(d)
                d["id"] = doc.id
            return d
        except Exception:
            return {}
    return {}
