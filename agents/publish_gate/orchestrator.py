"""PublishGateAgent: orchestrates all 7 Publish-Gate sub-stages.

Mirrors EditorAgent / InvestigatorAgent / StorytellerAgent on the public
surface (`__init__`, `name`, `autonomous_loop`) but the body is
deterministic — the seven sub-stages run in a fixed order, each producing
a typed result, and the orchestrator computes the final decision. There
is no LLM Runner driving the sub-stage selection — sub-stage selection
IS the agent's procedure (BUILD_SPEC §5.7).

Sub-stage order (BUILD_SPEC §5.7):
  1. Fact Check       (LLM-Pro, async, cost-counted)
  2. Source Review    (deterministic, sync)
  3. Parity Review    (deterministic, sync)
  4. NIL Redaction    (Day-2 stub: direct match + redact)
  5. Safety Review    (LLM-Flash-Lite, async, cost-counted)
  6. Language Review  (deterministic regex)
  7. Visual Review    (Day-6 stub — auto-pass)

Decision logic per BUILD_SPEC §5.7 step 6:
  - All sub-stages pass → final_decision='cleared'; write
    PublishAudit to `/publish_audits/{auto_id}`; emit Wire 'milestone'
    "Cleared for publication."
  - Any sub-stage fails AND draft.equity_review.revisions_count <
    max_revisions → return draft to Storyteller (mark
    publish_gate_decision='returned'); increment revisions; emit Wire
    'thinking' explaining the return.
  - Any sub-stage fails AND revisions_count >= max_revisions → kill the
    draft (publish_gate_decision='killed', kill_reason='[stage]_unresolvable');
    emit Wire 'milestone' "killed at [stage]: [reason]"; copy draft to
    `/killed_drafts/{auto_id}` for audit retention.

Voice text lives in `/prompts/publish_gate.md`. Python here contains
zero voice text. Wire emits per sub-stage pull from
`wire_vocabulary.json`'s `publish_gate` bucket; if a fragment is empty,
we fall back to a deterministic free-text format string.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.observability import log_agent_call, trace_span
from agents.publish_gate.types import (
    FactCheckResult,
    LanguageReviewResult,
    NilRedactionResult,
    ParityReviewResult,
    PublishAudit,
    SafetyReviewResult,
    SourceReviewResult,
    VisualReviewResult,
)
from agents.wire.emit import WireProxyNotReadyError

logger = logging.getLogger(__name__)


# Default max revisions per BUILD_SPEC §5.7 step 6 (also CONSTITUTION §7).
_DEFAULT_MAX_REVISIONS = 3

# Sub-stage names — keep in sync with BUILD_SPEC §8.6 sub_stages keys.
_SUBSTAGES_ORDER: tuple[str, ...] = (
    "fact_check",
    "source_review",
    "parity_review",
    "nil_redaction_review",
    "safety_review",
    "language_review",
    "visual_review",
)


class PublishGateAgent:
    """The Publish Gate orchestrator. Procedural, calm, reports facts."""

    def __init__(
        self,
        *,
        prompt: str,
        wire: Any,
        firestore: Any,
        nil_layer: Any,
        fact_check: Any,
        source_review: Any,
        parity_review: Any,
        safety_review: Any,
        language_review: Any,
        visual_review: Any | None = None,
        cost_counter: Any | None = None,
        wire_vocabulary: Any | None = None,
        runtime_state: Any | None = None,
        max_revisions: int = _DEFAULT_MAX_REVISIONS,
    ) -> None:
        # `prompt` is stored for parity with the other agents — Day-6 does
        # not invoke the LLM Runner here (sub-stages are programmatic), but
        # Day-7+ may add a Pro-tier audit-summary call.
        self._prompt = prompt
        self._wire = wire
        self._firestore = firestore
        self._nil_layer = nil_layer
        self._fact_check = fact_check
        self._source_review = source_review
        self._parity_review = parity_review
        self._safety_review = safety_review
        self._language_review = language_review
        # Visual Review stub is optional in tests; default to a no-op pass.
        if visual_review is None:
            from agents.publish_gate.visual_review import VisualReviewSubstage
            visual_review = VisualReviewSubstage()
        self._visual_review = visual_review
        self._cost_counter = cost_counter
        self._wire_vocabulary = wire_vocabulary
        self._runtime_state = runtime_state
        self._max_revisions = int(max_revisions)

    # -- Public surface ------------------------------------------------------

    @property
    def name(self) -> str:
        return "publish_gate"

    # -- Main entry point ----------------------------------------------------

    async def review(
        self,
        *,
        story_draft_id: str,
        ctx: Any | None = None,
    ) -> PublishAudit:
        """Run all 7 sub-stages on a single draft.

        Reads `/story_drafts/{story_draft_id}` from Firestore, then reads
        `/investigation_packets/{draft.investigation_packet_id}`, then
        executes sub-stages in order, then writes the audit.

        Failure modes (BUILD_SPEC §17.1):
          - Any sub-stage exception (not a deliberate fail) → emit Wire
            thinking ('hold — publish gate stage [N] errored, retrying'),
            retry once. If still failing, treat as a fail and either
            return or kill per the revision budget.
          - Draft missing → emit thinking + return PublishAudit with
            final_decision='killed', kill_reason='draft_not_found'.
          - Packet missing → emit thinking + still try to run the
            deterministic sub-stages; LLM sub-stages will fail gracefully.

        Returns the PublishAudit dict.
        """
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug(
                "publish_gate.review: paused (AGENT_RUNTIME_PAUSED=1); skipping"
            )
            return PublishAudit(
                story_id=story_draft_id,
                final_decision="killed",
                kill_reason="paused",
                completed_at=_iso_now(),
                sub_stages={},
            )

        investigation_id = (
            getattr(ctx, "investigation_id", None) if ctx is not None else None
        ) or f"publish-gate-{story_draft_id}"
        compression_factor = (
            float(getattr(ctx, "compression_factor", 1.0)) if ctx is not None else 1.0
        )

        # --- Read the draft ---------------------------------------------------
        draft = await self._read_story_draft(story_draft_id)
        if draft is None:
            await self._safe_emit_thinking(
                "*hold — story draft missing; publish gate cannot proceed*",
                investigation_id=investigation_id,
            )
            audit = PublishAudit(
                story_id=story_draft_id,
                final_decision="killed",
                kill_reason="draft_not_found",
                completed_at=_iso_now(),
                sub_stages={},
            )
            return audit

        packet_id = draft.get("investigation_packet_id") or ""
        packet = await self._read_investigation_packet(packet_id) if packet_id else {}
        if packet is None:
            packet = {}

        story_unit_id = draft.get("story_unit_id")

        # --- Run sub-stages in order -----------------------------------------
        with trace_span(
            "publish_gate.review",
            investigation_id=investigation_id,
            attrs={
                "story_draft_id": story_draft_id,
                "investigation_packet_id": packet_id,
                "compression_factor": compression_factor,
            },
        ):
            t0 = time.monotonic()
            sub_stages, first_failure = await self._run_substages(
                story_draft=draft,
                investigation_packet=packet,
                investigation_id=investigation_id,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

        # --- Decide --------------------------------------------------------
        revisions_count = _read_revisions_count(draft)
        revisions_requested: list[str] = []
        kill_reason: str = ""
        if first_failure is None:
            final_decision = "cleared"
        else:
            revisions_requested = [first_failure]
            if revisions_count >= self._max_revisions:
                final_decision = "killed"
                kill_reason = f"{first_failure}_unresolvable"
            else:
                final_decision = "returned"

        audit_id = uuid.uuid4().hex
        audit = PublishAudit(
            audit_id=audit_id,
            story_id=story_draft_id,
            investigation_packet_id=packet_id,
            sub_stages=sub_stages,
            final_decision=final_decision,
            completed_at=_iso_now(),
            revisions_requested=revisions_requested,
            kill_reason=kill_reason,
        )

        # --- Persist + emit ------------------------------------------------
        if final_decision == "cleared":
            await self._write_publish_audit(audit)
            await self._mark_publish_gate_decision(
                story_draft_id, "cleared"
            )
            await self._emit_milestone_with_vocabulary(
                free_text="Cleared for publication.",
                investigation_id=investigation_id,
                story_unit_id=story_unit_id,
            )
        elif final_decision == "returned":
            await self._mark_publish_gate_decision(
                story_draft_id, "returned",
                feedback=_render_revision_request(sub_stages, first_failure),
            )
            await self._safe_emit_thinking(
                f"returned at {first_failure} for revision",
                investigation_id=investigation_id,
                story_unit_id=story_unit_id,
            )
        else:  # killed
            await self._write_publish_audit(audit)
            await self._copy_to_killed_drafts(draft, kill_reason=kill_reason)
            await self._mark_publish_gate_decision(
                story_draft_id, "killed"
            )
            await self._emit_milestone_with_vocabulary(
                free_text=f"killed at {first_failure}: {kill_reason}",
                investigation_id=investigation_id,
                story_unit_id=story_unit_id,
            )

        # --- Structured logging --------------------------------------------
        log_agent_call(
            agent="publish_gate",
            sub_agent=None,
            story_unit_id=story_unit_id,
            investigation_id=investigation_id,
            model=None,
            tool=None,
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            compression_factor=compression_factor,
            outcome="success" if final_decision == "cleared" else "error",
            wire_event_id=None,
            error=None if final_decision == "cleared" else kill_reason or first_failure,
        )

        self._stamp_last_think_cycle()
        return audit

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """No autonomous loop — Publish Gate is invoked by the Editor /
        Storyteller via dispatch tool."""
        if stop_event is not None:
            try:
                await stop_event.wait()
            except Exception:
                logger.debug(
                    "publish_gate.autonomous_loop: stop_event.wait raised"
                )

    # -- Sub-stage runner ---------------------------------------------------

    async def _run_substages(
        self,
        *,
        story_draft: dict,
        investigation_packet: dict,
        investigation_id: str,
    ) -> tuple[dict, str | None]:
        """Run all 7 sub-stages in order. Return (sub_stages_dict, first_failure_name).

        first_failure_name is the canonical sub-stage key that failed first
        (e.g., 'fact_check'); None if every sub-stage passed.
        """
        story_unit_id = story_draft.get("story_unit_id")
        sub_stages: dict[str, Any] = {}
        first_failure: str | None = None

        # Sub-stage 1: Fact Check (Pro-tier LLM, with retry-on-error).
        fact = await self._run_one_substage(
            name="fact_check",
            invoke=lambda: self._fact_check.review(
                story_draft=story_draft,
                investigation_packet=investigation_packet,
                wire=self._wire,
                investigation_id=investigation_id,
            ),
            investigation_id=investigation_id,
        )
        sub_stages["fact_check"] = fact
        await self._emit_substage_thinking(
            substage="fact_check",
            result=fact,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(fact):
            first_failure = "fact_check"

        # Sub-stage 2: Source Review (deterministic, sync).
        source = await self._run_one_substage(
            name="source_review",
            invoke=lambda: _wrap_sync(
                self._source_review.review(
                    story_draft=story_draft,
                    investigation_packet=investigation_packet,
                )
            ),
            investigation_id=investigation_id,
        )
        sub_stages["source_review"] = source
        await self._emit_substage_thinking(
            substage="source_review",
            result=source,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(source):
            first_failure = "source_review"

        # Sub-stage 3: Parity Review (deterministic, sync).
        parity = await self._run_one_substage(
            name="parity_review",
            invoke=lambda: _wrap_sync(
                self._parity_review.review(story_draft=story_draft)
            ),
            investigation_id=investigation_id,
        )
        sub_stages["parity_review"] = parity
        await self._emit_substage_thinking(
            substage="parity_review",
            result=parity,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(parity):
            first_failure = "parity_review"

        # Sub-stage 4: NIL Redaction (Day-2 stub: direct-match + redact).
        nil = await self._run_one_substage(
            name="nil_redaction_review",
            invoke=lambda: _wrap_sync(
                _run_nil_redaction(self._nil_layer, story_draft)
            ),
            investigation_id=investigation_id,
        )
        sub_stages["nil_redaction_review"] = nil
        await self._emit_substage_thinking(
            substage="nil_redaction_review",
            result=nil,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(nil):
            first_failure = "nil_redaction_review"

        # Sub-stage 5: Safety Review (Flash-Lite LLM with deterministic
        # fallback baked in to the sub-stage).
        safety = await self._run_one_substage(
            name="safety_review",
            invoke=lambda: self._safety_review.review(
                story_draft=story_draft,
                investigation_packet=investigation_packet,
                wire=self._wire,
                investigation_id=investigation_id,
            ),
            investigation_id=investigation_id,
        )
        sub_stages["safety_review"] = safety
        await self._emit_substage_thinking(
            substage="safety_review",
            result=safety,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(safety):
            first_failure = "safety_review"

        # Sub-stage 6: Language Review (pure-Python regex; sync).
        language = await self._run_one_substage(
            name="language_review",
            invoke=lambda: _wrap_sync(
                self._language_review.review(story_draft=story_draft)
            ),
            investigation_id=investigation_id,
        )
        sub_stages["language_review"] = language
        await self._emit_substage_thinking(
            substage="language_review",
            result=language,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(language):
            first_failure = "language_review"

        # Sub-stage 7: Visual Review (Day-6 stub: auto-pass).
        visual = await self._run_one_substage(
            name="visual_review",
            invoke=lambda: _wrap_sync(
                self._visual_review.review(story_draft=story_draft)
            ),
            investigation_id=investigation_id,
        )
        sub_stages["visual_review"] = visual
        await self._emit_substage_thinking(
            substage="visual_review",
            result=visual,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )
        if first_failure is None and not _passed(visual):
            first_failure = "visual_review"

        return sub_stages, first_failure

    async def _run_one_substage(
        self,
        *,
        name: str,
        invoke,  # zero-arg callable returning an awaitable
        investigation_id: str,
    ) -> dict:
        """Run a single sub-stage with one retry on exception (BUILD_SPEC §17.1).

        On the second exception we surface a passed=False dict with an
        `error` field so the orchestrator can branch on the failure
        without raising.
        """
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                result = await invoke()
                # Sub-stage results are TypedDicts; coerce to dict for
                # Firestore-friendly serialization.
                return dict(result) if result is not None else {"passed": False}
            except Exception as e:
                last_exc = e
                logger.warning(
                    "publish_gate.%s: attempt %d/2 raised: %s",
                    name, attempt + 1, e,
                )
                if attempt == 0:
                    await self._safe_emit_thinking(
                        f"*hold — publish gate {name} errored, retrying*",
                        investigation_id=investigation_id,
                    )
        # Both attempts failed.
        logger.error("publish_gate.%s: failed after retries: %s", name, last_exc)
        return {
            "passed": False,
            "error": f"{name}_exception",
        }

    # -- Sub-stage Wire emit ------------------------------------------------

    async def _emit_substage_thinking(
        self,
        *,
        substage: str,
        result: dict,
        investigation_id: str,
        story_unit_id: str | None = None,
    ) -> None:
        """Emit a 'thinking' Wire event reporting this sub-stage's result.

        Pulls a vocabulary fragment from the publish_gate bucket; falls
        back to a deterministic free-text summary if vocabulary lookup
        returns empty. Slot values come from the sub-stage's typed
        result fields.
        """
        slots = _slots_for_substage(substage, result)
        free_text = _free_text_for_substage(substage, result)
        await self._emit_thinking_with_vocabulary(
            free_text=free_text,
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
            slots=slots,
        )

    async def _emit_thinking_with_vocabulary(
        self,
        *,
        free_text: str,
        investigation_id: str,
        story_unit_id: str | None = None,
        slots: dict | None = None,
    ) -> None:
        message = free_text
        if self._wire_vocabulary is not None:
            try:
                fragment = self._wire_vocabulary.sample(
                    "publish_gate", "thinking"
                )
                if fragment:
                    filled = self._wire_vocabulary.fill(fragment, **(slots or {}))
                    if filled:
                        message = filled
            except Exception:
                logger.debug(
                    "publish_gate: vocabulary sample/fill failed; using free text",
                    exc_info=True,
                )
        try:
            event: dict = {
                "agent": "publish_gate",
                "message": message,
                "message_type": "thinking",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "publish_gate: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "publish_gate: failed to emit thinking event"
            )

    async def _emit_milestone_with_vocabulary(
        self,
        *,
        free_text: str,
        investigation_id: str,
        story_unit_id: str | None = None,
        slots: dict | None = None,
    ) -> None:
        message = free_text
        if self._wire_vocabulary is not None:
            try:
                fragment = self._wire_vocabulary.sample(
                    "publish_gate", "milestone"
                )
                if fragment:
                    filled = self._wire_vocabulary.fill(fragment, **(slots or {}))
                    if filled:
                        message = filled
            except Exception:
                logger.debug(
                    "publish_gate: vocabulary sample/fill failed (milestone); using free text",
                    exc_info=True,
                )
        try:
            event: dict = {
                "agent": "publish_gate",
                "message": message,
                "message_type": "milestone",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "publish_gate: wire proxy not ready; cannot emit milestone event"
            )
        except Exception:
            logger.exception(
                "publish_gate: failed to emit milestone event"
            )

    async def _safe_emit_thinking(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None = None,
    ) -> None:
        try:
            event: dict = {
                "agent": "publish_gate",
                "message": message,
                "message_type": "thinking",
                "mode": "live",
            }
            if story_unit_id is not None:
                event["story_unit_id"] = story_unit_id
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "publish_gate: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "publish_gate: failed to emit thinking event"
            )

    # -- Firestore I/O ------------------------------------------------------

    async def _read_story_draft(self, draft_id: str) -> dict | None:
        """Best-effort read of `/story_drafts/{draft_id}` from Firestore."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return None
        try:
            coll = self._firestore.collection("story_drafts")
        except Exception:
            return None

        # Direct doc-id lookup first.
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(draft_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict()
                            if hasattr(snapshot, "to_dict")
                            else None
                        )
                        if data:
                            data.setdefault("id", draft_id)
                            return data
        except Exception:
            logger.debug(
                "publish_gate._read_story_draft: doc-id lookup failed; scanning",
                exc_info=True,
            )

        # Fallback: scan for matching `id` field.
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
            logger.exception("publish_gate._read_story_draft: scan failed")
            return None
        return None

    async def _read_investigation_packet(self, packet_id: str) -> dict:
        """Best-effort read of `/investigation_packets/{packet_id}`."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return {}
        try:
            coll = self._firestore.collection("investigation_packets")
        except Exception:
            return {}
        # Doc-id lookup.
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(packet_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict()
                            if hasattr(snapshot, "to_dict")
                            else None
                        )
                        if data:
                            data.setdefault("id", packet_id)
                            return data
        except Exception:
            logger.debug(
                "publish_gate._read_investigation_packet: doc-id lookup failed; scanning",
                exc_info=True,
            )
        # Fallback: scan.
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == packet_id:
                        return data
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == packet_id:
                        return data
        except Exception:
            logger.exception(
                "publish_gate._read_investigation_packet: scan failed"
            )
        return {}

    async def _write_publish_audit(self, audit: PublishAudit) -> None:
        """Write the audit doc to `/publish_audits/{auto_id}`. Best-effort."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        try:
            coll = self._firestore.collection("publish_audits")
        except Exception:
            return
        try:
            res = coll.add(dict(audit))
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
        except Exception:
            logger.exception(
                "publish_gate._write_publish_audit: write failed (audit=%s)",
                audit.get("audit_id"),
            )

    async def _copy_to_killed_drafts(
        self, draft: dict, *, kill_reason: str
    ) -> None:
        """Copy a killed draft to `/killed_drafts/{auto_id}` for audit retention."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        try:
            coll = self._firestore.collection("killed_drafts")
        except Exception:
            return
        try:
            payload = dict(draft)
            payload["kill_reason"] = kill_reason
            payload["killed_at"] = _iso_now()
            res = coll.add(payload)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
        except Exception:
            logger.exception(
                "publish_gate._copy_to_killed_drafts: write failed"
            )

    async def _mark_publish_gate_decision(
        self,
        draft_id: str,
        decision: str,
        *,
        feedback: str | None = None,
    ) -> None:
        """Mutate the draft's publish_gate_decision (and revisions count)."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        try:
            coll = self._firestore.collection("story_drafts")
        except Exception:
            return

        # Read current state so we can increment revisions on a return.
        current: dict | None = None
        doc_ref = None
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(draft_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        current = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
        except Exception:
            logger.debug(
                "publish_gate._mark_publish_gate_decision: doc-id lookup failed",
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
                    "publish_gate._mark_publish_gate_decision: scan failed"
                )
                current = None

        updated = dict(current or {})
        updated.setdefault("id", draft_id)
        updated["publish_gate_decision"] = decision
        updated["updated_at"] = _iso_now()
        if decision == "returned":
            equity_review = dict(updated.get("equity_review") or {})
            equity_review["revisions_count"] = (
                int(equity_review.get("revisions_count") or 0) + 1
            )
            if feedback is not None:
                equity_review["publish_gate_feedback"] = feedback
            updated["equity_review"] = equity_review
            if feedback is not None:
                updated["revision_request"] = feedback

        # Try doc_ref.update / set / coll.add.
        if doc_ref is not None and hasattr(doc_ref, "update"):
            try:
                payload = {
                    "publish_gate_decision": decision,
                    "updated_at": updated["updated_at"],
                }
                if decision == "returned":
                    payload["equity_review"] = updated["equity_review"]
                    if feedback is not None:
                        payload["revision_request"] = feedback
                res = doc_ref.update(payload)
                if hasattr(res, "__await__"):
                    await res
                return
            except Exception:
                logger.debug(
                    "publish_gate._mark_publish_gate_decision: doc_ref.update failed",
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
                    "publish_gate._mark_publish_gate_decision: doc_ref.set failed",
                    exc_info=True,
                )
        if hasattr(coll, "add"):
            try:
                res = coll.add(updated)
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                logger.exception(
                    "publish_gate._mark_publish_gate_decision: coll.add fallback failed"
                )

    # -- Internals ----------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception(
                "publish_gate: failed to stamp last_think_cycle"
            )


# -- Helpers ------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _passed(result: Any) -> bool:
    """True if the sub-stage result dict says passed=True."""
    if result is None:
        return False
    try:
        return bool(result.get("passed", False))
    except AttributeError:
        return False


async def _wrap_sync(value: Any) -> Any:
    """Tiny adapter: turn a sync sub-stage's already-evaluated result into
    an awaitable for `_run_one_substage`."""
    return value


def _run_nil_redaction(nil_layer: Any, story_draft: dict) -> NilRedactionResult:
    """Run the NIL Redaction Layer (Day-2 stub) against the draft body
    and produce a sub-stage 4 result dict.

    The Day-2 stub only does direct-match-and-redact via `scan_wire`. We
    scan the draft body and tally matches; the layer's redacted_message
    is not applied here (the Storyteller already passed the draft
    through equity, and Wire-level enforcement runs on every emit). This
    sub-stage's role is the AUDIT count.

    Returns a NilRedactionResult dict.
    """
    if nil_layer is None or not getattr(nil_layer, "is_loaded", False):
        # Layer not loaded — fail closed at the audit level (the runtime
        # would have exited already if registry was too small). Surface
        # passed=False so the orchestrator returns the draft.
        return NilRedactionResult(
            individual_refs_reviewed=0,
            direct_matches=0,
            near_identifications=0,
            small_aggregates=0,
            aggregated=0,
            redacted=0,
            returned_to_storyteller=0,
            passed=False,
        )

    body = (story_draft or {}).get("body") or ""
    try:
        scan = nil_layer.scan_wire(body, surface="wire", context=None)
    except Exception:
        logger.exception("nil_redaction: scan_wire raised")
        return NilRedactionResult(
            individual_refs_reviewed=0,
            direct_matches=0,
            near_identifications=0,
            small_aggregates=0,
            aggregated=0,
            redacted=0,
            returned_to_storyteller=0,
            passed=False,
        )

    direct_matches = int(scan.log.direct_matches_redacted or 0)
    aggregations = int(scan.log.aggregations_applied or 0)
    redacted = direct_matches  # Day-2 stub: every direct match is redacted.

    # Pass when no individual references found.
    passed = scan.decision == "pass"

    return NilRedactionResult(
        individual_refs_reviewed=direct_matches + aggregations,
        direct_matches=direct_matches,
        near_identifications=0,
        small_aggregates=0,
        aggregated=aggregations,
        redacted=redacted,
        returned_to_storyteller=0,
        passed=passed,
    )


def _read_revisions_count(draft: dict) -> int:
    """How many revisions has the draft been through already?"""
    if not isinstance(draft, dict):
        return 0
    equity_review = draft.get("equity_review") or {}
    if not isinstance(equity_review, dict):
        return 0
    try:
        return int(equity_review.get("revisions_count") or 0)
    except (TypeError, ValueError):
        return 0


def _slots_for_substage(substage: str, result: Any) -> dict:
    """Build the kwargs for `WireVocabulary.fill` for a sub-stage's fragment."""
    if not isinstance(result, dict):
        return {}
    if substage == "fact_check":
        return {
            "n": int(result.get("claims_checked") or 0),
            "m": int(result.get("claims_removed") or 0),
            "k": int(result.get("claims_softened") or 0),
            "reason": "ok" if result.get("passed") else "claims unsupported",
        }
    if substage == "source_review":
        outlets = result.get("outlets") or []
        return {
            "n": int(result.get("source_count") or 0),
            "m": len(outlets) if isinstance(outlets, list) else 0,
            "reason": "ok" if result.get("passed") else "insufficient sources",
        }
    if substage == "parity_review":
        return {
            "n": 1 if result.get("equity_cleared") else 0,
            "reason": result.get("equity_feedback") or "",
        }
    if substage == "nil_redaction_review":
        return {
            "n": int(result.get("individual_refs_reviewed") or 0),
            "m": int(result.get("aggregated") or 0),
            "k": int(result.get("redacted") or 0),
            "reason": "ok" if result.get("passed") else "individual refs found",
        }
    if substage == "safety_review":
        return {
            "n": int(result.get("invented_quotes") or 0),
            "m": int(result.get("private_info_flags") or 0),
            "reason": "ok" if result.get("passed") else "safety flags present",
        }
    if substage == "language_review":
        return {
            "n": int(result.get("predictive_phrases_softened") or 0),
            "m": int(result.get("restricted_terms_flagged") or 0),
            "reason": "ok" if result.get("passed") else "restricted terms present",
        }
    if substage == "visual_review":
        return {
            "n": int(result.get("regenerations") or 0),
            "reason": "stub" if result.get("stub") else "ok",
        }
    return {}


def _free_text_for_substage(substage: str, result: Any) -> str:
    """Deterministic free-text format-string fallback when vocabulary
    returns empty. Per BUILD_SPEC §5.7 voice signature examples."""
    if not isinstance(result, dict):
        return f"sub-stage {substage} complete"
    if substage == "fact_check":
        n = int(result.get("claims_checked") or 0)
        removed = int(result.get("claims_removed") or 0)
        softened = int(result.get("claims_softened") or 0)
        return f"{n} claims checked, {removed} removed, {softened} softened."
    if substage == "source_review":
        n = int(result.get("source_count") or 0)
        outlets = result.get("outlets") or []
        m = len(outlets) if isinstance(outlets, list) else 0
        return f"source count: {n}. hometown coverage confirmed via {m} outlets."
    if substage == "parity_review":
        if result.get("equity_cleared"):
            return "parity review: equity editor cleared."
        return "parity review: equity editor returned, holding."
    if substage == "nil_redaction_review":
        n = int(result.get("individual_refs_reviewed") or 0)
        aggregated = int(result.get("aggregated") or 0)
        redacted = int(result.get("redacted") or 0)
        return (
            f"nil redaction: {n} individual references reviewed. "
            f"{aggregated} aggregated. {redacted} redacted."
        )
    if substage == "safety_review":
        invented = int(result.get("invented_quotes") or 0)
        private = int(result.get("private_info_flags") or 0)
        return f"safety review: {invented} invented quotes, {private} private-info flags."
    if substage == "language_review":
        flagged = int(result.get("restricted_terms_flagged") or 0)
        soften = int(result.get("predictive_phrases_softened") or 0)
        return f"language review: {flagged} flagged, {soften} predictive constructions."
    if substage == "visual_review":
        regen = int(result.get("regenerations") or 0)
        return f"visual review: {regen} regenerations, cleared."
    return f"sub-stage {substage} complete."


def _render_revision_request(sub_stages: dict, first_failure: str | None) -> str:
    """Build a structured revision_request string for the returned draft.

    Mostly informational — the Storyteller's revision pass reads this
    string as Equity Editor-style feedback.
    """
    if not first_failure:
        return ""
    failed = sub_stages.get(first_failure) or {}
    lines = [f"Publish Gate returned at {first_failure}."]
    if first_failure == "fact_check":
        removed = failed.get("removed_claims") or []
        softened = failed.get("softened_claims") or []
        if removed:
            lines.append(f"Removed claims: {removed}")
        if softened:
            lines.append(f"Softened claims: {softened}")
    elif first_failure == "source_review":
        lines.append(
            f"source_count={failed.get('source_count')} outlets={failed.get('outlets')}"
        )
    elif first_failure == "parity_review":
        lines.append(
            f"equity_feedback={failed.get('equity_feedback')!r}"
        )
    elif first_failure == "nil_redaction_review":
        lines.append(
            f"direct_matches={failed.get('direct_matches')} "
            f"redacted={failed.get('redacted')}"
        )
    elif first_failure == "safety_review":
        reasons = failed.get("failed_reasons") or []
        if reasons:
            lines.append(f"safety reasons: {reasons}")
    elif first_failure == "language_review":
        flagged = failed.get("flagged_terms") or []
        if flagged:
            lines.append(f"flagged terms: {flagged}")
    return "\n".join(lines)


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


# Re-export TypedDict types for backward import compatibility.
__all__ = [
    "PublishGateAgent",
    "FactCheckResult",
    "SafetyReviewResult",
    "LanguageReviewResult",
    "ParityReviewResult",
    "SourceReviewResult",
    "NilRedactionResult",
    "VisualReviewResult",
    "PublishAudit",
]
