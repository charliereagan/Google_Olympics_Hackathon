"""Unit tests for WireEmitter.

Covers the four cases called out in plan §D + §F:
  1. emit() calls NIL Layer SYNCHRONOUSLY before the Firestore write.
  2. emit() rewrites the message in place when scan returns 'redact'.
  3. emit() raises WireProxyNotReadyError when the NIL Layer is not loaded
     and Firestore is never touched.
  4. emit() retries on Firestore failures (3× exponential backoff).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.wire.emit import WireEmitter, WireProxyNotReadyError
from agents.wire.types import NilLog, WireScanResult


# --- Test doubles -------------------------------------------------------------


class _FakeNilLayer:
    """Records call order so tests can assert NIL ran before Firestore."""

    def __init__(
        self,
        *,
        is_loaded: bool = True,
        decision: str = "pass",
        rewrite_to: str | None = None,
        on_call: Any = None,
    ) -> None:
        self.is_loaded = is_loaded
        self._decision = decision
        self._rewrite_to = rewrite_to
        self._on_call = on_call
        self.scan_calls: list[tuple[str, dict | None]] = []

    def scan_wire(self, text: str, *, surface: str = "wire", context: dict | None = None) -> WireScanResult:
        if self._on_call is not None:
            self._on_call()
        self.scan_calls.append((text, context))
        if self._decision == "redact":
            log = NilLog(direct_matches_redacted=1, aggregations_applied=0)
            return WireScanResult(
                decision="redact",
                redacted_message=self._rewrite_to or "[redacted]",
                log=log,
            )
        return WireScanResult(
            decision="pass",
            redacted_message=text,
            log=NilLog(direct_matches_redacted=0, aggregations_applied=0),
        )


class _FakeDocRef:
    def __init__(self, id: str) -> None:
        self.id = id


class _FakeCollection:
    def __init__(self, parent: "_FakeFirestore", name: str) -> None:
        self._parent = parent
        self._name = name

    def add(self, doc: dict) -> Any:
        # Record (collection-name, doc, count of NIL scans observed at this moment).
        scans_now = len(self._parent.nil.scan_calls) if self._parent.nil else 0
        self._parent.write_calls.append((self._name, doc, scans_now))
        # Optional pre-injection of failures.
        if self._parent.failures_remaining > 0:
            self._parent.failures_remaining -= 1
            err = self._parent.failure_exception
            async def _raiser():
                raise err
            return _raiser()
        idx = len(self._parent.write_calls)
        ref = _FakeDocRef(id=f"doc-{idx}")
        async def _ok():
            return (mock.MagicMock(), ref)
        return _ok()


class _FakeFirestore:
    def __init__(
        self,
        *,
        failures_remaining: int = 0,
        failure_exception: Exception | None = None,
        nil: "_FakeNilLayer | None" = None,
    ) -> None:
        self.write_calls: list[tuple[str, dict, int]] = []
        self.failures_remaining = failures_remaining
        self.failure_exception = failure_exception or RuntimeError("firestore down")
        self.nil = nil  # set after construction so the FakeCollection can read scan_calls

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self, name)


# --- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_calls_nil_layer_synchronously_before_firestore():
    """The NIL scan must run BEFORE Firestore is touched, in-process, sync."""
    nil = _FakeNilLayer(is_loaded=True, decision="pass")
    fs = _FakeFirestore(nil=nil)

    emitter = WireEmitter(fs, nil)
    await emitter.emit(
        {"agent": "editor", "message": "going with this place", "message_type": "decision"},
        investigation_id="inv-1",
    )

    assert len(nil.scan_calls) == 1, "NIL.scan_wire was not invoked"
    assert len(fs.write_calls) == 1, "Firestore.add was not invoked"
    # The recorded `scans_at_write` field captures `len(nil.scan_calls)` at the
    # moment .add() ran. It must be >= 1 — i.e., the NIL scan happened first.
    name, doc, scans_at_write = fs.write_calls[0]
    assert name == "wire_events"
    assert scans_at_write == 1, "Firestore write happened BEFORE the NIL scan"
    assert doc["nil_redaction_log"] == {"direct_matches_redacted": 0, "aggregations_applied": 0}


@pytest.mark.asyncio
async def test_emit_redacts_message_inline():
    """When scan returns decision='redact', the persisted event has the rewrite."""
    nil = _FakeNilLayer(
        is_loaded=True,
        decision="redact",
        rewrite_to="[redacted] ran fast",
    )
    fs = _FakeFirestore()
    emitter = WireEmitter(fs, nil)

    await emitter.emit(
        {"agent": "editor", "message": "Diego Maradona ran fast", "message_type": "thinking"},
    )

    assert len(fs.write_calls) == 1
    _, doc, _ = fs.write_calls[0]
    assert doc["message"] == "[redacted] ran fast"
    assert doc["nil_redaction_log"]["direct_matches_redacted"] == 1


@pytest.mark.asyncio
async def test_emit_fails_closed_when_unloaded():
    """is_loaded=False -> raise + Firestore is never called."""
    nil = _FakeNilLayer(is_loaded=False)
    fs = _FakeFirestore()
    emitter = WireEmitter(fs, nil)

    with pytest.raises(WireProxyNotReadyError):
        await emitter.emit({"agent": "editor", "message": "anything"})

    assert len(fs.write_calls) == 0
    assert len(nil.scan_calls) == 0


@pytest.mark.asyncio
async def test_emit_retries_on_firestore_failure():
    """Two failures then success: 3 attempts total, exponential backoff."""
    nil = _FakeNilLayer(is_loaded=True, decision="pass")
    fs = _FakeFirestore(failures_remaining=2, failure_exception=RuntimeError("transient"))
    emitter = WireEmitter(fs, nil, retry_backoff_seconds=(0.0, 0.0, 0.0))

    sleeps: list[float] = []
    real_sleep = asyncio.sleep
    async def capture(d):
        sleeps.append(d)
        await real_sleep(0)
    with mock.patch("asyncio.sleep", side_effect=capture):
        doc_id = await emitter.emit({"agent": "editor", "message": "ok"})

    assert doc_id.startswith("doc-")
    # 3 attempts total = 2 failed + 1 success. Backoff sleeps happen between
    # attempts, so 2 sleeps total.
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_emit_buffers_and_raises_when_all_retries_fail():
    """All retries exhausted -> raise + event is in the ring buffer."""
    nil = _FakeNilLayer(is_loaded=True, decision="pass")
    fs = _FakeFirestore(failures_remaining=99, failure_exception=RuntimeError("hard down"))
    emitter = WireEmitter(fs, nil, retry_backoff_seconds=(0.0, 0.0, 0.0))

    with mock.patch("asyncio.sleep", new=mock.AsyncMock()):
        with pytest.raises(RuntimeError):
            await emitter.emit({"agent": "editor", "message": "ok"})

    assert len(emitter._ring) == 1


@pytest.mark.asyncio
async def test_emit_stamps_timestamp_and_defaults():
    """The proxy fills timestamp, mode, and compression_factor defaults."""
    nil = _FakeNilLayer(is_loaded=True)
    fs = _FakeFirestore()
    fixed = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    emitter = WireEmitter(fs, nil, clock=lambda: fixed)

    await emitter.emit({"agent": "scout_desk", "message": "scanning"})

    _, doc, _ = fs.write_calls[0]
    assert doc["timestamp"] == fixed.isoformat()
    assert doc["mode"] == "live"
    assert doc["compression_factor"] == 1.0


@pytest.mark.asyncio
async def test_is_ready_property_delegates_to_layer():
    nil = _FakeNilLayer(is_loaded=False)
    fs = _FakeFirestore()
    emitter = WireEmitter(fs, nil)
    assert emitter.is_ready is False
    nil.is_loaded = True
    assert emitter.is_ready is True
