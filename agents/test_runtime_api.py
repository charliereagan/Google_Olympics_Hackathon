"""Unit tests for `POST /api/investigate` (BUILD_SPEC §11.1, §6.10).

Hits the helper directly so we don't need to spin uvicorn or run the full
boot sequence. The helper takes a `request`-shape and a `RuntimeState`-shape;
both are easy to fake.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

import agents.runtime as runtime
from agents.runtime import (
    RuntimeState,
    _check_and_record_rate_limit,
    _client_ip,
    _handle_investigate,
)


# -- Fake request / state -----------------------------------------------------


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    def __init__(
        self,
        body: dict | str,
        *,
        client_host: str = "1.2.3.4",
        headers: dict | None = None,
    ) -> None:
        self._body = body
        self.client = _FakeClient(client_host)
        self.headers = headers or {}

    async def json(self) -> dict:
        if isinstance(self._body, str):
            # Simulate invalid JSON body.
            raise ValueError("invalid json")
        return self._body


def _empty_state() -> RuntimeState:
    return RuntimeState(boot_time=datetime.now(timezone.utc))


# -- _client_ip ---------------------------------------------------------------


def test_client_ip_prefers_x_forwarded_for():
    req = _FakeRequest({}, client_host="10.0.0.1", headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
    assert _client_ip(req) == "203.0.113.5"


def test_client_ip_falls_back_to_client_host():
    req = _FakeRequest({}, client_host="198.51.100.7")
    assert _client_ip(req) == "198.51.100.7"


# -- Rate limit ---------------------------------------------------------------


def test_rate_limit_allows_under_threshold():
    state = _empty_state()
    now = time.time()
    for _ in range(3):
        ok, _rem = _check_and_record_rate_limit(state, "1.1.1.1", now=now, limit=3)
        assert ok is True


def test_rate_limit_blocks_at_threshold():
    state = _empty_state()
    now = time.time()
    for _ in range(3):
        _check_and_record_rate_limit(state, "1.1.1.1", now=now, limit=3)
    ok, _rem = _check_and_record_rate_limit(state, "1.1.1.1", now=now, limit=3)
    assert ok is False


def test_rate_limit_window_expires():
    state = _empty_state()
    now = time.time()
    for _ in range(3):
        _check_and_record_rate_limit(state, "1.1.1.1", now=now - 7200, limit=3, window_s=3600)
    # Earlier hits should be evicted by the window.
    ok, _rem = _check_and_record_rate_limit(state, "1.1.1.1", now=now, limit=3, window_s=3600)
    assert ok is True


# -- /api/investigate body validation ----------------------------------------


@pytest.mark.asyncio
async def test_investigate_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(runtime, "_state", _empty_state())
    req = _FakeRequest("not-json")  # raises in .json()
    resp = await _handle_investigate(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_investigate_rejects_empty_prompt(monkeypatch):
    monkeypatch.setattr(runtime, "_state", _empty_state())
    req = _FakeRequest({"prompt": "", "compression_factor": 0.25})
    resp = await _handle_investigate(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_investigate_rejects_overlong_prompt(monkeypatch):
    monkeypatch.setattr(runtime, "_state", _empty_state())
    req = _FakeRequest({"prompt": "x" * 600, "compression_factor": 0.25})
    resp = await _handle_investigate(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_investigate_rejects_out_of_range_compression(monkeypatch):
    monkeypatch.setattr(runtime, "_state", _empty_state())
    req = _FakeRequest({"prompt": "find me a story", "compression_factor": 2.0})
    resp = await _handle_investigate(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_investigate_rejects_below_min_compression(monkeypatch):
    monkeypatch.setattr(runtime, "_state", _empty_state())
    req = _FakeRequest({"prompt": "find me a story", "compression_factor": 0.001})
    resp = await _handle_investigate(req)
    assert resp.status_code == 422


# -- Happy path + edge paths --------------------------------------------------


@pytest.mark.asyncio
async def test_investigate_accepts_valid_submission(monkeypatch):
    """Valid submission spawns a fire-and-forget task and returns 202 with id."""
    state = _empty_state()
    fake_editor = mock.Mock()
    fake_editor.model = "gemini-3.1-pro-preview"
    # Use an asyncio.Future so we can wait on it
    completed = asyncio.Event()

    async def _think_once(ctx=None):
        completed.set()
        return {"action": "ok"}

    fake_editor.think_once = _think_once
    state.editor = fake_editor
    monkeypatch.setattr(runtime, "_state", state)

    req = _FakeRequest({
        "prompt": "find me a hometown story I haven't heard",
        "compression_factor": 0.25,
        "source": "cta",
    })
    resp = await _handle_investigate(req)
    assert resp.status_code == 202
    body = json.loads(resp.body)
    assert body["investigation_id"].startswith("inv-")
    assert body["compression_factor"] == 0.25
    assert state.active_live_investigation is not None
    # Wait for the fire-and-forget cycle to complete.
    await asyncio.wait_for(completed.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_investigate_queues_when_one_active(monkeypatch):
    """A second submission while one is active gets queued (202 + status:queued)."""
    state = _empty_state()
    state.editor = mock.Mock()

    # Pre-set an active task that hasn't completed.
    async def _hang():
        await asyncio.sleep(60)

    state.active_live_investigation = asyncio.create_task(_hang())
    state.active_live_investigation_id = "inv-already-running"
    monkeypatch.setattr(runtime, "_state", state)

    try:
        req = _FakeRequest(
            {"prompt": "another story", "compression_factor": 0.25},
            client_host="9.9.9.9",  # different IP — not blocked by rate limit
        )
        resp = await _handle_investigate(req)
        assert resp.status_code == 202
        body = json.loads(resp.body)
        assert body["status"] == "queued"
        assert "watching room work" in body["message"]
    finally:
        state.active_live_investigation.cancel()
        try:
            await state.active_live_investigation
        except (asyncio.CancelledError, BaseException):
            pass


@pytest.mark.asyncio
async def test_investigate_rate_limits_after_three(monkeypatch):
    state = _empty_state()
    state.editor = mock.Mock()
    state.editor.model = "gemini-3.1-pro-preview"

    completed_count = 0

    async def _think_once(ctx=None):
        nonlocal completed_count
        completed_count += 1
        return {"action": "ok"}

    state.editor.think_once = _think_once
    monkeypatch.setattr(runtime, "_state", state)

    ip = "5.5.5.5"
    # Three accepted submissions (each completes immediately so the next
    # one isn't blocked by the concurrent-investigation gate).
    for i in range(3):
        req = _FakeRequest(
            {"prompt": f"prompt {i}", "compression_factor": 0.25},
            client_host=ip,
        )
        resp = await _handle_investigate(req)
        assert resp.status_code == 202
        # Wait for the fire-and-forget task before submitting the next so
        # it doesn't trip the concurrent gate.
        if state.active_live_investigation is not None:
            await state.active_live_investigation

    # 4th attempt from same IP — rate limited.
    req = _FakeRequest(
        {"prompt": "fourth", "compression_factor": 0.25},
        client_host=ip,
    )
    resp = await _handle_investigate(req)
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_investigate_returns_503_when_runtime_not_ready(monkeypatch):
    monkeypatch.setattr(runtime, "_state", None)
    req = _FakeRequest({"prompt": "test", "compression_factor": 0.25})
    resp = await _handle_investigate(req)
    assert resp.status_code == 503
