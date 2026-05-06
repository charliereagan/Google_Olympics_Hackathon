"""Test the Narrator's `published_stories` write — the last surgical wire
that closes the end-to-end chain (Day-6 last-mile, Worker E).

Given a fake cleared draft + fake publish_audit + fake TTS + fake
Cloud Storage, `narrate(draft, voice_profile, audit_id)` writes a
`published_stories/{auto_id}` doc carrying the cleared draft text +
audio URL + audit-derived NIL signature.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from agents.narrator.agent import NarratorAgent, _build_nil_signature, _split_paragraphs
from tests.integration._chain_stubs import FsClient, StubStorage, StubTtsClient


# -- Local helpers ------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(
        self, event: dict, *, investigation_id: str | None = None
    ) -> str:
        self.emitted.append(dict(event))
        return f"fake-wire-{len(self.emitted)}"


def _seed_cleared_audit(fs: FsClient, *, audit_id: str, story_id: str) -> None:
    fs.collection("publish_audits")._add_internal(
        {
            "audit_id": audit_id,
            "story_id": story_id,
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


def _seed_draft() -> dict:
    return {
        "story_id": "draft-001",
        "story_unit_id": "place_test_iowa",
        "headline": "A small Iowa county keeps producing Team USA representation",
        "dek": "The pattern took shape from a single high-school program three decades ago",
        "body": (
            "The county sits on the eastern edge of Iowa, a place "
            "of rolling fields and a single large high school.\n\n"
            "The first Team USA athlete from this region competed in 1976; "
            "the newest competed in 2024."
        ),
        "hometown_panel_text": (
            "The county seat sits at 8,500 residents on the eastern edge of Iowa."
        ),
        "historical_echo_text": (
            "This echoes a 1960s post-war pattern of regional pipelines."
        ),
        "place_name_for_cues": "the county seat",
        "era_reference_for_cues": "1960s post-war regional pipelines",
    }


def _build_narrator(fs: FsClient, *, storage=None, tts_client=None) -> NarratorAgent:
    return NarratorAgent(
        wire=_FakeWire(),
        firestore=fs,
        storage=storage if storage is not None else StubStorage(),
        tts_client=tts_client if tts_client is not None else StubTtsClient(),
    )


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_narrate_writes_published_story_with_full_shape():
    """A successful narrate() with audit_id writes a published_stories doc
    carrying the cleared draft text, audio URL, NIL signature, and audit
    backref — the contract the Broadcast page renders against."""
    fs = FsClient()
    _seed_cleared_audit(fs, audit_id="aud-001", story_id="draft-001")

    narrator = _build_narrator(fs)
    manifest = await narrator.narrate(
        _seed_draft(),
        voice_profile="broadcast",
        audit_id="aud-001",
    )

    # The manifest itself rendered (sanity).
    assert manifest["fallback"] is False
    assert len(manifest["audio_urls"]) >= 1

    # Exactly one published_stories doc landed.
    published = fs.collection("published_stories").added
    assert len(published) == 1
    doc = published[0]

    # Top-level shape.
    assert doc["story_id"] == "draft-001"
    assert doc["story_unit_id"] == "place_test_iowa"
    assert doc["kicker_place"] == "the county seat"
    assert doc["headline"].startswith("A small Iowa county")
    assert "decades ago" in doc["dek"]
    assert isinstance(doc["body_paragraphs"], list)
    assert len(doc["body_paragraphs"]) == 2  # two paragraphs in the seed body
    assert doc["mode"] == "published"
    assert doc["audit_id"] == "aud-001"
    assert doc["published_at"]
    assert doc["hero_image_url"] is None  # not set by the seed draft

    # Narration block.
    narration = doc["narration"]
    assert narration["voice_name"] in {"Algenib", "broadcast"}
    assert narration["audio_url"].startswith("gs://storytellers-room-audio/")
    assert isinstance(narration["audio_urls"], list)
    assert narration["duration_s"] >= 0
    assert narration["manifest_id"]

    # NIL signature pulled from the cleared publish_audit.
    nil = doc["nil_signature"]
    assert nil["claims_checked"] == 29
    assert nil["claims_softened"] == 1
    assert nil["claims_removed"] == 0
    assert nil["redactions"] == 0
    assert nil["aggregations"] == 0


@pytest.mark.asyncio
async def test_narrate_skips_published_story_write_when_no_firestore():
    """Without a Firestore client the Narrator still produces a manifest
    but does NOT crash on the published_stories write attempt."""
    narrator = NarratorAgent(
        wire=_FakeWire(),
        firestore=None,
        storage=StubStorage(),
        tts_client=StubTtsClient(),
    )
    manifest = await narrator.narrate(
        _seed_draft(), voice_profile="broadcast", audit_id="aud-001"
    )
    assert manifest["fallback"] is False  # rendering still works
    # No exception raised — the persist step short-circuits silently.


@pytest.mark.asyncio
async def test_narrate_skips_published_story_write_on_fallback_manifest():
    """When TTS fails entirely (fallback manifest), the published_stories
    write is skipped — the Broadcast page should not surface a story
    with no real audio."""
    from agents.narrator.tts_client import TTSGenerationError

    class _AlwaysFailTts:
        model_id = "gemini-3.1-flash-tts-preview"

        async def synthesize(self, text, *, voice_name, **kwargs):
            raise TTSGenerationError("forced", status_code=500)

    fs = FsClient()
    _seed_cleared_audit(fs, audit_id="aud-001", story_id="draft-001")

    narrator = _build_narrator(fs, tts_client=_AlwaysFailTts())
    manifest = await narrator.narrate(
        _seed_draft(), voice_profile="broadcast", audit_id="aud-001"
    )
    assert manifest["fallback"] is True
    assert manifest["fallback_reason"] == "tts_failed"
    # No published_stories doc was written.
    assert fs.collection("published_stories").added == []


def test_split_paragraphs_drops_blanks():
    assert _split_paragraphs("") == []
    assert _split_paragraphs("a\n\nb") == ["a", "b"]
    assert _split_paragraphs("a\n\n\n\nb\n\n  \n\nc") == ["a", "b", "c"]


def test_build_nil_signature_handles_missing_audit():
    """When audit is None (no audit_id passed), the signature is
    zero-valued — published_stories still has a structurally-valid
    nil_signature block."""
    sig = _build_nil_signature(None)
    assert sig == {
        "claims_checked": 0,
        "claims_softened": 0,
        "claims_removed": 0,
        "redactions": 0,
        "aggregations": 0,
    }
