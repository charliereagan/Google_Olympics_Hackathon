"""Unit tests for `InvestigatorAgent.investigate` (Day-4 work).

Mirrors `agents/editor/test_agent.py`. Six required cases:
  1. constructs with the Pro model id
  2. skips on AGENT_RUNTIME_PAUSED=1
  3. handles a Runner exception (BUILD_SPEC §17.1)
  4. skips on CostCeilingExceeded
  5. writes an Investigation Packet on success
  6. handles missing Lead Report

The ADK Runner is mocked at the `_run_adk_once` boundary so we don't hit
live Vertex AI. The tools are not invoked in these tests — the test
mocks `_run_adk_once` to return a synthetic shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.investigator.agent import InvestigatorAgent
from agents.investigator.tools import LeadReportNotFoundError


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return "fake-wire-id"


class _FakeColl:
    """Minimal collection stub. `_docs` lets a test seed the contents."""

    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs = docs or []
        self.added: list[dict] = []

    def where(self, *args, **kwargs) -> "_FakeColl":
        return self

    def order_by(self, *args, **kwargs) -> "_FakeColl":
        return self

    def limit(self, n: int) -> "_FakeColl":
        return self

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
    """Collection-routing stub. Indexed by collection name."""

    def __init__(self, *, lead_reports: list[dict] | None = None,
                 investigation_packets: list[dict] | None = None) -> None:
        self.collections: dict[str, _FakeColl] = {
            "lead_reports": _FakeColl(lead_reports or []),
            "investigation_packets": _FakeColl(investigation_packets or []),
        }

    def collection(self, name: str) -> _FakeColl:
        return self.collections.setdefault(name, _FakeColl())


@dataclass
class _FakeRuntimeState:
    last_think_cycle: datetime | None = None


# -- Helpers ------------------------------------------------------------------


def _build_investigator(
    *,
    wire: Any | None = None,
    firestore: Any | None = None,
    bigquery: Any | None = None,
    cost_counter: Any | None = None,
    runtime_state: Any | None = None,
) -> InvestigatorAgent:
    return InvestigatorAgent(
        prompt="You are the Investigator (test).",
        wire=wire or _FakeWire(),
        firestore=firestore if firestore is not None else _FakeFirestore(),
        bigquery=bigquery,
        model_id="gemini-3.1-pro-preview",
        cost_counter=cost_counter,
        runtime_state=runtime_state,
    )


def _seed_lead_report(report_id: str = "lead-001", story_unit_id: str = "us-ia-mt-pleasant") -> dict:
    return {
        "id": report_id,
        "story_unit_id": story_unit_id,
        "story_unit_title": "Mt. Pleasant, Iowa",
        "story_unit_type": "place",
        "scout": "hometown",
        "signal_type": "hometown-disproportionate",
        "confidence": 1.0,
        "notes": "Eight Olympians and Paralympians from this town since 1976.",
        "evidence_refs": ["https://example.com/article"],
        "status": "investigating",
        "created_at": "2026-05-02T01:00:00+00:00",
        "updated_at": "2026-05-02T01:00:00+00:00",
    }


# -- Tests --------------------------------------------------------------------


def test_investigator_constructs_with_pro_model():
    """Default model is `gemini-3.1-pro-preview` per BUILD_SPEC §3.1."""
    investigator = _build_investigator()
    assert investigator.model == "gemini-3.1-pro-preview"
    # Eight tools: wire_emit + 6 runtime tools + pull_vocabulary.
    tool_names = [getattr(t, "__name__", "") for t in investigator._bound_tools]
    assert "wire_emit" in tool_names
    assert "read_lead_report" in tool_names
    assert "grounded_search" in tool_names
    assert "query_historical_athletes" in tool_names
    assert "query_geography" in tool_names
    assert "call_deep_research" in tool_names
    assert "write_investigation_packet" in tool_names
    assert "pull_vocabulary" in tool_names


@pytest.mark.asyncio
async def test_investigate_skips_on_pause(monkeypatch):
    """With AGENT_RUNTIME_PAUSED=1, investigate returns early."""
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    investigator = _build_investigator()

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when paused")

    with mock.patch.object(investigator, "_run_adk_once", side_effect=_should_not_be_called):
        result = await investigator.investigate("lead-001")

    assert result == {"action": "skipped", "reason": "paused"}


@pytest.mark.asyncio
async def test_investigate_handles_runner_exception():
    """When the Runner raises on BOTH attempts, investigate emits a thinking
    event and returns action='error'."""
    wire = _FakeWire()
    firestore = _FakeFirestore(lead_reports=[_seed_lead_report()])
    investigator = _build_investigator(wire=wire, firestore=firestore)

    async def _always_raises(**_kwargs):
        raise RuntimeError("model timeout")

    with mock.patch.object(investigator, "_run_adk_once", side_effect=_always_raises):
        result = await investigator.investigate("lead-001")

    assert result["action"] == "error"
    assert result["lead_report_id"] == "lead-001"
    failure_events = [
        e for e in wire.emitted if "model returned an error" in e.get("message", "")
    ]
    assert len(failure_events) == 1
    assert failure_events[0]["agent"] == "investigator"
    assert failure_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_investigate_handles_cost_ceiling():
    """When the cost counter raises CostCeilingExceeded, investigate emits a
    'pausing' Wire event and skips."""
    from agents.cost.counters import CostCeilingExceeded

    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=gemini_pro total=999 >= limit=200")
    )
    cost_counter.snapshot_today = mock.Mock(return_value={"gemini_pro": 999})

    investigator = _build_investigator(wire=wire, cost_counter=cost_counter)

    result = await investigator.investigate("lead-001")

    assert result == {"action": "skipped", "reason": "cost_ceiling"}
    cap_events = [
        e for e in wire.emitted if "daily Pro cap reached" in e.get("message", "")
    ]
    assert len(cap_events) == 1
    assert "investigator pausing" in cap_events[0]["message"]


@pytest.mark.asyncio
async def test_investigate_writes_investigation_packet_on_success():
    """On a successful Runner result, the Investigator surfaces the
    investigation_packet_id from Firestore and emits a milestone event."""
    wire = _FakeWire()
    # Seed a packet that the model "would have" written via its tool call.
    pre_existing_packet = {
        "id": "pkt-001",
        "story_unit_id": "us-ia-mt-pleasant",
        "story_unit_title": "Mt. Pleasant, Iowa",
        "story_unit_type": "place",
        "narrative_spine": "The town's first Olympian came in 1964.",
        "ready_for_storyteller": True,
        "created_at": "2026-05-02T02:00:00+00:00",
    }
    firestore = _FakeFirestore(
        lead_reports=[_seed_lead_report()],
        investigation_packets=[pre_existing_packet],
    )
    investigator = _build_investigator(wire=wire, firestore=firestore)

    async def _runner_ok(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [
                {"name": "grounded_search", "args": {"query": "Mt. Pleasant Iowa"}},
                {"name": "write_investigation_packet", "args": {}},
            ],
            "input_tokens": 4200,
            "output_tokens": 890,
        }

    with mock.patch.object(investigator, "_run_adk_once", side_effect=_runner_ok):
        result = await investigator.investigate("lead-001")

    assert result["action"] == "ok"
    assert result["lead_report_id"] == "lead-001"
    assert result["story_unit_id"] == "us-ia-mt-pleasant"
    assert result["investigation_packet_id"] == "pkt-001"
    # Milestone event emitted.
    milestone_events = [
        e for e in wire.emitted if e.get("message_type") == "milestone"
    ]
    assert len(milestone_events) >= 1
    assert "Investigation packet drafted" in milestone_events[0]["message"]


@pytest.mark.asyncio
async def test_investigate_handles_lead_report_not_found():
    """Missing Lead Report → emit thinking event, return error."""
    wire = _FakeWire()
    firestore = _FakeFirestore(lead_reports=[])  # empty
    investigator = _build_investigator(wire=wire, firestore=firestore)

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when lead missing")

    with mock.patch.object(investigator, "_run_adk_once", side_effect=_should_not_be_called):
        result = await investigator.investigate("lead-missing")

    assert result["action"] == "error"
    assert result["reason"] == "lead_report_not_found"
    assert result["lead_report_id"] == "lead-missing"
    miss_events = [
        e for e in wire.emitted if "lead report missing" in e.get("message", "")
    ]
    assert len(miss_events) == 1
    assert miss_events[0]["agent"] == "investigator"
    assert miss_events[0]["message_type"] == "thinking"


@pytest.mark.asyncio
async def test_investigate_records_cost_and_stamp_on_success():
    """On success, increments the cost counter with token counts and stamps
    last_think_cycle on the runtime state (parity with Editor)."""
    wire = _FakeWire()
    state = _FakeRuntimeState()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock()
    cost_counter.increment = mock.AsyncMock()
    cost_counter.snapshot_today = mock.Mock(return_value={})

    firestore = _FakeFirestore(
        lead_reports=[_seed_lead_report()],
        investigation_packets=[
            {
                "id": "pkt-002",
                "story_unit_id": "us-ia-mt-pleasant",
                "created_at": "2026-05-02T02:30:00+00:00",
            }
        ],
    )
    investigator = _build_investigator(
        wire=wire, firestore=firestore, cost_counter=cost_counter, runtime_state=state
    )

    async def _runner_ok(*, user_message: str, investigation_id: str):
        return {
            "tool_calls": [],
            "input_tokens": 1200,
            "output_tokens": 80,
        }

    with mock.patch.object(investigator, "_run_adk_once", side_effect=_runner_ok):
        result = await investigator.investigate("lead-001")

    assert result["action"] == "ok"
    assert state.last_think_cycle is not None
    delta = (datetime.now(timezone.utc) - state.last_think_cycle).total_seconds()
    assert delta < 5.0
    cost_counter.assert_under_ceiling.assert_awaited_once()
    cost_counter.increment.assert_awaited_once()
    inc_kwargs = cost_counter.increment.await_args.kwargs
    assert inc_kwargs["agent"] == "investigator"
    assert inc_kwargs["axis"] == "gemini_pro"
    assert inc_kwargs["input_tokens"] == 1200
    assert inc_kwargs["output_tokens"] == 80
