"""Unit tests for `EquityEditorAgent.review_feed` / `review_draft`.

Mirrors `agents/editor/test_agent.py` and `agents/investigator/test_agent.py`.
The ADK Runner is mocked at the `_run_adk_once` boundary so unit tests don't
hit live Vertex AI. The integration test (`tests/integration/`) is what
exercises the real ADK path.

Required cases (per HoE spec):
  1. Constructs with the Pro model id.
  2. review_feed skips on AGENT_RUNTIME_PAUSED=1.
  3. review_feed handles a Runner exception → emits intervention, returns error.
  4. review_feed handles CostCeilingExceeded → emits intervention, returns skipped.
  5. review_draft returns decision='cleared' when Runner calls clear_draft.
  6. review_draft returns decision='returned' when Runner calls return_draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.equity_editor.agent import EquityEditorAgent


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
        story_drafts: list[dict] | None = None,
        wire_events: list[dict] | None = None,
        equity_interventions: list[dict] | None = None,
        killed_drafts: list[dict] | None = None,
    ) -> None:
        self.collections: dict[str, _FakeColl] = {
            "story_drafts": _FakeColl(story_drafts or []),
            "wire_events": _FakeColl(wire_events or []),
            "equity_interventions": _FakeColl(equity_interventions or []),
            "killed_drafts": _FakeColl(killed_drafts or []),
        }

    def collection(self, name: str) -> _FakeColl:
        return self.collections.setdefault(name, _FakeColl())


@dataclass
class _FakeRuntimeState:
    last_think_cycle: datetime | None = None


# -- Helpers ------------------------------------------------------------------


def _build_agent(
    *,
    wire: Any | None = None,
    firestore: Any | None = None,
    bigquery: Any | None = None,
    cost_counter: Any | None = None,
    runtime_state: Any | None = None,
    wire_vocabulary: Any | None = None,
) -> EquityEditorAgent:
    return EquityEditorAgent(
        prompt="You are the Paralympic Equity Editor (test).",
        wire=wire or _FakeWire(),
        firestore=firestore if firestore is not None else _FakeFirestore(),
        bigquery=bigquery,
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
        wire_vocabulary=wire_vocabulary,
        runtime_state=runtime_state,
    )


# -- Tests --------------------------------------------------------------------


def test_equity_editor_constructs_with_pro_model():
    """Default model is `gemini-3.1-pro-preview` per BUILD_SPEC §3.1."""
    agent = _build_agent()
    assert agent.model == "gemini-3.1-pro-preview"
    # Seven tools: 6 from build_equity_editor_tools + pull_vocabulary.
    tool_names = [getattr(t, "__name__", "") for t in agent._bound_tools]
    for expected in (
        "read_published_feed",
        "read_draft",
        "intervene_feed_drift",
        "return_draft",
        "clear_draft",
        "block_draft",
        "pull_vocabulary",
    ):
        assert expected in tool_names, f"missing tool: {expected}"


@pytest.mark.asyncio
async def test_review_feed_skips_on_pause(monkeypatch):
    """With AGENT_RUNTIME_PAUSED=1, review_feed returns early."""
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    agent = _build_agent()

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when paused")

    with mock.patch.object(agent, "_run_adk_once", side_effect=_should_not_be_called):
        result = await agent.review_feed()

    assert result == {"action": "skipped", "reason": "paused"}


@pytest.mark.asyncio
async def test_review_feed_handles_runner_exception():
    """When Runner raises on BOTH attempts, review_feed emits an
    arrival-style `intervention` event (NOT thinking — BUILD_SPEC §6.5)
    and returns action='error'."""
    wire = _FakeWire()
    agent = _build_agent(wire=wire)

    async def _always_raises(**_kwargs):
        raise RuntimeError("model timeout")

    with mock.patch.object(agent, "_run_adk_once", side_effect=_always_raises):
        result = await agent.review_feed()

    assert result["action"] == "error"
    failure_events = [
        e for e in wire.emitted if "model returned an error" in e.get("message", "")
    ]
    assert len(failure_events) == 1, f"expected 1 failure event, got {wire.emitted!r}"
    assert failure_events[0]["agent"] == "equity_editor"
    # Equity Editor uses 'intervention' (arrival), not 'thinking' (streamed).
    assert failure_events[0]["message_type"] == "intervention"


@pytest.mark.asyncio
async def test_review_feed_handles_cost_ceiling():
    """When the cost counter raises CostCeilingExceeded, review_feed emits
    a 'pausing' Wire intervention and skips. Runner is NOT invoked."""
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
        result = await agent.review_feed()

    assert result == {"action": "skipped", "reason": "cost_ceiling"}
    cap_events = [
        e for e in wire.emitted if "daily Pro cap reached" in e.get("message", "")
    ]
    assert len(cap_events) == 1
    assert "equity editor pausing" in cap_events[0]["message"]
    # Arrival-style event for this agent.
    assert cap_events[0]["message_type"] == "intervention"


@pytest.mark.asyncio
async def test_review_draft_returns_cleared_decision_when_runner_calls_clear_draft():
    """Runner returns a tool call to `clear_draft`; review_draft surfaces
    `decision='cleared'`."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        story_drafts=[
            {
                "id": "draft-001",
                "story_unit_id": "us-ia-mt-pleasant",
                "headline": "test draft",
                "equity_review": {"cleared": False, "feedback": "", "revisions_count": 0},
            }
        ]
    )
    agent = _build_agent(wire=wire, firestore=firestore)

    async def _runner_clears(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [
                {"name": "read_draft", "args": {"draft_id": "draft-001"}},
                {"name": "clear_draft", "args": {"draft_id": "draft-001"}},
            ],
            "input_tokens": 1500,
            "output_tokens": 60,
        }

    with mock.patch.object(agent, "_run_adk_once", side_effect=_runner_clears):
        result = await agent.review_draft("draft-001")

    assert result["action"] == "ok"
    assert result["decision"] == "cleared"
    assert result["draft_id"] == "draft-001"


@pytest.mark.asyncio
async def test_review_draft_returns_returned_decision_when_runner_calls_return_draft():
    """Runner returns a tool call to `return_draft`; review_draft surfaces
    `decision='returned'` and `feedback` from the tool args."""
    wire = _FakeWire()
    firestore = _FakeFirestore(
        story_drafts=[
            {
                "id": "draft-002",
                "story_unit_id": "us-al-birmingham",
                "headline": "another test draft",
                "equity_review": {"cleared": False, "feedback": "", "revisions_count": 0},
            }
        ]
    )
    agent = _build_agent(wire=wire, firestore=firestore)

    async def _runner_returns(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [
                {"name": "read_draft", "args": {"draft_id": "draft-002"}},
                {
                    "name": "return_draft",
                    "args": {
                        "draft_id": "draft-002",
                        "reason": "Paralympic context shallower than Olympic. Revise.",
                    },
                },
            ],
            "input_tokens": 1700,
            "output_tokens": 90,
        }

    with mock.patch.object(agent, "_run_adk_once", side_effect=_runner_returns):
        result = await agent.review_draft("draft-002")

    assert result["action"] == "ok"
    assert result["decision"] == "returned"
    assert result["draft_id"] == "draft-002"
    assert "shallower" in result["feedback"]


@pytest.mark.asyncio
async def test_review_feed_stamps_runtime_state_on_success():
    """On a successful review_feed, RuntimeState.last_think_cycle is updated."""
    state = _FakeRuntimeState()
    assert state.last_think_cycle is None

    agent = _build_agent(runtime_state=state)

    async def _runner_ok(*, user_message: str, investigation_id: str):
        return {"tool_calls": [], "input_tokens": 100, "output_tokens": 40}

    with mock.patch.object(agent, "_run_adk_once", side_effect=_runner_ok):
        result = await agent.review_feed()

    assert result["action"] == "ok"
    assert state.last_think_cycle is not None
    delta = (datetime.now(timezone.utc) - state.last_think_cycle).total_seconds()
    assert delta < 5.0


@pytest.mark.asyncio
async def test_pull_vocabulary_tool_uses_equity_editor_bucket():
    """Bound `pull_vocabulary` tool calls vocabulary.sample('equity_editor', ...)."""
    fake_vocab = mock.Mock()
    fake_vocab.sample = mock.Mock(return_value="feed drift detected. last [n] places olympic-heavy.")
    fake_vocab.fill = mock.Mock(
        return_value="feed drift detected. last 4 places olympic-heavy."
    )

    agent = _build_agent(wire_vocabulary=fake_vocab)
    pull_vocabulary = next(
        t for t in agent._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "pull_vocabulary"
    )

    out = await pull_vocabulary(message_type="intervention", n=4)

    assert "4" in out
    fake_vocab.sample.assert_called_once_with("equity_editor", "intervention")
    fake_vocab.fill.assert_called_once_with(
        "feed drift detected. last [n] places olympic-heavy.", n=4
    )
