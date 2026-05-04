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
_DEFAULT_CEILINGS: dict[str, int] = {
    "gemini_pro": 200_000,        # tokens per investigation; checked separately
    "grounding": 5_000,           # per-Scout daily; check uses agent= kwarg
    "deep_research": 10,
    "tts": 200_000,               # chars/day
}


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
    ) -> None:
        self._bq = bigquery
        self._project_id = project_id
        self._dataset = dataset
        self._table = table
        self._ceilings = dict(_DEFAULT_CEILINGS)
        if ceilings:
            self._ceilings.update(ceilings)
        self._flush_interval = flush_interval_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state: dict[tuple, _Counter] = defaultdict(_Counter)
        self._dirty: set[tuple] = set()
        self._flush_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

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
    ) -> None:
        """Raise CostCeilingExceeded if the counter has hit its cap.

        Per-axis ceilings are global by default; the `grounding` axis is
        per-Scout (caller passes `agent=`).
        """
        if axis not in self._ceilings:
            return
        limit = self._ceilings[axis]
        # Sum all rows matching axis (and optionally agent) for today.
        today = self._clock().date()
        total = 0
        for key, c in self._state.items():
            k_date, k_agent, _k_sub, k_axis, _k_model = key
            if k_date != today or k_axis != axis:
                continue
            if agent is not None and k_agent != agent:
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
