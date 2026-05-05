"""End-to-end test of the full publication chain.

Covers: a synthetic Lead Report flows through Investigator → Storyteller
→ Equity Editor → Publish Gate (all 7 sub-stages) → Narrator, producing
a NarrationManifest and a PublishAudit.

This is the strongest integration coverage we have — it exercises the
seven-agent contract end-to-end without hitting live infrastructure.
The live equivalent is `scripts/probe_full_chain.py` (this directory's
sibling).

Mocking strategy:
  - Real agent classes (EditorAgent, InvestigatorAgent, StorytellerAgent,
    EquityEditorAgent, PublishGateAgent, NarratorAgent).
  - Real `WireEmitter` and real `NilRedactionLayer` (Day-2 stub) seeded
    with a 600-row synthetic registry — proves the proxy + Layer fire on
    every Wire emit.
  - In-memory async-shaped Firestore stub (`tests/integration/_chain_stubs.py`).
  - The ADK Runner is replaced (per-agent `_run_adk_once`) by a stub that
    actually executes the closure-bound tools the agent would call —
    capturing real tool responses. This means Storyteller →
    `request_equity_review` → real `EquityEditor.review_draft` →
    `clear_draft` → mutation lands on the in-memory Firestore. True
    wiring, not simulated.
  - Publish Gate sub-stages are stubbed to pass (the orchestrator
    decision logic is the integration-relevant part — sub-stage
    correctness is tested in `agents/publish_gate/test_orchestrator.py`).
  - Narrator's TTS client + storage are stubbed.

Pass criteria for the happy-path test:
  - Investigator wrote one Investigation Packet to Firestore.
  - Storyteller wrote one StoryDraft with publish_gate_decision='cleared'.
  - Publish Gate wrote one PublishAudit with final_decision='cleared' and
    all 7 sub-stage keys present.
  - Narrator returned a NarrationManifest with audio_urls populated.
  - Wire events were emitted at every boundary; all carry
    `nil_redaction_log` (proves the proxy ran).

NIL discipline (CONSTITUTION Law 4): zero individual Team USA athlete
names anywhere in this file. Synthetic place id `place_test_iowa`,
synthetic athlete fixture names (Synthetic Person N).
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.editor.agent import EditorAgent
from agents.equity_editor.agent import EquityEditorAgent
from agents.investigator.agent import InvestigatorAgent
from agents.narrator.agent import NarratorAgent
from agents.publish_gate.nil_redaction_layer_stub import NilRedactionLayer
from agents.publish_gate.orchestrator import PublishGateAgent
from agents.storyteller.agent import StorytellerAgent
from agents.wire.emit import WireEmitter

from tests.integration._chain_stubs import (
    FsClient,
    StubStorage,
    StubTtsClient,
    invoke_bound_tool,
    make_adk_runner_stub,
    make_runner_response,
    make_synthetic_registry_rows,
    synthetic_investigation_packet,
    synthetic_story_draft_args,
)


# --- Test-fixture builders ----------------------------------------------------


def _build_pass_substage(**extras) -> Any:
    class _Pass:
        def __init__(self, e: dict) -> None:
            self._e = e
            self.calls: list[dict] = []

        async def review(self, **kwargs):
            self.calls.append(kwargs)
            return {"passed": True, **self._e}

    return _Pass(extras)


def _build_pass_sync_substage(**extras) -> Any:
    class _SyncPass:
        def __init__(self, e: dict) -> None:
            self._e = e
            self.calls: list[dict] = []

        def review(self, **kwargs):
            self.calls.append(kwargs)
            return {"passed": True, **self._e}

    return _SyncPass(extras)


def _build_chain(
    *,
    fs: FsClient,
    nil_layer: NilRedactionLayer,
    runtime_state_holder: dict,
):
    """Construct all six agents wired against shared firestore + wire.

    `runtime_state_holder` is a dict with `{equity_editor, publish_gate,
    storyteller, investigator, narrator, editor}` references — the
    Storyteller's tool closures resolve `equity_editor` / `publish_gate`
    via this provider at call-time, so the order of construction doesn't
    matter.
    """
    wire = WireEmitter(fs, nil_layer)

    investigator = InvestigatorAgent(
        prompt="(test investigator prompt)",
        wire=wire,
        firestore=fs,
        bigquery=None,
    )
    equity_editor = EquityEditorAgent(
        prompt="(test equity editor prompt)",
        wire=wire,
        firestore=fs,
        bigquery=None,
    )
    storyteller = StorytellerAgent(
        prompt="(test storyteller prompt)",
        wire=wire,
        firestore=fs,
        bigquery=None,
        runtime_state=runtime_state_holder,
    )
    publish_gate = PublishGateAgent(
        prompt="(test publish_gate prompt)",
        wire=wire,
        firestore=fs,
        nil_layer=nil_layer,
        fact_check=_build_pass_substage(
            claims_checked=10,
            claims_removed=0,
            claims_softened=0,
            removed_claims=[],
            softened_claims=[],
        ),
        source_review=_build_pass_sync_substage(
            source_count=2, outlets=["Local Quad-City Times", "Iowa Public Radio"]
        ),
        parity_review=_build_pass_sync_substage(
            equity_cleared=True, equity_feedback=""
        ),
        safety_review=_build_pass_substage(
            invented_quotes=0,
            private_info_flags=0,
            failed_reasons=[],
            fallback_used=False,
        ),
        language_review=_build_pass_sync_substage(
            restricted_terms_flagged=0,
            flagged_terms=[],
            predictive_phrases_softened=0,
        ),
        visual_review=_build_pass_sync_substage(regenerations=0, stub=True),
    )
    narrator = NarratorAgent(
        wire=wire,
        firestore=fs,
        storage=StubStorage(),
        tts_client=StubTtsClient(),
    )
    editor = EditorAgent(
        prompt="(test editor prompt)",
        wire=wire,
        scout_desk=None,
        firestore=fs,
        investigator=investigator,
        equity_editor=equity_editor,
        storyteller=storyteller,
        publish_gate=publish_gate,
        narrator=narrator,
    )

    runtime_state_holder["equity_editor"] = equity_editor
    runtime_state_holder["publish_gate"] = publish_gate
    runtime_state_holder["storyteller"] = storyteller
    runtime_state_holder["investigator"] = investigator
    runtime_state_holder["narrator"] = narrator
    runtime_state_holder["editor"] = editor

    return {
        "wire": wire,
        "editor": editor,
        "investigator": investigator,
        "equity_editor": equity_editor,
        "storyteller": storyteller,
        "publish_gate": publish_gate,
        "narrator": narrator,
    }


def _seed_lead_report(fs: FsClient, *, lead_id: str, story_unit_id: str) -> None:
    fs.collection("lead_reports").add(
        {
            "id": lead_id,
            "story_unit_id": story_unit_id,
            "story_unit_title": "A small Iowa county pipeline (test)",
            "story_unit_type": "place",
            "scout": "cinderella",
            "signal_type": "test",
            "confidence": 0.85,
            "notes": "synthetic test lead — never references an athlete name",
            "evidence_refs": [],
            "status": "investigating",
            "created_at": "2026-05-02T12:00:00+00:00",
        }
    )


# -- A "runtime_state" provider object the Storyteller can dot-access ----------


class _RuntimeStateBag:
    """Dict-backed object that exposes attributes the storyteller looks up.

    Storyteller's `_resolve_runtime_attr(state_getter(), 'equity_editor')`
    expects either `state.equity_editor` or `state['equity_editor']`. We
    expose both.
    """

    def __init__(self) -> None:
        self._d: dict = {}

    def __setitem__(self, k: str, v: Any) -> None:
        self._d[k] = v

    def __getitem__(self, k: str) -> Any:
        return self._d[k]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._d:
            return self._d[name]
        raise AttributeError(name)

    def get(self, k: str, default: Any = None) -> Any:
        return self._d.get(k, default)


# --- Tests -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_chain_lead_to_narration() -> None:
    """One synthetic Lead Report → Investigation Packet → Story Draft →
    Equity-cleared → Publish Gate cleared → Narration manifest.

    Asserts the full chain wires up end-to-end without hitting live GCP.
    """
    # --- Bootstrap shared infra -----------------------------------------
    fs = FsClient()
    nil_layer = NilRedactionLayer(rows=make_synthetic_registry_rows(600), min_rows=500)
    assert nil_layer.is_loaded

    state = _RuntimeStateBag()
    chain = _build_chain(fs=fs, nil_layer=nil_layer, runtime_state_holder=state)

    # --- Pre-stage: seed Lead Report ------------------------------------
    lead_id = "lead-test-001"
    story_unit_id = "place_test_iowa"
    _seed_lead_report(fs, lead_id=lead_id, story_unit_id=story_unit_id)

    # --- Stage 1: Investigator ------------------------------------------
    # The Investigator's mocked Runner calls write_investigation_packet
    # exactly once — with our synthetic packet shape — letting the real
    # tool persist to Firestore.
    packet_args = synthetic_investigation_packet(story_unit_id=story_unit_id)

    def _investigator_plan(*, user_message: str, investigation_id: str, cycle: int):
        # The fixture's id is auto-generated by the tool; we provide
        # the rest of the schema.
        return [
            (
                "wire_emit",
                {"message": "pulling sources, geography, parallel eras", "message_type": "thinking"},
            ),
            (
                "write_investigation_packet",
                {
                    "story_unit_id": packet_args["story_unit_id"],
                    "story_unit_title": packet_args["story_unit_title"],
                    "story_unit_type": packet_args["story_unit_type"],
                    "narrative_spine": packet_args["narrative_spine"],
                    "geography": packet_args["geography"],
                    "historical_context": packet_args["historical_context"],
                    "trend_signals": packet_args["trend_signals"],
                    "sources": packet_args["sources"],
                    "paralympic_depth_score": packet_args["paralympic_depth_score"],
                    "ready_for_storyteller": packet_args["ready_for_storyteller"],
                },
            ),
        ]

    with mock.patch.object(
        chain["investigator"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["investigator"], _investigator_plan),
    ):
        inv_result = await chain["investigator"].investigate(lead_id)

    assert inv_result["action"] == "ok", inv_result
    assert inv_result["story_unit_id"] == story_unit_id
    assert inv_result["investigation_packet_id"], inv_result
    investigation_packet_id = inv_result["investigation_packet_id"]

    packet_docs = list(fs.collections["investigation_packets"]._by_id.values())
    assert len(packet_docs) == 1
    assert packet_docs[0]["story_unit_id"] == story_unit_id

    # --- Stage 2: Storyteller (with real Equity Editor + Publish Gate) --

    # Equity Editor's Runner stub: read the draft, then clear it. LAZY
    # args so draft_id is resolved when the tools actually run, after
    # the storyteller has just written its draft.
    def _equity_plan(*, user_message: str, investigation_id: str, cycle: int):
        return [
            ("read_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
            ("clear_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
        ]

    # Storyteller's Runner stub: write the draft, then request equity
    # review, then request publish gate. All three tools fire for real.
    # The post-write tools use LAZY args (callables) so draft_id is
    # resolved AFTER write_story_draft has actually run.
    storyteller_draft_args = synthetic_story_draft_args(
        investigation_packet_id=investigation_packet_id,
        story_unit_id=story_unit_id,
    )

    def _storyteller_plan(*, user_message: str, investigation_id: str, cycle: int):
        return [
            ("read_investigation_packet", {"packet_id": investigation_packet_id}),
            ("write_story_draft", storyteller_draft_args),
            (
                "request_equity_review",
                lambda: {"draft_id": _latest_draft_id(fs)},
            ),
            (
                "request_publish_gate",
                lambda: {"draft_id": _latest_draft_id(fs)},
            ),
        ]

    with mock.patch.object(
        chain["equity_editor"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["equity_editor"], _equity_plan),
    ), mock.patch.object(
        chain["storyteller"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["storyteller"], _storyteller_plan),
    ):
        story_result = await chain["storyteller"].write_story(investigation_packet_id)

    assert story_result["action"] == "cleared", story_result
    draft_id = story_result["draft_id"]
    assert draft_id, story_result

    # Verify the StoryDraft was persisted with publish_gate_decision='cleared'.
    drafts = list(fs.collections["story_drafts"]._by_id.values())
    assert len(drafts) == 1, f"expected 1 draft, got {len(drafts)}"
    persisted_draft = drafts[0]
    assert persisted_draft["publish_gate_decision"] == "cleared"

    # Verify a PublishAudit was written with final_decision='cleared'.
    audits_coll = fs.collections.get("publish_audits")
    assert audits_coll is not None and len(audits_coll._by_id) == 1, audits_coll
    audit = list(audits_coll._by_id.values())[0]
    assert audit["final_decision"] == "cleared"
    assert set(audit["sub_stages"].keys()) == {
        "fact_check",
        "source_review",
        "parity_review",
        "nil_redaction_review",
        "safety_review",
        "language_review",
        "visual_review",
    }

    # --- Stage 3: Narrator ---------------------------------------------
    # Editor's `dispatch_narrator` reads the draft, refuses unless cleared,
    # and calls narrator.narrate(...). We invoke the same path directly
    # via the bound tool so we exercise that gate.
    narrator_result = await invoke_bound_tool(
        chain["editor"],
        "dispatch_narrator",
        story_draft_id=draft_id,
        voice_profile="broadcast",
    )
    assert narrator_result["dispatched"] is True, narrator_result
    manifest = narrator_result["manifest"]
    # Manifest may be a fallback if anything failed; we want the success
    # shape with at least one audio URL recorded.
    assert manifest is not None
    assert manifest.get("fallback") is False or manifest.get("fallback") is None, (
        f"narrator fell back: {manifest}"
    )
    assert isinstance(manifest.get("audio_urls"), list)
    assert len(manifest["audio_urls"]) >= 1, manifest

    # --- Wire-event assertions -----------------------------------------
    wire_events = list(fs.collections.get("wire_events", FsClient().collection("wire_events"))._by_id.values())
    # Five-or-more boundary events expected over the chain (per HoE spec):
    # Investigator thinking, Investigator milestone (packet drafted),
    # Storyteller validation/thinking events, Equity intervention/milestone,
    # Publish Gate per-substage thinking + clear milestone, Narrator can
    # also emit. The exact count varies; we just want >=5.
    assert len(wire_events) >= 5, (
        f"expected >=5 wire events across the chain, got "
        f"{len(wire_events)}: {[(e.get('agent'), e.get('message_type')) for e in wire_events]}"
    )
    # Every event went through the proxy, so every event has a redaction
    # log attached. This is the strongest assertion — it proves the NIL
    # Layer fired on every emit.
    for ev in wire_events:
        assert "nil_redaction_log" in ev, f"missing nil_redaction_log: {ev}"
    # And no synthetic-fixture name should leak through.
    for ev in wire_events:
        msg = ev.get("message") or ""
        assert "Diego Maradona" not in msg
        assert "Pelé" not in msg


def _latest_draft_id(fs: FsClient) -> str:
    """Return the id of the most-recently-written story_drafts doc.

    Used as a LAZY arg resolver in the runner-stub plans so the tool
    that consumes draft_id (equity / publish_gate / etc.) sees the id
    that `write_story_draft` actually persisted on this cycle. See
    `_chain_stubs.make_adk_runner_stub` lazy-args note.
    """
    drafts_coll = fs.collections.get("story_drafts")
    if drafts_coll is None or not drafts_coll._by_id:
        return "draft-unresolved"
    return list(drafts_coll._by_id.keys())[-1]


@pytest.mark.asyncio
async def test_full_chain_storyteller_revision_loop() -> None:
    """Equity returns the draft once → Storyteller revises → cleared on
    second attempt → Publish Gate cleared. revisions_count=1."""
    fs = FsClient()
    nil_layer = NilRedactionLayer(rows=make_synthetic_registry_rows(600), min_rows=500)
    state = _RuntimeStateBag()
    chain = _build_chain(fs=fs, nil_layer=nil_layer, runtime_state_holder=state)

    # Pre-populate the investigation packet directly (we're testing the
    # Storyteller's revision loop, not the Investigator).
    packet = synthetic_investigation_packet(packet_id="pkt-rev-001")
    fs.collection("investigation_packets").add(packet)
    packet_id = packet["id"]

    # Equity Editor: returns on cycle 1, clears on cycle 2.
    def _equity_plan(*, user_message: str, investigation_id: str, cycle: int):
        if cycle == 1:
            return [
                ("read_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
                (
                    "return_draft",
                    lambda: {
                        "draft_id": _latest_draft_id(fs),
                        "reason": "Paralympic depth thin; revise the historical echo.",
                    },
                ),
            ]
        return [
            ("read_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
            ("clear_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
        ]

    storyteller_args_a = synthetic_story_draft_args(investigation_packet_id=packet_id)
    storyteller_args_b = synthetic_story_draft_args(investigation_packet_id=packet_id)
    storyteller_args_b["headline"] = (
        "A small Iowa county anchors Team USA Paralympic representation"
    )  # 9 words; revised

    def _storyteller_plan(*, user_message: str, investigation_id: str, cycle: int):
        # Cycle 1: write draft, request equity (which RETURNS). Don't
        # request publish gate yet — the storyteller wouldn't, since
        # equity declined. Cycle 2: write a fresh draft, request equity
        # (clears), request publish gate (clears).
        if cycle == 1:
            return [
                ("read_investigation_packet", {"packet_id": packet_id}),
                ("write_story_draft", storyteller_args_a),
                (
                    "request_equity_review",
                    lambda: {"draft_id": _latest_draft_id(fs)},
                ),
            ]
        return [
            ("read_investigation_packet", {"packet_id": packet_id}),
            ("write_story_draft", storyteller_args_b),
            (
                "request_equity_review",
                lambda: {"draft_id": _latest_draft_id(fs)},
            ),
            (
                "request_publish_gate",
                lambda: {"draft_id": _latest_draft_id(fs)},
            ),
        ]

    with mock.patch.object(
        chain["equity_editor"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["equity_editor"], _equity_plan),
    ), mock.patch.object(
        chain["storyteller"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["storyteller"], _storyteller_plan),
    ):
        result = await chain["storyteller"].write_story(packet_id)

    assert result["action"] == "cleared", result
    assert result["revisions_count"] == 1, result
    assert result["final_decision"] == "cleared"

    # Two drafts were written — one returned, one cleared. The cleared
    # one is the second.
    drafts = list(fs.collections["story_drafts"]._by_id.values())
    assert len(drafts) == 2, drafts
    cleared_drafts = [d for d in drafts if d["publish_gate_decision"] == "cleared"]
    assert len(cleared_drafts) == 1, drafts

    # Wire history shows the return-and-revise flow: the equity_editor
    # emitted at least one intervention event over the two cycles.
    wire_events = list(fs.collections["wire_events"]._by_id.values())
    equity_interventions = [
        e
        for e in wire_events
        if e.get("agent") == "equity_editor"
        and e.get("message_type") == "intervention"
    ]
    assert len(equity_interventions) >= 1, (
        f"expected at least 1 equity intervention; got "
        f"{[(e.get('agent'), e.get('message_type'), e.get('message')) for e in wire_events]}"
    )


@pytest.mark.asyncio
async def test_full_chain_kill_on_max_revisions() -> None:
    """Equity returns the draft 4 times (the storyteller's max_revisions
    default is 3, so the 4th attempt kills it). draft.publish_gate_decision
    ends up 'killed' and the wire shows the kill milestone."""
    fs = FsClient()
    nil_layer = NilRedactionLayer(rows=make_synthetic_registry_rows(600), min_rows=500)
    state = _RuntimeStateBag()
    chain = _build_chain(fs=fs, nil_layer=nil_layer, runtime_state_holder=state)

    packet = synthetic_investigation_packet(packet_id="pkt-kill-001")
    fs.collection("investigation_packets").add(packet)
    packet_id = packet["id"]

    def _equity_plan_always_returns(*, user_message: str, investigation_id: str, cycle: int):
        return [
            ("read_draft", lambda: {"draft_id": _latest_draft_id(fs)}),
            (
                "return_draft",
                lambda: {
                    "draft_id": _latest_draft_id(fs),
                    "reason": "Paralympic depth thin; revise.",
                },
            ),
        ]

    def _storyteller_plan(*, user_message: str, investigation_id: str, cycle: int):
        args = synthetic_story_draft_args(investigation_packet_id=packet_id)
        return [
            ("read_investigation_packet", {"packet_id": packet_id}),
            ("write_story_draft", args),
            (
                "request_equity_review",
                lambda: {"draft_id": _latest_draft_id(fs)},
            ),
        ]

    with mock.patch.object(
        chain["equity_editor"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["equity_editor"], _equity_plan_always_returns),
    ), mock.patch.object(
        chain["storyteller"],
        "_run_adk_once",
        side_effect=make_adk_runner_stub(chain["storyteller"], _storyteller_plan),
    ):
        result = await chain["storyteller"].write_story(packet_id)

    assert result["action"] == "killed", result
    assert result["reason"] == "max_revisions_reached", result
    assert result["revisions_count"] == 4, result

    # The latest draft was marked 'killed'.
    drafts = list(fs.collections["story_drafts"]._by_id.values())
    assert len(drafts) >= 1
    # The killed draft is the LAST one written.
    last_draft = drafts[-1]
    assert last_draft["publish_gate_decision"] == "killed", last_draft

    # The Storyteller emitted a milestone Wire event with "kill" in it.
    wire_events = list(fs.collections["wire_events"]._by_id.values())
    kill_milestones = [
        e
        for e in wire_events
        if e.get("agent") == "storyteller"
        and e.get("message_type") == "milestone"
        and "kill" in (e.get("message") or "").lower()
    ]
    assert len(kill_milestones) >= 1, (
        "expected at least 1 storyteller kill milestone; got "
        f"{[(e.get('agent'), e.get('message_type'), e.get('message')) for e in wire_events]}"
    )
