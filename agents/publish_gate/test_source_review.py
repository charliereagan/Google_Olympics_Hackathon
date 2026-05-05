"""Unit tests for `SourceReviewSubstage`.

The sub-stage is pure-deterministic; tests assert pass/fail thresholds
and the alphabetized-outlets contract.
"""

from __future__ import annotations

from agents.publish_gate.source_review import SourceReviewSubstage


def _build_packet(*, sources: list[dict]) -> dict:
    return {"sources": sources}


def test_source_review_passes_with_two_distinct_outlets():
    """>=2 sources AND >=2 distinct outlets → passed=True."""
    sub = SourceReviewSubstage()
    packet = _build_packet(
        sources=[
            {"url": "https://a.example.com/1", "outlet": "Mt Pleasant News"},
            {"url": "https://b.example.com/2", "outlet": "Quad-City Times"},
        ],
    )
    result = sub.review(story_draft={}, investigation_packet=packet)
    assert result["passed"] is True
    assert result["source_count"] == 2
    assert "Mt Pleasant News" in result["outlets"]
    assert "Quad-City Times" in result["outlets"]


def test_source_review_fails_with_only_one_outlet():
    """Two sources but one outlet → fails the distinct-outlet threshold."""
    sub = SourceReviewSubstage()
    packet = _build_packet(
        sources=[
            {"url": "https://a.example.com/1", "outlet": "Mt Pleasant News"},
            {"url": "https://a.example.com/2", "outlet": "Mt Pleasant News"},
        ],
    )
    result = sub.review(story_draft={}, investigation_packet=packet)
    assert result["passed"] is False
    assert result["source_count"] == 2
    assert result["outlets"] == ["Mt Pleasant News"]


def test_source_review_returns_alphabetized_outlets():
    """Distinct outlets must be alphabetized (case-insensitive) for stable
    audit output."""
    sub = SourceReviewSubstage()
    packet = _build_packet(
        sources=[
            {"url": "https://z.example.com/1", "outlet": "Zenith Daily"},
            {"url": "https://b.example.com/2", "outlet": "Birmingham News"},
            {"url": "https://m.example.com/3", "outlet": "Mt Pleasant News"},
        ],
    )
    result = sub.review(story_draft={}, investigation_packet=packet)
    assert result["passed"] is True
    assert result["outlets"] == [
        "Birmingham News",
        "Mt Pleasant News",
        "Zenith Daily",
    ]
