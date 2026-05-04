"""OpenTelemetry → Cloud Trace integration (BUILD_SPEC §16.2).

Day-2 surface:
  - init_tracer() — wires OTLP/Cloud Trace exporter at boot.
  - trace_span(name, investigation_id=, attrs=) — context manager every tool
    wrapper enters. One trace per investigation; spans roll up.

Degrades gracefully: if `opentelemetry` isn't installed (unit-test machines),
`trace_span` returns a no-op context manager that still yields a placeholder
object so callers can `__enter__` without conditional logic.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_initialized = False


def init_tracer() -> None:
    """Wire the OTLP exporter to Cloud Trace.

    Idempotent. Failures degrade to a no-op tracer — production runtime logs
    a warning so the operator notices.
    """
    global _initialized
    if _initialized:
        return
    if os.environ.get("AGENT_RUNTIME_DISABLE_TRACING") == "1":
        logger.info("tracing: disabled via AGENT_RUNTIME_DISABLE_TRACING=1")
        _initialized = True
        return
    try:
        from opentelemetry import trace  # type: ignore[import-untyped]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-untyped]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-untyped]
            BatchSpanProcessor,
        )

        provider = TracerProvider()
        try:
            from opentelemetry.exporter.cloud_trace import (  # type: ignore[import-untyped]
                CloudTraceSpanExporter,
            )
            exporter = CloudTraceSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("tracing: Cloud Trace exporter wired")
        except Exception as e:
            logger.warning("tracing: Cloud Trace exporter unavailable (%s); spans local-only", e)
        trace.set_tracer_provider(provider)
        _initialized = True
    except ImportError:
        logger.warning(
            "tracing: opentelemetry not installed; trace_span() will be a no-op"
        )
        _initialized = True


@contextlib.contextmanager
def trace_span(
    name: str,
    *,
    investigation_id: str | None = None,
    attrs: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Context manager that opens a span if OTel is available, else no-op."""
    try:
        from opentelemetry import trace  # type: ignore[import-untyped]

        tracer = trace.get_tracer("agent-runtime")
        span_attrs: dict[str, Any] = {}
        if investigation_id is not None:
            span_attrs["investigation_id"] = investigation_id
        if attrs:
            span_attrs.update(attrs)
        with tracer.start_as_current_span(name, attributes=span_attrs) as span:
            yield span
    except ImportError:
        # No-op span: yields a sentinel so callers don't crash on attr access.
        yield _NoopSpan()


class _NoopSpan:
    def set_attribute(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None

    def add_event(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None

    def record_exception(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None
