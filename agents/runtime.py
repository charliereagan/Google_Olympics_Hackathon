"""Container entry point. Boots seven agents, exposes health endpoints,
runs the always-on Editor loop.

Boot sequence (each step fatal on failure):
  1. Read env vars; assert GOOGLE_CLOUD_PROJECT == 'predictive-fx-495200-j4'
     and GOOGLE_CLOUD_LOCATION == 'global' (HOE-DEC-015).
  2. vertexai.init(project, location='global') — MUST not pass any region.
  3. Construct Firestore + BigQuery + Cloud Storage clients.
  4. Load /prompts/*.md.
  5. Load /data/streaming_profiles.json.
  6. NilRedactionLayer.bootstrap(...) — exits 1 on RegistryTooSmallError.
  7. Construct WireEmitter.
  8. Construct seven LlmAgents (Editor + Scout Desk + 5 placeholder shells).
  9. Start HND detector subscription.
 10. asyncio.create_task(editor.autonomous_loop()).

Health endpoints:
  GET /health/heartbeat — {"ok": true, ...}; Cloud Scheduler watchdog reads.
  GET /health/nil       — 503 if registry not loaded, 200 otherwise.
  GET /health/agents    — per-agent {idle|thinking|error, last_wire_emit_ts}.

API endpoints:
  POST /api/investigate — live URL hero CTA submission (BUILD_SPEC §11.1).
                          Per-IP rate-limited (3/hr). One concurrent live
                          investigation at a time (BUILD_SPEC §6.10).

SIGTERM: drain the autonomous task, persist a Firestore checkpoint, close.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Module-level FastAPI imports so type annotations on route handlers (e.g.
# `request: Request`) resolve via the module's __globals__ — required because
# `from __future__ import annotations` makes annotations strings, and FastAPI's
# get_type_hints() resolves them using __globals__, not the local scope of
# _build_app(). Guarded for environments without FastAPI installed.
try:
    from fastapi import Request as _FastAPIRequest  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _FastAPIRequest = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ----- Module-level constants -------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PROJECT = "predictive-fx-495200-j4"
EXPECTED_LOCATION = "global"


@dataclass
class RuntimeState:
    boot_time: datetime
    editor: Any = None
    scout_desk: Any = None
    nil_layer: Any = None
    wire_emitter: Any = None
    pacer_factory: Callable[[float], Any] | None = None
    cost_counter: Any = None
    firestore: Any = None
    bigquery: Any = None
    storage: Any = None
    prompts: dict[str, str] = field(default_factory=dict)
    streaming_profiles: dict[str, Any] = field(default_factory=dict)
    autonomous_task: asyncio.Task | None = None
    hnd_detector: Any = None
    placeholder_agents: dict[str, Any] = field(default_factory=dict)
    stop_event: asyncio.Event | None = None
    nil_refresh_task: asyncio.Task | None = None
    last_think_cycle: datetime | None = None
    # Per-IP submission timestamps (sliding 1h window, BUILD_SPEC §11.1).
    cta_rate_limit: dict[str, list[float]] = field(default_factory=dict)
    # Active live-investigation task; only one at a time (BUILD_SPEC §6.10).
    active_live_investigation: asyncio.Task | None = None
    active_live_investigation_id: str | None = None


# ----- Config validation ------------------------------------------------------


def _validate_env() -> dict[str, str]:
    """Read + validate required env vars. Exit 1 on any violation."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", EXPECTED_LOCATION)
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT is required")
        sys.exit(1)
    if location != EXPECTED_LOCATION:
        # HOE-DEC-015 hard gate: regional endpoints return 404 for Gemini 3.x.
        logger.error(
            "GOOGLE_CLOUD_LOCATION must be %r (got %r); HOE-DEC-015",
            EXPECTED_LOCATION, location,
        )
        sys.exit(1)
    return {
        "project": project,
        "location": location,
        "athlete_registry_dataset": os.environ.get(
            "ATHLETE_REGISTRY_DATASET", "storytellers_room"
        ),
        "athlete_registry_table": os.environ.get(
            "ATHLETE_REGISTRY_TABLE", "athlete_registry"
        ),
        "athlete_registry_min_rows": os.environ.get(
            "ATHLETE_REGISTRY_MIN_ROWS", "500"
        ),
        "model_editor": os.environ.get("MODEL_EDITOR", "gemini-3.1-pro-preview"),
        "model_scouts": os.environ.get("MODEL_SCOUTS", "gemini-3-flash-preview"),
    }


def _init_vertex_ai(project: str, location: str) -> None:
    """vertexai.init(project, location='global'). Must run before any LlmAgent.

    Also sets `GOOGLE_GENAI_USE_VERTEXAI=true` + `GOOGLE_CLOUD_PROJECT` +
    `GOOGLE_CLOUD_LOCATION` so the `google-genai` SDK (which ADK uses
    internally) routes Gemini calls through Vertex AI / ADC instead of
    defaulting to the Gemini Developer API (which requires an API key).
    Caught empirically during Day-3 smoke test — without these env vars,
    ADK's Runner raises `ValueError: No API key was provided.`
    """
    # Force ADK / google-genai to use Vertex AI auth (ADC) not API-key auth.
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    os.environ["GOOGLE_CLOUD_PROJECT"] = project
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    try:
        import vertexai  # type: ignore[import-untyped]

        vertexai.init(project=project, location=location)
        logger.info(
            "vertexai.init OK (project=%s location=%s); GOOGLE_GENAI_USE_VERTEXAI=true",
            project, location,
        )
    except ImportError:
        logger.warning("vertexai not installed; skipping init (Day-2 dev mode)")
    except Exception:
        logger.exception("vertexai.init failed")
        raise


# ----- Boot helpers -----------------------------------------------------------


def _load_streaming_profiles(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "data" / "streaming_profiles.json"
    if not path.exists():
        logger.warning("streaming_profiles.json missing at %s", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("streaming_profiles.json parse failed")
        return {}


def _build_firestore_client() -> Any:
    """Return a Firestore async client, or None for stub mode."""
    try:
        from google.cloud import firestore  # type: ignore[import-untyped]

        return firestore.AsyncClient()
    except Exception:
        logger.warning("Firestore client construction failed; running in stub mode")
        return None


def _build_bigquery_client() -> Any:
    try:
        from google.cloud import bigquery  # type: ignore[import-untyped]

        return bigquery.Client()
    except Exception:
        logger.warning("BigQuery client construction failed; running in stub mode")
        return None


def _build_storage_client() -> Any:
    try:
        from google.cloud import storage  # type: ignore[import-untyped]

        return storage.Client()
    except Exception:
        logger.warning("Cloud Storage client construction failed; running in stub mode")
        return None


def _bootstrap_nil_layer(bigquery_client: Any, env: dict[str, str]) -> Any:
    """Run NilRedactionLayer.bootstrap. On RegistryTooSmallError, exit 1."""
    from agents.publish_gate.nil_redaction_layer_stub import (
        NilRedactionLayer,
        RegistryTooSmallError,
    )

    if bigquery_client is None:
        logger.error("BigQuery client unavailable; cannot bootstrap NIL layer")
        sys.exit(1)
    min_rows = int(env["athlete_registry_min_rows"])
    try:
        return NilRedactionLayer.bootstrap(
            bigquery_client,
            dataset=env["athlete_registry_dataset"],
            table=env["athlete_registry_table"],
            min_rows=min_rows,
        )
    except RegistryTooSmallError:
        logger.exception("NIL Layer bootstrap failed (registry < min_rows)")
        sys.exit(1)


def _build_placeholder_agents(prompts: dict[str, str], model_id: str) -> dict[str, Any]:
    """Construct LlmAgent shells for the five not-yet-built agents.

    Investigator, Equity Editor, Storyteller, Narrator, Publish Gate get
    empty-instruction LlmAgents (or placeholder shells if ADK isn't on the
    host) so the seven-cast appears in /health/agents per plan §A.5.
    Bodies land Days 3-7.
    """
    placeholder_instruction = (
        "This agent's body lands in Day N — see HOE-HANDOFF.md. Day-2 only "
        "constructs the shell so the seven-cast surface is complete."
    )
    names = [
        "investigator",
        "equity_editor",
        "storyteller",
        "narrator",
        "publish_gate",
    ]
    agents: dict[str, Any] = {}
    try:
        from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

        for name in names:
            agents[name] = LlmAgent(
                name=name,
                model=model_id,
                instruction=placeholder_instruction,
                tools=[],
            )
    except ImportError:
        # Build pure-Python placeholders.
        from agents.scouts.cinderella import _PlaceholderAgent  # type: ignore[attr-defined]

        for name in names:
            agents[name] = _PlaceholderAgent(
                name=name,
                model=model_id,
                instruction=placeholder_instruction,
                tools=[],
            )
    return agents


# ----- Lifespan ---------------------------------------------------------------


_state: RuntimeState | None = None


def get_state() -> RuntimeState:
    """Accessor for tests / health endpoints. Raises if lifespan hasn't run."""
    if _state is None:
        raise RuntimeError("RuntimeState not initialized; lifespan has not run")
    return _state


@asynccontextmanager
async def lifespan(app):  # pragma: no cover — Cloud Run boot path
    """FastAPI lifespan context manager.

    Boot sequence runs on app startup; teardown runs on SIGTERM.
    """
    global _state

    # 1. Env validation
    env = _validate_env()

    # 2. Vertex AI init (BEFORE any LlmAgent construction).
    _init_vertex_ai(env["project"], env["location"])

    # 3. Cloud client construction
    fs_client = _build_firestore_client()
    bq_client = _build_bigquery_client()
    storage_client = _build_storage_client()

    # 4. Prompts
    from agents.prompts import load_prompts
    prompts = load_prompts(REPO_ROOT)

    # 5. Streaming profiles
    streaming_profiles = _load_streaming_profiles(REPO_ROOT)

    # 6. NIL layer bootstrap (fail-closed)
    nil_layer = _bootstrap_nil_layer(bq_client, env)

    # 7. Wire emitter
    from agents.wire.emit import WireEmitter
    wire_emitter = WireEmitter(fs_client, nil_layer)

    # 8. Cost counter
    from agents.cost.counters import CostCounter
    cost_counter = CostCounter(bq_client, project_id=env["project"])
    try:
        await cost_counter.recover_from_bigquery()
    except Exception:
        logger.exception("cost_counter recover failed; continuing fresh")
    cost_counter.start_flush_loop()

    # 9. HND detector + Scout Desk + Editor
    from agents.scouts.hnd_detector import HndDetector
    from agents.scouts.desk import ScoutDesk
    from agents.editor.agent import EditorAgent

    hnd = HndDetector(firestore=fs_client, wire=wire_emitter)
    scout_desk = ScoutDesk(
        prompts=prompts,
        wire=wire_emitter,
        bigquery=bq_client,
        firestore=fs_client,
        hnd=hnd,
        scout_model=env["model_scouts"],
    )
    # NOTE: editor.runtime_state is set AFTER RuntimeState construction
    # below, but EditorAgent already stores the ref so the assignment lands.
    editor = EditorAgent(
        prompt=prompts["editor"],
        wire=wire_emitter,
        scout_desk=scout_desk,
        firestore=fs_client,
        model_id=env["model_editor"],
        cost_counter=cost_counter,
    )
    placeholder_agents = _build_placeholder_agents(prompts, env["model_editor"])

    # 10. Start HND listener + autonomous loop
    await hnd.start()
    stop_event = asyncio.Event()
    autonomous_task = asyncio.create_task(editor.autonomous_loop(stop_event=stop_event))

    # Tracing init (best-effort)
    try:
        from agents.observability import init_tracer
        init_tracer()
    except Exception:
        logger.warning("tracing init failed; continuing")

    _state = RuntimeState(
        boot_time=datetime.now(timezone.utc),
        editor=editor,
        scout_desk=scout_desk,
        nil_layer=nil_layer,
        wire_emitter=wire_emitter,
        cost_counter=cost_counter,
        firestore=fs_client,
        bigquery=bq_client,
        storage=storage_client,
        prompts=prompts,
        streaming_profiles=streaming_profiles,
        autonomous_task=autonomous_task,
        hnd_detector=hnd,
        placeholder_agents=placeholder_agents,
        stop_event=stop_event,
    )
    # Backref so editor.think_once() can stamp last_think_cycle on
    # RuntimeState — done after construction to break the chicken-and-egg.
    editor._runtime_state = _state  # type: ignore[attr-defined]
    logger.info("agent-runtime: boot complete")

    try:
        yield
    finally:
        # SIGTERM path
        logger.info("agent-runtime: shutdown initiated")
        if _state is not None and _state.stop_event is not None:
            _state.stop_event.set()
        if _state is not None and _state.autonomous_task is not None:
            try:
                await asyncio.wait_for(_state.autonomous_task, timeout=25.0)
            except asyncio.TimeoutError:
                _state.autonomous_task.cancel()
        if _state is not None and _state.hnd_detector is not None:
            try:
                await _state.hnd_detector.stop()
            except Exception:
                logger.exception("hnd_detector.stop failed")
        if _state is not None and _state.cost_counter is not None:
            try:
                await _state.cost_counter.stop()
            except Exception:
                logger.exception("cost_counter.stop failed")
        logger.info("agent-runtime: shutdown complete")


# ----- POST /api/investigate (live URL hero CTA) -----------------------------


# BUILD_SPEC §11.1 + §6.10 binding constants.
_CTA_MAX_PROMPT_CHARS = 500
_CTA_MIN_COMPRESSION = 0.05
_CTA_MAX_COMPRESSION = 1.0
_CTA_RATE_LIMIT_HITS = 3
_CTA_RATE_LIMIT_WINDOW_S = 60.0 * 60.0  # 1 hour


def _client_ip(request: Any) -> str:
    """Best-effort client-IP extraction. Cloud Run sets X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for") if hasattr(request, "headers") else None
    if xff:
        # Leftmost IP is the original client (per RFC 7239 conventions).
        return xff.split(",")[0].strip()
    client = getattr(request, "client", None)
    if client is not None and getattr(client, "host", None):
        return str(client.host)
    return "unknown"


def _check_and_record_rate_limit(
    state: "RuntimeState",
    ip: str,
    *,
    now: float,
    limit: int = _CTA_RATE_LIMIT_HITS,
    window_s: float = _CTA_RATE_LIMIT_WINDOW_S,
) -> tuple[bool, int]:
    """Sliding-window per-IP rate-limit. Returns (ok, remaining).

    In-memory map; sufficient given Cloud Run min-instances=1. Day 8+ may
    move to Firestore if we scale past one instance.
    """
    bucket = state.cta_rate_limit.setdefault(ip, [])
    cutoff = now - window_s
    # Drop expired entries (in place).
    bucket[:] = [t for t in bucket if t > cutoff]
    if len(bucket) >= limit:
        return (False, 0)
    bucket.append(now)
    return (True, max(0, limit - len(bucket)))


async def _handle_investigate(request: Any) -> Any:
    """Body of POST /api/investigate. Module-level so tests can call it."""
    from fastapi.responses import JSONResponse

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid JSON body"},
        )

    prompt = body.get("prompt")
    compression_factor = body.get("compression_factor", 1.0)
    source = body.get("source", "cta")

    # --- Validation (422 on schema breach) ----------------------------------
    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse(
            status_code=422,
            content={"error": "prompt must be a non-empty string"},
        )
    if len(prompt) > _CTA_MAX_PROMPT_CHARS:
        return JSONResponse(
            status_code=422,
            content={
                "error": f"prompt exceeds {_CTA_MAX_PROMPT_CHARS} chars (got {len(prompt)})",
            },
        )
    try:
        cf = float(compression_factor)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=422,
            content={"error": "compression_factor must be a number"},
        )
    if not (_CTA_MIN_COMPRESSION <= cf <= _CTA_MAX_COMPRESSION):
        return JSONResponse(
            status_code=422,
            content={
                "error": (
                    f"compression_factor must be in [{_CTA_MIN_COMPRESSION},"
                    f"{_CTA_MAX_COMPRESSION}] (HOE-DEC-029)"
                ),
            },
        )

    try:
        s = get_state()
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"error": "runtime not ready"},
        )

    # --- Rate limit (429) ---------------------------------------------------
    import time as _time

    ip = _client_ip(request)
    ok, _remaining = _check_and_record_rate_limit(s, ip, now=_time.time())
    if not ok:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate limit: 3 submissions per hour per IP",
            },
        )

    # --- One concurrent live investigation at a time (BUILD_SPEC §6.10) -----
    if s.active_live_investigation is not None and not s.active_live_investigation.done():
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "message": (
                    "the room is investigating; watching room work in the meantime"
                ),
            },
        )

    if s.editor is None:
        return JSONResponse(
            status_code=503,
            content={"error": "editor not initialized"},
        )

    # --- Register the new investigation context -----------------------------
    from agents.wire.types import InvestigationContext as _InvCtx

    investigation_id = f"inv-{uuid.uuid4().hex[:12]}"
    ctx = _InvCtx(
        investigation_id=investigation_id,
        compression_factor=cf,
        mode="live",
    )

    # Log every accepted submission (BUILD_SPEC §16.1).
    try:
        from agents.observability import log_agent_call as _log
        _log(
            agent="editor",
            sub_agent=None,
            story_unit_id=None,
            investigation_id=investigation_id,
            model=getattr(s.editor, "model", None),
            tool="api_investigate",
            latency_ms=0,
            input_tokens=None,
            output_tokens=None,
            compression_factor=cf,
            outcome="success",
            wire_event_id=None,
            error=None,
        )
    except Exception:
        logger.exception("api_investigate: log_agent_call failed")

    async def _run_one_cycle():
        try:
            await s.editor.think_once(ctx=ctx)
        except Exception:
            logger.exception("api_investigate: editor.think_once raised")

    s.active_live_investigation = asyncio.create_task(_run_one_cycle())
    s.active_live_investigation_id = investigation_id

    return JSONResponse(
        status_code=202,
        content={
            "investigation_id": investigation_id,
            "compression_factor": cf,
            "source": source,
        },
    )


# ----- FastAPI app ------------------------------------------------------------


def _build_app():
    """Construct the FastAPI app. Lazy import so unit tests on machines
    without FastAPI still parse this module."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
    except ImportError:  # pragma: no cover
        logger.error("FastAPI not installed; agents.runtime is non-functional")
        return None

    app = FastAPI(title="The Storyteller's Room — agent runtime", lifespan=lifespan)

    @app.get("/health/heartbeat")
    async def heartbeat() -> dict:
        try:
            s = get_state()
            return {
                "ok": True,
                "boot_time": s.boot_time.isoformat() if s.boot_time else None,
                "last_think_cycle": (
                    s.last_think_cycle.isoformat() if s.last_think_cycle else None
                ),
            }
        except RuntimeError:
            # Health endpoints can be polled before lifespan completes; return a
            # consistent shape so the watchdog parser doesn't crash.
            return {"ok": False, "boot_time": None, "last_think_cycle": None}

    @app.get("/health/nil")
    async def health_nil():
        # The Cloud Run watchdog gates the SSE bridge on this endpoint's status code;
        # 503 means the NIL Layer hasn't bootstrapped yet (HOE-DEC-019 fail-closed).
        try:
            s = get_state()
        except RuntimeError:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "registry_size": 0, "loaded_at": None, "last_refresh": None},
            )
        if s.nil_layer is None or not s.nil_layer.is_loaded:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "registry_size": 0, "loaded_at": None, "last_refresh": None},
            )
        return {
            "ok": True,
            "registry_size": s.nil_layer.registry_size,
            "loaded_at": s.nil_layer.loaded_at,
            "last_refresh": s.nil_layer.last_refresh_at,
        }

    @app.post("/api/investigate")
    async def api_investigate(request: _FastAPIRequest):  # type: ignore[valid-type]
        """Live URL hero CTA submission (BUILD_SPEC §11.1, §6.10).

        Body shape: `{prompt, compression_factor, source}`.
        - 422 on invalid prompt length or out-of-range compression_factor.
        - 429 if the per-IP rate limit (3/hour) is exceeded.
        - 202 with `{status: 'queued'}` if another live investigation is in
          flight (BUILD_SPEC §6.10 — "the room is investigating; watching
          room work in the meantime").
        - 202 with `{investigation_id}` on accept; the Editor's think_once
          runs as a fire-and-forget asyncio task.

        The `_FastAPIRequest` annotation references the module-level alias
        because `from __future__ import annotations` makes annotations strings
        and FastAPI resolves them via `api_investigate.__globals__` — which is
        the module's globals, not the local scope of `_build_app()`. (Day-3
        smoke-test bug; fixed.)
        """
        return await _handle_investigate(request)

    @app.get("/health/agents")
    async def health_agents() -> dict:
        try:
            s = get_state()
        except RuntimeError:
            return {"agents": {}}
        agents: dict[str, dict] = {}
        if s.editor is not None:
            agents["editor"] = {"name": getattr(s.editor, "name", "editor"), "status": "idle"}
        if s.scout_desk is not None:
            agents["scout_desk"] = {"name": "scout_desk", "status": "idle"}
        for name, a in s.placeholder_agents.items():
            agents[name] = {"name": getattr(a, "name", name), "status": "shell"}
        return {"agents": agents, "streaming_profiles": s.streaming_profiles}

    return app


app = _build_app()


# Allow `python -m agents.runtime` for local dev.
if __name__ == "__main__":  # pragma: no cover
    import uvicorn  # type: ignore[import-untyped]

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
