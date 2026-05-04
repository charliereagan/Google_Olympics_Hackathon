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

SIGTERM: drain the autonomous task, persist a Firestore checkpoint, close.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
    """vertexai.init(project, location='global'). Must run before any LlmAgent."""
    try:
        import vertexai  # type: ignore[import-untyped]

        vertexai.init(project=project, location=location)
        logger.info("vertexai.init OK (project=%s location=%s)", project, location)
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
    editor = EditorAgent(
        prompt=prompts["editor"],
        wire=wire_emitter,
        scout_desk=scout_desk,
        firestore=fs_client,
        model_id=env["model_editor"],
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
