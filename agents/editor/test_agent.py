"""Unit tests for `EditorAgent.think_once` (Day-3 work).

Covers the three cases the Day-3 prompt requires:
  1. `think_once` skips on `AGENT_RUNTIME_PAUSED=1`.
  2. `think_once` handles a Runner exception (BUILD_SPEC §17.1).
  3. `think_once` updates `RuntimeState.last_think_cycle` on success.

The ADK Runner is mocked at the `_run_adk_once` boundary so unit tests don't
hit live Vertex AI. The integration test (`tests/integration/`) is what
exercises the real ADK path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.editor.agent import EditorAgent
from agents.wire.types import InvestigationContext


# -- Fakes --------------------------------------------------------------------


class _FakeNilLayer:
    is_loaded = True
    registry_size = 600


class _FakeFirestore:
    """Stub Firestore client. `collection` returns an empty stream so the
    Editor's context-snapshot reads succeed with no data."""

    def collection(self, name: str) -> "_FakeColl":
        return _FakeColl()


class _FakeColl:
    def where(self, *args, **kwargs) -> "_FakeColl":
        return self

    def order_by(self, *args, **kwargs) -> "_FakeColl":
        return self

    def limit(self, n: int) -> "_FakeColl":
        return self

    def stream(self) -> list:
        return []

    def add(self, doc: dict) -> tuple:
        return (mock.Mock(), mock.Mock(id="fake-doc-id"))


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _SeededColl:
    """Collection stub seeded with documents for the equity-recommendation tests."""

    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = docs or []
        self.added: list[dict] = []

    def where(self, *args, **kwargs) -> "_SeededColl":
        return self

    def order_by(self, *args, **kwargs) -> "_SeededColl":
        return self

    def limit(self, n: int) -> "_SeededColl":
        return self

    def stream(self):
        return [_SeededDoc(d) for d in self._docs]

    def add(self, doc: dict) -> tuple:
        self.added.append(dict(doc))
        return (mock.Mock(), mock.Mock(id=f"fs-{len(self.added)}"))


class _SeededDoc:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.id = data.get("id", "fake-id")
        self.exists = True

    def to_dict(self) -> dict:
        return dict(self._data)


class _SeededFirestore:
    """Routing stub for tests that need a specific seeded collection."""

    def __init__(self, *, equity_interventions: list[dict] | None = None) -> None:
        self.collections: dict[str, _SeededColl] = {
            "equity_interventions": _SeededColl(equity_interventions or []),
        }

    def collection(self, name: str) -> _SeededColl:
        return self.collections.setdefault(name, _SeededColl())


@dataclass
class _FakeRuntimeState:
    last_think_cycle: datetime | None = None


# -- Tests --------------------------------------------------------------------


def _build_editor(
    *,
    wire: Any | None = None,
    runtime_state: Any | None = None,
    firestore: Any | None = None,
) -> EditorAgent:
    return EditorAgent(
        prompt="You are the Editor (test).",
        wire=wire or _FakeWire(),
        scout_desk=mock.Mock(),
        firestore=firestore if firestore is not None else _FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        runtime_state=runtime_state,
    )


@pytest.mark.asyncio
async def test_think_once_skips_on_pause(monkeypatch):
    """With AGENT_RUNTIME_PAUSED=1, think_once returns early.

    The mocked `_run_adk_once` would raise if called — assertion is "didn't
    call".
    """
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    editor = _build_editor()

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when paused")

    with mock.patch.object(editor, "_run_adk_once", side_effect=_should_not_be_called):
        result = await editor.think_once()

    assert result == {"action": "skipped", "reason": "paused"}


@pytest.mark.asyncio
async def test_think_once_handles_runner_exception():
    """When the ADK Runner raises on BOTH attempts, think_once emits a
    BUILD_SPEC §17.1 thinking event and returns action='error'."""
    wire = _FakeWire()
    editor = _build_editor(wire=wire)

    async def _always_raises(**_kwargs):
        raise RuntimeError("model timeout")

    with mock.patch.object(editor, "_run_adk_once", side_effect=_always_raises):
        result = await editor.think_once()

    assert result["action"] == "error"
    # Both retries must have been attempted, so we'd see exactly one
    # thinking-event-on-failure emit (after the final failure).
    failure_events = [
        e for e in wire.emitted if "model returned an error" in e.get("message", "")
    ]
    assert len(failure_events) == 1, f"expected 1 failure event, got {wire.emitted!r}"
    assert failure_events[0]["agent"] == "editor"
    assert failure_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_think_once_updates_last_think_cycle():
    """On success, RuntimeState.last_think_cycle is stamped with a recent ts."""
    state = _FakeRuntimeState()
    assert state.last_think_cycle is None

    editor = _build_editor(runtime_state=state)

    async def _runner_ok(*, user_message: str, investigation_id: str):
        return {"tool_calls": [], "input_tokens": 100, "output_tokens": 50}

    with mock.patch.object(editor, "_run_adk_once", side_effect=_runner_ok):
        result = await editor.think_once()

    assert result["action"] == "ok"
    assert state.last_think_cycle is not None
    delta = (datetime.now(timezone.utc) - state.last_think_cycle).total_seconds()
    assert delta < 5.0, f"last_think_cycle should be recent; got delta={delta}s"


@pytest.mark.asyncio
async def test_think_once_skips_on_cost_ceiling():
    """When the cost counter raises CostCeilingExceeded, the Editor emits a
    'conserving' Wire event and skips."""
    from agents.cost.counters import CostCeilingExceeded

    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=gemini_pro total=999 >= limit=200")
    )
    cost_counter.snapshot_today = mock.Mock(return_value={"gemini_pro": 999})

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=wire,
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
    )
    result = await editor.think_once()

    assert result == {"action": "skipped", "reason": "cost_ceiling"}
    cap_events = [
        e for e in wire.emitted if "daily Pro cap reached" in e.get("message", "")
    ]
    assert len(cap_events) == 1


@pytest.mark.asyncio
async def test_dispatch_scout_calls_scout_desk():
    """Editor's bound dispatch_scout tool forwards to scout_desk.dispatch_one
    with (scout_id, story_unit_id) and returns whatever the desk returned."""
    scout_desk = mock.Mock()
    scout_desk.dispatch_one = mock.AsyncMock(
        return_value={
            "dispatched": True,
            "scout": "cinderella",
            "story_unit_id": "us-ia-mt-pleasant",
            "lead_report_id": "lead-001",
            "tool_calls": [],
            "latency_ms": 1234,
            "input_tokens": 500,
            "output_tokens": 100,
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=scout_desk,
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
    )
    # Pull the bound dispatch_scout tool out of _bound_tools.
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_scout"
    )
    result = await dispatch_tool("cinderella", "us-ia-mt-pleasant")

    assert result["dispatched"] is True
    assert result["lead_report_id"] == "lead-001"
    scout_desk.dispatch_one.assert_awaited_once_with("cinderella", "us-ia-mt-pleasant")


@pytest.mark.asyncio
async def test_dispatch_investigator_calls_investigator_investigate():
    """Editor's bound `dispatch_investigator` tool forwards to
    investigator.investigate(lead_report_id) and returns the success shape.
    """
    investigator = mock.Mock()
    investigator.investigate = mock.AsyncMock(
        return_value={
            "action": "ok",
            "lead_report_id": "lead-001",
            "story_unit_id": "us-ia-mt-pleasant",
            "investigation_packet_id": "pkt-001",
            "tool_calls": [{"name": "grounded_search", "args": {}}],
            "latency_ms": 1234,
            "input_tokens": 4200,
            "output_tokens": 890,
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        investigator=investigator,
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_investigator"
    )
    result = await dispatch_tool("lead-001")

    assert result["dispatched"] is True
    assert result["lead_report_id"] == "lead-001"
    assert result["investigation_packet_id"] == "pkt-001"
    assert result["story_unit_id"] == "us-ia-mt-pleasant"
    investigator.investigate.assert_awaited_once_with("lead-001")


@pytest.mark.asyncio
async def test_dispatch_investigator_returns_error_when_uninitialized():
    """Without an investigator instance, the tool returns dispatched=False."""
    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_investigator"
    )
    result = await dispatch_tool("lead-001")
    assert result["dispatched"] is False
    assert "error" in result
    assert "investigator" in result["error"].lower()


@pytest.mark.asyncio
async def test_dispatch_scout_returns_unknown_scout_error():
    """Calling dispatch_scout with an unknown scout_id returns an error dict
    and does NOT invoke scout_desk.dispatch_one."""
    scout_desk = mock.Mock()
    scout_desk.dispatch_one = mock.AsyncMock()
    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=scout_desk,
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_scout"
    )
    result = await dispatch_tool("nope", "us-ia-mt-pleasant")
    assert result["dispatched"] is False
    assert "error" in result
    assert "unknown scout_id" in result["error"]
    scout_desk.dispatch_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_pull_vocabulary_tool_returns_filled_fragment():
    """Editor's bound `pull_vocabulary` tool calls WireVocabulary.sample +
    fill and returns the filled string.

    BUILD_SPEC §6.4 — the LLM-facing tool wraps the loader; if the library
    returns a fragment, fill() resolves [slot]s and the result is returned
    as-is for the next wire_emit call.
    """
    fake_vocab = mock.Mock()
    fake_vocab.sample = mock.Mock(return_value="going with [place].")
    fake_vocab.fill = mock.Mock(return_value="going with Mt. Pleasant.")

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        wire_vocabulary=fake_vocab,
    )
    pull_vocabulary = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "pull_vocabulary"
    )

    out = await pull_vocabulary(message_type="thinking", place="Mt. Pleasant")

    assert out == "going with Mt. Pleasant."
    fake_vocab.sample.assert_called_once_with("editor", "thinking")
    fake_vocab.fill.assert_called_once_with("going with [place].", place="Mt. Pleasant")


@pytest.mark.asyncio
async def test_accept_equity_recommendation_reads_intervention_and_writes_response():
    """The bound `accept_equity_recommendation` tool reads the intervention
    doc, writes back `editor_response='accepted'`, and emits a Wire decision.
    """
    wire = _FakeWire()
    firestore = _SeededFirestore(
        equity_interventions=[
            {
                "id": "intv-001",
                "intervention_id": "intv-001",
                "kind": "feed_drift",
                "reason": "Last 4 places Olympic-heavy",
                "suggested_priority_lift_story_unit_id": "us-al-birmingham",
                "editor_response": None,
                "editor_response_at": None,
                "created_at": "2026-05-02T01:00:00+00:00",
            }
        ]
    )
    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=wire,
        scout_desk=mock.Mock(),
        firestore=firestore,
        model_id="gemini-3.1-pro-preview",
    )
    accept_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "accept_equity_recommendation"
    )

    result = await accept_tool("intv-001")

    assert result["accepted"] is True
    assert result["intervention_id"] == "intv-001"
    assert result["suggested_priority_lift_story_unit_id"] == "us-al-birmingham"
    assert result["persisted"] is True
    # Most-recent add() to /equity_interventions/ has editor_response='accepted'.
    added = firestore.collections["equity_interventions"].added
    assert len(added) == 1
    assert added[0]["editor_response"] == "accepted"
    assert added[0]["editor_response_at"] is not None
    # A decision-style Wire event was emitted.
    decision_events = [
        e for e in wire.emitted if e.get("message_type") == "decision"
    ]
    assert len(decision_events) == 1
    assert decision_events[0]["story_unit_id"] == "us-al-birmingham"


@pytest.mark.asyncio
async def test_request_equity_review_dispatches_to_equity_editor():
    """The bound `request_equity_review` tool dispatches to
    equity_editor.review_feed() / review_draft() based on scope."""
    equity_editor = mock.Mock()
    equity_editor.review_feed = mock.AsyncMock(
        return_value={"action": "ok", "tool_calls": [], "latency_ms": 1100}
    )
    equity_editor.review_draft = mock.AsyncMock(
        return_value={
            "action": "ok",
            "decision": "cleared",
            "draft_id": "draft-001",
            "tool_calls": [],
            "latency_ms": 800,
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        equity_editor=equity_editor,
    )
    request_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "request_equity_review"
    )

    # scope='feed' branch.
    feed_result = await request_tool(scope="feed")
    assert feed_result["action"] == "ok"
    equity_editor.review_feed.assert_awaited_once()

    # scope='draft' branch.
    draft_result = await request_tool(scope="draft", draft_id="draft-001")
    assert draft_result["decision"] == "cleared"
    equity_editor.review_draft.assert_awaited_once_with("draft-001")


@pytest.mark.asyncio
async def test_request_equity_review_returns_error_when_uninitialized():
    """Without an equity_editor, the tool returns an error dict."""
    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
    )
    request_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "request_equity_review"
    )
    result = await request_tool(scope="feed")
    assert result["dispatched"] is False
    assert "equity_editor" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_storyteller_calls_storyteller_write_story():
    """Editor's bound `dispatch_storyteller` tool forwards to
    storyteller.write_story(investigation_packet_id) and surfaces the
    cleared/returned/killed shape."""
    storyteller = mock.Mock()
    storyteller.write_story = mock.AsyncMock(
        return_value={
            "action": "cleared",
            "draft_id": "draft-001",
            "revisions_count": 0,
            "final_decision": "cleared",
            "latency_ms": 4500,
            "investigation_packet_id": "pkt-001",
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        storyteller=storyteller,
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_storyteller"
    )
    result = await dispatch_tool("pkt-001")

    assert result["dispatched"] is True
    assert result["action"] == "cleared"
    assert result["draft_id"] == "draft-001"
    storyteller.write_story.assert_awaited_once_with("pkt-001")


@pytest.mark.asyncio
async def test_dispatch_narrator_calls_narrator_narrate_with_cleared_draft():
    """Editor's bound `dispatch_narrator` tool reads the draft from
    Firestore, validates it's cleared, converts to NarrationManifest
    input shape, and calls narrator.narrate."""
    narrator = mock.Mock()
    narrator.narrate = mock.AsyncMock(
        return_value={
            "story_id": "draft-001",
            "audio_urls": ["gs://bucket/draft-001/0.mp3"],
            "audio_duration_ms": 12000,
            "voice_name": "Algenib",
        }
    )

    cleared_draft = {
        "id": "draft-001",
        "headline": "A small Iowa county keeps producing Olympians and Paralympians",
        "dek": "The pattern took shape from a single high-school program.",
        "body": "The county sits at the foot of the regional pipeline. " * 30,
        "hometown_panel": "The town's first Olympian came in 1976.",
        "historical_echo": "The pattern echoes the 1960s post-war track-and-field era.",
        "place_name": "Mt Pleasant, Iowa",
        "era_reference": "1960s post-war track-and-field",
        "publish_gate_decision": "cleared",
    }
    firestore = _SeededFirestore()
    firestore.collections["story_drafts"] = _SeededColl([cleared_draft])

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=firestore,
        model_id="gemini-3.1-pro-preview",
        narrator=narrator,
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_narrator"
    )
    result = await dispatch_tool("draft-001")

    assert result["dispatched"] is True
    assert result["manifest"]["story_id"] == "draft-001"
    narrator.narrate.assert_awaited_once()
    awaited = narrator.narrate.await_args
    narration_input = awaited.args[0]
    assert narration_input["story_id"] == "draft-001"
    assert narration_input["place_name_for_cues"] == "Mt Pleasant, Iowa"
    assert narration_input["era_reference_for_cues"] == "1960s post-war track-and-field"
    assert awaited.kwargs.get("voice_profile") == "broadcast"


@pytest.mark.asyncio
async def test_think_once_records_tool_calls_and_tokens():
    """When the Runner returns tool calls + usage metadata, the Editor
    surfaces them in the result and increments the cost counter."""
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock()
    cost_counter.increment = mock.AsyncMock()
    cost_counter.snapshot_today = mock.Mock(return_value={})

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
    )

    async def _runner_with_calls(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [
                {"name": "dispatch_scout", "args": {"scout_id": "hometown", "story_unit_id": "us-ia-mt-pleasant"}},
            ],
            "input_tokens": 1200,
            "output_tokens": 80,
        }

    with mock.patch.object(editor, "_run_adk_once", side_effect=_runner_with_calls):
        result = await editor.think_once(
            ctx=InvestigationContext(
                investigation_id="inv-test-001",
                compression_factor=0.25,
            )
        )

    assert result["action"] == "ok"
    assert result["tool_calls"][0]["name"] == "dispatch_scout"
    cost_counter.assert_under_ceiling.assert_awaited_once()
    cost_counter.increment.assert_awaited_once()
    inc_kwargs = cost_counter.increment.await_args.kwargs
    assert inc_kwargs["agent"] == "editor"
    assert inc_kwargs["axis"] == "gemini_pro"
    assert inc_kwargs["input_tokens"] == 1200
    assert inc_kwargs["output_tokens"] == 80


@pytest.mark.asyncio
async def test_dispatch_publish_gate_calls_publish_gate_review():
    """Editor's bound `dispatch_publish_gate` tool forwards to
    publish_gate.review(story_draft_id=...) and surfaces the audit dict.
    """
    publish_gate = mock.Mock()
    publish_gate.review = mock.AsyncMock(
        return_value={
            "audit_id": "aud-001",
            "story_id": "draft-001",
            "investigation_packet_id": "pkt-001",
            "sub_stages": {
                "fact_check": {"passed": True},
                "source_review": {"passed": True},
                "parity_review": {"passed": True},
                "nil_redaction_review": {"passed": True},
                "safety_review": {"passed": True},
                "language_review": {"passed": True},
                "visual_review": {"passed": True},
            },
            "final_decision": "cleared",
            "completed_at": "2026-05-02T00:00:00+00:00",
            "revisions_requested": [],
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=_FakeFirestore(),
        model_id="gemini-3.1-pro-preview",
        publish_gate=publish_gate,
    )
    dispatch_tool = next(
        t for t in editor._bound_tools  # type: ignore[attr-defined]
        if getattr(t, "__name__", "") == "dispatch_publish_gate"
    )
    result = await dispatch_tool("draft-001")

    assert result["dispatched"] is True
    assert result["audit"]["final_decision"] == "cleared"
    assert result["audit"]["story_id"] == "draft-001"
    publish_gate.review.assert_awaited_once_with(story_draft_id="draft-001")
