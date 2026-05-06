"""Day-11 R1 regression test — emit() applies the FULL disambiguation Layer.

The Day-4 over-redaction bug surfaced as `[redacted]la [redacted]ta` (Chula
Vista) and `[redacted] Placid` (Lake Placid) on the live wire feed. The
fix landed Day-7: `agents/publish_gate/nil_redaction_layer.py` runs the
full disambiguation pipeline (min_needle_length, word-boundary discipline,
50-char sport-context window for common given names) inside
`_direct_match_and_disambiguate`, and `_scan_wire_only` calls it.

This test is the integration guard that the wire emit path
(`agents.wire.emit.WireEmitter.emit`) actually invokes the FULL Layer —
not just a surface-match-only stub. We synthesize a registry whose short
needles ('la', 'Vis', 'lac', 'ake') would substring-match inside both
'Chula Vista' and 'Lake Placid' if disambiguation were skipped, then
route a wire event through `WireEmitter.emit` and assert the final
Firestore-bound `message` is unchanged (decision='pass') and the
disambiguation rejection counters fired.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agents.publish_gate.nil_redaction_layer import NilRedactionLayer
from agents.wire.emit import WireEmitter


# --- Test doubles -------------------------------------------------------------


def _make_registry_rows(n: int, *, seeds: list[dict]) -> list[dict]:
    """Synthetic registry: caller's seeds + filler to clear min_rows=500.

    The filler names are intentionally distinctive and absent from the
    test sentences so they cannot accidentally fire a match.
    """
    rows = list(seeds)
    while len(rows) < n:
        i = len(rows)
        rows.append(
            {
                "full_name": f"Synthetic Person {i}",
                "first_name": f"Synthetic{i}",
                "last_name": f"Person{i}",
                "known_variants": [],
            }
        )
    return rows[:n]


class _FakeDocRef:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _FakeCollection:
    def __init__(self, parent: "_FakeFirestore", name: str) -> None:
        self._parent = parent
        self._name = name

    def add(self, doc: dict) -> Any:
        self._parent.write_calls.append((self._name, doc))

        async def _ok():
            return (None, _FakeDocRef(f"doc-{len(self._parent.write_calls)}"))

        return _ok()


class _FakeFirestore:
    def __init__(self) -> None:
        self.write_calls: list[tuple[str, dict]] = []

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self, name)


# --- Tests --------------------------------------------------------------------


def test_emit_invokes_full_layer_chula_vista_passes_clean():
    """A wire event mentioning 'Chula Vista' must NOT be over-redacted.

    Registry seeds short needles ('la', 'Vis') that would substring-match
    inside 'Chula Vista' if `wire.emit` called a surface-match-only stub.
    With the full Layer routed through emit (the production path), the
    disambiguation pass rejects them on min_needle_length + word-boundary
    grounds and the message lands clean.
    """
    rows = _make_registry_rows(
        600,
        seeds=[
            {"full_name": "la", "first_name": "la", "last_name": "", "known_variants": []},
            {"full_name": "Vis", "first_name": "Vis", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    fs = _FakeFirestore()
    emitter = WireEmitter(firestore=fs, nil_layer=layer)

    event = {
        "agent": "scout_desk",
        "message": "Dispatching Echo scout to Chula Vista. Checking historical patterns.",
        "message_type": "decision",
    }

    doc_id = asyncio.run(emitter.emit(event))

    assert doc_id == "doc-1"
    assert len(fs.write_calls) == 1
    written = fs.write_calls[0][1]
    # The full disambiguation Layer must have spared 'Chula Vista'.
    assert "[redacted]" not in written["message"], (
        f"Chula Vista was over-redacted: {written['message']!r}. "
        "This means emit.py is NOT routing through the full disambiguation "
        "Layer (over-redaction regression — see Day-7 patch)."
    )
    assert "Chula Vista" in written["message"]
    # The redaction log must record zero direct matches (they were all rejected).
    log = written.get("nil_redaction_log", {})
    assert log.get("direct_matches_redacted", 0) == 0


def test_emit_invokes_full_layer_lake_placid_passes_clean():
    """A wire event mentioning 'Lake Placid' must NOT be over-redacted.

    Day-4 substring bug rewrote 'Lake Placid' as '[redacted] [redacted]'.
    Seeds short needles that would substring-match inside both words; the
    full Layer's word-boundary + min_needle_length checks must reject them.
    """
    rows = _make_registry_rows(
        600,
        seeds=[
            {"full_name": "lac", "first_name": "lac", "last_name": "", "known_variants": []},
            {"full_name": "ake", "first_name": "ake", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    fs = _FakeFirestore()
    emitter = WireEmitter(firestore=fs, nil_layer=layer)

    event = {
        "agent": "investigator",
        "message": "Pulling sources for Lake Placid 1980 modernization arc.",
        "message_type": "thinking",
    }

    asyncio.run(emitter.emit(event))

    written = fs.write_calls[0][1]
    assert "[redacted]" not in written["message"], (
        f"Lake Placid was over-redacted: {written['message']!r}. "
        "emit.py is not invoking the full Layer."
    )
    assert "Lake Placid" in written["message"]
    log = written.get("nil_redaction_log", {})
    assert log.get("direct_matches_redacted", 0) == 0


def test_emit_invokes_full_layer_distinctive_name_still_redacts():
    """Belt-and-suspenders: the full Layer still redacts a distinctive
    long needle. Confirms the test isn't passing because emit silently
    skipped scanning entirely."""
    rows = _make_registry_rows(
        600,
        seeds=[
            {
                "full_name": "Wexlonia Fertingdale",
                "first_name": "Wexlonia",
                "last_name": "Fertingdale",
                "known_variants": [],
            },
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    fs = _FakeFirestore()
    emitter = WireEmitter(firestore=fs, nil_layer=layer)

    event = {
        "agent": "storyteller",
        "message": "The story rhymes with Wexlonia Fertingdale's arc.",
        "message_type": "thinking",
    }

    asyncio.run(emitter.emit(event))

    written = fs.write_calls[0][1]
    assert "[redacted]" in written["message"], (
        "Distinctive long name was NOT redacted — emit may have bypassed "
        "the Layer entirely."
    )
    assert "Wexlonia" not in written["message"]
    log = written.get("nil_redaction_log", {})
    assert log.get("direct_matches_redacted", 0) >= 1
