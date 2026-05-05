"""Unit tests for `LanguageReviewSubstage`.

Pure-Python regex sub-stage. Tests cover all four pattern classes:
  - FORBIDDEN_WORDS (PROJECT_BRIEF §10).
  - CONTEXT_AWARE_FORBIDDEN ('fighter' / 'despite' only in disability
    context).
  - PREDICTIVE_PATTERNS (PROJECT_BRIEF §11) — counted, not blocked.
  - ENCOURAGED_TEMPORAL_PATTERNS (PROJECT_BRIEF §10) — must NOT flag
    'Olympian' inside 'first Olympian'.
"""

from __future__ import annotations

from agents.publish_gate.language_review import LanguageReviewSubstage


def _draft(**fields) -> dict:
    """Tiny helper: build a draft dict with arbitrary surface fields."""
    return dict(fields)


def test_language_review_flags_inspirational_word():
    """The forbidden word 'inspirational' is flagged regardless of casing."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body="The county's program is INSPIRATIONAL in its reach.",
        ),
    )
    assert result["passed"] is False
    assert "inspirational" in result["flagged_terms"]


def test_language_review_flags_former_olympian():
    """'former olympian' is flagged regardless of casing."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "A former Olympian visits the program once a year, "
                "the local paper reports."
            ),
        ),
    )
    assert result["passed"] is False
    assert "former olympian" in result["flagged_terms"]


def test_language_review_flags_predictive_phrases():
    """Predictive phrasing is counted, not blocked. The result still passes
    when no forbidden terms are present, but the count is surfaced."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "This means the program will result in more representation. "
                "The data guarantees the trend continues."
            ),
        ),
    )
    # No forbidden terms → passed=True.
    assert result["passed"] is True
    # But three predictive constructions counted.
    assert result["predictive_phrases_softened"] >= 3


def test_language_review_passes_clean_draft():
    """A draft using only encouraged + neutral language passes."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "The county sits at the foot of the regional pipeline. "
                "Local press has covered the program for decades."
            ),
            headline="A small Iowa county keeps producing Olympians",
        ),
    )
    assert result["passed"] is True
    assert result["restricted_terms_flagged"] == 0
    assert result["flagged_terms"] == []


def test_language_review_does_not_flag_first_olympian_temporal_pattern():
    """'first Olympian' (encouraged temporal phrasing) must NOT be flagged
    even though 'Olympian' appears in the forbidden 'former Olympian'
    construction."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "The town's first Olympian came in 1964. "
                "The next, sixteen years later. "
                "The newest Paralympian arrived in 2024."
            ),
        ),
    )
    assert result["passed"] is True
    # No forbidden terms; encouraged constructions skipped.
    assert "olympian" not in result["flagged_terms"]
    assert "paralympian" not in result["flagged_terms"]


def test_language_review_does_not_flag_fighter_in_non_disability_context():
    """'fighter' alone (no disability-context anchor within ~30 chars)
    must NOT be flagged — it's a CONTEXT_AWARE term, not unconditional."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            # 'fighter' here is a sport metaphor in a non-disability
            # paragraph; the closest disability-context anchor is far
            # away (more than 30 chars).
            body=(
                "The county's wrestling program produced a regional title "
                "fighter for three consecutive seasons in the 1990s."
            ),
        ),
    )
    assert result["passed"] is True
    assert "fighter" not in result["flagged_terms"]


def test_language_review_flags_fighter_in_disability_context():
    """'fighter' WITHIN ~30 chars of a disability-context word IS flagged."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body="The Paralympic athlete is a fighter in the program.",
        ),
    )
    assert result["passed"] is False
    assert "fighter" in result["flagged_terms"]
