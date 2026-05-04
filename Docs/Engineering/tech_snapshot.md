# tech_snapshot.md — Ground truth for the runtime environment

**Last refreshed:** 2026-05-04 by HoE Session 2 (Day-3 Editor `think_once` body + `/api/investigate` endpoint shipped; real ADK Runner integration against live Vertex AI; HOE-DEC-030 + HOE-DEC-031 ratified; 83 unit tests + 1 skipped)

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
| Last commit | `9d48dd7` (initial commit — project documents + Apache 2.0 license) |

## 9. Cost ceiling reality (vs BUILD_SPEC §15 estimates)

No spend yet. Budget alerts not yet configured. Day 1 task per BUILD_SPEC §15.2:
- $100 alert → informational
- $200 alert → audit which axis is driving spend
- $300 alert → flip `AGENT_RUNTIME_PAUSED=1` env var

## 10. Open knowns to verify before they bite

1. **Gemini TTS word-level timing API shape.** Empirical Day-5 verification — does the response include word timestamps, sentence-level only, or none? Three documented fallback paths in BUILD_SPEC §3.5.
2. **Gemini 3.1 Pro daily quota.** Day-5 quota check; request increase if continuous Day 8-9 operation projects to exceed.
3. **Music bed licensing.** Receipts in `/audio/music_beds/LICENSES.md` by Day 9 EOD; Suno-generated original as fallback.

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
