# tech_snapshot.md — Ground truth for the runtime environment

**Last refreshed:** 2026-05-05 by HoE Session 2 (Day-7 close-out: Visualizer + full NIL Layer + e2e smoke harness shipped. **Backend complete.** All 7 cast members idle; all 7 Publish Gate sub-stages real (no stubs). 293 unit tests + 1 skipped. Next: Day-8 frontend work, gated on design-approach checkpoint.)

This file is the **runtime ground truth**: what's actually provisioned, what model IDs respond, what voices exist, what env vars are set. Refresh this on **every infra change**. Distinct from:
- `BUILD_SPEC.md` = the plan (architecture, rules, schemas)
- `HOE-HANDOFF.md` = the running session log (decisions, work, lessons)
- `DEPLOYMENT.md` = the procedure (commands and flags to deploy)
- **This file** = "what's actually true on this machine right now"

A fresh coding agent landing on this repo cold should read this first to know what's real and what's still target-state.

---

## 1. GCP project

| Item | Value | Verified |
|---|---|---|
| Project ID | `predictive-fx-495200-j4` | ✓ |
| Project name | `Google-Olympics-Hackathon` | ✓ |
| Project number | `615585524733` | ✓ |
| Lifecycle state | `ACTIVE` | ✓ |
| Billing account | `billingAccounts/01933A-29A38C-94AD56` | ✓ (linked + enabled) |
| Active gcloud account (local) | `charlie@battlecards.pro` | ✓ |
| ADC quota project | `predictive-fx-495200-j4` | ✓ (set via `gcloud auth application-default set-quota-project`) |

## 2. APIs enabled (verified `gcloud services list --enabled` 2026-05-02)

```
aiplatform.googleapis.com         ✓ Vertex AI (all Gemini calls)
analyticshub.googleapis.com       ✓ (BigQuery family)
artifactregistry.googleapis.com   ✓ Container images for Cloud Run
bigquery.googleapis.com           ✓ + bigqueryconnection, bigquerydatapolicy,
                                       bigquerydatatransfer, bigquerymigration,
                                       bigqueryreservation, bigquerystorage
cloudapis.googleapis.com          ✓
cloudbuild.googleapis.com         ✓ CI/CD
cloudscheduler.googleapis.com     ✓ Always-on watchdog
cloudtrace.googleapis.com         ✓ Distributed tracing
dataform.googleapis.com           ✓ (BigQuery family)
dataplex.googleapis.com           ✓
datastore.googleapis.com          ✓ (Firestore family)
firestore.googleapis.com          ✓ Real-time agent state, Wire events
logging.googleapis.com            ✓ Structured logs
monitoring.googleapis.com         ✓ Golden-path dashboard
run.googleapis.com                ✓ Both services host
secretmanager.googleapis.com      ✓ API keys storage
servicemanagement.googleapis.com  ✓
serviceusage.googleapis.com       ✓
sql-component.googleapis.com      ✓
storage-api.googleapis.com        ✓
storage-component.googleapis.com  ✓
storage.googleapis.com            ✓ Cloud Storage (images, audio, fallback heroes)
telemetry.googleapis.com          ✓
texttospeech.googleapis.com       ✓ Cloud TTS catalog (for voice list)
```

## 3. Vertex AI — verified model fleet (probes from 2026-05-02)

All models reached on `location='global'`. Probe pattern: `POST https://aiplatform.googleapis.com/{version}/projects/predictive-fx-495200-j4/locations/global/publishers/google/models/{MODEL}:generateContent` with auth from `gcloud auth application-default print-access-token`.

| Model ID | API version | Verb / config | HTTP | Verified |
|---|---|---|---|---|
| `gemini-3.1-pro-preview` | `v1` | `:generateContent` | 200 | ✓ Reasoning thinking on by default |
| `gemini-3-flash-preview` | `v1beta1` | `:generateContent` | 200 | ✓ |
| `gemini-3.1-flash-lite-preview` | `v1beta1` | `:generateContent` | 200 | ✓ |
| `gemini-3-pro-image-preview` (Nano Banana Pro) | `v1beta1` | `:generateContent` + `generationConfig.responseModalities: ["IMAGE"]` | 200 | ✓ Returned a real PNG (`inlineData.mimeType: image/png`) |
| `gemini-3.1-flash-image-preview` (utility image gen) | `v1beta1` | `:generateContent` + `generationConfig.responseModalities: ["IMAGE"]` | 200 | ✓ |
| `gemini-3.1-flash-tts-preview` | `v1beta1` | `:generateContent` + `generationConfig.responseModalities: ["AUDIO"]` + `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName: "Charon"` | 200 | ✓ Returned 24kHz PCM audio (`audio/l16; rate=24000; channels=1`) |

**Critical operational notes:**
- All models global-endpoint only. `us-central1` returns **404 model-not-found**. (Source: Verdent guide + multiple GitHub issues across `gemini-cli` and `goose` projects.)
- `gemini-3-pro-preview` was discontinued **2026-03-26**; do not use. (Source: Vertex AI release notes.)
- Pro is on `v1`; the rest are on `v1beta1` for now.
- TTS via Vertex AI uses the **bare voice name** (`"Charon"`); the Cloud TTS API uses the FQN (`"en-US-Chirp3-HD-Charon"`).
- Reasoning is enabled by default on Pro 3.1 (the empty-content + `MAX_TOKENS` finish reason at `maxOutputTokens=8` indicates thought-token consumption).

### 3.1 SDK initialization

```python
import os, vertexai
# REQUIRED: tells google-genai (which ADK uses internally) to route via Vertex AI
# instead of the Gemini Developer API key path. HOE-DEC-030. Without this,
# ADK Runner calls fail with "No API key was provided." even after vertexai.init.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
vertexai.init(project="predictive-fx-495200-j4", location="global")
```

```bash
# environment
export GOOGLE_CLOUD_PROJECT=predictive-fx-495200-j4
export GOOGLE_CLOUD_LOCATION=global
export VERTEX_AI_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=true   # HOE-DEC-030 (REQUIRED for ADK + Vertex AI)
```

## 4. Gemini 3.1 Flash TTS — voice catalog + pinned picks

**Pinned (HOE-DEC-025, 2026-05-03):**
- **Broadcast Narrator → `Algenib`** (Cloud TTS FQN: `en-US-Chirp3-HD-Algenib`) — warm, mid-tone, documentary register
- **Wire Dispatcher → `Fenrir`** (Cloud TTS FQN: `en-US-Chirp3-HD-Fenrir`) — clipped, lower register, control-room
- **Single-voice fallback → `Fenrir`** (any future context where only one voice is used)

Vertex AI invocation form uses the bare voice name (`"Algenib"`, `"Fenrir"`); Cloud TTS standalone API uses the FQN.

Verified via `https://texttospeech.googleapis.com/v1/voices` (2026-05-02). 2,066 total voices in Cloud TTS. The 30 Gemini Chirp3 HD en-US voices (the ones we'd use for both Broadcast Narrator and Wire Dispatcher):

```
en-US-Chirp3-HD-Achernar
en-US-Chirp3-HD-Achird
en-US-Chirp3-HD-Algenib         ← PINNED for Broadcast Narrator (HOE-DEC-025)
en-US-Chirp3-HD-Algieba
en-US-Chirp3-HD-Alnilam
en-US-Chirp3-HD-Aoede
en-US-Chirp3-HD-Autonoe
en-US-Chirp3-HD-Callirrhoe
en-US-Chirp3-HD-Charon         ← v1.2 placeholder, auditioned, not selected
en-US-Chirp3-HD-Despina
en-US-Chirp3-HD-Enceladus
en-US-Chirp3-HD-Erinome
en-US-Chirp3-HD-Fenrir          ← PINNED for Wire Dispatcher + single-voice fallback (HOE-DEC-025)
en-US-Chirp3-HD-Gacrux
en-US-Chirp3-HD-Iapetus
en-US-Chirp3-HD-Kore
en-US-Chirp3-HD-Laomedeia
en-US-Chirp3-HD-Leda
en-US-Chirp3-HD-Orus
en-US-Chirp3-HD-Puck           ← v1.2 placeholder, auditioned, not selected
en-US-Chirp3-HD-Pulcherrima
en-US-Chirp3-HD-Rasalgethi
en-US-Chirp3-HD-Sadachbia
en-US-Chirp3-HD-Sadaltager
en-US-Chirp3-HD-Schedar
en-US-Chirp3-HD-Sulafat
en-US-Chirp3-HD-Umbriel
en-US-Chirp3-HD-Vindemiatrix
en-US-Chirp3-HD-Zephyr
en-US-Chirp3-HD-Zubenelgenubi
```

Day-1 audition completed 2026-05-03. Six candidates auditioned (Charon, Algenib, Iapetus, Puck, Fenrir, Orus) → Algenib + Fenrir picked (HOE-DEC-025).

**Vertex AI invocation form** (use bare name):
```json
{
  "speechConfig": {
    "voiceConfig": { "prebuiltVoiceConfig": { "voiceName": "Algenib" } }
  }
}
```

## 5. Inline TTS controls (verified per Google blog docs)

Gemini 3.1 Flash TTS supports inline tags within the prompt text:

| Tag family | Examples |
|---|---|
| Pace | `[slow]`, `[fast]` |
| Pause | `[short pause]`, `[long pause]`, `[pause=1.0]` |
| Emphasis | `[emphasis]` |
| Affect | `[cheerful]` (and ~200 others for expressive control) |

Output is watermarked with **SynthID** automatically.

## 6. Data services state (verified 2026-05-03)

| Service | State | Notes |
|---|---|---|
| Firestore | ✓ `(default)` database in `nam5` (US multi-region), `FIRESTORE_NATIVE`, `REALTIME_UPDATES_MODE_ENABLED` | Created 2026-05-03 |
| BigQuery datasets | ✓ `storytellers_room` (production) + `storytellers_room_dev` (local dev mirror) — both in `US` multi-region | Created 2026-05-03 |
| BigQuery tables (×7 each, 14 total) | ✓ `candidates`, `athlete_registry`, `historical_athletes`, `geography`, `championships`, `agent_call_counters`, `agent_errors` | Schemas in `data/bq_schemas/*.json` (committed). **`athlete_registry` seeded 2026-05-03: 11,188 rows in production (`storytellers_room`), 11,188 rows in dev (`storytellers_room_dev`).** Source: KeithGalli/Olympics-Dataset (Olympedia public CSVs filtered NOC=USA) + Wikidata SPARQL (12 Olympic + 19 Paralympic medalist cross-reference). Loader at `data/load_athlete_registry/`. |
| Cloud Storage buckets | ✓ `gs://storytellers-room-hero-images`, `gs://storytellers-room-audio`, `gs://storytellers-room-fallback-heroes` (US multi-region, uniform bucket-level access) | Created 2026-05-03; all empty |
| Artifact Registry | ✓ `storytellers-room` (Docker, `us-central1`) | Created 2026-05-03 for Cloud Run image storage |
| Cloud Run | **Empty** — no services yet | Pending: deploy `agent-runtime` + `web`. The runtime is locally-runnable as of 2026-05-04 — `uvicorn agents.runtime:app` boots cleanly against live Vertex AI + BigQuery with all 7 cast members constructed and `/health/nil` returning `registry_size: 11188`. |
| Agent runtime locally verified | ✓ uvicorn boots; `/health/heartbeat` 200; `/health/nil` 200 with registry_size 11188; `/health/agents` lists all 7 + 11 streaming profiles | 2026-05-04 |
| Aho-Corasick backend in production | `ahocorasick_rs 1.0.3` (HOE-DEC-027 primary) — wheels installed cleanly; `pyahocorasick` fallback NOT needed | 2026-05-04 verification |
| Async on_snapshot known gap | `firestore_v1.AsyncCollectionReference.on_snapshot` raises `NotImplementedError`; HND detector falls back to stub mode (logged) | Day-3/4 fix per plan §G open question 2 — sync watcher on a thread + `asyncio.run_coroutine_threadsafe`. Still pending. |
| Firestore composite index | `wire_events: (mode ASC, timestamp DESC, __name__ ASC)` — name `CICAgOjXh4EK`, state **READY** (built 2026-05-04). Required by Editor's `_read_recent_published` query. | Editor query now runs natively without falling through to the exception handler. |
| Editor `think_once` end-to-end verified | ✓ Live ADK Runner against `gemini-3.1-pro-preview` on `vertexai.init(location='global')` + `GOOGLE_GENAI_USE_VERTEXAI=true`; `last_think_cycle` populated; tool calls auto-executed by Runner | 2026-05-04 |
| `POST /api/investigate` end-to-end verified | ✓ HTTP 202 with `investigation_id` on accept; 422 on validation errors (prompt length, compression bounds); 429 on rate limit (3/hr/IP); 202 with `{status: queued}` when another investigation is in flight | 2026-05-04 |
| **Editor → Scout → wire.emit cycle verified live** | ✓ Single POST → Editor's `gemini-3.1-pro-preview` think → `dispatch_scout` tool call → Scout `gemini-3-flash-preview` Runner → `write_lead_report` tool persists to Firestore `lead_reports` → next Editor cycle sees them in the queue and emits decision Wire events. Two Lead Reports observed (Cinderella + Hometown on different programs); NIL Redaction Layer redacted athlete-name matches in Wire messages before persistence. | 2026-05-04 |
| Wire vocabulary library | ✓ `data/wire_vocabulary.json` — **558 fragments across 10 agent buckets** (Editor 74, Cinderella 55, Comeback 53, Hometown 52, Echo 56, Investigator 57, Equity Editor 50, Storyteller 54, Narrator 52, Publish Gate 55). Loader at `agents/wire/vocabulary.py` with `sample()` + `fill()` API. Consumers (Scouts, Editor) wire up Day-4. | 2026-05-04 |
| HND sync-watcher | ✓ `HndDetector.start()` now attaches `firestore_v1.Client.collection('lead_reports').on_snapshot(callback)` (sync client on a Firestore-managed thread); callbacks marshal back to the asyncio loop via `asyncio.run_coroutine_threadsafe`. `runtime.py` constructs separate sync + async Firestore clients. (Plan §G.2 fix.) | 2026-05-04 |
| Aho-Corasick library in production | ✓ `ahocorasick_rs 1.0.3` actively backing the NIL Layer. Backend logged at boot. **Over-redaction observed in smoke test** (`[redacted] State`, `[redacted]nitoring`, Day-4: `[redacted]la [redacted]ta` for "Chula Vista"; `[redacted] Placid` for "Lake Placid") — Day-2 stub doesn't yet have the disambiguation pass; full Day-6/7 Layer adds the 50-char context-window check. Fail-closed semantics working as designed. | 2026-05-04 |
| Investigator agent | ✓ alive end-to-end. `gemini-3.1-pro-preview` Runner via ADK; tools: `read_lead_report`, `grounded_search`, `query_historical_athletes` (aggregate-only), `query_geography`, `call_deep_research` (stub — see backlog), `write_investigation_packet`, `pull_vocabulary`. Voice texture observed live: *"pulling sources. confirming geography and historical parallel for the [redacted] Placid..."* | 2026-05-04 |
| Editor → Scout → Investigator dispatch chain | ✓ verified live. Editor decides `dispatch_scout(...)` AND/OR `dispatch_investigator(lead_report_id)`; both invoke real Pro/Flash Runners; tool calls auto-execute; results return through Firestore. The full Day-4 cycle observed in Wire stream: Editor decision → Scout thinking events → Editor `Investigator, 90 seconds.` → Investigator `pulling sources.` | 2026-05-04 |
| Wire vocabulary consumers | ✓ `pull_vocabulary` tool wired into Editor + 4 Scouts. Closure-bound to the right JSON key (`editor`, `cinderella_scout`, `comeback_scout`, `hometown_scout`, `echo_scout`). `fill()` handles both `{snake_case}` and `[snake_case]` slot syntax. `/health/agents` reports `vocabulary_loaded: True, fragment_count: 558`. | 2026-05-04 |
| Boot warnings filtered | ✓ surgical message-pattern filters in `_configure_logging()`: authlib.jose deprecation; ADK PLUGGABLE_AUTH UserWarning; google-genai non-text-parts message. Future legitimate warnings still surface. | 2026-05-04 |
| Narrator agent | ✓ alive end-to-end. Direct Vertex AI Gemini Flash TTS via async httpx (no ADK Runner — TTS is deterministic synthesis). `narrate(draft, voice_profile)` returns NarrationManifest with audio_urls (GCS) + word timings (linear-interpolated per-sentence) + cue points (place-name + era-reference offsets). Inline tags `[short pause]`, `[long pause]`, `[emphasis]` at sentence/paragraph boundaries + place-name first occurrence. Cost ceiling axis='tts'. **Live smoke verified** 2026-05-04: Algenib synthesizes ~6s of audio for a 14-word prompt in ~2s. | 2026-05-04 |
| Voice playback timing API empirical finding | Gemini Flash TTS does NOT return word-level timestamps in the response — only audio bytes (`audio/l16; rate=24000; channels=1`). Narrator falls back to per-sentence linear interpolation per BUILD_SPEC §3.5 path 2. Sentence-level highlighting on the Broadcast page is the load-bearing effect; word-level is bonus. | 2026-05-04 |
| Investigation-packet write visibility | ✓ `tools.py::_make_write_investigation_packet` now emits a Wire `thinking` event on Firestore-write failure ("hold — investigation packet write failed; the room will retry on the next dispatch") + INFO logs around the persist call. Closes a latent silent-failure bug found during Day-5 review. | 2026-05-04 |
| Equity Editor agent | ✓ alive end-to-end. Pro-tier ADK Runner; 6 closure-bound tools + pull_vocabulary; `review_feed()` and `review_draft(draft_id)` entry points. Failure-mode events use `intervention` not `thinking` (BUILD_SPEC §6.5 — Equity events arrive). Editor's `accept_equity_recommendation` real impl + new `request_equity_review` tool. | 2026-05-05 |
| Storyteller agent | ✓ alive end-to-end. Pro-tier ADK Runner; 4 closure-bound tools + pull_vocabulary; `write_story()` runs the full revision loop (max 3) calling equity then publish gate; on `returned`, re-invokes Runner with feedback; on `blocked` or `revisions >= max`, kills story. Validation enforces BUILD_SPEC §5.5 envelope (8-12 word headline, 400-700 word body, 3 why-this-matters bullets, etc.). The most rigorous prompt in the build (246 lines) — full forbidden-words + encouraged-temporal-phrasing lists verbatim from PROJECT_BRIEF §10. | 2026-05-05 |
| Publish Gate agent | ✓ alive end-to-end. Orchestrator runs all 7 sub-stages in order: 1=FactCheck (Pro structured-extraction + regex pre-pass for finish-times/scoring), 2=SourceReview (deterministic), 3=ParityReview (deterministic), 4=NIL Layer (Day-2 stub), 5=SafetyReview (Flash-Lite quote/private-info + regex fallback), 6=LanguageReview (pure-Python regex with context-aware fighter/despite + encouraged-temporal overlap filter), 7=VisualReview (Day-6 auto-pass stub; Day-7 ships the real Visualizer). Returns drafts on failure (max 3 revisions), kills with reason on revision-cap, writes PublishAudit on clear. Editor's new `dispatch_publish_gate` tool. | 2026-05-05 |
| **All 7 cast members operational** | ✓ editor, scout_desk, investigator, equity_editor, storyteller, narrator, publish_gate — zero shells in `/health/agents`. The Storyteller's Room is fully cast. | 2026-05-05 |
| Visualizer (Nano Banana Pro + Flash Image) | ✓ `agents/publish_gate/visualizer.py` (917 LOC). `generate_hero` (Pro Image), `generate_hometown_panel` + `generate_historical_echo` (Flash Image), `generate_assets` parallel via asyncio.gather, `fallback_hero` to gs://storytellers-room-fallback-heroes/. Three §7.4 prompt templates with 4 stricter-clause variants for regeneration. httpx timeout: **120s** (HoE-bumped from 60s after Day-7 smoke; Vertex AI image-gen latency is variable — Day-1 saw 21s, Day-7 saw >120s; HOE-DEC-020 Day-9 pre-cache pattern handles this for the demo). | 2026-05-05 |
| Visual Review sub-stage 7 | ✓ `agents/publish_gate/visual_review.py` (441 LOC, replaces Day-6 30-LOC stub). Pro vision check returns `{is_photoreal, has_likeness, detected_marks, confidence}` per image. Fail-closed on vision-call failure. Orchestrator runs the full regeneration loop (max 3) with stricter-prompt escalation, falls back to pre-rendered hero on 4th failure. | 2026-05-05 |
| **Full NIL Redaction Layer** | ✓ `agents/publish_gate/nil_redaction_layer.py` (775 LOC, supersedes Day-2 stub). Adds: disambiguation pass (min_needle_length≥4, word-boundary, 50-char sport-context window for common given names), near-id Flash-Lite check (broadcast surface only, gated), small-aggregate detection. **Day-3/4 over-redaction regressions FIXED:** "Monitoring" → pass; "Chula Vista" → pass; "Lake Placid" → pass. Day-2 stub kept importable as `NilRedactionLayerStub` for fallback. | 2026-05-05 |
| End-to-end smoke harness | ✓ `tests/integration/test_full_chain_e2e.py` (3 tests) — full Lead → Investigator → Storyteller → Equity → Publish Gate (7 sub-stages) → Narrator with NarrationManifest. `tests/integration/_chain_stubs.py` (525 LOC helper). `scripts/probe_full_chain.py` (operational, ~$0.50-1.00/run, documented). | 2026-05-05 |
| **Backend complete** | ✓ 293 tests + 1 skipped, lint clean across 51 files, live boot verified, all 7 sub-stages real. Day-8 starts the frontend; PAUSED for the design-approach checkpoint per memory feedback. | 2026-05-05 |
| Frontend (Days 8-11) | ✓ Next.js 15 App Router + React 19 + Tailwind 3.4 + Framer Motion + d3/d3-force + `@microsoft/fetch-event-source`. 4 surfaces live at `localhost:3000`: `/` (Wire feed via SSE), `/floor` (D3-Canvas constellation, 58 fixture nodes, 5 anchor labels, agitos-red intervention pulse on Birmingham), `/story/[id]` (Broadcast — 3 stories), `/publish-gate` (audit). Mobile responsive across all 4. Typecheck + lint clean. | 2026-05-04 → 2026-05-06 |
| Design system | ✓ `Docs/Engineering/design-system.md` v1.0 — 11 locked color tokens (navy-deep, navy-mid, navy-light, gold-warm, gold-deep, cream, parchment, agitos-red, slate-room, wire-text, wire-time), 9 type-scale entries (display-xl/lg/md, italic-md/sm, body-md/sm, mono-sm, caption), `room` cubic-bezier `(0.32, 0.72, 0, 1)`, AI-slop kill list. Per-tokens in `web/tailwind.config.ts`. | 2026-05-04 |
| Wire SSE bridge | ✓ `web/app/api/wire/stream/route.ts` — Next.js Route Handler (`runtime='nodejs'`, `dynamic='force-dynamic'`, `maxDuration=3600`). Pre-seeds last 6 events from `mode in ['replay','published']`; live `onSnapshot` listener on `mode == 'live'` with **1-hour time-window** (`LIVE_WINDOW_MS = 60 * 60 * 1000`, Day-11 D7) so pre-Day-7 stale rows don't reach UI. 15s heartbeat. Last-Event-ID resume. **Verified live**: pre-seed event arrives, then live `event: wire` rows arrive from Firestore. Frontend uses `useWireStream()` hook (`web/lib/wire-stream-client.ts`) via `@microsoft/fetch-event-source`. | 2026-05-05 |
| Firestore composite indexes (×2) | ✓ `wire_events: (mode ASC, timestamp DESC, __name__ ASC)` — name `CICAgOjXh4EK`, READY (Day-3, used by Editor's `_read_recent_published`). ✓ `wire_events: (mode ASC, timestamp ASC, __name__ ASC)` — name `CICAgJiUpoMK`, READY (Day-10, used by SSE bridge live query). | 2026-05-05/06 |
| BroadcastPage (3 stories) | ✓ `/story/fixture-mount-pleasant`, `/story/fixture-park-city-utah`, `/story/fixture-birmingham-alabama`. Each: stylized Nano Banana Pro hero (1376×768, painterly, no people/logos, 16:9), Algenib narration (~3:00-3:33 each), display-xl Playfair headline + italic Lora dek + drop-cap body + pull-quote + verified-claim ribbons + Publish Gate signature footer. Slow-fade hero motion (compression-factor 0.25 — opacity 0→1 / 800ms + scale 1.05→1.00 / 2s with `room` ease). All 3 passed `agents/publish_gate/language_review._scan_surface` audit (0 flagged terms, 0 predictive constructions). | 2026-05-05/06 |
| Floor (Pass-2 tuned) | ✓ `web/components/Floor.tsx` (441 LOC) + `web/lib/floor-fixture.ts` (225 LOC). D3-force on Hi-DPI Canvas. 58 nodes (HND ≥ 4.1), 63 bidirectional edges. Force config: `forceManyBody(-240)` + `forceCollide(r+18)` + `forceX/Y(0.02)` + `forceLink(distance=100, strength=0.16)`. Pinned anchors triangulated (Lake Placid upper-third, Chula Vista lower-left, Colorado Springs right-of-center). Two-pass halo (radial gradient + filled disc, `shadowBlur=12`). 5 labeled stars in tracked-small-cap mono gold-warm/0.6 (LAKE PLACID, CHULA VISTA, COLORADO SPRINGS, PARK CITY, HOUSTON). Mount stagger 1500ms — anchors first 150ms, non-anchors HND-descending. **`INTERVENTION_NODE_ID = 'birmingham-al'`** — agitos-red pulse fires on Birmingham at t+4.2s after mount. | 2026-05-05/06 |
| Publish Gate trust panel | ✓ `/publish-gate`. Aggregate stats strip (claims checked / redactions / disambiguation hits / cleared/blocked). Recent decisions feed (live `wire_events` lifted into `NilDecision` shape + 2 fixture rows for DISAMBIGUATED/RETURNED — labeled `live + fixture · mixed`). Disambiguation Trace marquee with Mount Pleasant resolved against `[athlete:A]` / `[athlete:B]` placeholder tokens. Footer: `athlete_registry: 11,188 entries · matcher: aho-corasick`. | 2026-05-05/06 |
| Demo asset cache (3 stories) | ✓ in repo at `web/public/fixture/heroes/{mount-pleasant,birmingham-alabama,park-city-utah}.png` (1.97 MB / 1.63 MB / 1.69 MB). ✓ in repo at `web/public/fixture/narration-{mount-pleasant,birmingham-alabama,park-city-utah}.mp3` (2.15 MB / 2.55 MB / 2.51 MB). All 6 currently served from `web/public/`. Day-12 deploy migrates to GCS. | 2026-05-06 |
| EE intervention demo seed | ✓ `scripts/seed_equity_editor_demo.py` (179 LOC, idempotent with `--purge`). 10 wire_events under `investigation_id=demo-equity-edit-001` covering the Birmingham EE arc end-to-end. EE intervention text passes the no-apology rule. NIL Layer ran on each event (rejected an earlier draft of "Story published. Stack updated." after flagging "Story" + "Stack" as athlete surnames — proof the Layer is fail-closed). | 2026-05-06 |
| NIL forward-path verification | ✓ R1 root cause confirmed: `agents/wire/emit.py:118` calls full `_direct_match_and_disambiguate` pipeline. Day-7 patch landed 2026-05-05 15:24 UTC; all 27 over-redacted rows in Firestore are pre-Day-7. New file `tests/test_emit_full_disambiguation.py` (3 integration tests, passing) guards the forward path. D7 1-hour window keeps stale rows out of UI. | 2026-05-06 |
| Cloud Run | **Still empty.** Both services local-only. Day-8/9 deploy is the last major infra task before submission. | — |
| **End-to-end chain proven** | ✅ 2026-05-07 Day-6: first-ever organic `published_story` landed in Firestore — *"The Tucson Desert Hub Operates as a Dual Engine for Endurance Training"*. Algenib narration 5:16 at `gs://storytellers-room-audio/jZz3aF6fof3ehDEmcxsk/0000.wav`. nil_signature `claims_checked=29, softened=1, removed=0` (Lesson 21 outcome — well-disciplined Storyteller). audit_id backref to cleared publish_audit. All 7 agents fired in real organic operation. Halt trigger fully closed. | 2026-05-07 |
| Firestore composite indexes (×4) | ✓ `wire_events:(mode ASC, timestamp DESC, __name__ ASC)` — `CICAgOjXh4EK`, READY (Day-3). ✓ `wire_events:(mode ASC, timestamp ASC, __name__ ASC)` — `CICAgJiUpoMK`, READY (Day-10). ✓ `agent_handoffs:(mode ASC, timestamp ASC, __name__ ASC)` — `CICAgJim14AK`, READY (Day-6). ✓ `publish_audits:(final_decision ASC, narration_dispatched ASC, completed_at DESC, __name__ ASC)` — `CICAgJjF9oIK`, READY (Day-6). | 2026-05-06/07 |
| Cost ceilings (HOE-DEC-034) | ✓ Three layers: per-axis (gemini_pro 5M tok/day, grounding 50K queries, deep_research 100 calls, tts 2M chars), per-day USD ($50 default), absolute USD ($300 default). All four overridable via env vars (`COST_CEILING_GEMINI_PRO_TOKENS`, `COST_CEILING_GROUNDING_QUERIES`, `COST_CEILING_DEEP_RESEARCH_CALLS`, `COST_CEILING_TTS_CHARS`, `COST_CEILING_DAILY_USD`, `COST_CEILING_ABSOLUTE_USD`). | 2026-05-07 |
| Agent handoff event stream (HOE-DEC-DEC-D / Worker D) | ✓ `agents/handoffs.py::emit_handoff()` writes structured `{from_agent, to_agent, tool_call_id, story_unit_id, investigation_id, timestamp, mode}` docs to the new `agent_handoffs` Firestore collection. 10 dispatch wires across Editor / Equity Editor / Storyteller / Publish Gate orchestrator. SSE bridge route handler emits `event: handoff` + `event: handoff-preseed` alongside the existing `event: wire` + `event: preseed` streams. Same 1-hour window + Last-Event-ID semantics. | 2026-05-06 |
| Cleared-audit → Narrator wire (HOE-DEC-035 / Worker E) | ✓ Editor's autonomous loop scans `publish_audits where final_decision == 'cleared' && narration_dispatched == False`, surfaces results to Pro model in context snapshot, prompt instructs `dispatch_narrator(draft_id, voice_profile='algenib', audit_id=...)`. Tool flips `narration_dispatched=True` + `narration_dispatched_at` after dispatch. Narrator's `narrate(...)` writes a `published_stories` doc with full schema including `nil_signature` carried over from the audit. | 2026-05-07 |
| Vertex AI service-agent IAM | ✓ Granted `roles/storage.objectViewer` to `service-615585524733@gcp-sa-aiplatform.iam.gserviceaccount.com` on all 3 GCS buckets (`storytellers-room-hero-images`, `storytellers-room-audio`, `storytellers-room-fallback-heroes`) — required for visual_review's vision-on-GCS calls. Day-6 chain debug surfaced this; without the grant the orchestrator hits FAILED_PRECONDITION → falls back to pre-cached hero. | 2026-05-07 |
| Service accounts | ✓ `agent-runtime@predictive-fx-495200-j4.iam.gserviceaccount.com`, ✓ `web-frontend@predictive-fx-495200-j4.iam.gserviceaccount.com` | Note: `web-frontend` not `web` (6-char minimum SA ID); docs updated to match. IAM bindings applied (see §6.1). |
| Secret Manager | **Empty** | Add only when an external API key is needed (e.g., music vendor) |
| Budget alerts | ✓ `$100 informational`, `$200 audit`, `$300 kill-switch` (each with 50%, 90%, 100%, 100%-forecasted thresholds) | Created 2026-05-03 |

### 6.1 Verified IAM bindings (2026-05-03)

`agent-runtime@`:
- `roles/aiplatform.user` (Vertex AI calls)
- `roles/datastore.user` (Firestore read/write)
- `roles/bigquery.dataViewer` (read corpus + registry)
- `roles/bigquery.jobUser` (run queries)
- `roles/storage.objectAdmin` (write hero/audio buckets)
- `roles/secretmanager.secretAccessor`
- `roles/logging.logWriter`
- `roles/cloudtrace.agent`

`web-frontend@`:
- `roles/datastore.user` (Firestore read for SSE bridge)
- `roles/storage.objectViewer` (read hero/audio buckets)
- `roles/logging.logWriter`
- `roles/run.invoker` (call agent-runtime service-to-service)

## 7. Local dev environment

| Tool | Version | Path |
|---|---|---|
| `gcloud` | 548.0.0 | `/opt/homebrew/bin/gcloud` |
| `gh` | (authed as `charliereagan`) | `/opt/homebrew/bin/gh` |
| `git` | (system) | `/opt/homebrew/bin/git` |
| `gcloud beta components` | 2025.11.17 | (installed for billing query) |
| `bq` | 2.1.25 | (bundled with gcloud) |

Repo path on this machine: `/Users/charliereagan/projects/Google_Olympics_Hackathon`

## 8. Repository state

| Item | Value |
|---|---|
| GitHub URL | https://github.com/charliereagan/Google_Olympics_Hackathon |
| Visibility | **PRIVATE** — flip to PUBLIC before submission |
| Default branch | `main` |
| License | Apache License 2.0 (badge auto-detected from `LICENSE`) |
| Last commit before Day-11 catchup | `e1a5c2f` (Day-8 design system + Charlie+HoE refinement loop) |

## 9. Cost ceiling reality (vs BUILD_SPEC §15 estimates)

Through Day 7 of build: total Vertex AI spend ~$100-140 cumulative. Day-6 spike was ~$60-70 (chain debugging session — multiple probes + 50 organic story_drafts produced + Pro deliberation across investigations). USD ceiling tripped at $51.64 mid-evening; HoE bumped override to $200 wall to finish debug. Cumulative spend still well under $300 hard kill-switch alert. Per-day budget for the bounded organic-op windows in Days 7-9 = $50-75. The runtime defaults OFF outside those windows per HOE-DEC-036. Budget alerts active per BUILD_SPEC §15.2:
- $100 alert → informational
- $200 alert → audit which axis is driving spend
- $300 alert → flip `AGENT_RUNTIME_PAUSED=1` env var

## 10. Open knowns to verify before they bite

1. **Gemini TTS word-level timing API shape.** Confirmed Day-5: the API does NOT return word timestamps; Narrator falls back to per-sentence linear interpolation per BUILD_SPEC §3.5 path 2.
2. **Gemini 3.1 Pro daily quota.** No quota issues observed across Days 1-11 of organic operation.
3. **Music bed licensing.** Receipts in `/audio/music_beds/LICENSES.md` by submission day; Suno-generated original as fallback. Day-12 task.

## 11. Refresh procedure

When infra changes (a new bucket, a new service deployed, a new env var set, a model ID shift), update this file. Suggested cadence:
- After every Cloud Run deploy
- After every API enable/disable
- After every Vertex AI model substitution
- Whenever `gcloud auth application-default` state changes
- Daily during Day 8-10 demo prep

The HoE session is responsible for keeping this current. Execution sessions can append observations under their own dated heading at the bottom if they discover something.

---

## Probe commands (for re-verification)

```bash
# Project + billing
gcloud projects describe predictive-fx-495200-j4 --format="value(projectId,name,projectNumber,lifecycleState)"
gcloud beta billing projects describe predictive-fx-495200-j4 --format="value(billingEnabled,billingAccountName)"

# APIs
gcloud services list --enabled --project=predictive-fx-495200-j4 --format="value(config.name)" | sort

# Model probe (one example — replace MODEL + VERSION as needed)
TOK=$(gcloud auth application-default print-access-token)
curl -sS -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  "https://aiplatform.googleapis.com/v1/projects/predictive-fx-495200-j4/locations/global/publishers/google/models/gemini-3.1-pro-preview:generateContent" \
  -d '{"contents":[{"role":"user","parts":[{"text":"hi"}]}],"generationConfig":{"maxOutputTokens":8}}'

# TTS voice catalog
curl -sS -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  -H "X-Goog-User-Project: predictive-fx-495200-j4" \
  "https://texttospeech.googleapis.com/v1/voices" | jq '.voices[] | select(.name | startswith("en-US-Chirp3-HD-")) | .name'

# Data services
gcloud firestore databases list --project=predictive-fx-495200-j4
bq --project_id=predictive-fx-495200-j4 ls
gcloud storage buckets list --project=predictive-fx-495200-j4
gcloud run services list --project=predictive-fx-495200-j4
```
