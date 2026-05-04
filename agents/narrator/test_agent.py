"""Unit tests for `NarratorAgent.narrate`.

Mocks the TTS client + Cloud Storage client so tests are fully offline.
The synthetic test drafts are place-only (Mt. Pleasant, Iowa) — no athlete
names, per CONSTITUTION Law 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from agents.narrator.agent import NarratorAgent
from agents.narrator.tts_client import TTSGenerationError


# -- Fakes --------------------------------------------------------------------


class _FakeWire:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict, *, investigation_id: str | None = None) -> str:
        self.emitted.append(dict(event))
        return f"fake-wire-{len(self.emitted)}"


class _FakeBlob:
    def __init__(self) -> None:
        self.data: bytes | None = None
        self.content_type: str | None = None

    def upload_from_string(self, data: bytes, content_type: str = "") -> None:
        self.data = data
        self.content_type = content_type


class _FakeBucket:
    def __init__(self) -> None:
        self.blobs: dict[str, _FakeBlob] = {}

    def blob(self, name: str) -> _FakeBlob:
        b = _FakeBlob()
        self.blobs[name] = b
        return b


class _FakeStorage:
    def __init__(self) -> None:
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        return self.buckets.setdefault(name, _FakeBucket())


class _FakeTTSClient:
    """Records sentences requested + voice name; returns deterministic PCM.

    Each call yields a fixed-size PCM buffer per sentence so duration math
    is predictable (default 24,000 bytes = 500ms at 24kHz mono 16-bit).
    """

    model_id = "gemini-3.1-flash-tts-preview"

    def __init__(
        self,
        *,
        chunk_size_bytes: int = 24000,
        fail_first_n: int = 0,
        always_fail: bool = False,
    ) -> None:
        self._chunk_size = chunk_size_bytes
        self._fail_first_n = fail_first_n
        self._always_fail = always_fail
        self.calls: list[dict] = []

    async def synthesize(
        self,
        text: str,
        *,
        voice_name: str,
        speaking_rate: float | None = None,
        timeout_s: float = 30.0,
    ) -> tuple[bytes, str]:
        self.calls.append(
            {"text": text, "voice_name": voice_name, "speaking_rate": speaking_rate}
        )
        if self._always_fail:
            raise TTSGenerationError("forced failure", status_code=500)
        if self._fail_first_n > 0:
            self._fail_first_n -= 1
            raise TTSGenerationError("transient", status_code=503)
        return (
            b"\x00\x00" * (self._chunk_size // 2),
            "audio/l16; rate=24000; channels=1",
        )


@dataclass
class _FakeRuntimeState:
    last_think_cycle: datetime | None = None


# -- Helpers ------------------------------------------------------------------


def _build_narrator(
    *,
    wire: Any | None = None,
    storage: Any | None = None,
    tts_client: Any | None = None,
    cost_counter: Any | None = None,
    runtime_state: Any | None = None,
) -> NarratorAgent:
    return NarratorAgent(
        wire=wire if wire is not None else _FakeWire(),
        firestore=None,
        storage=storage if storage is not None else _FakeStorage(),
        tts_client=tts_client if tts_client is not None else _FakeTTSClient(),
        cost_counter=cost_counter,
        runtime_state=runtime_state,
    )


def _seed_draft(
    *,
    place: str = "Mt. Pleasant",
    era: str = "1960 Rome sprint era",
) -> dict:
    return {
        "story_id": "story-001",
        "headline": "Eight Olympians and Paralympians from one Iowa town",
        "dek": (
            f"{place} has produced eight Olympians and Paralympians since 1976."
        ),
        "body": (
            f"The town of {place} sits on the eastern edge of Iowa. "
            "Its first Olympian came in 1976. "
            "The newest Paralympian from this region competed in 2024.\n\n"
            "The earliest pipeline trace is to a single high-school coach. "
            "The program never stopped."
        ),
        "hometown_panel_text": (
            f"{place}, Iowa: population 8,000; eight Olympians and "
            "Paralympians since 1976."
        ),
        "historical_echo_text": (
            f"This echoes a {era} pattern of regional pipelines becoming "
            "global stories."
        ),
        "place_name_for_cues": place,
        "era_reference_for_cues": era,
    }


# -- Tests --------------------------------------------------------------------


def test_narrator_constructs_with_default_voices() -> None:
    """Default voice profiles: Algenib (Broadcast) + Fenrir (Wire/fallback)."""
    narrator = _build_narrator()
    assert narrator.name == "narrator"
    assert narrator.broadcast_voice == "Algenib"
    assert narrator.dispatcher_voice == "Fenrir"


@pytest.mark.asyncio
async def test_narrate_skips_on_pause(monkeypatch) -> None:
    """With AGENT_RUNTIME_PAUSED=1, narrate returns an empty fallback manifest."""
    monkeypatch.setenv("AGENT_RUNTIME_PAUSED", "1")
    tts = _FakeTTSClient()
    narrator = _build_narrator(tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    assert manifest["fallback"] is True
    assert manifest["fallback_reason"] == "paused"
    assert manifest["audio_urls"] == []
    assert tts.calls == []  # Synthesizer never invoked


@pytest.mark.asyncio
async def test_narrate_handles_cost_ceiling() -> None:
    """When CostCeilingExceeded is raised, narrate emits a thinking event
    and returns an empty manifest."""
    from agents.cost.counters import CostCeilingExceeded

    wire = _FakeWire()
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(
        side_effect=CostCeilingExceeded("axis=tts total=200001 >= limit=200000")
    )
    cost_counter.snapshot_today = mock.Mock(return_value={"tts": 200001})

    tts = _FakeTTSClient()
    narrator = _build_narrator(wire=wire, cost_counter=cost_counter, tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    assert manifest["fallback"] is True
    assert manifest["fallback_reason"] == "cost_ceiling"
    assert manifest["audio_urls"] == []
    cap_events = [e for e in wire.emitted if "tts cap reached" in e["message"]]
    assert len(cap_events) == 1
    assert cap_events[0]["agent"] == "narrator"
    assert cap_events[0]["message_type"] == "thinking"
    # No TTS calls were made.
    assert tts.calls == []


@pytest.mark.asyncio
async def test_narrate_synthesizes_each_sentence_chunk() -> None:
    """Each sentence becomes one TTS call; one GCS object per chunk; the
    manifest lists all the gs:// URLs in order."""
    wire = _FakeWire()
    storage = _FakeStorage()
    tts = _FakeTTSClient()
    narrator = _build_narrator(wire=wire, storage=storage, tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    # Every TTS call goes to the Broadcast voice by default.
    assert all(c["voice_name"] == "Algenib" for c in tts.calls)
    # We synthesize at least one chunk per non-empty section.
    assert len(tts.calls) >= 5  # 1 dek + 3 body + 1 panel + 1 echo, give or take splitter
    # Audio URLs match chunk count.
    assert len(manifest["audio_urls"]) == len(tts.calls)
    assert all(
        u.startswith("gs://storytellers-room-audio/story-001/")
        for u in manifest["audio_urls"]
    )
    # Storage uploads landed.
    bucket = storage.buckets["storytellers-room-audio"]
    assert len(bucket.blobs) == len(tts.calls)
    # Each uploaded blob is a WAV (starts with RIFF).
    for blob in bucket.blobs.values():
        assert blob.data is not None
        assert blob.data[:4] == b"RIFF"
        assert blob.content_type == "audio/wav"
    # Milestone Wire event landed.
    milestones = [e for e in wire.emitted if e["message_type"] == "milestone"]
    assert len(milestones) == 1
    assert "narration ready" in milestones[0]["message"]


@pytest.mark.asyncio
async def test_narrate_estimates_word_timings_from_sentence_duration() -> None:
    """Each sentence's words are linearly interpolated across the chunk's
    audio duration. Verify a basic property: words within a sentence have
    monotonically increasing start_ms, and the sentence's last word ends at
    sentence end_ms."""
    tts = _FakeTTSClient(chunk_size_bytes=24000)  # 500ms per chunk @ 24kHz mono 16-bit
    narrator = _build_narrator(tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    # All words have start_ms <= end_ms.
    for w in manifest["words"]:
        assert w["start_ms"] <= w["end_ms"]

    # Within each sentence, word starts are monotonically non-decreasing.
    sentences = manifest["sentences"]
    for s_idx, s in enumerate(sentences):
        words = [w for w in manifest["words"] if w["sentence_idx"] == s_idx]
        if len(words) < 2:
            continue
        for prev, curr in zip(words, words[1:]):
            assert prev["start_ms"] <= curr["start_ms"]
        # Last word's end_ms equals the sentence's end_ms (per the
        # interpolation rule in agent._assemble_manifest).
        assert words[-1]["end_ms"] == s["end_ms"]

    # Total audio duration = sum of per-chunk durations.
    expected_duration = 500 * len(sentences)
    assert manifest["audio_duration_ms"] == expected_duration


@pytest.mark.asyncio
async def test_narrate_emits_cue_for_place_name_first_occurrence() -> None:
    """The hometown panel cue lands at the start_ms of the first sentence
    containing the place name."""
    narrator = _build_narrator()

    manifest = await narrator.narrate(_seed_draft(place="Mt. Pleasant"))

    hometown_cues = [c for c in manifest["cues"] if c["panel"] == "hometown"]
    assert len(hometown_cues) == 1
    cue = hometown_cues[0]
    assert cue["kind"] == "panel"
    # Locate the matching sentence and confirm at_ms == its start_ms.
    matching = [
        s
        for s in manifest["sentences"]
        if "Mt. Pleasant".lower() in s["text"].lower()
    ]
    assert matching, "Synthetic draft must contain the place name in at least one sentence."
    # The cue should fire at the FIRST matching sentence's start_ms.
    assert cue["at_ms"] == matching[0]["start_ms"]


@pytest.mark.asyncio
async def test_narrate_uses_dispatcher_voice_when_requested() -> None:
    """voice_profile='dispatcher' selects Fenrir."""
    tts = _FakeTTSClient()
    narrator = _build_narrator(tts_client=tts)

    await narrator.narrate(_seed_draft(), voice_profile="dispatcher")

    assert all(c["voice_name"] == "Fenrir" for c in tts.calls)


@pytest.mark.asyncio
async def test_narrate_falls_back_to_prerendered_on_total_tts_failure() -> None:
    """When every TTS attempt (including the strip-tags retry) fails, the
    Narrator emits a Wire thinking event and returns the fallback manifest
    (BUILD_SPEC §17.5)."""
    wire = _FakeWire()
    tts = _FakeTTSClient(always_fail=True)
    narrator = _build_narrator(wire=wire, tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    assert manifest["fallback"] is True
    assert manifest["fallback_reason"] == "tts_failed"
    assert manifest["audio_urls"] == [
        "gs://storytellers-room-fallback-heroes/narration_fallback.wav"
    ]
    failure_events = [
        e for e in wire.emitted if "voice rendering stalled" in e["message"]
    ]
    assert len(failure_events) == 1


@pytest.mark.asyncio
async def test_narrate_recovers_via_retry_when_first_attempt_fails() -> None:
    """One transient failure → retry succeeds → manifest has audio."""
    tts = _FakeTTSClient(fail_first_n=1)
    narrator = _build_narrator(tts_client=tts)

    manifest = await narrator.narrate(_seed_draft())

    # The retry path strips inline tags. Both attempts count as calls.
    assert len(tts.calls) >= 2
    # At least one non-fallback chunk landed.
    assert manifest["fallback"] is False
    assert len(manifest["audio_urls"]) >= 1


@pytest.mark.asyncio
async def test_narrate_increments_cost_counter_with_audio_chars() -> None:
    """On success the cost counter is incremented with axis='tts' and
    audio_chars=sum_of_chars."""
    cost_counter = mock.Mock()
    cost_counter.assert_under_ceiling = mock.AsyncMock(return_value=None)
    cost_counter.increment = mock.AsyncMock(return_value=None)
    cost_counter.snapshot_today = mock.Mock(return_value={})

    narrator = _build_narrator(cost_counter=cost_counter)

    await narrator.narrate(_seed_draft())

    cost_counter.assert_under_ceiling.assert_awaited_once()
    cost_counter.increment.assert_awaited_once()
    kwargs = cost_counter.increment.await_args.kwargs
    assert kwargs["axis"] == "tts"
    assert kwargs["agent"] == "narrator"
    assert kwargs["audio_chars"] > 0
    assert kwargs["calls"] >= 1


@pytest.mark.asyncio
async def test_narrate_stamps_last_think_cycle_on_success() -> None:
    """RuntimeState.last_think_cycle is updated after a successful narration."""
    state = _FakeRuntimeState()
    narrator = _build_narrator(runtime_state=state)

    await narrator.narrate(_seed_draft())

    assert state.last_think_cycle is not None
    # Updated within the last 60 seconds.
    delta = datetime.now(timezone.utc) - state.last_think_cycle
    assert delta.total_seconds() < 60
