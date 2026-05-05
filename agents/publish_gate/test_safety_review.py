"""Unit tests for `SafetyReviewSubstage`.

The Flash-Lite model is mocked at the `_call_model` boundary so unit
tests don't hit live Vertex AI.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.publish_gate.safety_review import SafetyReviewSubstage


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
) -> SafetyReviewSubstage:
    return SafetyReviewSubstage(
        model_id="gemini-3.1-flash-lite-preview",
        cost_counter=cost_counter,
    )


def _packet() -> dict:
    return {
        "sources": [
            {
                "url": "https://example.com/1",
                "outlet": "Mt Pleasant News",
                "relevance_note": (
                    "the program superintendent told the local paper: "
                    "\"the pipeline runs through the school\""
                ),
            },
        ],
    }


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safety_review_flags_invented_quotes():
    """The model returns invented_quotes >= 1 → passed=False."""
    sub = _build_substage()
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "\"This is what we live for,\" said the program director."
        ),
    }

    async def _model(prompt: str):
        return (
            {
                "invented_quotes": 1,
                "private_info_flags": 0,
                "failed_reasons": ["quote not found in any source"],
            },
            80,
            30,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet(),
        )

    assert result["invented_quotes"] == 1
    assert result["passed"] is False
    assert result["fallback_used"] is False


@pytest.mark.asyncio
async def test_safety_review_flags_private_medical_info():
    """The model returns private_info_flags >= 1 → passed=False."""
    sub = _build_substage()
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Records show one athlete was diagnosed with a rare condition."
        ),
    }

    async def _model(prompt: str):
        return (
            {
                "invented_quotes": 0,
                "private_info_flags": 1,
                "failed_reasons": ["medical condition reference"],
            },
            80,
            30,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet(),
        )

    assert result["private_info_flags"] == 1
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_safety_review_passes_clean_draft():
    """The model returns 0 / 0 → passed=True."""
    sub = _build_substage()
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Local press has covered the program for decades."
        ),
    }

    async def _model(prompt: str):
        return (
            {
                "invented_quotes": 0,
                "private_info_flags": 0,
                "failed_reasons": [],
            },
            80,
            20,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet(),
        )

    assert result["passed"] is True
    assert result["fallback_used"] is False


@pytest.mark.asyncio
async def test_safety_review_falls_back_when_flash_lite_fails_twice():
    """Both Flash-Lite attempts raise → fallback path; thinking event emitted."""
    sub = _build_substage()
    wire = _FakeWire()
    draft = {
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "Records show one athlete was diagnosed with a rare condition."
        ),
    }

    async def _always_raises(prompt: str):
        raise RuntimeError("flash_lite timeout")

    with mock.patch.object(sub, "_call_model", side_effect=_always_raises):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet(),
            wire=wire,
            investigation_id="test-sr-001",
        )

    assert result["fallback_used"] is True
    # The deterministic fallback should still detect the medical hint.
    assert result["private_info_flags"] >= 1
    # And emit the BUILD_SPEC §17.1 visible-recovery thinking event.
    fallback_events = [
        e for e in wire.emitted
        if "fell back to deterministic check" in e.get("message", "")
    ]
    assert len(fallback_events) == 1
    assert fallback_events[0]["agent"] == "publish_gate"
