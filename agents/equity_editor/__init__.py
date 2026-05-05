"""Paralympic Equity Editor agent: parity enforcement at three levels.

The Equity Editor is the 40% Impact lever (CONSTITUTION §3 Law 3 + §0
Decision Filter — "the Equity Editor caused the anchor story"). Its
interventions arrive (not stream) on the Wire and have veto power over
publication. Mirrors the Editor / Investigator pattern at
`agents/editor/agent.py` and `agents/investigator/agent.py` — same Runner
shape, same closure-bound tools, same retry + cost-ceiling + Wire-thinking
discipline. Voice signature lives in `/prompts/equity_editor.md` per
CONSTITUTION Rule 1.
"""

from __future__ import annotations

from agents.equity_editor.agent import EquityEditorAgent

__all__ = ["EquityEditorAgent"]
