"""Unit tests for `agents.handoffs.emit_handoff`.

Covers:
  1. Valid 7-agent enum -> doc written with correct fields.
  2. Invalid agent name -> raises ValueError BEFORE any Firestore call.
  3. Invalid mode -> raises ValueError BEFORE any Firestore call.
  4. Empty/non-string tool_call_id -> raises ValueError.
  5. Timestamp is UTC ISO 8601.
  6. Returned doc id is non-empty.
  7. `safe_emit_handoff` swallows runtime errors (returns None) but
     re-raises ValueErrors so programmer errors aren't masked.
  8. emit_handoff with firestore=None raises RuntimeError pre-write.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from agents.handoffs import (
    AGENT_IDS,
    COLLECTION_NAME,
    emit_handoff,
    safe_emit_handoff,
)


# --- Test doubles -----------------------------------------------------------


class _FakeDocRef:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _FakeCollection:
    def __init__(self, parent: "_FakeFirestore", name: str) -> None:
        self._parent = parent
        self._name = name

    def add(self, doc: dict):
        self._parent.write_calls.append((self._name, dict(doc)))
        idx = len(self._parent.write_calls)
        ref = _FakeDocRef(doc_id=f"handoff-{idx}")

        async def _result():
            return (None, ref)

        return _result()


class _FakeFirestore:
    """Minimal async-shaped Firestore stub matching the WireEmitter pattern."""

    def __init__(self) -> None:
        self.write_calls: list[tuple[str, dict]] = []

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self, name)


class _ExplodingCollection:
    def add(self, doc: dict):
        raise RuntimeError("simulated firestore failure")


class _ExplodingFirestore:
    def collection(self, name: str) -> _ExplodingCollection:  # noqa: ARG002
        return _ExplodingCollection()


# --- Tests ------------------------------------------------------------------


_ISO_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$"
)


@pytest.mark.asyncio
async def test_emit_handoff_writes_correct_doc_for_valid_agents():
    fs = _FakeFirestore()

    doc_id = await emit_handoff(
        fs,
        from_agent="editor",
        to_agent="investigator",
        tool_call_id="dispatch_investigator",
        story_unit_id="place_test_iowa",
        investigation_id="inv-abc",
    )

    assert doc_id == "handoff-1"
    assert len(fs.write_calls) == 1
    coll_name, doc = fs.write_calls[0]
    assert coll_name == COLLECTION_NAME
    assert doc["from_agent"] == "editor"
    assert doc["to_agent"] == "investigator"
    assert doc["tool_call_id"] == "dispatch_investigator"
    assert doc["story_unit_id"] == "place_test_iowa"
    assert doc["investigation_id"] == "inv-abc"
    assert doc["mode"] == "live"
    assert _ISO_UTC_RE.match(doc["timestamp"]), (
        f"timestamp {doc['timestamp']!r} is not UTC ISO 8601"
    )


@pytest.mark.asyncio
async def test_emit_handoff_defaults_optional_fields_to_none():
    fs = _FakeFirestore()

    await emit_handoff(
        fs,
        from_agent="editor",
        to_agent="scout_desk",
        tool_call_id="dispatch_scout",
    )

    _, doc = fs.write_calls[0]
    assert doc["story_unit_id"] is None
    assert doc["investigation_id"] is None
    assert doc["mode"] == "live"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "from_agent,to_agent",
    [
        ("not_an_agent", "investigator"),
        ("editor", "ghost_agent"),
        ("", "investigator"),
        ("editor", ""),
    ],
)
async def test_emit_handoff_invalid_agent_raises_before_firestore_call(
    from_agent: str,
    to_agent: str,
):
    fs = _FakeFirestore()

    with pytest.raises(ValueError):
        await emit_handoff(
            fs,
            from_agent=from_agent,
            to_agent=to_agent,
            tool_call_id="dispatch_investigator",
        )

    # Critical: no Firestore write happened.
    assert fs.write_calls == []


@pytest.mark.asyncio
async def test_emit_handoff_invalid_mode_raises():
    fs = _FakeFirestore()

    with pytest.raises(ValueError):
        await emit_handoff(
            fs,
            from_agent="editor",
            to_agent="investigator",
            tool_call_id="dispatch_investigator",
            mode="archived",  # not a valid mode
        )

    assert fs.write_calls == []


@pytest.mark.asyncio
async def test_emit_handoff_empty_tool_call_id_raises():
    fs = _FakeFirestore()

    with pytest.raises(ValueError):
        await emit_handoff(
            fs,
            from_agent="editor",
            to_agent="investigator",
            tool_call_id="",
        )

    assert fs.write_calls == []


@pytest.mark.asyncio
async def test_emit_handoff_none_firestore_raises_runtime_error():
    with pytest.raises(RuntimeError):
        await emit_handoff(
            None,
            from_agent="editor",
            to_agent="investigator",
            tool_call_id="dispatch_investigator",
        )


@pytest.mark.asyncio
async def test_emit_handoff_returned_id_is_non_empty():
    fs = _FakeFirestore()

    doc_id = await emit_handoff(
        fs,
        from_agent="editor",
        to_agent="investigator",
        tool_call_id="dispatch_investigator",
    )

    assert isinstance(doc_id, str)
    assert doc_id  # non-empty


@pytest.mark.asyncio
async def test_emit_handoff_timestamp_is_close_to_now():
    fs = _FakeFirestore()

    before = datetime.now(timezone.utc)
    await emit_handoff(
        fs,
        from_agent="editor",
        to_agent="storyteller",
        tool_call_id="dispatch_storyteller",
    )
    after = datetime.now(timezone.utc)

    _, doc = fs.write_calls[0]
    ts = datetime.fromisoformat(doc["timestamp"])
    assert before <= ts <= after


@pytest.mark.asyncio
async def test_emit_handoff_supports_replay_and_published_modes():
    fs = _FakeFirestore()

    for mode in ("live", "replay", "published"):
        await emit_handoff(
            fs,
            from_agent="editor",
            to_agent="storyteller",
            tool_call_id="dispatch_storyteller",
            mode=mode,
        )

    assert [doc["mode"] for _, doc in fs.write_calls] == [
        "live",
        "replay",
        "published",
    ]


def test_agent_ids_match_seven_cast():
    """The handoff enum must mirror `agents/wire/types.py::AgentId`."""
    expected = {
        "editor",
        "scout_desk",
        "investigator",
        "equity_editor",
        "storyteller",
        "narrator",
        "publish_gate",
    }
    assert AGENT_IDS == expected


# --- safe_emit_handoff ------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_emit_handoff_swallows_runtime_failures_and_returns_none():
    fs = _ExplodingFirestore()

    doc_id = await safe_emit_handoff(
        fs,
        from_agent="editor",
        to_agent="investigator",
        tool_call_id="dispatch_investigator",
    )

    assert doc_id is None  # transient failure -> None, no raise


@pytest.mark.asyncio
async def test_safe_emit_handoff_re_raises_value_errors():
    fs = _FakeFirestore()

    # Programmer errors must NOT be swallowed.
    with pytest.raises(ValueError):
        await safe_emit_handoff(
            fs,
            from_agent="not_an_agent",
            to_agent="investigator",
            tool_call_id="dispatch_investigator",
        )


@pytest.mark.asyncio
async def test_safe_emit_handoff_returns_doc_id_on_success():
    fs = _FakeFirestore()

    doc_id = await safe_emit_handoff(
        fs,
        from_agent="storyteller",
        to_agent="publish_gate",
        tool_call_id="request_publish_gate",
    )

    assert doc_id == "handoff-1"
    assert len(fs.write_calls) == 1
