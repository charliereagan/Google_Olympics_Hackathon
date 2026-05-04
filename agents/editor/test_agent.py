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
