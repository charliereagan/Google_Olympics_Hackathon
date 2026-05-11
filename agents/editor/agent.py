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
from agents.handoffs import safe_emit_handoff
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
        wire_vocabulary: Any | None = None,
        investigator: Any | None = None,
        equity_editor: Any | None = None,
        storyteller: Any | None = None,
        narrator: Any | None = None,
        publish_gate: Any | None = None,
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
        # WireVocabulary library (BUILD_SPEC §6.4). Optional — None means the
        # `pull_vocabulary` tool returns "" and the agent falls back to free-
        # text generation (texture is non-gating).
        self._wire_vocabulary = wire_vocabulary
        # InvestigatorAgent — bound by the runtime so the Editor's
        # `dispatch_investigator` tool can drive the depth-of-research stage.
        # Optional — None means the tool returns an error dict (the Editor
        # still boots; the chain just stops at Lead Reports).
        self._investigator = investigator
        # EquityEditorAgent — bound by the runtime so the Editor's
        # `request_equity_review` tool can invoke parity review at the feed
        # or draft level. Optional — None means the tool returns an error
        # dict (parallel-worker race tolerance during Day-6 rollout).
        self._equity_editor = equity_editor
        # StorytellerAgent — bound by the runtime so the Editor's
        # `dispatch_storyteller` tool can drive draft creation from a
        # cleared Investigation Packet. Optional — None means the tool
        # returns an error dict (parallel-worker race tolerance during
        # Day-6 rollout).
        self._storyteller = storyteller
        # NarratorAgent — bound by the runtime so the Editor's
        # `dispatch_narrator` tool can render a cleared draft to a
        # NarrationManifest. Optional.
        self._narrator = narrator
        # PublishGateAgent — bound by the runtime so the Editor's
        # `dispatch_publish_gate` tool can run the seven-sub-stage audit
        # on a Storyteller draft. Optional — None means the tool returns
        # an error dict (parallel-worker race tolerance during Day-6 rollout).
        self._publish_gate = publish_gate
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
        investigator = self._investigator
        equity_editor = self._equity_editor
        storyteller = self._storyteller
        narrator = self._narrator
        publish_gate = self._publish_gate
        firestore = self._firestore
        vocabulary = self._wire_vocabulary
        agent_name = "editor"

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
            await safe_emit_handoff(
                firestore,
                from_agent="editor",
                to_agent="scout_desk",
                tool_call_id="dispatch_scout",
                story_unit_id=story_unit_id,
            )
            return await scout_desk.dispatch_one(scout_id, story_unit_id)

        async def dispatch_storyteller(investigation_packet_id: str) -> dict:
            """Dispatch the Storyteller to write a draft from an
            Investigation Packet (BUILD_SPEC §5.5).

            The Storyteller reads the packet, composes a 400-700 word
            narrative against the structural envelope, and routes its
            draft through the Equity Editor and (optionally) the
            Publish Gate as part of its own cycle. The dispatch
            surfaces the final outcome so the Editor can react.

            Args:
                investigation_packet_id: id of the Investigation Packet
                    (the `dispatch_investigator` tool's return dict
                    surfaces this).

            Returns:
                `{dispatched, action, draft_id?, revisions_count,
                 final_decision?, latency_ms, ...}`. On failure (no
                storyteller, packet missing, cost ceiling, model
                error) `dispatched=false` and the `error`/`reason`
                field describes why.
            """
            if storyteller is None:
                logger.warning(
                    "editor.dispatch_storyteller: storyteller not initialized"
                )
                return {
                    "dispatched": False,
                    "investigation_packet_id": investigation_packet_id,
                    "error": "storyteller not initialized",
                }
            logger.info(
                "editor.dispatch_storyteller: investigation_packet_id=%s",
                investigation_packet_id,
            )
            await safe_emit_handoff(
                firestore,
                from_agent="editor",
                to_agent="storyteller",
                tool_call_id="dispatch_storyteller",
            )
            result = await storyteller.write_story(investigation_packet_id)
            return {"dispatched": True, **result}

        async def dispatch_narrator(
            story_draft_id: str,
            voice_profile: str = "broadcast",
            audit_id: str | None = None,
        ) -> dict:
            """Dispatch the Narrator to render a cleared story draft to
            a NarrationManifest (BUILD_SPEC §5.6 + §7.6).

            Reads `/story_drafts/{story_draft_id}` from Firestore.
            Refuses to dispatch unless `publish_gate_decision='cleared'`
            — Narrator output goes straight to the Broadcast page, so a
            non-cleared draft must not be narrated.

            Concurrency: when `audit_id` is provided the tool first
            attempts an atomic claim on the audit's
            `narration_dispatched` flag (Day-6 dedup fix). If the audit
            was already claimed by a concurrent think cycle the tool
            returns `{status: 'already_dispatched'}` WITHOUT invoking
            the Narrator — preventing the duplicate-published_stories
            race observed when two cycles overlap on a long TTS call.

            Args:
                story_draft_id: id of the cleared draft (the
                    `dispatch_storyteller` tool's return dict surfaces
                    this as `draft_id`).
                voice_profile: 'broadcast' / 'algenib' (default — the
                    warm, paced Algenib voice per HOE-DEC-025) or
                    'dispatcher' / 'fenrir' (the clipped Fenrir voice).
                audit_id: optional id of the cleared `publish_audits`
                    doc that authorized this narration. When provided,
                    the Narrator carries the audit's NIL signature
                    (claims_checked / softened / removed) into the
                    `published_stories` doc, and the Editor atomically
                    claims the audit (sets `narration_dispatched=True`
                    BEFORE invoking the Narrator) so the next think
                    cycle does not re-dispatch the same cleared audit.

            Returns:
                `{dispatched, manifest?, error?}` on success / soft
                failure paths. When `audit_id` is provided and another
                think cycle already claimed the audit, returns
                `{status: 'already_dispatched', audit_id}` and does not
                invoke the Narrator.
            """
            if narrator is None:
                logger.warning(
                    "editor.dispatch_narrator: narrator not initialized"
                )
                return {
                    "dispatched": False,
                    "story_draft_id": story_draft_id,
                    "error": "narrator not initialized",
                }
            if firestore is None or not hasattr(firestore, "collection"):
                return {
                    "dispatched": False,
                    "story_draft_id": story_draft_id,
                    "error": "firestore unavailable",
                }
            # Atomically claim the audit BEFORE doing any other work. If
            # a concurrent dispatch already won, abort cleanly so we
            # never invoke narrator.narrate() twice (which would write
            # two `published_stories` docs for the same draft).
            if audit_id:
                claimed = await self._claim_audit_for_narration(audit_id)
                if not claimed:
                    logger.info(
                        "editor.dispatch_narrator: audit %s already claimed; skipping",
                        audit_id,
                    )
                    return {
                        "status": "already_dispatched",
                        "dispatched": False,
                        "story_draft_id": story_draft_id,
                        "audit_id": audit_id,
                    }
            logger.info(
                "editor.dispatch_narrator: story_draft_id=%s voice=%s",
                story_draft_id, voice_profile,
            )
            draft = await self._read_story_draft(story_draft_id)
            if draft is None:
                return {
                    "dispatched": False,
                    "story_draft_id": story_draft_id,
                    "error": "draft not found",
                }
            if draft.get("publish_gate_decision") != "cleared":
                return {
                    "dispatched": False,
                    "story_draft_id": story_draft_id,
                    "error": (
                        f"draft not cleared (state="
                        f"{draft.get('publish_gate_decision')})"
                    ),
                }
            narration_input = {
                "story_id": story_draft_id,
                "headline": draft.get("headline", ""),
                "dek": draft.get("dek", ""),
                "body": draft.get("body", ""),
                "hometown_panel_text": draft.get("hometown_panel", ""),
                "historical_echo_text": draft.get("historical_echo", ""),
                "place_name_for_cues": draft.get("place_name", ""),
                "era_reference_for_cues": draft.get("era_reference", ""),
            }
            # Per BUILD_SPEC §9.6 the agent-graph particle stream renders
            # `storyteller -> narrator` here even though the Editor is the
            # tool-call dispatcher (the story is moving from Storyteller's
            # cleared draft to the Narrator's TTS rendering).
            await safe_emit_handoff(
                firestore,
                from_agent="storyteller",
                to_agent="narrator",
                tool_call_id="dispatch_narrator",
                story_unit_id=draft.get("story_unit_id"),
            )
            # Translate prompt-level voice aliases ('algenib' / 'fenrir' per
            # HOE-DEC-025) to the Narrator's API ('broadcast' / 'dispatcher').
            resolved_voice = _resolve_voice_alias(voice_profile)
            manifest = await narrator.narrate(
                narration_input,
                voice_profile=resolved_voice,
                audit_id=audit_id,
            )
            # The audit's `narration_dispatched=True` flag was already
            # written at claim time, so we do NOT call
            # `_mark_audit_narration_dispatched` here — that path is
            # now only invoked as a defensive idempotent fallback if
            # ever needed by a future code path.
            return {
                "dispatched": True,
                "story_draft_id": story_draft_id,
                "audit_id": audit_id,
                "manifest": manifest,
            }

        async def accept_equity_recommendation(intervention_id: str) -> dict:
            """Apply a Paralympic Equity Editor feed-drift intervention.

            Reads `/equity_interventions/{intervention_id}`, applies its
            `suggested_priority_lift_story_unit_id` (writes the editor's
            response back to the doc — `editor_response='accepted'`), and
            emits a Wire `decision` event so the user sees the
            Editor → Equity Editor handoff.

            Args:
                intervention_id: id returned by the Equity Editor's
                    `intervene_feed_drift` tool.

            Returns:
                `{accepted, intervention_id, suggested_priority_lift_story_unit_id?,
                  reason?, persisted}` on success. On any failure
                (firestore unavailable, doc missing, write failed),
                returns `{accepted: False, ...}` with an `error` field.
            """
            logger.info(
                "editor.accept_equity_recommendation: id=%s", intervention_id
            )
            return await self._apply_equity_recommendation(intervention_id)

        async def request_equity_review(
            scope: str = "feed",
            draft_id: str | None = None,
        ) -> dict:
            """Dispatch a parity review to the Paralympic Equity Editor.

            Args:
                scope: 'feed' (the default — audit the published feed for
                    Olympic / Paralympic balance) or 'draft' (review a
                    specific Storyteller draft).
                draft_id: required when scope='draft'.

            Returns:
                The Equity Editor's review result. For scope='feed': the
                cycle outcome dict (action, tool_calls, latency_ms). For
                scope='draft': the same shape plus `decision`
                ('cleared' | 'returned' | 'blocked' | 'no_decision').

                If the Equity Editor isn't initialized (parallel-worker
                race during Day-6 rollout) or the scope is invalid,
                returns an error dict.
            """
            if equity_editor is None:
                logger.warning(
                    "editor.request_equity_review: equity_editor not initialized"
                )
                return {
                    "dispatched": False,
                    "scope": scope,
                    "error": "equity_editor not initialized",
                }
            if scope == "feed":
                logger.info("editor.request_equity_review: scope=feed")
                await safe_emit_handoff(
                    firestore,
                    from_agent="editor",
                    to_agent="equity_editor",
                    tool_call_id="request_equity_review",
                )
                return await equity_editor.review_feed()
            if scope == "draft":
                if not draft_id:
                    return {
                        "dispatched": False,
                        "scope": scope,
                        "error": "draft_id is required when scope='draft'",
                    }
                logger.info(
                    "editor.request_equity_review: scope=draft draft_id=%s",
                    draft_id,
                )
                await safe_emit_handoff(
                    firestore,
                    from_agent="editor",
                    to_agent="equity_editor",
                    tool_call_id="request_equity_review",
                )
                return await equity_editor.review_draft(draft_id)
            return {
                "dispatched": False,
                "scope": scope,
                "error": f"unknown scope: {scope!r}; expected 'feed' or 'draft'",
            }

        async def dispatch_investigator(lead_report_id: str) -> dict:
            """Dispatch the Investigator to deepen a Lead Report into an
            Investigation Packet (BUILD_SPEC §5.3 + §8.4).

            The Investigator reads the Lead Report from Firestore, pulls
            public sources via grounded search, cross-references parallel
            ERAS via BigQuery (aggregate counts only — never names),
            optionally kicks off Deep Research (90s timeout), and writes
            an Investigation Packet to `/investigation_packets/`.

            Args:
                lead_report_id: id of the Lead Report (the
                    `dispatch_scout` tool's return dict surfaces this as
                    `lead_report_id`).

            Returns:
                `{dispatched, lead_report_id, story_unit_id?,
                 investigation_packet_id?, latency_ms?, ...}`. On
                failure (no investigator, lead report missing, cost
                ceiling, model error) `dispatched=false` and the
                `error`/`reason` field describes why.
            """
            if investigator is None:
                logger.warning(
                    "editor.dispatch_investigator: investigator not initialized"
                )
                return {
                    "dispatched": False,
                    "lead_report_id": lead_report_id,
                    "error": "investigator not initialized",
                }
            logger.info(
                "editor.dispatch_investigator: lead_report_id=%s", lead_report_id
            )
            await safe_emit_handoff(
                firestore,
                from_agent="editor",
                to_agent="investigator",
                tool_call_id="dispatch_investigator",
            )
            result = await investigator.investigate(lead_report_id)
            # The investigator's investigate(...) returns either an
            # `action='ok'` dict (success) or an `action='error'/'skipped'`
            # dict (failure modes). Map both to the Editor tool's contract.
            action = result.get("action")
            if action == "ok":
                return {
                    "dispatched": True,
                    "lead_report_id": lead_report_id,
                    "story_unit_id": result.get("story_unit_id"),
                    "investigation_packet_id": result.get("investigation_packet_id"),
                    "latency_ms": result.get("latency_ms"),
                    "tool_calls": result.get("tool_calls", []),
                }
            return {
                "dispatched": False,
                "lead_report_id": lead_report_id,
                "reason": result.get("reason") or action,
                **{k: v for k, v in result.items() if k not in ("action",)},
            }

        async def dispatch_publish_gate(story_draft_id: str) -> dict:
            """Dispatch the Publish Gate to run all 7 sub-stages on a
            Storyteller draft (BUILD_SPEC §5.7).

            The Publish Gate reads the draft from Firestore plus its
            Investigation Packet, runs Fact Check / Source Review /
            Parity Review / NIL Redaction / Safety Review / Language
            Review / Visual Review in order, and writes a PublishAudit
            doc to `/publish_audits/{auto_id}`.

            Final decisions:
              - 'cleared'  — every sub-stage passed; story may publish.
              - 'returned' — at least one sub-stage failed; draft sent
                back to the Storyteller for revision.
              - 'killed'   — sub-stage failed AND revision budget hit;
                draft permanently rejected.

            Args:
                story_draft_id: id of the Storyteller draft (the
                    `dispatch_storyteller` tool's return dict surfaces
                    this as `draft_id`).

            Returns:
                `{dispatched, audit?: PublishAudit, error?}`. On
                failure (no publish_gate, internal exception) returns
                `dispatched=False` with an error.
            """
            if publish_gate is None:
                logger.warning(
                    "editor.dispatch_publish_gate: publish_gate not initialized"
                )
                return {
                    "dispatched": False,
                    "story_draft_id": story_draft_id,
                    "error": "publish_gate not initialized",
                }
            logger.info(
                "editor.dispatch_publish_gate: story_draft_id=%s", story_draft_id
            )
            # Per BUILD_SPEC §9.6 the particle stream renders
            # `storyteller -> publish_gate` here — the draft is moving
            # from Storyteller to the Publish Gate's seven-substage audit.
            await safe_emit_handoff(
                firestore,
                from_agent="storyteller",
                to_agent="publish_gate",
                tool_call_id="dispatch_publish_gate",
            )
            audit = await publish_gate.review(story_draft_id=story_draft_id)
            return {"dispatched": True, "audit": audit}

        async def pull_vocabulary(message_type: str = "thinking", **slots: Any) -> str:
            """Pull a curated voice-fragment from the Wire Vocabulary library.

            Use for in-progress 'thinking' events to maintain consistent Wire
            voice texture (BUILD_SPEC §6.3 + §6.4). The fragment may have
            `[snake_case]` slots — pass them as kwargs.

            Args:
                message_type: 'thinking' | 'milestone' | 'intervention' | 'decision'
                **slots: kwargs filled into [snake_case] placeholders
                    (e.g., place="Mt. Pleasant").

            Returns:
                A filled fragment string. Use it directly as the message in
                your next wire_emit call. If the fragment library is empty
                for this agent + message_type, returns an empty string and
                you should fall back to free-text generation.

            Voice texture: BUILD_SPEC §6.3 wants ~70% thinking + ~30%
            milestone. Lean on this tool for thinking events; you may
            freelance milestones.
            """
            if vocabulary is None:
                return ""
            fragment = vocabulary.sample(agent_name, message_type)
            if fragment is None:
                return ""
            return vocabulary.fill(fragment, **slots)

        return [
            wire_emit,
            read_recent_published,
            read_queue,
            dispatch_scout,
            dispatch_investigator,
            dispatch_storyteller,
            dispatch_narrator,
            dispatch_publish_gate,
            accept_equity_recommendation,
            request_equity_review,
            pull_vocabulary,
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
        """Read recent published feed + queue + cleared audits + cost.

        Compact (~1-2 KB) JSON for the Editor's user message. Per BUILD_SPEC
        §3.6 + plan §A.5, the Editor's prompt drives the decision; Python
        only assembles the snapshot.

        The `cleared_audits_awaiting_narration` slot surfaces every
        publish_audit doc with `final_decision=='cleared'` and
        `narration_dispatched != True` so the model can dispatch the
        Narrator on each (highest-leverage first by completed_at desc).
        """
        recent: list[dict] = []
        queue: list[dict] = []
        cleared_awaiting: list[dict] = []
        try:
            recent = await self._read_recent_published()
        except Exception:
            logger.exception("editor: read_recent_published failed; using empty list")
        try:
            queue = await self._read_queue()
        except Exception:
            logger.exception("editor: read_queue failed; using empty list")
        try:
            cleared_awaiting = await self._read_cleared_audits_awaiting_narration()
        except Exception:
            logger.exception(
                "editor: read_cleared_audits_awaiting_narration failed; using empty list"
            )

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
            "cleared_audits_awaiting_narration": cleared_awaiting,
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

    async def _read_cleared_audits_awaiting_narration(
        self, *, limit: int = 5
    ) -> list[dict]:
        """Up to N cleared `publish_audits` docs with `narration_dispatched`
        falsy, ordered by `completed_at` desc (highest-leverage first).

        Surfaces in the context snapshot as `cleared_audits_awaiting_narration`
        so the Pro model can dispatch the Narrator on each. Each dict is
        the minimum the model needs to call dispatch_narrator:
        `{audit_id, story_id, story_unit_id, completed_at}`.

        Read-only and best-effort: any Firestore error returns an empty
        list so the cycle proceeds to the rest of the snapshot.
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        try:
            coll = self._firestore.collection("publish_audits")
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(
                    filter=FieldFilter("final_decision", "==", "cleared")
                ).where(
                    filter=FieldFilter("narration_dispatched", "==", False)
                )
            except Exception:
                # Older SDK / stub shape — chain the where() calls without
                # FieldFilter. Stubs in tests pass-through everything; the
                # `narration_dispatched != True` guard runs in Python below.
                q = coll
                if hasattr(coll, "where"):
                    q = coll.where("final_decision", "==", "cleared").where(
                        "narration_dispatched", "==", False
                    )
            if hasattr(q, "order_by"):
                try:
                    q = q.order_by("completed_at", direction="DESCENDING")
                except TypeError:
                    q = q.order_by("completed_at")
            if hasattr(q, "limit"):
                q = q.limit(limit)
            out: list[dict] = []
            stream = q.stream() if hasattr(q, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    summary = _summarize_audit_doc(d)
                    if summary is not None:
                        out.append(summary)
            else:
                for d in stream:
                    summary = _summarize_audit_doc(d)
                    if summary is not None:
                        out.append(summary)
            return out[:limit]
        except Exception:
            logger.exception(
                "editor: read_cleared_audits_awaiting_narration: query failed"
            )
            return []

    async def _claim_audit_for_narration(self, audit_id: str) -> bool:
        """Atomically check `narration_dispatched=False` and set to True.

        Returns True iff THIS call claimed the audit; False if it was
        already claimed by a concurrent dispatch (or if the audit doc
        cannot be found). Day-6 dedup fix: previously the
        `narration_dispatched` flag was set AFTER `narrator.narrate()`
        completed (a 30+ second TTS call), giving a second think cycle
        time to read the audit as un-claimed and dispatch a duplicate
        Narrator. Setting the flag BEFORE narration via this claim
        closes the race.

        Implementation notes — works against both the production
        google-cloud-firestore async client AND the in-memory test stub:

        - Production path: prefers a Firestore transaction
          (`async_transactional` read-check-set on the audit's doc id).
          Resolves the doc id via `where('audit_id', '==', audit_id)`
          since `audit_id` is a UUID-hex field, not the auto-generated
          Firestore doc id.
        - Stub / fallback path: a direct read-check-set against the
          collection. Naturally atomic in single-thread asyncio because
          neither the stub's `.get()` nor `.update()` await between
          read and write — there is no interleaving point for a
          concurrent task to slip in.

        Best-effort: any unexpected Firestore failure returns True so
        the dispatch chain still proceeds (defense in depth — losing
        the dedup guard is preferable to losing a story silently).
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            # Local / stub-less mode — no race possible.
            return True
        try:
            coll = self._firestore.collection("publish_audits")
        except Exception:
            return True

        # Resolve the Firestore doc id from the `audit_id` field. The
        # PublishGate writes audits via `coll.add(...)`, so the doc id
        # is auto-generated and the audit_id lives in the body.
        target_doc_id = await self._resolve_audit_doc_id(coll, audit_id)
        if target_doc_id is None:
            logger.info(
                "editor._claim_audit_for_narration: audit %s not found",
                audit_id,
            )
            return False

        payload = {
            "narration_dispatched": True,
            "narration_dispatched_at": datetime.now(timezone.utc).isoformat(),
            "narration_dispatched_via": "editor.dispatch_narrator",
        }

        # Production path: Firestore transaction (real async client).
        try:
            from google.cloud import firestore as _firestore_lib  # type: ignore[import-untyped]
            transaction_factory = getattr(self._firestore, "transaction", None)
            async_transactional = getattr(
                _firestore_lib, "async_transactional", None
            )
            if callable(transaction_factory) and callable(async_transactional):
                doc_ref = coll.document(target_doc_id)

                @async_transactional
                async def _claim(tx, ref):
                    snap = await tx.get(ref)
                    if not getattr(snap, "exists", False):
                        return False
                    data = snap.to_dict() or {}
                    if data.get("narration_dispatched", False) is True:
                        return False
                    tx.update(ref, payload)
                    return True

                transaction = transaction_factory()
                return bool(await _claim(transaction, doc_ref))
        except Exception:
            logger.debug(
                "editor._claim_audit_for_narration: transaction path "
                "unavailable; falling back to read-check-set",
                exc_info=True,
            )

        # Stub / fallback: read-check-set without await between steps.
        try:
            doc_ref = coll.document(target_doc_id)
            snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
            if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                snapshot = await snapshot
            if snapshot is None or not getattr(snapshot, "exists", False):
                return False
            data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else {}
            if (data or {}).get("narration_dispatched", False) is True:
                return False
            if hasattr(doc_ref, "update"):
                res = doc_ref.update(payload)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
                return True
        except Exception:
            logger.exception(
                "editor._claim_audit_for_narration: fallback claim failed for %s",
                audit_id,
            )
            # Defense in depth — return True so dispatch still proceeds.
            return True
        return False

    async def _resolve_audit_doc_id(self, coll: Any, audit_id: str) -> str | None:
        """Best-effort lookup: `audit_id` field → Firestore doc id.

        Tries a `where('audit_id', '==', audit_id)` query first (real
        client); falls back to a full-collection scan (the test stub
        ignores `where`).
        """
        # Query path (real client honors where()).
        try:
            q = coll
            if hasattr(coll, "where"):
                try:
                    from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                    q = coll.where(filter=FieldFilter("audit_id", "==", audit_id))
                except Exception:
                    q = coll.where("audit_id", "==", audit_id)
                if hasattr(q, "limit"):
                    q = q.limit(1)
            stream = q.stream() if hasattr(q, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("audit_id") == audit_id:
                        return getattr(d, "id", None) or data.get("id")
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("audit_id") == audit_id:
                        return getattr(d, "id", None) or data.get("id")
        except Exception:
            logger.debug(
                "editor._resolve_audit_doc_id: scan failed for %s",
                audit_id,
                exc_info=True,
            )
        return None

    async def _mark_audit_narration_dispatched(self, audit_id: str) -> None:
        """Stamp `narration_dispatched=True` on the cleared audit so the
        next think cycle's context snapshot does not re-surface it.

        Best-effort: any Firestore failure is logged but never raised
        into the dispatch path (the manifest has already rendered).
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        try:
            coll = self._firestore.collection("publish_audits")
        except Exception:
            return
        payload = {
            "narration_dispatched": True,
            "narration_dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        # Direct doc-id update first — but only if the doc already exists,
        # otherwise FsDocRef.update() (and many production stubs) will
        # create a phantom doc keyed off `audit_id` while the real audit
        # lives under an auto-generated key (PublishGate writes via
        # coll.add so doc id != audit_id).
        if hasattr(coll, "document"):
            try:
                doc_ref = coll.document(audit_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                    snapshot = await snapshot
                if snapshot is not None and getattr(snapshot, "exists", False):
                    if hasattr(doc_ref, "update"):
                        res = doc_ref.update(payload)
                        if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                            await res
                        return
            except Exception:
                logger.debug(
                    "editor._mark_audit_narration_dispatched: doc_ref lookup failed; falling back to scan",
                    exc_info=True,
                )
        # Fallback scan: PublishGate writes audits via coll.add(), so the
        # doc id is auto-generated and the audit_id lives in a field.
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            target_doc_id = None
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("audit_id") == audit_id or data.get("id") == audit_id:
                        target_doc_id = getattr(d, "id", None) or data.get("id")
                        break
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("audit_id") == audit_id or data.get("id") == audit_id:
                        target_doc_id = getattr(d, "id", None) or data.get("id")
                        break
            if target_doc_id and hasattr(coll, "document"):
                try:
                    doc_ref = coll.document(target_doc_id)
                    if hasattr(doc_ref, "update"):
                        res = doc_ref.update(payload)
                        if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                            await res
                except Exception:
                    logger.exception(
                        "editor._mark_audit_narration_dispatched: scan-resolved update failed"
                    )
        except Exception:
            logger.exception(
                "editor._mark_audit_narration_dispatched: scan failed"
            )

    async def _read_story_draft(self, draft_id: str) -> dict | None:
        """Best-effort read of `/story_drafts/{draft_id}` from Firestore.

        Used by the Editor's `dispatch_narrator` tool to verify the
        draft is cleared before invoking the Narrator. Returns None on
        any failure path (firestore unavailable, doc missing, scan
        error).
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return None
        try:
            coll = self._firestore.collection("story_drafts")
        except Exception:
            return None

        # Direct doc-id lookup (fastest).
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(draft_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
                        if data:
                            data.setdefault("id", draft_id)
                            return data
        except Exception:
            logger.debug(
                "editor._read_story_draft: doc-id lookup failed; falling back to scan",
                exc_info=True,
            )

        # Fallback: scan for matching `id` field (the path the unit-test
        # stub takes).
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        return data
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        return data
        except Exception:
            logger.exception("editor._read_story_draft: scan failed")
            return None

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

    async def _apply_equity_recommendation(self, intervention_id: str) -> dict:
        """Read `/equity_interventions/{id}`, write back editor_response,
        emit a Wire decision event.

        Returns: `{accepted, intervention_id,
        suggested_priority_lift_story_unit_id?, reason?, persisted}`. The
        method is defensive — every Firestore failure surfaces as an
        `accepted=False` result with an `error` field rather than raising
        into the loop.
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return {
                "accepted": False,
                "intervention_id": intervention_id,
                "error": "firestore_unavailable",
            }

        try:
            coll = self._firestore.collection("equity_interventions")
        except Exception as e:
            return {
                "accepted": False,
                "intervention_id": intervention_id,
                "error": f"equity_interventions_unavailable: {e}",
            }

        intervention: dict | None = None
        doc_ref = None

        # Direct doc-id lookup first (fastest path).
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(intervention_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
                        if data:
                            intervention = dict(data)
                            intervention.setdefault("intervention_id", intervention_id)
        except Exception:
            logger.debug(
                "editor._apply_equity_recommendation: doc-id lookup failed; falling back to scan",
                exc_info=True,
            )

        # Fallback: scan for a doc whose `intervention_id` matches.
        if intervention is None:
            try:
                stream = coll.stream() if hasattr(coll, "stream") else []
                if hasattr(stream, "__aiter__"):
                    async for d in stream:
                        data = _doc_to_dict(d)
                        if (
                            data.get("intervention_id") == intervention_id
                            or data.get("id") == intervention_id
                        ):
                            intervention = data
                            break
                else:
                    for d in stream:
                        data = _doc_to_dict(d)
                        if (
                            data.get("intervention_id") == intervention_id
                            or data.get("id") == intervention_id
                        ):
                            intervention = data
                            break
            except Exception as e:
                logger.exception(
                    "editor._apply_equity_recommendation: scan failed"
                )
                return {
                    "accepted": False,
                    "intervention_id": intervention_id,
                    "error": f"equity_interventions_scan_failed: {e}",
                }

        if intervention is None:
            logger.warning(
                "editor._apply_equity_recommendation: intervention %s not found",
                intervention_id,
            )
            return {
                "accepted": False,
                "intervention_id": intervention_id,
                "error": "intervention_not_found",
            }

        suggested_id = intervention.get(
            "suggested_priority_lift_story_unit_id"
        )
        reason = intervention.get("reason")

        # Update the intervention with editor_response. Try doc_ref.update,
        # fall back to coll.add (the unit-test stub records writes there).
        updated_at = datetime.now(timezone.utc).isoformat()
        update_payload = {
            "editor_response": "accepted",
            "editor_response_at": updated_at,
        }
        persisted = await self._persist_intervention_response(
            coll=coll,
            doc_ref=doc_ref,
            intervention=intervention,
            update_payload=update_payload,
        )

        # Emit a Wire decision event so the Editor → Equity Editor handoff is
        # visible. Voice text comes from the prompt; this is a structured
        # status emit, not a voice utterance.
        try:
            event: dict = {
                "agent": "editor",
                "message": "Agreed. Promoting Paralympic-anchored lead.",
                "message_type": "decision",
                "mode": "live",
            }
            if suggested_id:
                event["story_unit_id"] = suggested_id
            await self._wire.emit(event)
        except WireProxyNotReadyError:
            logger.warning(
                "editor._apply_equity_recommendation: wire proxy not ready"
            )
        except Exception:
            logger.exception(
                "editor._apply_equity_recommendation: wire emit failed"
            )

        return {
            "accepted": True,
            "intervention_id": intervention_id,
            "suggested_priority_lift_story_unit_id": suggested_id,
            "reason": reason,
            "persisted": persisted,
        }

    async def _persist_intervention_response(
        self,
        *,
        coll: Any,
        doc_ref: Any,
        intervention: dict,
        update_payload: dict,
    ) -> bool:
        """Persist the editor_response on an equity intervention doc.

        Tries doc_ref.update (preferred), falls back to coll.add of a merged
        doc (unit-test stub contract). Returns True iff a write succeeded.
        """
        if doc_ref is not None and hasattr(doc_ref, "update"):
            try:
                res = doc_ref.update(update_payload)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
                return True
            except Exception:
                logger.debug(
                    "editor._persist_intervention_response: doc_ref.update failed; falling back to add",
                    exc_info=True,
                )

        # Fallback to add() with the merged doc — the unit-test stub asserts
        # on the most-recent add() payload.
        if hasattr(coll, "add"):
            try:
                merged = dict(intervention)
                merged.update(update_payload)
                res = coll.add(merged)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
                return True
            except Exception:
                logger.exception(
                    "editor._persist_intervention_response: coll.add failed"
                )
        return False

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
    cleared_awaiting = snapshot.get("cleared_audits_awaiting_narration", [])
    cost = snapshot.get("cost_today", {})
    return (
        "## Recent published feed (last 10)\n"
        f"{json.dumps(recent, ensure_ascii=False)}\n\n"
        "## Active queue\n"
        f"{json.dumps(queue, ensure_ascii=False)}\n\n"
        "## Cleared audits awaiting narration\n"
        f"{json.dumps(cleared_awaiting, ensure_ascii=False)}\n\n"
        "## Cost dashboard (today, USD-equivalent axes)\n"
        f"{json.dumps(cost, ensure_ascii=False)}\n\n"
        "## What is your decision for this think-cycle?\n"
        "Choose one: dispatch a Scout, advance an investigation, accept an "
        "Equity recommendation, dispatch the Narrator on a cleared audit, "
        "or sleep. Keep your wire utterance terse (8-15 words)."
    )


def _resolve_voice_alias(voice_profile: str | None) -> str:
    """Map prompt-level voice aliases to the Narrator's voice_profile API.

    The Editor's prompt instructs the model to pass `'algenib'` (the warm
    Broadcast voice per HOE-DEC-025); the Narrator's `narrate(...)`
    accepts `'broadcast' | 'dispatcher'`. We translate at the dispatch
    boundary so neither side has to know about the other's vocabulary.
    """
    if not isinstance(voice_profile, str):
        return "broadcast"
    v = voice_profile.strip().lower()
    if v in {"algenib", "broadcast"}:
        return "broadcast"
    if v in {"fenrir", "dispatcher", "wire"}:
        return "dispatcher"
    return "broadcast"


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


def _summarize_audit_doc(doc: Any) -> dict | None:
    """Reduce a publish_audits doc to the fields the Editor cares about.

    Returns None when the doc isn't a cleared+un-narrated audit (defensive
    Python-side filter for stub clients that don't honor where()).
    """
    data = doc.to_dict() if hasattr(doc, "to_dict") else (doc if isinstance(doc, dict) else {})
    if not isinstance(data, dict):
        return None
    if data.get("final_decision") != "cleared":
        return None
    if data.get("narration_dispatched"):
        return None
    audit_id = data.get("audit_id") or data.get("id") or getattr(doc, "id", None)
    return {
        "audit_id": audit_id,
        "story_id": data.get("story_id"),
        "story_unit_id": data.get("story_unit_id"),
        "completed_at": data.get("completed_at"),
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
