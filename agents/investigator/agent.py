"""InvestigatorAgent: turns Scout Lead Reports into Investigation Packets.

Mirrors `EditorAgent` (`agents/editor/agent.py`) end-to-end:
  - Closure-bound tools via `_bind_tools`.
  - ADK `LlmAgent` constructed once in `_build_llm`.
  - Single Runner invocation in `_run_adk_once`, with retry + truncated-context
    fallback in `_invoke_runner`.
  - Failure modes (BUILD_SPEC §17.1): cost ceiling, runner exception, lead
    report not found, wire-proxy not ready — each emits a Wire `thinking`
    event then returns a structured error dict.

Voice signature lives in `/prompts/investigator.md` (CONSTITUTION Rule 1 +
Law 2). Python here contains zero voice text.

Day-4 body of `investigate(lead_report_id)` resolves the live ADK Runner path
the same way `EditorAgent.think_once` did — `gemini-3.1-pro-preview` on
`vertexai.init(location='global')`, no special override needed.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.cost.counters import CostCeilingExceeded
from agents.investigator.tools import (
    LeadReportNotFoundError,
    build_investigator_tools,
)
from agents.observability import log_agent_call, trace_span
from agents.wire.emit import WireProxyNotReadyError
from agents.wire.types import InvestigationContext

logger = logging.getLogger(__name__)


# Pro-tier cost axis (BUILD_SPEC §15.3).
_COST_AXIS = "gemini_pro"
# Default ceiling pre-check axis is per-investigation tokens; the cost
# counter aggregates today's totals (see counters._DEFAULT_CEILINGS).


class InvestigatorAgent:
    """The Investigator: depth-of-research synthesis.

    Construction mirrors EditorAgent — same kwargs, same tool-binding
    pattern, same fallback to a placeholder shell when ADK isn't on the
    host. Voice is in the prompt; this Python file does no voice work.
    """

    def __init__(
        self,
        *,
        prompt: str,
        wire: Any,
        firestore: Any,
        bigquery: Any,
        model_id: str = "gemini-3.1-pro-preview",
        cost_counter: Any | None = None,
        wire_vocabulary: Any | None = None,
        runtime_state: Any | None = None,
    ) -> None:
        self._prompt = prompt
        self._wire = wire
        self._firestore = firestore
        self._bigquery = bigquery
        self._model_id = model_id
        self._cost_counter = cost_counter
        # Backref so investigate() can stamp last_think_cycle on RuntimeState
        # (consistent with EditorAgent's pattern). Optional — None in tests.
        self._runtime_state = runtime_state
        self._wire_vocabulary = wire_vocabulary
        self._bound_tools = self._bind_tools()
        self._llm = self._build_llm()

    # -- Public surface ------------------------------------------------------

    @property
    def llm(self) -> Any:
        return self._llm

    @property
    def name(self) -> str:
        return getattr(self._llm, "name", "investigator")

    @property
    def model(self) -> str:
        return self._model_id

    # -- Tool binding --------------------------------------------------------

    def _bind_tools(self) -> list[Any]:
        """Build the Investigator's tool list with runtime deps closed over.

        Six tools the Investigator's Pro model has:
          - `wire_emit` — the in-process write-through proxy.
          - `read_lead_report(lead_report_id)` — Firestore fetch.
          - `grounded_search(query)` — Gemini google_search grounding.
          - `query_historical_athletes(...)` — BigQuery; aggregate counts only.
          - `query_geography(...)` — BigQuery; place/region context.
          - `call_deep_research(question, max_seconds)` — wraps Deep Research
            with 90s timeout + Wire-thinking fallback (BUILD_SPEC §3.2).
          - `write_investigation_packet(...)` — Firestore persist.
          - `pull_vocabulary(...)` — optional Wire vocabulary draws.

        Voice text comes from the prompt, not Python.
        """
        wire = self._wire
        vocabulary = self._wire_vocabulary
        agent_name = "investigator"

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
                message: the displayed text. Will be NIL-scanned. NEVER
                    name an individual Team USA athlete.
                message_type: 'thinking' | 'milestone' | 'intervention' | 'decision'.
                confidence: optional 0.0-1.0.
                story_unit_id: optional id of the place / program / pattern.

            Returns:
                The Firestore doc id of the persisted Wire event.
            """
            event: dict = {
                "agent": "investigator",
                "message": message,
                "message_type": message_type,
                "mode": "live",
            }
            if confidence is not None:
                event["confidence"] = confidence
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            return await wire.emit(event)

        async def pull_vocabulary(message_type: str = "thinking", **slots: Any) -> str:
            """Pull a curated voice-fragment from the Wire Vocabulary library.

            Use for in-progress 'thinking' events to maintain consistent
            Wire voice texture (BUILD_SPEC §6.3 + §6.4). Fragments may
            contain `[snake_case]` slots — pass them as kwargs.

            Args:
                message_type: 'thinking' | 'milestone' | 'intervention' | 'decision'
                **slots: kwargs filled into [snake_case] placeholders
                    (e.g., place="Mt. Pleasant", outlet="Quad-City Times").

            Returns:
                A filled fragment string. Use it directly as the message in
                your next wire_emit call. If the fragment library is empty
                for this agent + message_type, returns an empty string and
                you should fall back to free-text generation.
            """
            if vocabulary is None:
                return ""
            fragment = vocabulary.sample(agent_name, message_type)
            if fragment is None:
                return ""
            return vocabulary.fill(fragment, **slots)

        # The six runtime-bound tools live in `tools.py`; we just append the
        # two wire/vocabulary closures defined above.
        runtime_tools = build_investigator_tools(
            wire=wire,
            firestore=self._firestore,
            bigquery=self._bigquery,
            cost_counter=self._cost_counter,
        )

        return [wire_emit, *runtime_tools, pull_vocabulary]

    def _build_llm(self) -> Any:
        try:
            from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

            return LlmAgent(
                name="investigator",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )
        except ImportError:
            logger.warning(
                "google.adk not installed; InvestigatorAgent built as placeholder shell"
            )
            return _PlaceholderInvestigator(
                name="investigator",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )

    # -- One investigation cycle ---------------------------------------------

    async def investigate(
        self,
        lead_report_id: str,
        *,
        ctx: InvestigationContext | None = None,
    ) -> dict:
        """One full investigation cycle.

        Flow:
          1. Pause check (AGENT_RUNTIME_PAUSED).
          2. Cost ceiling pre-check on `axis='gemini_pro'` (BUILD_SPEC §15.3).
          3. Read the Lead Report from Firestore (raises if missing).
          4. Build a context snapshot — Lead Report + prior packets +
             cost dashboard.
          5. Invoke the ADK Runner. The model auto-executes its tool calls
             (grounded_search, query_historical_athletes, ...,
             write_investigation_packet).
          6. Read back the most-recent investigation_packets doc to surface
             its id in the return dict.
          7. Cost increment + structured logging + Wire milestone.

        Failure modes (BUILD_SPEC §17.1):
          - Runner exception → emit thinking event, retry once with
            truncated context, then skip and return error.
          - CostCeilingExceeded → emit "*daily Pro cap reached, investigator
            pausing*" and skip.
          - LeadReportNotFoundError → emit thinking, return error.
          - WireProxyNotReadyError → log + skip.

        Returns: a dict with the cycle's outcome.
        """
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug("investigator.investigate: paused (AGENT_RUNTIME_PAUSED=1)")
            return {"action": "skipped", "reason": "paused"}

        investigation_id = (
            ctx.investigation_id
            if ctx is not None
            else f"investigator-{lead_report_id}"
        )
        compression_factor = ctx.compression_factor if ctx is not None else 1.0

        # --- Cost ceiling pre-check ----------------------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="investigator"
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*daily Pro cap reached, investigator pausing*",
                    investigation_id=investigation_id,
                )
                return {"action": "skipped", "reason": "cost_ceiling"}

        # --- Read the Lead Report (blocks if missing) ----------------------
        try:
            lead_report = await self._read_lead_report(lead_report_id)
        except LeadReportNotFoundError as e:
            await self._safe_emit_thinking(
                f"*lead report missing: {lead_report_id}; cannot proceed*",
                investigation_id=investigation_id,
            )
            logger.warning("investigator.investigate: lead_report missing: %s", e)
            return {
                "action": "error",
                "reason": "lead_report_not_found",
                "lead_report_id": lead_report_id,
            }

        story_unit_id = lead_report.get("story_unit_id") if isinstance(lead_report, dict) else None

        # --- Build context snapshot ----------------------------------------
        snapshot = await self._build_context_snapshot(lead_report=lead_report)

        # --- Invoke ADK Runner ---------------------------------------------
        with trace_span(
            "investigator.investigate",
            investigation_id=investigation_id,
            attrs={
                "lead_report_id": lead_report_id,
                "story_unit_id": story_unit_id,
                "compression_factor": compression_factor,
            },
        ):
            t0 = time.monotonic()
            try:
                result = await self._invoke_runner(
                    user_message=_format_user_message(
                        lead_report_id=lead_report_id, snapshot=snapshot
                    ),
                    investigation_id=investigation_id,
                )
            except _RunnerFailedAfterRetryError as e:
                await self._safe_emit_thinking(
                    "*hold — model returned an error, retrying with shorter context*",
                    investigation_id=investigation_id,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="investigator",
                    sub_agent=None,
                    story_unit_id=story_unit_id,
                    investigation_id=investigation_id,
                    model=self._model_id,
                    tool=None,
                    latency_ms=latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    compression_factor=compression_factor,
                    outcome="error",
                    wire_event_id=None,
                    error=str(e),
                )
                self._stamp_last_think_cycle()
                return {
                    "action": "error",
                    "reason": str(e),
                    "lead_report_id": lead_report_id,
                }
            except WireProxyNotReadyError:
                logger.warning(
                    "investigator.investigate: WireProxyNotReady; skipping cycle"
                )
                return {"action": "skipped", "reason": "wire_not_ready"}

            latency_ms = int((time.monotonic() - t0) * 1000)

        # --- Cost increment + structured logging --------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="investigator",
                    sub_agent=None,
                    axis=_COST_AXIS,
                    model=self._model_id,
                    calls=1,
                    input_tokens=int(result.get("input_tokens") or 0),
                    output_tokens=int(result.get("output_tokens") or 0),
                )
            except Exception:
                logger.exception(
                    "investigator.investigate: cost_counter.increment failed"
                )

        # --- Read back the most-recent Investigation Packet ---------------
        packet_id = None
        if story_unit_id:
            packet_id = await self._latest_investigation_packet_id(
                story_unit_id=story_unit_id
            )

        # --- Milestone Wire event -----------------------------------------
        if packet_id is not None:
            await self._safe_emit_milestone(
                "Investigation packet drafted.",
                investigation_id=investigation_id,
                story_unit_id=story_unit_id,
            )

        log_agent_call(
            agent="investigator",
            sub_agent=None,
            story_unit_id=story_unit_id,
            investigation_id=investigation_id,
            model=self._model_id,
            tool=None,
            latency_ms=latency_ms,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            compression_factor=compression_factor,
            outcome="success",
            wire_event_id=None,
            error=None,
        )

        self._stamp_last_think_cycle()
        return {
            "action": "ok",
            "lead_report_id": lead_report_id,
            "story_unit_id": story_unit_id,
            "investigation_packet_id": packet_id,
            "tool_calls": result.get("tool_calls", []),
            "latency_ms": latency_ms,
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
        }

    # -- Internals -----------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        """Update RuntimeState.last_think_cycle (best-effort)."""
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception("investigator: failed to stamp last_think_cycle")

    async def _read_lead_report(self, lead_report_id: str) -> dict:
        """Read a Lead Report — proxy to the bound tool so behavior matches."""
        # Find the bound tool. Prefer the closure surface so tests that swap
        # the tool implementation (e.g., monkey-patched `read_lead_report`)
        # see the swap reflected here.
        for tool in self._bound_tools:
            if getattr(tool, "__name__", "") == "read_lead_report":
                return await tool(lead_report_id)
        # Fallback: fail closed.
        raise LeadReportNotFoundError(
            f"read_lead_report tool not bound; cannot read {lead_report_id!r}"
        )

    async def _build_context_snapshot(self, *, lead_report: dict) -> dict:
        """Compact JSON for the Investigator's user message.

        Contains the source Lead Report, any prior Investigation Packets
        for the same story_unit_id (so we don't re-investigate), and the
        cost dashboard. The Investigator's prompt drives the actual
        decision; Python only assembles state.
        """
        story_unit_id = lead_report.get("story_unit_id") if isinstance(lead_report, dict) else None

        prior_packets: list[dict] = []
        if story_unit_id:
            try:
                prior_packets = await self._read_prior_packets(story_unit_id)
            except Exception:
                logger.exception(
                    "investigator: read_prior_packets failed; using empty list"
                )

        cost_today: dict[str, int] = {}
        if self._cost_counter is not None:
            try:
                cost_today = self._cost_counter.snapshot_today()
            except Exception:
                logger.exception(
                    "investigator: cost_counter.snapshot_today failed"
                )
                cost_today = {}

        return {
            "lead_report": lead_report,
            "prior_packets": prior_packets,
            "cost_today": cost_today,
        }

    async def _read_prior_packets(self, story_unit_id: str) -> list[dict]:
        """Return prior Investigation Packets for the same story_unit_id."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        try:
            coll = self._firestore.collection("investigation_packets")
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(
                    filter=FieldFilter("story_unit_id", "==", story_unit_id)
                )
            except Exception:
                q = (
                    coll.where("story_unit_id", "==", story_unit_id)
                    if hasattr(coll, "where")
                    else coll
                )
            if hasattr(q, "limit"):
                q = q.limit(5)
            stream = q.stream() if hasattr(q, "stream") else []
            out: list[dict] = []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    out.append(_summarize_packet_doc(d))
            else:
                for d in stream:
                    out.append(_summarize_packet_doc(d))
            return out
        except Exception:
            logger.exception(
                "investigator: read_prior_packets: firestore query failed"
            )
            return []

    async def _latest_investigation_packet_id(
        self,
        *,
        story_unit_id: str,
    ) -> str | None:
        """Return the id of the most recent Investigation Packet for the
        story_unit_id. None if none."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return None
        try:
            coll = self._firestore.collection("investigation_packets")
            stream = coll.stream() if hasattr(coll, "stream") else []
            docs: list[dict] = []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    docs.append(_doc_to_dict(d))
            else:
                for d in stream:
                    docs.append(_doc_to_dict(d))
            best: dict | None = None
            for doc in docs:
                if doc.get("story_unit_id") != story_unit_id:
                    continue
                created = doc.get("created_at") or ""
                if best is None or created > (best.get("created_at") or ""):
                    best = doc
            if best is None:
                return None
            return best.get("id")
        except Exception:
            logger.exception(
                "investigator: latest_investigation_packet_id failed"
            )
            return None

    async def _invoke_runner(
        self,
        *,
        user_message: str,
        investigation_id: str,
    ) -> dict:
        """One ADK Runner invocation. Retries once with shorter context.

        Returns:
            `{"tool_calls": [...], "input_tokens": int|None, "output_tokens": int|None}`

        Raises:
            _RunnerFailedAfterRetryError after both attempts fail.
            WireProxyNotReadyError propagated unchanged.
        """
        attempts = [user_message, _truncate_for_retry(user_message)]
        last_exc: Exception | None = None
        for i, msg in enumerate(attempts, start=1):
            try:
                return await self._run_adk_once(
                    user_message=msg,
                    investigation_id=investigation_id,
                )
            except WireProxyNotReadyError:
                raise
            except Exception as e:
                last_exc = e
                logger.warning(
                    "investigator.investigate: Runner attempt %d/%d failed: %s",
                    i, len(attempts), e,
                )
        raise _RunnerFailedAfterRetryError(str(last_exc))

    async def _run_adk_once(
        self,
        *,
        user_message: str,
        investigation_id: str,
    ) -> dict:
        """One ADK Runner invocation. Returns parsed result dict."""
        try:
            from google.adk import Runner  # type: ignore[import-untyped]
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "investigator: google.adk not installed; investigate is a no-op"
            )
            return {"tool_calls": [], "input_tokens": 0, "output_tokens": 0}

        session_service = InMemorySessionService()
        # ADK validates app_name as a Python identifier (letters/digits/underscores).
        runner = Runner(
            app_name="storytellers_room",
            agent=self._llm,
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = f"investigator-{investigation_id}-{uuid.uuid4().hex[:8]}"
        user_content = genai_types.Content(
            parts=[genai_types.Part(text=user_message)],
            role="user",
        )

        tool_calls: list[dict] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async for event in runner.run_async(
                user_id="investigator-runtime",
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
                logger.debug("investigator: runner.close() raised", exc_info=True)

        return {
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    async def _safe_emit_thinking(
        self,
        message: str,
        *,
        investigation_id: str,
    ) -> None:
        """Emit a Wire `thinking` event without raising into the loop."""
        try:
            await self._wire.emit(
                {
                    "agent": "investigator",
                    "message": message,
                    "message_type": "thinking",
                    "mode": "live",
                },
                investigation_id=investigation_id,
            )
        except WireProxyNotReadyError:
            logger.warning(
                "investigator: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "investigator: failed to emit thinking event"
            )

    async def _safe_emit_milestone(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None = None,
    ) -> None:
        """Emit a Wire `milestone` event without raising into the loop."""
        try:
            event: dict = {
                "agent": "investigator",
                "message": message,
                "message_type": "milestone",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "investigator: wire proxy not ready; cannot emit milestone event"
            )
        except Exception:
            logger.exception(
                "investigator: failed to emit milestone event"
            )


# -- Helpers ------------------------------------------------------------------


class _RunnerFailedAfterRetryError(RuntimeError):
    """Raised by `_invoke_runner` after both Runner attempts fail."""


def _format_user_message(*, lead_report_id: str, snapshot: dict) -> str:
    """Compact user message handed to the ADK Runner.

    The Investigator's prompt drives WHAT to do; this hands it the source
    Lead Report + prior packets + cost dashboard. The model decides which
    tools to call.
    """
    lead_report = snapshot.get("lead_report") or {}
    prior_packets = snapshot.get("prior_packets") or []
    cost_today = snapshot.get("cost_today") or {}
    return (
        f"## Investigation assignment\n"
        f"You have been dispatched to deepen Lead Report `{lead_report_id}` "
        "into a full Investigation Packet (BUILD_SPEC §8.4).\n\n"
        "## Source Lead Report\n"
        f"{json.dumps(lead_report, ensure_ascii=False, default=str)}\n\n"
        "## Prior Investigation Packets for the same story unit (last 5)\n"
        f"{json.dumps(prior_packets, ensure_ascii=False, default=str)}\n\n"
        "## Cost dashboard (today)\n"
        f"{json.dumps(cost_today, ensure_ascii=False, default=str)}\n\n"
        "## Goal\n"
        "Build the Investigation Packet for this place / program / pattern. "
        "Pull public sources via grounded_search; cross-reference parallel "
        "ERAS via query_historical_athletes (aggregate counts only — never "
        "name athletes); confirm geography via query_geography; for "
        "high-priority leads, kick off call_deep_research (90s timeout — "
        "fall back to grounded_search if it stalls). Build confidence "
        "visibly via wire_emit. When ready, call write_investigation_packet "
        "with all required fields. NEVER name an individual Team USA "
        "athlete in any tool argument or Wire message. Use conditional "
        "phrasing for forward-looking claims."
    )


def _truncate_for_retry(message: str, max_chars: int = 1500) -> str:
    """Shorter context for the second attempt (BUILD_SPEC §17.1)."""
    if len(message) <= max_chars:
        return message
    head = message[: max_chars // 2]
    tail = message[-max_chars // 2 :]
    return f"{head}\n... [context truncated for retry] ...\n{tail}"


def _summarize_packet_doc(doc: Any) -> dict:
    """Reduce an investigation_packets doc to the fields the Investigator cares about."""
    data = doc.to_dict() if hasattr(doc, "to_dict") else (doc if isinstance(doc, dict) else {})
    return {
        "id": data.get("id") or getattr(doc, "id", None),
        "story_unit_id": data.get("story_unit_id"),
        "ready_for_storyteller": data.get("ready_for_storyteller"),
        "created_at": data.get("created_at"),
    }


def _doc_to_dict(doc: Any) -> dict:
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


class _PlaceholderInvestigator:
    """Stand-in for `LlmAgent` when ADK isn't on the host."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        instruction: str,
        tools: list[Any] | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.instruction = instruction
        self.tools = list(tools or [])
