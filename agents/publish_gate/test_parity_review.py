"""Unit tests for `ParityReviewSubstage`.

Pure pass-through of `story_draft.equity_review.cleared`. No LLM, no I/O.
"""

from __future__ import annotations

from agents.publish_gate.parity_review import ParityReviewSubstage


def test_parity_review_passes_when_equity_cleared():
    """`equity_review.cleared=True` → passed=True with feedback echoed."""
    sub = ParityReviewSubstage()
    draft = {
        "equity_review": {
            "cleared": True,
            "feedback": "draft 1 cleared on first review",
            "revisions_count": 0,
        },
    }
    result = sub.review(story_draft=draft)
    assert result["passed"] is True
    assert result["equity_cleared"] is True
    assert "cleared on first review" in result["equity_feedback"]


def test_parity_review_fails_when_equity_returned():
    """`equity_review.cleared=False` → passed=False, feedback surfaced."""
    sub = ParityReviewSubstage()
    draft = {
        "equity_review": {
            "cleared": False,
            "feedback": "Paralympic depth thin; please surface program data",
            "revisions_count": 1,
        },
    }
    result = sub.review(story_draft=draft)
    assert result["passed"] is False
    assert result["equity_cleared"] is False
    assert "Paralympic depth thin" in result["equity_feedback"]
