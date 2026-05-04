"""Structured Cloud Logging for agent calls.

Schema mirrors BUILD_SPEC §16.1 verbatim. One entry per agent call. If
`google-cloud-logging` isn't on the host (dev machine, unit-test sandbox), we
fall back to stdlib `logging.info` with the structured payload so the schema
is still honored even when not exporting to Cloud Logging.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

from agents.wire.types import AgentId, SubAgentId

_logger = logging.getLogger("agent-runtime")
_cloud_logger: Any = None  # populated lazily on first call if available


def _get_cloud_logger() -> Any:
    """Return a google.cloud.logging Logger, or None if unavailable."""
    global _cloud_logger
    if _cloud_logger is not None:
        return _cloud_logger
    if os.environ.get("AGENT_RUNTIME_DISABLE_CLOUD_LOGGING") == "1":
        return None
    try:
        # Imported lazily so unit tests on machines without the dep still run.
        from google.cloud import logging as gcl  # type: ignore[import-untyped]

        client = gcl.Client()
        _cloud_logger = client.logger("agent-runtime")
        return _cloud_logger
    except Exception:  # pragma: no cover — opportunistic init
        return None


def log_agent_call(
    *,
    agent: AgentId,
    sub_agent: SubAgentId | None,
    story_unit_id: str | None,
    investigation_id: str,
    model: str | None,
    tool: str | None,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    compression_factor: float,
    outcome: Literal["success", "error", "skipped"],
    wire_event_id: str | None,
    error: str | None,
) -> None:
    """Write one structured-JSON log entry for an agent call.

    Schema is BUILD_SPEC §16.1 verbatim. Always emits — even on degraded
    Cloud Logging — so the in-process logs are still useful for debugging.
    """
    payload = {
        "ts": _utcnow_iso(),
        "agent": agent,
        "sub_agent": sub_agent,
        "story_unit_id": story_unit_id,
        "investigation_id": investigation_id,
        "model": model,
        "tool": tool,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "compression_factor": compression_factor,
        "outcome": outcome,
        "wire_event_id": wire_event_id,
        "error": error,
    }
    cl = _get_cloud_logger()
    if cl is not None:
        try:
            cl.log_struct(payload, severity="INFO" if outcome != "error" else "ERROR")
            return
        except Exception as e:  # pragma: no cover — degraded path
            _logger.warning("cloud logging emit failed: %s; falling back to stdlib", e)
    # Stdlib fallback — JSON-encoded so structured ingestion still works.
    severity = logging.INFO if outcome != "error" else logging.ERROR
    _logger.log(severity, "agent_call %s", json.dumps(payload, default=str))


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
