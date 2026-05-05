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
        visualizer: Any | None = None,
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
        # Visualizer is optional in tests. When None and Visual Review is
        # asked to inspect images, the orchestrator skips the generation
        # step and passes empty assets to Visual Review (which fails
        # closed with reason='no_assets'). In production runtime, a real
        # Visualizer is always injected.
        self._visualizer = visualizer
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
            sub_stages, first_failure, visualizer_assets = await self._run_substages(
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
            asset_urls = _asset_urls_from_visualizer(visualizer_assets)
            await self._mark_publish_gate_decision(
                story_draft_id, "cleared",
                asset_urls=asset_urls,
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
    ) -> tuple[dict, str | None, dict | None]:
        """Run all 7 sub-stages in order.

        Returns ``(sub_stages_dict, first_failure_name, visualizer_assets)``.

        - first_failure_name is the canonical sub-stage key that failed
          first (e.g., 'fact_check'); None if every sub-stage passed.
        - visualizer_assets is the dict from `Visualizer.generate_assets`,
          or None if the orchestrator was constructed without a Visualizer
          (test-stub mode). The orchestrator persists the asset URLs onto
          the cleared draft so the Broadcast renderer can find them.
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

        # Sub-stage 4: NIL Redaction Review.
        # Day-7: prefer the full Layer's async `scan_broadcast` so the
        # broadcast surface runs the FULL pipeline (direct match +
        # disambiguation + near-id Flash-Lite + small-aggregate). The
        # Day-2 stub doesn't expose `scan_broadcast`; we fall back to its
        # sync `scan_wire` for backward compatibility.
        nil = await self._run_one_substage(
            name="nil_redaction_review",
            invoke=lambda: _run_nil_redaction_async(self._nil_layer, story_draft),
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

        # --- Pre sub-stage 7: Visualizer (HOE-DEC-020) ------------------
        # The Visualizer is a tool the Publish Gate calls (CONSTITUTION
        # Rule 2; BUILD_SPEC §5.7.1). It runs AFTER NIL clearance and
        # BEFORE Visual Review. The orchestrator owns the regeneration
        # loop: up to 3 regenerations on Visual Review failure, then a
        # curated Day-9 fallback.
        visualizer_assets, visual = await self._generate_and_review_visuals(
            story_draft=story_draft,
            investigation_packet=investigation_packet,
            story_unit_id=story_unit_id,
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

        # Persist the asset URLs back onto the draft so the Broadcast
        # renderer can find them. Only on a passing Visual Review (or
        # when the orchestrator handed the draft a fallback hero).
        if visualizer_assets is not None:
            self._stash_assets_on_draft(story_draft, visualizer_assets)

        return sub_stages, first_failure, visualizer_assets

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

    # -- Visualizer + Visual Review regeneration loop -----------------------

    async def _generate_and_review_visuals(
        self,
        *,
        story_draft: dict,
        investigation_packet: dict,
        story_unit_id: str | None,
        investigation_id: str,
    ) -> tuple[dict | None, dict]:
        """Generate hero + utility images, then run Visual Review.

        On failure, regenerate with progressively stricter prompts (HOE-
        DEC-020 + BUILD_SPEC §17.2). Up to 3 regenerations; on the 4th
        failure, fall back to the curated Day-9 hero. Returns
        ``(assets_dict_or_None, visual_review_result_dict)``.

        ``assets_dict_or_None`` is None when the Visualizer is absent
        (test stubs); the orchestrator then has no URLs to stash.
        """
        if self._visualizer is None:
            # Test path / Day-6 stub mode: skip generation, hand
            # the Visual Review sub-stage empty assets so its existing
            # contract (Day-6 stub auto-passes) still holds.
            try:
                # Day-6 stubs in tests use `review(story_draft=...)`;
                # the Day-7 sub-stage uses `review(visualizer_assets=...)`.
                # Try the Day-7 signature first, fall back to Day-6.
                try:
                    result = self._visual_review.review(
                        story_draft=story_draft,
                        visualizer_assets={},
                        investigation_id=investigation_id,
                    )
                except TypeError:
                    result = self._visual_review.review(
                        story_draft=story_draft
                    )
                if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                    result = await result
                return None, dict(result) if result is not None else {"passed": False}
            except Exception:
                logger.exception(
                    "publish_gate.visual_review (no visualizer): review raised"
                )
                return None, {"passed": False, "error": "visual_review_exception"}

        max_regen = int(getattr(self._visualizer, "max_regenerations", 3))
        regenerations = 0
        assets: dict = {}
        last_review: dict = {}

        while True:
            # Stricter prompt level escalates with each regeneration: 0
            # for the initial attempt, then 1 / 2 / 3.
            stricter_level = regenerations
            try:
                assets = await self._visualizer.generate_assets(
                    story_draft=story_draft,
                    investigation_packet=investigation_packet,
                    wire=self._wire,
                    investigation_id=investigation_id,
                    stricter_level=stricter_level,
                )
            except Exception as e:
                logger.warning(
                    "publish_gate.visualizer.generate_assets failed "
                    "(stricter=%d): %s",
                    stricter_level, e,
                )
                # Treat generation failure as a Visual Review fail with
                # the same regeneration budget — the orchestrator's job
                # is to either retry or fall back, regardless of which
                # side blew up.
                last_review = {
                    "passed": False,
                    "regenerations": regenerations,
                    "failed_reasons": [f"generation_error:{type(e).__name__}"],
                    "images_checked": [],
                }
                if regenerations >= max_regen:
                    break
                regenerations += 1
                continue

            # Run Visual Review against the freshly-generated assets.
            try:
                review_call = self._visual_review.review(
                    story_draft=story_draft,
                    visualizer_assets=assets,
                    wire=self._wire,
                    investigation_id=investigation_id,
                    regenerations=regenerations,
                )
                if asyncio.iscoroutine(review_call) or hasattr(
                    review_call, "__await__"
                ):
                    review_result = await review_call
                else:
                    review_result = review_call
            except Exception as e:
                logger.warning(
                    "publish_gate.visual_review.review raised: %s", e
                )
                review_result = {
                    "passed": False,
                    "regenerations": regenerations,
                    "failed_reasons": [f"review_error:{type(e).__name__}"],
                    "images_checked": [],
                }

            last_review = (
                dict(review_result) if review_result is not None else {"passed": False}
            )
            last_review.setdefault("regenerations", regenerations)

            if last_review.get("passed"):
                return assets, last_review

            if regenerations >= max_regen:
                break
            regenerations += 1

        # Exhausted the regeneration budget: fall back to the curated
        # Day-9 hero (HOE-DEC-020). The fallback hero replaces ONLY the
        # hero URL — utility panels carry their last-rendered values.
        logger.warning(
            "publish_gate: visual review exhausted %d regenerations; "
            "falling back to curated hero",
            regenerations,
        )
        try:
            fallback_url = await self._visualizer.fallback_hero(
                story_unit_id=story_unit_id or "unknown"
            )
            assets = dict(assets or {})
            assets["hero_url"] = fallback_url
            assets["fallback_used"] = True
        except Exception:
            logger.exception(
                "publish_gate: visualizer.fallback_hero raised"
            )

        # Emit a milestone-style thinking event so the audit drawer
        # shows the working-room recovery (BUILD_SPEC §17.2).
        await self._safe_emit_thinking(
            "visual review used pre-cached fallback hero "
            f"after {regenerations} regenerations",
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )

        # Final result reflects the regeneration count + the fallback
        # path, but stays passed=False so the orchestrator surfaces the
        # exhaustion in the audit. The fallback URL is what the renderer
        # will use; the audit captures that we hit the budget.
        last_review["regenerations"] = regenerations
        last_review["fallback_used"] = True
        return assets, last_review

    def _stash_assets_on_draft(self, story_draft: dict, assets: dict) -> None:
        """Mutate the story_draft in place with the asset URLs.

        The actual Firestore write happens in `_mark_publish_gate_decision`
        — which already reads the draft, applies a payload patch, and
        writes back. We piggy-back on that by setting fields on the
        in-memory draft dict; the cleared-path write picks them up.
        """
        if not isinstance(story_draft, dict) or not isinstance(assets, dict):
            return
        for src_key, draft_key in (
            ("hero_url", "hero_image_url"),
            ("hometown_panel_url", "hometown_panel_url"),
            ("echo_panel_url", "echo_panel_url"),
        ):
            url = assets.get(src_key)
            if url:
                story_draft[draft_key] = url
        if assets.get("fallback_used"):
            story_draft["hero_image_fallback_used"] = True

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
        asset_urls: dict | None = None,
    ) -> None:
        """Mutate the draft's publish_gate_decision (and revisions count).

        On a 'cleared' decision, also persists the Visualizer's asset
        URLs (`hero_image_url`, `hometown_panel_url`, `echo_panel_url`)
        if provided — these power the Broadcast page's hero rendering.
        """
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
        # On cleared, persist any asset URLs so the Broadcast renderer
        # can find them. The orchestrator passes `asset_urls=...` only
        # when generating visuals succeeded.
        if decision == "cleared" and asset_urls:
            for k in ("hero_image_url", "hometown_panel_url", "echo_panel_url"):
                v = asset_urls.get(k)
                if v:
                    updated[k] = v
            if asset_urls.get("hero_image_fallback_used"):
                updated["hero_image_fallback_used"] = True

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
                if decision == "cleared" and asset_urls:
                    for k in (
                        "hero_image_url",
                        "hometown_panel_url",
                        "echo_panel_url",
                    ):
                        v = asset_urls.get(k)
                        if v:
                            payload[k] = v
                    if asset_urls.get("hero_image_fallback_used"):
                        payload["hero_image_fallback_used"] = True
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


async def _run_nil_redaction_async(
    nil_layer: Any, story_draft: dict
) -> NilRedactionResult:
    """Run the NIL Redaction Layer against the draft body for sub-stage 4.

    Day-7: prefers the full Layer's async `scan_broadcast` so the broadcast
    surface runs the FULL pipeline (direct match + disambiguation +
    near-id Flash-Lite + small-aggregate). The Day-2 stub doesn't expose
    `scan_broadcast`; we fall back to its sync `scan_wire` for backward
    compatibility.

    Returns a NilRedactionResult dict — the audit-level count, NOT the
    rewritten body. (The Storyteller already passed the draft through
    equity; Wire-level enforcement runs on every emit. This sub-stage's
    role is the AUDIT count + return-to-Storyteller decision.)
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
        scan_broadcast = getattr(nil_layer, "scan_broadcast", None)
        if scan_broadcast is not None:
            # Full Day-7 Layer — run the broadcast pipeline.
            scan = await scan_broadcast(body, context=None)
        else:
            # Day-2 stub fallback — direct-match only via scan_wire.
            scan = nil_layer.scan_wire(body, surface="wire", context=None)
    except Exception:
        logger.exception("nil_redaction: scan raised")
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

    log = scan.log
    direct_matches = int(getattr(log, "direct_matches_redacted", 0) or 0)
    aggregations = int(getattr(log, "aggregations_applied", 0) or 0)
    near_ids = int(getattr(log, "near_identifications", 0) or 0)
    small_aggs = int(getattr(log, "small_aggregates", 0) or 0)
    redacted = direct_matches
    # decision='return' on broadcast surface means a near-id was detected
    # AND the Layer wants the draft returned to the Storyteller.
    returned_to_storyteller = 1 if scan.decision == "return" else 0

    # Pass criterion: scan decision is 'pass'. Aggregate / redact / return
    # all surface as `passed=False` so the orchestrator returns the draft
    # for revision (per CONSTITUTION §7 — the audit log shows the work,
    # the Storyteller revises, and the system re-runs).
    passed = scan.decision == "pass"

    return NilRedactionResult(
        individual_refs_reviewed=direct_matches + aggregations + near_ids + small_aggs,
        direct_matches=direct_matches,
        near_identifications=near_ids,
        small_aggregates=small_aggs,
        aggregated=aggregations,
        redacted=redacted,
        returned_to_storyteller=returned_to_storyteller,
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
        if result.get("stub"):
            reason = "stub"
        elif result.get("passed"):
            reason = "ok"
        else:
            reasons = result.get("failed_reasons") or []
            reason = ",".join(str(r) for r in reasons[:3]) if reasons else "fail"
        return {
            "n": int(result.get("regenerations") or 0),
            "reason": reason,
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
        if result.get("passed"):
            return f"visual review: {regen} regenerations, cleared."
        if result.get("fallback_used"):
            return (
                f"visual review: {regen} regenerations exhausted; "
                "fallback hero applied."
            )
        reasons = result.get("failed_reasons") or []
        if reasons:
            head = ", ".join(str(r) for r in reasons[:3])
            return f"visual review: failed ({head})."
        return "visual review: failed."
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


def _asset_urls_from_visualizer(assets: dict | None) -> dict:
    """Translate a Visualizer.generate_assets dict into draft-doc fields.

    The Visualizer's keys are pipeline-internal (`hero_url`, etc.); the
    Firestore draft schema uses `hero_image_url` / `hometown_panel_url` /
    `echo_panel_url`. This helper does the rename + a copy of the
    fallback flag.
    """
    if not isinstance(assets, dict):
        return {}
    out: dict = {}
    for src, dst in (
        ("hero_url", "hero_image_url"),
        ("hometown_panel_url", "hometown_panel_url"),
        ("echo_panel_url", "echo_panel_url"),
    ):
        v = assets.get(src)
        if v:
            out[dst] = v
    if assets.get("fallback_used"):
        out["hero_image_fallback_used"] = True
    return out


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
