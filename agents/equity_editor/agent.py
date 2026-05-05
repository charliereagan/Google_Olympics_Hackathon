"""EquityEditorAgent: Pro-tier parity enforcement at three levels.

Mirrors `agents/editor/agent.py` and `agents/investigator/agent.py`
end-to-end:
  - Closure-bound tools via `_bind_tools`, including the six runtime tools
    from `agents/equity_editor/tools.py::build_equity_editor_tools` plus a
    locally-bound `pull_vocabulary` (vocabulary key 'equity_editor').
  - ADK `LlmAgent` constructed once in `_build_llm`. Falls back to a
    placeholder shell when ADK isn't on the host (dev-mode unit tests).
  - Single Runner invocation in `_run_adk_once`, with retry + truncated-
    context fallback in `_invoke_runner`.
  - Failure modes (BUILD_SPEC §17.1): cost ceiling, runner exception,
    wire-proxy not ready — each emits an arrival-style Wire `intervention`
    event then returns a structured error dict. NOTE: this agent uses
    `intervention` (not `thinking`) for failure-mode events because its
    `streaming_profile.arrival_style = 'instant'` (BUILD_SPEC §6.5).

Voice signature lives in `/prompts/equity_editor.md` per CONSTITUTION
Rule 1. Python here contains zero voice text.

The Equity Editor has no autonomous loop. It is invoked by the Editor's
`request_equity_review` tool (scope='feed' or scope='draft'). The Storyteller
will likewise invoke it after every draft (deferred to Storyteller worker).
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
from agents.equity_editor.tools import build_equity_editor_tools
from agents.observability import log_agent_call, trace_span
from agents.wire.emit import WireProxyNotReadyError
from agents.wire.types import InvestigationContext

logger = logging.getLogger(__name__)


# Pro-tier per-cycle ceiling check axis (BUILD_SPEC §15.3). Same axis the
# Editor and Investigator use — the Equity Editor is also Pro-tier.
_COST_AXIS = "gemini_pro"

# Default investigation_id stamps for the two review entry points.
_AMBIENT_FEED_INVESTIGATION_ID = "equity-editor-feed"


class EquityEditorAgent:
    """The Paralympic Equity Editor.

    Construction mirrors EditorAgent / InvestigatorAgent — same kwargs, same
    tool-binding pattern, same fallback to a placeholder shell when ADK
    isn't on the host.
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
        self._wire_vocabulary = wire_vocabulary
        # Backref so review_*() can stamp last_think_cycle on RuntimeState.
        # Optional — None in unit-test paths; runtime sets it post-construction.
        self._runtime_state = runtime_state
        self._bound_tools = self._bind_tools()
        self._llm = self._build_llm()

    # -- Public surface ------------------------------------------------------

    @property
    def llm(self) -> Any:
        return self._llm

    @property
    def name(self) -> str:
        return getattr(self._llm, "name", "equity_editor")

    @property
    def model(self) -> str:
        return self._model_id

    # -- Tool binding --------------------------------------------------------

    def _bind_tools(self) -> list[Any]:
        """Build the Equity Editor's tool list with runtime deps closed over.

        Tool surface (six from tools.py + pull_vocabulary):
          - read_published_feed(limit=20)
          - read_draft(draft_id)
          - intervene_feed_drift(reason, suggested_priority_lift_story_unit_id)
          - return_draft(draft_id, reason)
          - clear_draft(draft_id)
          - block_draft(draft_id, reason)
          - pull_vocabulary(message_type='intervention'|'milestone', **slots)

        Voice text comes from the prompt, not Python.
        """
        runtime_tools = build_equity_editor_tools(
            wire=self._wire,
            firestore=self._firestore,
            bigquery=self._bigquery,
        )

        vocabulary = self._wire_vocabulary
        agent_name = "equity_editor"

        async def pull_vocabulary(
            message_type: str = "intervention", **slots: Any
        ) -> str:
            """Pull a curated voice-fragment from the equity_editor vocab bucket.

            BUILD_SPEC §6.4 + §6.5. Use `'intervention'` for arrival-style
            parity-correction events (the default — drift, return, block).
            Use `'milestone'` for clean status changes (cleared, parity
            confirmed). NEVER `'thinking'` for this agent — its
            interventions don't stream, they arrive. The fragment may have
            `[snake_case]` slots — pass them as kwargs.

            Args:
                message_type: 'intervention' | 'milestone'.
                **slots: kwargs filled into [snake_case] placeholders
                    (e.g., place="Mt. Pleasant", n=4).

            Returns:
                A filled fragment string, or "" when the library is empty
                for this bucket. The model uses the result as the message
                in its next intervene_feed_drift / return_draft / etc. call.
            """
            if vocabulary is None:
                return ""
            fragment = vocabulary.sample(agent_name, message_type)
            if fragment is None:
                return ""
            return vocabulary.fill(fragment, **slots)

        return [*runtime_tools, pull_vocabulary]

    def _build_llm(self) -> Any:
        try:
            from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

            return LlmAgent(
                name="equity_editor",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )
        except ImportError:
            logger.warning(
                "google.adk not installed; EquityEditorAgent built as placeholder shell"
            )
            return _PlaceholderEquityEditor(
                name="equity_editor",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )

    # -- Public review entry points ------------------------------------------

    async def review_feed(
        self,
        *,
        ctx: InvestigationContext | None = None,
    ) -> dict:
        """Feed-level review — invoked by the Editor periodically.

        The Pro model decides whether to call `read_published_feed` and
        whether the resulting parity stats warrant
        `intervene_feed_drift`. Python only orchestrates the Runner cycle;
        no Python decides WHEN to intervene (CONSTITUTION Law 1).

        Returns: a small dict with the cycle's outcome:
          - `{action: 'ok', tool_calls, latency_ms}` on success.
          - `{action: 'skipped', reason}` for paused / cost-ceiling /
            wire-not-ready states.
          - `{action: 'error', reason}` on Runner-after-retry failure.

        Failure modes (BUILD_SPEC §17.1): emit a Wire intervention event
        ("hold — model returned an error...") on Runner failure, "daily
        Pro cap reached" on cost ceiling. Per BUILD_SPEC §6.5, this agent
        emits arrival-style `intervention` events, not `thinking`.
        """
        return await self._review(
            kind="feed",
            ctx=ctx,
            snapshot_builder=self._build_feed_context_snapshot,
            user_message_formatter=self._format_user_message_feed,
            extra_log_attrs={},
            extra_result_fields={},
        )

    async def review_draft(
        self,
        draft_id: str,
        *,
        ctx: InvestigationContext | None = None,
    ) -> dict:
        """Story-level review of a Storyteller draft.

        The Pro model reads the draft, decides which check to apply
        (Paralympic depth / inspiration-porn safety / pass), and ends the
        cycle by calling exactly one of `clear_draft`, `return_draft`, or
        `block_draft`. The decision is read off the Runner's tool-call
        log; ties or no-call cases are reported as 'no_decision'.

        Returns: `{action, decision, draft_id, reason?, feedback?,
        tool_calls, latency_ms}`. The `decision` field is one of
        `'cleared' | 'returned' | 'blocked' | 'no_decision'`.
        """
        result = await self._review(
            kind="draft",
            ctx=ctx,
            snapshot_builder=lambda: self._build_draft_context_snapshot(draft_id),
            user_message_formatter=lambda snap: self._format_user_message_draft(
                draft_id, snap
            ),
            extra_log_attrs={"draft_id": draft_id},
            extra_result_fields={"draft_id": draft_id},
        )

        # Read the decision off the model's tool-call log. The tools mutate
        # Firestore as a side effect; the Runner result tells us which one
        # the model chose.
        if result.get("action") == "ok":
            decision, feedback = _decision_from_tool_calls(
                result.get("tool_calls") or []
            )
            result["decision"] = decision
            if feedback is not None:
                result["feedback"] = feedback
        return result

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """No autonomous loop. The Editor invokes review_feed() periodically
        (via its `request_equity_review` tool); the Storyteller (or the
        Editor) invokes review_draft() once per draft.

        We honor `stop_event` so the lifespan teardown stays consistent
        with the other agents — but we never spin a cycle ourselves.
        """
        if stop_event is not None:
            try:
                await stop_event.wait()
            except Exception:
                logger.debug("equity_editor.autonomous_loop: stop_event.wait raised")

    # -- Shared review pipeline ---------------------------------------------

    async def _review(
        self,
        *,
        kind: str,
        ctx: InvestigationContext | None,
        snapshot_builder,
        user_message_formatter,
        extra_log_attrs: dict,
        extra_result_fields: dict,
    ) -> dict:
        """Shared body of review_feed / review_draft.

        Steps mirror `EditorAgent.think_once`:
          1. Pause check.
          2. Cost ceiling pre-check.
          3. Build snapshot.
          4. Invoke Runner (retry-once-with-truncated-context).
          5. Cost increment + structured logging.
          6. Stamp RuntimeState.
        """
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug(
                "equity_editor.review_%s: paused (AGENT_RUNTIME_PAUSED=1); skipping",
                kind,
            )
            return {"action": "skipped", "reason": "paused", **extra_result_fields}

        investigation_id = (
            ctx.investigation_id
            if ctx is not None
            else _AMBIENT_FEED_INVESTIGATION_ID if kind == "feed"
            else f"equity-editor-draft-{extra_result_fields.get('draft_id', 'unknown')}"
        )
        compression_factor = ctx.compression_factor if ctx is not None else 1.0

        # --- Cost ceiling pre-check ----------------------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="equity_editor"
                )
            except CostCeilingExceeded:
                await self._safe_emit_intervention(
                    "*daily Pro cap reached, equity editor pausing*",
                    investigation_id=investigation_id,
                )
                return {
                    "action": "skipped",
                    "reason": "cost_ceiling",
                    **extra_result_fields,
                }

        # --- Build context snapshot ----------------------------------------
        try:
            snapshot = await snapshot_builder()
        except Exception:
            logger.exception(
                "equity_editor.review_%s: context snapshot build failed", kind
            )
            snapshot = {}

        # --- Invoke ADK Runner ---------------------------------------------
        with trace_span(
            f"equity_editor.review_{kind}",
            investigation_id=investigation_id,
            attrs={"compression_factor": compression_factor, **extra_log_attrs},
        ):
            t0 = time.monotonic()
            try:
                result = await self._invoke_runner(
                    user_message=user_message_formatter(snapshot),
                    investigation_id=investigation_id,
                    kind=kind,
                )
            except _RunnerFailedAfterRetryError as e:
                await self._safe_emit_intervention(
                    "*hold — model returned an error, retrying with shorter context*",
                    investigation_id=investigation_id,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="equity_editor",
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
                return {
                    "action": "error",
                    "reason": str(e),
                    **extra_result_fields,
                }
            except WireProxyNotReadyError:
                logger.warning(
                    "equity_editor.review_%s: WireProxyNotReady; skipping cycle", kind
                )
                return {
                    "action": "skipped",
                    "reason": "wire_not_ready",
                    **extra_result_fields,
                }

            latency_ms = int((time.monotonic() - t0) * 1000)

        # --- Cost increment + structured logging --------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="equity_editor",
                    sub_agent=None,
                    axis=_COST_AXIS,
                    model=self._model_id,
                    calls=1,
                    input_tokens=int(result.get("input_tokens") or 0),
                    output_tokens=int(result.get("output_tokens") or 0),
                )
            except Exception:
                logger.exception(
                    "equity_editor.review_%s: cost_counter.increment failed", kind
                )

        log_agent_call(
            agent="equity_editor",
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
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            **extra_result_fields,
        }

    # -- Internals -----------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        """Update RuntimeState.last_think_cycle (best-effort)."""
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception(
                "equity_editor: failed to stamp last_think_cycle"
            )

    async def _build_feed_context_snapshot(self) -> dict:
        """Compact JSON for the feed-review user message.

        Reads the recent published feed via the bound `read_published_feed`
        tool so the model sees the same shape it would see if it called the
        tool itself, plus the cost dashboard.
        """
        feed: dict = {}
        try:
            for tool in self._bound_tools:
                if getattr(tool, "__name__", "") == "read_published_feed":
                    feed = await tool(limit=20)
                    break
        except Exception:
            logger.exception(
                "equity_editor: read_published_feed snapshot read failed"
            )
            feed = {}

        cost_today: dict[str, int] = {}
        if self._cost_counter is not None:
            try:
                cost_today = self._cost_counter.snapshot_today()
            except Exception:
                logger.exception(
                    "equity_editor: cost_counter.snapshot_today failed"
                )
                cost_today = {}

        return {"feed": feed, "cost_today": cost_today}

    async def _build_draft_context_snapshot(self, draft_id: str) -> dict:
        """Compact JSON for the draft-review user message.

        Reads the draft via the bound `read_draft` tool. The model can
        re-read the same tool from its own cycle if it wants to verify;
        we hand it the snapshot up front for context.
        """
        draft: dict = {}
        try:
            for tool in self._bound_tools:
                if getattr(tool, "__name__", "") == "read_draft":
                    draft = await tool(draft_id)
                    break
        except Exception:
            logger.exception(
                "equity_editor: read_draft snapshot read failed"
            )
            draft = {"found": False, "draft_id": draft_id, "reason": "snapshot_failed"}

        cost_today: dict[str, int] = {}
        if self._cost_counter is not None:
            try:
                cost_today = self._cost_counter.snapshot_today()
            except Exception:
                logger.exception(
                    "equity_editor: cost_counter.snapshot_today failed"
                )
                cost_today = {}

        return {"draft": draft, "cost_today": cost_today}

    def _format_user_message_feed(self, snapshot: dict) -> str:
        """User message for a feed-level review."""
        feed = snapshot.get("feed") or {}
        cost = snapshot.get("cost_today") or {}
        return (
            "## Feed-level parity review\n"
            "You have been invoked to audit the published feed for "
            "Olympic / Paralympic balance.\n\n"
            "## Aggregate parity stats (recent published places)\n"
            f"{json.dumps(feed, ensure_ascii=False, default=str)}\n\n"
            "## Cost dashboard (today)\n"
            f"{json.dumps(cost, ensure_ascii=False, default=str)}\n\n"
            "## Decision\n"
            "If drift is real, call `intervene_feed_drift(reason, "
            "suggested_priority_lift_story_unit_id)` with a short, "
            "place-named reason and a candidate id from the queue. "
            "If no drift, do nothing — silence is a valid answer. "
            "Never name an individual Team USA athlete."
        )

    def _format_user_message_draft(self, draft_id: str, snapshot: dict) -> str:
        """User message for a story-level review."""
        draft = snapshot.get("draft") or {}
        cost = snapshot.get("cost_today") or {}
        return (
            "## Story-level parity review\n"
            f"You have been invoked to review draft `{draft_id}`.\n\n"
            "## Source draft\n"
            f"{json.dumps(draft, ensure_ascii=False, default=str)}\n\n"
            "## Cost dashboard (today)\n"
            f"{json.dumps(cost, ensure_ascii=False, default=str)}\n\n"
            "## Decision\n"
            "Call exactly one of `clear_draft(draft_id)` (Paralympic "
            "depth equals Olympic), `return_draft(draft_id, reason)` "
            "(shallow Paralympic context — revise), or `block_draft("
            "draft_id, reason)` (safety violation — inspiration porn / "
            "ableist phrasing). Never name an individual Team USA "
            "athlete; never use forbidden Storyteller words in the "
            "reason text — describe the failure pattern instead."
        )

    async def _invoke_runner(
        self,
        *,
        user_message: str,
        investigation_id: str,
        kind: str,
    ) -> dict:
        """One ADK Runner invocation. Retries once with truncated context.

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
                    "equity_editor.review_%s: Runner attempt %d/%d failed: %s",
                    kind, i, len(attempts), e,
                )
        raise _RunnerFailedAfterRetryError(str(last_exc))

    async def _run_adk_once(
        self,
        *,
        user_message: str,
        investigation_id: str,
    ) -> dict:
        """One ADK Runner invocation. Returns parsed result dict.

        Returns: `{"tool_calls": [...], "input_tokens": int|None,
        "output_tokens": int|None}`. Tests patch this method directly.
        """
        try:
            from google.adk import Runner  # type: ignore[import-untyped]
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "equity_editor: google.adk not installed; review is a no-op"
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

        session_id = f"equity_editor-{investigation_id}-{uuid.uuid4().hex[:8]}"
        user_content = genai_types.Content(
            parts=[genai_types.Part(text=user_message)],
            role="user",
        )

        tool_calls: list[dict] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async for event in runner.run_async(
                user_id="equity_editor-runtime",
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
                logger.debug("equity_editor: runner.close() raised", exc_info=True)

        return {
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    async def _safe_emit_intervention(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None = None,
    ) -> None:
        """Emit a Wire `intervention` event without raising into the loop.

        Per BUILD_SPEC §6.5, the Equity Editor's events arrive (not stream)
        — message_type is `intervention`, not `thinking`, even for the
        failure-mode "hold — model returned an error" event.
        """
        try:
            event: dict = {
                "agent": "equity_editor",
                "message": message,
                "message_type": "intervention",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "equity_editor: wire proxy not ready; cannot emit intervention event"
            )
        except Exception:
            logger.exception(
                "equity_editor: failed to emit intervention event"
            )


# -- Helpers ------------------------------------------------------------------


class _RunnerFailedAfterRetryError(RuntimeError):
    """Raised by `_invoke_runner` after both Runner attempts fail."""


def _truncate_for_retry(message: str, max_chars: int = 1500) -> str:
    """Shorter context for the second attempt (BUILD_SPEC §17.1)."""
    if len(message) <= max_chars:
        return message
    head = message[: max_chars // 2]
    tail = message[-max_chars // 2 :]
    return f"{head}\n... [context truncated for retry] ...\n{tail}"


def _decision_from_tool_calls(
    tool_calls: list[dict],
) -> tuple[str, str | None]:
    """Read the decision off the Runner's tool-call log.

    Returns `(decision, feedback)`. Decision is the latest decisive call
    in the log — `clear_draft` / `return_draft` / `block_draft`. If the
    model called more than one decisive tool, the latest wins (matches
    the on-disk Firestore state, which is also last-writer-wins).
    """
    decision = "no_decision"
    feedback: str | None = None
    for call in tool_calls:
        name = call.get("name") or ""
        if name == "clear_draft":
            decision = "cleared"
            feedback = None
        elif name == "return_draft":
            decision = "returned"
            args = call.get("args") or {}
            r = args.get("reason")
            if isinstance(r, str):
                feedback = r
        elif name == "block_draft":
            decision = "blocked"
            args = call.get("args") or {}
            r = args.get("reason")
            if isinstance(r, str):
                feedback = r
    return (decision, feedback)


class _PlaceholderEquityEditor:
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
