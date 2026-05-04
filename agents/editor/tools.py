"""Editor tool surface.

Each tool is a thin wrapper around a real impl. The docstring is the LLM-
facing spec — it's what the model sees when it decides to call the tool.

If `google.adk` is available, the `_tool` decorator becomes a real ADK
FunctionTool. Otherwise these run as plain async functions for unit tests.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _tool(_fn=None, **_kwargs):
    def _wrap(fn):
        try:
            from google.adk.tools import FunctionTool  # type: ignore[import-untyped]
            return FunctionTool(fn)
        except ImportError:
            return fn
    if _fn is not None:
        return _wrap(_fn)
    return _wrap


@_tool
async def wire_emit(
    *,
    message: str,
    message_type: str = "thinking",
    confidence: float | None = None,
    story_unit_id: str | None = None,
    wire: Any = None,  # injected by the runtime
    investigation_id: str | None = None,
) -> str:
    """Emit a single Wire event (the in-process write-through proxy).

    The proxy invokes the NIL Redaction Layer in-process before persistence;
    do not bypass.

    Args:
        message: the displayed text. Will be NIL-scanned. NEVER name an
            individual Team USA athlete.
        message_type: 'thinking' | 'milestone' | 'intervention' | 'decision'.
        confidence: optional 0.0-1.0.
        story_unit_id: optional id of the place/program/pattern this is about.

    Returns:
        The Firestore doc id of the persisted Wire event.
    """
    if wire is None:
        raise RuntimeError("wire_emit: no `wire` instance was injected")
    event: dict = {
        "agent": "editor",
        "message": message,
        "message_type": message_type,
        "mode": "live",
    }
    if confidence is not None:
        event["confidence"] = confidence
    if story_unit_id is not None:
        event["story_unit_id"] = story_unit_id
    return await wire.emit(event, investigation_id=investigation_id)


@_tool
async def read_recent_published(
    *,
    limit: int = 10,
    firestore: Any = None,  # injected by the runtime
) -> list[dict]:
    """Return the N most-recent published stories (for Editor context).

    Day-2: stub returning []. Day-3 wires Firestore `story_drafts where
    publish_gate_decision='cleared' order by updated_at desc limit N`.
    """
    logger.info("read_recent_published stub called (limit=%d)", limit)
    return []


@_tool
async def read_queue(
    *,
    firestore: Any = None,  # injected by the runtime
) -> list[dict]:
    """Return the current in-flight queue: leads, investigations, drafts.

    Day-2: stub returning []. Day-3 wires Firestore queries against
    `lead_reports`, `investigation_packets`, `story_drafts`.
    """
    logger.info("read_queue stub called")
    return []


@_tool
async def dispatch_scout(
    *,
    scout_id: str,
    story_unit_id: str,
    scout_desk: Any = None,  # injected by the runtime
) -> dict:
    """Dispatch a sub-scout to investigate a place / program / pattern.

    Args:
        scout_id: 'cinderella' | 'comeback' | 'hometown' | 'echo'.
        story_unit_id: stable id (NEVER an athlete id).

    Returns:
        `{"dispatched": True, "scout": ..., "story_unit_id": ...}`.
    """
    if scout_desk is None:
        raise RuntimeError("dispatch_scout: no `scout_desk` instance was injected")
    logger.info("dispatch_scout: scout=%s story_unit_id=%s", scout_id, story_unit_id)
    # Day-3: scout_desk.run_pass([story_unit_id], ctx=...)
    return {
        "dispatched": True,
        "scout": scout_id,
        "story_unit_id": story_unit_id,
    }


@_tool
async def accept_equity_recommendation(
    *,
    recommendation_id: str,
    firestore: Any = None,  # injected by the runtime
) -> dict:
    """Apply a Paralympic Equity Editor feed-drift recommendation.

    Day-2: stub. Day-3+ writes the queue-priority change to Firestore and
    emits an Editor 'agreed' Wire event.
    """
    logger.info("accept_equity_recommendation: recommendation_id=%s", recommendation_id)
    return {"accepted": True, "recommendation_id": recommendation_id}
