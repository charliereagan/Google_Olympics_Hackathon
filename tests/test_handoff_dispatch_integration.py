"""Integration: dispatch tools emit `agent_handoffs` documents.

Confirms that the closure-bound dispatch tools on the Editor (and the
Equity Editor / Storyteller / Publish Gate) emit one and only one
`agent_handoffs` document per invocation, with the correct
`from_agent` / `to_agent` / `tool_call_id`.

The agent-graph `/floor` (later worker) consumes these events to render
particle streams between the seven nodes; this test guarantees the
events flow from real agent operation rather than being inferred.

Approach: call each closure-bound tool directly using
`_chain_stubs.invoke_bound_tool`, with downstream agents replaced by
minimal async stubs whose only job is to satisfy the tool contract. The
focus is the handoff write, not the downstream agent's behavior — that
is covered by `tests/integration/test_full_chain_e2e.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.editor.agent import EditorAgent
from agents.equity_editor.tools import build_equity_editor_tools
from agents.handoffs import COLLECTION_NAME
from agents.storyteller.tools import build_storyteller_tools

from tests.integration._chain_stubs import FsClient, invoke_bound_tool


# --- Lightweight async stubs for downstream agents --------------------------


class _StubScoutDesk:
    async def dispatch_one(self, scout_id: str, story_unit_id: str) -> dict:
        return {"dispatched": True, "scout": scout_id, "story_unit_id": story_unit_id}


class _StubInvestigator:
    async def investigate(self, lead_report_id: str) -> dict:
        return {
            "action": "ok",
            "story_unit_id": "place_test_iowa",
            "investigation_packet_id": "pkt-test-001",
            "latency_ms": 0,
        }


class _StubStoryteller:
    async def write_story(self, packet_id: str) -> dict:
        return {"action": "cleared", "draft_id": "draft-test-001", "latency_ms": 0}


class _StubEquityEditor:
    def __init__(self) -> None:
        self.review_feed_calls = 0
        self.review_draft_calls: list[str] = []

    async def review_feed(self) -> dict:
        self.review_feed_calls += 1
        return {"action": "ok", "decision": "no_decision"}

    async def review_draft(self, draft_id: str) -> dict:
        self.review_draft_calls.append(draft_id)
        return {"action": "ok", "decision": "cleared", "draft_id": draft_id}


class _StubPublishGate:
    async def review(self, *, story_draft_id: str) -> dict:
        return {
            "story_id": story_draft_id,
            "final_decision": "cleared",
        }


class _StubNarrator:
    async def narrate(
        self,
        narration_input: dict,
        *,
        voice_profile: str,
        audit_id: str | None = None,
    ) -> dict:
        return {
            "manifest_id": "manifest-test-001",
            "voice_profile": voice_profile,
            "audit_id": audit_id,
        }


# --- Fixtures ---------------------------------------------------------------


def _make_editor(fs: FsClient) -> EditorAgent:
    """Build an EditorAgent with stub downstream agents."""
    return EditorAgent(
        prompt="(test editor prompt)",
        wire=_NoopWire(),
        scout_desk=_StubScoutDesk(),
        firestore=fs,
        investigator=_StubInvestigator(),
        equity_editor=_StubEquityEditor(),
        storyteller=_StubStoryteller(),
        publish_gate=_StubPublishGate(),
        narrator=_StubNarrator(),
    )


class _NoopWire:
    """Wire stub — `wire.emit()` no-ops; we only care about agent_handoffs."""

    is_loaded = True
    is_ready = True

    async def emit(self, event: dict, **kwargs) -> str:  # noqa: ARG002
        return "wire-noop"


def _seed_cleared_draft(fs: FsClient, draft_id: str) -> None:
    """Seed a cleared draft so dispatch_narrator's gate passes."""
    fs.collection("story_drafts").add(
        {
            "id": draft_id,
            "publish_gate_decision": "cleared",
            "headline": "test",
            "dek": "test",
            "body": "test",
            "hometown_panel": "",
            "historical_echo": "",
            "place_name": "",
            "era_reference": "",
            "story_unit_id": "place_test_iowa",
        }
    )


def _handoffs(fs: FsClient) -> list[dict]:
    return list(fs.docs(COLLECTION_NAME))


# --- Editor dispatch tools --------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_scout_emits_editor_to_scout_desk_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(
        editor,
        "dispatch_scout",
        scout_id="cinderella",
        story_unit_id="place_test_iowa",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "editor"
    assert h["to_agent"] == "scout_desk"
    assert h["tool_call_id"] == "dispatch_scout"
    assert h["story_unit_id"] == "place_test_iowa"
    assert h["mode"] == "live"


@pytest.mark.asyncio
async def test_dispatch_investigator_emits_editor_to_investigator_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(
        editor,
        "dispatch_investigator",
        lead_report_id="lead-test-001",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "editor"
    assert h["to_agent"] == "investigator"
    assert h["tool_call_id"] == "dispatch_investigator"


@pytest.mark.asyncio
async def test_dispatch_storyteller_emits_editor_to_storyteller_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(
        editor,
        "dispatch_storyteller",
        investigation_packet_id="pkt-test-001",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "editor"
    assert h["to_agent"] == "storyteller"
    assert h["tool_call_id"] == "dispatch_storyteller"


@pytest.mark.asyncio
async def test_dispatch_narrator_emits_storyteller_to_narrator_handoff():
    fs = FsClient()
    editor = _make_editor(fs)
    _seed_cleared_draft(fs, "draft-test-001")

    await invoke_bound_tool(
        editor,
        "dispatch_narrator",
        story_draft_id="draft-test-001",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    # Per BUILD_SPEC §9.6: the particle stream renders storyteller -> narrator
    # at this dispatch (the story is moving from cleared draft to TTS render),
    # even though the Editor is the dispatcher.
    assert h["from_agent"] == "storyteller"
    assert h["to_agent"] == "narrator"
    assert h["tool_call_id"] == "dispatch_narrator"
    assert h["story_unit_id"] == "place_test_iowa"


@pytest.mark.asyncio
async def test_dispatch_publish_gate_emits_storyteller_to_publish_gate_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(
        editor,
        "dispatch_publish_gate",
        story_draft_id="draft-test-001",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    # Per BUILD_SPEC §9.6: the particle stream renders storyteller -> publish_gate
    # at this dispatch, not editor -> publish_gate.
    assert h["from_agent"] == "storyteller"
    assert h["to_agent"] == "publish_gate"
    assert h["tool_call_id"] == "dispatch_publish_gate"


@pytest.mark.asyncio
async def test_request_equity_review_feed_emits_editor_to_equity_editor_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(editor, "request_equity_review", scope="feed")

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "editor"
    assert h["to_agent"] == "equity_editor"
    assert h["tool_call_id"] == "request_equity_review"


@pytest.mark.asyncio
async def test_request_equity_review_draft_emits_editor_to_equity_editor_handoff():
    fs = FsClient()
    editor = _make_editor(fs)

    await invoke_bound_tool(
        editor,
        "request_equity_review",
        scope="draft",
        draft_id="draft-test-001",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "editor"
    assert h["to_agent"] == "equity_editor"
    assert h["tool_call_id"] == "request_equity_review"


# --- Equity Editor tools ----------------------------------------------------


def _build_equity_tools(fs: FsClient) -> list[Any]:
    return build_equity_editor_tools(
        wire=_NoopWire(),
        firestore=fs,
        bigquery=None,
    )


def _find_tool(tools: list[Any], name: str) -> Any:
    for tool in tools:
        if getattr(tool, "__name__", "") == name:
            return tool
    raise AssertionError(f"tool {name!r} not found")


@pytest.mark.asyncio
async def test_intervene_feed_drift_emits_equity_editor_to_editor_handoff():
    fs = FsClient()
    tools = _build_equity_tools(fs)

    await _find_tool(tools, "intervene_feed_drift")(
        reason="last 4 places are olympic-heavy",
        suggested_priority_lift_story_unit_id="place_test_iowa",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "equity_editor"
    assert h["to_agent"] == "editor"
    assert h["tool_call_id"] == "intervene_feed_drift"
    assert h["story_unit_id"] == "place_test_iowa"


@pytest.mark.asyncio
async def test_return_draft_emits_equity_editor_to_storyteller_handoff():
    fs = FsClient()
    # Seed the draft so the mutation succeeds.
    fs.collection("story_drafts").add(
        {
            "id": "draft-test-001",
            "story_unit_id": "place_test_iowa",
            "equity_review": {"cleared": False, "feedback": "", "revisions_count": 0},
        }
    )

    tools = _build_equity_tools(fs)

    await _find_tool(tools, "return_draft")(
        draft_id="draft-test-001",
        reason="paralympic context shallow for this place",
    )

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "equity_editor"
    assert h["to_agent"] == "storyteller"
    assert h["tool_call_id"] == "return_draft"
    assert h["story_unit_id"] == "place_test_iowa"


# --- Storyteller tools ------------------------------------------------------


class _RuntimeStateLike:
    """Mimic `agents/runtime.py::RuntimeState` for the storyteller closures.

    The Storyteller's `request_equity_review` / `request_publish_gate`
    tools resolve `firestore` / `equity_editor` / `publish_gate` via
    `getattr(runtime_state, attr, None)`, so a small object with the
    attrs we need is sufficient.
    """

    def __init__(
        self,
        *,
        firestore: Any,
        equity_editor: Any,
        publish_gate: Any,
    ) -> None:
        self.firestore = firestore
        self.equity_editor = equity_editor
        self.publish_gate = publish_gate


def _build_storyteller_tools(state: Any) -> list[Any]:
    return build_storyteller_tools(
        wire=_NoopWire(),
        firestore=state.firestore,
        bigquery=None,
        runtime_state=state,
    )


@pytest.mark.asyncio
async def test_storyteller_request_equity_review_emits_handoff():
    fs = FsClient()
    state = _RuntimeStateLike(
        firestore=fs,
        equity_editor=_StubEquityEditor(),
        publish_gate=_StubPublishGate(),
    )
    tools = _build_storyteller_tools(state)

    await _find_tool(tools, "request_equity_review")(draft_id="draft-test-001")

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "storyteller"
    assert h["to_agent"] == "equity_editor"
    assert h["tool_call_id"] == "request_equity_review"


@pytest.mark.asyncio
async def test_storyteller_request_publish_gate_emits_handoff():
    fs = FsClient()
    state = _RuntimeStateLike(
        firestore=fs,
        equity_editor=_StubEquityEditor(),
        publish_gate=_StubPublishGate(),
    )
    tools = _build_storyteller_tools(state)

    await _find_tool(tools, "request_publish_gate")(draft_id="draft-test-001")

    hs = _handoffs(fs)
    assert len(hs) == 1
    h = hs[0]
    assert h["from_agent"] == "storyteller"
    assert h["to_agent"] == "publish_gate"
    assert h["tool_call_id"] == "request_publish_gate"


# --- Smoke: editor dispatch is exactly one handoff per call -----------------


@pytest.mark.asyncio
async def test_editor_dispatches_emit_exactly_one_handoff_per_call():
    """Sanity: chain four dispatches and confirm 4 handoffs land in order."""
    fs = FsClient()
    editor = _make_editor(fs)
    _seed_cleared_draft(fs, "draft-test-001")

    await invoke_bound_tool(editor, "dispatch_scout", scout_id="cinderella", story_unit_id="place_test_iowa")
    await invoke_bound_tool(editor, "dispatch_investigator", lead_report_id="lead-test-001")
    await invoke_bound_tool(editor, "dispatch_storyteller", investigation_packet_id="pkt-test-001")
    await invoke_bound_tool(editor, "dispatch_narrator", story_draft_id="draft-test-001")

    hs = _handoffs(fs)
    assert len(hs) == 4
    pairs = [(h["from_agent"], h["to_agent"]) for h in hs]
    assert pairs == [
        ("editor", "scout_desk"),
        ("editor", "investigator"),
        ("editor", "storyteller"),
        ("storyteller", "narrator"),
    ]
