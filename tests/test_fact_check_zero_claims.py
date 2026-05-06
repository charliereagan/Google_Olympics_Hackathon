"""Regression tests for the FactCheck 0-claims pass-through (Day-6 fix).

Symptom this guards against: when the structured-extraction model returns
an empty `claims_checked` list against a narrative-prose draft (no
enumerable factual claims), the Publish Gate orchestrator was routing the
draft back to the Storyteller for revision. The Storyteller would
re-write, the model would again extract 0 claims, and the loop ran until
`max_revisions=3` killed the draft. Net effect: 0 publish_audits despite
valid drafts.

The fix in `agents/publish_gate/fact_check.py` short-circuits when the
extraction returns nothing: 0 claims to verify == nothing to fail ==
PASS. The complementary path — N claims with all failing verification —
must still surface as `passed=False` so the orchestrator routes the draft
to revision normally (BUILD_SPEC §5.7 step 6).

Both tests mock the Pro-tier model at the `_call_model` boundary so the
unit test does not hit live Vertex AI.
"""

from __future__ import annotations

from unittest import mock

import pytest

from agents.publish_gate.fact_check import FactCheckSubstage


def _packet_with_sources() -> dict:
    return {
        "sources": [
            {
                "url": "https://example.com/regional-pipeline",
                "outlet": "Regional Press",
                "relevance_note": "covers the program's history",
            },
            {
                "url": "https://example.com/county-coverage",
                "outlet": "County Times",
                "relevance_note": "regional pipeline coverage",
            },
        ],
        "historical_context": {"era": "post-war track-and-field"},
        "trend_signals": {"momentum": "positive"},
    }


def _build_substage() -> FactCheckSubstage:
    return FactCheckSubstage(
        model_id="gemini-3.1-pro-preview",
        cost_counter=None,
    )


# -- Test 1 — 0 extracted claims pass through trivially -----------------------


@pytest.mark.asyncio
async def test_fact_check_zero_claims_passes_through():
    """Model extracts no claims from a narrative-prose draft.

    Expected: FactCheck returns passed=True with all counts at 0. The
    orchestrator's revision loop must NOT see a `passed=False` result for
    this case, otherwise narrative drafts churn until they hit
    `max_revisions=3` and die.
    """
    draft = {
        "body": (
            "The county sits at the foot of a regional pipeline. "
            "Local press has covered the program's reach for decades."
        ),
    }
    sub = _build_substage()

    async def _model_returns_no_claims(prompt: str):
        # Pro structured-extraction returns an empty list — the draft is
        # narrative prose, not enumerable factual claims.
        return (
            {
                "claims_checked": 0,
                "claims_removed": 0,
                "claims_softened": 0,
                "removed_claims": [],
                "softened_claims": [],
            },
            85,
            20,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model_returns_no_claims):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
        )

    # The pass-through guarantees: passed=True, all counts==0, no error.
    assert result["passed"] is True, (
        "0 extracted claims must pass FactCheck trivially; "
        "otherwise narrative-prose drafts loop forever in revision."
    )
    assert result["claims_checked"] == 0
    assert result["claims_removed"] == 0
    assert result["claims_softened"] == 0
    assert result["removed_claims"] == []
    assert result["softened_claims"] == []
    assert "error" not in result, (
        f"unexpected error field on 0-claims pass-through: {result.get('error')!r}"
    )


# -- Test 2 — N claims with all failing still routes to revision --------------


@pytest.mark.asyncio
async def test_fact_check_all_claims_fail_returns_for_revision():
    """N claims extracted, every one classified `removed` by the model.

    Expected: FactCheck reports claims_checked=N, claims_removed=N,
    passed=False — orchestrator routes to revision per BUILD_SPEC §5.7
    step 6. The 0-claims pass-through must NOT swallow this case.
    """
    draft = {
        "body": (
            "The county has produced 17 Olympians since 1976. "
            "The program's facility was rebuilt in 2008. "
            "The region trains 200 athletes per year."
        ),
    }
    sub = _build_substage()

    async def _model_fails_every_claim(prompt: str):
        return (
            {
                "claims_checked": 3,
                "claims_removed": 3,
                "claims_softened": 0,
                "removed_claims": [
                    "produced 17 Olympians since 1976",
                    "facility was rebuilt in 2008",
                    "trains 200 athletes per year",
                ],
                "softened_claims": [],
            },
            160,
            70,
        )

    with mock.patch.object(sub, "_call_model", side_effect=_model_fails_every_claim):
        result = await sub.review(
            story_draft=draft,
            investigation_packet=_packet_with_sources(),
        )

    # All claims failed -> passed=False, route for revision.
    assert result["passed"] is False, (
        "N claims with all failing must surface passed=False so the "
        "orchestrator routes the draft to revision."
    )
    assert result["claims_checked"] == 3
    assert result["claims_removed"] == 3
    assert result["claims_softened"] == 0
    assert len(result["removed_claims"]) == 3
