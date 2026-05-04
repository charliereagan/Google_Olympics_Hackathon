"""End-to-end integration test: HND detector -> WireEmitter -> Firestore.

Wires the *real* `HndDetector`, *real* `WireEmitter`, and *real*
`NilRedactionLayer` (loaded from a 600-row synthetic fixture so the
fail-closed assertion at HOE-DEC-019 passes) to a stub async Firestore
client that records writes in memory.

Unlike `tests/integration/test_editor_to_wire_e2e.py`, this test does NOT
require the Firestore emulator — the Firestore async client surface area we
exercise here (`collection(name).add(doc)` returning an awaitable) is small
enough to stub faithfully in-process. That keeps the test runnable on any
checkout without extra setup, and lets CI assert the HND fire path stays
green.

Covers:
  - 3-of-4 Scouts above 0.7 confidence within the 10-minute window emits a
    single milestone Wire event with `message_type='milestone'` and message
    containing 'High Narrative Density'.
  - 2-of-4 Scouts (negative path) emits no Wire event.

Threshold + window come from HOE-DEC-023 / BUILD_SPEC §5.2.

Naming compliance: the synthetic fixture rows use non-Team-USA names
('Pelé', 'Diego Maradona', etc., per
`agents/publish_gate/test_nil_redaction_layer_stub.py`); story_unit_ids are
synthetic strings (`'test-place-iowa'`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from agents.publish_gate.nil_redaction_layer_stub import NilRedactionLayer
from agents.scouts.hnd_detector import HndDetector
from agents.wire.emit import WireEmitter


# --- Synthetic registry fixture (same pattern used elsewhere in the suite) -----


def _make_fixture_rows(n: int) -> list[dict]:
    """Build a fixture of n synthetic registry rows.

    Mirrors `agents/publish_gate/test_nil_redaction_layer_stub.py::_make_fixture_rows`
    so the NIL Layer's fail-closed assertion (≥500 rows) is satisfied
    without any Team-USA NIL ever entering the test corpus
    (PROJECT_BRIEF §5).
    """
    seeds: list[dict] = [
        {
            "full_name": "Pelé",
            "first_name": "Pelé",
            "last_name": "",
            "known_variants": ["Edson Arantes"],
        },
        {
            "full_name": "Diego Maradona",
            "first_name": "Diego",
            "last_name": "Maradona",
            "known_variants": [],
        },
        {
            "full_name": "Roger Federer",
            "first_name": "Roger",
            "last_name": "Federer",
            "known_variants": [],
        },
    ]
    while len(seeds) < n:
        i = len(seeds)
        seeds.append(
            {
                "full_name": f"Synthetic Person {i}",
                "first_name": f"Synthetic{i}",
                "last_name": f"Person{i}",
                "known_variants": [],
            }
        )
    return seeds[:n]


# --- In-memory async Firestore stub -------------------------------------------


class _StubDocRef:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _StubAsyncCollection:
    """Records `.add(doc)` calls. Returns an awaitable yielding a doc_ref —
    matches the shape `WireEmitter._write_once` expects.

    Also supports the sync `.add(doc)` shape used by the HND detector for the
    `/hnd_fires/` paper-trail write (which is allowed direct).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.added: list[dict] = []
        self._counter = 0

    def add(self, doc: dict) -> Any:
        self._counter += 1
        self.added.append(dict(doc))
        doc_id = f"{self.name}-{self._counter}"

        if self.name == "wire_events":
            # Match the google-cloud-firestore async API: returns an
            # awaitable producing (write_result, doc_ref).
            doc_ref = _StubDocRef(doc_id)

            class _Awaitable:
                def __await__(self_inner):
                    async def _coro():
                        return (None, doc_ref)
                    return _coro().__await__()

            return _Awaitable()
        # /hnd_fires/ uses the sync .add() path; no return value required.
        return None


class _StubAsyncFirestore:
    def __init__(self) -> None:
        self.collections: dict[str, _StubAsyncCollection] = {}

    def collection(self, name: str) -> _StubAsyncCollection:
        return self.collections.setdefault(name, _StubAsyncCollection(name))


# --- Helpers ------------------------------------------------------------------


class _MockClock:
    """Minimal frozen-time clock for deterministic window assertions."""

    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def advance(self, delta: timedelta) -> None:
        self.t = self.t + delta


def _report(scout: str, *, story_unit_id: str, confidence: float = 0.8) -> dict:
    return {
        "scout": scout,
        "confidence": confidence,
        "story_unit_id": story_unit_id,
    }


# --- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hnd_fires_end_to_end_three_of_four():
    """3 different Scouts on the same story_unit_id, each >=0.7, within 10min.

    Asserts the milestone Wire event lands on the stub Firestore collection
    via the real HndDetector + real WireEmitter + real NilRedactionLayer
    (loaded from a 600-row synthetic fixture).
    """
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))

    nil_layer = NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)
    assert nil_layer.is_loaded

    fs = _StubAsyncFirestore()
    emitter = WireEmitter(fs, nil_layer, clock=clock)
    det = HndDetector(firestore=fs, wire=emitter, clock=clock)

    story_unit_id = "test-place-iowa"
    await det.record_lead_report(_report("cinderella", story_unit_id=story_unit_id))
    await det.record_lead_report(_report("comeback", story_unit_id=story_unit_id))
    await det.record_lead_report(_report("hometown", story_unit_id=story_unit_id))

    # Exactly one wire_event, and it's the HND milestone.
    wire_coll = fs.collections.get("wire_events")
    assert wire_coll is not None, "no wire_events writes recorded"
    assert len(wire_coll.added) == 1, (
        f"expected 1 wire_event from HND fire, got {len(wire_coll.added)}: "
        f"{wire_coll.added}"
    )
    event = wire_coll.added[0]
    assert event["message_type"] == "milestone"
    assert "High Narrative Density" in event["message"]
    assert event["story_unit_id"] == story_unit_id
    assert event["agent"] == "scout_desk"
    assert event["mode"] == "live"
    # WireEmitter always attaches the redaction log + timestamp.
    assert "nil_redaction_log" in event
    assert "timestamp" in event

    # And the paper-trail write to /hnd_fires/ landed too.
    fires_coll = fs.collections.get("hnd_fires")
    assert fires_coll is not None
    assert len(fires_coll.added) == 1
    fire = fires_coll.added[0]
    assert fire["story_unit_id"] == story_unit_id
    assert fire["wire_event_id"]  # the doc id we returned
    assert sorted(fire["scouts"]) == ["cinderella", "comeback", "hometown"]


@pytest.mark.asyncio
async def test_hnd_does_not_fire_on_two_of_four():
    """Negative path: 2-of-4 Scouts -> no Wire event written.

    Same wiring as the positive test; the assertion is the absence of any
    `wire_events.add(...)` call.
    """
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))

    nil_layer = NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)
    fs = _StubAsyncFirestore()
    emitter = WireEmitter(fs, nil_layer, clock=clock)
    det = HndDetector(firestore=fs, wire=emitter, clock=clock)

    story_unit_id = "test-place-iowa"
    await det.record_lead_report(_report("cinderella", story_unit_id=story_unit_id))
    await det.record_lead_report(_report("comeback", story_unit_id=story_unit_id))

    # No wire_events collection should have been touched.
    wire_coll = fs.collections.get("wire_events")
    if wire_coll is not None:
        assert wire_coll.added == [], (
            f"expected zero wire_events on 2-of-4, got {wire_coll.added}"
        )
    # And no /hnd_fires/ paper-trail entry either.
    fires_coll = fs.collections.get("hnd_fires")
    if fires_coll is not None:
        assert fires_coll.added == []
