"""Unit tests for `agents/equity_editor/tools.py`.

Five required cases (per HoE spec):
  1. read_published_feed aggregates parity counts across published events.
  2. intervene_feed_drift writes to Firestore + emits Wire intervention.
  3. return_draft increments revisions_count + sets cleared=False + feedback.
  4. block_draft sets publish_gate_decision='killed' + writes /killed_drafts/.
  5. clear_draft emits a Wire milestone event.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.equity_editor.tools import build_equity_editor_tools


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _FakeColl:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = docs or []
        self.added: list[dict] = []

    def where(self, *args, **kwargs) -> "_FakeColl":
        return self

    def order_by(self, *args, **kwargs) -> "_FakeColl":
        return self

    def limit(self, n: int) -> "_FakeColl":
        return self

    def stream(self):
        return [_FakeDoc(d) for d in self._docs]

    def add(self, doc: dict) -> tuple:
        self.added.append(dict(doc))
        return (mock.Mock(), mock.Mock(id=f"fs-{len(self.added)}"))


class _FakeDoc:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.id = data.get("id", "fake-id")
        self.exists = True

    def to_dict(self) -> dict:
        return dict(self._data)


class _FakeFirestore:
    def __init__(
        self,
        *,
        wire_events: list[dict] | None = None,
        story_drafts: list[dict] | None = None,
        equity_interventions: list[dict] | None = None,
        killed_drafts: list[dict] | None = None,
    ) -> None:
        self.collections: dict[str, _FakeColl] = {
            "wire_events": _FakeColl(wire_events or []),
            "story_drafts": _FakeColl(story_drafts or []),
            "equity_interventions": _FakeColl(equity_interventions or []),
            "killed_drafts": _FakeColl(killed_drafts or []),
        }

    def collection(self, name: str) -> _FakeColl:
        return self.collections.setdefault(name, _FakeColl())


# -- Helpers ------------------------------------------------------------------


def _get_tool(tools: list[Any], name: str):
    for t in tools:
        if getattr(t, "__name__", "") == name:
            return t
    raise AssertionError(f"tool {name!r} not bound")


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_published_feed_aggregates_parity_counts():
    """Feed mock returns 5 published events; tool aggregates by story_unit_id."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        wire_events=[
            {
                "story_unit_id": "us-ia-mt-pleasant",
                "story_unit_title": "Mt. Pleasant",
                "mode": "published",
                "olympic_count": 6,
                "paralympic_count": 2,
                "era": "1976-2024",
            },
            {
                "story_unit_id": "us-co-colorado-springs",
                "story_unit_title": "Colorado Springs",
                "mode": "published",
                "olympic_count": 4,
                "paralympic_count": 0,
                "era": "1980-2024",
            },
            {
                "story_unit_id": "us-mn-mpls",
                "story_unit_title": "Minneapolis",
                "mode": "published",
                "olympic_count": 5,
                "paralympic_count": 1,
                "era": "1972-2024",
            },
            {
                "story_unit_id": "us-fl-jax",
                "story_unit_title": "Jacksonville",
                "mode": "published",
                "olympic_count": 3,
                "paralympic_count": 0,
                "era": "1996-2024",
            },
            {
                "story_unit_id": "us-or-portland",
                "story_unit_title": "Portland",
                "mode": "published",
                "olympic_count": 4,
                "paralympic_count": 1,
                "era": "1984-2024",
            },
        ]
    )
    tools = build_equity_editor_tools(wire=wire, firestore=firestore)
    read_published_feed = _get_tool(tools, "read_published_feed")

    out = await read_published_feed(limit=20)

    assert out["places_window"] == 5
    assert out["olympic_count"] == 22  # 6+4+5+3+4
    assert out["paralympic_count"] == 4  # 2+0+1+0+1
    # All 5 places skew Olympic; the 4-place window is olympic_heavy.
    assert out["feed_olympic_heavy"] is True
    assert out["feed_paralympic_heavy"] is False
    assert out["window_threshold"] == 4
    place_ids = {p["story_unit_id"] for p in out["recent_places"]}
    assert "us-ia-mt-pleasant" in place_ids
    assert "us-or-portland" in place_ids


@pytest.mark.asyncio
async def test_intervene_feed_drift_writes_to_firestore_and_emits_wire():
    """Tool persists to /equity_interventions/ and emits intervention Wire event."""
    wire = _FakeWire()
    firestore = _FakeFirestore()
    tools = build_equity_editor_tools(wire=wire, firestore=firestore)
    intervene_feed_drift = _get_tool(tools, "intervene_feed_drift")

    out = await intervene_feed_drift(
        reason="Last 4 places Olympic-heavy",
        suggested_priority_lift_story_unit_id="us-al-birmingham",
    )

    assert out["kind"] == "feed_drift"
    assert out["persisted"] is True
    assert out["suggested_priority_lift_story_unit_id"] == "us-al-birmingham"
    # Firestore write to /equity_interventions/.
    interventions = firestore.collections["equity_interventions"].added
    assert len(interventions) == 1
    persisted = interventions[0]
    assert persisted["kind"] == "feed_drift"
    assert persisted["reason"] == "Last 4 places Olympic-heavy"
    assert persisted["editor_response"] is None
    # Wire intervention emitted.
    intervention_events = [
        e for e in wire.emitted if e.get("message_type") == "intervention"
    ]
    assert len(intervention_events) == 1
    assert intervention_events[0]["agent"] == "equity_editor"
    assert intervention_events[0]["story_unit_id"] == "us-al-birmingham"


@pytest.mark.asyncio
async def test_return_draft_increments_revisions_count():
    """Pre-loaded draft with revisions_count=0 → tool sets count=1, cleared=False."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        story_drafts=[
            {
                "id": "draft-100",
                "story_unit_id": "us-ia-mt-pleasant",
                "headline": "test",
                "equity_review": {
                    "cleared": True,
                    "feedback": "",
                    "revisions_count": 0,
                },
            }
        ]
    )
    tools = build_equity_editor_tools(wire=wire, firestore=firestore)
    return_draft = _get_tool(tools, "return_draft")

    out = await return_draft(
        "draft-100",
        "Paralympic context shallow. Revise.",
    )

    assert out["decision"] == "returned"
    assert out["revisions_count"] == 1
    assert out["feedback"] == "Paralympic context shallow. Revise."
    assert out["persisted"] is True
    # The most-recent add() captures the post-state.
    drafts = firestore.collections["story_drafts"].added
    assert len(drafts) == 1
    post = drafts[0]
    assert post["equity_review"]["cleared"] is False
    assert post["equity_review"]["revisions_count"] == 1
    assert post["equity_review"]["feedback"] == "Paralympic context shallow. Revise."
    assert post["publish_gate_decision"] == "returned"


@pytest.mark.asyncio
async def test_block_draft_sets_publish_gate_decision_killed():
    """block_draft sets publish_gate_decision='killed' and writes /killed_drafts/."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        story_drafts=[
            {
                "id": "draft-200",
                "story_unit_id": "us-co-colorado-springs",
                "headline": "test",
                "equity_review": {
                    "cleared": True,
                    "feedback": "",
                    "revisions_count": 0,
                },
            }
        ]
    )
    tools = build_equity_editor_tools(wire=wire, firestore=firestore)
    block_draft = _get_tool(tools, "block_draft")

    out = await block_draft(
        "draft-200",
        "Frames disability as inspiration",
    )

    assert out["decision"] == "blocked"
    assert out["persisted"] is True
    # Draft mutation: publish_gate_decision='killed'.
    drafts = firestore.collections["story_drafts"].added
    assert len(drafts) == 1
    post = drafts[0]
    assert post["publish_gate_decision"] == "killed"
    assert post["equity_review"]["cleared"] is False
    # Audit-trail write to /killed_drafts/.
    killed = firestore.collections["killed_drafts"].added
    assert len(killed) == 1
    assert killed[0]["draft_id"] == "draft-200"
    assert killed[0]["blocked_by"] == "equity_editor"
    assert "inspiration" in killed[0]["reason"]


@pytest.mark.asyncio
async def test_clear_draft_emits_milestone_wire_event():
    """clear_draft sets cleared=True (no revisions increment) and emits milestone."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        story_drafts=[
            {
                "id": "draft-300",
                "story_unit_id": "us-mn-mpls",
                "headline": "test",
                "equity_review": {
                    "cleared": False,
                    "feedback": "earlier feedback",
                    "revisions_count": 2,
                },
            }
        ]
    )
    tools = build_equity_editor_tools(wire=wire, firestore=firestore)
    clear_draft = _get_tool(tools, "clear_draft")

    out = await clear_draft("draft-300")

    assert out["decision"] == "cleared"
    # revisions_count is NOT incremented on clear.
    assert out["revisions_count"] == 2
    assert out["persisted"] is True
    # Wire milestone event emitted.
    milestone_events = [
        e for e in wire.emitted if e.get("message_type") == "milestone"
    ]
    assert len(milestone_events) == 1
    assert milestone_events[0]["agent"] == "equity_editor"
    assert "Cleared" in milestone_events[0]["message"]
    # Draft mutation: cleared=True, feedback cleared.
    drafts = firestore.collections["story_drafts"].added
    assert len(drafts) == 1
    post = drafts[0]
    assert post["equity_review"]["cleared"] is True
    assert post["equity_review"]["feedback"] == ""
