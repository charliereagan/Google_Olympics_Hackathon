"""Typed shapes for the Narrator.

Mirrors BUILD_SPEC §7.6 Audio Sync Architecture. The Broadcast frontend
(Day-8) and the Storyteller (Day-6) both read this contract. Keep it stable.

NIL note: this module never accepts athlete-name fields by name. The
Storyteller draft contains only place + program + pattern text (post-Equity,
post-NIL Layer when run through the full chain). The Narrator copies whatever
text it gets — no guarantees here.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class WordTiming(TypedDict, total=False):
    """One word's start/end offset within the full narration timeline."""

    w: str  # the word as spoken
    start_ms: int  # offset from the start of the full narration audio
    end_ms: int
    sentence_idx: int  # which sentence this word belongs to


class SentenceBoundary(TypedDict, total=False):
    """One sentence's start/end offset within the full narration timeline."""

    sentence_idx: int
    start_ms: int
    end_ms: int
    text: str  # the sentence as written


class VisualCue(TypedDict, total=False):
    """A panel reveal pegged to the narration audio timeline.

    BUILD_SPEC §7.6: cue points are embedded at narration generation time
    (here, by scanning sentence text for the place name + era reference) and
    stored in the manifest so the frontend doesn't have to string-match
    paraphrased text at playback.
    """

    kind: Literal["panel"]  # only 'panel' today; future expansions optional
    panel: Literal["hometown", "historical_echo"]
    at_ms: int  # narration timeline offset to fire the panel reveal


class NarrationManifest(TypedDict, total=False):
    """The Narrator's output. The Broadcast frontend renders against this."""

    story_id: str
    audio_urls: list[str]  # GCS URLs in playback order, one per sentence chunk
    audio_duration_ms: int  # sum of all chunks
    voice_name: str  # 'Algenib' (Broadcast) or 'Fenrir' (Wire / fallback)
    sample_rate_hz: int  # 24000
    sample_format: Literal["pcm_l16"]
    words: list[WordTiming]
    sentences: list[SentenceBoundary]
    cues: list[VisualCue]
    synthid_watermarked: bool  # True per Gemini Flash TTS docs
    created_at: str  # ISO 8601
    fallback: bool  # True iff the manifest is the pre-rendered fallback path
    fallback_reason: str  # populated when `fallback=True`


class StoryDraftForNarration(TypedDict, total=False):
    """The Narrator's input. A subset of `StoryDraft` (BUILD_SPEC §8.5) plus
    cue-detection helpers.

    The Storyteller (Day-6/7) will produce these. For Day-5 the Narrator
    consumes mocked drafts in tests.
    """

    story_id: str
    headline: str  # not narrated — used for Broadcast layout
    dek: str  # narrated as opening
    body: str  # the 400-700 word narrative; sentence-split for chunking
    hometown_panel_text: str  # narrated when the panel reveals
    historical_echo_text: str
    place_name_for_cues: str  # used to find the cue offset for the Hometown panel reveal
    era_reference_for_cues: str  # used to find the cue offset for the Historical Echo panel
