"""Typed shapes for the Wire layer.

Mirrors BUILD_SPEC §6.2 verbatim plus the cross-module dataclasses (LeadReport,
InvestigationContext, StreamingProfile, WireScanResult, NilLog).

Only stdlib imports — keeps this file safe for the lint test fixtures and
trivially importable from anywhere in the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

# --- Identity literals ---------------------------------------------------------

AgentId = Literal[
    "editor",
    "scout_desk",
    "investigator",
    "equity_editor",
    "storyteller",
    "narrator",
    "publish_gate",
]

SubAgentId = Literal["cinderella", "comeback", "hometown", "echo"]

MessageType = Literal["thinking", "milestone", "intervention", "decision"]

Mode = Literal["live", "replay", "published"]

VisualTreatment = Literal["normal", "highlighted", "intervention"]

# --- Wire event shape (TypedDict, matches Firestore document) -----------------


class NilRedactionLog(TypedDict, total=False):
    direct_matches_redacted: int
    aggregations_applied: int


class WireEvent(TypedDict, total=False):
    """A single Wire event, post-redaction.

    Fields with `total=False`: optional on emit input. The proxy fills
    `id`, `timestamp`, and `nil_redaction_log` automatically.
    """

    id: str
    timestamp: str
    agent: AgentId
    sub_agent: SubAgentId | None
    message: str
    message_type: MessageType
    confidence: float
    confidence_delta: float
    story_unit_id: str
    investigation_id: str
    evidence_refs: list[str]
    mode: Mode
    visual_treatment: VisualTreatment
    compression_factor: float
    nil_redaction_log: NilRedactionLog


# --- Cross-module dataclasses -------------------------------------------------


@dataclass(frozen=True)
class StreamingProfile:
    """Per-agent cognition-speed config (BUILD_SPEC §6.11)."""

    agent: str
    base_chars_per_second: float
    jitter: float
    mid_message_pause_chance: float
    pause_min_ms: int
    pause_max_ms: int
    arrival_style: Literal["streamed", "instant"]


@dataclass
class NilLog:
    """The structured log a NIL scan returns to the proxy.

    Fields mirror NilRedactionLog (TypedDict) but as a dataclass so the
    Layer can mutate / add internal fields without leaking them onto the
    Firestore document.
    """

    direct_matches_redacted: int = 0
    aggregations_applied: int = 0
    needles_matched: list[str] = field(default_factory=list)

    def to_log_dict(self) -> NilRedactionLog:
        """Project to the public shape that ships on the WireEvent."""
        return NilRedactionLog(
            direct_matches_redacted=self.direct_matches_redacted,
            aggregations_applied=self.aggregations_applied,
        )


@dataclass
class WireScanResult:
    """Output of NilRedactionLayer.scan_wire."""

    decision: Literal["pass", "aggregate", "redact"]
    redacted_message: str
    log: NilLog


@dataclass
class LeadReport:
    """A Scout Lead Report (BUILD_SPEC §8.3) — Firestore-persisted.

    The Scout Desk's `run_pass` returns a list of these; the HND detector
    aggregates them across the rolling window.
    """

    id: str
    story_unit_id: str
    story_unit_title: str
    story_unit_type: Literal["place", "program", "pattern"]
    scout: SubAgentId
    signal_type: str
    confidence: float
    notes: str  # never names individual athletes
    evidence_refs: list[str] = field(default_factory=list)
    status: Literal["investigating", "promoted", "killed", "merged"] = "investigating"
    created_at: str = ""


@dataclass
class InvestigationContext:
    """Per-investigation state passed down to Scouts/Investigator/Storyteller.

    The `compression_factor` is the lever for the live URL hero CTA's
    4× cadence (HOE-DEC-021, BUILD_SPEC §6.10).
    """

    investigation_id: str
    story_unit_id: str | None = None
    compression_factor: float = 1.0
    mode: Mode = "live"
