"""End-to-end test for the Editor's cleared-audit dispatch chain.

Covers Worker E's Day-6 last-mile wire (HOE-DEC-025): the Editor's
autonomous think_once loop scans `publish_audits` for cleared, not-yet-
narrated audits, surfaces them in the context snapshot, the Pro model
calls `dispatch_narrator(draft_id, voice_profile, audit_id)`, the
Narrator runs, and the audit gets stamped `narration_dispatched=True`
so the next cycle does not re-dispatch.

The ADK Runner is stubbed via `tests/integration/_chain_stubs` patterns
(`make_adk_runner_stub` + `PlanCycle`) so the real bound dispatch_narrator
tool fires against the real fake Firestore + a mocked Narrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.editor.agent import EditorAgent, _resolve_voice_alias
from agents.wire.types import InvestigationContext
from tests.integration._chain_stubs import (
    FsClient,
    PlanCycle,
    make_adk_runner_stub,
)


# -- Local fakes --------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(
        self, event: dict, *, investigation_id: str | None = None
    ) -> str:
        self.emitted.append(dict(event))
        return f"fake-wire-{len(self.emitted)}"


def _seed_cleared_audit(
    fs: FsClient,
    *,
    audit_id: str,
    story_id: str,
    story_unit_id: str = "place_test_iowa",
) -> None:
    fs.collection("publish_audits")._add_internal(
        {
            "audit_id": audit_id,
            "story_id": story_id,
            "story_unit_id": story_unit_id,
            "investigation_packet_id": "pkt-test-001",
            "final_decision": "cleared",
            "sub_stages": {
                "fact_check": {
                    "passed": True,
                    "claims_checked": 29,
                    "claims_softened": 1,
                    "removed_claims": [],
                },
                "nil_redaction_review": {
                    "passed": True,
                    "redacted": 0,
                    "aggregated": 0,
                },
            },
            "completed_at": "2026-05-05T01:00:00+00:00",
            "revisions_requested": [],
            "narration_dispatched": False,
        }
    )


def _seed_cleared_draft(
    fs: FsClient,
    *,
    story_id: str,
    story_unit_id: str = "place_test_iowa",
) -> None:
    fs.collection("story_drafts")._add_internal(
        {
            "id": story_id,
            "story_unit_id": story_unit_id,
            "headline": "A small Iowa county keeps producing Team USA representation",
            "dek": "The pattern took shape from a single high-school program three decades ago",
            "body": (
                "The county sits on the eastern edge of Iowa, "
                "a place of rolling fields. " * 30
            ),
            "hometown_panel": "The county seat sits at 8,500 residents.",
            "historical_echo": "This echoes a 1960s post-war pipeline pattern.",
            "place_name": "the county seat, Iowa",
            "era_reference": "1960s post-war regional pipelines",
            "publish_gate_decision": "cleared",
        }
    )


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_editor_context_snapshot_surfaces_cleared_audits():
    """The Editor's `_build_context_snapshot` includes
    `cleared_audits_awaiting_narration` with the cleared+un-narrated audit."""
    fs = FsClient()
    _seed_cleared_audit(fs, audit_id="aud-001", story_id="draft-001")

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=fs,
        model_id="gemini-3.1-pro-preview",
    )
    snapshot = await editor._build_context_snapshot()
    awaiting = snapshot["cleared_audits_awaiting_narration"]

    assert isinstance(awaiting, list)
    assert len(awaiting) == 1
    entry = awaiting[0]
    assert entry["audit_id"] == "aud-001"
    assert entry["story_id"] == "draft-001"
    assert entry["story_unit_id"] == "place_test_iowa"
    assert entry["completed_at"] == "2026-05-05T01:00:00+00:00"


@pytest.mark.asyncio
async def test_editor_context_snapshot_filters_already_narrated_audits():
    """A cleared audit with `narration_dispatched=True` does NOT appear in
    the context snapshot — the next think cycle leaves it alone."""
    fs = FsClient()
    fs.collection("publish_audits")._add_internal(
        {
            "audit_id": "aud-already",
            "story_id": "draft-already",
            "story_unit_id": "place_test_other",
            "final_decision": "cleared",
            "narration_dispatched": True,
            "narration_dispatched_at": "2026-05-05T00:30:00+00:00",
            "completed_at": "2026-05-05T00:00:00+00:00",
        }
    )
    _seed_cleared_audit(fs, audit_id="aud-fresh", story_id="draft-fresh")

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=fs,
        model_id="gemini-3.1-pro-preview",
    )
    snapshot = await editor._build_context_snapshot()
    audit_ids = [
        a["audit_id"] for a in snapshot["cleared_audits_awaiting_narration"]
    ]
    assert "aud-already" not in audit_ids
    assert "aud-fresh" in audit_ids


@pytest.mark.asyncio
async def test_editor_dispatch_narrator_marks_audit_narration_dispatched():
    """When the Pro model calls `dispatch_narrator(audit_id=...)`, the
    Editor's bound tool routes through the Narrator AND stamps
    `narration_dispatched=True` on the audit doc.

    Drives the bound tool through the same `make_adk_runner_stub` that
    the integration suite uses — so this exercises the real wiring,
    not a mocked tool response.
    """
    fs = FsClient()
    _seed_cleared_audit(fs, audit_id="aud-001", story_id="draft-001")
    _seed_cleared_draft(fs, story_id="draft-001")

    narrator = mock.Mock()
    narrator.narrate = mock.AsyncMock(
        return_value={
            "story_id": "draft-001",
            "audio_urls": ["gs://bucket/draft-001/0.wav"],
            "audio_duration_ms": 12000,
            "voice_name": "Algenib",
            "fallback": False,
        }
    )

    editor = EditorAgent(
        prompt="You are the Editor.",
        wire=_FakeWire(),
        scout_desk=mock.Mock(),
        firestore=fs,
        model_id="gemini-3.1-pro-preview",
        narrator=narrator,
    )

    # The model's plan: call dispatch_narrator with the cleared audit's
    # (story_id, audit_id) triple. Mirrors what the prompt now instructs.
    plan = lambda **_: PlanCycle(  # noqa: E731
        tools=[
            (
                "dispatch_narrator",
                {
                    "story_draft_id": "draft-001",
                    "voice_profile": "algenib",
                    "audit_id": "aud-001",
                },
            ),
        ]
    )

    with mock.patch.object(
        editor, "_run_adk_once", side_effect=make_adk_runner_stub(editor, plan)
    ):
        result = await editor.think_once(
            ctx=InvestigationContext(
                investigation_id="inv-test", compression_factor=1.0
            )
        )

    assert result["action"] == "ok"
    # The model's tool call landed with the right triple.
    tool_calls = result["tool_calls"]
    assert len(tool_calls) == 1
    call = tool_calls[0]
    assert call["name"] == "dispatch_narrator"
    assert call["args"]["story_draft_id"] == "draft-001"
    assert call["args"]["voice_profile"] == "algenib"
    assert call["args"]["audit_id"] == "aud-001"

    # The Narrator was actually awaited by the bound tool.
    narrator.narrate.assert_awaited_once()
    awaited = narrator.narrate.await_args
    # 'algenib' alias resolved to 'broadcast' at the dispatch boundary.
    assert awaited.kwargs.get("voice_profile") == "broadcast"
    assert awaited.kwargs.get("audit_id") == "aud-001"

    # The audit is now flagged narration_dispatched=True so the NEXT
    # cycle's snapshot will not re-surface it.
    audit_doc = fs.collection("publish_audits")._by_id
    audit_data = next(iter(audit_doc.values()))
    assert audit_data["narration_dispatched"] is True
    assert audit_data.get("narration_dispatched_at")


def test_resolve_voice_alias_maps_algenib_to_broadcast():
    """The Editor's prompt-level vocabulary ('algenib' / 'fenrir') is
    translated to the Narrator's API ('broadcast' / 'dispatcher') at the
    dispatch boundary."""
    assert _resolve_voice_alias("algenib") == "broadcast"
    assert _resolve_voice_alias("Algenib") == "broadcast"
    assert _resolve_voice_alias("broadcast") == "broadcast"
    assert _resolve_voice_alias("fenrir") == "dispatcher"
    assert _resolve_voice_alias("dispatcher") == "dispatcher"
    assert _resolve_voice_alias("wire") == "dispatcher"
    # Unknown values default to broadcast (the safe published-story voice).
    assert _resolve_voice_alias("garbage") == "broadcast"
    assert _resolve_voice_alias(None) == "broadcast"
