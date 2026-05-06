"""NarratorAgent: deterministic TTS synthesis of Storyteller drafts.

Unlike Editor/Investigator, the Narrator does NOT use an ADK Runner — TTS is
a direct Vertex AI call, not an LLM-reasoning step. The class name keeps the
seven-cast symmetry (`/health/agents` shows `narrator: idle`) but
`narrate(draft, voice_profile)` orchestrates TTS chunk-by-chunk synthesis,
WAV-wrapping, GCS upload, timeline assembly, cue detection, and manifest
emission.

Voice signature lives in `/prompts/narrator.md` for documentation symmetry
with the other six agents (CONSTITUTION Rule 1). Python here contains zero
voice text; all voice character is in the TTS voice config (Algenib /
Fenrir).

BUILD_SPEC refs:
  - §3.5 Gemini 3.1 Flash TTS shape + inline tags
  - §5.6 Narrator role + voice configs + word-level timing
  - §7.6 Audio sync architecture (NarrationManifest shape + cue points)
  - §17.5 TTS failure → fall back to pre-rendered MP3
  - §15.3 Cost ceilings (axis='tts' = 200K chars/day)

HOE-DEC refs:
  - HOE-DEC-025: Algenib (Broadcast) / Fenrir (Wire + fallback)
  - HOE-DEC-019: fail-closed boot semantics (the Narrator inherits Wire's)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from agents.cost.counters import CostCeilingExceeded
from agents.narrator.audio import (
    estimate_audio_duration_ms,
    split_into_sentences,
    wrap_pcm_as_wav,
)
from agents.narrator.tts_client import (
    GeminiFlashTTSClient,
    TTSGenerationError,
    parse_l16_rate,
)
from agents.narrator.types import (
    NarrationManifest,
    SentenceBoundary,
    StoryDraftForNarration,
    VisualCue,
    WordTiming,
)
from agents.observability import log_agent_call, trace_span
from agents.wire.emit import WireProxyNotReadyError

logger = logging.getLogger(__name__)


# Cost axis from BUILD_SPEC §15.3: 200K chars/day.
_COST_AXIS = "tts"

# Gemini 3.1 Flash TTS output is documented as 24kHz L16 mono PCM.
_DEFAULT_SAMPLE_RATE_HZ = 24000
_DEFAULT_CHANNELS = 1
_DEFAULT_SAMPLE_WIDTH = 2

# Voice profile → bare prebuilt voice name (HOE-DEC-025).
VoiceProfile = Literal["broadcast", "dispatcher"]


class NarratorAgent:
    """Deterministic TTS synthesis with timeline assembly.

    Construction takes everything the runtime injects; tests pass stubs.
    """

    def __init__(
        self,
        *,
        wire: Any,
        firestore: Any,
        storage: Any,
        tts_client: GeminiFlashTTSClient,
        cost_counter: Any | None = None,
        broadcast_voice: str = "Algenib",
        dispatcher_voice: str = "Fenrir",
        runtime_state: Any | None = None,
        bucket_name: str = "storytellers-room-audio",
        fallback_audio_url: str = (
            "gs://storytellers-room-fallback-heroes/narration_fallback.wav"
        ),
        sample_rate_hz: int = _DEFAULT_SAMPLE_RATE_HZ,
        clock: Any | None = None,
    ) -> None:
        self._wire = wire
        self._firestore = firestore
        self._storage = storage
        self._tts = tts_client
        self._cost_counter = cost_counter
        self._broadcast_voice = broadcast_voice
        self._dispatcher_voice = dispatcher_voice
        self._runtime_state = runtime_state
        self._bucket_name = bucket_name
        self._fallback_audio_url = fallback_audio_url
        self._sample_rate_hz = sample_rate_hz
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- Public surface ------------------------------------------------------

    @property
    def name(self) -> str:
        return "narrator"

    @property
    def broadcast_voice(self) -> str:
        return self._broadcast_voice

    @property
    def dispatcher_voice(self) -> str:
        return self._dispatcher_voice

    # -- Voice profile resolution -------------------------------------------

    def _resolve_voice(self, voice_profile: VoiceProfile) -> str:
        if voice_profile == "broadcast":
            return self._broadcast_voice
        if voice_profile == "dispatcher":
            return self._dispatcher_voice
        # Unknown profile → fall back to Fenrir (HOE-DEC-025 single-voice
        # fallback).
        logger.warning(
            "narrator: unknown voice_profile=%r; defaulting to dispatcher voice",
            voice_profile,
        )
        return self._dispatcher_voice

    # -- One narration cycle -------------------------------------------------

    async def narrate(
        self,
        draft: StoryDraftForNarration,
        *,
        voice_profile: VoiceProfile = "broadcast",
        ctx: Any | None = None,
        audit_id: str | None = None,
    ) -> NarrationManifest:
        """Convert a Storyteller draft to a NarrationManifest.

        See module docstring for the full flow. On failure (cost ceiling, TTS
        failure after retries, storage write failure) the method emits a Wire
        thinking event and returns a structured manifest reflecting the
        failure.

        When `audit_id` is provided AND the manifest renders successfully
        (non-fallback, audio_urls populated), the Narrator also writes
        a `published_stories/{auto_id}` doc carrying the cleared draft
        text + audio URL + audit-derived NIL signature so the Broadcast
        page has a single read-target for the published story.
        """
        if os.environ.get("AGENT_RUNTIME_PAUSED") == "1":
            logger.debug("narrator.narrate: paused (AGENT_RUNTIME_PAUSED=1)")
            return self._empty_manifest(
                draft=draft,
                voice_name=self._resolve_voice(voice_profile),
                fallback_reason="paused",
            )

        story_id = draft.get("story_id") or f"story-{uuid.uuid4().hex[:8]}"
        voice_name = self._resolve_voice(voice_profile)
        investigation_id = (
            getattr(ctx, "investigation_id", None) if ctx is not None else None
        ) or f"narrator-{story_id}"
        compression_factor = (
            float(getattr(ctx, "compression_factor", 1.0)) if ctx is not None else 1.0
        )

        # --- Cost ceiling pre-check (BUILD_SPEC §15.3) ----------------------
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=_COST_AXIS, agent="narrator"
                )
            except CostCeilingExceeded:
                await self._safe_emit_thinking(
                    "*tts cap reached, narrator pausing*",
                    investigation_id=investigation_id,
                    story_unit_id=None,
                )
                return self._empty_manifest(
                    draft=draft,
                    voice_name=voice_name,
                    fallback_reason="cost_ceiling",
                )

        # --- Build narration text ------------------------------------------
        sentences_text = self._build_narration_sentences(draft)
        if not sentences_text:
            logger.warning("narrator.narrate: empty draft for story_id=%s", story_id)
            return self._empty_manifest(
                draft=draft,
                voice_name=voice_name,
                fallback_reason="empty_draft",
            )

        # Inject inline tags ([short pause] / [long pause] / [emphasis]).
        # Best-effort and deterministic — we don't try to be clever.
        place_name = (draft.get("place_name_for_cues") or "").strip()
        sentences_for_tts = self._apply_inline_tags(
            sentences_text, place_name=place_name
        )

        # --- Synthesize each sentence (with one retry per chunk) -----------
        with trace_span(
            "narrator.narrate",
            investigation_id=investigation_id,
            attrs={
                "story_id": story_id,
                "voice": voice_name,
                "sentence_count": len(sentences_for_tts),
                "compression_factor": compression_factor,
            },
        ):
            t0 = time.monotonic()
            try:
                chunks = await self._synthesize_all(
                    sentences_for_tts, voice_name=voice_name
                )
            except TTSGenerationError as e:
                await self._safe_emit_thinking(
                    "*voice rendering stalled, falling back to pre-rendered audio*",
                    investigation_id=investigation_id,
                    story_unit_id=None,
                )
                logger.warning("narrator.narrate: TTS failed after retries: %s", e)
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="narrator",
                    sub_agent=None,
                    story_unit_id=None,
                    investigation_id=investigation_id,
                    model=self._tts.model_id,
                    tool=None,
                    latency_ms=latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    compression_factor=compression_factor,
                    outcome="error",
                    wire_event_id=None,
                    error=str(e),
                )
                self._stamp_last_think_cycle()
                return self._fallback_manifest(
                    draft=draft,
                    voice_name=voice_name,
                    reason="tts_failed",
                )

            # --- Upload each chunk to Cloud Storage ------------------------
            try:
                audio_urls = await self._upload_chunks(
                    chunks=chunks, story_id=story_id
                )
            except Exception as e:
                logger.exception(
                    "narrator.narrate: storage upload failed for story_id=%s",
                    story_id,
                )
                await self._safe_emit_thinking(
                    "*audio upload stalled; falling back to pre-rendered audio*",
                    investigation_id=investigation_id,
                    story_unit_id=None,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                log_agent_call(
                    agent="narrator",
                    sub_agent=None,
                    story_unit_id=None,
                    investigation_id=investigation_id,
                    model=self._tts.model_id,
                    tool=None,
                    latency_ms=latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    compression_factor=compression_factor,
                    outcome="error",
                    wire_event_id=None,
                    error=f"storage: {e}",
                )
                self._stamp_last_think_cycle()
                return self._fallback_manifest(
                    draft=draft,
                    voice_name=voice_name,
                    reason="storage_failed",
                )

            latency_ms = int((time.monotonic() - t0) * 1000)

        # --- Assemble timeline (sentences + words + cues) ------------------
        manifest = self._assemble_manifest(
            draft=draft,
            sentences_text=sentences_text,
            chunks=chunks,
            audio_urls=audio_urls,
            voice_name=voice_name,
        )

        # --- Cost increment ------------------------------------------------
        total_chars = sum(len(s) for s in sentences_for_tts)
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="narrator",
                    sub_agent=None,
                    axis=_COST_AXIS,
                    model=self._tts.model_id,
                    calls=len(sentences_for_tts),
                    audio_chars=total_chars,
                )
            except Exception:
                logger.exception(
                    "narrator.narrate: cost_counter.increment failed"
                )

        # --- Wire milestone ------------------------------------------------
        seconds = max(1, manifest.get("audio_duration_ms", 0) // 1000)
        milestone = f"audio rendered, {seconds}s, narration ready"
        await self._safe_emit_milestone(
            milestone, investigation_id=investigation_id, story_unit_id=None
        )

        # --- Persist `published_stories` doc (Day-6 last-mile wire) ---------
        # The cleared draft + manifest are the canonical published story.
        # The Broadcast page reads from `published_stories`. The Storyteller
        # already passed the draft through equity + the Publish Gate cleared
        # it, so we write the cleared text verbatim — no re-redaction here.
        try:
            await self._persist_published_story(
                draft=draft,
                manifest=manifest,
                voice_profile=voice_profile,
                audit_id=audit_id,
            )
        except Exception:
            # Persistence is best-effort: a dropped published_stories doc
            # is recoverable from publish_audits + the cleared draft, but
            # the manifest the caller is about to consume is still valid.
            logger.exception(
                "narrator.narrate: persist_published_story failed for story_id=%s",
                story_id,
            )

        log_agent_call(
            agent="narrator",
            sub_agent=None,
            story_unit_id=None,
            investigation_id=investigation_id,
            model=self._tts.model_id,
            tool=None,
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            compression_factor=compression_factor,
            outcome="success",
            wire_event_id=None,
            error=None,
        )

        self._stamp_last_think_cycle()
        return manifest

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """No-op for Day-5. Storyteller drafts trigger narration via direct
        dispatch from the Editor/Storyteller chain (Day-6+). For Day-5 this
        method simply waits for the stop_event and exits cleanly.
        """
        if stop_event is None:
            return
        try:
            await stop_event.wait()
        except asyncio.CancelledError:  # pragma: no cover — SIGTERM path
            return

    # -- Text assembly -------------------------------------------------------

    def _build_narration_sentences(
        self, draft: StoryDraftForNarration
    ) -> list[str]:
        """Concatenate dek + body + hometown_panel_text + historical_echo_text
        in playback order, then sentence-split.

        Paragraph breaks (blank lines) are PRESERVED as the literal token
        `\n\n` so `_apply_inline_tags` can detect them when injecting
        `[long pause]` markers.
        """
        parts: list[str] = []
        for key in ("dek", "body", "hometown_panel_text", "historical_echo_text"):
            value = (draft.get(key) or "").strip()
            if value:
                parts.append(value)
        if not parts:
            return []
        joined = "\n\n".join(parts)

        # Sentence-split per section so paragraph boundaries don't get fused.
        # Walk paragraphs, sentence-split each, and remember which sentences
        # ended a paragraph (those get a `[long pause]` later).
        sentences: list[str] = []
        for paragraph in joined.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            paragraph_sentences = split_into_sentences(paragraph)
            sentences.extend(paragraph_sentences)
            # Mark the last sentence of this paragraph with a sentinel so
            # `_apply_inline_tags` can swap it for a `[long pause]`.
            if sentences:
                sentences[-1] = sentences[-1] + "​"  # zero-width sentinel

        return sentences

    def _apply_inline_tags(
        self, sentences: list[str], *, place_name: str
    ) -> list[str]:
        """Inject `[short pause]`, `[long pause]`, `[emphasis]` markers.

        Rules (deterministic, conservative — BUILD_SPEC §3.5 + §5.6):
          - Every sentence: append `[short pause]`.
          - Sentence at a paragraph boundary (sentinel ​): append
            `[long pause]` instead of `[short pause]`.
          - First occurrence of `place_name` across ALL sentences: wrap in
            `[emphasis]...[/emphasis]`. (Best-effort; if Gemini doesn't
            recognize the close tag the model still says the words — no harm.)
        """
        out: list[str] = []
        place_emphasized = False
        place_lc = (place_name or "").strip()
        for raw in sentences:
            paragraph_break = raw.endswith("​")
            text = raw.rstrip("​").strip()
            if not text:
                continue

            # Apply [emphasis] to the first occurrence of the place name.
            if place_lc and not place_emphasized:
                idx = text.lower().find(place_lc.lower())
                if idx >= 0:
                    end = idx + len(place_lc)
                    text = (
                        text[:idx]
                        + "[emphasis]"
                        + text[idx:end]
                        + "[/emphasis]"
                        + text[end:]
                    )
                    place_emphasized = True

            tag = "[long pause]" if paragraph_break else "[short pause]"
            out.append(f"{text} {tag}")
        return out

    # -- Synthesis -----------------------------------------------------------

    async def _synthesize_all(
        self,
        sentences: list[str],
        *,
        voice_name: str,
    ) -> list[dict]:
        """Synthesize each sentence; return a list of `{pcm, mime, sample_rate, duration_ms}`.

        Failure handling: each chunk gets one retry with inline tags stripped
        (BUILD_SPEC §17.5). On second failure, raise TTSGenerationError;
        caller falls back to the pre-rendered MP3.
        """
        chunks: list[dict] = []
        for sentence in sentences:
            chunk = await self._synthesize_one_with_retry(
                sentence, voice_name=voice_name
            )
            chunks.append(chunk)
        return chunks

    async def _synthesize_one_with_retry(
        self,
        text: str,
        *,
        voice_name: str,
    ) -> dict:
        """Synthesize one chunk with one retry on failure.

        First attempt: text as-is (with inline tags).
        Second attempt: tags stripped (BUILD_SPEC §17.5 simplification).
        """
        attempts = [text, _strip_inline_tags(text)]
        last_exc: Exception | None = None
        for i, attempt_text in enumerate(attempts, start=1):
            try:
                pcm, mime = await self._tts.synthesize(
                    attempt_text, voice_name=voice_name
                )
                sample_rate = parse_l16_rate(mime, default=self._sample_rate_hz)
                duration_ms = estimate_audio_duration_ms(
                    len(pcm),
                    sample_rate=sample_rate,
                    channels=_DEFAULT_CHANNELS,
                    sample_width=_DEFAULT_SAMPLE_WIDTH,
                )
                return {
                    "pcm": pcm,
                    "mime": mime,
                    "sample_rate": sample_rate,
                    "duration_ms": duration_ms,
                }
            except TTSGenerationError as e:
                last_exc = e
                logger.warning(
                    "narrator: TTS attempt %d/%d failed: %s",
                    i, len(attempts), e,
                )
        raise TTSGenerationError(
            f"TTS failed after {len(attempts)} attempts: {last_exc}",
            status_code=getattr(last_exc, "status_code", None),
        )

    # -- Cloud Storage upload ------------------------------------------------

    async def _upload_chunks(
        self, *, chunks: list[dict], story_id: str
    ) -> list[str]:
        """Upload each chunk's WAV-wrapped PCM to GCS. Returns gs:// URLs.

        Each chunk goes to `gs://{bucket}/{story_id}/{idx:04d}.wav`. The
        upload is synchronous; we hop to a thread to avoid blocking the
        event loop.
        """
        if self._storage is None:
            raise RuntimeError("narrator: storage client not configured")
        bucket = self._get_bucket()
        urls: list[str] = []
        for idx, chunk in enumerate(chunks):
            wav_bytes = wrap_pcm_as_wav(
                chunk["pcm"],
                sample_rate=chunk.get("sample_rate", self._sample_rate_hz),
                channels=_DEFAULT_CHANNELS,
                sample_width=_DEFAULT_SAMPLE_WIDTH,
            )
            blob_name = f"{story_id}/{idx:04d}.wav"
            await asyncio.to_thread(
                _upload_blob, bucket, blob_name, wav_bytes
            )
            urls.append(f"gs://{self._bucket_name}/{blob_name}")
        return urls

    def _get_bucket(self) -> Any:
        """Return the GCS bucket. Tests override `_storage` with a stub that
        exposes `bucket(name)`.
        """
        return self._storage.bucket(self._bucket_name)

    # -- Manifest assembly ---------------------------------------------------

    def _assemble_manifest(
        self,
        *,
        draft: StoryDraftForNarration,
        sentences_text: list[str],
        chunks: list[dict],
        audio_urls: list[str],
        voice_name: str,
    ) -> NarrationManifest:
        """Build the NarrationManifest from per-sentence chunk durations.

        Word-level timing note (BUILD_SPEC §3.5 fallback path 2/3):
        Gemini Flash TTS does NOT return word-level timestamps natively as of
        Day-1 verification. We estimate them per-sentence-then-interpolate:
            duration_per_word = sentence_chunk_duration_ms / word_count
            word.start_ms = sentence.start_ms + (word_index * duration_per_word)
            word.end_ms = word.start_ms + duration_per_word

        This is per-sentence linear interpolation — sentence-level highlighting
        is the primary effect on the Broadcast page anyway and lands well.
        """
        cleaned_sentences = [
            s.rstrip("​").strip() for s in sentences_text
        ]

        sentences_out: list[SentenceBoundary] = []
        words_out: list[WordTiming] = []
        cursor_ms = 0
        for sentence_idx, (text, chunk) in enumerate(
            zip(cleaned_sentences, chunks)
        ):
            duration_ms = int(chunk.get("duration_ms", 0))
            start_ms = cursor_ms
            end_ms = cursor_ms + duration_ms
            sentences_out.append(
                SentenceBoundary(
                    sentence_idx=sentence_idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                )
            )
            # Per-word linear interpolation across this sentence's duration.
            words = text.split()
            if words and duration_ms > 0:
                per_word = duration_ms // max(1, len(words))
                for w_idx, w in enumerate(words):
                    w_start = start_ms + (w_idx * per_word)
                    w_end = (
                        w_start + per_word
                        if w_idx < len(words) - 1
                        else end_ms
                    )
                    words_out.append(
                        WordTiming(
                            w=w,
                            start_ms=w_start,
                            end_ms=w_end,
                            sentence_idx=sentence_idx,
                        )
                    )
            cursor_ms = end_ms

        cues = self._detect_cues(
            sentences=sentences_out,
            place_name=(draft.get("place_name_for_cues") or "").strip(),
            era_reference=(draft.get("era_reference_for_cues") or "").strip(),
        )

        return NarrationManifest(
            story_id=draft.get("story_id") or "",
            audio_urls=audio_urls,
            audio_duration_ms=cursor_ms,
            voice_name=voice_name,
            sample_rate_hz=self._sample_rate_hz,
            sample_format="pcm_l16",
            words=words_out,
            sentences=sentences_out,
            cues=cues,
            synthid_watermarked=True,  # Gemini Flash TTS docs: SynthID always on
            created_at=self._clock().isoformat(),
            fallback=False,
        )

    def _detect_cues(
        self,
        *,
        sentences: list[SentenceBoundary],
        place_name: str,
        era_reference: str,
    ) -> list[VisualCue]:
        """Find sentence offsets where the place name + era reference first
        appear; record them as `VisualCue` entries.

        BUILD_SPEC §7.6: "Cue points are embedded at narration generation
        time, not detected client-side by string matching" — we do the
        matching here, on the as-written sentences (no athlete-name risk
        because the input is post-NIL-Layer when it goes through the full
        chain; for Day-5 tests the input is synthetic place-only).
        """
        cues: list[VisualCue] = []
        place_lc = (place_name or "").lower()
        era_lc = (era_reference or "").lower()

        if place_lc:
            for s in sentences:
                if place_lc in (s.get("text") or "").lower():
                    cues.append(
                        VisualCue(
                            kind="panel",
                            panel="hometown",
                            at_ms=int(s.get("start_ms", 0)),
                        )
                    )
                    break
        if era_lc:
            for s in sentences:
                if era_lc in (s.get("text") or "").lower():
                    cues.append(
                        VisualCue(
                            kind="panel",
                            panel="historical_echo",
                            at_ms=int(s.get("start_ms", 0)),
                        )
                    )
                    break
        return cues

    # -- Failure modes -------------------------------------------------------

    def _empty_manifest(
        self,
        *,
        draft: StoryDraftForNarration,
        voice_name: str,
        fallback_reason: str,
    ) -> NarrationManifest:
        """Empty manifest used for cost-ceiling / paused / empty-input paths."""
        return NarrationManifest(
            story_id=draft.get("story_id") or "",
            audio_urls=[],
            audio_duration_ms=0,
            voice_name=voice_name,
            sample_rate_hz=self._sample_rate_hz,
            sample_format="pcm_l16",
            words=[],
            sentences=[],
            cues=[],
            synthid_watermarked=False,
            created_at=self._clock().isoformat(),
            fallback=True,
            fallback_reason=fallback_reason,
        )

    def _fallback_manifest(
        self,
        *,
        draft: StoryDraftForNarration,
        voice_name: str,
        reason: str,
    ) -> NarrationManifest:
        """Pre-rendered MP3 fallback manifest (BUILD_SPEC §17.5).

        Points at `gs://storytellers-room-fallback-heroes/...narration_fallback.wav`
        — a path that may or may not exist in the bucket today (Day-9 pre-cache
        is the canonical population path). The Broadcast page handles missing
        objects gracefully via the curtain rise's audio prime catch.
        """
        return NarrationManifest(
            story_id=draft.get("story_id") or "",
            audio_urls=[self._fallback_audio_url],
            audio_duration_ms=0,
            voice_name=voice_name,
            sample_rate_hz=self._sample_rate_hz,
            sample_format="pcm_l16",
            words=[],
            sentences=[],
            cues=[],
            synthid_watermarked=False,
            created_at=self._clock().isoformat(),
            fallback=True,
            fallback_reason=reason,
        )

    # -- Published story persistence ----------------------------------------

    async def _persist_published_story(
        self,
        *,
        draft: StoryDraftForNarration,
        manifest: NarrationManifest,
        voice_profile: VoiceProfile,
        audit_id: str | None,
    ) -> None:
        """Write the cleared draft + manifest to `published_stories`.

        Skipped silently when:
          - firestore is unavailable (test stubs without `_firestore`)
          - the manifest is a fallback (no audio rendered)
          - the manifest has no audio URL (degenerate empty draft)

        The Storyteller draft is already NIL-clean (the cleared
        publish_audit said so); we copy it verbatim.
        """
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return
        if manifest.get("fallback") and not manifest.get("audio_urls"):
            return
        audio_urls = manifest.get("audio_urls") or []
        if not audio_urls:
            return

        story_id = draft.get("story_id") or manifest.get("story_id") or ""
        story_unit_id = draft.get("story_unit_id")
        # NIL signature: pulled from the cleared publish_audit when an
        # audit_id was threaded through. Best-effort — the audit may have
        # been written by a stub coll.add() so direct doc-id lookups can
        # miss; we fall back to a scan.
        audit = await self._read_publish_audit(audit_id) if audit_id else None
        nil_signature = _build_nil_signature(audit)

        duration_ms = int(manifest.get("audio_duration_ms") or 0)
        manifest_id = manifest.get("story_id") or story_id

        published: dict[str, Any] = {
            "story_id": story_id,
            "story_unit_id": story_unit_id,
            "kicker_place": draft.get("place_name_for_cues")
            or draft.get("place_name"),
            "headline": draft.get("headline", ""),
            "dek": draft.get("dek", ""),
            "body_paragraphs": _split_paragraphs(draft.get("body", "")),
            "pull_quote": draft.get("pull_quote"),
            "verified_claims": draft.get("verified_claims", []),
            "narration": {
                "voice_name": manifest.get("voice_name") or voice_profile,
                "audio_url": audio_urls[0],
                "audio_urls": list(audio_urls),
                "duration_s": duration_ms // 1000,
                "manifest_id": manifest_id,
            },
            "hero_image_url": draft.get("hero_image_url"),
            "nil_signature": nil_signature,
            "audit_id": audit_id,
            "published_at": self._clock().isoformat(),
            "mode": "published",
        }

        try:
            coll = self._firestore.collection("published_stories")
        except Exception:
            return
        try:
            res = coll.add(published)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
        except Exception:
            logger.exception(
                "narrator._persist_published_story: write failed for story_id=%s",
                story_id,
            )

    async def _read_publish_audit(self, audit_id: str) -> dict | None:
        """Best-effort read of `/publish_audits/{audit_id}`. Returns None on
        any failure path so `_persist_published_story` proceeds with an
        empty NIL signature."""
        if not audit_id:
            return None
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return None
        try:
            coll = self._firestore.collection("publish_audits")
        except Exception:
            return None
        # Direct doc-id lookup.
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(audit_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
                        if data:
                            return dict(data)
        except Exception:
            logger.debug(
                "narrator._read_publish_audit: doc-id lookup failed; scanning",
                exc_info=True,
            )
        # Fallback: scan for matching `audit_id` field (PublishGate writes
        # via coll.add, so the doc id is auto-generated).
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = d.to_dict() if hasattr(d, "to_dict") else (
                        d if isinstance(d, dict) else {}
                    )
                    if data.get("audit_id") == audit_id or data.get("id") == audit_id:
                        return dict(data)
            else:
                for d in stream:
                    data = d.to_dict() if hasattr(d, "to_dict") else (
                        d if isinstance(d, dict) else {}
                    )
                    if data.get("audit_id") == audit_id or data.get("id") == audit_id:
                        return dict(data)
        except Exception:
            logger.exception("narrator._read_publish_audit: scan failed")
        return None

    # -- Wire helpers --------------------------------------------------------

    async def _safe_emit_thinking(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None,
    ) -> None:
        await self._safe_emit(
            message,
            message_type="thinking",
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )

    async def _safe_emit_milestone(
        self,
        message: str,
        *,
        investigation_id: str,
        story_unit_id: str | None,
    ) -> None:
        await self._safe_emit(
            message,
            message_type="milestone",
            investigation_id=investigation_id,
            story_unit_id=story_unit_id,
        )

    async def _safe_emit(
        self,
        message: str,
        *,
        message_type: str,
        investigation_id: str,
        story_unit_id: str | None,
    ) -> None:
        """Emit a Wire event without raising into the caller."""
        event: dict = {
            "agent": "narrator",
            "message": message,
            "message_type": message_type,
            "mode": "live",
        }
        if story_unit_id is not None:
            event["story_unit_id"] = story_unit_id
        try:
            await self._wire.emit(event, investigation_id=investigation_id)
        except WireProxyNotReadyError:
            logger.warning(
                "narrator: wire proxy not ready; cannot emit %s event",
                message_type,
            )
        except Exception:
            logger.exception(
                "narrator: failed to emit %s event", message_type
            )

    # -- Misc ---------------------------------------------------------------

    def _stamp_last_think_cycle(self) -> None:
        if self._runtime_state is None:
            return
        try:
            self._runtime_state.last_think_cycle = datetime.now(timezone.utc)
        except Exception:
            logger.exception("narrator: failed to stamp last_think_cycle")


# -- Module helpers -----------------------------------------------------------


def _strip_inline_tags(text: str) -> str:
    """Remove `[short pause]`, `[long pause]`, `[pause=...]`, `[emphasis]`,
    `[/emphasis]`, `[slow]`, `[fast]` markers.

    Used as the second-attempt fallback per BUILD_SPEC §17.5 — if the model
    chokes on the tagged variant, a clean text retry is more likely to land.
    """
    import re as _re

    return _re.sub(r"\[[^\[\]]*\]", "", text).strip()


def _split_paragraphs(body: str) -> list[str]:
    """Split a Storyteller body into paragraphs on blank lines.

    The Storyteller separates paragraphs with `\n\n`; published_stories
    consumers (the Broadcast page) want a list of paragraph strings, not
    a single blob. Empty paragraphs are dropped.
    """
    if not isinstance(body, str) or not body.strip():
        return []
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def _build_nil_signature(audit: dict | None) -> dict:
    """Pull the NIL signature off a cleared publish_audit doc.

    The signature surfaces in `published_stories.nil_signature` so the
    Broadcast page can render the audit drawer's "29 claims checked,
    1 softened, 0 removed" line — proof of trust per Demo Moment 5.
    """
    if not isinstance(audit, dict):
        return {
            "claims_checked": 0,
            "claims_softened": 0,
            "claims_removed": 0,
            "redactions": 0,
            "aggregations": 0,
        }
    sub_stages = audit.get("sub_stages") or {}
    fact_check = sub_stages.get("fact_check") or {}
    nil_review = sub_stages.get("nil_redaction_review") or {}
    removed_claims = fact_check.get("removed_claims") or []
    return {
        "claims_checked": int(fact_check.get("claims_checked") or 0),
        "claims_softened": int(fact_check.get("claims_softened") or 0),
        "claims_removed": (
            len(removed_claims) if isinstance(removed_claims, list)
            else int(fact_check.get("claims_removed") or 0)
        ),
        "redactions": int(nil_review.get("redacted") or 0),
        "aggregations": int(nil_review.get("aggregated") or 0),
    }


def _upload_blob(bucket: Any, blob_name: str, data: bytes) -> None:
    """Synchronous GCS upload, wrapped via asyncio.to_thread.

    Matches `google.cloud.storage.Bucket.blob(name).upload_from_string(...)`
    — tests pass a stub that records the call.
    """
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type="audio/wav")
