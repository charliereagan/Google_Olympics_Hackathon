"""Wire emission layer.

Public surface:
  - WireEmitter (the in-process write-through proxy; the only legitimate
    writer of `wire_events` documents)
  - WirePacer (per-investigation compression cadence)
  - WireEvent / LeadReport / InvestigationContext / WireScanResult / NilLog
    typed shapes shared across modules

Per HOE-DEC-018: every other path that wants to emit must call
`WireEmitter.emit(event)`. Direct Firestore writes to the wire-events
collection are caught by `scripts/lint_no_direct_wire_writes.py`.
"""

from __future__ import annotations

from agents.wire.pacing import WirePacer
from agents.wire.types import (
    AgentId,
    InvestigationContext,
    LeadReport,
    Mode,
    NilLog,
    NilRedactionLog,
    StreamingProfile,
    SubAgentId,
    WireEvent,
    WireScanResult,
)

__all__ = [
    "AgentId",
    "InvestigationContext",
    "LeadReport",
    "Mode",
    "NilLog",
    "NilRedactionLog",
    "StreamingProfile",
    "SubAgentId",
    "WireEvent",
    "WirePacer",
    "WireScanResult",
]
