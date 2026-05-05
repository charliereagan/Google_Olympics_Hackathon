"""Unit tests for `FactCheckSubstage`.

Covers the four cases the prompt requires:
  - Regex pre-pass removes finish-time claims (PROJECT_BRIEF §6).
  - Unsupported numeric claims removed by the model.
  - Supported claims pass through.
  - Both Runner attempts raising returns passed=False with
    error='fact_check_unavailable' and emits the BUILD_SPEC §17.1
    thinking event.

The Pro-tier model is mocked at the `_call_model` boundary so unit tests
don't hit live Vertex AI.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.publish_gate.fact_check import FactCheckSubstage


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(
        self,
        event: dict,
        *,
        investigation_id: str | None = None,
    ) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


def _build_substage(
    *,
    cost_counter: Any | None = None,
) -> FactCheckSubstage:
    return FactCheckSubstage(
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
    )


def _packet_with_sources() -> dict:
    return {
        "sources": [
            {
                "url": "https://example.com/iowa-pipeline",
                "outlet": "Mt Pleasant News",
                "relevance_note": "covers the program's history since 1976",
            },
            {
                "url": "https://example.com/county-coverage",
                "outlet": "Quad-City Times",
                "relevance_note": "regional pipeline coverage",
            },
        ],
        "historical_context": {"era": "post-war track-and-field"},
        "trend_signals": {"momentum": "positive"},
    }


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fact_check_removes_finish_time_claims():
    """The regex pre-pass marks finish-time sentences as REMOVED before the
    model runs (PROJECT_BRIEF §6 — auto-DQ data fields)."""
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Athletes from the program have run 9.79 seconds in regional meets. "
            "The pattern took shape from the 1970s onward."
        ),
    }
    sub = _build_substage()

    async def _model_returns_clean(prompt: str):
        # The model should never see the finish-time sentence.
        assert "9.79" not in prompt, "regex pre-pass should strip finish times"
        return (
            {
                "claims_checked": 2,
                "claims_removed": 0,
                "claims_softened": 0,
                "removed_claims": [],
                "softened_claims": [],
            },
            120,
            40,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model_returns_clean):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
        )

    assert result["claims_removed"] == 1
    assert any(
        "9.79" in claim for claim in result["removed_claims"]
    ), f"finish-time claim should be in removed list: {result['removed_claims']!r}"
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_fact_check_removes_unsupported_numeric_claims():
    """The model returns 2 unsupported numeric claims; both surface as
    removed_claims and the sub-stage fails."""
    draft = {
        "body": (
            "The county has produced 17 Olympians since 1976. "
            "The program's facility was rebuilt in 2008."
        ),
    }
    sub = _build_substage()

    async def _model(prompt: str):
        return (
            {
                "claims_checked": 2,
                "claims_removed": 2,
                "claims_softened": 0,
                "removed_claims": [
                    "produced 17 Olympians since 1976",
                    "facility was rebuilt in 2008",
                ],
                "softened_claims": [],
            },
            150,
            55,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
        )

    assert result["claims_removed"] == 2
    assert len(result["removed_claims"]) == 2
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_fact_check_passes_supported_claims():
    """When the model says 0 removed, 0 softened, the sub-stage passes."""
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Local press has covered the program's reach since 1976."
        ),
    }
    sub = _build_substage()

    async def _model(prompt: str):
        return (
            {
                "claims_checked": 2,
                "claims_removed": 0,
                "claims_softened": 0,
                "removed_claims": [],
                "softened_claims": [],
            },
            100,
            30,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
        )

    assert result["passed"] is True
    assert result["claims_removed"] == 0
    assert result["claims_softened"] == 0


@pytest.mark.asyncio
async def test_fact_check_handles_runner_exception():
    """When `_call_model` raises on both attempts, return passed=False with
    error='fact_check_unavailable'. A retry-thinking Wire event is emitted."""
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Local press has covered the program for decades."
        ),
    }
    wire = _FakeWire()
    sub = _build_substage()

    async def _always_raises(prompt: str):
        raise RuntimeError("model timeout")

    with mock.patch.object(sub, "_call_model", side_effect=_always_raises):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
            wire=wire,
            investigation_id="test-fc-001",
        )

    assert result["passed"] is False
    assert result.get("error") == "fact_check_unavailable"
    # Exactly one BUILD_SPEC §17.1 thinking event between attempts.
    retry_events = [
        e for e in wire.emitted
        if "fact check stalled" in e.get("message", "")
    ]
    assert len(retry_events) == 1
    assert retry_events[0]["agent"] == "publish_gate"
    assert retry_events[0]["message_type"] == "thinking"
