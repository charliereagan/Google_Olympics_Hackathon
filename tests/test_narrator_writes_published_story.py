"""Test the Narrator's `published_stories` write — the last surgical wire
that closes the end-to-end chain (Day-6 last-mile, Worker E + VPS-DEC-054).

Given a fake cleared draft + fake publish_audit + fake TTS + fake
Cloud Storage, `narrate(draft, voice_profile, audit_id)` writes a
`published_stories/{auto_id}` doc with the EXACT `BroadcastStory` shape
the `/story/[id]` route's Firestore fallback validator expects.
"""

from __future__ import annotations

import pytest

from agents.narrator.agent import (
    NarratorAgent,
    _build_nil_signature,
    _format_kicker,
    _split_paragraphs,
)
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
        "place_name": "Mount Pleasant, IA",
        "place_name_for_cues": "the county seat",
        "era_reference_for_cues": "1960s post-war regional pipelines",
        "verified_claims": [
            {
                "slug": "olympians_count_since_1972",
                "text": "Eight Olympians have come from the county since 1972.",
                "source": "olympedia.org",
            },
        ],
        "pull_quote": "The pattern stopped looking like luck a long time ago.",
        "pull_quote_after_paragraph": 1,
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
    that matches `BroadcastStory` verbatim — the contract the `/story/[id]`
    route's Firestore fallback renders against (VPS-DEC-054)."""
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

    # --- Top-level BroadcastStory fields -------------------------------------
    # `id` is intentionally absent — the route synthesizes from snap.id.
    # `kicker_place` MUST be the prefixed PUBLISHED · CITY · STATE form.
    assert doc["kicker_place"] == "PUBLISHED · MOUNT PLEASANT · IOWA"
    assert doc["headline"].startswith("A small Iowa county")
    assert "decades ago" in doc["dek"]
    assert isinstance(doc["body_paragraphs"], list)
    assert len(doc["body_paragraphs"]) == 2  # two paragraphs in the seed body
    assert doc["mode"] == "published"
    assert doc["audit_id"] == "aud-001"
    assert doc["story_id"] == "draft-001"
    assert doc["story_unit_id"] == "place_test_iowa"
    assert doc["published_at"]
    assert doc["hero_image_url"] is None  # not set by the seed draft
    assert doc["pull_quote"] == "The pattern stopped looking like luck a long time ago."
    assert doc["pull_quote_after_paragraph"] == 1

    # --- Fact-check counts ---------------------------------------------------
    assert doc["claims_checked"] == 29
    assert doc["claims_passed"] == 29  # 29 checked, 0 removed
    assert doc["claims_removed"] == 0
    # claims is the list-of-StoryClaim shape the audit drawer renders against.
    assert doc["claims"] == [
        {
            "slug": "olympians_count_since_1972",
            "text": "Eight Olympians have come from the county since 1972.",
            "source": "olympedia.org",
        },
    ]

    # --- Narration block (BroadcastStory.narration) --------------------------
    narration = doc["narration"]
    assert narration["voice_name"] in {"Algenib", "broadcast"}
    assert narration["audio_url"].startswith("gs://storytellers-room-audio/")
    assert isinstance(narration["duration_s"], int)
    assert narration["duration_s"] >= 0

    # --- nil_log block (BroadcastStory.nil_log) ------------------------------
    nil = doc["nil_log"]
    assert nil["direct_matches_redacted"] == 0
    assert nil["aggregations_applied"] == 0

    # --- publish_gate_audit block --------------------------------------------
    audit = doc["publish_gate_audit"]
    assert audit["total_claims_checked"] == 29
    assert audit["nil_layer_passed"] is True
    assert audit["publish_gate_cleared"] is True


@pytest.mark.asyncio
async def test_published_story_has_source_organic_field():
    """Per VPS-DEC-054 every Narrator-persisted doc carries
    `source: 'organic'` so the data layer can distinguish in-repo
    fixtures from organic Firestore docs (UI shows no distinction)."""
    fs = FsClient()
    _seed_cleared_audit(fs, audit_id="aud-002", story_id="draft-002")
    narrator = _build_narrator(fs)
    await narrator.narrate(
        {**_seed_draft(), "story_id": "draft-002"},
        voice_profile="broadcast",
        audit_id="aud-002",
    )
    doc = fs.collection("published_stories").added[0]
    assert doc["source"] == "organic"


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
        "language_violations_returned": 0,
    }


def test_kicker_format_handles_state_abbreviations():
    """`_format_kicker` expands USPS abbreviations to the full state name
    so the Broadcast kicker reads as `PUBLISHED · CITY · STATE` regardless
    of how the Storyteller wrote the place_name."""
    # Full state names — pass-through (uppercased).
    assert _format_kicker("Tucson, Arizona") == "PUBLISHED · TUCSON · ARIZONA"
    assert _format_kicker("Park City, Utah") == "PUBLISHED · PARK CITY · UTAH"
    assert (
        _format_kicker("Birmingham, Alabama")
        == "PUBLISHED · BIRMINGHAM · ALABAMA"
    )
    # Two-letter abbreviations — expanded.
    assert (
        _format_kicker("Mount Pleasant, IA")
        == "PUBLISHED · MOUNT PLEASANT · IOWA"
    )
    assert (
        _format_kicker("Colorado Springs, CO")
        == "PUBLISHED · COLORADO SPRINGS · COLORADO"
    )
    # Unknown abbreviation — falls through unchanged but capitalized.
    assert _format_kicker("Townsville, ZZ") == "PUBLISHED · TOWNSVILLE · ZZ"
    # No comma → city only.
    assert _format_kicker("Birmingham") == "PUBLISHED · BIRMINGHAM"
    # Empty → bare PUBLISHED prefix (defensive).
    assert _format_kicker("") == "PUBLISHED"


@pytest.mark.asyncio
async def test_narrate_falls_back_to_draft_story_unit_id_when_audit_lacks_one():
    """When the audit doc doesn't carry `story_unit_id` (older audits),
    the Narrator falls back to reading it from the draft directly."""
    fs = FsClient()
    # Audit doc seeded WITHOUT a story_unit_id field.
    fs.collection("publish_audits")._add_internal(
        {
            "audit_id": "aud-no-unit",
            "story_id": "draft-001",
            "investigation_packet_id": "pkt-test-001",
            "final_decision": "cleared",
            "sub_stages": {
                "fact_check": {
                    "passed": True,
                    "claims_checked": 14,
                    "claims_softened": 0,
                    "removed_claims": [],
                },
                "nil_redaction_review": {"passed": True, "redacted": 0, "aggregated": 0},
            },
            "completed_at": "2026-05-05T01:00:00+00:00",
            "revisions_requested": [],
        }
    )
    narrator = _build_narrator(fs)
    await narrator.narrate(
        _seed_draft(), voice_profile="broadcast", audit_id="aud-no-unit"
    )
    doc = fs.collection("published_stories").added[0]
    # Fell back to the draft's story_unit_id (the audit had none).
    assert doc["story_unit_id"] == "place_test_iowa"
