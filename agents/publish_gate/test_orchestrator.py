"""Unit tests for `PublishGateAgent` orchestrator.

Each sub-stage is mocked so the orchestrator's decision logic is the
unit under test:
  - All seven sub-stages run in order.
  - First sub-stage failure with revisions_count < max → 'returned'.
  - Sub-stage failure with revisions_count >= max → 'killed'.
  - All-pass → 'cleared' + audit doc written to /publish_audits/.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.publish_gate.orchestrator import PublishGateAgent


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


class _SeededColl:
    """Minimal Firestore collection stub.

    `add` records writes; `stream` yields seeded docs; `document(id)`
    returns a doc-ref shim that supports `.get()` and `.update()`.
    """

    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = list(docs or [])
        self.added: list[dict] = []
        self.updated: list[dict] = []

    def add(self, doc: dict) -> tuple:
        self.added.append(dict(doc))
        return (mock.Mock(), mock.Mock(id=f"fake-{len(self.added)}"))

    def stream(self):
        return [_SeededDoc(d) for d in self._docs]

    def document(self, doc_id: str) -> "_SeededDocRef":
        # Match docs by `id` field.
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
        if self._data is None:
            return
        self._data.update(payload)
        self._parent.updated.append({"id": self._data.get("id"), **payload})


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
    """Stub NIL Layer: passes by default; the orchestrator just reads
    `is_loaded` and calls `scan_wire`."""

    is_loaded = True

    def __init__(self, *, decision: str = "pass", direct_matches: int = 0) -> None:
        self._decision = decision
        self._direct_matches = direct_matches

    def scan_wire(
        self, text: str, *, surface: str = "wire", context: Any | None = None
    ):
        from agents.wire.types import NilLog, WireScanResult

        return WireScanResult(
            decision=self._decision,
            redacted_message=text,
            log=NilLog(
                direct_matches_redacted=self._direct_matches,
                aggregations_applied=0,
            ),
        )


def _make_substage(passed: bool, **extras) -> Any:
    """Stub sub-stage object whose `review(...)` returns a typed-shaped dict."""

    class _Stub:
        def __init__(self, p: bool, e: dict) -> None:
            self._passed = p
            self._extras = e
            self.calls: list[dict] = []

        async def review(self, **kwargs):
            self.calls.append(kwargs)
            return {"passed": self._passed, **self._extras}

    return _Stub(passed, extras)


def _make_sync_substage(passed: bool, **extras) -> Any:
    """Stub sub-stage with a SYNC `review(...)` (parity / source / language)."""

    class _SyncStub:
        def __init__(self, p: bool, e: dict) -> None:
            self._passed = p
            self._extras = e
            self.calls: list[dict] = []

        def review(self, **kwargs):
            self.calls.append(kwargs)
            return {"passed": self._passed, **self._extras}

    return _SyncStub(passed, extras)


def _build_pg(
    *,
    fact_check_passed: bool = True,
    source_passed: bool = True,
    parity_passed: bool = True,
    safety_passed: bool = True,
    language_passed: bool = True,
    visual_passed: bool = True,
    nil_decision: str = "pass",
    firestore: Any | None = None,
    wire: Any | None = None,
    max_revisions: int = 3,
) -> PublishGateAgent:
    return PublishGateAgent(
        prompt="(test prompt)",
        wire=wire or _FakeWire(),
        firestore=firestore or _FakeFirestore(),
        nil_layer=_FakeNilLayer(decision=nil_decision),
        fact_check=_make_substage(
            fact_check_passed,
            claims_checked=10,
            claims_removed=0 if fact_check_passed else 2,
            claims_softened=0,
            removed_claims=[] if fact_check_passed else ["unsupported claim"],
            softened_claims=[],
        ),
        source_review=_make_sync_substage(
            source_passed,
            source_count=4 if source_passed else 1,
            outlets=["A", "B"] if source_passed else ["A"],
        ),
        parity_review=_make_sync_substage(
            parity_passed,
            equity_cleared=parity_passed,
            equity_feedback="ok" if parity_passed else "Paralympic depth thin",
        ),
        safety_review=_make_substage(
            safety_passed,
            invented_quotes=0 if safety_passed else 1,
            private_info_flags=0,
            failed_reasons=[] if safety_passed else ["invented quote"],
            fallback_used=False,
        ),
        language_review=_make_sync_substage(
            language_passed,
            restricted_terms_flagged=0 if language_passed else 2,
            flagged_terms=[] if language_passed else ["inspirational", "hero"],
            predictive_phrases_softened=0,
        ),
        visual_review=_make_sync_substage(
            visual_passed,
            regenerations=0,
            stub=True,
        ),
        max_revisions=max_revisions,
    )


# -- Tests --------------------------------------------------------------------


def _seed_draft(*, draft_id: str = "draft-001", revisions_count: int = 0) -> dict:
    return {
        "id": draft_id,
        "investigation_packet_id": "pkt-001",
        "story_unit_id": "us-ia-mt-pleasant",
        "headline": "A small Iowa county keeps producing Olympians",
        "dek": "The pattern took shape from a single program.",
        "body": "The county sits at the foot of the regional pipeline. " * 6,
        "hometown_panel": "The town's first Olympian came in 1976.",
        "historical_echo": "The pattern echoes the 1960s post-war track-and-field era.",
        "place_name": "Mt Pleasant, Iowa",
        "era_reference": "1960s post-war track-and-field",
        "equity_review": {
            "cleared": True,
            "feedback": "ok",
            "revisions_count": revisions_count,
        },
    }


def _seed_packet() -> dict:
    return {
        "id": "pkt-001",
        "story_unit_id": "us-ia-mt-pleasant",
        "sources": [
            {"url": "https://a.example.com/1", "outlet": "A"},
            {"url": "https://b.example.com/2", "outlet": "B"},
        ],
    }


@pytest.mark.asyncio
async def test_review_runs_all_substages_in_order():
    """All seven sub-stages must be invoked, each exactly once, in the
    BUILD_SPEC §5.7 order. The orchestrator records the audit doc when
    cleared."""
    fs = _FakeFirestore(
        story_drafts=[_seed_draft()],
        investigation_packets=[_seed_packet()],
    )
    pg = _build_pg(firestore=fs)
    audit = await pg.review(story_draft_id="draft-001")

    # Every sub-stage saw exactly one call.
    assert len(pg._fact_check.calls) == 1
    assert len(pg._source_review.calls) == 1
    assert len(pg._parity_review.calls) == 1
    assert len(pg._safety_review.calls) == 1
    assert len(pg._language_review.calls) == 1
    assert len(pg._visual_review.calls) == 1

    # And the audit dict carries every sub_stage key in the right order.
    assert list(audit["sub_stages"].keys()) == [
        "fact_check",
        "source_review",
        "parity_review",
        "nil_redaction_review",
        "safety_review",
        "language_review",
        "visual_review",
    ]
    assert audit["final_decision"] == "cleared"


@pytest.mark.asyncio
async def test_review_returns_draft_on_substage_failure_below_max_revisions():
    """First sub-stage failure with revisions_count<max → 'returned'."""
    fs = _FakeFirestore(
        story_drafts=[_seed_draft(revisions_count=1)],
        investigation_packets=[_seed_packet()],
    )
    pg = _build_pg(firestore=fs, fact_check_passed=False, max_revisions=3)
    audit = await pg.review(story_draft_id="draft-001")

    assert audit["final_decision"] == "returned"
    assert "fact_check" in audit["revisions_requested"]
    # The draft was mutated to publish_gate_decision='returned'.
    drafts_coll = fs.collections["story_drafts"]
    draft = drafts_coll._docs[0]
    assert draft["publish_gate_decision"] == "returned"
    # And revisions_count was incremented by the orchestrator.
    assert draft["equity_review"]["revisions_count"] == 2


@pytest.mark.asyncio
async def test_review_kills_story_on_max_revisions_reached():
    """First sub-stage failure with revisions_count>=max → 'killed'."""
    fs = _FakeFirestore(
        story_drafts=[_seed_draft(revisions_count=3)],
        investigation_packets=[_seed_packet()],
    )
    pg = _build_pg(firestore=fs, language_passed=False, max_revisions=3)
    audit = await pg.review(story_draft_id="draft-001")

    assert audit["final_decision"] == "killed"
    assert audit["kill_reason"].endswith("_unresolvable")
    # killed draft was copied to /killed_drafts/.
    killed = fs.collections["killed_drafts"]
    assert len(killed.added) == 1
    assert killed.added[0]["kill_reason"].endswith("_unresolvable")


@pytest.mark.asyncio
async def test_review_clears_when_all_substages_pass():
    """All sub-stages pass → 'cleared' + Wire milestone emitted."""
    fs = _FakeFirestore(
        story_drafts=[_seed_draft()],
        investigation_packets=[_seed_packet()],
    )
    wire = _FakeWire()
    pg = _build_pg(firestore=fs, wire=wire)
    audit = await pg.review(story_draft_id="draft-001")

    assert audit["final_decision"] == "cleared"
    # A milestone Wire event was emitted.
    milestones = [
        e for e in wire.emitted if e.get("message_type") == "milestone"
    ]
    assert len(milestones) == 1
    assert milestones[0]["agent"] == "publish_gate"
    # Draft mutated to publish_gate_decision='cleared'.
    drafts_coll = fs.collections["story_drafts"]
    assert drafts_coll._docs[0]["publish_gate_decision"] == "cleared"


@pytest.mark.asyncio
async def test_review_writes_publish_audit_to_firestore_on_clear():
    """When cleared, a PublishAudit doc is added to /publish_audits/."""
    fs = _FakeFirestore(
        story_drafts=[_seed_draft()],
        investigation_packets=[_seed_packet()],
    )
    pg = _build_pg(firestore=fs)
    audit = await pg.review(story_draft_id="draft-001")

    assert audit["final_decision"] == "cleared"
    audits_coll = fs.collections["publish_audits"]
    assert len(audits_coll.added) == 1
    written = audits_coll.added[0]
    assert written["story_id"] == "draft-001"
    assert written["final_decision"] == "cleared"
    # All 7 sub-stage keys are present in the persisted doc.
    assert set(written["sub_stages"].keys()) == {
        "fact_check",
        "source_review",
        "parity_review",
        "nil_redaction_review",
        "safety_review",
        "language_review",
        "visual_review",
    }
