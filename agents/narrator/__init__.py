"""Narrator agent: turns Storyteller drafts into spoken Olympic-broadcast
narration via Gemini 3.1 Flash TTS.

Outputs a `NarrationManifest` (audio chunks + word/sentence timing + visual
cue points) that the Broadcast page choreographs against (BUILD_SPEC §5.6 +
§7.6). The Narrator is deterministic synthesis, not an LLM Runner — TTS is
a direct Vertex AI call.

The public API is `NarratorAgent.narrate(draft, voice_profile=...)`.
"""

from __future__ import annotations

from agents.narrator.agent import NarratorAgent
from agents.narrator.tts_client import GeminiFlashTTSClient, TTSGenerationError
from agents.narrator.types import (
    NarrationManifest,
    SentenceBoundary,
    StoryDraftForNarration,
    VisualCue,
    WordTiming,
)

__all__ = [
    "GeminiFlashTTSClient",
    "NarrationManifest",
    "NarratorAgent",
    "SentenceBoundary",
    "StoryDraftForNarration",
    "TTSGenerationError",
    "VisualCue",
    "WordTiming",
]
