"""The Wire-emit write-through proxy.

This module is the SINGLE legitimate path for any agent to write a
`wire_events` document. CI lint (`scripts/lint_no_direct_wire_writes.py`)
flags any direct firestore.add('wire_events', ...) elsewhere in `/agents/`.

Per HOE-DEC-018: every Wire emit must route through here so the NIL Redaction
Layer can scan + redact in-process before the Firestore write. The Layer is
called SYNCHRONOUSLY and the message is mutated in place; redaction never
happens after the write.

Per HOE-DEC-019 (fail-closed): if the NIL Layer is not loaded, the proxy
raises and refuses to write. The runtime treats this as a fatal-at-boot
condition.

This file is whitelisted by `scripts/lint_no_direct_wire_writes.py:_is_proxy_file`.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Iterable

from agents.wire.types import (
    AgentId,
    NilRedactionLog,
    SubAgentId,
    WireEvent,
)

logger = logging.getLogger(__name__)


class WireProxyNotReadyError(RuntimeError):
    """Raised when emit() is called before the NIL Layer has loaded.

    The runtime catches this at boot to exit 1; agent loops catch it to
    skip the current think-cycle without crashing.
    """


# Per HOE-DEC-019: refresh failures preserve the prior automaton, but if the
# very first bootstrap never completed, the proxy fails closed.
_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 4.0, 16.0)
_RING_BUFFER_MAXLEN = 100


class WireEmitter:
    """The in-process write-through proxy.

    Args:
        firestore: an async-capable Firestore client (real or stub). The
            stub used in unit tests just needs a `collection(name).add(doc)`
            shape that returns an awaitable producing a doc id.
        nil_layer: the NilRedactionLayer (or stub) — must expose `is_loaded`
            and `scan_wire(text, surface=, context=)`.
        fail_closed: per HOE-DEC-019, defaults True. The proxy refuses to
            write if `nil_layer.is_loaded is False`. Tests may set False to
            exercise unhappy paths.
        clock: callable returning timezone-aware `datetime`. Defaults to
            `datetime.now(timezone.utc)`. Override in tests.
    """

    def __init__(
        self,
        firestore: Any,
        nil_layer: Any,
        *,
        fail_closed: bool = True,
        clock: Any = None,
        retry_backoff_seconds: Iterable[float] = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._firestore = firestore
        self._nil = nil_layer
        self._fail_closed = fail_closed
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._retry_backoff = tuple(retry_backoff_seconds)
        self._ring: "deque[WireEvent]" = deque(maxlen=_RING_BUFFER_MAXLEN)

    @property
    def is_ready(self) -> bool:
        """True if the NIL Layer has loaded; the SSE bridge gates on this."""
        return bool(getattr(self._nil, "is_loaded", False))

    # -- Public emit API -----------------------------------------------------

    async def emit(
        self,
        event: WireEvent,
        *,
        investigation_id: str | None = None,
    ) -> str:
        """Scan + write a single Wire event. Returns the Firestore doc id.

        The flow:
          1. If the NIL Layer is not loaded, raise WireProxyNotReadyError
             (defense in depth — `/health/nil` already 503s, but we don't
             trust the SSE bridge to be the only gate).
          2. Call `nil_layer.scan_wire(message, surface='wire', context=...)`
             SYNCHRONOUSLY. The Layer's API is sync; we don't await it.
          3. If `decision == 'redact'`, replace `event['message']` with the
             redacted text. Attach `nil_redaction_log`.
          4. Stamp `timestamp = utcnow()` (real wall-clock per HOE-DEC-021).
          5. Write to Firestore. Retry 3× with backoff per BUILD_SPEC §17.3.
          6. Drain the ring buffer of any pending events from prior failures.
        """
        if self._fail_closed and not self.is_ready:
            raise WireProxyNotReadyError(
                "NIL Redaction Layer not loaded — Wire emit refused (HOE-DEC-019)"
            )

        # --- NIL scan (synchronous, in-process) ---
        message = event.get("message", "")
        ctx = {"investigation_id": investigation_id, "story_unit_id": event.get("story_unit_id")}
        scan = self._nil.scan_wire(message, surface="wire", context=ctx)

        if scan.decision == "redact":
            event["message"] = scan.redacted_message
        # `aggregate` decision arrives in Day-6/7 work; today the stub never
        # returns it, but the codepath is symmetric.
        elif scan.decision == "aggregate":
            event["message"] = scan.redacted_message

        # Attach the redaction log to the event document.
        log_dict: NilRedactionLog = {
            "direct_matches_redacted": scan.log.direct_matches_redacted,
            "aggregations_applied": scan.log.aggregations_applied,
        }
        event["nil_redaction_log"] = log_dict

        # --- Stamp timestamp (real wall clock) ---
        event["timestamp"] = self._clock().isoformat()

        # --- Default fields the agent may have omitted ---
        event.setdefault("mode", "live")
        event.setdefault("compression_factor", 1.0)
        if investigation_id is not None and "investigation_id" not in event:
            event["investigation_id"] = investigation_id

        # --- Write with retry ---
        doc_id = await self._write_with_retry(event)

        # --- Drain any buffered events from prior failures ---
        await self._drain_ring()

        return doc_id

    async def emit_handoff(
        self,
        src: AgentId,
        dst: AgentId,
        *,
        story_unit_id: str | None = None,
        investigation_id: str | None = None,
        sub_agent: SubAgentId | None = None,
    ) -> str:
        """Convenience: emit a 'handoff' decision event between two agents."""
        event: WireEvent = {
            "agent": src,
            "message": f"handoff -> {dst}",
            "message_type": "decision",
            "mode": "live",
        }
        if sub_agent is not None:
            event["sub_agent"] = sub_agent
        if story_unit_id is not None:
            event["story_unit_id"] = story_unit_id
        return await self.emit(event, investigation_id=investigation_id)

    # -- Internals -----------------------------------------------------------

    def _collection_path(self) -> str:
        """The Firestore collection path. Hook for Day-9 sub-collection sharding."""
        return "wire_events"

    async def _write_with_retry(self, event: WireEvent) -> str:
        """Write with exponential backoff. On final failure, buffer + raise."""
        last_exc: Exception | None = None
        for attempt, backoff in enumerate(self._retry_backoff, start=1):
            try:
                return await self._write_once(event)
            except Exception as e:
                last_exc = e
                logger.warning(
                    "wire.emit: Firestore write failed on attempt %d/%d: %s",
                    attempt, len(self._retry_backoff), e,
                )
                # Don't sleep after the final attempt.
                if attempt < len(self._retry_backoff):
                    await asyncio.sleep(backoff)

        # All retries exhausted: buffer the event so the next successful emit
        # can drain it, log ERROR, and re-raise so the caller knows.
        self._ring.append(event)
        logger.error(
            "wire.emit: all %d retries exhausted; event buffered (ring size=%d)",
            len(self._retry_backoff), len(self._ring),
        )
        assert last_exc is not None
        raise last_exc

    async def _write_once(self, event: WireEvent) -> str:
        """One Firestore write. Returns the doc id.

        We support three async-Firestore client shapes:
          - `collection(name).add(doc)` returns an awaitable producing a tuple
            `(write_result, doc_ref)` — the google-cloud-firestore async API.
          - Or returns just `doc_ref` directly (some stubs).
          - Or returns a coroutine that yields a doc id string directly.
        """
        # NOTE: this is the ONE legitimate `.collection('wire_events')` write
        # path in the entire `/agents/` tree. The lint script whitelists this
        # exact file via `_is_proxy_file`.
        coll = self._firestore.collection(self._collection_path())
        result = coll.add(dict(event))
        # Some clients return a coroutine; others return an awaitable result.
        if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
            result = await result
        # google-cloud-firestore async returns (write_result, doc_ref).
        if isinstance(result, tuple) and len(result) >= 2:
            doc_ref = result[1]
            return getattr(doc_ref, "id", str(doc_ref))
        # Stubs may return a doc_ref directly or a string id.
        if hasattr(result, "id"):
            return str(result.id)
        return str(result)

    async def _drain_ring(self) -> None:
        """If the ring buffer has any events from prior failures, emit them.

        Best-effort. We don't recursively retry; if these fail again they go
        back on the buffer.
        """
        if not self._ring:
            return
        pending = list(self._ring)
        self._ring.clear()
        for buffered in pending:
            try:
                await self._write_once(buffered)
            except Exception as e:
                self._ring.append(buffered)
                logger.warning("wire.emit: drain failed for buffered event: %s", e)
