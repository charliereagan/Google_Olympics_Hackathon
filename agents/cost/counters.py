"""Per-axis daily cost counter (BUILD_SPEC §15.3).

Tracks API spend by axis (gemini_pro, grounding, image_pro, ...) so the tool
wrappers can `assert_under_ceiling` BEFORE each invocation. On breach: raise
`CostCeilingExceeded` — the calling agent catches and emits a Wire `thinking`
event ("daily cap reached"), backs off, and the runtime keeps running.

Persistence: the BigQuery `agent_call_counters` table per
`data/bq_schemas/agent_call_counters.json`. Writes are batched (60s flush) to
avoid wasteful per-call upserts. The in-memory accumulator is the source of
truth for `assert_under_ceiling`; the table is the durable record for crash
recovery.

Crash recovery: on boot, query today's row sums to repopulate in-memory state.
The runtime loses at most 60s of counters on instance crash.

Kill-switch path: when `AGENT_RUNTIME_PAUSED=1` flips, the autonomous loop
short-circuits at the top (BUILD_SPEC §15.4) — counters keep flushing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal

from agents.wire.types import AgentId, SubAgentId

logger = logging.getLogger(__name__)

# Cost axes from data/bq_schemas/agent_call_counters.json.
CostAxis = Literal[
    "gemini_pro",
    "gemini_flash",
    "gemini_flash_lite",
    "image_pro",
    "image_flash",
    "tts",
    "grounding",
    "deep_research",
    "meta",  # for HND fires + other internal events that don't hit a model
]


# Defaults from BUILD_SPEC §15.3. Map: (axis -> daily limit). Some axes are
# enforced inline at the call site (Nano Banana per-story regen) — those aren't
# global ceilings. Per-Scout grounded prompts has a per-agent dimension.
#
# Day-6 update (HOE-DEC-034 — paired with the USD ceiling bump below): the
# pre-Day-6 per-axis caps were tight enough to bind before the USD cap fired,
# blocking continuous operation after a single investigation. The USD ceiling
# is the strategic guard rail; the per-axis caps now exist as defense-in-depth
# against a runaway in a single axis. Each is also overridable via env var
# (COST_CEILING_GEMINI_PRO_TOKENS, COST_CEILING_GROUNDING_QUERIES,
# COST_CEILING_DEEP_RESEARCH_CALLS, COST_CEILING_TTS_CHARS).
_DEFAULT_CEILINGS: dict[str, int] = {
    "gemini_pro":     5_000_000,  # tokens/day — ample for ~10-20 investigations
    "grounding":         50_000,  # per-Scout daily
    "deep_research":        100,
    "tts":            2_000_000,  # chars/day — enough for ~600 sentences of narration
}


def _read_int_env(name: str, default: int) -> int:
    """Parse an int env var; fall back to default on missing / invalid."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _ceilings_with_env_overrides() -> dict[str, int]:
    """Build the per-axis ceiling map honoring env overrides."""
    return {
        "gemini_pro":    _read_int_env("COST_CEILING_GEMINI_PRO_TOKENS",   _DEFAULT_CEILINGS["gemini_pro"]),
        "grounding":     _read_int_env("COST_CEILING_GROUNDING_QUERIES",   _DEFAULT_CEILINGS["grounding"]),
        "deep_research": _read_int_env("COST_CEILING_DEEP_RESEARCH_CALLS", _DEFAULT_CEILINGS["deep_research"]),
        "tts":           _read_int_env("COST_CEILING_TTS_CHARS",            _DEFAULT_CEILINGS["tts"]),
    }


# --- USD-cost guard rails (HOE-DEC-033 update, 2026-05-05) -------------------
#
# In addition to the per-axis token / call ceilings above, we enforce two
# total-USD caps so a runaway loop trips before the GCP $300 billing alert
# fires (BUILD_SPEC §15.2). Defaults bumped Day-6 to enable continuous
# operation across the remaining 96 hours per VPS guidance:
#   - per-day USD ceiling: $50  (was effectively ~$1-2 via tight token caps)
#   - absolute USD ceiling: $300 (matches the GCP kill-switch alert)
#
# Either ceiling can be overridden at runtime via env var without a code
# change:
#   COST_CEILING_DAILY_USD=50.0       (float, USD)
#   COST_CEILING_ABSOLUTE_USD=300.0   (float, USD)
#
# Pricing-per-token table is intentionally rough. We are not a billing
# system; we only need to convert token / call counters into a
# USD-ish number tight enough to catch a runaway. Per BUILD_SPEC §15.1
# rough estimates. Update if Vertex AI pricing changes materially.
_DEFAULT_DAILY_USD = 50.0
_DEFAULT_ABSOLUTE_USD = 300.0

# Approximate USD prices per 1M tokens (input, output) per axis. Numbers are
# conservative-high so we trip slightly early rather than slightly late.
_PRICE_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini_pro":        (5.00, 20.00),   # Gemini 3.1 Pro
    "gemini_flash":      (0.30,  2.50),
    "gemini_flash_lite": (0.25,  1.50),
}

# Per-call USD cost for axes counted as `calls` (not tokens). Image gen and
# TTS are coarse but sufficient to catch a loop.
_PRICE_PER_CALL: dict[str, float] = {
    "image_pro":     0.30,    # Nano Banana Pro hero (~50 gens at ~$0.30 each)
    "image_flash":   0.10,    # utility panels
    "deep_research": 1.50,    # premium tier
    "grounding":     0.014,   # $14/1K queries past free tier
    "meta":          0.0,     # internal events don't cost anything
}

# TTS billed per character; very rough.
_PRICE_TTS_PER_CHAR = 0.000016  # ~$16/1M chars


def _read_float_env(name: str, default: float) -> float:
    """Parse a float env var; fall back to default on missing / invalid."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "cost_counter: invalid %s=%r; falling back to %.2f",
            name, raw, default,
        )
        return default


class CostCeilingExceeded(RuntimeError):
    """Raised by `assert_under_ceiling` when a counter has hit its cap."""


@dataclass
class _Counter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    audio_chars: int = 0
    grounded_queries: int = 0


@dataclass
class _PendingFlush:
    rows: dict = field(default_factory=dict)


class CostCounter:
    """Per-axis daily counter with batched BigQuery flush.

    The in-memory state shape is `{(date, agent, sub_agent, axis, model): _Counter}`.
    """

    def __init__(
        self,
        bigquery: Any,
        *,
        project_id: str,
        dataset: str = "storytellers_room",
        table: str = "agent_call_counters",
        ceilings: dict[str, int] | None = None,
        flush_interval_seconds: float = 60.0,
        clock: Any = None,
        daily_usd_limit: float | None = None,
        absolute_usd_limit: float | None = None,
    ) -> None:
        self._bq = bigquery
        self._project_id = project_id
        self._dataset = dataset
        self._table = table
        self._ceilings = _ceilings_with_env_overrides()
        if ceilings:
            self._ceilings.update(ceilings)
        self._flush_interval = flush_interval_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state: dict[tuple, _Counter] = defaultdict(_Counter)
        self._dirty: set[tuple] = set()
        self._flush_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        # USD ceilings (HOE-DEC-033 Day-6 update). Constructor args win;
        # fall back to env vars; fall back to module defaults.
        self._daily_usd_limit = (
            float(daily_usd_limit)
            if daily_usd_limit is not None
            else _read_float_env("COST_CEILING_DAILY_USD", _DEFAULT_DAILY_USD)
        )
        self._absolute_usd_limit = (
            float(absolute_usd_limit)
            if absolute_usd_limit is not None
            else _read_float_env("COST_CEILING_ABSOLUTE_USD", _DEFAULT_ABSOLUTE_USD)
        )

    # -- Public API ---------------------------------------------------------

    async def increment(
        self,
        *,
        agent: AgentId,
        sub_agent: SubAgentId | None,
        axis: CostAxis,
        model: str | None,
        calls: int = 1,
        input_tokens: int = 0,
        output_tokens: int = 0,
        images: int = 0,
        audio_chars: int = 0,
        grounded_queries: int = 0,
    ) -> None:
        """Bump the counter. Called by tool wrappers BEFORE the model call."""
        key = self._key(axis=axis, agent=agent, sub_agent=sub_agent, model=model)
        c = self._state[key]
        c.calls += calls
        c.input_tokens += input_tokens
        c.output_tokens += output_tokens
        c.images += images
        c.audio_chars += audio_chars
        c.grounded_queries += grounded_queries
        self._dirty.add(key)

    def snapshot_today(
        self,
        *,
        axis: CostAxis | None = None,
        agent: AgentId | None = None,
    ) -> dict[str, int]:
        """Return today's totals as a flat dict for inclusion in agent context.

        If `axis` is provided, returns just that axis (e.g. `{'gemini_pro': 12345}`);
        otherwise returns a per-axis breakdown across all axes touched today.
        Filtered by `agent` when provided. The Editor's `think_once` calls this
        to feed today's burn into its context window — used for the
        ``## Cost dashboard`` section of the user message.

        Synchronous (in-memory only). The BigQuery flush is independent.
        """
        today = self._clock().date()
        out: dict[str, int] = {}
        for key, c in self._state.items():
            k_date, k_agent, _k_sub, k_axis, _k_model = key
            if k_date != today:
                continue
            if axis is not None and k_axis != axis:
                continue
            if agent is not None and k_agent != agent:
                continue
            # Pick the right field per axis (mirrors assert_under_ceiling).
            if k_axis == "tts":
                value = c.audio_chars
            elif k_axis == "grounding":
                value = c.grounded_queries
            elif k_axis == "gemini_pro":
                value = c.input_tokens + c.output_tokens
            else:
                value = c.calls
            out[k_axis] = out.get(k_axis, 0) + value
        return out

    async def assert_under_ceiling(
        self,
        *,
        axis: CostAxis,
        agent: AgentId | None = None,
        sub_agent: SubAgentId | None = None,
    ) -> None:
        """Raise CostCeilingExceeded if the counter has hit its cap.

        Three guard rails are checked, in order:
          1. Per-axis token / call ceiling (BUILD_SPEC §15.3 — original
             Day-2 behavior). Only fires when ``axis`` has an entry in
             ``self._ceilings``. ``grounding`` is per-Scout (caller passes
             ``agent=`` / ``sub_agent=``); the rest are global.
          2. Daily total USD ceiling (HOE-DEC-033 Day-6 update). Sums the
             USD-equivalent of every counter touched today across all
             axes. Default $50/day; overridable via
             ``COST_CEILING_DAILY_USD`` env var.
          3. Absolute total USD ceiling (HOE-DEC-033 Day-6 update). Sums
             across the entire in-memory + recovered history. Default
             $300; overridable via ``COST_CEILING_ABSOLUTE_USD``.

        The USD checks catch runaway loops the per-axis caps miss (e.g.,
        an agent making thousands of cheap Flash calls that never trip a
        token ceiling).
        """
        if axis in self._ceilings:
            limit = self._ceilings[axis]
            # Sum all rows matching axis (+ optional agent + optional sub_agent) for today.
            today = self._clock().date()
            total = 0
            for key, c in self._state.items():
                k_date, k_agent, k_sub, k_axis, _k_model = key
                if k_date != today or k_axis != axis:
                    continue
                if agent is not None and k_agent != agent:
                    continue
                if sub_agent is not None and k_sub != sub_agent:
                    continue
                # Pick the right field per axis.
                if axis == "tts":
                    total += c.audio_chars
                elif axis == "grounding":
                    total += c.grounded_queries
                elif axis == "gemini_pro":
                    total += c.input_tokens + c.output_tokens
                else:
                    total += c.calls
            if total >= limit:
                raise CostCeilingExceeded(
                    f"axis={axis} agent={agent} total={total} >= limit={limit}"
                )

        # USD guard rails. Fire BEFORE the next call, not after, so we
        # never overshoot by the cost of one model invocation.
        daily_usd = self._estimate_usd(today_only=True)
        if daily_usd >= self._daily_usd_limit:
            raise CostCeilingExceeded(
                f"daily_usd={daily_usd:.2f} >= limit={self._daily_usd_limit:.2f}"
            )
        absolute_usd = self._estimate_usd(today_only=False)
        if absolute_usd >= self._absolute_usd_limit:
            raise CostCeilingExceeded(
                f"absolute_usd={absolute_usd:.2f} >= limit={self._absolute_usd_limit:.2f}"
            )

    def _estimate_usd(self, *, today_only: bool) -> float:
        """Sum the USD-equivalent of every counter in scope.

        Conservative-high pricing per `_PRICE_PER_M_TOKENS` /
        `_PRICE_PER_CALL` / `_PRICE_TTS_PER_CHAR`. Approximate by
        construction; we're catching runaway loops, not generating an
        invoice.
        """
        today = self._clock().date()
        total = 0.0
        for key, c in self._state.items():
            k_date, _k_agent, _k_sub, k_axis, _k_model = key
            if today_only and k_date != today:
                continue
            if k_axis in _PRICE_PER_M_TOKENS:
                price_in, price_out = _PRICE_PER_M_TOKENS[k_axis]
                total += (c.input_tokens / 1_000_000.0) * price_in
                total += (c.output_tokens / 1_000_000.0) * price_out
            elif k_axis == "tts":
                total += c.audio_chars * _PRICE_TTS_PER_CHAR
            elif k_axis in _PRICE_PER_CALL:
                total += c.calls * _PRICE_PER_CALL[k_axis]
            # Unknown axes contribute $0; the guard rail is best-effort.
        return total

    def start_flush_loop(self) -> None:
        """Kick off the 60s flush background task. Called from runtime.lifespan."""
        if self._flush_task is not None:
            return
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._flush_task is not None:
            try:
                await asyncio.wait_for(self._flush_task, timeout=self._flush_interval + 5)
            except asyncio.TimeoutError:  # pragma: no cover
                self._flush_task.cancel()
        await self._flush_now()  # final drain

    async def recover_from_bigquery(self) -> None:
        """Repopulate today's in-memory state from the BigQuery table.

        On boot. Runs in a thread so the asyncio loop isn't blocked.
        """
        today = self._clock().date()
        sql = (
            f"SELECT counter_date, agent, sub_agent, axis, model, "
            f"call_count, input_tokens, output_tokens, images_generated, "
            f"audio_chars, grounded_search_queries "
            f"FROM `{self._dataset}.{self._table}` "
            f"WHERE counter_date = DATE('{today.isoformat()}')"
        )
        try:
            rows = await asyncio.to_thread(self._run_query_rows, sql)
        except Exception as e:
            logger.warning("cost_counter: recover_from_bigquery failed: %s", e)
            return
        for row in rows:
            key = (
                today,
                row["agent"],
                row.get("sub_agent"),
                row["axis"],
                row.get("model"),
            )
            c = _Counter(
                calls=row.get("call_count") or 0,
                input_tokens=row.get("input_tokens") or 0,
                output_tokens=row.get("output_tokens") or 0,
                images=row.get("images_generated") or 0,
                audio_chars=row.get("audio_chars") or 0,
                grounded_queries=row.get("grounded_search_queries") or 0,
            )
            self._state[key] = c
        logger.info("cost_counter: recovered %d rows from BigQuery", len(rows))

    # -- Internals ----------------------------------------------------------

    def _key(self, *, axis: str, agent: str, sub_agent: str | None, model: str | None) -> tuple:
        today = self._clock().date()
        return (today, agent, sub_agent, axis, model)

    async def _flush_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._flush_interval)
            except asyncio.TimeoutError:
                pass  # interval elapsed, time to flush
            try:
                await self._flush_now()
            except Exception:
                logger.exception("cost_counter: flush failed; will retry next interval")

    async def _flush_now(self) -> None:
        if not self._dirty:
            return
        snapshot = list(self._dirty)
        self._dirty.clear()
        rows = []
        for key in snapshot:
            d, agent, sub_agent, axis, model = key
            c = self._state[key]
            rows.append(
                {
                    "counter_date": d.isoformat() if isinstance(d, date) else str(d),
                    "agent": agent,
                    "sub_agent": sub_agent,
                    "axis": axis,
                    "model": model,
                    "call_count": c.calls,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "images_generated": c.images,
                    "audio_chars": c.audio_chars,
                    "grounded_search_queries": c.grounded_queries,
                    "last_updated": self._clock().isoformat(),
                }
            )
        try:
            await asyncio.to_thread(self._upsert_rows, rows)
        except Exception:
            # Re-mark as dirty so we retry next flush.
            for key in snapshot:
                self._dirty.add(key)
            raise

    def _upsert_rows(self, rows: list[dict]) -> None:
        """Issue a MERGE statement to BigQuery. Synchronous."""
        if not rows or self._bq is None:
            return
        # Use insert_rows_json for simplicity in Day 2; switch to MERGE if
        # duplicate primary keys become an issue. Each (counter_date, agent,
        # sub_agent, axis, model) tuple should be unique per flush.
        try:
            errors = self._bq.insert_rows_json(
                f"{self._project_id}.{self._dataset}.{self._table}",
                rows,
            )
            if errors:
                logger.warning("cost_counter: insert_rows_json errors: %s", errors)
        except Exception as e:  # pragma: no cover — observed only on real BQ
            logger.warning("cost_counter: insert_rows_json failed: %s", e)
            raise

    def _run_query_rows(self, sql: str) -> list[dict]:  # pragma: no cover — real BQ path
        if self._bq is None:
            return []
        job = self._bq.query(sql)
        return [dict(r) for r in job.result()]
