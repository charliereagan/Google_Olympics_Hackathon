"""Typed shapes for the Storyteller.

Pinned to BUILD_SPEC §8.5 (StoryDraft) plus the equity_review block. The
Storyteller's `write_story_draft` tool validates against this shape; the
Narrator (`StoryDraftForNarration`) consumes a subset of it.

NIL note: NEVER include any field that holds an athlete's name. The
Storyteller works exclusively at the place / program / pattern level.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class EquityReview(TypedDict, total=False):
    """The equity-review block on a StoryDraft (BUILD_SPEC §8.5)."""

    cleared: bool
    feedback: str
    revisions_count: int


class StoryDraft(TypedDict, total=False):
    """The Firestore doc shape persisted to `/story_drafts/{auto_id}`.

    Mirrors BUILD_SPEC §8.5 with the addition of `place_name` /
    `era_reference` (used by the Narrator to derive cue offsets without
    re-parsing the body) and `storyteller_notes` (internal commentary —
    NOT user-facing).
    """

    id: str
    investigation_packet_id: str
    headline: str               # 8-12 words
    dek: str                    # one sentence, emotional hook
    body: str                   # 400-700 words
    why_this_matters: list[str]  # 3 bullets
    hometown_panel: str         # 50-75 word place portrait
    historical_echo: str        # 50-100 words connecting to era
    storyteller_notes: str      # internal — NOT user-facing
    equity_review: EquityReview
    publish_gate_decision: Literal["pending", "cleared", "returned", "killed"]
    place_name: str             # canonical place display string for Narrator cues
    era_reference: str          # canonical era reference for Narrator cues
    story_unit_id: str          # carried through from investigation packet (search key)
    created_at: str
    updated_at: str
