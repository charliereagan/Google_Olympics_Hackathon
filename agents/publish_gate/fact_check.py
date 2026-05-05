"""Sub-stage 1: Fact Check.

Every factual claim in a Storyteller draft must trace to a source in the
Investigation Packet. Hard rules per PROJECT_BRIEF §6 (auto-DQ data):
  - finish times = REMOVED.
  - specific scoring results = REMOVED.
  - any numeric statistic must trace to a packet source — else REMOVED.

Implementation:
  1. Deterministic regex pre-pass — finish times + scoring results never
     reach the model. They are removed up front and counted as
     `claims_removed`.
  2. One Pro-tier (`gemini-3.1-pro-preview`) structured-extraction call
     against `client.aio.models.generate_content` (mirrors the Investigator's
     `grounded_search` private call shape). The prompt asks the model to
     enumerate claims, classify each as `removed | softened | cleared`, and
     return JSON.
  3. On a Runner exception we retry once with truncated context per
     BUILD_SPEC §17.1; on second failure we return passed=False with
     `error='fact_check_unavailable'` so the orchestrator surfaces it.

Cost ceiling axis = `gemini_pro` (BUILD_SPEC §15.3).

Voice text lives in `/prompts/publish_gate.md`. The Pro model called here
is doing structured extraction, not voice work — its response is parsed
JSON, never displayed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.cost.counters import CostCeilingExceeded
from agents.publish_gate.types import FactCheckResult
from agents.wire.emit import WireProxyNotReadyError

logger = logging.getLogger(__name__)

_COST_AXIS = "gemini_pro"

# Regex pre-pass: finish times + scoring results.
#
# Finish-time pattern. Catches:
#   "9.79 seconds", "9.79s", "9.79 sec", "1:23.45", "01:23.456".
# All are auto-DQ per PROJECT_BRIEF §6.
_FINISH_TIME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b\d{1,2}\.\d{2,3}\s*(?:seconds?|secs?|s)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}:\d{2}(?:\.\d{1,3})?\b",
    ),
    re.compile(
        r"\b\d{1,2}\.\d{2,3}\s*(?:minutes?|mins?|m)\b",
        re.IGNORECASE,
    ),
]

# Scoring-result pattern. Catches:
#   "16.733 in vault", "16.733 points", "9.5 score".
# Conservative: requires either an explicit "points/score" word or a
# decimal-3+ number adjacent to a sport-discipline word (vault, beam,
# routine, dive, etc.). Avoids false-positives on year ranges.
_SCORING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b\d{1,3}\.\d{2,3}\s*(?:points?|score|pts)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,3}\.\d{2,3}\s+in\s+(?:vault|beam|floor|bars|routine|dive|all-around)\b",
        re.IGNORECASE,
    ),
]


def _split_sentences(text: str) -> list[str]:
    """Lightweight sentence splitter. Keeps punctuation on the trailing token."""
    if not text:
        return []
    # Split on . ! ? followed by whitespace + capital. Keeps the
    # delimiter; strips leading/trailing whitespace per sentence.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"])", text)
    return [p.strip() for p in parts if p and p.strip()]


def _regex_prepass(text: str) -> tuple[list[str], str]:
    """Find finish-time / scoring sentences. Return (removed_claims, cleaned_text).

    Removed sentences are excluded from the cleaned_text we hand to the
    model — the model can't 'softens' a claim that's already auto-DQ.
    """
    sentences = _split_sentences(text)
    removed: list[str] = []
    kept: list[str] = []
    all_patterns = _FINISH_TIME_PATTERNS + _SCORING_PATTERNS
    for s in sentences:
        flagged = False
        for pat in all_patterns:
            if pat.search(s):
                flagged = True
                break
        if flagged:
            removed.append(s)
        else:
            kept.append(s)
    return removed, " ".join(kept)


# JSON shape the model is asked to return.
_PROMPT_TEMPLATE = """\
You are the Fact Check sub-stage of The Storyteller's Room Publish Gate.

Your job: read the draft body and the Investigation Packet's sources /
historical_context / trend_signals. Identify every factual claim in the
draft. For each claim, classify it as:
  - "removed": the claim has no support in the packet's sources, OR the
    claim contains a numeric statistic with no source. (FINISH-TIME and
    SCORING-RESULT claims have already been stripped by a deterministic
    pre-pass — do NOT re-flag those.)
  - "softened": the claim is partially supported but the phrasing is
    too strong (e.g., predictive without conditional softening).
  - "cleared": the claim is supported by the packet.

Output ONLY a single JSON object with this shape, no prose, no
markdown fences:

{{
  "claims_checked": int,
  "claims_removed": int,
  "claims_softened": int,
  "removed_claims": [string],
  "softened_claims": [string]
}}

## Draft body
{body}

## Investigation Packet snapshot
sources:
{sources_json}

historical_context:
{historical_context_json}

trend_signals:
{trend_signals_json}
"""


def _build_prompt(*, body: str, packet: dict) -> str:
    sources = packet.get("sources") or []
    historical_context = packet.get("historical_context") or {}
    trend_signals = packet.get("trend_signals") or {}
    return _PROMPT_TEMPLATE.format(
        body=body or "",
        sources_json=json.dumps(sources[:8], ensure_ascii=False, default=str),
        historical_context_json=json.dumps(
            historical_context, ensure_ascii=False, default=str
        ),
        trend_signals_json=json.dumps(
            trend_signals, ensure_ascii=False, default=str
        ),
    )


def _truncate_for_retry(prompt: str, max_chars: int = 4500) -> str:
    """Shorter context for the second attempt (BUILD_SPEC §17.1)."""
    if len(prompt) <= max_chars:
        return prompt
    head = prompt[: max_chars // 2]
    tail = prompt[-max_chars // 2 :]
    return f"{head}\n... [context truncated for retry] ...\n{tail}"


def _parse_model_json(text: str) -> dict | None:
    """Extract the first JSON object from `text`. Tolerant of stray prose
    or markdown fences the model may emit."""
    if not text:
        return None
    # Strip common markdown fences.
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the first fence line; keep until the next fence.
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    # Try a direct parse first.
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fall back: find the first {...} block.
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


class FactCheckSubstage:
    """Sub-stage 1 — Fact Check.

    Pro-tier model call (`gemini-3.1-pro-preview` by default; same as the
    Editor / Investigator / Storyteller). We use `google-genai`'s
    `client.aio.models.generate_content` directly — same shape the
    Investigator's `grounded_search` private call uses. ADK's Runner is
    overkill here because this is a one-shot structured-extraction call,
    not a multi-tool decision loop.
    """

    def __init__(
        self,
        *,
        model_id: str = "gemini-3.1-pro-preview",
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
    ) -> FactCheckResult:
        """Run the Fact Check sub-stage.

        Args:
            story_draft: the StoryDraft dict (per BUILD_SPEC §8.5).
            investigation_packet: the InvestigationPacket dict (per
                BUILD_SPEC §8.4) supplying sources / historical_context /
                trend_signals.
            wire: optional WireEmitter — used only on retry-fallback
                thinking events.
            investigation_id: tag for any wire emits.

        Returns:
            `FactCheckResult` with claims_checked / claims_removed /
            claims_softened / removed_claims / softened_claims / passed.

        Failure modes (BUILD_SPEC §17.1):
          - Cost ceiling → return passed=False with
            `error='cost_ceiling'`.
          - Runner exception twice (after truncated retry) → emit a
            thinking event ("hold — fact check stalled, retrying with
            shorter context"), return passed=False with
            `error='fact_check_unavailable'`.
        """
        body = (story_draft or {}).get("body") or ""
        # Deterministic pre-pass. Always runs; cheap.
        regex_removed, cleaned_body = _regex_prepass(body)

        # If the cleaned body is empty (entire draft was finish-times /
        # scoring), short-circuit before calling the model.
        if not cleaned_body.strip():
            removed = list(regex_removed)
            return FactCheckResult(
                claims_checked=len(removed),
                claims_removed=len(removed),
                claims_softened=0,
                removed_claims=removed,
                softened_claims=[],
                passed=False,
            )

        # Cost ceiling pre-check.
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="publish_gate"
                )
            except CostCeilingExceeded:
                logger.info(
                    "fact_check: cost ceiling reached; returning passed=False"
                )
                return FactCheckResult(
                    claims_checked=len(regex_removed),
                    claims_removed=len(regex_removed),
                    claims_softened=0,
                    removed_claims=list(regex_removed),
                    softened_claims=[],
                    passed=False,
                    error="cost_ceiling",
                )

        prompt = _build_prompt(body=cleaned_body, packet=investigation_packet or {})

        attempts = [prompt, _truncate_for_retry(prompt)]
        last_exc: Exception | None = None
        model_result: dict | None = None
        usage_in = 0
        usage_out = 0

        for i, attempt_prompt in enumerate(attempts, start=1):
            try:
                model_result, usage_in, usage_out = await self._call_model(
                    attempt_prompt
                )
                break
            except Exception as e:
                last_exc = e
                logger.warning(
                    "fact_check: model attempt %d/%d failed: %s",
                    i, len(attempts), e,
                )
                if i == 1 and wire is not None:
                    # Visible recovery (BUILD_SPEC §17.1) — retry with
                    # shorter context.
                    await self._safe_emit_thinking(
                        wire,
                        "*hold — fact check stalled, retrying with shorter context*",
                        investigation_id=investigation_id,
                    )

        if model_result is None:
            # Both attempts failed.
            logger.error(
                "fact_check: model unavailable after retries: %s", last_exc
            )
            return FactCheckResult(
                claims_checked=len(regex_removed),
                claims_removed=len(regex_removed),
                claims_softened=0,
                removed_claims=list(regex_removed),
                softened_claims=[],
                passed=False,
                error="fact_check_unavailable",
            )

        # Increment cost counter on success.
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
                logger.exception("fact_check: cost_counter.increment failed")

        # Merge regex results with model results. The regex sweep already
        # counted finish-time / scoring removals; the model has been told
        # not to re-flag those.
        model_removed = _str_list(model_result.get("removed_claims"))
        model_softened = _str_list(model_result.get("softened_claims"))
        all_removed = list(regex_removed) + model_removed
        # claims_checked: the model's count plus the regex pre-pass count.
        # If the model returned something nonsensical (negative / non-int),
        # fall back to len(model_removed) + len(model_softened).
        try:
            model_checked = int(model_result.get("claims_checked", 0))
            if model_checked < 0:
                raise ValueError
        except (TypeError, ValueError):
            model_checked = len(model_removed) + len(model_softened)
        claims_checked = model_checked + len(regex_removed)
        claims_removed = len(all_removed)
        claims_softened = len(model_softened)

        passed = claims_removed == 0

        return FactCheckResult(
            claims_checked=claims_checked,
            claims_removed=claims_removed,
            claims_softened=claims_softened,
            removed_claims=all_removed,
            softened_claims=model_softened,
            passed=passed,
        )

    # -- Internals ----------------------------------------------------------

    async def _call_model(self, prompt: str) -> tuple[dict, int, int]:
        """One `client.aio.models.generate_content` call.

        Returns (parsed_json, input_tokens, output_tokens). Raises on any
        failure path so the caller can retry.
        """
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
                f"fact_check: model returned non-JSON response (head={text[:120]!r})"
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
        """Emit a Wire thinking event without raising into the orchestrator."""
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
                "fact_check: wire proxy not ready; cannot emit thinking event"
            )
        except Exception:
            logger.exception(
                "fact_check: failed to emit thinking event"
            )


def _str_list(value: Any) -> list[str]:
    """Coerce a model field to a list[str], dropping non-strings."""
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, (str, int, float))]
