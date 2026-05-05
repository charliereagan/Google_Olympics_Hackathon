"""Unit tests for the Day-7 `VisualReviewSubstage`.

The Pro-vision call is mocked at the `_call_model_vision` boundary so
unit tests don't hit live Vertex AI. The patterns mirror
`agents/publish_gate/test_safety_review.py`.
"""

from __future__ import annotations

from unittest import mock

import pytest

from agents.publish_gate.visual_review import VisualReviewSubstage


# --- Fakes -------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(
        self, event: dict, *, investigation_id: str | None = None
    ) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


def _ok_assets() -> dict:
    """Three asset URLs as returned by `Visualizer.generate_assets`."""
    return {
        "hero_url": "gs://hero-bucket/sd-001/hero.png",
        "hometown_panel_url": "gs://hero-bucket/sd-001/hometown.png",
        "echo_panel_url": "gs://hero-bucket/sd-001/echo.png",
    }


def _build_substage() -> VisualReviewSubstage:
    return VisualReviewSubstage(
        model_id="gemini-3.1-pro-preview",
        cost_counter=None,
    )


# --- Tests -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visual_review_passes_clean_image():
    """All three checks return is_photoreal=False, has_likeness=False, no marks → passed=True."""
    sub = _build_substage()

    async def _check(image_url: str):
        return {
            "is_photoreal": False,
            "has_likeness": False,
            "detected_marks": [],
            "confidence_0_to_1": 0.95,
        }

    with mock.patch.object(sub, "check_image", side_effect=_check):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
        )

    assert result["passed"] is True
    assert result["failed_reasons"] == []
    assert len(result["images_checked"]) == 3
    assert result["regenerations"] == 0


@pytest.mark.asyncio
async def test_visual_review_fails_on_photorealistic_image():
    """Any image with is_photoreal=True → passed=False; reason flagged."""
    sub = _build_substage()

    async def _check(image_url: str):
        # Hero is photoreal; others are clean.
        if image_url.endswith("/hero.png"):
            return {
                "is_photoreal": True,
                "has_likeness": False,
                "detected_marks": [],
                "confidence_0_to_1": 0.9,
            }
        return {
            "is_photoreal": False,
            "has_likeness": False,
            "detected_marks": [],
            "confidence_0_to_1": 0.95,
        }

    with mock.patch.object(sub, "check_image", side_effect=_check):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
        )

    assert result["passed"] is False
    assert any("photorealistic" in r for r in result["failed_reasons"])


@pytest.mark.asyncio
async def test_visual_review_fails_on_likeness_detection():
    """has_likeness=True on any image → passed=False; reason 'identifiable_likeness'."""
    sub = _build_substage()

    async def _check(image_url: str):
        if image_url.endswith("/hometown.png"):
            return {
                "is_photoreal": False,
                "has_likeness": True,
                "detected_marks": [],
                "confidence_0_to_1": 0.85,
            }
        return {
            "is_photoreal": False,
            "has_likeness": False,
            "detected_marks": [],
            "confidence_0_to_1": 0.9,
        }

    with mock.patch.object(sub, "check_image", side_effect=_check):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
        )

    assert result["passed"] is False
    assert any(
        "identifiable_likeness" in r for r in result["failed_reasons"]
    )
    # The failure reason names which image (the hometown panel).
    assert any(
        "hometown_panel" in r for r in result["failed_reasons"]
    )


@pytest.mark.asyncio
async def test_visual_review_fails_on_protected_mark():
    """Olympic rings detected → passed=False; reason flagged with mark name."""
    sub = _build_substage()

    async def _check(image_url: str):
        if image_url.endswith("/hero.png"):
            return {
                "is_photoreal": False,
                "has_likeness": False,
                "detected_marks": ["olympic_rings"],
                "confidence_0_to_1": 0.95,
            }
        return {
            "is_photoreal": False,
            "has_likeness": False,
            "detected_marks": [],
            "confidence_0_to_1": 0.9,
        }

    with mock.patch.object(sub, "check_image", side_effect=_check):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
        )

    assert result["passed"] is False
    assert any(
        "protected_mark_olympic_rings" in r
        for r in result["failed_reasons"]
    )


@pytest.mark.asyncio
async def test_visual_review_handles_vision_call_failure_fail_closed():
    """Both vision attempts raise → passed=False with reason='vision_call_unavailable'.

    The Wire receives a thinking event explaining the fail-closed
    behavior. This is the BUILD_SPEC §17.1 visible-recovery contract.
    """
    sub = _build_substage()
    wire = _FakeWire()

    async def _always_raises(image_url: str):
        # check_image is the public method; raising here surfaces the
        # _VisionCallFailed sentinel internally.
        from agents.publish_gate.visual_review import _VisionCallFailed
        raise _VisionCallFailed(
            f"vision call unavailable for {image_url}"
        )

    with mock.patch.object(sub, "check_image", side_effect=_always_raises):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
            wire=wire,
            investigation_id="test-vr-001",
        )

    assert result["passed"] is False
    assert "vision_call_unavailable" in result["failed_reasons"]
    # Visible-recovery thinking event was emitted.
    fail_closed = [
        e for e in wire.emitted
        if "fail-closed" in e.get("message", "")
    ]
    assert len(fail_closed) == 1
    assert fail_closed[0]["agent"] == "publish_gate"


@pytest.mark.asyncio
async def test_visual_review_no_assets_fails_closed_with_no_assets_reason():
    """When `visualizer_assets` is empty, the sub-stage fails closed without calling vision."""
    sub = _build_substage()
    wire = _FakeWire()

    # check_image must NOT be called; assert that.
    with mock.patch.object(sub, "check_image") as ci:
        result = await sub.review(
            visualizer_assets={},
            wire=wire,
            investigation_id="test-vr-002",
        )

    assert ci.call_count == 0
    assert result["passed"] is False
    assert "no_assets" in result["failed_reasons"]


@pytest.mark.asyncio
async def test_visual_review_persists_regenerations_in_result():
    """The `regenerations` count passed in is echoed into the result dict."""
    sub = _build_substage()

    async def _check(image_url: str):
        return {
            "is_photoreal": False,
            "has_likeness": False,
            "detected_marks": [],
            "confidence_0_to_1": 0.9,
        }

    with mock.patch.object(sub, "check_image", side_effect=_check):
        result = await sub.review(
            visualizer_assets=_ok_assets(),
            regenerations=2,
        )

    assert result["regenerations"] == 2
    assert result["passed"] is True
