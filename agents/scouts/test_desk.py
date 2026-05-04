"""Unit tests for `ScoutDesk.dispatch_one` and `ScoutDesk.run_pass`.

The ADK Runner is mocked at the `_run_adk_once` boundary so unit tests don't
hit live Vertex AI. Live Gemini exercises happen in the integration test +
post-commit smoke run.

Cases (from the Day-3 prompt §6):
  1. ScoutDesk constructs four sub-scouts.
  2. `dispatch_one('nonexistent', ...)` returns an error dict.
  3. `dispatch_one(...)` calls Runner once and returns shape including
     `scout`, `story_unit_id`, `lead_report_id`.
  4. `dispatch_one(...)` short-circuits on `CostCeilingExceeded`, emits a
     Wire thinking event, and does NOT call the Runner.
  5. `run_pass` returns Lead Reports written during the pass-window
     (read-back from the firestore stub).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.cost.counters import CostCeilingExceeded
from agents.scouts.desk import ScoutDesk
from agents.wire.types import InvestigationContext


# -- Fakes --------------------------------------------------------------------


class _RecordingWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return f"wire-evt-{len(self.emitted)}"


class _DocSnap:
    def __init__(self, data: dict) -> None:
        self._data = dict(data)
        self.id = data.get("id", "doc-id")

    def to_dict(self) -> dict:
        return dict(self._data)


class _FakeColl:
    def __init__(self, parent: "_FakeFirestore", name: str) -> None:
        self._parent = parent
        self._name = name

    def add(self, doc: dict) -> tuple:
        # Real firestore returns (write_result, doc_ref). Stubs may return
        # anything; test code just needs an "added" effect we can read back.
        self._parent.added.setdefault(self._name, []).append(dict(doc))
        return (mock.Mock(), mock.Mock(id=doc.get("id", "added-doc")))

    def where(self, *args, **kwargs) -> "_FakeColl":
        return self

    def order_by(self, *args, **kwargs) -> "_FakeColl":
        return self

    def limit(self, _n: int) -> "_FakeColl":
        return self

    def stream(self) -> list:
        # Return everything written so far; the desk's where()/in-process
        # filter handles created_at >= since.
        return [_DocSnap(d) for d in self._parent.added.get(self._name, [])]


class _FakeFirestore:
    def __init__(self) -> None:
        self.added: dict[str, list[dict]] = {}

    def collection(self, name: str) -> _FakeColl:
        return _FakeColl(self, name)


def _prompts() -> dict[str, str]:
    return {
        "cinderella_scout": "You are the Cinderella Scout (test).",
        "comeback_scout": "You are the Comeback Scout (test).",
        "hometown_scout": "You are the Hometown Scout (test).",
        "echo_scout": "You are the Echo Scout (test).",
    }


def _build_desk(
    *,
    wire: Any | None = None,
    firestore: Any | None = None,
    cost_counter: Any | None = None,
) -> ScoutDesk:
    return ScoutDesk(
        prompts=_prompts(),
        wire=wire or _RecordingWire(),
        bigquery=None,
        firestore=firestore if firestore is not None else _FakeFirestore(),
        hnd=mock.Mock(),
        scout_model="gemini-3-flash-preview",
        cost_counter=cost_counter,
    )


# -- Tests --------------------------------------------------------------------


def test_scout_desk_constructs_four_subscouts():
    """All four sub-scouts wired up via `build_*_scout`. In placeholder mode
    (no ADK on host) each is a `_PlaceholderAgent` with name + tools."""
    desk = _build_desk()
    assert len(desk.sub_scouts) == 4
    names = sorted(getattr(s, "name", None) for s in desk.sub_scouts)
    assert names == ["cinderella", "comeback", "echo", "hometown"]
    # Each sub-scout has the four standard tools bound.
    for s in desk.sub_scouts:
        assert len(getattr(s, "tools", [])) == 4


@pytest.mark.asyncio
async def test_dispatch_one_invalid_scout_id_returns_error():
    """dispatch_one('nonexistent', ...) returns dispatched=False with error."""
    desk = _build_desk()
    result = await desk.dispatch_one("nonexistent", "us-ia-mt-pleasant")
    assert result["dispatched"] is False
    assert "error" in result
    assert "unknown scout_id" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_one_calls_runner_and_returns_result():
    """dispatch_one runs the Runner and returns the expected shape including
    `lead_report_id` when the scout's tool wrote a /lead_reports doc."""
    fs = _FakeFirestore()
    desk = _build_desk(firestore=fs)

    async def _runner_writes_report(*, agent, user_message, investigation_id, scout_id):
        # Mimic the scout's `write_lead_report` tool persisting a doc DURING
        # the dispatch (so `created_at >= dispatch_started_at`).
        fs.added.setdefault("lead_reports", []).append(
            {
                "id": "lead-001",
                "scout": "cinderella",
                "story_unit_id": "us-ia-mt-pleasant",
                "story_unit_title": "Mount Pleasant, IA",
                "story_unit_type": "place",
                "signal_type": "cinderella-disproportionate",
                "confidence": 0.82,
                "notes": "no athlete names here",
                "evidence_refs": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "tool_calls": [{"name": "write_lead_report", "args": {}}],
            "input_tokens": 250,
            "output_tokens": 60,
        }

    with mock.patch.object(desk, "_run_adk_once", side_effect=_runner_writes_report) as m:
        result = await desk.dispatch_one(
            "cinderella",
            "us-ia-mt-pleasant",
            ctx=InvestigationContext(investigation_id="inv-test", compression_factor=1.0),
        )

    assert m.await_count == 1
    assert result["dispatched"] is True
    assert result["scout"] == "cinderella"
    assert result["story_unit_id"] == "us-ia-mt-pleasant"
    assert result["lead_report_id"] == "lead-001"
    assert result["input_tokens"] == 250
    assert result["output_tokens"] == 60
    assert result["tool_calls"][0]["name"] == "write_lead_report"


@pytest.mark.asyncio
async def test_dispatch_one_cost_ceiling_skips_runner():
    """When the cost counter raises CostCeilingExceeded, dispatch_one does
    NOT invoke the Runner and emits a Wire thinking event."""
    wire = _RecordingWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded(
            "axis=gemini_flash agent=scout_desk total=999 >= limit=200"
        )
    )
    desk = _build_desk(wire=wire, cost_counter=cost_counter)

    async def _should_not_be_called(**_kwargs):
        raise AssertionError("Runner should not be invoked when ceiling hit")

    with mock.patch.object(desk, "_run_adk_once", side_effect=_should_not_be_called):
        result = await desk.dispatch_one("cinderella", "us-ia-mt-pleasant")

    assert result["dispatched"] is False
    assert result["reason"] == "cost_ceiling"
    cap_events = [
        e for e in wire.emitted
        if "Flash cap reached" in e.get("message", "")
    ]
    assert len(cap_events) == 1
    assert cap_events[0]["agent"] == "scout_desk"
    assert cap_events[0]["sub_agent"] == "cinderella"


@pytest.mark.asyncio
async def test_run_pass_returns_lead_reports_from_firestore():
    """run_pass reads back any /lead_reports docs created during the pass-window.

    We mock `_run_adk_once` to be a no-op (no real model calls) and seed the
    Firestore stub with two reports — one BEFORE pass_start and one AFTER.
    Only the AFTER report should be returned.
    """
    fs = _FakeFirestore()
    desk = _build_desk(firestore=fs)

    # Seed an OLD doc that should be filtered out by created_at < pass_start.
    fs.added["lead_reports"] = [
        {
            "id": "lead-old",
            "scout": "cinderella",
            "story_unit_id": "us-old",
            "created_at": "1970-01-01T00:00:00+00:00",
        }
    ]

    async def _runner_writes_one_post_start(*, agent, user_message, investigation_id, scout_id):
        # Simulate one scout's tool persisting a Lead Report.
        if scout_id == "cinderella":
            fs.added["lead_reports"].append(
                {
                    "id": "lead-new",
                    "scout": "cinderella",
                    "story_unit_id": "us-ia-mt-pleasant",
                    "story_unit_title": "Mount Pleasant, IA",
                    "story_unit_type": "place",
                    "signal_type": "cinderella-disproportionate",
                    "confidence": 0.81,
                    "notes": "places only — no athlete names",
                    "evidence_refs": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        return {"tool_calls": [], "input_tokens": 0, "output_tokens": 0}

    with mock.patch.object(desk, "_run_adk_once", side_effect=_runner_writes_one_post_start):
        results = await desk.run_pass(
            ["us-ia-mt-pleasant"],
            ctx=InvestigationContext(investigation_id="inv-pass-test"),
        )

    ids = [r.get("id") for r in results]
    assert "lead-new" in ids
    assert "lead-old" not in ids


@pytest.mark.asyncio
async def test_dispatch_one_increments_cost_counter_after_runner():
    """On a successful dispatch, the cost counter is incremented with the
    token usage from the Runner result."""
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock()
    cost_counter.increment = mock.AsyncMock()
    desk = _build_desk(cost_counter=cost_counter)

    async def _runner_ok(*, agent, user_message, investigation_id, scout_id):
        return {
            "tool_calls": [],
            "input_tokens": 1500,
            "output_tokens": 300,
        }

    with mock.patch.object(desk, "_run_adk_once", side_effect=_runner_ok):
        result = await desk.dispatch_one("hometown", "us-ia-mt-pleasant")

    assert result["dispatched"] is True
    cost_counter.assert_under_ceiling.assert_awaited_once()
    cost_counter.increment.assert_awaited_once()
    inc_kwargs = cost_counter.increment.await_args.kwargs
    assert inc_kwargs["agent"] == "scout_desk"
    assert inc_kwargs["sub_agent"] == "hometown"
    assert inc_kwargs["axis"] == "gemini_flash"
    assert inc_kwargs["input_tokens"] == 1500
    assert inc_kwargs["output_tokens"] == 300


@pytest.mark.asyncio
async def test_write_lead_report_tool_forwards_to_hnd():
    """The bound write_lead_report tool calls hnd.record_lead_report so the
    HND detector sees every Lead Report (BUILD_SPEC §5.2 + HOE-DEC-023).

    We inspect the bound tool list on a sub-scout and call its
    write_lead_report directly — no Runner needed.
    """
    hnd = mock.Mock()
    hnd.record_lead_report = mock.AsyncMock()
    fs = _FakeFirestore()
    desk = ScoutDesk(
        prompts=_prompts(),
        wire=_RecordingWire(),
        bigquery=None,
        firestore=fs,
        hnd=hnd,
        scout_model="gemini-3-flash-preview",
    )
    cinderella = next(s for s in desk.sub_scouts if getattr(s, "name", None) == "cinderella")
    # Tool order matches build_scout_tools: [wire_emit, query_candidates,
    # grounded_search, write_lead_report].
    write_lead_report = cinderella.tools[3]

    report_id = await write_lead_report(
        story_unit_id="us-ia-mt-pleasant",
        story_unit_title="Mount Pleasant, IA",
        story_unit_type="place",
        signal_type="cinderella-disproportionate",
        confidence=0.82,
        notes="eight Olympians and Paralympians since 1976",
        evidence_refs=["https://example.test/quad-city-times"],
    )
    assert isinstance(report_id, str) and len(report_id) > 0
    assert hnd.record_lead_report.await_count == 1
    arg = hnd.record_lead_report.await_args.args[0]
    assert arg.story_unit_id == "us-ia-mt-pleasant"
    assert arg.scout == "cinderella"
    assert arg.confidence == 0.82
    # And the Firestore stub got the doc.
    assert any(
        d["story_unit_id"] == "us-ia-mt-pleasant"
        for d in fs.added.get("lead_reports", [])
    )
