# Plan: Day-2 Agent-Runtime Skeleton (v1)

**Status:** APPROVED with HoE additions (see §HOE-REVIEW below) — ready for an implementation worker to execute.
**Drafted:** 2026-05-03 by a Plan-style worker agent
**Reviewed + amended:** 2026-05-03 by HoE Session 2

**Scope:** seven-agent skeleton on ADK Python 2.0 Beta + Cloud Run, with Wire-emit proxy, fail-closed NIL guard stub, autonomous Editor loop, ParallelAgent Scout Desk, HND detector, observability, and per-axis cost counters. Does NOT implement the full NIL Layer, Visualizer, Equity Editor body, Storyteller body, Narrator, Publish Gate sub-stages, or any frontend.

**Constitutional anchor:** Python decides WHETHER text reaches the user (the proxy + NIL stub + cost ceilings). Python does NOT decide WHAT a Scout investigates (that lives in `/prompts/*.md`). Every file in this plan is checked against that line.

---

## HOE-REVIEW (read first, supersedes any conflicting plan detail below)

The plan as drafted by the worker is sound. HoE adds these binding amendments:

1. **HOE-DEC-026 (this plan):** FastAPI is the ASGI framework. Single uvicorn process per Cloud Run instance. Lifespan-managed boot/shutdown. No Flask/aiohttp/raw-uvicorn alternatives.
2. **HOE-DEC-027 (this plan):** `ahocorasick_rs` (Rust-backed, ~5× faster than `pyahocorasick` per published benchmarks) is the primary pick for the Aho-Corasick automaton. Implementation worker falls back to `pyahocorasick` ONLY if `ahocorasick_rs` wheels are missing on the Cloud Run base image (`python:3.12-slim`). The fallback decision and its reason must be logged in `tech_snapshot.md`.
3. **Add env var `ATHLETE_REGISTRY_DATASET`** (default `storytellers_room`; dev override `storytellers_room_dev`) — the NIL Layer reads from this. Without it, the runtime defaults to production, which is wrong for local dev. (Amends §E.)
4. **Top-level `/requirements.txt`** (separate from `scripts/requirements.txt`) for the agent runtime deps. The two requirements files have intentionally non-overlapping concerns: scripts are operational tooling (google-auth, requests); the runtime is the actual production code (FastAPI, ADK, Vertex AI SDK, Firestore, BigQuery, Cloud Logging, OpenTelemetry, ahocorasick_rs).
5. **Manual handoff (not ADK auto-handoff)** is the right call to protect Voice Signatures (CONSTITUTION Law 2). Editor's tool-call decisions select the next agent; Python invokes that agent's Runner. The plan correctly identifies the trap and avoids it. Locked.
6. **ParallelAgent + Firestore-as-rendezvous** for the Scout Desk is the correct primary pattern. `asyncio.gather` is the documented fallback. Locked.

The HOE-DECs above will be appended to `Docs/Engineering/HOE-HANDOFF.md` Section 4 when the next commit lands.

The implementation worker should treat this entire document as the binding spec for the skeleton. If the worker discovers a conflict between this plan and BUILD_SPEC.md, BUILD_SPEC wins; flag the conflict for HoE before changing direction.

---

## A. File-by-file plan

### A.1 `/agents/runtime.py`  (~250 LOC)

**Purpose:** Container entry point. Boots all seven agents, starts Editor's autonomous task, exposes health endpoints. The `agent-runtime` Cloud Run service runs `python -m agents.runtime` (or `uvicorn agents.runtime:app --host 0.0.0.0 --port $PORT`).

**Public API (module level):**
- `app: fastapi.FastAPI` — the ASGI app Cloud Run serves.
- `async def lifespan(app)` — FastAPI lifespan context manager that runs the boot sequence and shuts down cleanly on SIGTERM.
- `class RuntimeState` (dataclass): `editor: EditorAgent`, `scout_desk: ScoutDesk`, `nil_layer: NilRedactionLayer`, `wire_emitter: WireEmitter`, `pacer_factory: Callable[[float], WirePacer]`, `cost_counter: CostCounter`, `firestore: AsyncClient`, `bigquery: bigquery.Client`, `boot_time: datetime`, `autonomous_task: asyncio.Task | None`.

**Key behaviors:**
- Boot sequence (in order, each step fatal on failure): (1) read env vars and validate (`GOOGLE_CLOUD_PROJECT == 'predictive-fx-495200-j4'`, `GOOGLE_CLOUD_LOCATION == 'global'`); (2) `vertexai.init(project, location='global')` — must NOT pass any region; (3) construct Firestore + BigQuery + Cloud Storage clients; (4) load `/prompts/*.md` into a dict keyed by stem; (5) load `/data/streaming_profiles.json`; (6) instantiate `NilRedactionLayer.bootstrap(bigquery_client, dataset=os.environ['ATHLETE_REGISTRY_DATASET'])` which queries `athlete_registry` and asserts ≥500 rows or raises `RegistryTooSmallError` → `sys.exit(1)`; (7) instantiate `WireEmitter(firestore, nil_layer)`; (8) construct seven ADK agents passing the wire emitter + tools (Editor, Scout Desk wrapping ParallelAgent of four sub-scouts, plus stubs for Investigator/Equity/Storyteller/Narrator/Publish Gate that just register tool surfaces — bodies land later); (9) start HND detector subscription; (10) `asyncio.create_task(editor.autonomous_loop())` and store handle on `RuntimeState`.
- Health endpoints (FastAPI routes): `GET /health/heartbeat` returns `{"ok": true, "boot_time": ..., "last_think_cycle": ...}` (used by Cloud Scheduler watchdog per HOE-DEC-022); `GET /health/nil` returns 503 if registry not loaded or row count <500, else 200 with `{registry_size, loaded_at, last_refresh}`; `GET /health/agents` returns per-agent `{idle | thinking | error, last_wire_emit_ts}`.
- Pause path: at the top of every think-cycle the autonomous loop checks `os.environ.get("AGENT_RUNTIME_PAUSED") == "1"` and skips dispatch (BUILD_SPEC §15.4).
- SIGTERM handler awaits `autonomous_task`, drains the in-flight investigations to a Firestore checkpoint doc (`/runtime_state/{instance_id}`), cancels HND subscription, closes Firestore.

**Dependencies:** A.2 emit; A.3 pacing; A.4 types; A.5 editor; A.6 scouts; A.7 hnd_detector; A.8 prompts loader; A.9 observability; A.10 cost counters; A.11 nil_redaction_layer_stub.

**ADK primitives:** none directly here; this is the host. ADK agents are constructed but their `Runner` is invoked from inside the Editor loop and the Scout Desk methods.

---

### A.2 `/agents/wire/emit.py` — the write-through proxy (~180 LOC)

**Purpose:** The single legitimate path for any agent to write a `wire_events` document. Implements HOE-DEC-018.

**Public API:**
```python
class WireEmitter:
    def __init__(self, firestore: AsyncClient, nil_layer: NilRedactionLayer, *, fail_closed: bool = True): ...
    async def emit(self, event: WireEvent, *, investigation_id: str | None = None) -> str: ...
    async def emit_handoff(self, src: AgentId, dst: AgentId, *, story_unit_id: str | None) -> str: ...
    @property
    def is_ready(self) -> bool: ...   # delegates to nil_layer.is_loaded
```

**Key behaviors:**
- `emit(event)` flow: (1) raise `WireProxyNotReadyError` if `nil_layer.is_loaded is False` — the `/health/nil` endpoint is what gates the SSE bridge, but the proxy itself fails closed for defense in depth; (2) call `nil_layer.scan_wire(event.message, surface='wire', context={story_unit_id})` synchronously — it returns a `WireScanResult(decision: 'pass'|'aggregate'|'redact', redacted_message: str, log: NilLog)`; (3) if `decision == 'redact'`, replace `event.message` with `redacted_message`; (4) attach `event.nil_redaction_log = log`; (5) write to Firestore `wire_events` collection (auto-id) with `mode`, `timestamp = now()` (real wall-clock per HOE-DEC-021), `compression_factor` from event; (6) emit one structured Cloud Logging entry (BUILD_SPEC §16.1 schema); (7) return doc id.
- Retry: 3× exponential backoff (1s/4s/16s) on Firestore write failure per BUILD_SPEC §17.3. On final failure, append to an in-memory ring buffer (deque, maxlen=100) and log ERROR; the next successful emit drains the buffer.
- NIL substitution NEVER happens after the Firestore write — the proxy mutates the dict in-process before `add()`, which is the entire point of the proxy vs an `onCreate` trigger.
- Fail-closed signal for the autonomous loop: if `nil_layer` raises during scan (e.g., automaton corrupted), the proxy DOES NOT write and re-raises. Editor's loop is responsible for not crashing the runtime — it logs and skips this think-cycle.
- The proxy is the only file in `/agents/` allowed to call `firestore.collection('wire_events')` per `scripts/lint_no_direct_wire_writes.py:_is_proxy_file`.
- Sharding hook (BUILD_SPEC §6.12): a single internal `_collection_path()` method returns `'wire_events'` today and can later return `f'sessions/{session_id}/wire_events'` without touching agents.

**Dependencies:** A.4 types; the NIL Layer stub at `/agents/publish_gate/nil_redaction_layer_stub.py`; observability A.9.

---

### A.3 `/agents/wire/pacing.py` — `WirePacer` (~80 LOC)

**Purpose:** Per-investigation `compression_factor` cadence (HOE-DEC-021, BUILD_SPEC §6.10).

**Public API:**
```python
class WirePacer:
    def __init__(self, compression_factor: float = 1.0, *, jitter: float = 0.0): ...
    @property
    def compression_factor(self) -> float: ...
    async def delay(self, target_seconds: float) -> None: ...
    async def jittered_delay(self, base_min: float, base_max: float) -> None: ...
```

**Key behaviors:**
- `delay(target)` computes `effective = target / compression_factor` (4× faster at 0.25; same at 1.0) and `await asyncio.sleep(effective)`.
- `jittered_delay(min, max)` picks a uniform random in `[min, max]` then divides by compression. Used by the Editor's 30–90s think-cycle (BUILD_SPEC §5.1).
- Validation: `compression_factor` clamped to `[0.05, 1.0]` to refuse hostile sub-millisecond values; raise on anything outside.
- Pure asyncio; no Firestore/network. Trivially unit-testable with `freezegun` + `asyncio.sleep` patch.
- Pacer is constructed per-investigation and passed down to Scouts/Investigator/Storyteller via the investigation context dict so the live URL CTA's `0.25` flows automatically.

**Dependencies:** none (stdlib only).

---

### A.4 `/agents/wire/types.py` (~120 LOC)

**Purpose:** Typed shapes shared by emit, pacing, agent bodies, and (eventually) the SSE bridge consumer.

**Public API (TypedDict + `Literal` to mirror BUILD_SPEC §6.2 verbatim):**
```python
AgentId = Literal['editor','scout_desk','investigator','equity_editor','storyteller','narrator','publish_gate']
SubAgentId = Literal['cinderella','comeback','hometown','echo']
MessageType = Literal['thinking','milestone','intervention','decision']
Mode = Literal['live','replay','published']

class NilRedactionLog(TypedDict, total=False):
    direct_matches_redacted: int
    aggregations_applied: int

class WireEvent(TypedDict, total=False):
    id: str            # set by Firestore on write; optional on emit input
    timestamp: str     # set by emitter
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
    visual_treatment: Literal['normal','highlighted','intervention']
    compression_factor: float
    nil_redaction_log: NilRedactionLog
```

Plus `LeadReport`, `InvestigationContext`, `StreamingProfile`, `WireScanResult`, `NilLog` dataclasses for cross-module use.

**Dependencies:** stdlib `typing` + `dataclasses`. No third-party imports — keeps the proxy importable in lint test fixtures.

---

### A.5 `/agents/editor/` (~400 LOC across `__init__.py`, `agent.py`, `loop.py`, `tools.py`)

**Purpose:** Editor agent + autonomous loop (HOE-DEC-022).

**Public API:**
```python
# agents/editor/agent.py
class EditorAgent:
    def __init__(self, *, prompt: str, wire: WireEmitter, scout_desk: ScoutDesk, firestore, model_id: str = 'gemini-3.1-pro-preview'): ...
    @property
    def llm(self) -> google.adk.agents.LlmAgent: ...
    async def think_once(self, ctx: InvestigationContext | None = None) -> EditorDecision: ...
    async def autonomous_loop(self, *, stop_event: asyncio.Event) -> None: ...
```

**Key behaviors:**
- Constructs `google.adk.agents.LlmAgent(name='editor', model='gemini-3.1-pro-preview', instruction=prompt, tools=[...])`. Tools registered: `wire_emit`, `read_recent_published`, `read_queue`, `dispatch_scout`, `accept_equity_recommendation` — each defined in `tools.py` as ADK `FunctionTool` decorated functions.
- `autonomous_loop` runs forever: `while not stop_event.is_set(): await pacer.jittered_delay(30, 90); await self.think_once()`. Each iteration constructs an `adk.Runner` for the Editor agent, invokes with a single user-message containing queue + recent-feed snapshot serialized as JSON, then parses tool calls. The Editor's prompt drives whether to dispatch Scouts, advance an investigation, or sleep — Python only executes the chosen tool.
- Pause check at top of loop: `if os.environ.get("AGENT_RUNTIME_PAUSED") == "1": continue` (BUILD_SPEC §15.4).
- On exception inside a think_cycle: log to `agent_errors`, emit a `wire.emit` thinking event (`"hold — model returned an error, retrying with shorter context"` per BUILD_SPEC §17.1), backoff per §17.1, do not crash the loop.
- `think_once(ctx)` is the same body callable synchronously for tests / for the `POST /api/investigate` path (Day-3 work). Accepts optional `InvestigationContext` so the live CTA's `compression_factor=0.25` flows in.
- Voice signature is enforced exclusively by `/prompts/editor.md`; the Python file contains zero voice text.

**ADK primitives used:** `LlmAgent`, `FunctionTool`, `Runner`. The Editor is the *root agent* in ADK's multi-agent hierarchy (BUILD_SPEC §3.6); Scouts/Investigator/etc. are constructed as separate `LlmAgent`s but are NOT registered as ADK sub-agents — handoffs are mediated by Editor's tool-call decisions, then Python invokes the next agent's `Runner`. **Reason: ADK's auto-handoff would let the Editor's prompt accidentally call another agent's persona inline; we want explicit Python control over which agent runs next so Voice Signatures (CONSTITUTION Law 2) are protected.**

**Dependencies:** A.2, A.3, A.4, A.6, A.8, A.9.

---

### A.6 `/agents/scouts/` (~500 LOC across `__init__.py`, `desk.py`, `cinderella.py`, `comeback.py`, `hometown.py`, `echo.py`, `tools.py`)

**Purpose:** ParallelAgent-wrapped Scout Desk (BUILD_SPEC §5.2).

**Public API:**
```python
class ScoutDesk:
    def __init__(self, *, prompts: dict[str, str], wire: WireEmitter, bigquery, firestore, hnd: HndDetector): ...
    async def run_pass(self, candidates: list[StoryUnitRef], *, ctx: InvestigationContext) -> list[LeadReport]: ...
    @property
    def parallel_agent(self) -> google.adk.agents.ParallelAgent: ...
```

**Key behaviors:**
- Each sub-scout is a `LlmAgent(name='cinderella', model='gemini-3-flash-preview', instruction=prompts['cinderella_scout'], tools=[grounded_search, query_candidates, wire_emit, write_lead_report])`. Voice is enforced by the prompt file; streaming-profile (cognition speed) is enforced at Wire-render time and consumed by the frontend via `/data/streaming_profiles.json` — Scouts don't need to know.
- `parallel_agent = ParallelAgent(name='scout_desk', sub_agents=[cinderella, comeback, hometown, echo])` per ADK docs.
- **Result aggregation: Firestore as the rendezvous.** Each sub-scout's `write_lead_report` tool persists to `/lead_reports/{id}`; `run_pass` returns by querying Firestore for reports created in this pass-window. Decoupled, retry-safe, and isolates us from any quirks in `ParallelAgent`'s result aggregation in ADK Python 2.0 Beta.
- Backup pattern if `ParallelAgent` fails empirically: replace with `await asyncio.gather(*[scout.run() for scout in [cinderella, comeback, hometown, echo]])` using per-scout `Runner`s. Identical latency, no API surprise.
- Each `write_lead_report` call is observed by the HND detector (A.7).

**Dependencies:** A.2, A.4, A.7, A.8.

---

### A.7 `/agents/scouts/hnd_detector.py` (~150 LOC)

**Purpose:** High Narrative Density milestone (HOE-DEC-023, BUILD_SPEC §5.2).

**Public API:**
```python
class HndDetector:
    def __init__(self, *, firestore: AsyncClient, wire: WireEmitter, window: timedelta = timedelta(minutes=10), threshold: int = 3, min_confidence: float = 0.7): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def _on_lead_report(self, change: firestore.DocumentChange) -> None: ...   # internal
```

**Key behaviors:**
- `start()` opens a server-side Firestore `on_snapshot` listener on `/lead_reports` filtered to `created_at >= now - window`. The listener handler is the standard Firestore Admin SDK callback (synchronous; we hop back into asyncio via `asyncio.run_coroutine_threadsafe`).
- For each new report, compute the rolling set of distinct scouts per `story_unit_id` over the trailing 10 minutes (in-memory dict `{story_unit_id: {scout: (confidence, ts)}}`, pruned on each callback). Threshold check: `len({s for s, (c, _) in scouts.items() if c >= 0.7}) >= 3`.
- On threshold crossing: emit a single `WireEvent(agent='scout_desk', message_type='milestone', message='High Narrative Density: {scouts} on the same place.', story_unit_id=...)` via `wire.emit()`. Also write a Firestore doc `/hnd_fires/{id}` for the dashboard. Debounce: don't refire for the same `story_unit_id` within the same window (track a `fired_until` timestamp per unit).
- Confidence threshold and window come from constructor args so unit tests can override.
- HND firing increments the cost counter under axis `meta` for visibility.
- Watchdog: if no callback received for >2× the longest expected inter-report gap, restart the listener (defensive against silent listener death). Log to `agent_errors`.

**Dependencies:** A.2, A.4, A.9. Pulls Firestore Admin SDK's `firestore_v1.AsyncClient` from runtime.

---

### A.8 `/prompts/` (markdown files, no Python)

Files (each ~80–150 lines): `editor.md`, `cinderella_scout.md`, `comeback_scout.md`, `hometown_scout.md`, `echo_scout.md`. Voice signatures from BUILD_SPEC §5.1 / §5.2 reproduced verbatim — no rephrasing. Each file ends with a "constraints" block restating the place-over-person rule and the forbidden-words list relevant to the agent (Echo Scout's prompt explicitly forbids named athletes per BUILD_SPEC §5.2 / PROJECT_BRIEF §5).

**Loader:** A small `agents/prompts.py` (~40 LOC) reads `/prompts/*.md` at runtime boot, returns a `dict[str, str]`. File-watcher hot-reload (BUILD_SPEC §18.1) is out of scope for Day 2 — add a backlog entry to wire `watchfiles` in Day 3.

**Constitutional check:** these are markdown; behavior changes require editing markdown only (CONSTITUTION Rule 1). No `if scout == 'echo':` branches in Python.

---

### A.9 `/agents/observability/` (~200 LOC across `logging.py`, `tracing.py`)

**Purpose:** Structured Cloud Logging + OpenTelemetry traces (BUILD_SPEC §16.1, §16.2).

**Public API:**
```python
# observability/logging.py
def log_agent_call(*, agent: AgentId, sub_agent: SubAgentId | None, story_unit_id: str | None, investigation_id: str, model: str | None, tool: str | None, latency_ms: int, input_tokens: int | None, output_tokens: int | None, compression_factor: float, outcome: Literal['success','error','skipped'], wire_event_id: str | None, error: str | None) -> None: ...

# observability/tracing.py
@contextmanager
def trace_span(name: str, *, investigation_id: str, attrs: dict | None = None) -> Iterator[Span]: ...
def init_tracer() -> None: ...
```

**Key behaviors:**
- `log_agent_call` writes a single structured-JSON entry via `google.cloud.logging.Client().logger('agent-runtime').log_struct(...)`. Schema matches BUILD_SPEC §16.1 verbatim. One entry per agent call.
- `init_tracer` wires OpenTelemetry → OTLP exporter → Cloud Trace per BUILD_SPEC §16.2. Trace ID = `investigation_id` (set via a `Resource` attribute or a custom `IdGenerator`).
- `trace_span` is the context manager every tool wrapper enters. Spans roll up into a single end-to-end trace per investigation.
- Every Wire emit, NIL scan, ADK Runner invocation, and BigQuery query is wrapped in a span.

**Dependencies:** `google-cloud-logging`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-gcp-trace`.

---

### A.10 `/agents/cost/counters.py` (~180 LOC)

**Purpose:** Per-axis daily call/token tracking + ceilings (BUILD_SPEC §15.3).

**Public API:**
```python
class CostCounter:
    def __init__(self, bigquery: bigquery.Client, *, project_id: str, dataset: str = 'storytellers_room', ceilings: dict[str, int] | None = None): ...
    async def increment(self, *, agent: AgentId, sub_agent: SubAgentId | None, axis: CostAxis, model: str | None, calls: int = 1, input_tokens: int = 0, output_tokens: int = 0, images: int = 0, audio_chars: int = 0, grounded_queries: int = 0) -> None: ...
    async def assert_under_ceiling(self, *, axis: CostAxis, agent: AgentId | None = None) -> None: ...   # raises CostCeilingExceeded
```

**Key behaviors:**
- Each tool wrapper calls `await counter.assert_under_ceiling(axis=...)` BEFORE the model invocation (per BUILD_SPEC §15.3 — "incremented before invocation; ceilings enforced in the tool wrapper"). On breach: raise `CostCeilingExceeded`; the calling agent catches and emits a Wire `thinking` event (*"daily cap on grounded search reached, switching to corpus-only"*) and backs off. The ceiling exception fails the call, not the runtime.
- Ceilings (defaults from BUILD_SPEC §15.3): per-Scout daily 5,000 grounded prompts; per-investigation Pro 200K tokens; Deep Research 10/day; Nano Banana Pro per-story regen 3 (this one is enforced inline at the Visualizer, not here); TTS 200K chars/day.
- Persistence: `agent_call_counters` BigQuery table per `data/bq_schemas/agent_call_counters.json`. Use a 60-second batched write (in-memory accumulator flushed by an async background task) — single-row upserts on every tool call would be wasteful and expensive. The in-memory state is what `assert_under_ceiling` checks; the table is the durable record.
- Crash recovery: on boot, query today's row sums to repopulate in-memory state. The runtime can lose at most 60s of counters.
- Kill switch: when the $300 budget alert flips `AGENT_RUNTIME_PAUSED=1`, the autonomous loop short-circuits at the top per A.5 — counters keep flushing.

**Dependencies:** `google-cloud-bigquery`, A.4.

---

### A.11 `/agents/publish_gate/nil_redaction_layer_stub.py` (~120 LOC) — placeholder

**Why it's in scope:** Day-2 needs a working Wire-level NIL guard. The full Layer (with near-id check, aggregation, return-to-Storyteller actions) lands Days 6–7. The stub at Day 2 implements just the direct-match-and-redact path — enough to make the proxy correctness-complete.

**Public API (matches what the real Layer will expose so Day-6/7 work is drop-in):**
```python
class NilRedactionLayer:
    @classmethod
    def bootstrap(cls, bq: bigquery.Client, *, dataset: str, min_rows: int = 500) -> 'NilRedactionLayer': ...
    @property
    def is_loaded(self) -> bool: ...
    @property
    def registry_size(self) -> int: ...
    def scan_wire(self, text: str, *, surface: Literal['wire'] = 'wire', context: dict | None = None) -> WireScanResult: ...
    async def refresh(self) -> None: ...
```

**Key behaviors (Day-2 stub level):**
- `bootstrap`: query `SELECT full_name, first_name, last_name, known_variants FROM {dataset}.athlete_registry`; flatten into a list of needles (Unicode-normalized via NFC + accent-fold). Assert `len(needles) >= 500` or raise `RegistryTooSmallError`. Build an `ahocorasick_rs.AhoCorasick` automaton (fall back to `pyahocorasick.Automaton` if the rs wheels aren't on the Cloud Run base image — see HOE-DEC-027).
- `scan_wire(text)`: NFC-normalize the input; iterate automaton matches; if any, return `WireScanResult(decision='redact', redacted_message=re.sub(needle_regex, '[redacted]', text), log=NilLog(direct_matches_redacted=N, aggregations_applied=0))`. If none, `decision='pass'`. The disambiguation pass and near-id check are NOT in this stub.
- `refresh()`: re-runs `bootstrap()` query; on success, atomic-swap the `Automaton`. On failure, keep the current automaton (HOE-DEC-019 — refresh failures preserve prior state). Scheduled by runtime.py as a 6-hour background task.
- `is_loaded` is `False` until bootstrap completes. The proxy refuses to write before that.

**Dependencies:** `google-cloud-bigquery`, `ahocorasick_rs` (primary; `pyahocorasick` fallback per HOE-DEC-027).

---

## B. Async / concurrency model

| Concern | Approach |
|---|---|
| Event loop | Single asyncio event loop per Cloud Run instance. FastAPI/`uvicorn` owns it. The autonomous task and HND detector live as tasks on the same loop. |
| Always-on loop | `asyncio.create_task(editor.autonomous_loop(stop_event))` started in FastAPI `lifespan`. `stop_event` is set on SIGTERM. Cloud Run's `--cpu-always-allocated` (BUILD_SPEC §3.7) keeps the task running between requests. |
| ParallelAgent vs `asyncio.gather` | Build with `ParallelAgent` per BUILD_SPEC §3.6 + §5.2. Read results via Firestore (each scout's `write_lead_report` is the rendezvous). If empirical Day-3 testing reveals `ParallelAgent` quirks in ADK 2.0 Beta, fall back to `asyncio.gather([scout.run() for scout in subscouts])` — identical for our purposes. |
| HND detector concurrency | Firestore `on_snapshot` callbacks fire on a Firestore-managed thread; we hop into the event loop via `asyncio.run_coroutine_threadsafe(self._handle(change), self._loop)`. Internal state (`_state: dict`) is protected with a single `asyncio.Lock` because HND callbacks AND Scout writes can both touch it. |
| SSE bridge coexistence | The SSE bridge lives in `/web/` (Next.js). The agent runtime exposes nothing to it directly except Firestore writes. **Recommended pattern:** the Next.js Route Handler at `/web/app/api/wire/stream/route.ts` opens its own Firestore Admin `onSnapshot` listener (HOE-DEC-024). Agent runtime does NOT need a Pub/Sub channel — Firestore's snapshot stream is the broadcast bus. *If* (Day 8 work) we discover ordering or fan-out issues, add a Pub/Sub `wire-events` topic the proxy publishes to and the SSE bridge subscribes to. Today: not needed. |
| Restart on container recycle | Cloud Run recycles instances on deploy or scale events. SIGTERM handler in `runtime.py` awaits the autonomous task with a 25s budget (Cloud Run gives 10s grace by default; we configure 30s via `--container-grace-period`). On boot, the new instance reads `/runtime_state/{instance_id}` if present and resumes any orphaned investigations; if not present it starts fresh. The Cloud Scheduler 5-min watchdog (HOE-DEC-022) catches dead-loop cases — if `/health/heartbeat`'s `last_think_cycle` is >7 minutes old, it forces a new revision. |

## C. ADK choices and unknowns

| Concern | Choice | Rationale |
|---|---|---|
| Editor | `LlmAgent` with `model='gemini-3.1-pro-preview'` and a tool surface for queue/scout-dispatch/wire-emit | BUILD_SPEC §5.1, HOE-DEC-016 |
| Sub-scouts | 4× `LlmAgent` with `model='gemini-3-flash-preview'` | BUILD_SPEC §3.1 (Flash for cost/latency on continuous polling) |
| Scout Desk | `ParallelAgent(sub_agents=[cinderella, comeback, hometown, echo])` | BUILD_SPEC §3.6 |
| Investigator / Equity / Storyteller / Narrator / Publish Gate | Constructed as `LlmAgent` shells in Day 2 (so the seven-cast is visible in `/health/agents`), but `think()` raises `NotImplementedError` — bodies in Day 3-7 | Out of scope per prompt |
| Tool registration | `google.adk.tools.FunctionTool` decorator with explicit `description` and `args_schema` (Pydantic). Each tool is a thin Python function that wraps a real impl | ADK convention; keeps tool docstrings as the LLM-facing spec |
| Agent state | **Hand-rolled Firestore writes for canonical state** (lead reports, investigation packets, wire events, audit logs — schemas already in BUILD_SPEC §8). ADK's session abstraction is used only for transient single-turn context within a Runner invocation | Avoids dual sources of truth; Firestore is the bus the SSE bridge reads anyway |
| Handoffs | NOT via ADK's auto-handoff. Editor's tool-call decision selects the next agent; Python invokes that agent's Runner | CONSTITUTION Law 2 — voice signatures sacred — but the Editor's prompt + tool surface is what picks the next move; Python just executes |
| Vertex AI init | `vertexai.init(project='predictive-fx-495200-j4', location='global')` exactly once at boot, before any ADK construction | HOE-DEC-015 |

**Open questions to resolve empirically (also in §G):**
1. Does ADK Python 2.0 Beta's `ParallelAgent` call sub-agents on the same asyncio loop or spawn threads? Affects how Firestore async clients behave in tools.
2. Does ADK's `LlmAgent` accept a pre-initialized Vertex AI client, or does it pick up `GOOGLE_CLOUD_LOCATION` from env? Need to confirm `location='global'` flows through ADK.
3. ADK tool schemas — Pydantic v1 or v2? Affects `args_schema` shape.
4. Whether ADK 2.0 Beta exposes a way to override the model client per-agent (we want different `model_id`s per agent — `pro` for Editor, `flash` for Scouts, `flash-lite` for Wire vocab fills).

## D. Wire-level NIL guard interface

**Pseudocode (≤5 lines, illustrative — not for cut-and-paste):**

```python
async def emit(self, event: WireEvent) -> str:
    if not self._nil.is_loaded: raise WireProxyNotReadyError
    scan = self._nil.scan_wire(event['message'], surface='wire', context=...)
    if scan.decision == 'redact': event['message'] = scan.redacted_message
    event['nil_redaction_log'] = scan.log; event['timestamp'] = utcnow_iso()
    return await self._firestore.collection(self._collection_path()).add(event)
```

**Aho-Corasick load location:** `runtime.py` step 6 of the boot sequence calls `NilRedactionLayer.bootstrap(bigquery, dataset=os.environ['ATHLETE_REGISTRY_DATASET'])`. The `Automaton` is held on `runtime_state.nil_layer._automaton`, refreshed every 6 hours by `asyncio.create_task(nil_layer._refresh_loop())`. Refresh failures preserve the prior automaton (HOE-DEC-019).

**Unloaded-automaton detection:** `NilRedactionLayer.is_loaded` returns `False` if `self._automaton is None`. `WireEmitter.emit` checks this first and raises `WireProxyNotReadyError`. The `/health/nil` endpoint reads the same property and returns 503 — the SSE bridge in `/web/` checks `/health/nil` before opening to clients (HOE-DEC-019 + BUILD_SPEC §23).

**Test fixtures the implementation worker should write:**
- `agents/wire/test_emit.py::test_emit_calls_nil_layer` — assert NIL is invoked synchronously before Firestore write (use a Firestore mock that records call order vs an NIL stub).
- `agents/wire/test_emit.py::test_emit_redacts_message_inline` — assert input `"Wilma Rudolph ran fast"` becomes `"[redacted] ran fast"` in the persisted event AND the `nil_redaction_log.direct_matches_redacted == 1`.
- `agents/wire/test_emit.py::test_emit_fails_closed_when_unloaded` — instantiate `WireEmitter` with a stub that returns `is_loaded=False`; assert `await emitter.emit(...)` raises `WireProxyNotReadyError` and Firestore is never called.
- `agents/wire/test_emit.py::test_emit_retries_on_firestore_failure` — Firestore stub raises twice then succeeds; assert 3 attempts, exponential backoff.
- `agents/publish_gate/test_nil_redaction_layer_stub.py::test_bootstrap_asserts_min_rows` — BigQuery stub returns 200 rows; assert `bootstrap` raises `RegistryTooSmallError`.
- `agents/publish_gate/test_nil_redaction_layer_stub.py::test_unicode_normalization` — needle "Pelé" matches input "Pele".
- Run `python scripts/lint_no_direct_wire_writes.py` against `/agents/` in CI; assert exit 0. The proxy file is whitelisted by the lint already.

## E. Configuration

**Env vars read at boot (validated in `runtime.py`):**

| Var | Default | Source |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | (required) | tech_snapshot §1 |
| `GOOGLE_CLOUD_LOCATION` | `global` (required, validated) | HOE-DEC-015 |
| `VERTEX_AI_LOCATION` | `global` | tech_snapshot §3.1 |
| `FIRESTORE_DATABASE` | `(default)` | tech_snapshot §6 |
| `BIGQUERY_DATASET` | `storytellers_room` | tech_snapshot §6 |
| `BIGQUERY_DATASET_DEV` | `storytellers_room_dev` | local dev only |
| `ATHLETE_REGISTRY_DATASET` | `storytellers_room` (override `storytellers_room_dev` for local) | HoE addition; controls which dataset NIL Layer reads from |
| `ATHLETE_REGISTRY_TABLE` | `athlete_registry` | BUILD_SPEC §8.2 |
| `ATHLETE_REGISTRY_MIN_ROWS` | `500` | HOE-DEC-019 |
| `COMPRESSION_FACTOR_DEFAULT` | `1.0` | HOE-DEC-021 |
| `EDITOR_THINK_CYCLE_MIN_SECONDS` | `30` | BUILD_SPEC §5.1 |
| `EDITOR_THINK_CYCLE_MAX_SECONDS` | `90` | BUILD_SPEC §5.1 |
| `AGENT_RUNTIME_PAUSED` | unset | BUILD_SPEC §15.4 kill switch |
| `MODEL_EDITOR` | `gemini-3.1-pro-preview` | tech_snapshot §3 |
| `MODEL_SCOUTS` | `gemini-3-flash-preview` | tech_snapshot §3 |
| `MODEL_FLASH_LITE` | `gemini-3.1-flash-lite-preview` | tech_snapshot §3 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (Cloud Run injects) | BUILD_SPEC §16.2 |
| `PORT` | `8080` | Cloud Run convention |

Boot fails (exit 1) if `GOOGLE_CLOUD_LOCATION != 'global'` (HOE-DEC-015) or any required var missing.

**Prompt loading:** `agents/prompts.py::load_prompts(repo_root: Path) -> dict[str, str]` walks `/prompts/*.md` once at boot.

**Streaming profile loading:** `runtime.py` reads `/data/streaming_profiles.json` once at boot into a dict and exposes it via `/health/agents` so the frontend can also fetch it. (Day-2 scope: load and validate the JSON; the per-agent values are committed separately by Day-3 EOD per BUILD_SPEC §6.11.)

## F. Test plan

**Unit tests** (pytest, run by `pytest -x` per BUILD_SPEC §18.2):

- `agents/wire/test_pacing.py`
  - `test_delay_uncompressed`: `compression_factor=1.0`, `delay(2.0)` sleeps ~2.0s.
  - `test_delay_compressed`: `compression_factor=0.25`, `delay(2.0)` sleeps ~0.5s.
  - `test_compression_clamps`: `compression_factor=0.0` raises; `compression_factor=2.0` raises.
  - `test_jittered_delay_within_bounds`: across 100 iterations, all delays fall in `[min/cf, max/cf]`.

- `agents/wire/test_emit.py` — see §D.

- `agents/scouts/test_hnd_detector.py`
  - `test_fires_on_three_of_four_above_threshold`: feed 3 reports for same `story_unit_id`, all `confidence=0.8`, all within 10 min → assert `wire.emit` called once with milestone.
  - `test_does_not_fire_on_two_of_four`: 2 reports → assert no emit.
  - `test_does_not_fire_on_low_confidence`: 4 reports all at `0.6` → assert no emit.
  - `test_window_expiry`: 2 reports at t=0, freezegun to t=11min, third report → assert no emit (older 2 expired).
  - `test_debounce_per_unit`: trigger HND, then 4 more reports at confidence 0.9 within window → assert only 1 emit.

- `agents/cost/test_counters.py`
  - `test_increment_below_ceiling_passes`.
  - `test_increment_at_ceiling_raises`.
  - `test_batched_flush_to_bigquery`: 10 increments, advance time 60s, assert one BigQuery write with summed values.
  - `test_recover_from_bigquery_on_boot`.

- `agents/publish_gate/test_nil_redaction_layer_stub.py` — see §D.

- `agents/editor/test_loop.py`
  - `test_loop_respects_pause_env`: with `AGENT_RUNTIME_PAUSED=1`, `think_once` is never called.
  - `test_loop_recovers_from_exception`: stub `think_once` raises once then succeeds; loop continues; one `agent_errors` row written.
  - `test_loop_exits_on_stop_event`.

**Integration test** — `tests/integration/test_editor_to_wire_e2e.py`
- Uses Firestore emulator (`gcloud emulators firestore start`).
- Boots a stripped runtime: real `WireEmitter`, real `NilRedactionLayer` stub (loaded from a 600-row test fixture CSV), real Editor with a mocked `Runner` that returns a deterministic `dispatch_scout(cinderella, story_unit_id='us-ia-mt-pleasant')` decision, real `cinderella` Scout with a mocked `Runner` that returns a `write_lead_report` tool-call.
- Asserts: ≥3 `wire_events` documents in Firestore, all containing `nil_redaction_log` field, none containing the test fixture's redacted name in `message`, all having `mode='live'` and `compression_factor=1.0`.

## G. Open questions / unknowns for the implementation worker

1. **ADK `ParallelAgent` result aggregation** — does it return a list of sub-agent outputs, or do we read from each sub-agent's session? Try both during Day-3 buildout; recommend Firestore-as-rendezvous regardless because it's the canonical store.
2. **Firestore Admin SDK in-process `onSnapshot`** — Python's `firestore_v1.AsyncClient` has `Query.stream()` for one-shot reads; the watch / on_snapshot capability lives on the sync client (`firestore_v1.Client.collection(...).on_snapshot(callback)`). Pattern: run the sync watcher on a thread, marshal callbacks to the asyncio loop via `asyncio.run_coroutine_threadsafe`. Verify on Day 2 that this doesn't wedge under Cloud Run's `cpu-always-allocated` model.
3. **Vertex AI init + ADK** — `vertexai.init(location='global')` is the supported call (tech_snapshot §3.1). Confirm empirically that ADK's `LlmAgent` honors this global init versus picking up a regional default from env or service-account metadata. If ADK forces a regional client, override via the `model_options=` or `client=` kwarg (whichever ADK 2.0 Beta exposes) and pass a `vertexai.generative_models.GenerativeModel` constructed against `location='global'`.
4. **Aho-Corasick library pick** — primary `ahocorasick_rs` per HOE-DEC-027; fallback `pyahocorasick` if Cloud Run base image (`python:3.12-slim`) lacks the rs wheel. Performance delta is in the noise compared to Firestore write latency anyway.
5. **ADK FunctionTool args schema** — Pydantic v1 vs v2 affects how `args_schema` is declared. Confirm in the ADK changelog before writing tools.
6. **OpenTelemetry trace ID** — using `investigation_id` directly as the trace ID requires either a custom `IdGenerator` (16 random bytes formatted as hex) or stuffing it into a `Resource` attribute. Cloud Trace prefers the latter; Day-3 implementation worker confirms.

## H. Order of implementation (topo-sorted)

The implementation worker writes files in this order; each step is independently testable with `pytest -x` before moving on.

1. **`/agents/wire/types.py`** — pure types, no deps. Test by `mypy --strict agents/wire/types.py`.
2. **`/agents/wire/pacing.py`** — pure asyncio. `pytest agents/wire/test_pacing.py`.
3. **`/agents/publish_gate/nil_redaction_layer_stub.py`** — needs BigQuery client; can be tested with a stubbed client returning a 600-row fixture. `pytest agents/publish_gate/`.
4. **`/agents/wire/emit.py`** — depends on 1+3. `pytest agents/wire/test_emit.py`.
5. **`/agents/observability/`** — logging + tracing. Test by emitting a log entry to a captured stream.
6. **`/agents/cost/counters.py`** — depends on BigQuery client. `pytest agents/cost/`.
7. **`/agents/prompts.py`** — file walker. Trivial test.
8. **`/prompts/*.md`** — content only; no code.
9. **`/agents/scouts/hnd_detector.py`** — depends on 4. `pytest agents/scouts/test_hnd_detector.py`.
10. **`/agents/scouts/`** sub-scouts + desk — depends on 4, 5, 6, 7, 8, 9. Skeleton with mocked `Runner` for tests.
11. **`/agents/editor/`** — depends on 4, 5, 6, 7, 8, 10. Skeleton + autonomous loop. `pytest agents/editor/`.
12. **`/agents/runtime.py`** — depends on everything above. Boot sequence + FastAPI app + lifespan. Smoke test with `uvicorn agents.runtime:app --port 8080` against the Firestore emulator.
13. **Integration test** `tests/integration/test_editor_to_wire_e2e.py` — runs against the emulator. Last because it exercises the full topology.
14. **Lint check** — `python scripts/lint_no_direct_wire_writes.py` exits 0 against the new `/agents/` tree. The proxy and test files are auto-skipped by the lint.

## I. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ADK 2.0 Beta API churn between Day 2 and Day 9 | Medium | Pin `google-adk` version in `requirements.txt`; vendor-lock through Day 11. Constructor calls are isolated to `agent.py` files — a single migration point. |
| `ParallelAgent` doesn't aggregate sub-agent outputs as expected | Medium | Use Firestore as the rendezvous (Scouts write `lead_reports`; ScoutDesk reads back). Fallback: `asyncio.gather` with per-scout Runners — identical for our purposes. |
| `vertexai.init(location='global')` regresses or ADK overrides it | Low | Day-1 hard gate `scripts/verify_models.py` already verifies all seven IDs respond on global. Re-run before Day-2 push. Add a runtime assertion: after `vertexai.init`, immediately make a `gemini-3.1-flash-lite-preview` ping and assert 200. |
| Athlete registry seeding incomplete by Day 2 (Day-1 outstanding task per HOE-HANDOFF) | Medium | The runtime's fail-closed exit IS the safety net. If <500 rows, runtime exits 1 → `/health/nil` 503 → SSE bridge refuses to open → no Wire events leak. Implementation worker proceeds with a 600-row test fixture for unit tests; production seeding is a separate Day-1 deliverable currently in flight. |
| Firestore emulator behavior diverges from production (e.g., `on_snapshot` semantics) | Medium | Integration test runs against emulator AND a `dev-` Cloud Run service before Day 8 freeze. Document any divergences in `tech_snapshot.md`. |
| Cloud Run instance recycle drops in-flight investigations | Low | SIGTERM handler checkpoints to `/runtime_state/{instance_id}`; new instance reads it on boot. Cloud Scheduler 5-min watchdog catches dead-loop edge cases. |
| `ahocorasick_rs` wheel missing on `python:3.12-slim` Cloud Run base | Low | Switch to `pyahocorasick` (manylinux wheels widely available). HOE-DEC-027 covers this. |
| HND detector misses a fire because the Firestore listener died silently | Medium | Wrap the listener in a watchdog: if no callback received for >2× the longest expected inter-report gap, restart the listener. Log to `agent_errors`. |
| Cost counters lose 60s of writes on instance crash | Low | Acceptable per BUILD_SPEC §15.3; ceilings have headroom. If demo nears a ceiling, investigate. |
| Editor's prompt accidentally tries to call a Scout's persona inline (CONSTITUTION Law 2 — voice signatures) | Medium | The prompt explicitly says "you do not write Scout-style messages; you dispatch Scouts via the dispatch_scout tool." Voice-blind test (BUILD_SPEC §14.1) catches this on Day 7. Manual handoff (not ADK auto-handoff) is the structural defense. |
| `wire.emit` becomes a hot serialization point under compressed-time bursts (4× cadence) | Low | Compressed bursts are 1 write/sec — well under Firestore's per-collection budget (BUILD_SPEC §6.12). Sub-collection sharding hook is in the proxy if Day-9 profiling shows hot-spotting. |
