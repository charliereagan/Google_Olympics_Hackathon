"""Tests for VPS-DEC-053: predictive frames are FORBIDDEN, not "soften to."

The Day-6 Tucson failure: predictive frames ("could lead to ...", "may
indicate ...", "could lead to a framework ...") leaked through Publish
Gate's language_review and into the published prose. The audit reported
`softened=N` but the predictive frame still made it to the reader because
the softening only converted "will" → "could" / "may" without changing
the semantics.

PROJECT_BRIEF §11 lists predictive constructions under FORBIDDEN, not
"soften to." The right behavior is: language_review FLAGS predictive
frames → orchestrator RETURNS the draft to the Storyteller for revision.

Four tests:

  1. A draft containing "could lead to ..." returns from language_review
     with passed=False and the verbatim construction in
     predictive_violations.
  2. A clean Mount-Pleasant-style draft (no predictive frames) passes.
  3. Encouraged temporal phrasing ("first / next / newest Olympian"
     applied to a place) still passes — the encouraged-overlap filter
     keeps these out of the predictive scan.
  4. The orchestrator increments
     audit.language_violations_returned_to_storyteller >= 1 when a
     predictive frame causes a return.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.publish_gate.language_review import LanguageReviewSubstage
from agents.publish_gate.orchestrator import PublishGateAgent


def _draft(**fields) -> dict:
    return dict(fields)


# --- Test 1 — predictive frame returns for revision -------------------------


def test_predictive_frame_returns_for_revision():
    """A draft body containing 'could lead to increased participation'
    returns passed=False with the verbatim offending construction."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "The county's program could lead to increased participation "
                "in the regional pipeline over the next decade."
            ),
        ),
    )
    assert result["passed"] is False
    violations = result["predictive_violations"]
    # Substring match on 'could lead to' — the verbatim capture also
    # carries the trailing context up to the next sentence terminator.
    assert any("could lead to" in v.lower() for v in violations), violations
    # Per-violation reason surfaces for the Storyteller's revision feedback.
    reasons = result["predictive_reasons"]
    assert len(reasons) == len(violations) >= 1
    assert all("predictive" in r.lower() for r in reasons)


# --- Test 2 — clean draft passes --------------------------------------------


def test_clean_draft_passes_language_review():
    """A Mount-Pleasant-style draft with no predictive frames passes."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            headline="A small Iowa county keeps producing Olympians",
            dek="The pattern took shape from a single high-school program three decades ago.",
            body=(
                "The county sits at the foot of the regional pipeline. "
                "Local press has covered the program for decades. "
                "The high school's track-and-field facility has hosted "
                "regional meets since the 1960s."
            ),
            hometown_panel="The county seat sits at 8,500 residents on the eastern edge of Iowa.",
            historical_echo="This echoes a 1960s post-war pattern of regional pipelines.",
        ),
    )
    assert result["passed"] is True
    assert result["restricted_terms_flagged"] == 0
    assert result["flagged_terms"] == []
    assert result["predictive_violations"] == []
    assert result["predictive_reasons"] == []


# --- Test 3 — encouraged temporal phrasing still passes ---------------------


def test_encouraged_temporal_phrasing_still_passes():
    """'first Olympian', 'next Olympian', 'newest Olympian', etc. — the
    encouraged constructions per PROJECT_BRIEF §10 — must continue to
    pass. The predictive-frame scan must NOT catch them."""
    sub = LanguageReviewSubstage()
    result = sub.review(
        story_draft=_draft(
            body=(
                "The town's first Olympian came home in 1972. "
                "The newest Olympian came home in the Tokyo cycle. "
                "The newest Paralympian arrived in 2024."
            ),
        ),
    )
    assert result["passed"] is True
    assert result["restricted_terms_flagged"] == 0
    assert result["predictive_violations"] == []
    # Sanity: 'first / newest' overlap filter still suppressed any
    # forbidden-list hit on the literal words 'olympian' / 'paralympian'.
    assert "olympian" not in result["flagged_terms"]
    assert "paralympian" not in result["flagged_terms"]


# --- Test 4 — orchestrator increments returned-counter ----------------------


# Reuse the orchestrator-test infrastructure shape (collection stub etc.).


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _SeededColl:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = list(docs or [])
        self.added: list[dict] = []

    def add(self, doc: dict) -> tuple:
        self.added.append(dict(doc))
        return (mock.Mock(), mock.Mock(id=f"fake-{len(self.added)}"))

    def stream(self):
        return [_SeededDoc(d) for d in self._docs]

    def document(self, doc_id: str) -> "_SeededDocRef":
        for d in self._docs:
            if d.get("id") == doc_id:
                return _SeededDocRef(d, self)
        return _SeededDocRef(None, self)


class _SeededDoc:
    def __init__(self, data: dict) -> None:
        self._data = dict(data)
        self.id = data.get("id", "fake-id")
        self.exists = True

    def to_dict(self) -> dict:
        return dict(self._data)


class _SeededDocRef:
    def __init__(self, data: dict | None, parent: _SeededColl) -> None:
        self._data = data
        self._parent = parent

    def get(self):
        if self._data is None:
            return _MissingSnapshot()
        return _SeededDoc(self._data)

    def update(self, payload: dict) -> None:
        if self._data is not None:
            self._data.update(payload)


class _MissingSnapshot:
    exists = False

    def to_dict(self) -> dict:
        return {}


class _FakeFirestore:
    def __init__(
        self,
        *,
        story_drafts: list[dict] | None = None,
        investigation_packets: list[dict] | None = None,
    ) -> None:
        self.collections: dict[str, _SeededColl] = {
            "story_drafts": _SeededColl(story_drafts or []),
            "investigation_packets": _SeededColl(investigation_packets or []),
            "publish_audits": _SeededColl(),
            "killed_drafts": _SeededColl(),
        }

    def collection(self, name: str) -> _SeededColl:
        return self.collections.setdefault(name, _SeededColl())


class _FakeNilLayer:
    is_loaded = True

    def scan_wire(self, text: str, *, surface: str = "wire", context: Any | None = None):
        from agents.wire.types import NilLog, WireScanResult

        return WireScanResult(
            decision="pass",
            redacted_message=text,
            log=NilLog(direct_matches_redacted=0, aggregations_applied=0),
        )


def _passing_async_substage(**extras) -> Any:
    class _Stub:
        async def review(self, **kwargs):
            return {"passed": True, **extras}

    return _Stub()


def _passing_sync_substage(**extras) -> Any:
    class _SyncStub:
        def review(self, **kwargs):
            return {"passed": True, **extras}

    return _SyncStub()


@pytest.mark.asyncio
async def test_orchestrator_increments_returned_counter():
    """Drive a draft with a predictive frame through the orchestrator;
    assert audit['language_violations_returned_to_storyteller'] >= 1."""
    draft = {
        "id": "draft-pred-001",
        "investigation_packet_id": "pkt-001",
        "story_unit_id": "place_test",
        "headline": "A small county keeps producing Olympians",
        "dek": "The pattern is decades old.",
        # The body contains a forbidden predictive frame — the real
        # LanguageReviewSubstage must catch it and return passed=False.
        "body": (
            "The county sits at the foot of the regional pipeline. "
            "The program could lead to increased global competitive "
            "platforms over the next two decades."
        ),
        "hometown_panel": "The county seat sits at 8,500 residents.",
        "historical_echo": "This echoes a 1960s post-war pattern.",
        "equity_review": {
            "cleared": True,
            "feedback": "ok",
            "revisions_count": 0,
        },
    }
    packet = {
        "id": "pkt-001",
        "story_unit_id": "place_test",
        "sources": [
            {"url": "https://a.example.com/1", "outlet": "A"},
            {"url": "https://b.example.com/2", "outlet": "B"},
        ],
    }
    fs = _FakeFirestore(story_drafts=[draft], investigation_packets=[packet])

    pg = PublishGateAgent(
        prompt="(test prompt)",
        wire=_FakeWire(),
        firestore=fs,
        nil_layer=_FakeNilLayer(),
        # All upstream sub-stages pass; only the REAL language_review
        # enforces VPS-DEC-053.
        fact_check=_passing_async_substage(
            claims_checked=10, claims_removed=0, claims_softened=0,
            removed_claims=[], softened_claims=[],
        ),
        source_review=_passing_sync_substage(
            source_count=4, outlets=["A", "B"]
        ),
        parity_review=_passing_sync_substage(
            equity_cleared=True, equity_feedback="ok"
        ),
        safety_review=_passing_async_substage(
            invented_quotes=0, private_info_flags=0,
            failed_reasons=[], fallback_used=False,
        ),
        # Real language_review — the unit under test.
        language_review=LanguageReviewSubstage(),
        visual_review=_passing_sync_substage(regenerations=0, stub=True),
        max_revisions=3,
    )

    audit = await pg.review(story_draft_id="draft-pred-001")

    # The orchestrator returned the draft for revision...
    assert audit["final_decision"] == "returned"
    assert "language_review" in audit["revisions_requested"]
    # ...AND the new audit field surfaces the language_review return.
    assert audit["language_violations_returned_to_storyteller"] >= 1
    # The language_review sub-stage's typed result carries the verbatim
    # violation for the Storyteller's revision feedback.
    lang = audit["sub_stages"]["language_review"]
    assert lang["passed"] is False
    assert any(
        "could lead to" in v.lower() for v in lang["predictive_violations"]
    )
