"""Unit tests for `agents/investigator/tools.py`.

Five required cases plus a couple of supporting tests for the geography
+ helper paths. The point of this file is to prove the place-over-person
discipline at the SQL boundary: `query_historical_athletes` MUST aggregate
before returning, even when underlying rows carry athlete-bearing columns.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.cost.counters import CostCeilingExceeded
from agents.investigator.tools import (
    LeadReportNotFoundError,
    _decade_bounds,
    _decade_label,
    build_investigator_tools,
)


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, **_kw) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _FakeColl:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = docs or []
        self.added: list[dict] = []

    def stream(self):
        return [_FakeDoc(d) for d in self._docs]

    def add(self, doc: dict) -> tuple:
        self.added.append(dict(doc))
        return (mock.Mock(), mock.Mock(id=f"fs-{len(self.added)}"))


class _FakeDoc:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.id = data.get("id", "fake-id")

    def to_dict(self) -> dict:
        return dict(self._data)


class _FakeFirestore:
    def __init__(self, *, lead_reports=None, investigation_packets=None) -> None:
        self.collections: dict[str, _FakeColl] = {
            "lead_reports": _FakeColl(lead_reports or []),
            "investigation_packets": _FakeColl(investigation_packets or []),
        }

    def collection(self, name: str) -> _FakeColl:
        return self.collections.setdefault(name, _FakeColl())


class _FakeBigQueryRow:
    """A row with attribute access (mirrors `bigquery.Row`)."""

    def __init__(self, **fields) -> None:
        self._fields = fields

    def get(self, key, default=None):
        return self._fields.get(key, default)

    def __getitem__(self, key):
        return self._fields[key]


class _FakeBigQueryJob:
    def __init__(self, rows: list[_FakeBigQueryRow]) -> None:
        self._rows = rows

    def result(self):
        return iter(self._rows)


class _FakeBigQuery:
    """Minimal BQ stub — captures the SQL + params so we can assert no
    athlete-bearing columns leak into return paths."""

    def __init__(self, rows: list[_FakeBigQueryRow]) -> None:
        self._rows = rows
        self.last_sql: str | None = None
        self.last_params: list = []

    def query(self, sql: str, *, job_config=None):
        self.last_sql = sql
        self.last_params = list(getattr(job_config, "query_parameters", []) or [])
        return _FakeBigQueryJob(self._rows)


# -- Helpers ------------------------------------------------------------------


def _build_tools(*, wire=None, firestore=None, bigquery=None, cost_counter=None) -> dict[str, Any]:
    """Build tools and return as a `{name: tool}` dict for clarity in tests."""
    tools = build_investigator_tools(
        wire=wire or _FakeWire(),
        firestore=firestore,
        bigquery=bigquery,
        cost_counter=cost_counter,
    )
    return {getattr(t, "__name__", ""): t for t in tools}


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_historical_athletes_returns_aggregate_only():
    """Even if the BigQuery rows have athlete-identifying columns, the tool
    MUST return aggregate counts only (CONSTITUTION Law 4)."""
    # Underlying rows (BigQuery) have sport/year/state — we project a name-
    # bearing column too to prove the tool drops it.
    rows = [
        _FakeBigQueryRow(sport="Athletics", games_year=1964, hometown_state="IA",
                         games_type="summer_olympic", athlete_id="banned-001"),
        _FakeBigQueryRow(sport="Athletics", games_year=1968, hometown_state="IA",
                         games_type="summer_olympic", athlete_id="banned-002"),
        _FakeBigQueryRow(sport="Swimming", games_year=1972, hometown_state="IA",
                         games_type="summer_olympic", athlete_id="banned-003"),
    ]
    bq = _FakeBigQuery(rows)
    tools = _build_tools(bigquery=bq)
    out = await tools["query_historical_athletes"](
        sport=None, decade="1960s", hometown_state="IA", limit=50
    )
    assert isinstance(out, dict)
    assert out["count"] == 3
    assert out["by_decade"] == {"1960s": 2, "1970s": 1}
    assert "Athletics" in out["by_sport"]
    assert out["by_state"]["IA"] == 3
    # Place-over-person: no names anywhere in the output.
    flat = repr(out)
    assert "athlete_id" not in flat
    assert "banned" not in flat
    # Verify the SQL itself didn't SELECT athlete_id either (defense in
    # depth — the BQ row could have been mocked larger than what we
    # selected, but our SQL must not pull the names column).
    assert "athlete_id" not in (bq.last_sql or "")


@pytest.mark.asyncio
async def test_grounded_search_calls_cost_counter():
    """Cost counter `assert_under_ceiling` is awaited once per call."""
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock()
    cost_counter.increment = mock.AsyncMock()
    tools = _build_tools(cost_counter=cost_counter)

    # google.genai isn't installed in test env -> tool returns the
    # `genai_not_installed` error path. The ceiling check must still fire
    # before that.
    out = await tools["grounded_search"]("Mount Pleasant Iowa pipeline")

    cost_counter.assert_under_ceiling.assert_awaited_once_with(
        axis="grounding", agent="investigator"
    )
    assert out["query"] == "Mount Pleasant Iowa pipeline"


@pytest.mark.asyncio
async def test_grounded_search_skips_on_cost_ceiling():
    """When `assert_under_ceiling` raises, the tool returns a cost_ceiling
    error and does NOT call generate_content."""
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=grounding total=5000 >= limit=5000")
    )
    tools = _build_tools(cost_counter=cost_counter)
    out = await tools["grounded_search"]("a query")
    assert out["error"] == "cost_ceiling"
    assert out["summary"] == ""
    assert out["citations"] == []


@pytest.mark.asyncio
async def test_call_deep_research_emits_thinking_on_timeout():
    """When the underlying call raises (or times out), the tool emits a Wire
    `thinking` event with the 'stalled' message and returns None."""
    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock()
    cost_counter.increment = mock.AsyncMock()
    tools = _build_tools(wire=wire, cost_counter=cost_counter)

    # Day-4 stub raises _DeepResearchUnavailable inside the wrapper, which
    # the wrapper converts to the same Wire-thinking + None contract as a
    # timeout. (The HoE will swap in a real timeout-bearing call later.)
    out = await tools["call_deep_research"]("What's the place's pipeline arc?")

    assert out is None
    stalled = [
        e for e in wire.emitted
        if "deep research stalled" in e.get("message", "")
    ]
    assert len(stalled) == 1
    assert stalled[0]["agent"] == "investigator"
    assert stalled[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_call_deep_research_skips_on_cost_ceiling():
    """When the daily cap is reached, deep_research returns None silently
    (no Wire event, no API call)."""
    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=deep_research total=10 >= limit=10")
    )
    tools = _build_tools(wire=wire, cost_counter=cost_counter)
    out = await tools["call_deep_research"]("any question")
    assert out is None
    # No "stalled" texture when we never tried — the room shouldn't lie.
    stalled = [
        e for e in wire.emitted
        if "deep research stalled" in e.get("message", "")
    ]
    assert stalled == []


@pytest.mark.asyncio
async def test_write_investigation_packet_persists_to_firestore():
    """write_investigation_packet writes to /investigation_packets/ with the
    BUILD_SPEC §8.4 schema and returns the doc id."""
    firestore = _FakeFirestore()
    tools = _build_tools(firestore=firestore)
    packet_id = await tools["write_investigation_packet"](
        story_unit_id="us-ia-mt-pleasant",
        story_unit_title="Mt. Pleasant, Iowa",
        story_unit_type="place",
        narrative_spine="The town's first Olympian came in 1964.",
        geography={"state": "IA", "region": "Midwest", "population": 8500, "notes": ""},
        historical_context={
            "era_parallel": "1960s Athletics era",
            "pattern_notes": "regional pipeline since Olympic Games Tokyo 1964",
        },
        trend_signals={
            "olympic_count_history": [{"year": 1964, "count": 1}],
            "paralympic_count_history": [],
        },
        sources=[
            {"url": "https://example.com/a", "outlet": "Quad-City Times", "relevance_note": "hometown coverage"},
        ],
        paralympic_depth_score=0.4,
        ready_for_storyteller=False,
    )
    assert isinstance(packet_id, str) and len(packet_id) > 0
    coll = firestore.collections["investigation_packets"]
    assert len(coll.added) == 1
    persisted = coll.added[0]
    # BUILD_SPEC §8.4 required fields.
    for key in (
        "id", "story_unit_id", "story_unit_title", "story_unit_type",
        "narrative_spine", "geography", "historical_context",
        "trend_signals", "sources", "paralympic_depth_score",
        "ready_for_storyteller", "created_at",
    ):
        assert key in persisted, f"missing {key!r} in persisted packet"
    assert persisted["story_unit_type"] == "place"
    assert persisted["paralympic_depth_score"] == 0.4
    assert persisted["ready_for_storyteller"] is False
    # NIL discipline: the narrative_spine MUST not contain forbidden
    # words. The Investigator's prompt enforces this — the test fixture
    # is already compliant. We just sanity-check it.
    assert "former Olympian" not in persisted["narrative_spine"]
    assert "inspirational" not in persisted["narrative_spine"]


@pytest.mark.asyncio
async def test_write_investigation_packet_emits_wire_thinking_on_firestore_failure():
    """When the Firestore write raises, the tool MUST emit a Wire `thinking`
    event so the operator sees the failure (BUILD_SPEC §17.1 — "fail visibly
    on the Wire"). The function still returns a packet_id to preserve the
    LLM-facing return contract; the failure visibility is the new bit.
    """

    class _RaisingColl:
        def __init__(self) -> None:
            self.added: list[dict] = []

        def stream(self):
            return iter([])

        def add(self, doc):  # noqa: D401
            raise RuntimeError("simulated firestore unavailable")

    class _RaisingFirestore:
        def collection(self, name: str):
            return _RaisingColl()

    wire = _FakeWire()
    tools = _build_tools(wire=wire, firestore=_RaisingFirestore())
    packet_id = await tools["write_investigation_packet"](
        story_unit_id="us-ia-mt-pleasant",
        story_unit_title="Mt. Pleasant, Iowa",
        story_unit_type="place",
        narrative_spine="The town's first Olympian came in 1964.",
        geography={"state": "IA", "region": "Midwest", "population": 8500, "notes": ""},
        historical_context={"era_parallel": "1960s Athletics era", "pattern_notes": ""},
        trend_signals={"olympic_count_history": [], "paralympic_count_history": []},
        sources=[],
        paralympic_depth_score=0.0,
        ready_for_storyteller=False,
    )
    # Return contract preserved (model thinks it succeeded — that's the
    # contract; the operator sees the failure on the Wire).
    assert isinstance(packet_id, str) and len(packet_id) > 0
    # Wire failure event emitted.
    failure_events = [
        e for e in wire.emitted
        if "investigation packet write failed" in e.get("message", "")
    ]
    assert len(failure_events) == 1
    assert failure_events[0]["agent"] == "investigator"
    assert failure_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_read_lead_report_raises_on_missing_doc():
    """read_lead_report raises LeadReportNotFoundError when nothing matches."""
    firestore = _FakeFirestore(lead_reports=[
        {"id": "lead-other", "story_unit_id": "us-other"},
    ])
    tools = _build_tools(firestore=firestore)
    with pytest.raises(LeadReportNotFoundError):
        await tools["read_lead_report"]("lead-missing")


@pytest.mark.asyncio
async def test_read_lead_report_returns_match():
    """Happy path: scan finds the matching id."""
    firestore = _FakeFirestore(lead_reports=[
        {"id": "lead-001", "story_unit_id": "us-ia-mt-pleasant", "scout": "hometown"},
    ])
    tools = _build_tools(firestore=firestore)
    out = await tools["read_lead_report"]("lead-001")
    assert out["id"] == "lead-001"
    assert out["story_unit_id"] == "us-ia-mt-pleasant"
    assert out["scout"] == "hometown"


@pytest.mark.asyncio
async def test_query_geography_returns_dicts():
    """query_geography returns dicts; no athlete data on this table."""
    rows = [
        {"place_id": "p-1", "city": "Mount Pleasant", "state": "IA",
         "region": "Midwest", "population": 8500, "latitude": 40.96,
         "longitude": -91.55, "regional_sport_infrastructure_notes": "small high school"},
    ]
    bq = _FakeBigQuery([_FakeBigQueryRow(**r) for r in rows])

    # Patch the BQ row -> dict conversion.
    class _DictRow(dict):
        pass

    real_rows = [_DictRow(r) for r in rows]
    bq._rows = real_rows  # type: ignore[attr-defined]

    tools = _build_tools(bigquery=bq)
    out = await tools["query_geography"](state="IA", limit=20)
    assert isinstance(out, list)
    assert out and out[0]["city"] == "Mount Pleasant"
    assert out[0]["state"] == "IA"


# -- Helper coverage ----------------------------------------------------------


def test_decade_bounds_round_to_decade():
    assert _decade_bounds("1960s") == (1960, 1969)
    assert _decade_bounds("1962") == (1960, 1969)
    assert _decade_bounds("pre-1900") == (1880, 1899)
    assert _decade_bounds(None) == (None, None)
    assert _decade_bounds("garbage") == (None, None)


def test_decade_label_buckets_year():
    assert _decade_label(1964) == "1960s"
    assert _decade_label(2024) == "2020s"
    assert _decade_label(None) == "unknown"
