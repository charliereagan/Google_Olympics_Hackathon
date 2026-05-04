"""High Narrative Density milestone detector (HOE-DEC-023, BUILD_SPEC §5.2).

HND fires when ≥3 of 4 Scouts have written a Lead Report for the same
`story_unit_id` within a rolling 10-minute window AND each Scout's confidence
is ≥0.7. On threshold crossing, emit a single Wire `milestone`:
*"High Narrative Density: {scouts} on the same place."* Editor pivots queue
priority. Debounce per `story_unit_id`: don't refire within the same window.

The detector subscribes to Firestore `/lead_reports`. In production, that's a
server-side `on_snapshot` listener. The Firestore async SDK does not implement
`on_snapshot` (NotImplementedError), so the listener runs against the *sync*
Firestore client on a Firestore-managed thread; callbacks marshal back to the
asyncio event loop via `asyncio.run_coroutine_threadsafe`. (Plan §B,
concurrency model row for HND; §G open question 2.)

For unit tests, callers push reports via `record_lead_report()` directly —
same code path, no Firestore needed.
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
        firestore_sync: Any | None = None,
        window: timedelta = timedelta(minutes=10),
        threshold: int = 3,
        min_confidence: float = 0.7,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        # `firestore` is the async client (used for hnd_fires writes + shared
        # with WireEmitter / Editor reads). `firestore_sync` is a dedicated
        # sync client for the on_snapshot listener thread; the async SDK does
        # not implement on_snapshot. Keeping them separate avoids any
        # interaction between Firestore's async/sync internals.
        self._firestore = firestore
        self._firestore_sync = firestore_sync
        self._wire = wire
        self._window = window
        self._threshold = threshold
        self._min_confidence = min_confidence
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state: dict[str, _UnitState] = {}
        self._lock = asyncio.Lock()
        self._listener_handle: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_listener_attached(self) -> bool:
        """True if a sync on_snapshot watch handle is active. Test helper."""
        return self._listener_handle is not None

    async def start(self) -> None:
        """Open the Firestore on_snapshot listener.

        If no sync Firestore client was supplied (test stub or local dev
        without ADC), this is a no-op — tests drive `record_lead_report`
        directly.

        Otherwise: capture the running event loop, attach a sync watch on
        `/lead_reports`. Firestore's sync client runs the callback on a
        Firestore-managed thread; `_on_snapshot_callback` marshals each
        ADDED change back into the loop.
        """
        if self._firestore_sync is None:
            logger.info("hnd_detector: no sync firestore client; running in stub mode")
            return
        try:
            self._loop = asyncio.get_running_loop()
            coll = self._firestore_sync.collection("lead_reports")
            self._listener_handle = coll.on_snapshot(self._on_snapshot_callback)
            logger.info("hnd_detector: sync on_snapshot listener attached")
        except Exception:
            logger.exception("hnd_detector: failed to start listener; running in stub mode")
            self._listener_handle = None

    async def stop(self) -> None:
        if self._listener_handle is not None:
            try:
                self._listener_handle.unsubscribe()
            except Exception:
                logger.exception("hnd_detector: listener unsubscribe failed")
            self._listener_handle = None

    def _on_snapshot_callback(
        self, doc_snapshots: Any, changes: Any, _read_time: Any
    ) -> None:
        """Sync callback from Firestore SDK. Runs on a Firestore-managed
        thread — must NOT touch the event loop directly. Use
        `run_coroutine_threadsafe` against the loop captured in `start()`.

        Filter to ADDED changes so MODIFIED/REMOVED don't double-fire
        `record_lead_report`. Wrap each marshal in try/except so a single
        bad doc can't kill the listener.
        """
        loop = self._loop
        if loop is None:
            logger.warning("hnd_detector: callback fired before start(); dropping")
            return
        for change in changes or []:
            try:
                change_type = getattr(getattr(change, "type", None), "name", None)
                if change_type != "ADDED":
                    continue
                doc = change.document.to_dict()
                if not doc:
                    continue
                asyncio.run_coroutine_threadsafe(self.record_lead_report(doc), loop)
            except Exception:
                # One bad doc must not kill the watch — log and keep going.
                logger.exception("hnd_detector: failed to marshal change to loop")

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
        wire_event_id: str | None = None
        try:
            wire_event_id = await self._wire.emit(event)
            logger.info(
                "hnd_detector: fired for story_unit_id=%s scouts=%s wire_event_id=%s",
                story_unit_id, scouts_str, wire_event_id,
            )
        except Exception:
            logger.exception("hnd_detector: wire.emit failed for HND fire")
            # Don't return — still record the fire to /hnd_fires/ with
            # wire_event_id=None so we have a paper trail of the threshold
            # crossing even when the Wire is degraded.
        # Record the fire to /hnd_fires/{id} (best-effort, not blocking).
        # /hnd_fires/ is NOT a Wire collection — direct .add() is allowed
        # here (lint excludes hnd_fires).
        try:
            if self._firestore is not None and hasattr(self._firestore, "collection"):
                self._firestore.collection("hnd_fires").add(
                    {
                        "story_unit_id": story_unit_id,
                        "scouts": scouts,
                        "fired_at": now.isoformat(),
                        "wire_event_id": wire_event_id,
                    }
                )
        except Exception:
            logger.exception("hnd_detector: hnd_fires write failed (non-fatal)")
