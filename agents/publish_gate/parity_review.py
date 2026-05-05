"""Sub-stage 3: Parity Review.

Pass-through of the Equity Editor's earlier decision on the draft. NO LLM
call — the agent is just reading the Equity Editor's `equity_review.cleared`
flag.

CONSTITUTION Law 3 (Parity is a System Property): the Equity Editor's veto
is structural. The Publish Gate's role here is to confirm that the Equity
Editor signed off — never to override the Equity Editor.

Per BUILD_SPEC §8.5 the StoryDraft carries:
    equity_review: {
      cleared: bool
      feedback: str
      revisions_count: int
    }

A draft missing `equity_review` (or with `cleared=False`) fails this stage.
"""

from __future__ import annotations

import logging

from agents.publish_gate.types import ParityReviewResult

logger = logging.getLogger(__name__)


class ParityReviewSubstage:
    """Sub-stage 3 — confirm Equity Editor cleared the draft.

    Synchronous, no LLM, no I/O. Cheap to run.
    """

    def __init__(self) -> None:  # noqa: D401 — empty by design
        pass

    def review(self, *, story_draft: dict) -> ParityReviewResult:
        """Read the draft's `equity_review.cleared` field.

        Pass-through if True; fail with `equity_feedback` if False or missing.

        Args:
            story_draft: the StoryDraft dict per BUILD_SPEC §8.5.

        Returns:
            `ParityReviewResult` with `equity_cleared`, `equity_feedback`,
            and `passed`.
        """
        equity_review = (story_draft or {}).get("equity_review") or {}
        if not isinstance(equity_review, dict):
            logger.warning(
                "parity_review: equity_review is not a dict (got %s); failing closed",
                type(equity_review).__name__,
            )
            equity_review = {}

        equity_cleared = bool(equity_review.get("cleared", False))
        feedback_raw = equity_review.get("feedback", "") or ""
        equity_feedback = (
            str(feedback_raw)
            if not isinstance(feedback_raw, str)
            else feedback_raw
        )

        # Default-when-missing audit text: a draft without an equity_review
        # block at all should fail with a clear reason rather than empty
        # feedback. The Equity Editor is mandatory upstream of Publish Gate.
        if not equity_cleared and not equity_feedback:
            equity_feedback = "equity_review missing or not cleared"

        return ParityReviewResult(
            equity_cleared=equity_cleared,
            equity_feedback=equity_feedback,
            passed=equity_cleared,
        )
