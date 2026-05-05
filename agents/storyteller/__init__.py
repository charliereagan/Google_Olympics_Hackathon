"""Storyteller agent: turns Investigation Packets into final 400-700 word
narratives about a place, program, or pattern. Never names individuals.

Voice signature lives in `/prompts/storyteller.md` per CONSTITUTION Rule 1.
This module mirrors the Editor / Investigator / Narrator pattern at
`agents/editor/agent.py` etc. — same Runner shape, same closure-bound tools,
same retry + cost-ceiling + Wire-thinking discipline.

The Storyteller is the literary-restraint specialist: BUILD_SPEC §5.5 +
CONSTITUTION Law 4 (Place over Person) + Law 5 (Documentary, not
Sportscaster). Its output is the actual narrative the Narrator will speak
and the Broadcast page will display.
"""

from __future__ import annotations

from agents.storyteller.agent import StorytellerAgent
from agents.storyteller.types import EquityReview, StoryDraft

__all__ = [
    "EquityReview",
    "StoryDraft",
    "StorytellerAgent",
]
