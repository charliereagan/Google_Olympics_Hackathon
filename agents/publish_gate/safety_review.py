"""Sub-stage 5: Safety Review.

Two checks, one Flash-Lite call:
  1. Invented quotes — any direct quote in the body that is NOT in
     `investigation_packet.sources`?
  2. Private info — references to medical conditions, private records,
     non-public personal details?

Cost ceiling axis = `gemini_flash_lite` (BUILD_SPEC §3 + §15.3).

Failure modes per BUILD_SPEC §17.1:
  - Flash-Lite call fails twice → emit a Wire thinking event ("safety
    review fell back to deterministic check"), run a regex-only
    fallback (we can't verify quote sources without an LLM, so we
    return passed=True with a `failed_reasons` flag explaining the
    degradation).

Voice text lives in `/prompts/publish_gate.md`. The Flash-Lite model
returns parsed JSON, never displayed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.cost.counters import CostCeilingExceeded
from agents.publish_gate.types import SafetyReviewResult
from agents.wire.emit import WireProxyNotReadyError

logger = logging.getLogger(__name__)


_COST_AXIS = "gemini_flash_lite"

# Heuristic patterns for the deterministic fallback.
_QUOTE_PATTERN = re.compile(r"[“”\"](.+?)[“”\"]", re.DOTALL)

_PRIVATE_INFO_HINTS: list[re.Pattern[str]] = [
    re.compile(r"\bdiagnosed with\b", re.IGNORECASE),
    re.compile(r"\bmedical (?:record|history|condition)\b", re.IGNORECASE),
    re.compile(r"\bprivate (?:record|file|note)\b", re.IGNORECASE),
    re.compile(r"\bprescribed\b", re.IGNORECASE),
    re.compile(r"\bhospitali[sz]ed\b", re.IGNORECASE),
]


_PROMPT_TEMPLATE = """\
You are the Safety Review sub-stage of The Storyteller's Room Publish Gate.

Run two checks against the draft body and surfaces, using the
Investigation Packet's sources as the ground truth for whether a quote
is "real".

Check 1 — Invented quotes:
  Find every direct quote (text inside double quotes) in the body. For
  each, verify the quote text appears in one of the packet sources
  (`source.relevance_note`, `source.text` if present, or the URL's
  outlet name + obvious topic). If you cannot find the quote attributed
  to any source, count it as INVENTED.

Check 2 — Private info / medical:
  Flag any reference to medical conditions, private medical records,
  non-public personal details (e.g., "diagnosed with X", "her medical
  records show", "his personal therapist said").

Output ONLY a single JSON object with this shape, no prose, no fences:

{{
  "invented_quotes": int,
  "private_info_flags": int,
  "failed_reasons": [string]
}}

`failed_reasons` lists short human-readable reason strings (one per
flag) that the audit log will surface.

## Draft body
{body}

## Other surfaces
headline: {headline}
dek: {dek}
hometown_panel: {hometown_panel}
historical_echo: {historical_echo}

## Investigation Packet sources
{sources_json}
"""


def _build_prompt(*, story_draft: dict, packet: dict) -> str:
    sources = packet.get("sources") or []
    return _PROMPT_TEMPLATE.format(
        body=story_draft.get("body") or "",
        headline=story_draft.get("headline") or "",
        dek=story_draft.get("dek") or "",
        hometown_panel=story_draft.get("hometown_panel") or "",
        historical_echo=story_draft.get("historical_echo") or "",
        sources_json=json.dumps(sources[:8], ensure_ascii=False, default=str),
    )


def _parse_model_json(text: str) -> dict | None:
    """Extract the first JSON object from `text`. Same shape as fact_check's."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        return None
    return None


def _deterministic_fallback(story_draft: dict) -> SafetyReviewResult:
    """No-LLM regex fallback. Counts heuristic private-info hits.

    Cannot verify quote-source attribution without the model. We flag
    presence of quotes but always count them as 0 invented (we don't
    know). The orchestrator surfaces `fallback_used=True` so the audit
    is honest about the degraded check.
    """
    body = story_draft.get("body") or ""
    private_hits = 0
    for pat in _PRIVATE_INFO_HINTS:
        private_hits += len(pat.findall(body))

    failed_reasons: list[str] = []
    if private_hits:
        failed_reasons.append(
            f"deterministic fallback flagged {private_hits} possible "
            "private-info reference(s)"
        )
    failed_reasons.append(
        "safety review fell back to deterministic check (LLM unavailable); "
        "invented-quote detection skipped"
    )

    return SafetyReviewResult(
        invented_quotes=0,
        private_info_flags=private_hits,
        failed_reasons=failed_reasons,
        fallback_used=True,
        passed=private_hits == 0,
    )


class SafetyReviewSubstage:
    """Sub-stage 5 — Safety Review (LLM-Flash-Lite, async, cost-counted)."""

    def __init__(
        self,
        *,
        model_id: str = "gemini-3.1-flash-lite-preview",
        cost_counter: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._cost_counter = cost_counter

    async def review(
        self,
        *,
        story_draft: dict,
        investigation_packet: dict,
        wire: Any | None = None,
        investigation_id: str = "ambient",
    ) -> SafetyReviewResult:
        """Run the Safety Review sub-stage.

        On Flash-Lite failure (after one retry), emits a Wire thinking
        event explaining the degradation and falls back to a regex-only
        check (BUILD_SPEC §17.1).
        """
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="publish_gate"
                )
            except CostCeilingExceeded:
                logger.info(
                    "safety_review: cost ceiling reached; using deterministic fallback"
                )
                result = _deterministic_fallback(story_draft)
                # Annotate so the orchestrator can surface the reason.
                result.setdefault("failed_reasons", []).insert(
                    0, "cost_ceiling: flash_lite cap hit"
                )
                return result

        prompt = _build_prompt(
            story_draft=story_draft or {},
            packet=investigation_packet or {},
        )

        # Two attempts, no truncation needed (the prompt is small).
        last_exc: Exception | None = None
        model_result: dict | None = None
        usage_in = 0
        usage_out = 0
        for i in range(2):
            try:
                model_result, usage_in, usage_out = await self._call_model(prompt)
                break
            except Exception as e:
                last_exc = e
                logger.warning(
                    "safety_review: model attempt %d/2 failed: %s", i + 1, e,
                )

        if model_result is None:
            # Both attempts failed — fall back.
            logger.error(
                "safety_review: flash_lite unavailable after retries: %s", last_exc
            )
            if wire is not None:
                await self._safe_emit_thinking(
                    wire,
                    "*safety review fell back to deterministic check*",
                    investigation_id=investigation_id,
                )
            return _deterministic_fallback(story_draft)

        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="publish_gate",
                    sub_agent=None,
                    axis=_COST_AXIS,
                    model=self._model_id,
                    calls=1,
                    input_tokens=int(usage_in or 0),
                    output_tokens=int(usage_out or 0),
                )
            except Exception:
                logger.exception(
                    "safety_review: cost_counter.increment failed"
                )

        # Coerce model fields defensively.
        try:
            invented = int(model_result.get("invented_quotes", 0))
            if invented < 0:
                invented = 0
        except (TypeError, ValueError):
            invented = 0
        try:
            private_flags = int(model_result.get("private_info_flags", 0))
            if private_flags < 0:
                private_flags = 0
        except (TypeError, ValueError):
            private_flags = 0
        failed_reasons = model_result.get("failed_reasons") or []
        if not isinstance(failed_reasons, list):
            failed_reasons = []
        failed_reasons = [str(r) for r in failed_reasons if isinstance(r, (str, int, float))]

        passed = invented == 0 and private_flags == 0

        return SafetyReviewResult(
            invented_quotes=invented,
            private_info_flags=private_flags,
            failed_reasons=failed_reasons,
            fallback_used=False,
            passed=passed,
        )

    # -- Internals ----------------------------------------------------------

    async def _call_model(self, prompt: str) -> tuple[dict, int, int]:
        """One Flash-Lite generate_content call."""
        try:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError("google-genai not installed") from e

        client = genai.Client()
        config = genai_types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        )
        response = await client.aio.models.generate_content(
            model=self._model_id,
            contents=prompt,
            config=config,
        )
        text = getattr(response, "text", "") or ""
        parsed = _parse_model_json(text)
        if parsed is None:
            raise RuntimeError(
                f"safety_review: model returned non-JSON (head={text[:120]!r})"
            )
        usage = getattr(response, "usage_metadata", None)
        in_tokens = (
            int(getattr(usage, "prompt_token_count", 0) or 0)
            if usage is not None
            else 0
        )
        out_tokens = (
            int(getattr(usage, "candidates_token_count", 0) or 0)
            if usage is not None
            else 0
        )
        return parsed, in_tokens, out_tokens

    async def _safe_emit_thinking(
        self,
        wire: Any,
        message: str,
        *,
        investigation_id: str,
    ) -> None:
        """Emit a Wire thinking event without raising."""
        try:
            await wire.emit(
                {
                    "agent": "publish_gate",
                    "message": message,
                    "message_type": "thinking",
                    "mode": "live",
                },
                investigation_id=investigation_id,
            )
        except WireProxyNotReadyError:
            logger.warning(
                "safety_review: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "safety_review: failed to emit thinking event"
            )
