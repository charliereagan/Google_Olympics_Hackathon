"""Unit tests for HndDetector.

Plan §F lists 5 cases:
  1. Fires on 3-of-4 above threshold.
  2. Does not fire on 2-of-4.
  3. Does not fire on low-confidence (4 reports all at 0.6).
  4. Window expiry (old reports drop out).
  5. Debounce per unit (re-trigger within window does nothing).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
