"""Unit tests for WirePacer.

Covers the four cases called out in plan §F:
  1. Uncompressed delay (cf=1.0).
  2. Compressed delay (cf=0.25).
  3. Compression clamping (rejects 0.0 and 2.0).
  4. Jittered delay falls within bounds across many iterations.
"""

from __future__ import annotations

from unittest import mock

import pytest

from agents.wire.pacing import WirePacer


@pytest.mark.asyncio
async def test_delay_uncompressed():
    pacer = WirePacer(compression_factor=1.0)
    with mock.patch("asyncio.sleep", new=mock.AsyncMock()) as sleeper:
        await pacer.delay(2.0)
    sleeper.assert_awaited_once()
    args, _ = sleeper.await_args
    assert args[0] == pytest.approx(2.0, rel=1e-6)


@pytest.mark.asyncio
async def test_delay_compressed():
    """At cf=0.25, a 2.0s nominal pause becomes 0.5s wall-clock (4× faster).

    The intent is unambiguous in BUILD_SPEC §6.10's worked example: "a 6s
    think pause becomes 1.5s at compression 0.25" — only consistent with
    `target * compression_factor`.
    """
    pacer = WirePacer(compression_factor=0.25)
    with mock.patch("asyncio.sleep", new=mock.AsyncMock()) as sleeper:
        await pacer.delay(2.0)
    args, _ = sleeper.await_args
    assert args[0] == pytest.approx(0.5, rel=1e-6)


def test_compression_clamp_rejects_zero():
    with pytest.raises(ValueError):
        WirePacer(compression_factor=0.0)


def test_compression_clamp_rejects_above_one():
    with pytest.raises(ValueError):
        WirePacer(compression_factor=2.0)


def test_compression_clamp_rejects_negative():
    with pytest.raises(ValueError):
        WirePacer(compression_factor=-0.5)


@pytest.mark.asyncio
async def test_jittered_delay_within_bounds():
    """Across 100 iterations, jittered delays fall in [base_min*cf, base_max*cf]."""
    pacer = WirePacer(compression_factor=0.5)
    seen: list[float] = []

    async def capture_sleep(d: float) -> None:
        seen.append(d)

    with mock.patch("asyncio.sleep", new=mock.AsyncMock(side_effect=capture_sleep)):
        for _ in range(100):
            await pacer.jittered_delay(2.0, 4.0)

    assert len(seen) == 100
    # nominal in [2,4]; effective = nominal * 0.5 -> [1.0, 2.0]
    for v in seen:
        assert 1.0 - 1e-6 <= v <= 2.0 + 1e-6, f"out of bounds: {v}"


@pytest.mark.asyncio
async def test_jittered_delay_rejects_inverted_bounds():
    pacer = WirePacer()
    with pytest.raises(ValueError):
        await pacer.jittered_delay(5.0, 2.0)
