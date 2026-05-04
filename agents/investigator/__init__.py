"""Investigator agent: depth-of-research synthesis.

Takes a Scout Lead Report (about a place / program / pattern) and turns it
into an Investigation Packet (BUILD_SPEC §5.3 + §8.4). Mirrors the EditorAgent
pattern at `agents/editor/agent.py` — same Runner shape, same closure-bound
tools, same retry + cost-ceiling + Wire-thinking discipline.
"""

from __future__ import annotations

from agents.investigator.agent import InvestigatorAgent

__all__ = ["InvestigatorAgent"]
