"""Unit tests for the Editor's autonomous loop.

Plan §F lists 3 cases:
  1. Loop respects `AGENT_RUNTIME_PAUSED=1` — `think_fn` is never called.
  2. Loop recovers from a `think_fn` exception (one raise then succeeds).
  3. Loop exits on `stop_event`.
"""

from __future__ import annotations

import asyncio
import os
from unittest import mock

import pytest

from agents.editor.loop import autonomous_loop
from agents.wire.pacing import WirePacer


@pytest.mark.asyncio
async def test_loop_respects_pause_env(monkeypatch):
    """With AGENT_RUNTIME_PAUSED=1, think_fn is never invoked."""
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    calls = 0

    async def think():
        nonlocal calls
        calls += 1

    with mock.patch("asyncio.sleep", new=mock.AsyncMock()):
        await autonomous_loop(
            think,
            pause_poll_seconds=0.0,
            max_iterations=5,
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_loop_recovers_from_exception():
    """think_fn raises once then succeeds; loop continues."""
    states: list[str] = []

    async def think():
        if not states:
            states.append("raised")
            raise RuntimeError("boom")
        states.append("ok")

    with mock.patch("asyncio.sleep", new=mock.AsyncMock()):
        await autonomous_loop(
            think,
            pacer=WirePacer(compression_factor=1.0),
            recovery_backoff_seconds=0.0,
            max_iterations=3,
        )
    assert "raised" in states
    assert states.count("ok") >= 1, f"loop didn't recover: {states}"


@pytest.mark.asyncio
async def test_loop_exits_on_stop_event():
    stop = asyncio.Event()
    calls = 0

    async def think():
        nonlocal calls
        calls += 1
        if calls == 2:
            stop.set()

    with mock.patch("asyncio.sleep", new=mock.AsyncMock()):
        await autonomous_loop(
            think,
            stop_event=stop,
            pacer=WirePacer(compression_factor=1.0),
            max_iterations=10,
        )
    # Should have invoked think twice (last one set stop_event), then exited
    # before a 3rd call.
    assert calls == 2
