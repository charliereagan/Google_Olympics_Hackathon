"""Scout Desk: wraps the four sub-scouts and runs them via ADK.

Public API:
  - `ScoutDesk(prompts=, wire=, bigquery=, firestore=, hnd=, cost_counter=)`
  - `await desk.dispatch_one(scout_id, story_unit_id)` — single-scout
    dispatch. The Editor's `dispatch_scout` tool calls this.
  - `await desk.run_pass(candidates, ctx=)` — fan out all four scouts; read
    Lead Reports from Firestore (the rendezvous, plan §A.6 + §C).
  - `desk.parallel_agent` — the underlying ADK ParallelAgent (or placeholder).

Result aggregation: **Firestore as the rendezvous (plan §A.6).** Each
sub-scout's `write_lead_report` tool persists to `/lead_reports/{id}`;
`run_pass` records `started_at` at the top, runs the scouts, queries
`/lead_reports` for `created_at >= started_at`, and returns those.

Empirical findings (Day-3):
  - ADK 2.0 Beta's `ParallelAgent` does not return sub-agent outputs in a
    shape we can rely on — it's a coordination primitive, not a result
    aggregator. We construct it for parity with BUILD_SPEC §3.6 (and so
    the Floor view can show the agent graph), but `run_pass` runs the
    four scouts via `asyncio.gather([self._run_one_scout(...) for ...])`
    using per-scout Runners, then reads results out of Firestore. This
    matches plan §G open-question 1's recommendation.
  - The `ParallelAgent` instance is still wired up + exposed via
    `parallel_agent` so future workers can swap the codepath without
    touching the desk's surface.

Cost: each scout dispatch is gated on
`cost_counter.assert_under_ceiling(axis='gemini_flash', agent='scout_desk',
sub_agent=scout_id)` BEFORE the Runner runs (BUILD_SPEC §15.3). On breach
we emit a Wire `thinking` event ("*scout pausing*") and skip the dispatch.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.cost.counters import CostCeilingExceeded
from agents.observability import log_agent_call, trace_span
from agents.scouts.cinderella import build_cinderella_scout
from agents.scouts.comeback import build_comeback_scout
from agents.scouts.echo import build_echo_scout
from agents.scouts.hnd_detector import HndDetector
from agents.scouts.hometown import build_hometown_scout
from agents.wire.emit import WireProxyNotReadyError
from agents.wire.types import InvestigationContext

logger = logging.getLogger(__name__)


_VALID_SCOUTS = {"cinderella", "comeback", "hometown", "echo"}
_COST_AXIS_FLASH = "gemini_flash"


class ScoutDesk:
    def __init__(
        self,
        *,
        prompts: dict[str, str],
        wire: Any,
        bigquery: Any | None = None,
        firestore: Any | None = None,
        hnd: HndDetector | None = None,
        scout_model: str = "gemini-3-flash-preview",
        cost_counter: Any | None = None,
        wire_vocabulary: Any | None = None,
    ) -> None:
        self._wire = wire
        self._bigquery = bigquery
        self._firestore = firestore
        self._hnd = hnd
        self._cost_counter = cost_counter
        self._model = scout_model
        self._wire_vocabulary = wire_vocabulary

        # Construct sub-scout LlmAgents with bound tools. The five standard
        # scout tools (wire_emit, query_candidates, grounded_search,
        # write_lead_report, pull_vocabulary) are built inside each
        # `build_*_scout` from the runtime deps passed here.
        common = dict(
            model=scout_model,
            wire=wire,
            bigquery=bigquery,
            firestore=firestore,
            hnd=hnd,
            cost_counter=cost_counter,
            wire_vocabulary=wire_vocabulary,
        )
        self._cinderella = build_cinderella_scout(prompt=prompts["cinderella_scout"], **common)
        self._comeback = build_comeback_scout(prompt=prompts["comeback_scout"], **common)
        self._hometown = build_hometown_scout(prompt=prompts["hometown_scout"], **common)
        self._echo = build_echo_scout(prompt=prompts["echo_scout"], **common)

        self._sub_scouts = [self._cinderella, self._comeback, self._hometown, self._echo]
        self._by_id: dict[str, Any] = {
            "cinderella": self._cinderella,
            "comeback": self._comeback,
            "hometown": self._hometown,
            "echo": self._echo,
        }
        self._parallel = self._build_parallel()

    @property
    def parallel_agent(self) -> Any:
        return self._parallel

    @property
    def sub_scouts(self) -> list[Any]:
        return list(self._sub_scouts)

    # -- Single-scout dispatch (Editor's dispatch_scout tool calls this) ------

    async def dispatch_one(
        self,
        scout_id: str,
        story_unit_id: str,
        *,
        ctx: InvestigationContext | None = None,
    ) -> dict:
        """Run one Scout's Runner against `story_unit_id`. Return the result.

        Cost ceiling pre-check on `axis='gemini_flash'`. On breach: emit a
        Wire `thinking` event and return `{dispatched: False, reason: ...}`.

        Returns:
            `{dispatched, scout, story_unit_id, lead_report_id?, tool_calls,
             latency_ms, input_tokens, output_tokens}`. `lead_report_id` is
            the id of the most-recent /lead_reports doc the scout wrote
            during this dispatch (or None if the scout chose not to write).
        """
        if scout_id not in _VALID_SCOUTS:
            return {
                "dispatched": False,
                "scout": scout_id,
                "story_unit_id": story_unit_id,
                "error": f"unknown scout_id: {scout_id}",
            }
        agent = self._by_id[scout_id]

        # Cost ceiling pre-check (BUILD_SPEC §15.3).
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS_FLASH,
                    agent="scout_desk",
                    sub_agent=scout_id,  # type: ignore[arg-type]
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*daily Flash cap reached, scout pausing*",
                    sub_agent=scout_id,
                    story_unit_id=story_unit_id,
                )
                return {
                    "dispatched": False,
                    "scout": scout_id,
                    "story_unit_id": story_unit_id,
                    "reason": "cost_ceiling",
                }
            except Exception:
                logger.exception(
                    "scout_desk.dispatch_one: cost ceiling check raised; continuing"
                )

        investigation_id = (
            ctx.investigation_id if ctx is not None else f"scout-dispatch-{scout_id}"
        )
        compression_factor = ctx.compression_factor if ctx is not None else 1.0

        # Snapshot of /lead_reports BEFORE the Runner runs so we can find any
        # report this scout writes by diffing against post-run docs.
        dispatch_started_at = datetime.now(timezone.utc)

        # Run the scout's Runner.
        with trace_span(
            "scout_desk.dispatch_one",
            investigation_id=investigation_id,
            attrs={
                "scout": scout_id,
                "story_unit_id": story_unit_id,
                "compression_factor": compression_factor,
            },
        ):
            t0 = time.monotonic()
            try:
                result = await self._run_adk_once(
                    agent=agent,
                    user_message=_format_dispatch_message(
                        scout_id=scout_id, story_unit_id=story_unit_id
                    ),
                    investigation_id=investigation_id,
                    scout_id=scout_id,
                )
            except WireProxyNotReadyError:
                logger.warning(
                    "scout_desk.dispatch_one: WireProxyNotReady; skipping"
                )
                return {
                    "dispatched": False,
                    "scout": scout_id,
                    "story_unit_id": story_unit_id,
                    "reason": "wire_not_ready",
                }
            except Exception as e:
                logger.exception("scout_desk.dispatch_one: Runner failed")
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="scout_desk",
                    sub_agent=scout_id,  # type: ignore[arg-type]
                    story_unit_id=story_unit_id,
                    investigation_id=investigation_id,
                    model=self._model,
                    tool=None,
                    latency_ms=latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    compression_factor=compression_factor,
                    outcome="error",
                    wire_event_id=None,
                    error=str(e),
                )
                return {
                    "dispatched": False,
                    "scout": scout_id,
                    "story_unit_id": story_unit_id,
                    "error": str(e),
                }

            latency_ms = int((time.monotonic() - t0) * 1000)

        # Cost increment AFTER the call so we have token counts.
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="scout_desk",
                    sub_agent=scout_id,  # type: ignore[arg-type]
                    axis=_COST_AXIS_FLASH,
                    model=self._model,
                    calls=1,
                    input_tokens=int(result.get("input_tokens") or 0),
                    output_tokens=int(result.get("output_tokens") or 0),
                )
            except Exception:
                logger.exception(
                    "scout_desk.dispatch_one: cost_counter.increment failed"
                )

        # Read back any Lead Report this scout wrote during the dispatch.
        lead_report_id = await self._latest_lead_report_id_since(
            scout_id=scout_id,
            story_unit_id=story_unit_id,
            since=dispatch_started_at,
        )

        log_agent_call(
            agent="scout_desk",
            sub_agent=scout_id,  # type: ignore[arg-type]
            story_unit_id=story_unit_id,
            investigation_id=investigation_id,
            model=self._model,
            tool=None,
            latency_ms=latency_ms,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            compression_factor=compression_factor,
            outcome="success",
            wire_event_id=None,
            error=None,
        )

        return {
            "dispatched": True,
            "scout": scout_id,
            "story_unit_id": story_unit_id,
            "lead_report_id": lead_report_id,
            "tool_calls": result.get("tool_calls", []),
            "latency_ms": latency_ms,
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
        }

    # -- Parallel pass (one think-cycle's worth of all four scouts) -----------

    async def run_pass(
        self,
        candidates: list[Any],
        *,
        ctx: InvestigationContext | None = None,
    ) -> list[dict]:
        """Fan out all four scouts in parallel against `candidates`.

        Per plan §A.6 + §G.1: we use `asyncio.gather` with per-scout Runners
        because ADK 2.0 Beta's `ParallelAgent` does not return sub-agent
        results in a usable shape. Either way the Lead Reports flow back via
        Firestore (each scout's `write_lead_report` tool persists to
        `/lead_reports/{id}`); `run_pass` queries that collection for
        reports created at or after `pass_start`.

        Args:
            candidates: a list of candidate dicts (from
                `query_candidates(...)`) or a list of `story_unit_id` strings.
                Each scout decides which candidates to investigate (Law 1).
            ctx: optional investigation context.

        Returns:
            A list of Lead Report dicts written during the pass-window.
        """
        pass_start = datetime.now(timezone.utc)
        ids = _candidates_to_id_list(candidates)
        logger.info(
            "scout_desk: run_pass start (investigation=%s candidates=%d)",
            ctx.investigation_id if ctx is not None else "ambient",
            len(ids),
        )

        # asyncio.gather across the four scouts; each scout decides what to
        # do with the candidate list (Law 1). We pass `ctx` and the `ids`
        # via the user-message body.
        coros = [
            self._run_one_scout_with_candidates(
                scout_id=sid, candidate_ids=ids, ctx=ctx
            )
            for sid in ("cinderella", "comeback", "hometown", "echo")
        ]
        try:
            await asyncio.gather(*coros, return_exceptions=True)
        except Exception:
            logger.exception("scout_desk.run_pass: asyncio.gather raised")

        return await self._read_back_reports_since(pass_start)

    # -- ADK Runner invocation -----------------------------------------------

    async def _run_one_scout_with_candidates(
        self,
        *,
        scout_id: str,
        candidate_ids: list[str],
        ctx: InvestigationContext | None,
    ) -> dict | None:
        """Run one scout against a candidate-id list (used by run_pass)."""
        agent = self._by_id[scout_id]
        investigation_id = (
            ctx.investigation_id if ctx is not None else f"scout-pass-{scout_id}"
        )
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS_FLASH,
                    agent="scout_desk",
                    sub_agent=scout_id,  # type: ignore[arg-type]
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*daily Flash cap reached, scout pausing*",
                    sub_agent=scout_id,
                )
                return None

        try:
            return await self._run_adk_once(
                agent=agent,
                user_message=_format_pass_message(
                    scout_id=scout_id, candidate_ids=candidate_ids
                ),
                investigation_id=investigation_id,
                scout_id=scout_id,
            )
        except Exception:
            logger.exception(
                "scout_desk._run_one_scout_with_candidates: scout=%s failed",
                scout_id,
            )
            return None

    async def _run_adk_once(
        self,
        *,
        agent: Any,
        user_message: str,
        investigation_id: str,
        scout_id: str,
    ) -> dict:
        """One ADK Runner invocation. Mirrors `EditorAgent._run_adk_once`.

        Returns `{tool_calls, input_tokens, output_tokens}`. Unit tests can
        patch this method to bypass ADK entirely.
        """
        try:
            from google.adk import Runner  # type: ignore[import-untyped]
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "scout_desk: google.adk not installed; %s dispatch is a no-op",
                scout_id,
            )
            return {"tool_calls": [], "input_tokens": 0, "output_tokens": 0}

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="storytellers_room",
            agent=agent,
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = f"{scout_id}-{investigation_id}-{uuid.uuid4().hex[:8]}"
        user_content = genai_types.Content(
            parts=[genai_types.Part(text=user_message)],
            role="user",
        )

        tool_calls: list[dict] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async for event in runner.run_async(
                user_id=f"scout-{scout_id}",
                session_id=session_id,
                new_message=user_content,
            ):
                try:
                    fcs = event.get_function_calls() or []
                except Exception:
                    fcs = []
                for fc in fcs:
                    tool_calls.append(
                        {
                            "name": getattr(fc, "name", None),
                            "args": dict(getattr(fc, "args", {}) or {}),
                        }
                    )
                usage = getattr(event, "usage_metadata", None)
                if usage is not None:
                    pt = getattr(usage, "prompt_token_count", None)
                    ct = getattr(usage, "candidates_token_count", None)
                    if pt is not None:
                        input_tokens = (input_tokens or 0) + int(pt)
                    if ct is not None:
                        output_tokens = (output_tokens or 0) + int(ct)
        finally:
            try:
                await runner.close()
            except Exception:
                logger.debug("scout_desk: runner.close() raised", exc_info=True)

        return {
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    # -- Firestore helpers ----------------------------------------------------

    def _build_parallel(self) -> Any:
        """Construct the ADK ParallelAgent (or a placeholder if ADK absent).

        Wired up for parity with BUILD_SPEC §3.6; `run_pass` does NOT
        currently route through it. See module docstring (empirical findings).
        """
        try:
            from google.adk.agents import ParallelAgent  # type: ignore[import-untyped]

            return ParallelAgent(
                name="scout_desk",
                sub_agents=self._sub_scouts,
            )
        except ImportError:
            logger.warning(
                "google.adk not installed; ScoutDesk parallel_agent is a placeholder"
            )
            return _PlaceholderParallel(name="scout_desk", sub_agents=self._sub_scouts)

    async def _read_back_reports_since(self, pass_start: datetime) -> list[dict]:
        """Query Firestore for lead_reports created at/after `pass_start`."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        since_iso = pass_start.isoformat()
        try:
            coll = self._firestore.collection("lead_reports")
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(filter=FieldFilter("created_at", ">=", since_iso))
            except Exception:
                # Older SDK / stub shape — best-effort fallback.
                q = (
                    coll.where("created_at", ">=", since_iso)
                    if hasattr(coll, "where")
                    else coll
                )
            stream = q.stream() if hasattr(q, "stream") else []
            docs: list[dict] = []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    docs.append(_doc_to_dict(d))
            else:
                for d in stream:
                    docs.append(_doc_to_dict(d))
            # Filter again in-process if the stub didn't support where() — safe.
            return [
                d for d in docs
                if (d.get("created_at") or "") >= since_iso
            ]
        except Exception:
            logger.exception("scout_desk: lead_report read-back failed")
            return []

    async def _latest_lead_report_id_since(
        self,
        *,
        scout_id: str,
        story_unit_id: str,
        since: datetime,
    ) -> str | None:
        """Return the id of the most recent lead_reports doc matching scout +
        story_unit_id with `created_at >= since`. None if none."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return None
        try:
            coll = self._firestore.collection("lead_reports")
            stream = coll.stream() if hasattr(coll, "stream") else []
            since_iso = since.isoformat()
            docs: list[dict] = []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    docs.append(_doc_to_dict(d))
            else:
                for d in stream:
                    docs.append(_doc_to_dict(d))
            best: dict | None = None
            for doc in docs:
                if doc.get("scout") != scout_id:
                    continue
                if doc.get("story_unit_id") != story_unit_id:
                    continue
                created = doc.get("created_at") or ""
                if created < since_iso:
                    continue
                if best is None or created > (best.get("created_at") or ""):
                    best = doc
            return best.get("id") if best else None
        except Exception:
            logger.exception("scout_desk: latest_lead_report_id_since failed")
            return None

    async def _safe_emit_thinking(
        self,
        message: str,
        *,
        sub_agent: str | None = None,
        story_unit_id: str | None = None,
    ) -> None:
        """Emit a Wire `thinking` event without raising into the caller."""
        try:
            event: dict = {
                "agent": "scout_desk",
                "message": message,
                "message_type": "thinking",
                "mode": "live",
            }
            if sub_agent is not None:
                event["sub_agent"] = sub_agent
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event)
        except WireProxyNotReadyError:
            logger.warning(
                "scout_desk: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception("scout_desk: failed to emit thinking event")


# -- Helpers ------------------------------------------------------------------


def _format_dispatch_message(*, scout_id: str, story_unit_id: str) -> str:
    """User message for a single-scout dispatch.

    The scout's prompt drives WHAT to do; this hands it the candidate id.
    """
    return (
        f"## Dispatch\n"
        f"You are the {scout_id} sub-scout. The Editor has dispatched you to "
        f"investigate the story unit `{story_unit_id}`.\n\n"
        "## Tools available\n"
        "- `query_candidates(state=, region=, sport=, ...)` — read the candidate "
        "pool from BigQuery.\n"
        "- `grounded_search(query)` — Gemini Google Search grounding.\n"
        "- `wire_emit(message=, message_type=, ...)` — emit a Wire event "
        "(in-process write-through proxy).\n"
        "- `write_lead_report(story_unit_id=, story_unit_title=, "
        "story_unit_type=, signal_type=, confidence=, notes=, evidence_refs=)` "
        "— persist your finding.\n\n"
        "## Goal\n"
        "Investigate the place / program / pattern. Build confidence visibly "
        "via Wire emits as sources confirm or contradict. When ready, write a "
        "Lead Report. NEVER name an individual Team USA athlete in any tool "
        "call argument or Wire message."
    )


def _format_pass_message(*, scout_id: str, candidate_ids: list[str]) -> str:
    """User message for a parallel-pass invocation. Hands the scout a slate."""
    ids_str = ", ".join(candidate_ids[:25]) if candidate_ids else "(empty)"
    return (
        f"## Pass\n"
        f"You are the {scout_id} sub-scout. The Editor has handed you a "
        f"candidate slate. Decide which to investigate first based on your "
        f"own signal.\n\n"
        f"## Candidate ids\n{ids_str}\n\n"
        "## Tools\n"
        "- `query_candidates(...)`, `grounded_search(query)`, `wire_emit(...)`, "
        "`write_lead_report(...)`.\n\n"
        "## Goal\nWrite Lead Reports for any story units that fit your signal. "
        "Build confidence visibly. NEVER name an individual athlete."
    )


def _candidates_to_id_list(candidates: list[Any]) -> list[str]:
    """Coerce a candidate list into story_unit_id strings."""
    out: list[str] = []
    for c in candidates or []:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict):
            sid = c.get("story_unit_id")
            if sid:
                out.append(str(sid))
        else:
            sid = getattr(c, "story_unit_id", None)
            if sid:
                out.append(str(sid))
    return out


def _doc_to_dict(doc: Any) -> dict:
    """Coerce a Firestore doc snapshot (or already-a-dict) to a plain dict."""
    if isinstance(doc, dict):
        return doc
    if hasattr(doc, "to_dict"):
        try:
            d = doc.to_dict() or {}
            # Some snapshot stubs expose .id alongside; preserve if doc shape
            # didn't include it.
            if "id" not in d and hasattr(doc, "id"):
                d = dict(d)
                d["id"] = doc.id
            return d
        except Exception:
            return {}
    return {}


class _PlaceholderParallel:
    def __init__(self, *, name: str, sub_agents: list[Any]) -> None:
        self.name = name
        self.sub_agents = sub_agents
