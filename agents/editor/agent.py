"""EditorAgent: orchestrator + autonomous loop owner.

The Editor is the *root* agent in ADK's hierarchy (BUILD_SPEC §3.6) but
sub-scouts/Investigator/etc. are NOT registered as ADK auto-handoff sub-
agents. Handoffs are mediated by Editor's tool-call decisions and Python
invokes the next agent's Runner. This protects Voice Signatures (CONSTITUTION
Law 2) — see plan §A.5 / HOE-DEC §HOE-REVIEW item 5.

Voice signature is enforced by `/prompts/editor.md`; this Python file
contains zero voice text.

Day-3 body of `think_once` resolves plan §G open question 3 empirically:
ADK's `LlmAgent` honors `vertexai.init(location='global')` set at runtime
boot — no special override needed (verified by running the cycle and
observing 200s on calls to `gemini-3.1-pro-preview`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.cost.counters import CostCeilingExceeded
from agents.editor.loop import autonomous_loop
from agents.observability import log_agent_call, trace_span
from agents.wire.emit import WireProxyNotReadyError
from agents.wire.pacing import WirePacer
from agents.wire.types import InvestigationContext

logger = logging.getLogger(__name__)


# Default ID used for the Editor's autonomous (non-investigation) cycles.
_AMBIENT_INVESTIGATION_ID = "editor-ambient"
# How many recent published wire events to surface in context.
_RECENT_PUBLISHED_LIMIT = 10
# Pro-tier per-think-cycle ceiling check axis.
_COST_AXIS = "gemini_pro"


class EditorAgent:
    def __init__(
        self,
        *,
        prompt: str,
        wire: Any,
        scout_desk: Any,
        firestore: Any,
        model_id: str = "gemini-3.1-pro-preview",
        pacer: WirePacer | None = None,
        cost_counter: Any | None = None,
        runtime_state: Any | None = None,
    ) -> None:
        self._prompt = prompt
        self._wire = wire
        self._scout_desk = scout_desk
        self._firestore = firestore
        self._model_id = model_id
        self._pacer = pacer or WirePacer(compression_factor=1.0)
        self._cost_counter = cost_counter
        # Backref to RuntimeState so think_once can stamp last_think_cycle
        # without an import cycle. Optional — None in unit-test paths.
        self._runtime_state = runtime_state
        # Bind the runtime-injected deps to the LLM tool surface ONCE so the
        # ADK Runner can auto-execute tool calls.
        self._bound_tools = self._bind_tools()
        self._llm = self._build_llm()

    @property
    def llm(self) -> Any:
        return self._llm

    @property
    def name(self) -> str:
        return getattr(self._llm, "name", "editor")

    @property
    def model(self) -> str:
        return self._model_id

    # -- Tool binding ---------------------------------------------------------

    def _bind_tools(self) -> list[Any]:
        """Build the Editor's tool list with runtime deps closed over.

        ADK's `LlmAgent.tools` accepts plain callables; the Runner introspects
        the function signature to build the JSONSchema the model sees. We
        define each tool as a closure over `self._wire`, `self._scout_desk`,
        `self._firestore` so ADK only sees clean LLM-facing args. Docstrings
        ARE the LLM-facing spec — be careful when editing.

        Voice text comes from the Editor's prompt, not Python.
        """
        wire = self._wire
        scout_desk = self._scout_desk

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
                story_unit_id: optional id of the place/program/pattern this is about.

            Returns:
                The Firestore doc id of the persisted Wire event.
            """
            event: dict = {
                "agent": "editor",
                "message": message,
                "message_type": message_type,
                "mode": "live",
            }
            if confidence is not None:
                event["confidence"] = confidence
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            return await wire.emit(event)

        async def read_recent_published(limit: int = 10) -> list[dict]:
            """Return the N most-recent published stories (for Editor context).

            Read-only; safe to call any time. Already included in the
            think-cycle's user message — call again only to refresh.
            """
            return await self._read_recent_published(limit=limit)

        async def read_queue() -> list[dict]:
            """Return the current in-flight queue: leads, investigations, drafts.

            Read-only; safe to call any time. Already included in the
            think-cycle's user message.
            """
            return await self._read_queue()

        async def dispatch_scout(scout_id: str, story_unit_id: str) -> dict:
            """Dispatch a sub-scout to investigate a place / program / pattern.

            Args:
                scout_id: 'cinderella' | 'comeback' | 'hometown' | 'echo'.
                story_unit_id: stable id (NEVER an athlete id).

            Returns:
                The Scout Desk's dispatch result:
                `{dispatched, scout, story_unit_id, lead_report_id?,
                 tool_calls, latency_ms, input_tokens, output_tokens}`.
            """
            if scout_desk is None:
                raise RuntimeError("dispatch_scout: no `scout_desk` instance was injected")
            if scout_id not in {"cinderella", "comeback", "hometown", "echo"}:
                logger.warning(
                    "editor.dispatch_scout: unknown scout_id=%r", scout_id
                )
                return {
                    "dispatched": False,
                    "scout": scout_id,
                    "story_unit_id": story_unit_id,
                    "error": f"unknown scout_id: {scout_id}",
                }
            logger.info(
                "editor.dispatch_scout: scout=%s story_unit_id=%s",
                scout_id, story_unit_id,
            )
            return await scout_desk.dispatch_one(scout_id, story_unit_id)

        async def accept_equity_recommendation(recommendation_id: str) -> dict:
            """Apply a Paralympic Equity Editor feed-drift recommendation.

            Args:
                recommendation_id: id of the recommendation to apply.
            """
            logger.info(
                "editor.accept_equity_recommendation: id=%s", recommendation_id
            )
            return {"accepted": True, "recommendation_id": recommendation_id}

        return [
            wire_emit,
            read_recent_published,
            read_queue,
            dispatch_scout,
            accept_equity_recommendation,
        ]

    def _build_llm(self) -> Any:
        try:
            from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

            return LlmAgent(
                name="editor",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )
        except ImportError:
            logger.warning("google.adk not installed; EditorAgent built as placeholder shell")
            return _PlaceholderEditor(
                name="editor",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )

    # -- One think-cycle ------------------------------------------------------

    async def think_once(self, ctx: InvestigationContext | None = None) -> dict:
        """One autonomous think-cycle: build context → invoke Runner → react.

        Day-3 body: real ADK Runner invocation against
        `gemini-3.1-pro-preview` on `vertexai.init(location='global')`. Tool
        calls the model emits are auto-executed by the Runner.

        Failure modes (BUILD_SPEC §17.1):
          - Runner exception → emit a Wire `thinking` event ("hold — model
            returned an error, retrying with shorter context"), retry once
            with truncated prompt, then skip the cycle. The autonomous_loop's
            recovery_backoff_seconds sleeps before the next attempt.
          - CostCeilingExceeded → emit "*daily Pro cap reached, room is
            conserving*" and skip.
          - WireProxyNotReadyError → log and skip (NIL Layer not loaded;
            runtime should have failed-closed at boot, but defense in depth).

        Returns a small dict with the cycle's outcome (used by tests).
        """
        # AGENT_RUNTIME_PAUSED is checked at the top of autonomous_loop too;
        # we re-check here because think_once is also the entry from
        # POST /api/investigate, which doesn't go through the loop's check.
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug("editor.think_once: paused (AGENT_RUNTIME_PAUSED=1); skipping")
            return {"action": "skipped", "reason": "paused"}

        investigation_id = (
            ctx.investigation_id if ctx is not None else _AMBIENT_INVESTIGATION_ID
        )
        compression_factor = ctx.compression_factor if ctx is not None else 1.0

        # --- Cost ceiling pre-check (BUILD_SPEC §15.3) ------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="editor"
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*daily Pro cap reached, room is conserving*",
                    investigation_id=investigation_id,
                )
                return {"action": "skipped", "reason": "cost_ceiling"}

        # --- Build context snapshot for the model -----------------------------
        snapshot = await self._build_context_snapshot()

        # --- Invoke ADK Runner (with retry on transient failures) ------------
        with trace_span(
            "editor.think_once",
            investigation_id=investigation_id,
            attrs={"compression_factor": compression_factor},
        ):
            t0 = time.monotonic()
            try:
                result = await self._invoke_runner(
                    user_message=_format_user_message(snapshot),
                    investigation_id=investigation_id,
                )
            except _RunnerFailedAfterRetryError as e:
                # BUILD_SPEC §17.1: emit a Wire event then skip this cycle.
                await self._safe_emit_thinking(
                    "*hold — model returned an error, retrying with shorter context*",
                    investigation_id=investigation_id,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="editor",
                    sub_agent=None,
                    story_unit_id=None,
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
                return {"action": "error", "reason": str(e)}
            except WireProxyNotReadyError:
                logger.warning("editor.think_once: WireProxyNotReady; skipping cycle")
                return {"action": "skipped", "reason": "wire_not_ready"}

            latency_ms = int((time.monotonic() - t0) * 1000)

        # --- Cost increment (after the call so we have token counts) --------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="editor",
                    sub_agent=None,
                    axis=_COST_AXIS,
                    model=self._model_id,
                    calls=1,
                    input_tokens=int(result.get("input_tokens") or 0),
                    output_tokens=int(result.get("output_tokens") or 0),
                )
            except Exception:
                logger.exception("editor.think_once: cost_counter.increment failed")

        # --- Structured Cloud Logging (BUILD_SPEC §16.1) --------------------
        log_agent_call(
            agent="editor",
            sub_agent=None,
            story_unit_id=None,
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
            "tool_calls": result.get("tool_calls", []),
            "latency_ms": latency_ms,
        }

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """Always-on loop wrapper. See `autonomous_loop` in `loop.py`."""
        await autonomous_loop(self.think_once, stop_event=stop_event, pacer=self._pacer)

    # -- Internals ------------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        """Update RuntimeState.last_think_cycle so /health/heartbeat is fresh."""
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception("editor.think_once: failed to stamp last_think_cycle")

    async def _build_context_snapshot(self) -> dict:
        """Read recent published feed + queue + cost dashboard.

        Compact (~1-2 KB) JSON for the Editor's user message. Per BUILD_SPEC
        §3.6 + plan §A.5, the Editor's prompt drives the decision; Python
        only assembles the snapshot.
        """
        recent: list[dict] = []
        queue: list[dict] = []
        try:
            recent = await self._read_recent_published()
        except Exception:
            logger.exception("editor: read_recent_published failed; using empty list")
        try:
            queue = await self._read_queue()
        except Exception:
            logger.exception("editor: read_queue failed; using empty list")

        cost_today: dict[str, int] = {}
        if self._cost_counter is not None:
            try:
                cost_today = self._cost_counter.snapshot_today()
            except Exception:
                logger.exception("editor: cost_counter.snapshot_today failed")
                cost_today = {}

        return {
            "recent_published": recent,
            "queue": queue,
            "cost_today": cost_today,
        }

    async def _read_recent_published(self, *, limit: int = _RECENT_PUBLISHED_LIMIT) -> list[dict]:
        """Last N published wire events from Firestore.

        Per BUILD_SPEC §6.2: published broadcasts surface as `wire_events`
        with `mode='published'`. There is no separate `published_stories`
        collection (the prompt's note allowed either; we use what exists).
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        try:
            coll = self._firestore.collection("wire_events")
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(filter=FieldFilter("mode", "==", "published"))
            except Exception:
                # Older SDK / stub shape.
                q = (
                    coll.where("mode", "==", "published")
                    if hasattr(coll, "where")
                    else coll
                )
            if hasattr(q, "order_by"):
                try:
                    q = q.order_by("timestamp", direction="DESCENDING")
                except TypeError:
                    q = q.order_by("timestamp")
            if hasattr(q, "limit"):
                q = q.limit(limit)
            out: list[dict] = []
            stream = q.stream() if hasattr(q, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    out.append(_summarize_wire_doc(d))
            else:
                for d in stream:
                    out.append(_summarize_wire_doc(d))
            return out[:limit]
        except Exception:
            logger.exception("editor: read_recent_published: firestore query failed")
            return []

    async def _read_queue(self) -> list[dict]:
        """Current in-flight queue from Firestore `lead_reports`.

        Filters to `status in ('investigating', 'promoted')` per BUILD_SPEC §8.3.
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        try:
            coll = self._firestore.collection("lead_reports")
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(
                    filter=FieldFilter("status", "in", ["investigating", "promoted"])
                )
            except Exception:
                q = (
                    coll.where("status", "in", ["investigating", "promoted"])
                    if hasattr(coll, "where")
                    else coll
                )
            if hasattr(q, "limit"):
                q = q.limit(50)
            out: list[dict] = []
            stream = q.stream() if hasattr(q, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    out.append(_summarize_lead_doc(d))
            else:
                for d in stream:
                    out.append(_summarize_lead_doc(d))
            return out
        except Exception:
            logger.exception("editor: read_queue: firestore query failed")
            return []

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
            WireProxyNotReadyError propagated unchanged (caller decides).
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
                # Not a model error — propagate so the caller can skip cleanly.
                raise
            except Exception as e:
                last_exc = e
                logger.warning(
                    "editor.think_once: Runner attempt %d/%d failed: %s",
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
            # Dev-mode without ADK installed — return an empty result so the
            # autonomous loop keeps running. Unit tests patch this method.
            logger.warning("editor: google.adk not installed; think_once is a no-op")
            return {"tool_calls": [], "input_tokens": 0, "output_tokens": 0}

        session_service = InMemorySessionService()
        # NOTE: ADK validates app_name as a Python identifier (empirically:
        # `letters, digits, and underscores` only — no hyphens). We use
        # `storytellers_room` to match BIGQUERY_DATASET conventions.
        runner = Runner(
            app_name="storytellers_room",
            agent=self._llm,
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = f"editor-{investigation_id}-{uuid.uuid4().hex[:8]}"
        user_content = genai_types.Content(
            parts=[genai_types.Part(text=user_message)],
            role="user",
        )

        tool_calls: list[dict] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async for event in runner.run_async(
                user_id="editor-runtime",
                session_id=session_id,
                new_message=user_content,
            ):
                # Track tool calls the model made (ADK auto-executes them).
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
                # Roll up usage metadata when present.
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
                logger.debug("editor: runner.close() raised", exc_info=True)

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
                    "agent": "editor",
                    "message": message,
                    "message_type": "thinking",
                    "mode": "live",
                },
                investigation_id=investigation_id,
            )
        except WireProxyNotReadyError:
            logger.warning("editor: wire proxy not ready; cannot emit thinking event")
        except Exception:
            logger.exception("editor: failed to emit thinking event")


# -- Helpers ------------------------------------------------------------------


class _RunnerFailedAfterRetryError(RuntimeError):
    """Raised by `_invoke_runner` after both Runner attempts fail."""


def _format_user_message(snapshot: dict) -> str:
    """Compact, human-readable user message for the Editor's Runner.

    The Editor's prompt drives WHAT to do; this just hands it the state.
    """
    recent = snapshot.get("recent_published", [])
    queue = snapshot.get("queue", [])
    cost = snapshot.get("cost_today", {})
    return (
        "## Recent published feed (last 10)\n"
        f"{json.dumps(recent, ensure_ascii=False)}\n\n"
        "## Active queue\n"
        f"{json.dumps(queue, ensure_ascii=False)}\n\n"
        "## Cost dashboard (today, USD-equivalent axes)\n"
        f"{json.dumps(cost, ensure_ascii=False)}\n\n"
        "## What is your decision for this think-cycle?\n"
        "Choose one: dispatch a Scout, advance an investigation, accept an "
        "Equity recommendation, or sleep. Keep your wire utterance terse "
        "(8-15 words)."
    )


def _truncate_for_retry(message: str, max_chars: int = 1500) -> str:
    """Shorter context for the second attempt (BUILD_SPEC §17.1).

    Keeps the prompt-shape intact (headings still present) so the model
    behaves the same; just drops the bulk of the snapshot bodies.
    """
    if len(message) <= max_chars:
        return message
    head = message[: max_chars // 2]
    tail = message[-max_chars // 2 :]
    return f"{head}\n... [context truncated for retry] ...\n{tail}"


def _summarize_wire_doc(doc: Any) -> dict:
    """Reduce a Firestore wire_events doc to the fields the Editor cares about."""
    data = doc.to_dict() if hasattr(doc, "to_dict") else (doc if isinstance(doc, dict) else {})
    return {
        "story_unit_id": data.get("story_unit_id"),
        "agent": data.get("agent"),
        "message_type": data.get("message_type"),
    }


def _summarize_lead_doc(doc: Any) -> dict:
    """Reduce a Firestore lead_reports doc to the fields the Editor cares about."""
    data = doc.to_dict() if hasattr(doc, "to_dict") else (doc if isinstance(doc, dict) else {})
    return {
        "id": data.get("id") or getattr(doc, "id", None),
        "story_unit_id": data.get("story_unit_id"),
        "story_unit_type": data.get("story_unit_type"),
        "scout": data.get("scout"),
        "confidence": data.get("confidence"),
        "status": data.get("status"),
    }


class _PlaceholderEditor:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        instruction: str,
        tools: list | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.instruction = instruction
        self.tools: list = list(tools or [])
