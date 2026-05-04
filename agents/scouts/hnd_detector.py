"""High Narrative Density milestone detector (HOE-DEC-023, BUILD_SPEC §5.2).

HND fires when ≥3 of 4 Scouts have written a Lead Report for the same
`story_unit_id` within a rolling 10-minute window AND each Scout's confidence
is ≥0.7. On threshold crossing, emit a single Wire `milestone`:
*"High Narrative Density: {scouts} on the same place."* Editor pivots queue
priority. Debounce per `story_unit_id`: don't refire within the same window.

The detector subscribes to Firestore `/lead_reports`. In production, that's a
server-side `on_snapshot` listener. For unit tests, callers push reports via
`record_lead_report()` directly — same code path, no Firestore needed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from agents.wire.types import LeadReport, SubAgentId, WireEvent

logger = logging.getLogger(__name__)


@dataclass
class _UnitState:
    """Per-`story_unit_id` rolling state."""

    scouts: dict[SubAgentId, tuple[float, datetime]] = field(default_factory=dict)
    fired_until: datetime | None = None


class HndDetector:
    """Watches Lead Reports and emits High Narrative Density milestones."""

    def __init__(
        self,
        *,
        firestore: Any,
        wire: Any,
        window: timedelta = timedelta(minutes=10),
        threshold: int = 3,
        min_confidence: float = 0.7,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._firestore = firestore
        self._wire = wire
        self._window = window
        self._threshold = threshold
        self._min_confidence = min_confidence
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state: dict[str, _UnitState] = {}
        self._lock = asyncio.Lock()
        self._listener_handle: Any = None

    async def start(self) -> None:
        """Open the Firestore on_snapshot listener.

        In Day-2, if `firestore` doesn't support on_snapshot (test stub),
        this is a no-op. Tests drive `record_lead_report` directly.
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            logger.info("hnd_detector: no firestore listener (stub mode)")
            return
        try:
            coll = self._firestore.collection("lead_reports")
            # The Firestore Admin SDK's sync watch handle: attach on a thread,
            # marshal callbacks back to the event loop. For Day-2 we punt the
            # actual subscription wiring to runtime.py; this method just
            # records the intent.
            on_snapshot = getattr(coll, "on_snapshot", None)
            if on_snapshot is None:
                logger.info("hnd_detector: collection lacks on_snapshot; stub mode")
                return
            self._listener_handle = on_snapshot(self._on_snapshot_callback)
            logger.info("hnd_detector: listener attached")
        except Exception:
            logger.exception("hnd_detector: failed to start listener; running in stub mode")

    async def stop(self) -> None:
        if self._listener_handle is not None:
            try:
                self._listener_handle.unsubscribe()
            except Exception:
                logger.exception("hnd_detector: listener unsubscribe failed")
            self._listener_handle = None

    def _on_snapshot_callback(self, doc_snapshots: Any, changes: Any, _read_time: Any) -> None:
        """Sync callback from Firestore SDK. Marshal to the event loop."""
        loop = asyncio.get_event_loop()
        for change in changes or []:
            try:
                doc = change.document.to_dict()
            except Exception:
                continue
            asyncio.run_coroutine_threadsafe(self.record_lead_report(doc), loop)

    async def record_lead_report(self, report: dict | LeadReport) -> None:
        """Public: feed a Lead Report into the detector.

        Tests call this directly. Production does too via the Firestore
        listener callback (above).
        """
        if isinstance(report, LeadReport):
            story_unit_id = report.story_unit_id
            scout = report.scout
            confidence = report.confidence
        else:
            story_unit_id = report.get("story_unit_id")
            scout = report.get("scout")
            confidence = float(report.get("confidence", 0.0))
        if not story_unit_id or not scout:
            return

        now = self._clock()
        async with self._lock:
            unit = self._state.setdefault(story_unit_id, _UnitState())
            self._prune(unit, now)

            # Record this scout's latest confidence + timestamp.
            unit.scouts[scout] = (confidence, now)

            # Debounced? Skip the firing logic but still keep state fresh.
            if unit.fired_until is not None and now < unit.fired_until:
                return

            qualifying = [s for s, (c, _) in unit.scouts.items() if c >= self._min_confidence]
            if len(qualifying) < self._threshold:
                return

            # Fire.
            scouts_list = sorted(qualifying)
            unit.fired_until = now + self._window
        # Release the lock BEFORE awaiting wire.emit — wire.emit may itself
        # call back into the detector (e.g., re-record an event); we don't
        # want a deadlock.
        await self._fire(story_unit_id, scouts_list, now)

    def _prune(self, unit: _UnitState, now: datetime) -> None:
        cutoff = now - self._window
        unit.scouts = {s: (c, t) for s, (c, t) in unit.scouts.items() if t >= cutoff}

    async def _fire(self, story_unit_id: str, scouts: list[str], now: datetime) -> None:
        scouts_str = " + ".join(scouts)
        event: WireEvent = {
            "agent": "scout_desk",
            "message_type": "milestone",
            "message": f"High Narrative Density: {scouts_str} on the same place.",
            "story_unit_id": story_unit_id,
            "mode": "live",
        }
        try:
            wire_event_id = await self._wire.emit(event)
            logger.info(
                "hnd_detector: fired for story_unit_id=%s scouts=%s wire_event_id=%s",
                story_unit_id, scouts_str, wire_event_id,
            )
        except Exception:
            logger.exception("hnd_detector: wire.emit failed for HND fire")
            return
        # Record the fire to /hnd_fires/{id} (best-effort, not blocking).
        try:
            if self._firestore is not None and hasattr(self._firestore, "collection"):
                self._firestore.collection("hnd_fires").add(
                    {
                        "story_unit_id": story_unit_id,
                        "scouts": scouts,
                        "fired_at": now.isoformat(),
                        "wire_event_id": wire_event_id if "wire_event_id" in dir() else None,
                    }
                )
        except Exception:
            logger.exception("hnd_detector: hnd_fires write failed (non-fatal)")
