"""Athlete-registry loader for The Storyteller's Room.

Public, US-filtered roster of Olympians and Paralympians used as the source of
truth for the NIL Redaction Layer (BUILD_SPEC §5.7). The output is INTERNAL
DATA ONLY — it is never exposed to user-facing surfaces.

Run via: ``python3 -m data.load_athlete_registry.cli --dry-run``
"""

__version__ = "0.1.0"
