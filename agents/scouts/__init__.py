"""Scout Desk: ParallelAgent of four sub-scouts + the HND detector.

Day-2 scope: ScoutDesk class + HndDetector + per-scout LlmAgent shells. Sub-
scout bodies are driven entirely from `/prompts/*.md`. Python here is
plumbing — tools, runners, Firestore-as-rendezvous aggregation.

Imports are deliberately lazy so a stripped-down test environment (HND
detector only) can import this package without pulling in the ADK shells.
"""

from __future__ import annotations

__all__ = ["HndDetector", "ScoutDesk"]


def __getattr__(name: str):  # pragma: no cover — lazy attr access
    if name == "HndDetector":
        from agents.scouts.hnd_detector import HndDetector
        return HndDetector
    if name == "ScoutDesk":
        from agents.scouts.desk import ScoutDesk
        return ScoutDesk
    raise AttributeError(f"module 'agents.scouts' has no attribute {name!r}")
