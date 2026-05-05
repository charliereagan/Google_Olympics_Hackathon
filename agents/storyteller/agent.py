"""StorytellerAgent: Pro-tier literary-restraint specialist.

Mirrors `agents/editor/agent.py`, `agents/investigator/agent.py`, and
`agents/equity_editor/agent.py` end-to-end:
  - Closure-bound tools via `_bind_tools`, including the four runtime
    tools from `agents/storyteller/tools.py::build_storyteller_tools`
    plus a locally-bound `pull_vocabulary` (vocabulary key 'storyteller').
  - ADK `LlmAgent` constructed once in `_build_llm`. Falls back to a
    placeholder shell when ADK isn't on the host (dev-mode unit tests).
  - Single Runner invocation in `_run_adk_once`, with retry +
    truncated-context fallback in `_invoke_runner`.
  - Failure modes (BUILD_SPEC §17.1): cost ceiling, runner exception,
    wire-proxy not ready, draft validation — each emits a `thinking`
    Wire event and either retries (validation, up to max_revisions) or
    skips the cycle (cost ceiling, runner failure).

Voice signature lives in `/prompts/storyteller.md` per CONSTITUTION
Rule 1. Python here contains zero voice text. The Storyteller's voice
is the most rigorous in the cast (CONSTITUTION Law 4 + Law 5) — its
output is the actual narrative the Narrator speaks and the Broadcast
page displays.

The Storyteller has no autonomous loop. It is invoked by the Editor's
`dispatch_storyteller(investigation_packet_id)` tool. Its `write_story`
method drives one full storytelling cycle: read packet → invoke Runner
→ on equity 'returned' re-prompt with feedback → on cleared, request
publish gate → loop counts revisions; max 3.
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
from agents.observability import log_agent_call, trace_span
from agents.storyteller.tools import _DraftValidationError, build_storyteller_tools
from agents.wire.emit import WireProxyNotReadyError

logger = logging.getLogger(__name__)


# Pro-tier per-cycle ceiling check axis (BUILD_SPEC §15.3). Same axis the
# Editor / Investigator / Equity Editor use — the Storyteller is also
# Pro-tier (BUILD_SPEC §3.1).
_COST_AXIS = "gemini_pro"

# How many revisions the Storyteller will attempt before killing the
# draft. BUILD_SPEC §5.7 + the Equity Editor's `return_draft` contract
# both cap revisions at 3.
_DEFAULT_MAX_REVISIONS = 3


class StorytellerAgent:
    """The Storyteller. Pro-tier literary-restraint specialist.

    Construction mirrors EditorAgent / InvestigatorAgent /
    EquityEditorAgent — same kwargs, same tool-binding pattern, same
    fallback to a placeholder shell when ADK isn't on the host.
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
        max_revisions: int = _DEFAULT_MAX_REVISIONS,
    ) -> None:
        self._prompt = prompt
        self._wire = wire
        self._firestore = firestore
        self._bigquery = bigquery
        self._model_id = model_id
        self._cost_counter = cost_counter
        self._wire_vocabulary = wire_vocabulary
        # Backref so `request_equity_review` and `request_publish_gate`
        # can locate the live agent instances. Optional — None falls
        # through to graceful 'unknown' decisions in the tools.
        self._runtime_state = runtime_state
        self._max_revisions = int(max_revisions)
        self._bound_tools = self._bind_tools()
        self._llm = self._build_llm()

    # -- Public surface ------------------------------------------------------

    @property
    def llm(self) -> Any:
        return self._llm

    @property
    def name(self) -> str:
        return getattr(self._llm, "name", "storyteller")

    @property
    def model(self) -> str:
        return self._model_id

    # -- Tool binding --------------------------------------------------------

    def _bind_tools(self) -> list[Any]:
        """Build the Storyteller's tool list with runtime deps closed over.

        Tool surface (four from tools.py + pull_vocabulary):
          - read_investigation_packet(packet_id)
          - write_story_draft(headline, dek, body, why_this_matters,
              hometown_panel, historical_echo, place_name,
              era_reference, investigation_packet_id, story_unit_id?,
              storyteller_notes?)
          - request_equity_review(draft_id)
          - request_publish_gate(draft_id)
          - pull_vocabulary(message_type='thinking'|'milestone', **slots)

        Voice text comes from the prompt, not Python.
        """
        # Use the lazy provider so the equity_editor / publish_gate
        # references resolve at call time, not at agent-build time.
        # The runtime sets `agent._runtime_state = _state` AFTER
        # constructing both the agent and the RuntimeState.
        runtime_tools = build_storyteller_tools(
            wire=self._wire,
            firestore=self._firestore,
            bigquery=self._bigquery,
            runtime_state_provider=lambda: self._runtime_state,
        )

        vocabulary = self._wire_vocabulary
        agent_name = "storyteller"

        async def pull_vocabulary(
            message_type: str = "thinking", **slots: Any
        ) -> str:
            """Pull a curated voice-fragment from the storyteller bucket.

            BUILD_SPEC §6.4 + §6.5. The Storyteller streams its
            thinking — use `'thinking'` for in-progress drafting beats
            ("opening on the place", "draft 1 done, sending to equity")
            and `'milestone'` for clean status changes ("Draft 1
            complete.", "Headline locked."). The fragment may have
            `[snake_case]` slots — pass them as kwargs.

            Args:
                message_type: 'thinking' | 'milestone'.
                **slots: kwargs filled into [snake_case] placeholders
                    (e.g., outlet="Mt Pleasant News", n=12).

            Returns:
                A filled fragment string, or "" when the library is
                empty for this bucket. The model uses the result as the
                message in its next wire_emit call (or just ignores it
                and freelances).
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
                name="storyteller",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )
        except ImportError:
            logger.warning(
                "google.adk not installed; StorytellerAgent built as placeholder shell"
            )
            return _PlaceholderStoryteller(
                name="storyteller",
                model=self._model_id,
                instruction=self._prompt,
                tools=self._bound_tools,
            )

    # -- Public entry point --------------------------------------------------

    async def write_story(
        self,
        investigation_packet_id: str,
        *,
        ctx: Any | None = None,
    ) -> dict:
        """One full storytelling cycle.

        Steps mirror the BUILD_SPEC §5.5 flow plus the failure-mode
        discipline of the Editor / Investigator / Equity Editor:
          1. AGENT_RUNTIME_PAUSED check → skip.
          2. Cost ceiling pre-check → skip with thinking event.
          3. Read the Investigation Packet via the bound tool (so the
             user message has it inline; the model can also re-read
             from its own cycle).
          4. Invoke the ADK Runner with the prompt-driven user message.
             The Pro model will eventually call write_story_draft() →
             request_equity_review() → on cleared, request_publish_gate()
             (or be returned for revision).
          5. On equity 'returned': re-invoke Runner with feedback
             included; loop up to max_revisions=3.
          6. On equity 'blocked' OR revisions_count >= max_revisions:
             stop; mark publish_gate_decision='killed'; emit a
             milestone Wire event with kill_reason.
          7. On publish_gate 'cleared': mark publish_gate_decision=
             'cleared'; emit a milestone Wire event.
          8. log_agent_call + cost_counter.increment after each Runner
             cycle with token counts.

        Args:
            investigation_packet_id: id of the source packet.
            ctx: optional `InvestigationContext` for compression /
                investigation-id stamping.

        Returns:
            `{action: 'cleared'|'returned'|'killed'|'error'|'skipped',
              draft_id: str|None,
              revisions_count: int,
              final_decision: str|None,
              latency_ms: int}`.

        Failure modes per BUILD_SPEC §17.1:
          - Runner exception (after retry-with-truncated-context) → emit
            thinking ("hold — model returned an error, retrying with
            shorter context") → return action='error'.
          - CostCeilingExceeded → emit thinking ("daily Pro cap reached,
            storyteller pausing") → return action='skipped'.
          - WireProxyNotReadyError → log + return action='skipped'.
          - _DraftValidationError raised inside the model's tool call →
            counts as a revision; the model re-prompts with the
            field-specific feedback.
        """
        # --- AGENT_RUNTIME_PAUSED gate --------------------------------------
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug(
                "storyteller.write_story: paused (AGENT_RUNTIME_PAUSED=1); skipping"
            )
            return {
                "action": "skipped",
                "reason": "paused",
                "draft_id": None,
                "revisions_count": 0,
                "final_decision": None,
                "latency_ms": 0,
            }

        investigation_id = (
            getattr(ctx, "investigation_id", None) if ctx is not None else None
        ) or f"storyteller-{investigation_packet_id}"
        compression_factor = (
            float(getattr(ctx, "compression_factor", 1.0)) if ctx is not None else 1.0
        )

        # --- Cost ceiling pre-check ----------------------------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="storyteller"
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*daily Pro cap reached, storyteller pausing*",
                    investigation_id=investigation_id,
                )
                return {
                    "action": "skipped",
                    "reason": "cost_ceiling",
                    "draft_id": None,
                    "revisions_count": 0,
                    "final_decision": None,
                    "latency_ms": 0,
                }

        # --- Read the investigation packet (snapshot for user message) ----
        packet = await self._read_investigation_packet(investigation_packet_id)
        if not packet or packet.get("error") == "not_found":
            await self._safe_emit_thinking(
                "*hold — investigation packet missing; storyteller cannot draft*",
                investigation_id=investigation_id,
            )
            return {
                "action": "error",
                "reason": "investigation_packet_not_found",
                "draft_id": None,
                "revisions_count": 0,
                "final_decision": None,
                "latency_ms": 0,
                "investigation_packet_id": investigation_packet_id,
            }

        # --- Revision loop -------------------------------------------------
        last_draft_id: str | None = None
        last_decision: str | None = None
        last_feedback: str | None = None
        revisions_count = 0
        total_latency_ms = 0
        action = "error"

        # The loop body is one Runner cycle. The model is expected to
        # call write_story_draft() then request_equity_review(); the
        # equity decision drives the loop. max_revisions counts the
        # number of *return* decisions accepted before the kill.
        for attempt in range(self._max_revisions + 1):
            user_message = (
                self._format_user_message(packet)
                if attempt == 0
                else self._build_revision_user_message(
                    packet=packet,
                    previous_draft_id=last_draft_id,
                    equity_feedback=last_feedback or "",
                    revisions_count=revisions_count,
                )
            )

            with trace_span(
                "storyteller.write_story",
                investigation_id=investigation_id,
                attrs={
                    "compression_factor": compression_factor,
                    "investigation_packet_id": investigation_packet_id,
                    "attempt": attempt,
                },
            ):
                t0 = time.monotonic()
                try:
                    result = await self._invoke_runner(
                        user_message=user_message,
                        investigation_id=investigation_id,
                    )
                except _RunnerFailedAfterRetryError as e:
                    await self._safe_emit_thinking(
                        "*hold — model returned an error, retrying with shorter context*",
                        investigation_id=investigation_id,
                    )
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    total_latency_ms += latency_ms
                    log_agent_call(
                        agent="storyteller",
                        sub_agent=None,
                        story_unit_id=packet.get("story_unit_id"),
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
                        "draft_id": last_draft_id,
                        "revisions_count": revisions_count,
                        "final_decision": last_decision,
                        "latency_ms": total_latency_ms,
                        "investigation_packet_id": investigation_packet_id,
                    }
                except WireProxyNotReadyError:
                    logger.warning(
                        "storyteller.write_story: WireProxyNotReady; skipping cycle"
                    )
                    return {
                        "action": "skipped",
                        "reason": "wire_not_ready",
                        "draft_id": last_draft_id,
                        "revisions_count": revisions_count,
                        "final_decision": last_decision,
                        "latency_ms": total_latency_ms,
                        "investigation_packet_id": investigation_packet_id,
                    }

                latency_ms = int((time.monotonic() - t0) * 1000)
                total_latency_ms += latency_ms

            # --- Cost increment after each cycle --------------------------
            if self._cost_counter is not None:
                try:
                    await self._cost_counter.increment(
                        agent="storyteller",
                        sub_agent=None,
                        axis=_COST_AXIS,
                        model=self._model_id,
                        calls=1,
                        input_tokens=int(result.get("input_tokens") or 0),
                        output_tokens=int(result.get("output_tokens") or 0),
                    )
                except Exception:
                    logger.exception(
                        "storyteller.write_story: cost_counter.increment failed"
                    )

            log_agent_call(
                agent="storyteller",
                sub_agent=None,
                story_unit_id=packet.get("story_unit_id"),
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

            # --- Read decisions off the tool-call log --------------------
            tool_calls = result.get("tool_calls") or []
            new_draft_id = _last_draft_id_from_tool_calls(tool_calls)
            if new_draft_id is not None:
                last_draft_id = new_draft_id
            equity_decision, equity_feedback = _equity_decision_from_tool_calls(
                tool_calls
            )
            publish_decision = _publish_decision_from_tool_calls(tool_calls)

            # No draft was written this cycle — the model may have
            # short-circuited. Treat as error so the operator sees it.
            if last_draft_id is None and equity_decision is None:
                await self._safe_emit_thinking(
                    "*hold — model did not produce a draft; storyteller stopping*",
                    investigation_id=investigation_id,
                )
                return {
                    "action": "error",
                    "reason": "no_draft_written",
                    "draft_id": None,
                    "revisions_count": revisions_count,
                    "final_decision": None,
                    "latency_ms": total_latency_ms,
                    "investigation_packet_id": investigation_packet_id,
                }

            # --- Equity decision branching --------------------------------
            last_decision = equity_decision or last_decision
            last_feedback = equity_feedback if equity_feedback else last_feedback

            if equity_decision == "blocked":
                # Permanent kill — Equity Editor blocked for safety.
                await self._mark_publish_gate_decision(
                    last_draft_id, "killed"
                )
                await self._safe_emit_milestone(
                    "Draft killed at equity review.",
                    investigation_id=investigation_id,
                    story_unit_id=packet.get("story_unit_id"),
                )
                self._stamp_last_think_cycle()
                return {
                    "action": "killed",
                    "reason": "equity_blocked",
                    "draft_id": last_draft_id,
                    "revisions_count": revisions_count,
                    "final_decision": "blocked",
                    "latency_ms": total_latency_ms,
                    "investigation_packet_id": investigation_packet_id,
                }

            if equity_decision == "returned":
                revisions_count += 1
                if revisions_count > self._max_revisions:
                    # Max revisions hit — kill the draft.
                    await self._mark_publish_gate_decision(
                        last_draft_id, "killed"
                    )
                    await self._safe_emit_milestone(
                        f"Draft killed: {self._max_revisions} revisions exhausted.",
                        investigation_id=investigation_id,
                        story_unit_id=packet.get("story_unit_id"),
                    )
                    self._stamp_last_think_cycle()
                    return {
                        "action": "killed",
                        "reason": "max_revisions_reached",
                        "draft_id": last_draft_id,
                        "revisions_count": revisions_count,
                        "final_decision": "returned",
                        "latency_ms": total_latency_ms,
                        "investigation_packet_id": investigation_packet_id,
                    }
                # Loop and re-prompt with feedback.
                continue

            if equity_decision == "cleared":
                # If the model also called request_publish_gate this
                # cycle, surface its decision; otherwise treat the cycle
                # as 'cleared' (the Editor's dispatch_publish_gate tool
                # can pick it up).
                if publish_decision == "cleared":
                    await self._mark_publish_gate_decision(
                        last_draft_id, "cleared"
                    )
                    await self._safe_emit_milestone(
                        "Draft cleared. Sent to publish gate.",
                        investigation_id=investigation_id,
                        story_unit_id=packet.get("story_unit_id"),
                    )
                    self._stamp_last_think_cycle()
                    return {
                        "action": "cleared",
                        "draft_id": last_draft_id,
                        "revisions_count": revisions_count,
                        "final_decision": "cleared",
                        "latency_ms": total_latency_ms,
                        "investigation_packet_id": investigation_packet_id,
                    }
                if publish_decision in {"returned", "killed"}:
                    final_action = (
                        "killed" if publish_decision == "killed" else "returned"
                    )
                    if publish_decision == "killed":
                        await self._mark_publish_gate_decision(
                            last_draft_id, "killed"
                        )
                    self._stamp_last_think_cycle()
                    return {
                        "action": final_action,
                        "draft_id": last_draft_id,
                        "revisions_count": revisions_count,
                        "final_decision": publish_decision,
                        "latency_ms": total_latency_ms,
                        "investigation_packet_id": investigation_packet_id,
                    }
                # Cleared but no publish-gate call this cycle. Surface
                # 'cleared' to the caller — the Editor can dispatch the
                # Publish Gate explicitly via its `dispatch_publish_gate`
                # tool (the parallel Day-6 worker is wiring that).
                await self._safe_emit_milestone(
                    "Draft cleared at equity review.",
                    investigation_id=investigation_id,
                    story_unit_id=packet.get("story_unit_id"),
                )
                self._stamp_last_think_cycle()
                return {
                    "action": "cleared",
                    "draft_id": last_draft_id,
                    "revisions_count": revisions_count,
                    "final_decision": "cleared",
                    "latency_ms": total_latency_ms,
                    "investigation_packet_id": investigation_packet_id,
                }

            # No equity decision yet — the model may have written the
            # draft but not requested review. Treat the cycle as
            # 'pending' and ask for one more revision attempt with a
            # nudge.
            revisions_count += 1
            if revisions_count > self._max_revisions:
                await self._mark_publish_gate_decision(
                    last_draft_id, "killed"
                )
                await self._safe_emit_milestone(
                    "Draft killed: equity review never invoked.",
                    investigation_id=investigation_id,
                    story_unit_id=packet.get("story_unit_id"),
                )
                self._stamp_last_think_cycle()
                return {
                    "action": "killed",
                    "reason": "no_equity_decision",
                    "draft_id": last_draft_id,
                    "revisions_count": revisions_count,
                    "final_decision": None,
                    "latency_ms": total_latency_ms,
                    "investigation_packet_id": investigation_packet_id,
                }
            # Else loop again with a generic nudge.
            last_feedback = (
                "Draft was written but equity review was not requested. "
                "Call request_equity_review(draft_id) after writing the draft."
            )

        # Loop exhausted without returning — defensive only.
        self._stamp_last_think_cycle()
        return {
            "action": "killed",
            "reason": "loop_exhausted",
            "draft_id": last_draft_id,
            "revisions_count": revisions_count,
            "final_decision": last_decision,
            "latency_ms": total_latency_ms,
            "investigation_packet_id": investigation_packet_id,
        }

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """No autonomous loop — Storyteller invoked by the Editor.

        We honor `stop_event` so the lifespan teardown stays consistent
        with the other agents — but we never spin a cycle ourselves.
        """
        if stop_event is not None:
            try:
                await stop_event.wait()
            except Exception:
                logger.debug("storyteller.autonomous_loop: stop_event.wait raised")

    # -- Internals -----------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        """Update RuntimeState.last_think_cycle (best-effort)."""
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception(
                "storyteller: failed to stamp last_think_cycle"
            )

    async def _read_investigation_packet(self, packet_id: str) -> dict:
        """Read the packet via the bound tool (closure-based path)."""
        for tool in self._bound_tools:
            if getattr(tool, "__name__", "") == "read_investigation_packet":
                try:
                    return await tool(packet_id)
                except Exception:
                    logger.exception(
                        "storyteller._read_investigation_packet: tool raised"
                    )
                    return {"error": "not_found", "packet_id": packet_id}
        return {"error": "not_found", "packet_id": packet_id}

    def _build_context_snapshot(self, packet: dict) -> dict:
        """Project the Investigation Packet to the fields the model needs.

        Truncates `sources` to the first N (BUILD_SPEC §5.5: the
        Storyteller works from the packet only; the body of each
        source URL is irrelevant to the prompt). Keeps the payload
        compact (~1-2 KB) so the Pro model's context budget is spent
        on writing, not parsing.
        """
        sources = packet.get("sources") or []
        return {
            "story_unit_id": packet.get("story_unit_id"),
            "story_unit_title": packet.get("story_unit_title"),
            "story_unit_type": packet.get("story_unit_type"),
            "narrative_spine": packet.get("narrative_spine"),
            "geography": packet.get("geography") or {},
            "historical_context": packet.get("historical_context") or {},
            "trend_signals": packet.get("trend_signals") or {},
            "sources": [
                {
                    "url": s.get("url"),
                    "outlet": s.get("outlet"),
                    "relevance_note": s.get("relevance_note"),
                }
                for s in sources[:8]
                if isinstance(s, dict)
            ],
            "paralympic_depth_score": packet.get("paralympic_depth_score"),
        }

    def _format_user_message(self, packet: dict) -> str:
        """Initial user message for the Storyteller's Runner cycle.

        The Pro model's instruction (the system prompt) drives WHAT and
        HOW; this message hands it the source-of-truth and the
        contractual closing instructions.
        """
        snapshot = self._build_context_snapshot(packet)
        packet_id = packet.get("id", "unknown")
        return (
            "## Investigation Packet\n"
            f"{json.dumps(snapshot, ensure_ascii=False, default=str)}\n\n"
            "## Your task\n"
            "Write a 400-700 word place narrative (per the structural "
            "envelope in your instructions). Call write_story_draft() "
            "exactly once when ready, with the investigation_packet_id "
            f"set to `{packet_id}`. After the draft is persisted, call "
            "request_equity_review(draft_id) with the id you got back. "
            "If the Equity Editor returns the draft, call "
            "write_story_draft() again with the revised content (the "
            "Storyteller is allowed up to 3 revisions). After the Equity "
            "Editor clears the draft, you may call request_publish_gate("
            "draft_id) — the Publish Gate runs the seven-sub-stage audit "
            "and returns the final decision."
        )

    def _build_revision_user_message(
        self,
        *,
        packet: dict,
        previous_draft_id: str | None,
        equity_feedback: str,
        revisions_count: int,
    ) -> str:
        """User message for revision attempts.

        Includes the original packet snapshot, the prior draft id (if
        we have one), the equity-editor feedback, and an explicit
        revision-budget marker so the model knows how many attempts
        remain.
        """
        snapshot = self._build_context_snapshot(packet)
        remaining = max(0, self._max_revisions - revisions_count + 1)
        return (
            "## Investigation Packet\n"
            f"{json.dumps(snapshot, ensure_ascii=False, default=str)}\n\n"
            "## Equity Editor feedback (revise the draft)\n"
            f"{equity_feedback}\n\n"
            "## Revision context\n"
            f"Previous draft id: `{previous_draft_id or 'unknown'}`. "
            f"This is revision #{revisions_count}. "
            f"You have {remaining} attempt(s) remaining "
            "before the draft is killed for max-revisions.\n\n"
            "## Your task\n"
            "Call write_story_draft() with the revised content "
            "(addressing the feedback above), then call "
            "request_equity_review(draft_id) with the new draft id."
        )

    async def _invoke_runner(
        self,
        *,
        user_message: str,
        investigation_id: str,
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
                    "storyteller.write_story: Runner attempt %d/%d failed: %s",
                    i, len(attempts), e,
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
                "storyteller: google.adk not installed; write_story is a no-op"
            )
            return {"tool_calls": [], "input_tokens": 0, "output_tokens": 0}

        session_service = InMemorySessionService()
        # ADK validates app_name as a Python identifier (letters/digits/
        # underscores). We use `storytellers_room` to match the rest of
        # the cast.
        runner = Runner(
            app_name="storytellers_room",
            agent=self._llm,
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = f"storyteller-{investigation_id}-{uuid.uuid4().hex[:8]}"
        user_content = genai_types.Content(
            parts=[genai_types.Part(text=user_message)],
            role="user",
        )

        tool_calls: list[dict] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async for event in runner.run_async(
                user_id="storyteller-runtime",
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
                            "response": _extract_tool_response(event, fc),
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
                logger.debug("storyteller: runner.close() raised", exc_info=True)

        return {
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    async def _mark_publish_gate_decision(
        self,
        draft_id: str | None,
        decision: str,
    ) -> None:
        """Best-effort `publish_gate_decision` mutation on the draft.

        Used to mark a draft as 'killed' (max revisions / equity blocked)
        or 'cleared' (publish gate cleared) — the storyteller writes
        directly here because the Equity Editor / Publish Gate may not
        own the lifecycle terminal state. Failures are logged but never
        raised — the operational signal already shipped via Wire.
        """
        if not draft_id:
            return
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        try:
            coll = self._firestore.collection("story_drafts")
        except Exception:
            return

        # Try doc-id lookup first (fastest), then update / set.
        doc_ref = None
        current: dict | None = None
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(draft_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        current = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
        except Exception:
            logger.debug(
                "storyteller._mark_publish_gate_decision: doc-id lookup failed; falling back to scan",
                exc_info=True,
            )

        if current is None:
            try:
                stream = coll.stream() if hasattr(coll, "stream") else []
                if hasattr(stream, "__aiter__"):
                    async for d in stream:
                        data = _doc_to_dict(d)
                        if data.get("id") == draft_id:
                            current = data
                            break
                else:
                    for d in stream:
                        data = _doc_to_dict(d)
                        if data.get("id") == draft_id:
                            current = data
                            break
            except Exception:
                logger.exception(
                    "storyteller._mark_publish_gate_decision: scan failed"
                )
                return

        if current is None:
            logger.warning(
                "storyteller._mark_publish_gate_decision: draft %s not found",
                draft_id,
            )
            return

        updated = dict(current)
        updated["publish_gate_decision"] = decision
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Try doc_ref.update, then doc_ref.set, then coll.add as a
        # last resort (the unit-test stub records writes via add()).
        if doc_ref is not None and hasattr(doc_ref, "update"):
            try:
                res = doc_ref.update(
                    {
                        "publish_gate_decision": decision,
                        "updated_at": updated["updated_at"],
                    }
                )
                if hasattr(res, "__await__"):
                    await res
                return
            except Exception:
                logger.debug(
                    "storyteller._mark_publish_gate_decision: doc_ref.update failed; trying set",
                    exc_info=True,
                )
        if doc_ref is not None and hasattr(doc_ref, "set"):
            try:
                res = doc_ref.set(updated)
                if hasattr(res, "__await__"):
                    await res
                return
            except Exception:
                logger.debug(
                    "storyteller._mark_publish_gate_decision: doc_ref.set failed; falling back to add",
                    exc_info=True,
                )
        if hasattr(coll, "add"):
            try:
                res = coll.add(updated)
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                logger.exception(
                    "storyteller._mark_publish_gate_decision: coll.add fallback failed"
                )

    async def _safe_emit_thinking(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None = None,
    ) -> None:
        """Emit a Wire `thinking` event without raising into the loop.

        BUILD_SPEC §6.5: the Storyteller streams its thinking, so
        thinking-style failure events are correct here (vs. the Equity
        Editor's arrival-style 'intervention' events).
        """
        try:
            event: dict = {
                "agent": "storyteller",
                "message": message,
                "message_type": "thinking",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "storyteller: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "storyteller: failed to emit thinking event"
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
                "agent": "storyteller",
                "message": message,
                "message_type": "milestone",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "storyteller: wire proxy not ready; cannot emit milestone event"
            )
        except Exception:
            logger.exception(
                "storyteller: failed to emit milestone event"
            )


# -- Helpers ------------------------------------------------------------------


class _RunnerFailedAfterRetryError(RuntimeError):
    """Raised by `_invoke_runner` after both Runner attempts fail."""


def _truncate_for_retry(message: str, max_chars: int = 4500) -> str:
    """Shorter context for the second attempt (BUILD_SPEC §17.1).

    Storyteller user-message budget is larger than the Editor's because
    the Investigation Packet snapshot is the prompt's main content. We
    keep ~4500 chars (vs. Editor's 1500) so the model still has the
    narrative spine + geography + historical context after truncation.
    """
    if len(message) <= max_chars:
        return message
    head = message[: max_chars // 2]
    tail = message[-max_chars // 2:]
    return f"{head}\n... [context truncated for retry] ...\n{tail}"


def _last_draft_id_from_tool_calls(
    tool_calls: list[dict],
) -> str | None:
    """Find the most-recent write_story_draft call's returned draft id.

    The ADK Runner stores tool responses on the function-response event;
    `_run_adk_once` projects them to `tool_call['response']`. Falls back
    to args (`investigation_packet_id`) only as a debugging hint — the
    real id comes from the tool's return.
    """
    last_id: str | None = None
    for call in tool_calls:
        if call.get("name") != "write_story_draft":
            continue
        resp = call.get("response") or {}
        if isinstance(resp, dict):
            cand = resp.get("draft_id") or resp.get("id")
            if isinstance(cand, str) and cand:
                last_id = cand
    return last_id


def _equity_decision_from_tool_calls(
    tool_calls: list[dict],
) -> tuple[str | None, str | None]:
    """Find the most-recent request_equity_review call's decision.

    Returns `(decision, feedback)`. Decision is one of `'cleared' |
    'returned' | 'blocked' | 'no_decision' | None`; None when no
    request_equity_review call appeared. Feedback is set when the
    decision is `'returned'` (the Equity Editor's `return_draft` tool
    surfaces a `feedback` field).
    """
    decision: str | None = None
    feedback: str | None = None
    for call in tool_calls:
        if call.get("name") != "request_equity_review":
            continue
        resp = call.get("response") or {}
        if isinstance(resp, dict):
            d = resp.get("decision")
            if isinstance(d, str):
                decision = d
            f = resp.get("feedback")
            if isinstance(f, str):
                feedback = f
    return (decision, feedback)


def _publish_decision_from_tool_calls(
    tool_calls: list[dict],
) -> str | None:
    """Find the most-recent request_publish_gate call's decision.

    Returns one of `'cleared' | 'returned' | 'killed' | None`.
    """
    decision: str | None = None
    for call in tool_calls:
        if call.get("name") != "request_publish_gate":
            continue
        resp = call.get("response") or {}
        if isinstance(resp, dict):
            d = resp.get("decision")
            if isinstance(d, str):
                decision = d
    return decision


def _extract_tool_response(event: Any, fc: Any) -> dict | None:
    """Extract the function-response payload for `fc` from an ADK event.

    ADK event types vary; we try a few attribute paths and fall back to
    None. The runner often surfaces tool returns as
    `event.get_function_responses()` or as parts on a separate event;
    we check both shapes defensively.
    """
    try:
        if hasattr(event, "get_function_responses"):
            for fr in event.get_function_responses() or []:
                if getattr(fr, "name", None) == getattr(fc, "name", None):
                    response = getattr(fr, "response", None)
                    if isinstance(response, dict):
                        return response
    except Exception:
        pass
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


class _PlaceholderStoryteller:
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
