"""Sub-stage 7: Visual Review (Day-6 stub).

Day-7 ships the real Visualizer integration plus Nano Banana Pro hero
generation and the photorealism / likeness / protected-mark checks
(BUILD_SPEC §5.7.1, §7.4). For Day-6 we ship an auto-pass stub so the
orchestrator's seven-sub-stage pipeline is end-to-end testable.
"""

from __future__ import annotations

from agents.publish_gate.types import VisualReviewResult


class VisualReviewSubstage:
    """Day-6 stub — auto-passes.

    Public API matches the eventual Day-7 surface so the orchestrator
    code never changes.
    """

    def __init__(self) -> None:  # noqa: D401 — empty by design
        pass

    def review(self, *, story_draft: dict) -> VisualReviewResult:  # noqa: ARG002
        """Always returns passed=True with a `stub` flag for audit honesty."""
        return VisualReviewResult(
            regenerations=0,
            passed=True,
            stub=True,
        )
