"""The Editor's always-on autonomous loop (HOE-DEC-022, BUILD_SPEC §5.1).

Owns four behaviors:
  1. Sleep `jittered_delay(30, 90)` between think-cycles.
  2. At the TOP of every cycle, check `AGENT_RUNTIME_PAUSED=1` (BUILD_SPEC
     §15.4 kill-switch) and short-circuit if set.
  3. On exception inside a cycle: log, emit a Wire `thinking` event for
     visibility, back off, do NOT crash the loop (BUILD_SPEC §17.1).
  4. Exit cleanly when `stop_event.set()` (SIGTERM path).

Pure orchestration — no voice text, no decision content. Voice + behavior
live in `/prompts/editor.md`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable

from agents.wire.pacing import WirePacer

logger = logging.getLogger(__name__)


_DEFAULT_THINK_MIN_S = 30.0
_DEFAULT_THINK_MAX_S = 90.0
_DEFAULT_PAUSE_POLL_S = 5.0
_DEFAULT_RECOVERY_BACKOFF_S = 10.0


def _think_cycle_bounds() -> tuple[float, float]:
    """Read EDITOR_THINK_CYCLE_MIN/MAX_SECONDS env vars with sane defaults."""
    try:
        lo = float(os.environ.get("EDITOR_THINK_CYCLE_MIN_SECONDS", _DEFAULT_THINK_MIN_S))
        hi = float(os.environ.get("EDITOR_THINK_CYCLE_MAX_SECONDS", _DEFAULT_THINK_MAX_S))
    except ValueError:
        lo, hi = _DEFAULT_THINK_MIN_S, _DEFAULT_THINK_MAX_S
    if lo <= 0 or hi < lo:
        lo, hi = _DEFAULT_THINK_MIN_S, _DEFAULT_THINK_MAX_S
    return lo, hi


async def autonomous_loop(
    think_fn: Callable[[], Awaitable[Any]],
    *,
    stop_event: asyncio.Event | None = None,
    pacer: WirePacer | None = None,
    pause_poll_seconds: float = _DEFAULT_PAUSE_POLL_S,
    recovery_backoff_seconds: float = _DEFAULT_RECOVERY_BACKOFF_S,
    max_iterations: int | None = None,
) -> None:
    """Run `think_fn` forever (or until stop_event is set / max_iterations hit).

    Args:
        think_fn: a no-arg coroutine; one think-cycle.
        stop_event: optional event; when set, the loop exits cleanly.
        pacer: optional WirePacer; controls the jittered delay.
        pause_poll_seconds: while AGENT_RUNTIME_PAUSED=1, poll this often.
        recovery_backoff_seconds: backoff after an exception.
        max_iterations: optional ceiling for unit tests.
    """
    pacer = pacer or WirePacer(compression_factor=1.0)
    iters = 0
    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("editor.autonomous_loop: stop_event set; exiting")
            return
        if max_iterations is not None and iters >= max_iterations:
            return

        # Pause check at the TOP of every cycle (BUILD_SPEC §15.4).
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug("editor.autonomous_loop: paused (AGENT_RUNTIME_PAUSED=1)")
            await asyncio.sleep(pause_poll_seconds)
            iters += 1
            continue

        try:
            await think_fn()
        except Exception:
            # BUILD_SPEC §17.1: log + back off, don't crash the loop.
            logger.exception("editor.autonomous_loop: think_fn raised; backing off")
            await asyncio.sleep(recovery_backoff_seconds)
            iters += 1
            continue

        # Inter-cycle delay.
        lo, hi = _think_cycle_bounds()
        try:
            await pacer.jittered_delay(lo, hi)
        except Exception:
            logger.exception("editor.autonomous_loop: pacer delay raised; ignoring")
        iters += 1
