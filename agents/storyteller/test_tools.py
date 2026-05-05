"""Unit tests for `agents/storyteller/tools.py`.

Six required cases (per HoE spec):
  1. write_story_draft validates headline word count (5 words → error).
  2. write_story_draft validates body word count (300 words → error).
  3. write_story_draft persists a valid draft to Firestore + returns id.
  4. write_story_draft emits a Wire thinking event on validation error.
  5. request_equity_review calls runtime_state.equity_editor.review_draft.
  6. request_equity_review returns 'unknown' when the agent is not yet
     initialized.

NIL discipline: ZERO athlete names anywhere. Place ids are synthetic
(place_mt_pleasant_ia); era refs are synthetic.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest import mock

import pytest

from agents.storyteller.tools import (
    _DraftValidationError,
    build_storyteller_tools,
)


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
    equity_editor: Any = None
    publish_gate: Any = None


# -- Helpers ------------------------------------------------------------------


def _get_tool(tools: list[Any], name: str):
    for t in tools:
        if getattr(t, "__name__", "") == name:
            return t
    raise AssertionError(f"tool {name!r} not bound")


# Valid envelope baseline — derived once and edited per test for
# specific failures. NIL-clean: place + counts only, no names.
def _valid_body() -> str:
    """Return a body of ~520 words. Whitespace-stable across edits."""
    base_sentence = (
        "The county sits at the foot of the regional pipeline that has "
        "delivered Team USA representation in three consecutive Games. "
    )
    # Each repetition adds ~20 words; 26 reps ≈ 520 words.
    return (base_sentence * 26).strip()


def _valid_panel() -> str:
    """Return a hometown panel of ~62 words."""
    return (
        "The town sits at the south edge of a county of fewer than ten "
        "thousand. A single high school anchors the regional pipeline. "
        "Five decades of Team USA representation trace back to a community "
        "that builds athletes the way other towns build levees: slowly, "
        "communally, against the run of the river."
    )


def _valid_echo() -> str:
    """Return a historical echo of ~75 words."""
    return (
        "The pattern echoes the 1960s post-war track-and-field era when "
        "regional pipelines, not metropolitan training centers, built the "
        "national team. Communities of this size developed competitors who "
        "arrived in the rosters one decade at a time, and they carried the "
        "regional identity into the Games. The arc from county to roster "
        "has not changed; the cadence has."
    )


def _valid_kwargs(**overrides) -> dict:
    payload = {
        "headline": "Mt Pleasant, Iowa: a county that keeps producing Olympians",  # 9 words
        "dek": "A small Iowa county has built a Team USA pipeline the slow way",
        "body": _valid_body(),
        "why_this_matters": [
            "Place pipelines are not metropolitan; they are regional.",
            "Paralympic depth equal to Olympic depth signals lasting infrastructure.",
            "Generational arcs land harder than single-Games stories.",
        ],
        "hometown_panel": _valid_panel(),
        "historical_echo": _valid_echo(),
        "place_name": "Mt Pleasant, Iowa",
        "era_reference": "1960s post-war track-and-field",
        "investigation_packet_id": "pkt-001",
    }
    payload.update(overrides)
    return payload


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_story_draft_validates_headline_word_count():
    """A 5-word headline raises _DraftValidationError(field='headline')."""
    wire = _FakeWire()
    firestore = _FakeFirestore()
    tools = build_storyteller_tools(wire=wire, firestore=firestore)
    write_story_draft = _get_tool(tools, "write_story_draft")

    kwargs = _valid_kwargs(headline="Place builds Team USA pipeline")  # 5 words

    with pytest.raises(_DraftValidationError) as exc_info:
        await write_story_draft(**kwargs)

    assert exc_info.value.field == "headline"
    assert "out of bounds" in exc_info.value.message
    # Nothing persisted on validation failure.
    assert firestore.collections["story_drafts"].added == []


@pytest.mark.asyncio
async def test_write_story_draft_validates_body_word_count():
    """A ~300-word body raises _DraftValidationError(field='body')."""
    wire = _FakeWire()
    firestore = _FakeFirestore()
    tools = build_storyteller_tools(wire=wire, firestore=firestore)
    write_story_draft = _get_tool(tools, "write_story_draft")

    short_body = ("The county sits at the foot of the pipeline. " * 20).strip()
    # 9 words/sentence × 20 ≈ 180 words — well under the 400 floor.
    kwargs = _valid_kwargs(body=short_body)

    with pytest.raises(_DraftValidationError) as exc_info:
        await write_story_draft(**kwargs)

    assert exc_info.value.field == "body"
    assert firestore.collections["story_drafts"].added == []


@pytest.mark.asyncio
async def test_write_story_draft_persists_to_firestore():
    """A fully-valid envelope persists to /story_drafts/ and returns an id."""
    wire = _FakeWire()
    firestore = _FakeFirestore()
    tools = build_storyteller_tools(wire=wire, firestore=firestore)
    write_story_draft = _get_tool(tools, "write_story_draft")

    kwargs = _valid_kwargs()
    out = await write_story_draft(**kwargs)

    assert out["persisted"] is True
    assert isinstance(out["draft_id"], str) and out["draft_id"]
    assert out["investigation_packet_id"] == "pkt-001"

    # One write to /story_drafts/ — the doc carries the right shape.
    drafts = firestore.collections["story_drafts"].added
    assert len(drafts) == 1
    persisted = drafts[0]
    assert persisted["headline"] == kwargs["headline"]
    assert persisted["dek"] == kwargs["dek"]
    assert len(persisted["why_this_matters"]) == 3
    assert persisted["place_name"] == "Mt Pleasant, Iowa"
    assert persisted["era_reference"] == "1960s post-war track-and-field"
    # Initial state of the equity-review block.
    assert persisted["equity_review"] == {
        "cleared": False,
        "feedback": "",
        "revisions_count": 0,
    }
    assert persisted["publish_gate_decision"] == "pending"
    assert "created_at" in persisted and "updated_at" in persisted


@pytest.mark.asyncio
async def test_write_story_draft_emits_wire_thinking_on_validation_error():
    """On a validation failure, write_story_draft schedules a Wire
    thinking emit before raising. The emit is best-effort; the exception
    is the load-bearing signal."""
    wire = _FakeWire()
    firestore = _FakeFirestore()
    tools = build_storyteller_tools(wire=wire, firestore=firestore)
    write_story_draft = _get_tool(tools, "write_story_draft")

    kwargs = _valid_kwargs(headline="too short")  # 2 words

    with pytest.raises(_DraftValidationError):
        await write_story_draft(**kwargs)

    # Drain any scheduled coroutines so the wire emit lands.
    pending = [
        t
        for t in asyncio.all_tasks()
        if t is not asyncio.current_task() and not t.done()
    ]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    matching = [
        e
        for e in wire.emitted
        if e.get("agent") == "storyteller"
        and e.get("message_type") == "thinking"
        and "headline" in e.get("message", "")
    ]
    assert len(matching) >= 1, f"expected validation thinking event, got {wire.emitted!r}"


@pytest.mark.asyncio
async def test_request_equity_review_calls_equity_agent():
    """Tool routes through runtime_state.equity_editor.review_draft."""
    wire = _FakeWire()
    fake_equity = mock.Mock()
    fake_equity.review_draft = mock.AsyncMock(
        return_value={
            "action": "ok",
            "decision": "cleared",
            "draft_id": "draft-001",
            "tool_calls": [],
            "latency_ms": 1234,
        }
    )
    runtime_state = _FakeRuntimeState(equity_editor=fake_equity)
    tools = build_storyteller_tools(wire=wire, runtime_state=runtime_state)
    request_equity_review = _get_tool(tools, "request_equity_review")

    out = await request_equity_review("draft-001")

    assert out["decision"] == "cleared"
    assert out["draft_id"] == "draft-001"
    fake_equity.review_draft.assert_awaited_once_with("draft-001")


@pytest.mark.asyncio
async def test_request_equity_review_returns_unknown_when_agent_not_initialized():
    """No runtime_state → graceful 'unknown' decision dict."""
    wire = _FakeWire()
    tools = build_storyteller_tools(wire=wire, runtime_state=None)
    request_equity_review = _get_tool(tools, "request_equity_review")

    out = await request_equity_review("draft-001")

    assert out["decision"] == "unknown"
    assert out["draft_id"] == "draft-001"
    assert "not yet operational" in out["error"]
