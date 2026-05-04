"""Observability layer: structured Cloud Logging + OpenTelemetry traces.

Per BUILD_SPEC §16. Day-2 keeps the surface narrow:
  - log_agent_call(...) — one structured-JSON entry per agent call.
  - trace_span(...) / init_tracer() — OpenTelemetry context manager.

If the optional dependencies (google-cloud-logging, opentelemetry) aren't on
the host, the module degrades to stdlib `logging` + a no-op span. This keeps
unit tests runnable on dev machines without the full GCP stack installed.
"""

from __future__ import annotations

from agents.observability.logging import log_agent_call
from agents.observability.tracing import init_tracer, trace_span

__all__ = ["init_tracer", "log_agent_call", "trace_span"]
