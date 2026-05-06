"""Unit tests for CostCounter.

Plan §F lists 4 cases:
  1. increment below ceiling passes.
  2. increment at ceiling raises.
  3. batched flush to BigQuery.
  4. recover from BigQuery on boot.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

import pytest

from agents.cost.counters import CostCeilingExceeded, CostCounter


class _FakeBQ:
    def __init__(self) -> None:
        self.inserted: list[tuple[str, list[dict]]] = []
        self.recovered_rows: list[dict] = []

    def insert_rows_json(self, table_path: str, rows: list[dict]) -> list:
        self.inserted.append((table_path, list(rows)))
        return []

    def query(self, sql: str) -> Any:
        rows = self.recovered_rows
        class _Job:
            def result(self_inner):
                return list(rows)
        return _Job()


def _fixed_clock(d: datetime):
    return lambda: d


@pytest.mark.asyncio
async def test_increment_below_ceiling_passes():
    bq = _FakeBQ()
    counter = CostCounter(
        bq,
        project_id="p",
        ceilings={"grounding": 5},
        flush_interval_seconds=10.0,
    )
    await counter.increment(
        agent="scout_desk",
        sub_agent="cinderella",
        axis="grounding",
        model=None,
        grounded_queries=3,
    )
    # Below 5 -> no raise.
    await counter.assert_under_ceiling(axis="grounding", agent="scout_desk")


@pytest.mark.asyncio
async def test_increment_at_ceiling_raises():
    bq = _FakeBQ()
    counter = CostCounter(
        bq,
        project_id="p",
        ceilings={"grounding": 5},
        flush_interval_seconds=10.0,
    )
    await counter.increment(
        agent="scout_desk",
        sub_agent="cinderella",
        axis="grounding",
        model=None,
        grounded_queries=5,
    )
    with pytest.raises(CostCeilingExceeded):
        await counter.assert_under_ceiling(axis="grounding", agent="scout_desk")


@pytest.mark.asyncio
async def test_batched_flush_to_bigquery():
    bq = _FakeBQ()
    fixed = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    counter = CostCounter(
        bq,
        project_id="p",
        flush_interval_seconds=0.05,
        clock=_fixed_clock(fixed),
    )
    counter.start_flush_loop()
    for _ in range(10):
        await counter.increment(
            agent="editor",
            sub_agent=None,
            axis="gemini_pro",
            model="gemini-3.1-pro-preview",
            input_tokens=100,
            output_tokens=50,
        )
    # Wait for one flush cycle.
    await asyncio.sleep(0.15)
    await counter.stop()

    # The flush should have produced at least one BigQuery write with a
    # single row for the (today, editor, None, gemini_pro, model) key
    # holding summed values (not 10 separate rows).
    assert len(bq.inserted) >= 1
    table_path, rows = bq.inserted[0]
    assert table_path.endswith("agent_call_counters")
    assert len(rows) == 1, f"expected one summed row, got {rows!r}"
    assert rows[0]["call_count"] == 10
    assert rows[0]["input_tokens"] == 1000
    assert rows[0]["output_tokens"] == 500


@pytest.mark.asyncio
async def test_daily_usd_ceiling_blocks_runaway_pro_spend():
    """The USD daily-cap (HOE-DEC-033 Day-6 update) trips even when the
    per-axis token cap has plenty of headroom.

    With a $50/day limit at conservative-high Pro pricing
    ($5/$20 per 1M in/out), 2,000,000 input tokens already implies
    ~$10 of spend; we push to ~$51 and assert the third call raises.
    """
    bq = _FakeBQ()
    counter = CostCounter(
        bq,
        project_id="p",
        # Disable the per-axis cap so we know it's the USD guard that fires.
        ceilings={"gemini_pro": 10**12},
        flush_interval_seconds=10.0,
        daily_usd_limit=50.0,
        absolute_usd_limit=300.0,
    )
    # ~$25 in two calls (5M input @ $5/M = $25).
    for _ in range(2):
        await counter.increment(
            agent="editor",
            sub_agent=None,
            axis="gemini_pro",
            model="gemini-3.1-pro-preview",
            input_tokens=2_500_000,
            output_tokens=0,
        )
    # Below $50 -> still passes.
    await counter.assert_under_ceiling(axis="gemini_pro", agent="editor")

    # Push another ~$26 of input -> total ~$51, over the $50 ceiling.
    await counter.increment(
        agent="editor",
        sub_agent=None,
        axis="gemini_pro",
        model="gemini-3.1-pro-preview",
        input_tokens=5_200_000,
        output_tokens=0,
    )
    with pytest.raises(CostCeilingExceeded):
        await counter.assert_under_ceiling(axis="gemini_pro", agent="editor")


@pytest.mark.asyncio
async def test_usd_ceilings_read_env_vars(monkeypatch):
    """`COST_CEILING_DAILY_USD` / `COST_CEILING_ABSOLUTE_USD` env vars
    override the module defaults at construction time."""
    monkeypatch.setenv("COST_CEILING_DAILY_USD", "5.0")
    monkeypatch.setenv("COST_CEILING_ABSOLUTE_USD", "20.0")
    bq = _FakeBQ()
    counter = CostCounter(
        bq,
        project_id="p",
        ceilings={"gemini_pro": 10**12},
        flush_interval_seconds=10.0,
    )
    # 1.2M input tokens at $5/M -> $6 -> over the $5 daily cap.
    await counter.increment(
        agent="editor",
        sub_agent=None,
        axis="gemini_pro",
        model="gemini-3.1-pro-preview",
        input_tokens=1_200_000,
        output_tokens=0,
    )
    with pytest.raises(CostCeilingExceeded):
        await counter.assert_under_ceiling(axis="gemini_pro", agent="editor")


@pytest.mark.asyncio
async def test_recover_from_bigquery_on_boot():
    """Recovery seeds in-memory state from BigQuery."""
    bq = _FakeBQ()
    today_str = date(2026, 5, 3).isoformat()
    bq.recovered_rows = [
        {
            "counter_date": today_str,
            "agent": "scout_desk",
            "sub_agent": "cinderella",
            "axis": "grounding",
            "model": None,
            "call_count": 100,
            "input_tokens": 0,
            "output_tokens": 0,
            "images_generated": 0,
            "audio_chars": 0,
            "grounded_search_queries": 4_500,
        }
    ]
    fixed = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    counter = CostCounter(
        bq,
        project_id="p",
        ceilings={"grounding": 5_000},
        flush_interval_seconds=10.0,
        clock=_fixed_clock(fixed),
    )
    await counter.recover_from_bigquery()
    # Already at 4,500 — should still pass under 5,000 ceiling.
    await counter.assert_under_ceiling(axis="grounding", agent="scout_desk")
    # Add 600 more grounded_queries -> over ceiling.
    await counter.increment(
        agent="scout_desk",
        sub_agent="cinderella",
        axis="grounding",
        model=None,
        grounded_queries=600,
    )
    with pytest.raises(CostCeilingExceeded):
        await counter.assert_under_ceiling(axis="grounding", agent="scout_desk")
