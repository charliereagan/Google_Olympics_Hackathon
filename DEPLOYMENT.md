# DEPLOYMENT.md — The Storyteller's Room

This file documents how the system is deployed. Refresh whenever a deployment changes. **For "what's currently provisioned right now," see [`Docs/Engineering/tech_snapshot.md`](Docs/Engineering/tech_snapshot.md)** — that's the runtime ground truth; this file is the procedure.

> **Note:** This file is the deployment procedure document. Until Day 1 GCP provisioning runs and the first Cloud Run deploy lands, most of what's below is the *target* deployment shape. Every command + flag is what we plan to use. Mark verified sections with ✓ as they go live.

---

## 0. Project + account

| Item | Value |
|---|---|
| GCP project ID | `predictive-fx-495200-j4` |
| GCP project name | `Google-Olympics-Hackathon` |
| GCP project number | `615585524733` |
| Billing account | `billingAccounts/01933A-29A38C-94AD56` (linked + enabled ✓) |
| Active gcloud account | `charlie@battlecards.pro` |
| ADC quota project | `predictive-fx-495200-j4` ✓ |
| GitHub repo | https://github.com/charliereagan/Google_Olympics_Hackathon (PRIVATE → flip PUBLIC before submission) |

## 1. APIs enabled

```
aiplatform.googleapis.com
artifactregistry.googleapis.com
bigquery.googleapis.com (+ family)
cloudbuild.googleapis.com
cloudscheduler.googleapis.com
cloudtrace.googleapis.com
firestore.googleapis.com
logging.googleapis.com
monitoring.googleapis.com
run.googleapis.com
secretmanager.googleapis.com
storage.googleapis.com
texttospeech.googleapis.com
```

Re-check / re-enable: `gcloud services enable aiplatform.googleapis.com firestore.googleapis.com run.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com texttospeech.googleapis.com artifactregistry.googleapis.com --project=predictive-fx-495200-j4`

## 2. Service accounts (per BUILD_SPEC §19.1)

To be created on Day 1:

| Service account | Used by | Roles |
|---|---|---|
| `agent-runtime@predictive-fx-495200-j4.iam.gserviceaccount.com` ✓ | `agent-runtime` Cloud Run service | `aiplatform.user`, `datastore.user`, `bigquery.dataViewer`, `bigquery.jobUser`, `storage.objectAdmin`, `secretmanager.secretAccessor`, `logging.logWriter`, `cloudtrace.agent` |
| `web-frontend@predictive-fx-495200-j4.iam.gserviceaccount.com` ✓ | `web` Cloud Run service | `datastore.user`, `storage.objectViewer`, `logging.logWriter`, `run.invoker` (call agent-runtime) |

Creation commands (run Day 1):

```bash
gcloud iam service-accounts create agent-runtime \
  --display-name="Storyteller's Room agent runtime" \
  --project=predictive-fx-495200-j4

gcloud iam service-accounts create web \
  --display-name="Storyteller's Room web frontend" \
  --project=predictive-fx-495200-j4
```

## 3. Firestore (Native mode)

Database location: `nam5` (multi-region US) for low-latency reads from `us-central1` Cloud Run + judges anywhere in the US.

```bash
gcloud firestore databases create \
  --database='(default)' \
  --location=nam5 \
  --type=firestore-native \
  --project=predictive-fx-495200-j4
```

**Security rules:** server-side `onSnapshot` only. Client access denied. See `firestore.rules` (Day 1).

## 4. BigQuery (datasets + tables)

Dataset: `storytellers_room` (production), `storytellers_room_dev` (local dev mirror).

Schemas in `BUILD_SPEC.md §8`. Loader scripts in `/data/`.

```bash
bq --project_id=predictive-fx-495200-j4 mk --dataset \
  --location=US \
  storytellers_room

bq --project_id=predictive-fx-495200-j4 mk --dataset \
  --location=US \
  storytellers_room_dev
```

Tables to create (Day 1):
- `candidates` (story unit pool — places, programs, patterns)
- `historical_athletes` (filtered Team USA only)
- `geography` (hometown population, region)
- `championships` (placement counts only — NO finish times, NO scoring data)
- `athlete_registry` (NIL Layer source)
- `agent_call_counters` (cost-ceiling tracking per BUILD_SPEC §15.3)
- `agent_errors` (failure-mode logging per BUILD_SPEC §17)

## 5. Cloud Storage buckets

```bash
gcloud storage buckets create gs://storytellers-room-hero-images \
  --location=US --project=predictive-fx-495200-j4

gcloud storage buckets create gs://storytellers-room-audio \
  --location=US --project=predictive-fx-495200-j4

gcloud storage buckets create gs://storytellers-room-fallback-heroes \
  --location=US --project=predictive-fx-495200-j4
```

## 6. Cloud Run services

Two services, deployed independently.

### 6.1 `agent-runtime`

```bash
gcloud run deploy agent-runtime \
  --source=./agents \
  --service-account=agent-runtime@predictive-fx-495200-j4.iam.gserviceaccount.com \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=4 \
  --cpu=2 \
  --memory=2Gi \
  --cpu-always-allocated \
  --use-http2 \
  --timeout=3600s \
  --port=8080 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=predictive-fx-495200-j4,GOOGLE_CLOUD_LOCATION=global,VERTEX_AI_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true,FIRESTORE_DATABASE=(default),APP_ENV=production" \
  --set-secrets="..." \
  --no-allow-unauthenticated \
  --project=predictive-fx-495200-j4
```

`--no-allow-unauthenticated` — only the `web` service invokes this directly via service-to-service auth.

### 6.2 `web` (Next.js 15 frontend + SSE bridge)

```bash
gcloud run deploy web \
  --source=./web \
  --service-account=web-frontend@predictive-fx-495200-j4.iam.gserviceaccount.com \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=10 \
  --cpu=1 \
  --memory=1Gi \
  --cpu-always-allocated \
  --use-http2 \
  --timeout=3600s \
  --port=3000 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=predictive-fx-495200-j4,FIRESTORE_DATABASE=(default),AGENT_RUNTIME_URL=https://agent-runtime-xxx-uc.a.run.app,APP_ENV=production" \
  --allow-unauthenticated \
  --project=predictive-fx-495200-j4
```

`--allow-unauthenticated` — this is the public demo URL judges will hit.

## 7. Cloud Scheduler (always-on watchdog)

Per HOE-DEC-022. Pings `agent-runtime/health/heartbeat` every 5 minutes; if stale, triggers a forced revision update.

```bash
gcloud scheduler jobs create http agent-runtime-watchdog \
  --schedule="*/5 * * * *" \
  --uri="https://agent-runtime-xxx-uc.a.run.app/health/heartbeat" \
  --http-method=GET \
  --location=us-central1 \
  --project=predictive-fx-495200-j4
```

## 8. Secrets (Secret Manager)

| Secret | Purpose |
|---|---|
| `epidemic-sound-api-key` | If using their API for music bed auto-fetch (optional) |
| (no Vertex AI keys needed — service account auth) | |
| (no Firestore / BQ / GCS keys needed — service account auth) | |

API keys never live in `.env` files committed to the repo. Cloud Run mounts them via `--set-secrets`.

## 9. Cloud Build pipeline

`cloudbuild.yaml` at repo root. Triggered on push to `main`. Two parallel build steps:
1. Build + push `agent-runtime` image to Artifact Registry → deploy to Cloud Run
2. Build + push `web` image to Artifact Registry → deploy to Cloud Run

`make deploy-demo` is the manual promotion command for the public demo URL on Day 10.

## 10. Vertex AI configuration

**Critical:** all Gemini 3 family preview models are global-endpoint only. The agent runtime must `vertexai.init(project=..., location='global')`. Regional calls (e.g., `us-central1`) return 404.

URL shape per verified probes (2026-05-02):
- `gemini-3.1-pro-preview` → `v1` `:generateContent` (Pro is the only one currently on v1; the rest are v1beta1)
- `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview` → `v1beta1` `:generateContent`
- `gemini-3-pro-image-preview`, `gemini-3.1-flash-image-preview` → `v1beta1` `:generateContent` + `responseModalities: ["IMAGE"]`
- `gemini-3.1-flash-tts-preview` → `v1beta1` `:generateContent` + `responseModalities: ["AUDIO"]` + `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` (bare voice name, e.g., `"Charon"` not `"en-US-Chirp3-HD-Charon"`)

## 11. Observability

- **Cloud Logging** — structured JSON per agent call (schema in BUILD_SPEC §16.1)
- **Cloud Trace** — OpenTelemetry spans across Editor → Scout → Investigator → Equity → Storyteller → Publish Gate → Narrator chain
- **Cloud Monitoring** — `storytellers-room-golden-path` dashboard (BUILD_SPEC §16.3)
- **Budget alerts** — $100 / $200 / $300 thresholds (BUILD_SPEC §15.2)

## 12. Apache 2.0 license verification

Daily CI check via `scripts/check_license.sh`. Manual verification: visit https://github.com/charliereagan/Google_Olympics_Hackathon and confirm the "Apache-2.0 license" badge is in the About sidebar.

**Day 10 pre-submission gate:** repo must be flipped from PRIVATE → PUBLIC before clicking submit. Until then, the badge is detectable but the repo isn't accessible to judges.

```bash
gh repo edit charliereagan/Google_Olympics_Hackathon --visibility public
```

## 13. Demo-day pre-flight checklist

5–30 minutes before recording:

- [ ] Warm both Cloud Run URLs with synthetic traffic (`curl https://web-xxx-uc.a.run.app` × 2)
- [ ] Confirm `min-instances=1` is honored (`gcloud run services describe agent-runtime --format="value(spec.template.metadata.annotations)"`)
- [ ] Check Vertex AI quota dashboard — ensure available quota >2× expected demo burn
- [ ] Confirm `/health/nil` returns 200 on agent-runtime
- [ ] Confirm Firestore `wire_events` has recent published events for the pre-seed
- [ ] Confirm anchor candidate fallback hero image is in `gs://storytellers-room-fallback-heroes/`
- [ ] Verify last commit is on `main` and deployed (Cloud Run latest revision = recent commit SHA)
- [ ] Hide browser bookmarks bar, notifications, dock badges (PROJECT_BRIEF §14)

## 14. Rollback

```bash
gcloud run services update-traffic agent-runtime --to-revisions=PREVIOUS=100 --region=us-central1
gcloud run services update-traffic web --to-revisions=PREVIOUS=100 --region=us-central1
```

By Day 9 EOD, label the last-known-good revisions in Cloud Run console as `v0.10.0-demo-final`.

## 15. Post-submission ops (May 12 – June 10, 2026)

- Min-instances stays at 1 on both services through June 10.
- Budget alerts retuned for steady-state low-traffic ($20 / $40 / $60 monthly).
- No destructive deploys until June 11+. The submitted state is what judges evaluate.
- Per PROJECT_BRIEF §6: Team USA Data must be destroyed at conclusion. `scripts/teardown_team_usa_data.sh` drops `athlete_registry`, `historical_athletes`, `championships`, `geography` BigQuery tables on or after June 16, 2026.

## 16. Local development

See [`BUILD_SPEC.md §18`](Docs/Engineering/BUILD_SPEC.md). `make dev` boots Firestore emulator + agent runtime + Next.js dev server.
