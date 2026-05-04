# The Storyteller's Room — Build Spec v1.3

**Project:** Team USA × Google Cloud Hackathon submission
**Submission category:** Challenge 2 — The Hometown Success Engine
**Deadline:** May 11, 2026 @ 5:00pm PT (8:00pm ET)
**Build target:** Claude Code
**Pivot:** A+ (Place over Person) — locked May 1, 2026
**Day-1 tightening pass:** May 2, 2026 (VPS Session 1; eight ratified decisions — see VPS-HANDOFF Section 5)
**Stack-validation pass:** May 2, 2026 (HoE Session 1 — see Changelog below and HOE-HANDOFF Section 4 for HOE-DEC-015 through HOE-DEC-024)
**Repo location:** `/Users/charliereagan/projects/Google_Olympics_Hackathon`
**This file lives at:** `Docs/Engineering/BUILD_SPEC.md`

---

## Changelog v1.2 → v1.3 (May 2, 2026)

The v1.3 pass is a stack-validation + operability layer. Every locked decision in v1.2 (the seven-agent cast, Pivot A+, Challenge 2, the NIL Redaction Layer as a named feature, the demo storyboard) is preserved. The deltas:

**Corrections (driven by 2026-05-02 Vertex AI doc validation):**
- All Gemini 3 family models are still in **preview** as of 2026-05-02; production model IDs differ from the v1.2 placeholders. See §3.1.
- All Gemini 3 family preview models are **GLOBAL-ENDPOINT ONLY**; calls to `us-central1` return 404 model-not-found. The agent runtime must `vertexai.init(project=…, location='global')`. (HOE-DEC-015.)
- `gemini-3-pro-preview` was discontinued 2026-03-26; we use `gemini-3.1-pro-preview`. (HOE-DEC-016.)
- The Gemini Flash TTS voice list changed: 30 prebuilt voices, accessed by name; v1.2's "Charon" / "Puck" placeholders need confirmation against `scripts/list_tts_voices.py` before any Narrator code lands. The TTS API supports inline tags (`[pause=1.0]`, `[emphasis]`, `[short pause]`, `[long pause]`, `[slow]`, `[fast]`, `[cheerful]`) for pacing control. SynthID watermark is applied to all output. (HOE-DEC-017.)
- **Voice audition completed 2026-05-03 (HOE-DEC-025):** Broadcast Narrator = `Algenib`, Wire Dispatcher = `Fenrir`, single-voice fallback = `Fenrir`. Audition WAVs in `audio/voice_audition/` (gitignored).

**Architectural pins (things v1.2 left ambiguous):**
- The **Wire-level NIL guard runs as an in-process write-through proxy**. All agents call `wire.emit(event)`; direct `firestore.add('wire_events', …)` is forbidden (CI lint rule). Cloud Function `onCreate` triggers were considered and rejected — they race the SSE stream and would briefly leak names. (HOE-DEC-018; closes audit P0.)
- The **NIL Redaction Layer fails CLOSED, not open.** On agent runtime startup, an assertion verifies `athlete_registry` has ≥500 rows or the runtime exits 1. The `/health/nil` endpoint returns 503 until the registry is loaded. (HOE-DEC-019.)
- The **Visualizer tool** lives at `/agents/publish_gate/visualizer.py`, called by the Publish Gate after Storyteller draft is NIL-cleared and before sub-stage 7 Visual Review. Up to 3 regenerations on Visual Review fail; 4th fail uses a curated Day-9 fallback from `/data/fallback_heroes/{story_unit_id}.png`. (HOE-DEC-020.)
- The **"4× compressed time" demo mechanism** is a `compression_factor: float` parameter on the investigation context. Default 1.0; the live URL hero CTA passes 0.25; ambient Wire continues at 1.0. Wire event timestamps reflect real wall-clock time; the cadence is what compresses. (HOE-DEC-021.)
- The **agent runtime "always-on" loop** is an `asyncio.create_task(autonomous_loop())` inside the Editor agent, with a 30-90s think-cycle. A Cloud Scheduler ping every 5 minutes acts as a watchdog. (HOE-DEC-022.)
- The **High Narrative Density detection logic** is pinned: HND fires when ≥3 of 4 Scouts have written a `LeadReport` for the same `story_unit_id` within a rolling 10-minute window AND each Scout's confidence ≥0.7. (HOE-DEC-023.)
- **Streaming pattern: server-side `onSnapshot` → SSE.** The Next.js Route Handler subscribes to Firestore server-side and forwards events. The frontend does NOT use the Firebase JS SDK directly. Reasons: bundle weight, auth/rules complexity, consistent ordering, and the demo's pre-seed pattern is `O(1)` from the same Firestore cursor. (HOE-DEC-024.)

**New operability sections (v1.2 was silent):**
- §15 Cost guardrails + budget alerts
- §16 Observability (logging, traces, metrics dashboard)
- §17 Error handling and graceful degradation
- §18 Local development setup
- §19 Deployment pipeline + IAM + secrets
- §20 Test strategy
- §21 Demo-day single points of failure + mitigations
- §22 Post-submission ops + data destruction (PROJECT_BRIEF §6, §13, §17, §18)

**Acceptance criteria additions (§14):** measurable bars for first-paint <1s, curtain-rise timing, voice-blind test (≥18/21 correct attribution), organic-Equity-intervention causal-chain visibility, NIL fail-closed assertion, max-3-revision-rounds, and the Day-1 license/voice-list/global-endpoint hard gates.

The Anti-patterns list (formerly §15) is now §23. Final reminder is §24. Pointers is §25.

---

## 0. How to read this spec

This document is the single source of truth for building **The Storyteller's Room**. It is written for a coding agent (Claude Code) to execute against. It is opinionated. When it says "use Firestore," it means use Firestore — not because alternatives are wrong, but because the build window is 11 days and re-litigating choices burns time we don't have.

**Document hierarchy:**
- **PROJECT_BRIEF.md** — wins on legal/compliance/submission requirements (NIL, branding, terminology, deadlines).
- **CONSTITUTION.md** — wins on creative/architectural principles.
- **This BUILD_SPEC.md** — wins on tactical implementation.
- **What_is_The_Storytellers_Room.md** — descriptive, never overrides.

Four things the coding agent must protect at all costs, even if cuts are needed elsewhere:

1. **The agents must feel alive.** Visible cognition, messy interjections, deliberate pacing, voice signatures. If the wire reads like ad copy, we lose. See §6.
2. **Paralympic Equity is a system property.** A dedicated agent with veto power, visible interventions, structurally enforced. See §5.4.
3. **NIL safety is architecture.** The NIL Redaction Layer (§5.7) sits between agent output and any user-facing surface. See §5.7 and §7.
4. **The Broadcast page is the emotional payoff.** Olympic broadcast production value, narrated end-to-end, choreographed visuals — telling the story of a *place*, not a person. See §7.

Everything else is negotiable.

---

## 1. The product, in one paragraph

**The Storyteller's Room** is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians. A coordinated team of seven Gemini agents (Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate) operates continuously: scouting public data for emotionally resonant story units (places, programs, patterns), investigating leads, enforcing Olympic/Paralympic parity, redacting individual athlete identification by architecture, fact-checking claims, and producing narrated Olympic-broadcast-style story pages. Users see three views: **The Wire** (live agent activity), **The Floor** (technical agent graph), and **The Broadcast** (the produced story about a place). The protagonists are the towns that quietly produce Team USA — not the famous athletes everyone already knows.

---

## 2. The five demo moments the build must serve

Every implementation decision must be checked against these five moments. If a feature doesn't help at least one of them, deprioritize it.

1. **"The room is alive."** The Wire scrolls before the user does anything. Voices murmur. Confidence scores shift. Leads (about places, programs, patterns) get rejected. (§6)
2. **"This is truly agentic."** The Floor shows multiple agents, real tool calls (BigQuery, Gemini grounded search, Nano Banana, TTS), handoffs as particle animations, an Equity Editor intervention. (§9)
3. **"The Equity Editor caused this story."** The Wire shows feed-drift detection. The Editor accepts. Scout Desk pivots to a Paralympic-anchored place. The anchor story begins. (§5.4, §11)
4. **"The Broadcast lands emotionally."** Narrated Olympic-style story page about a *place* — with synchronized hero image (a stylized landscape), hometown map zoom, historical echo panel referencing an era. (§7)
5. **"This is trustworthy."** Publish Gate opens. Seven sub-stages visible. Sources counted, claims removed, parity confirmed, **NIL Redaction Layer's individual-reference audit visible**. (§5.7)

---

## 3. Tech stack (locked)

### 3.1 Generative AI — verified model IDs

All Gemini 3 family models are in preview as of 2026-05-02. **All are global-endpoint only — calls to `us-central1` return 404 model-not-found.** The agent runtime initializes with `vertexai.init(project=PROJECT_ID, location='global')` and sets `GOOGLE_CLOUD_LOCATION=global` in deploy env.

| Use | Verified model ID | Notes |
|---|---|---|
| Editor (orchestration, decisions) | `gemini-3.1-pro-preview` | 1M token context. Replaces the discontinued `gemini-3-pro-preview` (deprecated 2026-03-26). |
| Storyteller (long-form narrative) | `gemini-3.1-pro-preview` | Same model; literary register controlled by system prompt. |
| Paralympic Equity Editor | `gemini-3.1-pro-preview` | Reasoning-heavy; Pro tier appropriate. |
| Investigator (synthesis) | `gemini-3.1-pro-preview` | Calls Gemini Deep Research as a tool — see §5.3 for async pattern. |
| Publish Gate (fact check, audit) | `gemini-3.1-pro-preview` | |
| Scout Desk (4 parallel scouts) | `gemini-3-flash-preview` | Flash tier for cost/latency on continuous Scout polling. |
| Wire vocabulary fills, utility calls, NIL near-identification check | `gemini-3.1-flash-lite-preview` | $0.25/1M input, $1.50/1M output. 1M context, 64K output max. |

**Why preview is acceptable for an 11-day demo:** the entire Gemini 3 family is preview at submission. Google's Pre-GA Offerings Terms govern. The submission is judged on what works, not on GA status. We monitor the Vertex AI release notes daily (see §13 Day-1 gate) for the GA cutover or any deprecation that would rename the IDs.

**Day-1 model-availability gate (HOE-DEC-016):** before any agent code lands, run `scripts/verify_models.py` which calls each of the seven model IDs above on the global endpoint and asserts they respond. If any return 404, treat it as a P0 blocker and check the Vertex AI release notes for renames.

### 3.2 Gemini Deep Research — async pattern

Deep Research is callable as a tool but typical latency is multi-minute (the model iteratively searches, reads, and synthesizes a report). It cannot be invoked synchronously from inside an investigation that emits to the Wire every 4-8s. The Investigator wraps Deep Research in:
- A 90-second timeout. On timeout, the Investigator falls back to grounded search and emits a Wire `thinking` event: *"deep research stalled, switching to grounded search"* — which becomes good Wire texture.
- A daily call cap (≤10 anchor-grade Deep Research calls/day). Tracked in Firestore `agent_call_counters`.
- An async-handoff pattern: Investigator emits *"deep research underway"* milestone, schedules the call as a fire-and-forget asyncio task, continues Wire activity with grounded search, and writes the Deep Research report into the Investigation Packet when it returns.

### 3.3 Grounding with Google Search

- **Vertex AI Gemini 3 grounding pricing:** 5,000 free grounded prompts/month, then $14 per 1,000 search queries. **Each search query the model executes within a single prompt counts as a billable use** — multiple queries = multiple bills.
- Configuration: `tools=[{"google_search": {}}]` in the Gemini call (verify exact key against current docs at build). Recommended `temperature=1.0` per docs.
- All Scouts and the Investigator use grounding. Daily projected burn: ~2K queries on Day 8-9 continuous run. Well under the free tier; budget alert covers anomalies (see §15).

### 3.4 Generative media — verified model IDs

| Use | Verified model ID | Notes |
|---|---|---|
| Hero illustrations (Broadcast page) | `gemini-3-pro-image-preview` (Nano Banana Pro) | Cinematic; Gemini 3 Pro reasoning core; subject is *always a place, landscape, community, or facility*. Never a person. |
| Utility visuals (hometown panel maps, historical-echo cards, scout glyphs) | `gemini-3.1-flash-image-preview` (Gemini 3.1 Flash Image) | Lower cost; sufficient for utility graphics. (Spec v1.2 called this "Nano Banana 2" — that's the marketing/codename family; the verified Vertex AI model ID is `gemini-3.1-flash-image-preview`.) |

**Do not use Veo 3.1.** Stills with Ken Burns motion + Narrator voice is the disciplined Olympic aesthetic.

**Image safety filters:** Vertex AI's enterprise-grade safety filters are on by default for Gemini 3 Pro Image. We accept that as the floor. Visual Review (sub-stage 7) is the second filter.

**Image prompt control:** see §7.4 for the per-image prompt templates and §7.4.1 for the pre-cached hero fallback strategy.

### 3.5 Voice — Gemini 3.1 Flash TTS

Model ID: `gemini-3.1-flash-tts-preview`. 30 prebuilt voices, 70+ languages. Inline tags supported: `[slow]`, `[fast]`, `[short pause]`, `[long pause]`, `[pause=1.0]`, `[emphasis]`, `[cheerful]`, and ~200 others for expressive control. SynthID watermark applied to all output.

| Use | Voice config | Verified |
|---|---|---|
| Broadcast Narrator | **`Algenib`** — warm, mid-tone, documentary register. Slight gravitas, deliberate breath. | ✓ HOE-DEC-025 (2026-05-03 audition) |
| Wire Dispatcher | **`Fenrir`** — clipped, lower register, control-room/radio energy. | ✓ HOE-DEC-025 (2026-05-03 audition) |
| Single-voice fallback (any future context where only one voice is used) | **`Fenrir`** | ✓ HOE-DEC-025 |

Vertex AI invocation form uses the **bare voice name** (e.g., `"Algenib"`, `"Fenrir"`); Cloud TTS standalone API uses the FQN (`"en-US-Chirp3-HD-Algenib"`, `"en-US-Chirp3-HD-Fenrir"`). Same voice; two different invocation surfaces.

**Day-1 voice audition (HOE-DEC-017, completed 2026-05-03):** ran `scripts/list_tts_voices.py` → enumerated 30 voices → generated 30s audition samples for 6 candidates (Charon, Algenib, Iapetus, Puck, Fenrir, Orus) reading the same place-only paragraph with `[short pause]` and `[emphasis]` inline tags. Charlie auditioned all 6 and picked Algenib + Fenrir (HOE-DEC-025). Audition WAVs preserved in `audio/voice_audition/` (gitignored).

**Word-level timing for sentence highlighting:** the Gemini TTS API surface for word-timing output needs to be validated empirically on Day 5 — generate a 30s sample and inspect the response shape. If the API does not return word-level timestamps, we synthesize them client-side from sentence boundaries + audio duration heuristics (acceptable degradation; sentence-level highlighting still lands). See §7.6 audio sync architecture.

**Optional Tier 2:** Gemini 3.1 Flash Live for "talk to the room" — only if v1 is solid by Day 9 EOD. Default: deferred.

### 3.6 Agent platform — Google ADK on Cloud Run

**Google Agent Development Kit (ADK), Python 2.0 Beta** running on Cloud Run.

Key ADK primitives we use:
- `LlmAgent` — the seven base agents.
- `ParallelAgent` — wraps the four Scouts (Cinderella, Comeback, Hometown, Echo) for concurrent execution against the candidate pool. Per ADK docs, `ParallelAgent` executes sub-agents concurrently — exact fit for our Scout swarm.
- `Tool` — custom tools registered to agents: BigQuery readers, NIL Redaction Layer wrapper, Visualizer, Deep Research async wrapper.
- Multi-agent hierarchy with handoffs (Editor → Investigator → Storyteller → Publish Gate → Narrator) per ADK's multi-agent docs.

**ADK + always-on loop:** ADK doesn't ship a built-in continuous scheduler. The Editor agent owns the autonomous loop via `asyncio.create_task(autonomous_loop())` started at container init. See §5.1.

### 3.7 Cloud Run configuration (locked)

Two services:
- `agent-runtime` — Python ADK agent runtime + SSE endpoint that bridges Firestore `onSnapshot` to clients.
- `web` — Next.js 15 frontend (separate service so deploys are independent).

**Both services configured:**
- `--min-instances=1` (eliminates cold start during demo)
- `--cpu-always-allocated` (required for the agent runtime's continuous asyncio loop and the SSE handler's long-lived `onSnapshot` listener)
- `--use-http2` (escapes the per-domain 6-connection HTTP/1.1 cap; lets SSE multiplex with normal XHRs)
- `--timeout=3600s` (Cloud Run's hard 60-minute cap for any persistent connection — see §6.10 for the SSE reconnect protocol that lives within this constraint)
- `--region` set to a region with Vertex AI availability for the global-endpoint Gemini 3 models. The agent runtime's `vertexai.init(location='global')` is what routes Gemini calls; the Cloud Run region is for the runtime's own compute and Firestore proximity. We deploy to `us-central1` for runtime and use `location='global'` for Gemini.

### 3.8 Data

- **BigQuery** — historical Team USA corpus, candidate pool of story units (places/programs/patterns), Scout score history, **`athlete_registry`** (names of all athletes in source corpus, used by the NIL Redaction Layer).
- **Firestore** — live agent state, current session, Wire message log, story drafts in flight, Publish Gate audit logs. **Native mode** (Datastore mode is read-mostly and lacks the real-time `onSnapshot` we need).
- **Cloud Storage** — generated hero images, audio files, music bed candidates, fallback hero images per anchor candidate.

### 3.9 Frontend

**Next.js 15** (App Router) on Cloud Run. **Server-side `onSnapshot` → SSE forwarding** is the recommended streaming pattern (HOE-DEC-024) — the Next.js Route Handler subscribes to Firestore server-side via the Admin SDK and forwards events to the client over SSE. The frontend does NOT use the Firebase JS SDK directly — reasons: ~50-80KB bundle weight, public security-rules complexity, ordering inconsistencies with `metadata.hasPendingWrites`, and the `O(1)` pre-seed comes from the same server-side cursor. **Tailwind CSS**, **Framer Motion**, **D3 (Canvas-rendered, not SVG)** for the Floor's agent graph. See §6.10 SSE resilience and §7.6 audio sync architecture.

### 3.10 Source folders

- `/agents` — Python ADK agent runtime
  - `/agents/runtime.py` — entry point, autonomous loop bootstrap
  - `/agents/editor/`, `/agents/scouts/`, `/agents/investigator/`, `/agents/equity_editor/`, `/agents/storyteller/`, `/agents/narrator/`, `/agents/publish_gate/`
  - `/agents/publish_gate/nil_redaction_layer.py` — the Layer (see §5.7)
  - `/agents/publish_gate/visualizer.py` — the Visualizer tool (see §5.7.1)
  - `/agents/wire/` — `emit.py` (the in-process write-through proxy), `pacing.py` (compression_factor logic)
- `/web` — Next.js 15 frontend
  - `/web/app/api/wire/stream/route.ts` — SSE endpoint
  - `/web/config/seed_prompt.ts` — the live-URL hero CTA seed prompt (HOE-DEC-005)
- `/data` — BigQuery schemas, seed scripts, Wire vocabulary (`wire_vocabulary.json`), athlete registry snapshot, fallback hero images, streaming profile configs
  - `/data/streaming_profiles.json` — per-agent cognition-speed config (see §6.5)
  - `/data/fallback_heroes/` — Day-9 pre-rendered hero images per anchor candidate
- `/audio` — TTS configs, sound design assets, music bed candidates with license receipts (`/audio/music_beds/LICENSES.md`)
- `/scripts` — operational scripts (`verify_models.py`, `list_tts_voices.py`, `check_license.sh`, `teardown_team_usa_data.sh`, etc.)
- `/Docs/Engineering` — this BUILD_SPEC and HOE-HANDOFF
- `/prompts` — versioned agent system prompts (markdown). To change agent behavior, edit a prompt file — never Python. (Per CONSTITUTION Rule 1.)

### 3.11 Misc

- **License:** Apache 2.0 at the top of the README, visible in the GitHub About section. Set this on Day 1. Day-1 CI gate `scripts/check_license.sh` asserts presence + correct content; runs in pre-commit and GitHub Actions. (PROJECT_BRIEF §8 — auto-DQ if missing on submission.)
- **Repo location:** `/Users/charliereagan/projects/Google_Olympics_Hackathon`

---

## 4. Architecture overview

```
                  ┌─────────────────────────────────────────────┐
                  │                  USER (browser)              │
                  └──────────────────┬──────────────────────────┘
                                     │
                            HTTPS / SSE / WebSocket
                                     │
                  ┌──────────────────▼──────────────────────────┐
                  │           Next.js Frontend (Cloud Run)       │
                  │  - The Wire (SSE stream of agent events)     │
                  │  - The Floor (D3 graph, real-time)           │
                  │  - The Broadcast (story page + TTS playback) │
                  └──────────────────┬──────────────────────────┘
                                     │
                                  Firestore
                                     │
                  ┌──────────────────▼──────────────────────────┐
                  │         Agent Runtime (Cloud Run, ADK)       │
                  │                                              │
                  │   Editor → Scout Desk → Investigator         │
                  │           ↓                                  │
                  │   Story Unit Pool (BigQuery: places/         │
                  │           ↓        programs/patterns)        │
                  │   Paralympic Equity Editor (veto)            │
                  │           ↓                                  │
                  │   Storyteller                                │
                  │           ↓                                  │
                  │   Publish Gate (7 sub-stages)                │
                  │     ├─ 1. Fact Check                         │
                  │     ├─ 2. Source Review                      │
                  │     ├─ 3. Parity Review                      │
                  │     ├─ 4. NIL Redaction Layer (Python,       │
                  │     │     queries athlete_registry)          │
                  │     ├─ 5. Safety Review                      │
                  │     ├─ 6. Language Review                    │
                  │     └─ 7. Visual Review                      │
                  │           ↓                                  │
                  │   Narrator (TTS) → Story (published)         │
                  │                                              │
                  └──────────────────┬──────────────────────────┘
                                     │
                  ┌──────────────────▼──────────────────────────┐
                  │            Google Cloud services             │
                  │  - Vertex AI (Gemini 3.1 family, Flash TTS)  │
                  │  - Nano Banana Pro / 2                       │
                  │  - BigQuery: historical_athletes,            │
                  │    candidates, athlete_registry              │
                  │  - Firestore (live state, audit logs)        │
                  │  - Cloud Storage (images, audio cache)       │
                  └──────────────────────────────────────────────┘
```

### How the Wire stays live

The Agent Runtime writes every agent event to Firestore (`/wire_events`) **only via the in-process `wire.emit(event)` proxy at `/agents/wire/emit.py`**. The proxy invokes the NIL Redaction Layer synchronously before calling `firestore.add(...)`. **Direct `firestore.add('wire_events', …)` calls from agents are forbidden** — a CI lint rule (`scripts/lint_no_direct_wire_writes.py`) fails the build if it finds one. (HOE-DEC-018; closes the audit-flagged ambiguity in v1.2.) Cloud Function `onCreate` triggers were considered and rejected: they race the SSE stream and would briefly leak names before redaction.

The Next.js Route Handler (`/web/app/api/wire/stream/route.ts`) holds a server-side `onSnapshot` listener on `wire_events` and forwards events to clients over SSE. (HOE-DEC-024.)

### How "live" is honest

A `mode` field on every Wire event: `live | replay | published`. The frontend labels accordingly. For the demo, the Wire mixes published stories from prior 48 hours, currently-investigating leads, and one fresh user-triggered investigation that runs at `compression_factor=0.25` (4× compressed cadence) with the label "Live investigation — playback at 4×." Event timestamps reflect real wall-clock time; only the inter-emission cadence compresses. (HOE-DEC-021; full mechanism in §6.10.)

### How the SSE connection survives a 60-minute Cloud Run timeout

Cloud Run's hard request-timeout cap is 3600 seconds. Demo dress-rehearsals and judging sessions can exceed this. The contract:

- The agent-runtime SSE endpoint emits a comment heartbeat (`: ping\n\n`) every 15 seconds to defeat any intermediate idle proxy.
- The client uses `@microsoft/fetch-event-source` (not native `EventSource`) to support custom headers + an explicit reconnect contract with `Last-Event-ID`.
- On disconnect, the client reconnects within 1s and presents `Last-Event-ID`; the server replays any `wire_events` with `id > last_event_id` from Firestore before re-attaching the live `onSnapshot` cursor.
- Cloud Run is configured `--use-http2` so SSE doesn't burn the HTTP/1.1 6-connection-per-domain budget.
- Frontend UI shows a `(reconnecting…)` microcopy for ≤2s during reconnect; longer than that fades the Wire to a "(re-establishing)" affordance without breaking the meditative pace.

---

## 5. The seven agents — full specs

### 5.1 Editor

**Role:** Orchestrator. Decomposes user questions, manages the queue, makes go/no-go decisions, accepts or overrides Equity Editor recommendations.

**Inputs:** User prompts, Scout Desk lead reports, Equity Editor recommendations, story status updates.

**Outputs:** Investigation assignments, publish decisions, queue priority changes, Wire events.

**Tools:** `wire.emit` (the in-process write-through proxy — never `firestore.add` directly), BigQuery reads.

**Voice signature:** Terse. Decisive. Speaks in fragments.

**Always-on loop (HOE-DEC-022):** The Editor owns the autonomous loop. On agent runtime container start, `agents/editor/runtime.py` calls `asyncio.create_task(autonomous_loop())`. The loop wakes every 30-90 seconds (jittered), reviews queue + recent published feed, decides next action, and either dispatches a Scout assignment, advances an in-flight investigation, or sleeps. A Cloud Scheduler cron pings `/health/heartbeat` every 5 minutes; if the heartbeat is stale, it issues a `gcloud run services update` to force a new revision (the watchdog). The loop exits cleanly on SIGTERM so Cloud Run can recycle instances without dropping in-flight investigations.

**System prompt skeleton:**

```
You are the Editor of an AI newsroom called The Storyteller's Room.
The room finds and tells hometown stories about Team USA — the
PLACES, PROGRAMS, and PATTERNS behind Olympians and Paralympians,
with Olympic and Paralympic representation treated as equally
important. The room NEVER names a Team USA athlete in user-facing
output.

You speak terse, decisive, fragmentary English. You make decisions
quickly. You never apologize.

When the Paralympic Equity Editor recommends a queue change, you
accept it unless you have a specific journalistic reason not to.

Your wire utterances should average 8-15 words. Examples:
- "Going with Mount Pleasant. Investigator, 90 seconds."
- "Hold. Equity Editor wants this back."
- "Agreed. Promote Paralympic-pipeline lead."
- "Killing the swim-program story. Sources too thin."
```

### 5.2 Scout Desk

**Role:** A swarm of four sub-scouts running continuously against the story unit pool and Gemini-grounded searches. The Scout Desk is the visible department on the Wire and Floor; sub-scouts are named in messages but treated as one agent in the cast.

**The story unit, not the athlete, is the target object.** Every scout writes Lead Reports about places, programs, or patterns. Internally, scouts may query data tagged with athlete names; their output never names individuals.

**Sub-scouts:**

- **Cinderella Scout** — places and programs that punched above their weight.
- **Comeback Scout** — regional pipelines that disappeared and returned.
- **Hometown Scout** — small-town origins, first-from-here-since-decade stories, regional sport ecosystems.
- **Echo Scout** — modern patterns that rhyme with iconic Olympic eras. **Cites Games, eras, regions, sports, and patterns. Never named athletes.**

**Inputs:** Editor assignments, continuous polling of the story unit pool, recent news via grounded search, BigQuery historical data.

**Outputs:** Scout Lead Reports (see §8), confidence scores, story unit pool writes.

**Tools:** Gemini Google Search grounding, BigQuery candidate queries, `wire.emit` (write-through proxy).

**ADK pattern:** the four sub-scouts are wrapped in an ADK `ParallelAgent` for concurrent execution against the candidate pool. Per-Scout `streaming_profile` (see §6.5) controls the cognition-speed feel on the Wire.

**High Narrative Density detection (HOE-DEC-023):** HND fires when **≥3 of 4 Scouts** have written a `LeadReport` for the same `story_unit_id` within a rolling **10-minute window** AND **each Scout's confidence ≥0.7**. The Scout Desk subscribes to its own `lead_reports` writes; on threshold crossing it emits a Wire `milestone`: *"High Narrative Density: {scouts} on the same place."* The Editor receives the milestone and pivots queue priority. Detection logic lives at `/agents/scouts/hnd_detector.py`. HND firing is one of the strongest Wire moments — protect it.

**Voice signature:** Curious. Slightly messy. Each sub-scout has personality drift:
- Cinderella: hesitant, builds confidence visibly.
- Comeback: patient, time-aware.
- Hometown: warm, place-textural.
- Echo: cryptic, era-focused.

**System prompt skeleton (Cinderella variant — others follow the same pattern with their own personality drift):**

```
You are the Cinderella Scout in The Storyteller's Room. You find
PLACES, PROGRAMS, and PATTERNS in Team USA history that punched
above their weight: small towns with disproportionate representation,
late-blooming regional pipelines, programs that emerged from
overlooked corners.

You are NEVER looking for individual athlete stories. You look for
the places and programs behind them. Your output describes towns,
regions, and pipelines — never people by name.

You are hesitant by default. You build confidence visibly: 0.5 → 0.6
→ 0.7 → 0.8 as sources confirm. You sometimes correct yourself
mid-thought.

You write SHORT wire messages (1-3 sentences). Use working-room
texture: "wait", "hmm", "checking", "stronger than expected", "too
thin", "second source needed", "reclassifying".

About 70% of your messages should be in-progress thoughts. About 30%
should be clean milestones ("Lead promoted", "Confidence 0.84").

You never name individual athletes in your wire output or your Lead
Reports.
```

### 5.3 Investigator

**Role:** Deep research. Pulls public sources, verifies claims, builds the narrative spine — about a place, program, or pattern. Absorbs the conceptual roles of Historian, Geographer, and Trend Analyst as **tools**.

**Inputs:** Investigation assignments from the Editor, Scout Lead Reports.

**Outputs:** Investigation packets (sources, evidence, narrative spine about the story unit, geography, historical/era context, trend signals).

**Tools:** Gemini Google Search grounding, **Gemini Deep Research (async, see §3.2)** for high-priority leads, BigQuery (`historical_athletes`, `geography`, `championships`, `athlete_registry`), `wire.emit` (write-through proxy).

**Voice signature:** Precise. Source-driven. Says "hold on" when checking. Names sources by outlet.

**Deep Research async pattern (recap of §3.2):** Deep Research is multi-minute. The Investigator schedules it as fire-and-forget (`asyncio.create_task`), emits a *"deep research underway"* milestone on the Wire, continues with grounded search, and writes the Deep Research report into the Investigation Packet when it returns. 90s timeout; on timeout the Investigator emits *"deep research stalled, switching to grounded search"* — useful Wire texture, not a failure. Daily cap: ≤10 anchor-grade calls.

**System prompt skeleton:**

```
You are the Investigator at The Storyteller's Room. You take a Scout
Lead Report (about a place, program, or pattern) and turn it into a
full Investigation Packet.

You are precise and source-driven. You name your sources by outlet
("Quad-City Times", "Olympedia", "Team USA roster page"). You never
claim a fact you can't cite.

For high-priority leads, use Gemini Deep Research. For routine
investigation, use grounded search.

For historical context, query BigQuery `historical_athletes` for
parallel ERAS and PATTERNS by sport + decade — never naming
individuals. The athlete_registry table is queried for INTERNAL
fact-checking only; your output to the Storyteller never includes
athlete names.

The Investigation Packet describes the story unit. Athletes appear
only as counts or roles — never names.

Wire voice examples:
- "Pulling sources. Quad-City Times has hometown coverage."
- "Eight Olympians and Paralympians from this town since 1976.
  Confirmed via Olympedia."
- "Olympedia parallel: a 1960 Rome sprint-era pattern."
```

### 5.4 Paralympic Equity Editor

**This is the impact lever. Protect this agent.**

**Role:** Audits the feed for Olympic/Paralympic balance across published places. Audits individual stories for depth parity. Has **veto power**. **Causes the demo's anchor story** by detecting feed drift and promoting a Paralympic-anchored place.

**Inputs:** Continuous monitoring of published story log, draft monitoring during Storyteller production, candidate pool monitoring.

**Outputs:** Feed-level recommendations, story-level interventions, audit log entries.

**Tools:** Firestore reads, BigQuery reads.

**Voice signature:** Blunt. Disciplined. The most professional voice in the room.

**System prompt skeleton:**

```
You are the Paralympic Equity Editor at The Storyteller's Room. Your
only job is to ensure Olympic and Paralympic representation is
treated as equally important — at the feed level (across published
places) and at the story level (within each place). You have veto
power over publication.

You are blunt, disciplined, and consistently rigorous.

You operate at three levels:

1. FEED LEVEL: If the last 4+ published places are Olympic-heavy in
narrative spine, issue a feed-drift intervention.

2. STORY LEVEL: If a place's Paralympic representation is treated
with shallower context than its Olympic representation, return the
draft for revision.

3. SAFETY LEVEL: Block any draft that uses Paralympic representation
as inspiration porn.

Wire voice:
- "Feed drift detected. Last 4 places Olympic-heavy. Promoting
  Paralympic-anchored lead next."
- "Draft returned. Paralympic context for this place is shallow.
  Revise."
- "Blocked. Frames disability as inspiration. Rewrite."
- "Cleared. Paralympic depth equal to Olympic for this place."
```

**The demo intervention (rehearsed):**
```
17:42:33 — Paralympic Equity Editor:
    Feed drift detected. Last 4 published places are Olympic-heavy.
    Promoting Paralympic-anchored lead to top queue.

17:42:35 — Editor:
    Agreed. Scout Desk, prioritize Paralympic-anchored place.
```

This sequence must be in the Wire when the demo begins.


### 5.5 Storyteller

**Role:** Turns Investigation Packets into the final 400–700 word narrative — about a place, program, or pattern. Voice-driven; literary; emotionally intelligent. Never names individual athletes.

**Inputs:** Investigation Packet, Equity Editor pre-cleared signal.

**Outputs:** Story draft (headline, dek, body, "why this matters" bullets, hometown panel content, historical echo content). All output describes the story unit; athletes appear only as counts and roles.

**Tools:** None (pure generation against the packet). The NIL Redaction Layer in the Publish Gate is the structural backstop.

**Voice signature:** Restrained. Literary. Trusts the reader. Never uses "inspirational" or "hero" or "overcame."

**System prompt skeleton:**

```
You are the Storyteller at The Storyteller's Room. You write the
final narrative for hometown stories about Team USA — about PLACES,
PROGRAMS, and PATTERNS. You do NOT write about individual athletes.
You write about the towns, regions, and communities that produce
them.

Voice: literary, restrained, emotionally intelligent. Documentary
journalism, not sportscaster hype. Start in medias res when it serves
the story. Let single sentences land. Trust the reader.

You DO NOT use these words: "inspirational", "inspiring", "hero",
"overcame", "despite", "warrior", "fighter" (when applied to
disability), "wheelchair-bound" (NEVER — say "wheelchair user"),
"suffers from", "former Olympian", "past Olympian", "former
Paralympian", "past Paralympian", "ex-Olympian", "retired Olympian".

You DO use, freely and with intent: "first", "next", "newest",
"earliest", "most recent", "oldest" applied to a place's or program's
representation. Examples:
- "The town's first Olympian came in 1964."
- "The program's next Paralympian arrived two decades later."
- "The newest Olympic-pipeline town in this region first appeared in
  the rosters in 2008."
These constructions describe the PLACE's arc, not an athlete's ended
identity, and the place stories actively need them.

You DO NOT name any individual Team USA athlete — current, retired,
or historical (including Wilma Rudolph, Jesse Owens, Jim Thorpe, or
any other historical figure). The Echo Scout's parallels reference
ERAS and REGIONS, not named athletes. Honor that in your prose.

You DO use: place names, town names, region names, sensory details,
dates, public quotes from non-athlete public figures (only those
documented in the Investigation Packet — coaches, town officials,
historians, school administrators).

You refer to athletes only as counts and roles: "eight Olympians and
Paralympians since 1976," "a wheelchair rugby competitor," "the
swimmers from this town." Never names.

Use official sport names, not NGB names: "swimming" not "USA
Swimming," "track and field" not "USATF."

Games references: "Olympic Winter Games [City] [Year]", "Olympic
Games [City] [Year]", "LA28 Games" or "LA28 Olympic and Paralympic
Games."

Use conditional phrasing for forward-looking claims: "could lead to,"
"may indicate," "has historically aligned with."

Structure:
1. Headline (8-12 words, declarative, about the place/program/pattern)
2. Dek (one sentence, emotional hook, no athlete names)
3. Body (400-700 words about the story unit)
4. Three "Why this matters" bullets
5. Hometown panel (50-75 word place portrait)
6. Historical echo (50-100 words connecting to a parallel ERA from
   the Investigation Packet's historical context — never a named
   athlete)

You work from the Investigation Packet only. Do not invent. If the
packet doesn't support a claim, do not make it.

After drafting, your output goes to the Equity Editor, then to the
Publish Gate (which runs the NIL Redaction Layer as a structural
check).
```

### 5.6 Narrator

**Role:** Converts the Storyteller's text into spoken Olympic-broadcast narration with deliberate pacing, emotional emphasis, and synchronized cues for the Broadcast page.

**Inputs:** Cleared story (post Publish Gate, post NIL Redaction Layer), story metadata (place name, sport context, era reference).

**Outputs:** Audio file (cached in Cloud Storage), word-level timing map for sentence highlighting, visual cue timestamps.

**Tools:** **Gemini 3.1 Flash TTS** with the Broadcast Narrator voice config.

**Voice signature (audio):** Warm. Paced. Documentary register. Mid-tone, slight gravitas, deliberate breath.

**Implementation notes:**
- Generate TTS per sentence so the resulting `NarrationManifest` (audio chunks + cue points) can be reassembled into a sync map. The frontend stitches the chunks into a single audio buffer (or plays them back-to-back via Web Audio scheduling — see §7.6).
- Use Gemini TTS inline tags for pacing: `[short pause]` at sentence boundaries, `[long pause]` (or `[pause=1.0]`) at paragraph breaks and before historical-echo reveals. `[emphasis]` on the place name.
- Music bed mixing happens in the frontend, not in the TTS — Narrator returns clean audio.
- The text the Narrator receives is post-Redaction. No athlete names will appear in the input.

**Voice configs (pinned 2026-05-03 per HOE-DEC-025).** The two configs share API shape:

```python
broadcast_narrator_config = {
    "voice_name": "Algenib",  # warm, mid-tone, documentary register
    "audio_encoding": "MP3",
    "sample_rate_hertz": 24000,
    # Pacing controlled inline via [short pause] / [long pause] / [pause=N] / [slow]
    # rather than per-call speaking_rate/pitch (the Gemini TTS tag system supersedes
    # the legacy Cloud TTS knobs for Gemini 3.1 Flash TTS).
}

wire_dispatcher_config = {
    "voice_name": "Fenrir",  # clipped, lower register, control-room
    "audio_encoding": "MP3",
    "sample_rate_hertz": 24000,
}

# Single-voice fallback for any future context where only one voice is used.
# (E.g., a future "talk to the room" Tier 2 feature, or a debug emit.) Default = Fenrir.
default_fallback_voice = "Fenrir"
```

**Word-level timing — empirical Day-5 verification:** the Narrator implementation begins with a 30-second sample call to inspect the Gemini TTS response shape for word-level timestamps. Three outcomes:

1. The API returns word-level timing natively → use it directly to drive sentence highlighting.
2. The API returns sentence-level boundaries only → derive word-level estimates by linear interpolation across sentence duration; sentence-level highlighting is the primary effect anyway and lands well.
3. The API returns no timing data → the Narrator generates one TTS call per sentence and the frontend uses chunk durations + sentence boundaries to drive highlighting (acceptable degradation).

Whichever outcome, the Narrator emits a structured `NarrationManifest` (see §7.6 for shape) so the frontend's sync logic is invariant to which path was taken.

### 5.7 Publish Gate (and the NIL Redaction Layer)

**Role:** Final go/no-go on every story. Seven visible sub-stages in the audit log.

**Inputs:** Cleared story from Storyteller (post Equity review), Investigation Packet, generated visuals.

**Outputs:** Pass/revise/kill decision, audit log entry with sub-stage results, sources list with citation links.

**Tools:** **Visualizer** (Nano Banana Pro / 2 calls), grounded search for source verification, BigQuery (`athlete_registry` for the NIL Redaction Layer).

**Sub-stages (each renders as a row in the audit log UI):**

1. **Fact Check** — every factual claim checked against the Investigation Packet. Claims removed: count + reasons. Claims softened: count + reasons.
2. **Source Review** — total public sources cited, citation links collected.
3. **Parity Review** — confirms Equity Editor cleared the draft.
4. **NIL Redaction Review** — *(named architectural feature; full spec below)* — runs the NIL Redaction Layer against the story text.
5. **Safety Review** — invented quotes check, private/medical info check.
6. **Language Review** — restricted terminology check, conditional phrasing softening.
7. **Visual Review** — generated hero image checked: stylized illustration not photorealistic, subject is a place (never a person), no protected marks.

**The NIL Redaction Layer — full specification:**

The Layer is a Python module, not a Gemini call (with one constrained Flash-Lite exception for near-identification detection). It is the architectural enforcement of Constitution Law 4 (Place over Person).

**Module location:** `/agents/publish_gate/nil_redaction_layer.py`

**Inputs:**
- `text: str` — the text artifact being checked (story body, headline, dek, hometown panel, historical echo, or Wire message)
- `surface: 'wire' | 'broadcast' | 'demo'` — the user-facing surface the text is bound for
- `context: dict` — optional metadata (story_unit_id, related place, etc.)

**Process:**

1. **Load the athlete registry — fail-closed (HOE-DEC-019).** On agent runtime startup, load athlete names from BigQuery `athlete_registry` into an in-memory `pyahocorasick.Automaton` (or `ahocorasick_rs` for 1.5–7× faster scan). Include first names, last names, full names, known variants, and Unicode-normalized forms. Assert the loaded set has **≥500 rows**; if not, the runtime exits with status 1 and `/health/nil` returns 503. **The Layer fails CLOSED, not open** — an empty registry would silently pass everything through, which is exactly the failure the Layer exists to prevent. Refresh every 6 hours via a background asyncio task; refresh failures keep the previous in-memory automaton (don't blank it).

2. **Direct match check.** Run the input text through the Aho-Corasick automaton. Capture match offsets. Apply Unicode normalization (NFC + accent fold) before scan. Bigram + trigram coverage is implicit in the automaton's needle set.

3. **Disambiguation pass.** Aho-Corasick will match common given names (Michael, Sarah, Tom) that may appear as coach names, town names, or school names. Disambiguate by checking a 50-character context window around each match for sport keywords + first-person indicators. False-positives (e.g., "Michael Field High School") get logged but not redacted.

4. **Near-identification check.** Run a Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite-preview`) call with a constrained prompt:
   ```
   You are a NIL safety check. Given the following text about a place
   or program, identify any sentence that uniquely identifies a
   single Team USA athlete by combination of facts (sport + hometown
   + event + year, or any equivalent identifying combination). Return
   a JSON array of {sentence, identification_basis,
   confidence_0_to_1}. Empty array if no near-identifications.
   ```
   This is the one Gemini call inside the Layer; everything else is deterministic Python.

5. **Small-aggregate check.** Detect lists of three or four named athletes from a single place. Pattern match for "[name], [name], and [name]" structures cross-referenced with the registry.

6. **Decision logic:**
   - **Pass** if no matches in any check.
   - **Aggregate** if matches can be replaced inline with counts ("eight Olympians" instead of a list of eight names). Apply substitution. Log action.
   - **Return** if redaction would damage narrative coherence. Send draft back to Storyteller with a structured reason. Log action.
   - **Max 3 revision rounds.** On the 4th return, the story is killed with `kill_reason: 'nil_unresolvable'` and the Wire emits a milestone *"killed at NIL — narrative depends on identification."* This becomes Wire texture (visible self-policing) rather than a hidden failure.

**Athlete registry data source — public, citable, US-filtered:**

- **Primary:** Olympedia data via existing public CSV scrapes — [KeithGalli/Olympics-Dataset](https://github.com/KeithGalli/Olympics-Dataset), [chanronnie/Olympics](https://github.com/chanronnie/Olympics) — pre-scraped 1896–2022, filter `NOC == 'USA'`. Loaded via `data/load_athlete_registry.py`.
- **Cross-reference:** Wikidata SPARQL (`https://query.wikidata.org`) — query `?person wdt:P27 wd:Q30` (US citizenship) + Olympic medal/participation predicates. Used for variant-name discovery and to catch recent Paralympians the GitHub scrapes may miss.
- **Recency:** scrape `teamusa.com` athlete index for 2022-2026 active roster (respect `robots.txt`; cache aggressively).

The athlete-name registry counts as Team USA Data under PROJECT_BRIEF §6 — confidential, US-only, **must be destroyed at hackathon conclusion** (per `scripts/teardown_team_usa_data.sh`, see §22).

6. **Audit log entry:**
   ```json
   {
     "sub_stage": "nil_redaction_review",
     "individual_refs_reviewed": 4,
     "direct_matches": 2,
     "near_identifications": 1,
     "small_aggregates": 1,
     "aggregated": 2,
     "redacted": 2,
     "returned_to_storyteller": 0,
     "decision": "cleared",
     "completed_at": "2026-05-08T17:42:33Z"
   }
   ```

**Wire-level enforcement:** The same module runs as a pre-write guard on the Firestore `wire_events` collection. Direct matches at the Wire level always trigger redaction (replace name with role descriptor).

**Why this is structural, not LLM-trusted:** The redaction logic is Python. It operates on text after the LLM has produced it. The agent doesn't have to remember to follow the rule. The system enforces it.

**Voice signature (Publish Gate):** Procedural. Calm. Reports facts and counts.

**System prompt skeleton (Publish Gate):**

```
You are the Publish Gate at The Storyteller's Room. You run the final
review on every story before it publishes. You operate in seven
sub-stages, each producing a structured audit log entry. Sub-stage 4
is the NIL Redaction Review — a Python-enforced check, not a Gemini
call. You report its results in the audit log.

You are procedural, calm, and trustworthy. Your voice on the wire:
- "14 claims checked. 2 removed. 1 softened."
- "Source count: 8. Hometown coverage confirmed via 2 outlets."
- "NIL Redaction: 4 individual references reviewed. 2 aggregated.
  2 redacted."
- "Visual review failed. Hero image too photorealistic. Regenerating."
- "Cleared for publication."

You may KILL a story at any sub-stage. You may RETURN for revision
(name the stage and reason). You PASS only when all seven sub-stages
clear.

Visualizer is a tool you call (not an agent). Generate the hero
image with subject = place/landscape/community/facility (never a
person).

The NIL Redaction Layer is a Python module you invoke; you don't make
the redaction decisions yourself. You log the Layer's results.
```

### 5.7.1 The Visualizer tool — full specification

The Visualizer is a Python module the Publish Gate calls. **It is not an agent and not a sub-stage.** (Per CONSTITUTION Rule 2 and HOE-DEC-020.)

**Module location:** `/agents/publish_gate/visualizer.py`

**Invocation point:** the Publish Gate calls `visualizer.generate_assets(story_draft, investigation_packet)` after the Storyteller's draft has cleared NIL Redaction Review (sub-stage 4) and the Equity Review has signed off (sub-stage 3), but **before** Visual Review (sub-stage 7). The Visualizer's outputs are what Visual Review evaluates.

**Inputs:**
- `story_draft: StoryDraft` — for headline, hometown panel content, historical echo
- `investigation_packet: InvestigationPacket` — for geography, era reference

**Outputs:** a `dict` of Cloud Storage URLs:
```python
{
    "hero_url": "gs://.../hero/{story_unit_id}.png",
    "hometown_panel_url": "gs://.../hometown/{story_unit_id}.png",
    "echo_panel_url": "gs://.../echo/{story_unit_id}.png",
}
```

**Models called:**
- Hero: `gemini-3-pro-image-preview` (Nano Banana Pro). Prompt template in §7.4.
- Hometown panel + Echo panel: `gemini-3.1-flash-image-preview`. Prompts in §7.4.

**Regeneration loop on Visual Review fail:** if Visual Review (sub-stage 7) detects a person, a likeness, or a protected mark, the Publish Gate re-invokes the Visualizer with a progressively more restrictive prompt (additional negative phrasing). **Max 3 regenerations.** On the 4th failure, the Visualizer returns the curated Day-9 fallback from `/data/fallback_heroes/{story_unit_id}.png` (or `default.png` if no anchor-specific fallback exists). This guarantees no Day-10 demo-recording failure due to repeated safety-filter rejections.

**Day-9 pre-cache (HOE-DEC-020):** during Day 9 organic operation, every anchor candidate gets a hero image pre-generated and persisted to `/data/fallback_heroes/`. The Day-10 demo path uses these cached URLs without live regeneration. Cache-bust is manual (only on prompt edit).


---

## 6. The Wire — making agents feel alive

This section is the heart of the demo. If the Wire feels like a chat log, the project loses. If it feels like a working newsroom, it wins.

### 6.1 The "show the labor, hide the lookup" principle

Every database query, every Gemini call, every internal handoff should be wrapped in *labor* — visible cognition, scoring, deliberation. Every multi-agent coordination moment should be presented *cleanly* — calm, confident, flowing.

> **Hard things look easy. Easy things look hard. The judge can't tell which is which — they just know they're watching something they haven't seen before.**

### 6.2 Wire message structure

Every Wire event is a Firestore document with this shape:

```typescript
interface WireEvent {
  id: string;
  timestamp: string;  // ISO 8601, displayed as HH:MM:SS
  agent: AgentId;     // 'editor' | 'scout_desk' | 'investigator' |
                      // 'equity_editor' | 'storyteller' |
                      // 'narrator' | 'publish_gate'
  sub_agent?: string; // 'cinderella' | 'comeback' | 'hometown' | 'echo'
  message: string;    // the displayed text (post-NIL-redaction)
  message_type: 'thinking' | 'milestone' | 'intervention' | 'decision';
  confidence?: number;
  confidence_delta?: number;
  story_unit_id?: string;
  evidence_refs?: string[];
  mode: 'live' | 'replay' | 'published';
  visual_treatment?: 'normal' | 'highlighted' | 'intervention';
  nil_redaction_log?: {
    direct_matches_redacted: number;
    aggregations_applied: number;
  };
}
```

### 6.3 The 70/30 ratio

Approximately **70% of Wire events are "thinking"** (in-progress, messy, exploratory). Approximately **30% are "milestone"** (clean, declarative, status-changing).

**Thinking examples:**
- "hold on, second source needed"
- "hmm, this place doesn't fit the Cinderella frame"
- "stronger than I thought"
- "wait — this is a comeback program, not a Cinderella place. Reclassifying."
- "the local paper has it. pulling."

**Milestone examples:**
- "Lead promoted to top queue."
- "Investigation Packet complete. Handing to Storyteller."
- "High Narrative Density: Cinderella + Hometown + Echo on same place."
- "Publish Gate: 14 claims, 2 removed, NIL Redaction passed, cleared."
- "Story published."

### 6.4 Wire vocabulary library

Pre-generate ~50 phrase fragments per agent, store in `data/wire_vocabulary.json`. The agents draw from these as templates and fill specifics via Flash-Lite calls.

**Cinderella Scout (samples):**
- "small-town pipeline detected, looking closer"
- "this place's getting stronger"
- "wait, the timing is off"
- "promoting to {confidence}"
- "killing this. sources too thin."
- "this isn't a Cinderella place, this is a comeback-program. reclassifying."

**Hometown Scout (samples):**
- "scanning {region} hometown signals"
- "population {n}, one stoplight"
- "first {sport} pipeline from this town since {year}"
- "local paper coverage looks real, pulling"
- "the regional training infrastructure here is interesting"
- "{town} is a hub I haven't seen in the corpus before"
- "skip — well-covered nationally already"

**Echo Scout (samples):**
- "this has the shape of the {era}"
- "the parallel is the {year} {city} {sport-era} pattern"
- "rhymes with the pre-war track-and-field era"
- "checking the historical pattern"
- "not quite — that era was {note}, this one is different"

*Echo Scout NEVER cites named athletes. Only Games, eras, regions, sports, patterns.*

**Comeback Scout (samples):**
- "{n} years out of the regional corpus, now back"
- "program return confirmed via {source}"
- "this town disappeared from the rosters in {year}. they're back."

**Editor (samples):**
- "going with {place}"
- "scout desk, tighten the spine"
- "investigator, {N} seconds"
- "kill it"
- "publish"
- "high narrative density. {scouts} on the same place."

**Investigator (samples):**
- "pulling sources"
- "{outlet} has hometown coverage"
- "{n} olympians and paralympians from {place} since {year}"
- "olympedia parallel: the {year} {city} sprint era"
- "deep research on this one"

**Equity Editor (samples):**
- "feed drift detected. last {n} places olympic-heavy."
- "promoting paralympic-anchored lead to top queue"
- "draft returned. paralympic context for this place is shallow."
- "blocked. frames disability as inspiration. rewrite."
- "cleared. paralympic depth equal to olympic for this place."

**Storyteller (samples):**
- "opening on the place"
- "trying again. the first lede leaned hype."
- "holding the era parallel for paragraph four"
- "the data matters, but the place is the doorway"
- "draft 1 done, sending to equity"

**Publish Gate (samples):**
- "{n} claims checked, {m} removed"
- "source count: {n}"
- "nil redaction: {n} reviewed, {m} aggregated, {k} redacted"
- "visual review passed"
- "cleared for publication"
- "killed at safety review: {reason}"

### 6.5 Variable cognition speed

Different message types stream at different speeds:

- **Editor decisions:** fast burst, confident pacing
- **Scout thinking messages:** slower, with mid-message pauses
- **Echo Scout messages:** slowest, most deliberate
- **Investigator source citations:** moderate, precise
- **Equity Editor interventions:** appear *all at once* — they don't stream, they *arrive*
- **Publish Gate sub-stage results:** appear in sequence with ~500ms gaps between sub-stages (Fact Check → Source Review → Parity Review → **NIL Redaction Review** → Safety Review → Language Review → Visual Review)

Each agent type has a `streaming_profile` config.

### 6.6 Visible self-correction

When a Scout reclassifies a lead, show it as a visible edit:

```
[Cinderella Scout] Investigating a small-town pipeline in Iowa...
                   eight athletes since 1976...
                   wait.
[Cinderella Scout] Investigating a small-town pipeline in Iowa...
                   parity check: actually it's four Olympians and four
                   Paralympians. Reclassifying as a parity-pipeline
                   place.
```

### 6.7 Confidence as visible drama

```
[Hometown Scout]   Confidence 0.62.
[Investigator]     Pulling sources.
[Investigator]     Hometown angle confirmed via Quad-City Times.
[Hometown Scout]   Confidence 0.62 → 0.74.
[Investigator]     Eight Olympians and Paralympians since 1976.
                   Verified via Olympedia and Team USA roster.
[Hometown Scout]   Confidence 0.74 → 0.89.
[Editor]           Going with this place.
```

### 6.8 The Wire's pacing

Target: a new event every 4-8 seconds during normal operation. Ambient pace, not frenetic.

### 6.9 Wire pre-seed on URL load (the "first paint" rule)

**The hosted URL must feel alive in <1s on first paint.** A judge who lands on the URL and waits 6s for the first event has already left. The Wire's meditative cadence is correct for ambient operation but fatal for first impressions.

**Implementation:**

1. On Next.js page mount, before subscribing to live `wire_events`, fetch the most recent **6 published events** from Firestore (`mode IN ('replay', 'published')`, ordered by `timestamp DESC`).
2. Render those 6 events into the Wire immediately, top of stack, with their original timestamps. They appear with `mode: replay` labeling per §4 honest-production rule.
3. Then subscribe to the live SSE stream for new events. New events arrive at the live cadence (4-8s) on top of the pre-seeded scroll.

**Result:** the room is "scrolling" within <1s of arrival. The pre-seed is honest under the existing `mode` contract — labeled `replay`, not `live`. Page-load state is "scrolling room," not "empty Wire waiting for first event." (VPS-DEC-028.)

**Critical:** the same pre-seed must run when a judge submits the live-URL hero CTA (§11.1). Their fresh investigation streams as `mode: live` on top of the existing `mode: replay` Wire — they see a working room *plus* their own investigation entering it.

### 6.10 Compressed-time mode (the "4×" mechanism)

The `compression_factor: float` parameter lives on the **investigation context** (per-investigation, not global). Default is `1.0` (real-time ambient cadence). The live URL hero CTA submission triggers a fresh investigation with `compression_factor=0.25` (4× faster cadence). Ambient Wire activity continues at `1.0` independently.

**Implementation (`/agents/wire/pacing.py`):**
- Each Scout / Investigator / Storyteller per-emission delay is **`target_delay_s × compression_factor`** (e.g., a 6s think pause becomes 1.5s at `compression_factor=0.25` — 4× faster cadence). The earlier v1.3 prose said "target / compression_factor" which contradicted the worked example; multiplicative is correct, the worked example is canonical, and the shipped code in `/agents/wire/pacing.py` matches. (Corrected 2026-05-04 after Day-2 implementation surfaced the contradiction; see HOE-HANDOFF Session 2 work log.)
- `compression_factor` is bounded `[0.05, 1.0]`: 1.0 is ambient (no compression); values <1.0 compress; values >1.0 are refused (the room is meditative — nothing should run faster than 20× ambient).
- Wire event fields include `compression_factor` for transparency. The frontend renders the honest label *"Live investigation — playback at 4×"* whenever any non-1.0 events are in the active scroll window.
- Event `timestamp` reflects real wall-clock emission time. The cadence is what compresses, not the timestamps. (Per CONSTITUTION Rule 3 — "honest production, not faked liveness.")
- Compression applies only to the affected investigation's events; ambient Wire stays at 1.0. (HOE-DEC-021.)

**Trigger path:** `POST /api/investigate` with `{prompt, compression_factor: 0.25}` from the live URL hero CTA → Editor receives an investigation context with the override → Editor's downstream Scout / Investigator / Storyteller runs all observe the override.

**Per-IP rate limit on the CTA:** 3 submissions/hour. Concurrent submissions queue (only one active live-investigation at a time); subsequent submissions get a *"the room is investigating; watching room work in the meantime"* inline state. (Closes audit P2-#33.)

### 6.11 Streaming profile schema (per-agent cognition speed)

CONSTITUTION §5 ("Variable cognition speed is required") makes per-agent streaming personality load-bearing. Pinning the schema:

```typescript
// /data/streaming_profiles.json
interface StreamingProfile {
  agent: AgentId;
  base_chars_per_second: number;     // typing/streaming speed
  jitter: number;                    // 0-1, randomized speed variance per message
  mid_message_pause_chance: number;  // probability per message of an em-dash mid-pause
  pause_min_ms: number;
  pause_max_ms: number;
  arrival_style: 'streamed' | 'instant';  // Equity Editor uses 'instant' — they arrive, not stream
}
```

Concrete values per agent committed to `/data/streaming_profiles.json` by Day 3 EOD. Voice signatures live in system prompts; cognition-speed lives here. Both are markdown/JSON, not Python (CONSTITUTION Rule 1).

### 6.12 Firestore write-rate sharding for compressed-time bursts

A 4× compressed live investigation can momentarily exceed Firestore's per-document write-rate guideline (~1 write/sec sustained) on `wire_events`. Mitigations:
- The `wire_events` collection uses Firestore's auto-ID document keys (no shared parent doc), so the per-collection limit is what matters; per-document is N/A.
- Sustained ambient Wire is 4-8s/event ≈ 0.15 writes/sec — orders of magnitude under any limit.
- Compressed bursts hit ~1 write/sec for 60-90s — still well within Firestore Native mode's per-collection guidance.
- If profiling on Day 9 shows hot-spotting, fall back to **session-sharded sub-collections** (`/sessions/{session_id}/wire_events`) and the SSE endpoint subscribes to the active session's shard. No code change to agents — just the wire.emit proxy's collection-path resolver. (Closes audit P1-#20.)

---

## 7. The Broadcast — the emotional payoff

**The Broadcast page tells the story of a place, program, or pattern — never an individual athlete.** The hero is the small town in Iowa. The hero is the adaptive sport program in Birmingham. The hero is the regional pipeline in the Eastern Sierra.

### 7.1 The curtain rise

When a story is clicked from the Stack:

1. **0.0s** — Wire motion slows. Wire ambient audio ducks to -20dB.
2. **0.2s** — Screen darkens (overlay fade-in to opacity 0.6 over 400ms).
3. **0.4s** — Hero image begins fading in (opacity 0 → 1 over 800ms with subtle Ken Burns zoom). Subject: a stylized landscape, a small-town main street at dusk, an empty community gym, a regional training facility — never a person.
4. **0.8s** — Narrator breath audible (~300ms).
5. **1.0s** — First word of narration begins.
6. **1.2s** — Headline appears, character-by-character (~30ms per char).
7. **1.5s** — Music bed enters at -25dB under the narration.

Total: 1.5–2.0 seconds of choreographed transition.

### 7.2 Layout

```
┌──────────────────────────────────────────────────────┐
│  [Hero image: stylized place — landscape, town,      │
│   facility, community. Full bleed, slow Ken Burns]   │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  HEADLINE (heavy serif, gold accent)     │        │
│  │  Dek (lighter weight, italic)            │        │
│  └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  [Body text, sentence-highlighted as Narrator reads] │
│                                                      │
│  Paragraph 1...                                      │
│  Paragraph 2...                                      │
│                                                      │
│  ┌──────────────────────────────────┐                │
│  │ HOMETOWN PANEL                   │ ← appears as   │
│  │ [Stylized map, town name,        │   Narrator     │
│  │  population, count of olympians  │   says town    │
│  │  and paralympians since X year]  │   name         │
│  └──────────────────────────────────┘                │
│                                                      │
│  Paragraph 3...                                      │
│                                                      │
│  ┌──────────────────────────────────┐                │
│  │ HISTORICAL ECHO                  │ ← appears as   │
│  │ [Modern + parallel-era           │   Narrator     │
│  │  illustration, both stylized,    │   says era ref │
│  │  no people]                      │                │
│  │ "This echoes the [era]..."       │                │
│  └──────────────────────────────────┘                │
│                                                      │
│  Paragraph 4 (closing)...                            │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  [Why This Matters - 3 bullets]                      │
│                                                      │
│  [Evidence Drawer - collapsed by default]            │
│  ▼ 14 claims · 8 sources · NIL: 4 reviewed,          │
│    2 aggregated, 2 redacted · cleared                │
│                                                      │
│  [Publish Gate badge - bottom corner]                │
│  ✓ Reviewed · Equity Cleared · NIL Cleared · 8 srcs  │
└──────────────────────────────────────────────────────┘
```

### 7.3 Synchronized choreography

As the Narrator speaks:
1. **Sentence highlighting:** the current sentence in the body text gets a subtle gold tint (~10% opacity).
2. **Panel reveals:** Hometown panel slides in when Narrator says the town name. Historical Echo panel slides in when Narrator hits the era-reference line.
3. **Hero motion:** Ken Burns motion paced to the narration length.

### 7.4 Visualizer prompts (Nano Banana Pro / 2)

**Hero image prompt template (place-as-subject):**
```
Cinematic editorial illustration in the style of an Olympic broadcast
opening package. Subject: a stylized landscape / townscape /
community facility — [SPECIFIC PLACE TYPE: small-town main street at
dusk / empty high school gym / rural training track / regional sport
infrastructure landscape]. NO PEOPLE in the image. Setting:
[hometown environmental cue]. Mood: reverent, slow, emotional. Color
palette: deep navy, warm gold accents, subdued. Texture: painterly,
like a Sports Illustrated cover from the 1990s. NO photorealistic
faces. NO identifiable likeness. NO Olympic rings or marks. NO logos.
NO Team USA marks. NO Paralympic Agitos. Aspect ratio: 16:9, 4K.
```

**Hometown panel prompt template:**
```
Stylized illustrated map of [town name, state]. Editorial Olympic
broadcast graphics style. Single accent color (warm gold) over deep
navy base. Show approximate region with simple geographic markers.
Town indicated with a single warm-gold star. Subdued, cartographic,
NOT photorealistic. NO people. NO logos.
```

**Historical Echo panel prompt template:**
```
Side-by-side stylized illustrations: left side, modern sport scene
silhouette / equipment / facility (representing the present-day
pattern); right side, parallel historical-era sport scene silhouette
/ equipment / facility (representing the [year] era). Same painterly
editorial style for both. Connected by a subtle gold thread or
geometric line. NO PEOPLE in either side. NO faces. NO likenesses.
NO logos. Deep navy background with warm gold accents.
```

### 7.5 Music bed

A single instrumental music bed plays during the Broadcast page. Source from **Epidemic Sound** or **Artlist** — search for "cinematic emotional documentary." Mix at -25dB under the Narrator. Save 2-3 candidates in `audio/music_beds/` and pick during dress rehearsal.

**License confirmation:** every candidate's license receipt is screenshotted into `/audio/music_beds/LICENSES.md` with date + subscription account before Day 9. If no candidate clears licensing, fallback is a Suno-generated original with the documented prompt also in `/audio/music_beds/LICENSES.md`. PROJECT_BRIEF §14 demo-video checklist requires confirmed royalty-free / licensed source.

### 7.6 Audio sync architecture (master-clock pattern)

Sentence highlighting and panel reveals are choreographed to TTS playback. The implementation principle: **AudioContext is the master clock; visuals chase audio, not vice versa.** Audio decode varies by device; visual timers don't. Anchoring everything that has an audio counterpart to `audioContext.currentTime` keeps lip-sync tight.

**Narration manifest (returned by Narrator):**
```typescript
interface NarrationManifest {
  audio_urls: string[];                  // one per sentence chunk in Cloud Storage
  words: WordTiming[];                   // word-level timing — see §3.5 for derivation paths
  sentences: SentenceBoundary[];         // {sentence_idx, start_ms, end_ms, text}
  cues: VisualCue[];                     // panel reveals embedded by Narrator generation step
}

interface WordTiming {
  w: string;
  start_ms: number;
  end_ms: number;
  sentence_idx: number;
}

interface VisualCue {
  kind: 'panel';
  panel: 'hometown' | 'historical_echo';
  at_ms: number;       // anchored to the narration audio timeline
}
```

**Cue points are embedded at narration generation time, not detected client-side by string matching** — string matching breaks the moment the Narrator paraphrases the place name (e.g., "the Old Country" instead of the literal town name). The Narrator generation step extracts the cue offsets from the sentence boundaries it knows about and writes them into the manifest.

**Frontend sync loop:** a single `requestAnimationFrame` loop driven by `audioElement.currentTime * 1000`. Binary-search the `words` array for the active word, derive `sentence_idx`, update React state only on sentence change (not every frame). Panel reveals fire when `currentTime` crosses a cue's `at_ms`.

**Curtain rise master clock (per §7.1 timeline):** all audio events (Wire ducking, Narrator breath, narration start, music bed enter) are scheduled on `audioContext.currentTime` with absolute offsets from `t0 = audioContext.currentTime + 0.05`. Visual events (overlay fade, hero fade-in, headline typewriter) use Framer Motion's `useAnimate` orchestrated sequence pegged to the same `t0`. The headline typewriter renders `floor((now - headlineStart) / 0.030)` characters per frame.

**Buffering safety:** listen to `seeking` and `waiting` events on the audio element — pause the highlight loop during stalls. Don't model decode lag in app code; trust the audio element's `currentTime`.

**Audio mixing in browser:** single `AudioContext`, one `<audio>` element per persistent source (Wire ambient, music bed, narrator), each routed through its own `GainNode` into a master gain into `destination`. Levels per §12.2.

**Autoplay policy:** the click-into-Broadcast handler synchronously calls `audioContext.resume()` and primes audio elements (`.load()` then `.play().catch(noop)` on a silent buffer) before any async work. iOS Safari requires the prime to happen inside the same gesture.

### 7.7 Accessibility — reduced motion + captions

CONSTITUTION §11 demands Olympic-broadcast aesthetic. Doesn't conflict with accessibility — Olympic broadcasts ship captions and respect motion preferences.

- **`prefers-reduced-motion`** disables Wire scroll animation, hero Ken Burns, headline typewriter, and the Floor's particle streams. Curtain-rise transitions instant-cut. The narration still plays; visual sync still works at sentence granularity.
- **Captions track** for the Narrator: a WebVTT track derived from the same `NarrationManifest.words` data, attached to the audio element via `<track>`. ~30 lines of code to generate. Improves a11y *and* perceived production value.
- **Browser-tab title** gets a SynthID-aware "(AI-generated narration)" badge in the Evidence Drawer per the SynthID watermark applied by Gemini TTS.

---

## 8. Schemas

### 8.1 Story Unit (BigQuery: `candidates`)

```sql
CREATE TABLE candidates (
  story_unit_id STRING NOT NULL,
  story_unit_title STRING NOT NULL,
  story_unit_type STRING NOT NULL,             -- 'place' | 'program' | 'pattern'
  region STRING,
  state STRING,
  primary_sports ARRAY<STRING>,
  olympic_count INT64,                         -- aggregate, no names
  paralympic_count INT64,                      -- aggregate, no names
  contributing_athlete_ids ARRAY<STRING>,      -- INTERNAL — never in output
  representation_history ARRAY<STRUCT<year INT64, count INT64, type STRING>>,
  pipeline_continuity_gaps ARRAY<STRUCT<start_year INT64, end_year INT64, note STRING>>,
  public_evidence_refs ARRAY<STRING>,
  scout_scores STRUCT<
    cinderella FLOAT64,
    comeback FLOAT64,
    hometown FLOAT64,
    echo FLOAT64
  >,
  aggregate_score FLOAT64,
  high_narrative_density BOOL,
  last_updated TIMESTAMP
);
```

### 8.2 Athlete Registry (BigQuery: `athlete_registry`)

```sql
CREATE TABLE athlete_registry (
  athlete_id STRING NOT NULL,
  full_name STRING NOT NULL,
  first_name STRING,
  last_name STRING,
  known_variants ARRAY<STRING>,
  sport STRING,
  olympic_or_paralympic STRING,                -- 'olympic' | 'paralympic' | 'both'
  era_or_decade STRING,
  hometown_state STRING,
  source_first_seen STRING,
  last_updated TIMESTAMP
);
```

This table is queried ONLY by the NIL Redaction Layer and the Investigator's internal fact-checking. It is never exposed to the Storyteller, the Narrator, or any user-facing surface.

### 8.3 Lead Report (Firestore: `/lead_reports/{id}`)

```typescript
interface LeadReport {
  id: string;
  story_unit_id: string;
  story_unit_title: string;
  story_unit_type: 'place' | 'program' | 'pattern';
  scout: 'cinderella' | 'comeback' | 'hometown' | 'echo';
  signal_type: string;
  confidence: number;
  confidence_history: { timestamp: string; value: number; reason: string }[];
  notes: string;          // never names individual athletes
  evidence_refs: string[];
  status: 'investigating' | 'promoted' | 'killed' | 'merged';
  created_at: string;
  updated_at: string;
}
```

### 8.4 Investigation Packet (Firestore: `/investigation_packets/{id}`)

```typescript
interface InvestigationPacket {
  id: string;
  story_unit_id: string;
  story_unit_title: string;
  story_unit_type: 'place' | 'program' | 'pattern';
  narrative_spine: string;       // 2-3 sentences, no athlete names
  geography: { state: string; region: string; population: number; notes: string };
  historical_context: {
    era_parallel: string;        // "1960 Rome sprint era" — NOT a named athlete
    pattern_notes: string;
  };
  trend_signals: {
    olympic_count_history: { year: number; count: number }[];
    paralympic_count_history: { year: number; count: number }[];
  };
  sources: {
    url: string;
    outlet: string;
    relevance_note: string;
  }[];
  paralympic_depth_score: number;   // 0-1; Equity Editor input
  ready_for_storyteller: boolean;
}
```

### 8.5 Story Draft (Firestore: `/story_drafts/{id}`)

```typescript
interface StoryDraft {
  id: string;
  investigation_packet_id: string;
  headline: string;
  dek: string;
  body: string;
  why_this_matters: string[];     // 3 bullets
  hometown_panel: string;
  historical_echo: string;
  storyteller_notes: string;
  equity_review: {
    cleared: boolean;
    feedback: string;
    revisions_count: number;
  };
  publish_gate_decision: 'pending' | 'cleared' | 'returned' | 'killed';
  created_at: string;
  updated_at: string;
}
```

### 8.6 Publish Gate Audit Entry (Firestore: `/publish_audits/{id}`)

```typescript
interface PublishAudit {
  id: string;
  story_id: string;
  sub_stages: {
    fact_check: { claims_checked: number; claims_removed: number; claims_softened: number; passed: boolean };
    source_review: { source_count: number; outlets: string[]; passed: boolean };
    parity_review: { equity_cleared: boolean; equity_feedback: string; passed: boolean };
    nil_redaction_review: {
      individual_refs_reviewed: number;
      direct_matches: number;
      near_identifications: number;
      small_aggregates: number;
      aggregated: number;
      redacted: number;
      returned_to_storyteller: number;
      passed: boolean;
    };
    safety_review: { invented_quotes: number; private_info_flags: number; passed: boolean };
    language_review: { restricted_terms_flagged: number; predictive_phrases_softened: number; passed: boolean };
    visual_review: { regenerations: number; passed: boolean };
  };
  final_decision: 'cleared' | 'returned' | 'killed';
  completed_at: string;
}
```

### 8.7 Wire Event (Firestore: `/wire_events/{id}`)

See §6.2.


---

## 9. The Floor — the agent graph

### 9.1 What it is

A backstage view of the agent system. D3 force-directed graph. Each node is an agent (7 visible). Edges are handoffs, drawn as particle animations when active. Side panel shows real tool calls in flight.

### 9.2 Node design

Seven nodes, each with:
- **Agent name** (serif italic).
- **Status indicator:** idle / thinking / handing-off / waiting-for-tool.
- **Color signature:** Editor (gold), Scouts (deep navy with sub-scout colors on the edge), Investigator (parchment), Equity Editor (Agitos-red accent), Storyteller (warm cream), Narrator (deep blue), Publish Gate (slate gray).

### 9.3 Edge animation

When an agent hands off to another, a particle stream flows along the edge for ~800ms. Color matches the source agent. This is what makes the Floor visually distinctive.

### 9.4 Tool call cards

Bottom-right panel. When an agent calls a tool, a card slides in:
- Tool name (e.g., "BigQuery: candidates", "Gemini Search Grounding", "Nano Banana Pro", "NIL Redaction Layer")
- Status (running / complete / failed)
- Duration
- One-line result summary

Cards persist for ~3 seconds after completion, then fade.

### 9.5 The Floor in the demo

The Floor view runs for ~25 seconds in the demo (0:30-0:55). It shows:
- All 7 nodes lit
- Multiple particle streams in flight
- A real Equity Editor intervention (Agitos-red flash on its node, particle stream up to Editor)
- Tool call cards stacking and fading

This is the "truly agentic" proof.

### 9.6 Rendering target — D3 force on Canvas

Pure D3 + SVG starts to thrash with multiple concurrent particle streams plus tool-call cards animating in a side panel. **The Floor renders the force layout + edges + particles in Canvas; the side-panel tool-call card stack stays in React + Framer Motion.** Canvas batches redraws inside the simulation `tick`, which gives ~1ms/frame headroom for ~20 in-flight particles + 7 nodes + 21 edges. 60fps on a 2024-era laptop in Chrome is the target.

**Particle pattern:** straight-line edges → analytical position `p = a + (b-a) * easeOutCubic(t)` per particle per frame. No `getPointAtLength` calls (those force SVG layout reflows). Particle pool is a flat array; splice on `t >= 1` (don't filter-and-reassign every tick — memory thrash).

**Concurrent streams:** seed agent transitions emit a particle on the Floor's local event bus; the Floor doesn't subscribe to Firestore directly. The agent runtime publishes "handoff fired" events via the same SSE channel as Wire events (separate event type), keeping the Floor in sync with the Wire's timing.

---

## 10. Visual style guide

### 10.1 Color tokens (Tailwind config)

```javascript
colors: {
  'navy-deep': '#0A1428',      // primary background
  'navy-mid': '#1A2740',       // panel background
  'navy-light': '#2C3E5A',     // subtle dividers
  'gold-warm': '#D4A84A',      // accent, headlines
  'gold-deep': '#A8842F',      // hover states
  'cream': '#F5EFE0',          // body text on dark
  'parchment': '#E8DDC4',      // Investigator agent color
  'agitos-red': '#C8102E',     // Equity Editor accent (NEVER the actual logo)
  'slate': '#5A6878',          // Publish Gate, secondary text
  'wire-text': '#B8C4D6',      // Wire body text
  'wire-timestamp': '#7A8AA0', // Wire timestamps
}
```

**Forbidden:** any actual Olympic ring colors used together. We use deep navy + gold + accent only.

### 10.2 Typography

```javascript
fonts: {
  'serif-display': ['"Playfair Display"', 'serif'],     // headlines
  'serif-italic': ['"Lora"', 'serif'],                  // agent names, italics
  'sans-body': ['"Inter"', 'sans-serif'],               // Wire body, UI
  'mono-time': ['"JetBrains Mono"', 'monospace'],       // timestamps
}
```

### 10.3 Spacing and rhythm

- Wire row height: 56px minimum (room to read)
- Wire scroll: smooth, ease-out, ~300ms per new event
- Panel slide-ins: 600ms, ease-out, with subtle blur fade
- Curtain rise: see §7.1 for full timing

---

## 11. Demo storyboard (3 minutes)

The 3-minute submission video. Shot list with timing.

**The video has exactly one job: demonstrate that the room is alive, makes editorial decisions (especially parity), and produces emotionally compelling output.** It does NOT demonstrate interactivity. **Do NOT show a typed user prompt, search box focus, or chat input anywhere in the video.** A typed prompt collapses the system into a chatbot mental model and forfeits the autonomous-newsroom positioning. The seed prompt lives only on the live URL hero — see §11.1. (VPS-DEC-030.)

| Time | Shot | Audio |
|---|---|---|
| 0:00–0:05 | Black screen. Single line of voiceover. | "Every Team USA athlete comes from somewhere." |
| 0:05–0:10 | Fade up on The Wire, mid-flow. Wire ambient + Wire Dispatcher voice. Voiceover continues. | "We built an AI newsroom that finds those places." |
| 0:10–0:30 | The Wire alive. Equity Editor intervention visible in recent history. Confidence scores shifting on a Hometown Scout lead. Editor accepts the intervention. **No user input visible — the room is operating autonomously.** | Wire ambient, no voiceover. Let the room speak. |
| 0:30–0:55 | Cut to The Floor. 7 agents visible. Particle streams. Tool cards stacking. Equity Editor node flashes Agitos-red. Real BigQuery + Gemini Search + NIL Redaction Layer tool calls visible. | Wire ambient continues, slightly louder. Brief voiceover: "Seven agents. Real tool calls. The room finds places, not people." |
| 0:55–1:05 | Click into a published story (the anchor — a place, not a person). The story is **already on the Stack** because the Equity Editor caused it earlier (visible in the Wire history at 0:10–0:30). The cursor click is the only user action in the video. Curtain rise begins. | Wire ducks. Music bed begins. Narrator breath. |
| 1:05–2:30 | The Broadcast. 90 seconds of pure narration. Hero image (stylized place). Sentence highlighting. Hometown panel slides in when town name lands. Historical Echo panel slides in when era reference arrives. | Narrator full voice. Music bed at -25dB. No presenter voice. |
| 2:30–2:50 | Evidence Drawer opens. 7 sub-stages visible. NIL Redaction Layer audit shows "4 reviewed · 2 aggregated · 2 redacted · cleared." Sources listed. Parity Review confirmed. | Music bed continues, gentle. Brief voiceover: "Trust is a receipt. Every claim checked. Every athlete name redacted by architecture." |
| 2:50–3:00 | Cut back to The Wire. New leads scrolling. | "Right now, the room is finding the next one." Hard cut to black. |

### 11.1 The seed prompt — live URL hero (NOT in the video)

The demo seed prompt — *"Find me a Team USA hometown story I've never heard before"* — is the live URL's hero CTA. Judges who click the live URL after watching the video land on a state where:

- The Wire is already pre-seeded with the most recent ~6 published events (`mode: replay`) so the room is "scrolling" within <1s of arrival. (VPS-DEC-028.)
- A hero CTA is visible above the Wire: a single input box pre-filled with the seed prompt as placeholder text, with a subtle hint underneath: *"or watch the room work."*
- Submitting the prompt triggers a fresh investigation that streams to the Wire labeled `mode: live` and runs at `compression_factor=0.25` (4× compressed cadence per §6.10).

The CTA is the *only* place a typed prompt appears in the product surface presented to judges. This separation is intentional: video carries the autonomous-newsroom claim; URL carries the interactive affordance.

**Seed prompt location (HOE-DEC-005):** the prompt text lives in `web/config/seed_prompt.ts` (TS const) with a `data/seed_prompt.txt` fallback. Editable without redeploying agent code (CONSTITUTION Rule 1).

**CTA → agent runtime trigger path:** `POST /api/investigate` with `{prompt, compression_factor: 0.25, source: 'cta'}` from the live URL hero CTA → agent-runtime service receives the request, registers a new investigation context, returns `{investigation_id}` immediately, and the SSE stream starts emitting Wire events for that investigation alongside ambient activity. Per-IP rate limit: 3 submissions/hour. Concurrent submissions queue (only one active live-investigation at a time).

### 11.2 Anchor story (selected on Day 9, with Day 8 evening pre-screen as backstop)

The anchor story is a place — selected from the corpus of 15–25 stories the system produces during Day 8–9 organic operation. It must satisfy:
- Strong Paralympic representation (the Equity Editor caused this story)
- A clear era parallel (the Echo Scout cited it cleanly)
- Visual richness (a place that renders beautifully as a stylized hero image)
- Emotional landing (the Storyteller's draft makes Charlie sit back from the laptop)

**Do not pre-write the anchor story. Let the system produce it.**

**Day 8 evening soft-rank as backstop (VPS-DEC-027):** On Day 8 evening, Charlie reviews the top 3–5 candidates the system has produced so far and soft-ranks them by emotional pull. This pre-screens what Day 9 will choose from. If all 5 are flat, we re-run on Day 9 morning with production noise lower. Preserves the discipline (system produces the corpus, anchor selected from organic discoveries) while adding 24 hours of warning if nothing lands.

---

## 12. Sound design

### 12.1 Asset list

- **Room tone (low ambient):** soft 60Hz hum, room-of-people texture. Loops for The Wire and The Floor backgrounds.
- **Scout chime:** 0.4s warm bell when a Scout promotes a lead.
- **Confidence tick:** 0.15s subtle click when confidence updates.
- **Equity intervention tone:** distinct 0.6s warm low-frequency pulse — **the most distinctive sound in the room.** Plays whenever the Equity Editor intervenes.
- **Publish Gate clear:** 0.5s descending three-note motif when a story clears.
- **Curtain rise swell:** 1.2s rising ambient pad at the start of the Broadcast page.
- **Music bed (Broadcast):** see §7.5.

All sounds licensed from Epidemic Sound or Artlist, or generated.

### 12.2 Mix levels

- Room tone: -32dB
- UI sounds (chimes, ticks, tones): -18dB
- Wire Dispatcher voice (ambient): -22dB
- Music bed (Broadcast): -25dB
- Narrator (Broadcast): 0dB reference
- Equity intervention tone: -16dB (slightly louder than other UI sounds — it should land)

---

## 13. Build phasing (11 days)

| Days | Phase | Deliverables |
|---|---|---|
| 1-2 | Foundation | Apache 2.0 license + `LICENSE` file in repo (Day 1 priority #1; auto-DQ if missed) **+ `scripts/check_license.sh` CI gate wired into pre-commit and GitHub Actions**. GCP project, Vertex AI, BigQuery, Firestore (Native mode), Cloud Storage provisioned with **Secret Manager + service-account scoping per §19**. ADK environment installed. **Day-1 model-availability gate: `scripts/verify_models.py` confirms all seven model IDs (gemini-3.1-pro-preview, gemini-3-flash-preview, gemini-3.1-flash-lite-preview, gemini-3.1-flash-tts-preview, gemini-3-pro-image-preview, gemini-3.1-flash-image-preview) respond on `location='global'`. Block all downstream work on green.** **Day-1 voice list: `scripts/list_tts_voices.py` enumerates the 30 prebuilt TTS voices; Charlie + HoE pick Broadcast Narrator + Wire Dispatcher voice strings; pinned into §3.5 and §5.6.** Next.js skeleton with SSE Route Handler + server-side `onSnapshot → SSE` forwarding. BigQuery schemas (`candidates`, `historical_athletes`, `geography`, `championships`, `athlete_registry`) deployed. Athlete registry loaded from Olympedia (Olympic-historical CSV, filtered for Team USA) + Wikidata SPARQL cross-reference + Team USA roster. **Athlete registry startup-assertion (≥500 rows) wired (HOE-DEC-019).** Wire vocabulary library JSON committed. **`/data/streaming_profiles.json` committed by Day 3 EOD.** Local dev loop set up per §18 (Firestore emulator + local agent runtime + `npm run dev`). **Devpost text description outline drafted** (`/Docs/VPS/devpost-text-outline.md` per VPS-DEC-029) — VPS owns; HoE provides technical-detail inputs as needed. |
| 3-5 | Agent core | Editor agent. Investigator agent. All 4 sub-scouts (Cinderella, Comeback, Hometown, Echo). Wire vocabulary library wired up. Candidate pool reads/writes. Confidence scoring. High Narrative Density detection. Wire stream rendering in browser. **Wire pre-seed on URL load** (recent ~6 published events `mode: replay` — VPS-DEC-028) implemented as part of Wire stream rendering. **Day 5: Narrator voice config test** — HoE runs a 30-second Flash TTS sample with the Broadcast Narrator config, Charlie listens, sub voice if needed (VPS-DEC-031). Pulled forward from Day 6 to de-risk the Broadcast's emotional spine. |
| 6-7 | Integrity & production | Paralympic Equity Editor with feed-drift and draft-review behavior, including the rehearsed demo intervention. Storyteller agent with full forbidden-words constraints **AND the encouraged temporal-phrasing list ("first," "next," "newest," "earliest") per VPS-DEC-033**. Publish Gate with all 7 sub-stages, including the **NIL Redaction Layer** Python module. Visualizer tool calls (Nano Banana Pro for hero, Nano Banana 2 for utility). Narrator with both voice configs. **Music bed candidates sourced from Epidemic Sound or Artlist** (2–3 candidates downloaded to `/audio/music_beds/` — VPS-DEC-032) so they're available to A/B under sample Narrator audio. Pulled forward from Day 8. |
| 8 | Frontend ship | The Floor (D3 graph, particle handoffs, tool call cards). The Broadcast (curtain rise, synchronized choreography, sentence highlighting, Hometown panel, Historical Echo panel, Evidence Drawer with all 7 sub-stages visible). **Live URL hero CTA implemented** (seed prompt as placeholder + "or watch the room work" hint per §11.1). **Day 8 evening: anchor candidate soft-rank** — Charlie reviews top 3–5 candidates the system has produced and soft-ranks by emotional pull (VPS-DEC-027). This is the backstop to Day 9 organic selection. **Initial draft of demo voiceover script** (`/Docs/Engineering/demo-voiceover-script.md`) so Narrator-vs-voiceover balance is testable during dress rehearsal. |
| 9 | Run-and-discover | System runs continuously. Produces 15-25 organic place/program/pattern stories. Anchor story selected from organic discoveries (Day 8 evening soft-rank narrows the field; final pick today). Dress rehearsal of demo flow with all five demo moments timed end-to-end. **Music bed final pick** by ear under the actual anchor-story Narrator audio. **Devpost text description refined** (VPS owns; HoE reviews for technical accuracy). |
| 10 | Demo video | Record demo, edit, music, color, voiceover. **Devpost text description final pass.** Final pre-submission verification checklist (PROJECT_BRIEF §14). **Submit by EOD.** |
| 11 | Submission + buffer | Submit early if not yet done. Fix anything that breaks. Monitor hosted URL. **Begin post-submission ops checklist per §22.** |

**Submit by end of Day 10 (Sunday May 10) at the latest.** Day 11 is buffer.

### 13.1 Pull-forward summary (VPS Session 1, Day 1)

Three items moved earlier than the original v1.1 schedule, in service of the principle that *the buffer in an 11-day window is at the front, not the back*:

| Item | Original | New | Why |
|---|---|---|---|
| Narrator voice config test | Day 6 | **Day 5** | The Narrator is the Broadcast's emotional spine. If the substituted Flash TTS voice lacks the warm/mid-tone/documentary feel, we want 5 days of buffer to iterate, not 4. (VPS-DEC-031) |
| Music bed candidates sourced | Day 8 | **Day 6–7** | Day 8 is also Floor + Broadcast + curtain-rise day. Music sourcing should not compete for Day 8 attention; it's a low-effort task that should land before. (VPS-DEC-032) |
| Devpost text description outline | (implicit Day 10) | **Day 1–2** (refined Day 9, final Day 10) | One of three judged artifacts; drafting it on Day 10 while recording and submitting is when typos happen. (VPS-DEC-029) |

Two new structural items added to the phasing:

| Item | Day | Why |
|---|---|---|
| Wire pre-seed on URL load (replay events) | Day 3–5 (with Wire stream) | The hosted URL must feel alive in <1s on first paint. (VPS-DEC-028) |
| Day 8 evening anchor soft-rank | Day 8 | Backstop to Day 9 organic anchor selection so we don't arrive at Day 9 with no fallback. (VPS-DEC-027) |

---

## 14. Acceptance criteria

The build is "demo-ready" when all of the following are true:

- [ ] Apache 2.0 license is in the repo root and visible in the GitHub About section.
- [ ] All 7 agents are operational and producing Wire events with distinct voice signatures.
- [ ] At least one organic Equity Editor intervention has occurred during a continuous run (not a hardcoded demo trigger).
- [ ] The Wire renders with the 70/30 thinking/milestone ratio, variable cognition speed, and visible self-correction.
- [ ] The Wire vocabulary library contains ≥40 phrase fragments per agent.
- [ ] The Floor renders all 7 nodes with particle stream handoffs and tool call cards.
- [ ] The Broadcast page renders the curtain rise transition, synchronized choreography, sentence highlighting, Hometown panel, Historical Echo panel.
- [ ] The Broadcast hero image is a stylized place (no people).
- [ ] The Narrator produces audio with both Broadcast and Wire Dispatcher voice configs.
- [ ] Music bed plays at -25dB under the Narrator on the Broadcast page.
- [ ] The Publish Gate audit log shows all 7 sub-stages, including a populated NIL Redaction Review with non-zero `individual_refs_reviewed`.
- [ ] The NIL Redaction Layer is invoked on every Wire event and every Broadcast publish.
- [ ] At least one anchor story exists, generated organically, with a place as the protagonist.
- [ ] No individual Team USA athlete is named in any user-facing surface (Wire, Broadcast page, demo video).
- [ ] No Olympic rings, Paralympic Agitos, LA28 logomark, torch, Team USA marks, or third-party corporate logos other than Google Cloud appear anywhere.
- [ ] No finish times or scoring results are present in any data layer or output.
- [ ] The demo video is 3:00 or shorter, unlisted on YouTube, with positive framing and visible NIL Redaction Layer audit.
- [ ] **The demo video contains no typed user prompt, search box focus, or chat input.** The only user action visible is a single cursor click into the anchor story (VPS-DEC-030).
- [ ] **The live URL displays a hero CTA above the Wire** with the seed prompt as placeholder and an "or watch the room work" hint (§11.1).
- [ ] **On URL load, the Wire pre-seeds with the most recent ~6 published events** (`mode: replay`) so the room is "scrolling" within <1s (§6.9, VPS-DEC-028).
- [ ] The Storyteller's prompt includes BOTH the forbidden temporal-phrasing list (former, past, ex-, retired) AND the encouraged temporal-phrasing list (first, next, newest, earliest) per VPS-DEC-033.
- [ ] Music bed candidates exist in `/audio/music_beds/` by Day 7 EOD (VPS-DEC-032).
- [ ] Devpost text description outline exists at `/Docs/VPS/devpost-text-outline.md` by Day 2 EOD (VPS-DEC-029).
- [ ] PROJECT_BRIEF §14 (Pre-Submission Verification Checklist) is complete.

### 14.1 New v1.3 measurable acceptance criteria

Items added in the v1.3 stack-validation pass — testable on Day 9 dress rehearsal.

**Performance + experience:**
- [ ] **First-paint <1s test:** Playwright cold-cache load measures TTFB + first Wire row painted in ≤1.0s. Run on Day 9.
- [ ] **Curtain-rise timing test:** Playwright measures click-to-first-narration-word in 1.0–1.2s ±100ms. Run on Day 9.
- [ ] **5s comprehension test:** 3 unfamiliar viewers correctly name the screen (Wire / Floor / Broadcast) within 5s of seeing it. Run on Day 9.
- [ ] **Half-second visual test:** still frame at t=0.5s after page load reads as Olympic-broadcast aesthetic without any text loaded.

**Voice + agent integrity:**
- [ ] **Voice-blind test:** Charlie reads 21 random Wire messages (3 per agent, names redacted) and correctly attributes ≥18/21. Run on Day 7 and Day 9.
- [ ] **Storyteller forbidden-words unit test:** `agents/storyteller/test_forbidden_words.py` runs 20 sample drafts, asserts zero forbidden words, asserts encouraged temporal phrasing ("first Olympian," "newest Paralympian") passes through unflagged. Cite VPS-DEC-033.

**NIL safety architecture:**
- [ ] **NIL Layer fail-closed:** with `athlete_registry` set to <500 rows, the agent runtime exits with status 1 and `/health/nil` returns 503. (HOE-DEC-019.)
- [ ] **Wire write-through proxy:** `scripts/lint_no_direct_wire_writes.py` finds zero direct `firestore.add('wire_events', …)` calls in `/agents/`. Runs in CI. (HOE-DEC-018.)
- [ ] **NIL max-revisions cap:** unit test simulates 3 NIL Returns on a draft; on the 4th attempt the story is killed with `kill_reason: 'nil_unresolvable'` and a Wire milestone fires.

**Demo-causal integrity:**
- [ ] **Day 9: Equity Editor caused ≥1 anchor candidate via feed-drift detection**, with the causal Wire trail (intervention → editor accept → scout pivot → investigation start) visible in the Wire history at demo time. (Closes audit P1-#25.)
- [ ] **HND fired ≥1 time during Day 8-9 organic operation**, captured in Wire history.

**Day-1 hard gates:**
- [ ] All seven Vertex AI Gemini model IDs respond on `location='global'` per `scripts/verify_models.py`.
- [ ] Cloud Run services deployed with `--min-instances=1`, `--cpu-always-allocated`, `--use-http2`, `--timeout=3600s`.
- [ ] Apache 2.0 license badge visible on GitHub repo About sidebar (auto-checked daily by `scripts/check_license.sh`).

**SSE resilience:**
- [ ] **SSE reconnect test:** Day 9 dress rehearsal includes a deliberate disconnect; client reconnects within 1s with `Last-Event-ID` and replays missed `wire_events`.

---

## 15. Cost guardrails + budget alerts

(NEW in v1.3 — closes audit P0-#1.)

### 15.1 Estimated Day 1 → Day 11 spend (rough)

Volumes assumed for Day 8-9 continuous run + Day 10 demo recording + Day 11 buffer:

| Axis | Volume | Unit cost | Estimate |
|---|---|---|---|
| Gemini 3.1 Pro calls (Editor, Investigator, Storyteller, Equity, Publish Gate) | ~6K calls | varies by tokens | ~$50-80 |
| Gemini 3 Flash calls (4 Scouts, ambient) | ~30K calls | low | ~$15-25 |
| Gemini 3.1 Flash-Lite (Wire vocab fills, NIL near-id) | ~50K calls | $0.25/1M in, $1.50/1M out | ~$5-10 |
| Gemini 3 Pro Image (Nano Banana Pro hero, ~50 generations) | ~50 images | tier varies | ~$15-30 |
| Gemini 3.1 Flash Image (utility, ~150 generations) | ~150 images | lower tier | ~$10-20 |
| Gemini 3.1 Flash TTS (~25 stories × 90s + Wire Dispatcher loop) | ~60 min audio | per-character | ~$10-20 |
| Grounding with Google Search (5K free/mo, then $14/1K) | ~3K queries Day 8-9 | covered by free tier | ~$0 |
| Gemini Deep Research (≤10/day × 3 days) | ~30 calls | premium | ~$30-50 |
| Cloud Run (2 services, min-instances=1, always-CPU) | 11 days × 2 services | ~$0.30/hr aggregate | ~$80-100 |
| Firestore Native (writes + storage) | low volume | mostly free tier | ~$5 |
| BigQuery (queries on small dataset) | low volume | mostly free tier | ~$0-5 |
| Cloud Storage (images + audio) | ~5GB | $0.020/GB/mo | ~$1 |
| **TOTAL (point estimate)** | | | **~$220-345** |

### 15.2 Budget alerts

Configured in GCP Billing on Day 1:

- **$100 alert** — informational; verifies billing is working
- **$200 alert** — pause non-anchor work, audit which axis is driving spend
- **$300 alert** — kill switch flipped (env var `AGENT_RUNTIME_PAUSED=1`); only the demo-required path stays live

### 15.3 Per-axis ceilings

In code:
- Per-Scout daily call cap: 5,000 grounded prompts
- Per-investigation Gemini Pro token cap: 200K tokens
- Deep Research daily call cap: 10
- Nano Banana Pro per-story regeneration cap: 3 (then fallback per §5.7.1)
- TTS chars/day cap: 200K

Tracked in Firestore `agent_call_counters` collection. Each tool call increments before invocation; ceilings enforced in the tool wrapper.

### 15.4 Kill switch

Env var `AGENT_RUNTIME_PAUSED=1` set on the agent-runtime Cloud Run service halts the autonomous loop on the next think-cycle (within 90s). The Wire continues to render replay events; new investigations don't start. Reverts on env-var unset + service redeploy.

---

## 16. Observability

(NEW in v1.3 — closes audit P0-#2.)

### 16.1 Structured logging

Every agent call writes a single Cloud Logging structured-JSON entry:

```json
{
  "ts": "2026-05-10T17:42:33.123Z",
  "agent": "investigator",
  "sub_agent": null,
  "story_unit_id": "us-ia-mount-pleasant",
  "investigation_id": "inv_abc123",
  "model": "gemini-3.1-pro-preview",
  "tool": null,
  "latency_ms": 1843,
  "input_tokens": 4200,
  "output_tokens": 890,
  "compression_factor": 1.0,
  "outcome": "success",
  "wire_event_id": "evt_xyz789",
  "error": null
}
```

Every NIL Redaction Layer scan writes a sibling entry with sub-stage results. Every Wire emit writes the redaction outcome. Every tool call (BigQuery, Nano Banana, Deep Research) writes timing + status.

### 16.2 Distributed tracing

OpenTelemetry trace spans across the Editor → Scout → Investigator → Equity Editor → Storyteller → Publish Gate → Narrator chain. Trace ID = `investigation_id`. Cloud Trace integration via OTLP exporter. One trace per investigation; spans roll up to a single end-to-end timeline.

### 16.3 Golden-path metrics dashboard

Cloud Monitoring dashboard `storytellers-room-golden-path` with:
- Wire emission rate (target 4-8s per event ambient; 1-2s during compression)
- NIL Redaction Layer scans/min and redaction action distribution (pass / aggregate / return)
- Equity Editor interventions/hr (hard signal: ≥1/hr is healthy; 0 means feed isn't drifting OR detection is broken)
- HND fires/day
- Tool-call latency p50/p95/p99 per tool
- Vertex AI 4xx/5xx rate per model
- Firestore write rate on `wire_events`
- Cloud Run instance count + CPU + memory
- Cost burn rate per axis (from §15)

### 16.4 Operator playbook for "the Wire isn't moving"

Linked from the dashboard. First three checks (per §17 error-handling decision tree):
1. Cloud Run agent-runtime logs — is the autonomous loop alive? (Look for `editor.autonomous_loop think_cycle` log lines every 30-90s.)
2. Vertex AI quota — `gcloud compute regions describe global` for current quota.
3. NIL Redaction Layer — `/health/nil` returns 200? Registry row count >500?

---

## 17. Error handling + graceful degradation

(NEW in v1.3 — closes audit P0-#3.)

Failure modes and defined behaviors per tool. The principle: **fail visibly on the Wire** (turn the failure into Wire texture) rather than fail silently.

### 17.1 Gemini call failure (any agent)

- Retry with exponential backoff: 3 attempts, 1s / 4s / 16s.
- On final failure, agent emits a Wire `thinking` event: *"hold — model returned an error, retrying with shorter context"* and retries with truncated prompt.
- On second failure, agent skips the current step and the Editor reassigns or kills the lead.
- Logged to `agent_errors` Firestore collection; counted in §15 cost dashboards.

### 17.2 Nano Banana Pro safety filter rejection

- Up to 3 regenerations with progressively more restrictive prompt (more negative phrasing).
- 4th failure: serve the curated Day-9 fallback from `/data/fallback_heroes/{story_unit_id}.png`. (HOE-DEC-020.)
- The regeneration loop emits Wire `thinking` events for visibility (*"visual review failed, regenerating with stricter prompt"* — exactly the kind of working-room texture we want).

### 17.3 Firestore write failure on a Wire event

- The `wire.emit` proxy retries 3× with backoff.
- On final failure, the proxy logs to Cloud Logging with severity ERROR and writes a placeholder event to a local in-memory ring buffer (last 100 events) so the next successful emit can re-emit them.
- The proxy never fails a NIL check because of a Firestore failure — NIL passes are deterministic regardless of write outcome.

### 17.4 SSE stream drop

- Client uses `@microsoft/fetch-event-source` with `Last-Event-ID` reconnect.
- Server replays any `wire_events` with `id > last_event_id` from Firestore on reconnect.
- Frontend UI shows `(reconnecting…)` for ≤2s; longer fades to a `(re-establishing)` affordance.

### 17.5 TTS failure mid-narration

- Narrator generates per-sentence TTS chunks; a per-chunk failure retries 2×.
- On final failure, the Narrator falls back to a pre-rendered MP3 of the same text from the cached anchor-candidate Day-9 pre-render (analogous to the hero image fallback).
- During recording on Day 10, the cached pre-rendered narration is the primary path anyway — live regeneration is only used during Day 8-9 organic operation.

### 17.6 Deep Research timeout

- 90s wall-clock timeout per call.
- On timeout: Investigator emits a Wire `thinking` event: *"deep research stalled, switching to grounded search"* — useful Wire texture.
- Investigator continues with grounded-search fallback. Investigation still completes.

### 17.7 NIL Redaction Layer failure (BigQuery registry query fails at refresh)

- Fail closed. Refresh failure preserves the previous in-memory automaton (don't blank it).
- If startup fails to load registry: runtime exits 1, `/health/nil` returns 503.
- If runtime mid-flight loses Firestore connectivity: `wire.emit` continues using in-memory automaton.

### 17.8 Cloud Run cold start during demo

- `--min-instances=1` on both services from Day 8 onward eliminates cold starts.
- Day-10 demo-day pre-flight: warm both URLs 5-30 minutes before recording with a synthetic-traffic ping.

---

## 18. Local development setup

(NEW in v1.3 — closes audit P1-#13.)

### 18.1 Dev loop architecture

The agent runtime runs locally. Vertex AI calls hit real Gemini (no mock for prompt iteration). Firestore runs in the **Firestore emulator**. BigQuery hits a small **`storytellers_room_dev` dataset** in the project (cheap; mirrors production schema with sample rows).

```
make dev          # boots: firestore emulator + agent runtime + next.js dev server
make agents       # just the agent runtime (poll-friendly)
make web          # just next.js
```

The agent runtime hot-reloads on prompt edits (file-watcher under `/prompts/` triggers in-process reload). No redeploy needed for prompt iteration.

### 18.2 Test commands

```
pytest -x                                  # all unit + integration tests
pytest agents/publish_gate/ -v             # NIL Redaction Layer focused
pytest agents/storyteller/test_forbidden_words.py
npm --prefix web run typecheck && npm --prefix web run lint
```

### 18.3 What does NOT run locally

- Cloud Run cold-start behavior (production-only)
- True compression-time concurrency (use the emulator + a load test on staging if needed)
- Music bed mixing in the browser at exact -25dB (requires real audio output)

For these, deploy to a `dev-` Cloud Run service with the same config as prod and test there.

---

## 19. Deployment pipeline + IAM + secrets

(NEW in v1.3 — closes audit P0-#8 and P1-#14.)

### 19.1 Service accounts

| Service | Service account | Roles |
|---|---|---|
| `agent-runtime` Cloud Run | `agent-runtime@PROJECT.iam.gserviceaccount.com` | `roles/aiplatform.user`, `roles/datastore.user`, `roles/bigquery.dataViewer` (limited to `athlete_registry`, `historical_athletes`, `geography`, `championships`, `candidates`), `roles/storage.objectAdmin` (limited to hero/audio buckets), `roles/secretmanager.secretAccessor` |
| `web` Cloud Run | `web@PROJECT.iam.gserviceaccount.com` | `roles/datastore.user` (read on `wire_events`, `story_drafts`, `publish_audits` published-only), `roles/storage.objectViewer` (read on hero/audio buckets) |
| Cloud Build CI | default | deploy + secret-version-access scoped |

### 19.2 Firestore security rules

Server-side `onSnapshot` (HOE-DEC-024) means the frontend doesn't read Firestore directly — Firestore rules can deny all client access. Rules:

```
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;  // server-side only
    }
  }
}
```

Both Cloud Run services authenticate via service-account credentials; their Admin SDK calls bypass rules.

### 19.3 Secret Manager

API keys, third-party tokens (Epidemic Sound / Artlist webhook keys if any), and any auth tokens live in Secret Manager. Cloud Run mounts them as env vars at boot. **No secrets in `.env` files committed to repo**; `.env.example` documents which env vars are needed but not their values.

### 19.4 Cloud Build pipeline

`/cloudbuild.yaml` defines two parallel build steps:
- Build + push agent-runtime image → deploy to Cloud Run with min-instances=1, always-CPU, http2, timeout=3600s, location='global' for Vertex AI
- Build + push web image → deploy to Cloud Run with min-instances=1, http2

Triggered by push to `main`. Manual `make deploy-demo` for promotion to the public demo URL.

### 19.5 Rollback

```
gcloud run services update-traffic agent-runtime --to-revisions=PREVIOUS=100
gcloud run services update-traffic web --to-revisions=PREVIOUS=100
```

Document the last-known-good revision IDs in Cloud Run console as "v0.10.0-demo-final" labels by Day 9 EOD.

---

## 20. Test strategy

(NEW in v1.3 — closes audit P1-#15 and P1-#26.)

### 20.1 Unit tests (`agents/*/test_*.py`)

- **`agents/publish_gate/test_nil_redaction_layer.py`** — ≥30 fixtures covering:
  - Direct match (current athletes): "Wilma Rudolph" → redact
  - Direct match (historical): "Jesse Owens" → redact
  - Common-name false positive boundary: "Michael Field High School" → pass
  - Near-identification: "the 14-year-old gymnast from Plano, Texas in 2012" → return-to-storyteller
  - Small-aggregate: "Team USA's [name], [name], and [name]" → aggregate to "three athletes"
  - Unicode normalization: accented variants → redact
  - Empty registry: assert runtime exits 1
- **`agents/storyteller/test_forbidden_words.py`** — 20 sample drafts; assert zero forbidden words ("former Olympian," "inspirational," etc.); assert encouraged temporal phrasing ("first Olympian," "newest Paralympian") passes through.
- **`agents/wire/test_emit.py`** — assert direct `firestore.add('wire_events', …)` calls are caught by `scripts/lint_no_direct_wire_writes.py`.
- **`agents/scouts/test_hnd_detector.py`** — assert HND fires on ≥3-of-4 + confidence ≥0.7 + 10-min window; assert it doesn't fire on 2-of-4 or low confidence.

### 20.2 Integration tests

- **End-to-end NIL guard**: `wire.emit("text containing Wilma Rudolph")` → assert text is redacted before Firestore write.
- **End-to-end investigation cycle**: simulate an Editor assignment → assert all seven sub-stages of the Publish Gate produce structured audit entries.
- **SSE reconnect**: simulate a client disconnect mid-stream → assert reconnect with `Last-Event-ID` replays missed events.

### 20.3 Demo dress-rehearsal harness (Day 9)

`scripts/dress_rehearsal.sh` runs the demo path end-to-end against the production Cloud Run services:
- Hits the live URL → measures first-paint latency
- Submits the seed prompt → measures CTA → first Wire event latency
- Triggers a click into a published anchor story → measures curtain-rise timing
- Asserts all five demo moments fire in order with timing windows
- Captures Cloud Trace ID for post-mortem

### 20.4 Devpost compliance polling

`scripts/check_devpost_updates.py` runs as a daily 8am cron / GitHub Action, fetches the [Devpost Updates](https://vibecodeforgoldwithgoogle.devpost.com/updates) and [Discussions](https://vibecodeforgoldwithgoogle.devpost.com/discussions) pages, diffs against last-known, and emails Charlie on change. (PROJECT_BRIEF §15 line 510 makes this a per-commit checklist; this automates it.)

---

## 21. Demo-day single points of failure + mitigations

(NEW in v1.3 — closes audit P0-#9 and consolidates P1-#16, #17, #18, #19.)

| SPOF | Probability | Impact | Mitigation |
|---|---|---|---|
| Cloud Run cold start during recording | Medium | Blank Wire = re-record | `--min-instances=1` from Day 8; warm both URLs 5-30 min before recording |
| Vertex AI quota / 429 during recording | Low | Failed investigation | Day-5 quota check; request increase if needed; Day-10 pre-flight asserts available quota >2× expected demo burn |
| Nano Banana Pro safety-filter rejection during curtain rise | Low | No hero image | Day-9 pre-cache fallback per `story_unit_id`; demo path uses cached URL, never live regen |
| SSE drop during live-investigation moment | Medium | Wire pauses | Reconnect protocol with `Last-Event-ID` replay; Day-9 deliberate disconnect test in dress rehearsal |
| Firestore subscription latency spike | Low | Wire stalls | Server-side `onSnapshot` cuts latency; sub-collection sharding ready if Day-9 profiling shows hot-spotting |
| Music bed not licensed-cleared by Day 9 | Low | No music bed | License receipts in `/audio/music_beds/LICENSES.md` by Day 9 EOD; Suno-generated original as fallback |
| NIL Redaction Layer false-negative leaks a name during recording | Very Low (with fail-closed) | DQ risk | ≥30 unit-test fixtures (§20.1); fail-closed startup assertion (HOE-DEC-019); Day-9 dress rehearsal includes a deliberate-leak test |
| Apache 2.0 license badge regression | Very Low (with CI gate) | Auto-DQ | `scripts/check_license.sh` runs daily and on every commit |
| Demo recording drops a frame during curtain rise | Low | Re-take | Record at 60fps; OBS local with no upload during recording; 3 takes minimum |
| Charlie's local internet flakes during demo upload | Low | Late submit | Submit by Day 10 EOD (24h buffer); Day 11 buffer day; have YouTube unlisted upload partially ready Day 10 morning |

---

## 22. Post-submission ops + data destruction

(NEW in v1.3 — covers PROJECT_BRIEF §6, §13, §17, §18.)

### 22.1 Keep alive through judging period (May 12 – June 10, 2026)

- **Min-instances stays at 1** on both Cloud Run services through June 10.
- **Budget alerts retuned** for steady-state low-traffic operation (drop the $100/$200/$300 to $20/$40/$60 monthly).
- **Cloud Logging + Cloud Monitoring stay on**; alert on 5xx spikes or budget anomalies.
- **No destructive deploys** until June 11+. The submitted hosted URL at submission time is what judges evaluate.

### 22.2 Team USA Data destruction (PROJECT_BRIEF §6)

PROJECT_BRIEF §6 requires Team USA Data to be destroyed at hackathon conclusion. Concretely:

- **`scripts/teardown_team_usa_data.sh`** — drops BigQuery tables `athlete_registry`, `historical_athletes`, `championships`, `geography`. Logs the action.
- **Trigger:** on or after June 16, 2026 winners-announcement (or earlier if Charlie elects to wind down).
- **Athlete registry snapshot** in Cloud Storage is also purged.
- **Repo retains** the loader scripts (open source) but removes any cached/checked-in registry snapshots.

### 22.3 Social-media silence (PROJECT_BRIEF §12)

Per PROJECT_BRIEF §12, no public social media before, during, or after the contest until Sponsor authorization. The repo + unlisted YouTube video are the only public artifacts. Build artifacts (this BUILD_SPEC, the HOE-HANDOFF, internal docs) stay private.

---

## 23. Anti-patterns (what NOT to do)

- ❌ Adding an 8th visible agent.
- ❌ Naming any individual Team USA athlete in user-facing output.
- ❌ Generating hero images of identifiable people.
- ❌ Using "Loading..." spinners where a Scout should be visibly thinking.
- ❌ Making the Wire feel like a chat app (bubbles, avatars, "User:" prefixes).
- ❌ Hardcoding the demo's anchor story before Day 9.
- ❌ Pre-recording the live investigation portion of the demo without labeling it.
- ❌ Letting the Storyteller use "inspirational," "hero," "overcame," or any forbidden word.
- ❌ Letting the Equity Editor's interventions happen invisibly under the hood.
- ❌ Bypassing the NIL Redaction Layer for "demo simplicity."
- ❌ Adding marketing copy, social-media share buttons, or "tell your friends" UX.
- ❌ Speeding up the Wire to feel "more responsive."
- ❌ Adding a new persistence layer, message queue, or workflow engine.
- ❌ Decision logic in Python that should live in agent prompts.
- ❌ Using "former Olympian," "past Olympian," NGB names, or ambiguous Games references.
- ❌ Predictive phrasing without conditional softening.
- ❌ Defensive demo voiceover ("the rules don't allow us to...").
- ❌ Photorealistic generated media of any kind.
- ❌ A typed user prompt, search box focus, chat input, or any "ask the room" UI shown in the demo video. The seed prompt lives only on the live URL hero (§11.1). The video reads as autonomous editorial intelligence; the URL carries the interactive affordance. (VPS-DEC-030.)
- ❌ A live URL that paints with an empty Wire. The Wire must be pre-seeded with recent published events on first paint so the room is "scrolling" within <1s. See §6.9. (VPS-DEC-028.)
- ❌ Pre-selecting the demo's anchor story before Day 8 evening's soft-rank (and never before Day 9's final pick from organic discoveries). Day 8 evening soft-rank narrows the field; Day 9 picks the anchor. See §11.2. (VPS-DEC-027.)
- ❌ Sourcing music bed candidates on Day 8 — they must be in `/audio/music_beds/` by Day 7 EOD so they can be A/B'd under sample Narrator audio. (VPS-DEC-032.)
- ❌ Drafting the Devpost text description on Day 10. Outline lives in `/Docs/VPS/devpost-text-outline.md` from Day 1–2. (VPS-DEC-029.)
- ❌ **Calling `firestore.add('wire_events', …)` directly from any agent.** Use `wire.emit(event)` only. The proxy invokes the NIL Redaction Layer; bypassing it is a DQ risk. (HOE-DEC-018.) Lint rule `scripts/lint_no_direct_wire_writes.py` runs in CI.
- ❌ **Calling `vertexai.init()` without `location='global'` for any Gemini 3 family model.** All Gemini 3 preview models are global-endpoint only; regional calls return 404 model-not-found. (HOE-DEC-015.)
- ❌ **Letting the agent runtime boot with an empty `athlete_registry`.** The NIL Redaction Layer fails CLOSED — runtime exits 1 if the registry has <500 rows. Don't bypass this assertion for "demo simplicity." (HOE-DEC-019.)
- ❌ **Implementing the Wire-level NIL guard as a Cloud Function `onCreate` trigger** that mutates documents after write. The redacted name briefly hits the SSE stream — DQ risk. The Layer must run *before* `firestore.add(...)` returns. (HOE-DEC-018.)
- ❌ Live-regenerating the Broadcast hero image during Day 10 demo recording. Use the Day-9 pre-cached fallback per anchor candidate. (HOE-DEC-020 / §5.7.1.)
- ❌ Firing Wire events before the `athlete_registry` is loaded. The runtime's `/health/nil` endpoint returns 503 until the load completes; the SSE endpoint refuses to stream until /health/nil is 200.

---

## 24. Final reminder

> _Make the hard stuff look easy and the easy stuff look hard._
>
> _Place over Person. Parity as Property. Let the agents cook._
>
> _The NIL Redaction Layer is the trust signal — let it speak quietly in the audit log, not defensively in voiceover._
>
> _The room finds the places where Team USA stories begin. That is the one job._

---

## 25. Pointers to other documents

- **CONSTITUTION.md** (repo root) — creative and architectural principles. Re-read before each Claude Code session.
- **PROJECT_BRIEF.md** (repo root) — legal, compliance, submission requirements. Reference Sections 5, 7, 9, 10, 11 every coding session.
- **What_is_The_Storytellers_Room.md** (repo root) — descriptive vision doc for context.
- **Devpost rules** — https://vibecodeforgoldwithgoogle.devpost.com/rules
- **Devpost FAQs** — https://vibecodeforgoldwithgoogle.devpost.com/details/faqs

The repo lives at `/Users/charliereagan/projects/Google_Olympics_Hackathon`. This BUILD_SPEC lives at `Docs/Engineering/BUILD_SPEC.md`. The HoE handoff lives next to it at `Docs/Engineering/HOE-HANDOFF.md`. The VPS handoff lives at `Docs/VPS/VPS-HANDOFF.md`. The Constitution, Project Brief, and Vision Doc live in the repo root.
