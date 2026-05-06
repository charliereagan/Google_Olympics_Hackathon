"""Agent handoff event emission.

A *handoff* is the structured "control passed from agent A to agent B" event
the agent-graph `/floor` consumes to render particle streams between the
seven agent nodes (BUILD_SPEC §9.6). Handoffs live in the parallel
`agent_handoffs` Firestore collection — a sibling of `wire_events`, not a
sub-set of it.

Why a separate collection (and not a `wire.emit()` extension):

    1. Wire events carry redactable narrative text and route through the
       NIL Redaction Layer. Handoffs are pure structured metadata
       (`{from_agent, to_agent, tool_call_id, ...}`) — there is nothing
       for NIL to redact, and routing them through the proxy would block
       handoff emission whenever the NIL Layer is unloaded.
    2. The `/floor` frontend wants `event: handoff` SSE frames that are
       distinct from `event: wire`. Two collections, two `onSnapshot`
       listeners, two SSE event types.
    3. Append-only and infrastructure-emitted: the LLM does NOT decide to
       emit a handoff. The dispatch tools call `emit_handoff(...)` from
       Python the moment control passes between agents.

This module exposes ONE function — `emit_handoff(...)` — and the seven-
agent enum (`AGENT_IDS`). The dispatch wires call it from
`agents/editor/agent.py`, `agents/equity_editor/tools.py`,
`agents/storyteller/tools.py`, and the publish_gate orchestrator.

NEVER call `wire.emit()` from this module — `agent_handoffs` is a parallel
collection. NEVER call the NIL Layer here — handoffs have no narrative
text. NEVER write to the `wire_events` collection from here either — that
bypasses the proxy and CI lint blocks it (see
`scripts/lint_no_direct_wire_writes.py`, HOE-DEC-018).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# The seven-agent cast (CONSTITUTION Rule 2). Any handoff with a `from_agent`
# or `to_agent` outside this set is a programmer error.
AGENT_IDS: frozenset[str] = frozenset(
    {
        "editor",
        "scout_desk",
        "investigator",
        "equity_editor",
        "storyteller",
        "narrator",
        "publish_gate",
    }
)

# The Firestore collection for handoff events. Append-only.
COLLECTION_NAME = "agent_handoffs"


async def emit_handoff(
    firestore: Any,
    *,
    from_agent: str,
    to_agent: str,
    tool_call_id: str,
    story_unit_id: str | None = None,
    investigation_id: str | None = None,
    mode: str = "live",
) -> str:
    """Persist one handoff event to `agent_handoffs`. Returns the doc id.

    Args:
        firestore: an async-capable Firestore client (real or stub). The
            same shape `WireEmitter` accepts — `collection(name).add(doc)`
            returning either an awaitable producing `(write_result, doc_ref)`
            or a doc ref directly.
        from_agent: source — must be a member of `AGENT_IDS`.
        to_agent: destination — must be a member of `AGENT_IDS`.
        tool_call_id: the dispatch tool name that triggered the handoff
            (e.g., `'dispatch_investigator'`, `'request_equity_review'`,
            `'request_publish_gate'`).
        story_unit_id: optional — the active investigation context's
            place / program / pattern id, when known.
        investigation_id: optional — the active investigation id.
        mode: `'live' | 'replay' | 'published'`. Defaults to `'live'`.
            Mirrors the `wire_events` mode field so SSE pre-seed and
            live-window queries work consistently.

    Returns:
        The Firestore-assigned document id (or a best-effort string from
        the stub client).

    Raises:
        ValueError: if `from_agent` or `to_agent` is not in `AGENT_IDS`,
            or if `mode` is not one of the three accepted values. Raises
            BEFORE any Firestore call so a programmer error fails fast and
            never produces a malformed document.
        RuntimeError: if `firestore` is None or doesn't expose a
            `.collection(name).add(doc)` shape — handoffs are
            infrastructure events; the runtime should always be able to
            persist them.
    """
    # --- Validate inputs (raise BEFORE touching Firestore) ----------------
    if from_agent not in AGENT_IDS:
        raise ValueError(
            f"emit_handoff: unknown from_agent {from_agent!r}; "
            f"expected one of {sorted(AGENT_IDS)}"
        )
    if to_agent not in AGENT_IDS:
        raise ValueError(
            f"emit_handoff: unknown to_agent {to_agent!r}; "
            f"expected one of {sorted(AGENT_IDS)}"
        )
    if mode not in {"live", "replay", "published"}:
        raise ValueError(
            f"emit_handoff: unknown mode {mode!r}; "
            f"expected one of 'live', 'replay', 'published'"
        )
    if not isinstance(tool_call_id, str) or not tool_call_id:
        raise ValueError(
            "emit_handoff: tool_call_id must be a non-empty string"
        )

    if firestore is None or not hasattr(firestore, "collection"):
        raise RuntimeError(
            "emit_handoff: firestore client unavailable; "
            "cannot persist agent handoff"
        )

    doc: dict[str, Any] = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "tool_call_id": tool_call_id,
        "story_unit_id": story_unit_id,
        "investigation_id": investigation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }

    coll = firestore.collection(COLLECTION_NAME)
    result = coll.add(doc)
    # The async Firestore client returns an awaitable producing
    # `(write_result, doc_ref)`; some stubs return a doc ref directly,
    # or even a coroutine producing a string. Normalize all three.
    if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
        result = await result

    if isinstance(result, tuple) and len(result) >= 2:
        doc_ref = result[1]
        return str(getattr(doc_ref, "id", doc_ref))
    if hasattr(result, "id"):
        return str(result.id)
    return str(result)


async def safe_emit_handoff(
    firestore: Any,
    *,
    from_agent: str,
    to_agent: str,
    tool_call_id: str,
    story_unit_id: str | None = None,
    investigation_id: str | None = None,
    mode: str = "live",
) -> str | None:
    """Best-effort wrapper for `emit_handoff` — never raises into the loop.

    The dispatch points use this so a transient Firestore failure (or a
    stub-mode `firestore=None`) doesn't crash the agent that's just
    handing control off. The handoff event is purely informational for
    the agent-graph Floor; losing one frame is acceptable, taking down
    the dispatching agent is not.

    Returns the doc id on success, None on any failure path.
    """
    try:
        return await emit_handoff(
            firestore,
            from_agent=from_agent,
            to_agent=to_agent,
            tool_call_id=tool_call_id,
            story_unit_id=story_unit_id,
            investigation_id=investigation_id,
            mode=mode,
        )
    except ValueError:
        # Programmer error — re-raise so tests catch it loudly.
        raise
    except Exception:
        logger.warning(
            "emit_handoff: persist failed for %s -> %s (tool=%s); "
            "agent-graph particle stream may drop one frame",
            from_agent,
            to_agent,
            tool_call_id,
            exc_info=True,
        )
        return None


__all__ = [
    "AGENT_IDS",
    "COLLECTION_NAME",
    "emit_handoff",
    "safe_emit_handoff",
]
