"""Unit tests for HndDetector.

Plan §F lists 5 cases:
  1. Fires on 3-of-4 above threshold.
  2. Does not fire on 2-of-4.
  3. Does not fire on low-confidence (4 reports all at 0.6).
  4. Window expiry (old reports drop out).
  5. Debounce per unit (re-trigger within window does nothing).

Listener-wiring cases (Plan §B concurrency, §G open question 2):
  6. start() is a no-op when no sync client is supplied.
  7. start() attaches an on_snapshot listener when a sync client is supplied.
  8. The on_snapshot callback marshals docs into the asyncio loop from a
     non-loop thread (the production case).
  9. _fire writes to /hnd_fires/ with wire_event_id=None when wire.emit
     fails (covers the buggy `dir()` expression).
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from agents.scouts.hnd_detector import HndDetector


class _MockClock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def advance(self, delta: timedelta) -> None:
        self.t = self.t + delta


class _RecordingWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return f"evt-{len(self.emitted)}"


def _report(scout: str, confidence: float, story_unit_id: str = "us-ia-mt-pleasant") -> dict:
    return {
        "scout": scout,
        "confidence": confidence,
        "story_unit_id": story_unit_id,
    }


@pytest.mark.asyncio
async def test_fires_on_three_of_four_above_threshold():
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    await det.record_lead_report(_report("cinderella", 0.8))
    await det.record_lead_report(_report("hometown", 0.8))
    await det.record_lead_report(_report("echo", 0.8))

    assert len(wire.emitted) == 1
    assert wire.emitted[0]["message_type"] == "milestone"
    assert "High Narrative Density" in wire.emitted[0]["message"]
    assert wire.emitted[0]["story_unit_id"] == "us-ia-mt-pleasant"


@pytest.mark.asyncio
async def test_does_not_fire_on_two_of_four():
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    await det.record_lead_report(_report("cinderella", 0.8))
    await det.record_lead_report(_report("hometown", 0.8))

    assert len(wire.emitted) == 0


@pytest.mark.asyncio
async def test_does_not_fire_on_low_confidence():
    """4 reports all at 0.6 — below the 0.7 threshold — no fire."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    for s in ("cinderella", "hometown", "echo", "comeback"):
        await det.record_lead_report(_report(s, 0.6))

    assert len(wire.emitted) == 0


@pytest.mark.asyncio
async def test_window_expiry():
    """Two reports at t=0; advance to t=11min; third report — no fire (older 2 expired)."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    await det.record_lead_report(_report("cinderella", 0.8))
    await det.record_lead_report(_report("hometown", 0.8))
    clock.advance(timedelta(minutes=11))
    await det.record_lead_report(_report("echo", 0.8))

    assert len(wire.emitted) == 0


@pytest.mark.asyncio
async def test_debounce_per_unit():
    """After firing, additional high-confidence reports within the window
    do not refire."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    await det.record_lead_report(_report("cinderella", 0.8))
    await det.record_lead_report(_report("hometown", 0.8))
    await det.record_lead_report(_report("echo", 0.8))
    assert len(wire.emitted) == 1

    # Add more reports within the window — no second fire.
    clock.advance(timedelta(minutes=5))
    await det.record_lead_report(_report("comeback", 0.9))
    await det.record_lead_report(_report("cinderella", 0.95))
    assert len(wire.emitted) == 1


# --- Listener-wiring tests ----------------------------------------------------


class _StubWatchHandle:
    def __init__(self) -> None:
        self.unsubscribed = False

    def unsubscribe(self) -> None:
        self.unsubscribed = True


class _StubSyncCollection:
    def __init__(self) -> None:
        self.callback: Any = None
        self.handle = _StubWatchHandle()

    def on_snapshot(self, callback: Any) -> _StubWatchHandle:
        self.callback = callback
        return self.handle


class _StubSyncFirestore:
    """Minimal sync Firestore client stub for listener wiring tests."""

    def __init__(self) -> None:
        self.collections: dict[str, _StubSyncCollection] = {}

    def collection(self, name: str) -> _StubSyncCollection:
        return self.collections.setdefault(name, _StubSyncCollection())


class _StubDocSnapshot:
    def __init__(self, data: dict) -> None:
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


class _StubChange:
    def __init__(self, data: dict, type_name: str = "ADDED") -> None:
        self.document = _StubDocSnapshot(data)
        # Mimic Firestore SDK: change.type.name is "ADDED"|"MODIFIED"|"REMOVED".
        self.type = SimpleNamespace(name=type_name)


@pytest.mark.asyncio
async def test_start_no_op_when_no_sync_client():
    """No sync client → start() returns cleanly; no listener attached."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    det = HndDetector(firestore=None, wire=wire, clock=clock)

    await det.start()
    assert det.is_listener_attached is False


@pytest.mark.asyncio
async def test_start_attaches_listener():
    """A sync client whose collection exposes on_snapshot → handle stored."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    fs_sync = _StubSyncFirestore()
    det = HndDetector(
        firestore=None, firestore_sync=fs_sync, wire=wire, clock=clock,
    )

    await det.start()

    coll = fs_sync.collections["lead_reports"]
    assert coll.callback is not None, "on_snapshot callback should be registered"
    assert det.is_listener_attached is True

    # And stop() unsubscribes cleanly.
    await det.stop()
    assert coll.handle.unsubscribed is True
    assert det.is_listener_attached is False


@pytest.mark.asyncio
async def test_callback_marshals_to_loop():
    """Invoke the captured on_snapshot callback from a separate thread with
    three ADDED changes and verify record_lead_report runs on the loop —
    enough to fire HND. This covers the production path: Firestore's sync
    client runs the callback on its own thread, and we marshal back via
    run_coroutine_threadsafe against the loop captured in start()."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _RecordingWire()
    fs_sync = _StubSyncFirestore()
    det = HndDetector(
        firestore=None, firestore_sync=fs_sync, wire=wire, clock=clock,
    )
    await det.start()
    callback = fs_sync.collections["lead_reports"].callback
    assert callback is not None

    fired = asyncio.Event()

    # Wrap wire.emit so the test can synchronize on the fire.
    real_emit = wire.emit

    async def _tracking_emit(event: dict, *, investigation_id: str | None = None) -> str:
        result = await real_emit(event, investigation_id=investigation_id)
        fired.set()
        return result

    wire.emit = _tracking_emit  # type: ignore[assignment]

    changes = [
        _StubChange({"scout": "cinderella", "confidence": 0.8,
                     "story_unit_id": "us-ia-mt-pleasant"}),
        _StubChange({"scout": "hometown", "confidence": 0.85,
                     "story_unit_id": "us-ia-mt-pleasant"}),
        _StubChange({"scout": "echo", "confidence": 0.9,
                     "story_unit_id": "us-ia-mt-pleasant"}),
        # MODIFIED must be ignored — would otherwise look like a 4th scout.
        _StubChange({"scout": "comeback", "confidence": 0.95,
                     "story_unit_id": "us-ia-mt-pleasant"},
                    type_name="MODIFIED"),
    ]

    def _fire_from_thread() -> None:
        # Mimic Firestore's sync SDK invoking the callback on its own thread.
        callback(None, changes, None)

    thread = threading.Thread(target=_fire_from_thread)
    thread.start()
    thread.join(timeout=2.0)

    # Wait for the marshalled coroutines to complete on this event loop.
    await asyncio.wait_for(fired.wait(), timeout=2.0)

    assert len(wire.emitted) == 1
    emitted = wire.emitted[0]
    assert emitted["message_type"] == "milestone"
    assert "High Narrative Density" in emitted["message"]
    assert emitted["story_unit_id"] == "us-ia-mt-pleasant"


class _ExplodingWire:
    """Wire stub whose emit() always raises — simulates a Wire outage."""

    def __init__(self) -> None:
        self.emit_calls = 0

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emit_calls += 1
        raise RuntimeError("simulated wire outage")


class _RecordingFirestore:
    """Async-shaped Firestore stub that records hnd_fires writes."""

    class _Coll:
        def __init__(self) -> None:
            self.added: list[dict] = []

        def add(self, doc: dict) -> None:
            self.added.append(dict(doc))

    def __init__(self) -> None:
        self._collections: dict[str, _RecordingFirestore._Coll] = {}

    def collection(self, name: str) -> "_RecordingFirestore._Coll":
        return self._collections.setdefault(name, _RecordingFirestore._Coll())


@pytest.mark.asyncio
async def test_fire_handles_wire_emit_failure_then_writes_hnd_fires_with_none_id():
    """If wire.emit fails, the detector still records the threshold crossing
    in /hnd_fires/ with wire_event_id=None — ensures the previously buggy
    `wire_event_id if "wire_event_id" in dir() else None` expression is
    fixed and the local is always defined."""
    clock = _MockClock(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc))
    wire = _ExplodingWire()
    fs = _RecordingFirestore()
    det = HndDetector(firestore=fs, wire=wire, clock=clock)

    await det.record_lead_report(_report("cinderella", 0.8))
    await det.record_lead_report(_report("hometown", 0.8))
    await det.record_lead_report(_report("echo", 0.8))

    assert wire.emit_calls == 1
    fires = fs._collections["hnd_fires"].added
    assert len(fires) == 1
    fire = fires[0]
    assert fire["story_unit_id"] == "us-ia-mt-pleasant"
    assert fire["wire_event_id"] is None
    assert sorted(fire["scouts"]) == ["cinderella", "echo", "hometown"]
