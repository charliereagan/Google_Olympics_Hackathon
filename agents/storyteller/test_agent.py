"""Unit tests for `StorytellerAgent.write_story`.

Mirrors `agents/equity_editor/test_agent.py` and
`agents/editor/test_agent.py`. The ADK Runner is mocked at the
`_run_adk_once` boundary so unit tests don't hit live Vertex AI. The
integration test (`tests/integration/`) is what exercises the real
ADK path.

Required cases (per HoE spec):
  1. Constructs with the Pro model id.
  2. write_story skips on AGENT_RUNTIME_PAUSED=1.
  3. write_story handles a Runner exception → emits thinking, returns error.
  4. write_story handles CostCeilingExceeded → emits thinking, returns skipped.
  5. write_story writes draft on success — Runner returns a successful
     write_story_draft + cleared equity_review.
  6. write_story handles equity 'returned' once and 'cleared' on revision.
  7. write_story kills the draft after max_revisions reached.

NIL discipline: ZERO athlete names in any test fixture. Place ids are
synthetic (place_mt_pleasant_ia, etc.); era_parallels are synthetic
(1960s post-war track-and-field).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.storyteller.agent import StorytellerAgent


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _FakeColl:
    """Minimal Firestore collection stub. `_docs` lets a test seed contents."""

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
    """Collection-routing stub. Indexed by collection name."""

    def __init__(
        self,
        *,
        investigation_packets: list[dict] | None = None,
        story_drafts: list[dict] | None = None,
    ) -> None:
        self.collections: dict[str, _FakeColl] = {
            "investigation_packets": _FakeColl(investigation_packets or []),
            "story_drafts": _FakeColl(story_drafts or []),
        }

    def collection(self, name: str) -> _FakeColl:
        return self.collections.setdefault(name, _FakeColl())


@dataclass
class _FakeRuntimeState:
    last_think_cycle: datetime | None = None
    equity_editor: Any = None
    publish_gate: Any = None


def _build_packet(packet_id: str = "pkt-001") -> dict:
    """Synthetic Investigation Packet — no athlete names anywhere."""
    return {
        "id": packet_id,
        "story_unit_id": "place_mt_pleasant_ia",
        "story_unit_title": "Mt Pleasant, Iowa — county pipeline",
        "story_unit_type": "place",
        "narrative_spine": (
            "A small Iowa county has produced Team USA representation in "
            "three consecutive Games. The pattern took shape from a single "
            "high school program."
        ),
        "geography": {
            "state": "IA",
            "region": "Southeast Iowa",
            "population": 8500,
            "notes": "rural county seat; one large high school",
        },
        "historical_context": {
            "era_parallel": "1960s post-war track-and-field",
            "pattern_notes": "regional pipelines that fed the national team",
        },
        "trend_signals": {
            "olympic_count_history": [
                {"year": 1976, "count": 1},
                {"year": 2008, "count": 2},
                {"year": 2024, "count": 3},
            ],
            "paralympic_count_history": [
                {"year": 2012, "count": 1},
                {"year": 2024, "count": 2},
            ],
        },
        "sources": [
            {
                "url": "https://example.com/article",
                "outlet": "Local Paper",
                "relevance_note": "summary of county program history",
            }
        ],
        "paralympic_depth_score": 0.7,
        "ready_for_storyteller": True,
    }


def _build_agent(
    *,
    wire: Any | None = None,
    firestore: Any | None = None,
    bigquery: Any | None = None,
    cost_counter: Any | None = None,
    runtime_state: Any | None = None,
    wire_vocabulary: Any | None = None,
    max_revisions: int = 3,
) -> StorytellerAgent:
    seeded_fs = (
        firestore
        if firestore is not None
        else _FakeFirestore(investigation_packets=[_build_packet()])
    )
    return StorytellerAgent(
        prompt="You are the Storyteller (test).",
        wire=wire or _FakeWire(),
        firestore=seeded_fs,
        bigquery=bigquery,
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
        wire_vocabulary=wire_vocabulary,
        runtime_state=runtime_state,
        max_revisions=max_revisions,
    )


# -- Tests --------------------------------------------------------------------


def test_storyteller_constructs_with_pro_model():
    """Default model is `gemini-3.1-pro-preview` per BUILD_SPEC §3.1."""
    agent = _build_agent()
    assert agent.model == "gemini-3.1-pro-preview"
    # Five tools: 4 from build_storyteller_tools + pull_vocabulary.
    tool_names = [getattr(t, "__name__", "") for t in agent._bound_tools]
    for expected in (
        "read_investigation_packet",
        "write_story_draft",
        "request_equity_review",
        "request_publish_gate",
        "pull_vocabulary",
    ):
        assert expected in tool_names, f"missing tool: {expected}"


@pytest.mark.asyncio
async def test_write_story_skips_on_pause(monkeypatch):
    """With AGENT_RUNTIME_PAUSED=1, write_story returns early."""
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    agent = _build_agent()

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when paused")

    with mock.patch.object(agent, "_run_adk_once", side_effect=_should_not_be_called):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "skipped"
    assert result["reason"] == "paused"
    assert result["draft_id"] is None


@pytest.mark.asyncio
async def test_write_story_handles_runner_exception():
    """When Runner raises on BOTH attempts, write_story emits a Wire
    `thinking` event and returns action='error'."""
    wire = _FakeWire()
    agent = _build_agent(wire=wire)

    async def _always_raises(**_kwargs):
        raise RuntimeError("model timeout")

    with mock.patch.object(agent, "_run_adk_once", side_effect=_always_raises):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "error"
    failure_events = [
        e for e in wire.emitted if "model returned an error" in e.get("message", "")
    ]
    assert len(failure_events) == 1, f"expected 1 failure event, got {wire.emitted!r}"
    assert failure_events[0]["agent"] == "storyteller"
    # Storyteller streams its thinking — message_type='thinking' (not
    # 'intervention' like the Equity Editor).
    assert failure_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_write_story_handles_cost_ceiling():
    """When the cost counter raises CostCeilingExceeded, write_story emits
    a 'pausing' Wire thinking and skips. Runner is NOT invoked."""
    from agents.cost.counters import CostCeilingExceeded

    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=gemini_pro total=999 >= limit=200")
    )
    cost_counter.snapshot_today = mock.Mock(return_value={"gemini_pro": 999})

    agent = _build_agent(wire=wire, cost_counter=cost_counter)

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked at cost ceiling")

    with mock.patch.object(agent, "_run_adk_once", side_effect=_should_not_be_called):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "skipped"
    assert result["reason"] == "cost_ceiling"
    cap_events = [
        e for e in wire.emitted if "daily Pro cap reached" in e.get("message", "")
    ]
    assert len(cap_events) == 1
    assert "storyteller pausing" in cap_events[0]["message"]
    assert cap_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_write_story_writes_draft_on_success():
    """Runner returns successful write_story_draft + cleared equity review;
    write_story surfaces action='cleared' and the draft id."""
    wire = _FakeWire()
    agent = _build_agent(wire=wire)

    async def _runner_clears(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [
                {
                    "name": "write_story_draft",
                    "args": {
                        "headline": "Mt Pleasant, Iowa: a county that keeps producing Olympians",
                    },
                    "response": {
                        "id": "draft-abc",
                        "draft_id": "draft-abc",
                        "persisted": True,
                        "investigation_packet_id": "pkt-001",
                    },
                },
                {
                    "name": "request_equity_review",
                    "args": {"draft_id": "draft-abc"},
                    "response": {
                        "action": "ok",
                        "decision": "cleared",
                        "draft_id": "draft-abc",
                    },
                },
            ],
            "input_tokens": 4500,
            "output_tokens": 800,
        }

    with mock.patch.object(agent, "_run_adk_once", side_effect=_runner_clears):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "cleared"
    assert result["draft_id"] == "draft-abc"
    assert result["final_decision"] == "cleared"
    # Milestone Wire event emitted on cleared.
    milestone_events = [
        e for e in wire.emitted if e.get("message_type") == "milestone"
    ]
    assert any("cleared" in e["message"].lower() for e in milestone_events)


@pytest.mark.asyncio
async def test_write_story_handles_equity_return_with_one_revision():
    """First Runner cycle returns 'returned'; second cycle returns
    'cleared'. write_story surfaces action='cleared' with revisions_count=1."""
    wire = _FakeWire()
    agent = _build_agent(wire=wire)

    call_count = {"n": 0}

    async def _runner(*, user_message: str, investigation_id: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "tool_calls": [
                    {
                        "name": "write_story_draft",
                        "args": {},
                        "response": {
                            "id": "draft-001",
                            "draft_id": "draft-001",
                            "persisted": True,
                            "investigation_packet_id": "pkt-001",
                        },
                    },
                    {
                        "name": "request_equity_review",
                        "args": {"draft_id": "draft-001"},
                        "response": {
                            "action": "ok",
                            "decision": "returned",
                            "draft_id": "draft-001",
                            "feedback": "Paralympic depth shallow. Revise.",
                        },
                    },
                ],
                "input_tokens": 4500,
                "output_tokens": 800,
            }
        return {
            "tool_calls": [
                {
                    "name": "write_story_draft",
                    "args": {},
                    "response": {
                        "id": "draft-002",
                        "draft_id": "draft-002",
                        "persisted": True,
                        "investigation_packet_id": "pkt-001",
                    },
                },
                {
                    "name": "request_equity_review",
                    "args": {"draft_id": "draft-002"},
                    "response": {
                        "action": "ok",
                        "decision": "cleared",
                        "draft_id": "draft-002",
                    },
                },
            ],
            "input_tokens": 4500,
            "output_tokens": 800,
        }

    with mock.patch.object(agent, "_run_adk_once", side_effect=_runner):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "cleared"
    assert result["revisions_count"] == 1
    assert result["draft_id"] == "draft-002"
    assert result["final_decision"] == "cleared"
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_write_story_kills_on_max_revisions_reached():
    """Equity returns the draft 4 times; on the 4th, write_story kills it."""
    wire = _FakeWire()
    agent = _build_agent(wire=wire, max_revisions=3)

    call_count = {"n": 0}

    async def _always_returns(*, user_message: str, investigation_id: str):
        call_count["n"] += 1
        return {
            "tool_calls": [
                {
                    "name": "write_story_draft",
                    "args": {},
                    "response": {
                        "id": f"draft-{call_count['n']:03d}",
                        "draft_id": f"draft-{call_count['n']:03d}",
                        "persisted": True,
                        "investigation_packet_id": "pkt-001",
                    },
                },
                {
                    "name": "request_equity_review",
                    "args": {"draft_id": f"draft-{call_count['n']:03d}"},
                    "response": {
                        "action": "ok",
                        "decision": "returned",
                        "draft_id": f"draft-{call_count['n']:03d}",
                        "feedback": "Paralympic depth shallow. Revise.",
                    },
                },
            ],
            "input_tokens": 4500,
            "output_tokens": 800,
        }

    with mock.patch.object(agent, "_run_adk_once", side_effect=_always_returns):
        result = await agent.write_story("pkt-001")

    assert result["action"] == "killed"
    assert result["reason"] == "max_revisions_reached"
    assert result["revisions_count"] == 4
    # Loop ran max_revisions + 1 cycles before kill.
    assert call_count["n"] == 4
    # Milestone event for the kill.
    kill_events = [
        e
        for e in wire.emitted
        if e.get("message_type") == "milestone"
        and "kill" in e.get("message", "").lower()
    ]
    assert len(kill_events) >= 1
