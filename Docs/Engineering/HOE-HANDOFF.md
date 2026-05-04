# The Storyteller's Room — Head of Engineering Handoff

## Product Standard (Read First, Override Everything Below)

We are not staging half-baked solutions to address artificial timelines that don't exist. We make product decisions and build sessions based on **what serves the demo's emotional impact and architectural credibility** — not what's fast, not what "solves the immediate problem." We nail the room and the Broadcast experience. If the correct solution requires more work, do more work. Do not ship a partial version and call it progress.

The 11-day window IS real, and it IS the constraint. But the constraint is "submit the demo by Day 10 evening with all five demo moments landing." It is NOT "ship anything that runs on Cloud Run." A submission that ships on time and is mediocre does not win. A submission that ships at Day 10 hour 23:00 with a Broadcast page that makes the judge tear up wins.

**The Decision Filter (re-stated):** Every engineering decision passes through:

> _Does this serve one of the five demo moments?_
> 1. The room is alive.
> 2. The agents are truly agentic.
> 3. The Equity Editor caused the anchor story.
> 4. The Broadcast lands emotionally.
> 5. The Publish Gate (with the NIL Redaction Layer) proves trust.

If yes → proceed. If no → cut it.

---

**Purpose:** This document IS the Head of Engineering's memory. When context is exhausted and a fresh Claude Code session takes over the HoE role, it reads this document and picks up exactly where the previous session left off — with the same understanding, the same decisions, and the same strategic picture. No re-investigation. No re-explaining.

**Last updated:** 2026-05-02 by HoE Session 1 (Stack validation pass — BUILD_SPEC.md bumped to v1.3 with verified Vertex AI model IDs, pinned NIL Wire-level enforcement mechanism, added cost/observability/error-handling/dev/deploy/IAM/test/SPOF/post-submission sections; HOE-DEC-015 through HOE-DEC-024 ratified; no code written yet — Day 1 begins next session)

**Project countdown:** **9 days to internal deadline (Sunday May 10 EOD), 10 days to Devpost hard deadline (May 11 5:00pm PT / 8:00pm ET).**

---

## How This Document Works

### For the incoming HoE session

1. Read this document first, completely
2. Then read, in this order:
   - `PROJECT_BRIEF.md` (legal/compliance — wins on rules questions)
   - `CONSTITUTION.md` (creative/architectural principles)
   - `Docs/Engineering/BUILD_SPEC.md` (tactical implementation)
   - `What_is_The_Storytellers_Room.md` (descriptive vision context)
3. You now have everything the previous HoE session knew
4. Run repo health check before doing anything:
   - `cd /Users/charliereagan/projects/Google_Olympics_Hackathon`
   - `git status` (working tree clean? any orphan branches?)
   - `git log --oneline -10` (what shipped recently?)
   - If a Python test suite exists: `cd agents && pytest -x`
   - If a Next.js project exists: `cd web && npm run typecheck && npm run lint`
   - Verify Apache 2.0 license badge is still visible on the GitHub About sidebar

### Update rules

- **Current State (Section 2):** OVERWRITE each HoE session. This is always the latest snapshot.
- **Decisions Log (Section 4):** APPEND-ONLY. Decisions are immutable. Only Charlie can reverse a decision.
- **Lessons Learned (Section 5):** APPEND-ONLY. Only prune when a lesson is superseded by a newer one.
- **Investigation Narrative (Section 3):** APPEND new investigations. Do not edit prior investigations — they're historical reasoning.
- **Work Log (Section 6):** APPEND-ONLY. Archive entries older than 5 days to keep the doc bounded (the build is only 11 days; nothing will need archiving until the post-mortem).
- **Active Priorities (Section 7):** OVERWRITE each HoE session.

### Who updates what

- **HoE session:** All sections.
- **Execution sessions (directed by HoE):** May APPEND to Work Log (Section 6) only. All other updates go through the HoE session.
- **Charlie:** May override anything. If Charlie gives direction that contradicts a decision, update the decision with Charlie's override and reasoning.

### Relationship to other docs

- `PROJECT_BRIEF.md` > this doc on legal/compliance/submission. Always.
- `CONSTITUTION.md` > this doc on creative/architectural principles.
- This doc > `BUILD_SPEC.md` for operational truth and current priorities (the spec is reference; this doc is what's actually shipping).
- `What_is_The_Storytellers_Room.md` is descriptive only and never overrides.

---

## 1. What The Storyteller's Room Is (Strategic Context)

The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians.

**Submission category:** Challenge 2 — The Hometown Success Engine.

**The architecture philosophy in one line:** The agents cook. Python defines the boundaries (the Wire stream contract, the NIL Redaction Layer, the Publish Gate sub-stages, the parity gate). The LLM decides what happens inside them.

**The Constitutional test that cuts through everything:**

> If Python decides WHAT a scout investigates → violation.
> If Python decides WHETHER an agent can publish without Equity Editor sign-off → governance (required).
> If Python decides WHETHER an athlete name reaches the user → governance (required).

**What's load-bearing:**

- The seven-agent cast (Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate). Locked. No 8th agent.
- The Wire as the heartbeat (4-8s pacing, 70/30 thinking/milestone ratio, distinct voice signatures, visible self-correction).
- The Paralympic Equity Editor's veto power (parity is a system property — the 40% Impact lever).
- The NIL Redaction Layer (sub-stage 4 of the Publish Gate; Python module that scans every text artifact bound for a user-facing surface).
- The Broadcast page's curtain rise + synchronized choreography (the emotional payoff).
- The Apache 2.0 license at the top of the README (auto-DQ if missing on submission day).

**Active fleet (target end-state):** Editor + Scout Desk (Cinderella, Comeback, Hometown, Echo as sub-scouts inside it) + Investigator + Paralympic Equity Editor + Storyteller + Narrator + Publish Gate. Seven agents. All real Gemini calls.

**Current model fleet (locked):**

- Gemini 3.1 Pro — Editor, Storyteller, Equity Editor, Investigator, Publish Gate
- Gemini 3 Flash — the four parallel Scouts
- Gemini 3.1 Flash-Lite — Wire vocabulary fills, NIL near-identification check
- Gemini Deep Research — Investigator's tool for high-priority leads
- Nano Banana Pro — Broadcast hero illustrations (places/landscapes/facilities only)
- Nano Banana 2 — utility visuals
- Gemini 3.1 Flash TTS — Broadcast Narrator voice + Wire Dispatcher voice

**Platform:** Google Agent Development Kit (ADK) on Cloud Run. BigQuery for corpus + candidate pool + athlete registry. Firestore for live state, Wire events, audit logs. Cloud Storage for images and audio. Next.js 15 frontend on Cloud Run. SSE for the Wire stream.

**The five demo moments are the spine.** Every engineering decision serves at least one. See PROJECT_BRIEF §0 and CONSTITUTION §0.

---

## 2. Current State (Overwrite Each Session)

**Last updated:** 2026-05-02, HoE Session 1 (Stack validation pass)

**Local repo state:**

- Path: `/Users/charliereagan/projects/Google_Olympics_Hackathon`
- Branch: `main` (or to be initialized — has not yet been confirmed by Charlie at the time of this writing; HoE Session 1 did not run a `git status`)
- Commits: none yet (project documents are being staged before the first commit)
- Tests: none yet (no source code)
- Apache 2.0 license: **NOT YET CREATED.** This is Day 1 priority #1. See §7.

**Documents in the repo:**

| File | Location | Status |
|---|---|---|
| `CONSTITUTION.md` | repo root | v1.2 (Pivot A+ — Place over Person; Day-1 tightening pass) |
| `PROJECT_BRIEF.md` | repo root | v1.1 (Pivot A+) |
| `What_is_The_Storytellers_Room.md` | repo root | v1.1 (Pivot A+) |
| `BUILD_SPEC.md` | `Docs/Engineering/BUILD_SPEC.md` | **v1.3 (Pivot A+ + Day-1 tightening + HoE Session 1 stack-validation pass — see Changelog at top of file)** |
| `HOE-HANDOFF.md` | `Docs/Engineering/HOE-HANDOFF.md` | This document — Session 1 baseline |

**Production / deployment state:**

- **No GCP project provisioned yet.**
- **No Cloud Run services running.**
- **No BigQuery tables deployed.**
- **No Firestore database initialized.**
- **No Vertex AI access verified.**
- **No demo URL exists.**
- **No code, no tests, no agents.**

This is intentional. Days 0-1 are documents + spec hardening. Day 1 (next session) begins GCP provisioning + Apache 2.0 license + repo skeleton + the Day-1 hard gates from BUILD_SPEC §13.

**Architecture summary (target — not yet built; all v1.3 architectural pins reflected):**

- Seven Gemini agents on ADK Python 2.0 Beta, deployed to Cloud Run.
- **Two Cloud Run services:** `agent-runtime` (Python ADK + SSE bridge) and `web` (Next.js 15 frontend). Both with `--min-instances=1`, `--cpu-always-allocated`, `--use-http2`, `--timeout=3600s`.
- **Vertex AI calls go to `location='global'`** — all Gemini 3 family preview models are global-endpoint only; `us-central1` returns 404. Cloud Run runtime can deploy to `us-central1` for compute proximity.
- **Wire stream via server-side `onSnapshot` → SSE** (frontend does NOT use Firebase JS SDK directly; HOE-DEC-024).
- **All agent Wire emits route through `wire.emit()`** — the in-process write-through proxy at `/agents/wire/emit.py` that invokes the NIL Redaction Layer synchronously before `firestore.add(...)`. Direct `firestore.add('wire_events', …)` is forbidden by CI lint rule (HOE-DEC-018).
- BigQuery holds the historical Team USA corpus (filtered Team USA only), the candidate pool of story units (places/programs/patterns), and the `athlete_registry` (Olympedia CSVs + Wikidata SPARQL cross-reference + Team USA roster). NIL Layer asserts ≥500 rows on startup or runtime exits 1 (HOE-DEC-019).
- ADK `ParallelAgent` wraps the four Scouts.
- Editor owns the always-on autonomous loop via `asyncio.create_task(autonomous_loop())` + Cloud Scheduler watchdog (HOE-DEC-022).
- High Narrative Density fires on ≥3-of-4 Scouts on the same `story_unit_id` within a 10-min window with each ≥0.7 confidence (HOE-DEC-023).
- Compressed-time mode: `compression_factor: float` parameter on the investigation context; live URL hero CTA passes 0.25 (HOE-DEC-021).
- Visualizer at `/agents/publish_gate/visualizer.py` — called by Publish Gate after NIL clearance, before Visual Review; max 3 regenerations then Day-9 fallback (HOE-DEC-020).
- Broadcast page: curtain rise, AudioContext-as-master-clock sync, embedded cue points (not client-side string-match), reduced-motion + WebVTT captions, music bed at -25dB.
- The Floor: D3 force on Canvas (not SVG) with analytical-position particle pool.

**Verified Vertex AI model IDs (per Day-1 gate `scripts/verify_models.py`):**

| Use | Model ID |
|---|---|
| Editor / Investigator / Storyteller / Equity Editor / Publish Gate | `gemini-3.1-pro-preview` |
| Scouts (4 parallel) | `gemini-3-flash-preview` |
| Wire vocab + NIL near-id check | `gemini-3.1-flash-lite-preview` |
| Broadcast Narrator + Wire Dispatcher TTS | `gemini-3.1-flash-tts-preview` (voice strings TBD Day 1 via `scripts/list_tts_voices.py`) |
| Hero illustrations (Nano Banana Pro) | `gemini-3-pro-image-preview` |
| Utility visuals | `gemini-3.1-flash-image-preview` |

`gemini-3-pro-preview` was discontinued 2026-03-26 — do not use. (HOE-DEC-016.)

**Current engineering blockers:**

- **None yet.** Build has not started. First Day-1 risk: GCP project provisioning + Vertex AI access verification + the model-availability gate (`scripts/verify_models.py`) — these all need to land same-day on Day 1.

**Known open questions to resolve in early sessions:**

- **Day 1:** TTS voice strings — `scripts/list_tts_voices.py` enumerates the 30 prebuilt voices; Charlie + HoE pick Broadcast Narrator + Wire Dispatcher voice strings; pinned into BUILD_SPEC §3.5 and §5.6. (Pulled from Day 5 to Day 1 in v1.3.)
- **Day 1:** Vertex AI Gemini 3 family preview-model availability via `scripts/verify_models.py` against `location='global'`. Hard gate; blocks all downstream agent code.
- **Day 5:** Empirical validation of Gemini TTS word-level timing API surface — does the response include word timestamps natively, sentence-level only, or none? Drives the §7.6 sync implementation. Three fallback paths documented in BUILD_SPEC §3.5.
- **Day 5:** Gemini 3.1 Pro daily quota check; request increase if continuous Day 8-9 operation projects to exceed.
- **Day 9:** Music bed final pick (license receipts in `/audio/music_beds/LICENSES.md` confirmed by Day 9 EOD).
- **Optional Tier 2 (Gemini 3.1 Flash Live "talk to the room"):** default deferred unless v1 is solid by Day 9 EOD.

---

## 3. Investigation Narrative

*This section will accumulate as the build runs. Each meaningful debugging session, design decision, or root-cause analysis goes here. Do not edit prior investigations — they're historical reasoning.*

### Session 0 (2026-05-01) — Project Concept Pivot from Person to Place

**Trigger:** Original product concept was an AI newsroom finding and telling stories of overlooked individual Team USA athletes (a "named-athlete" newsroom). On reading the official hackathon rules in detail, the concept conflicted with the NIL prohibition.

**What we found:**

1. **The NIL rule is strict and disqualifying.** Section 6 of the Official Rules: *"There is a strict prohibition on the use of any athlete's Name, Image, or Likeness (NIL) in your submission. Your project can analyze data that is associated with an athlete by name, but the output should not be at the individual level."* Section 19: immediate disqualification for NIL violations. The Stage One vetting is pass/fail. A submission that names an individual athlete in user-facing output gets DQ'd before judging.

2. **The strict reading also excludes historical athletes.** No carve-out for Wilma Rudolph, Jesse Owens, Jim Thorpe, or any other deceased Olympic figure. The Echo Scout cannot rhyme modern stories with named individuals. It must rhyme them with eras, Games, regions, sports, and patterns.

3. **The pivot makes the project more aligned, not less.** Pivoting story units to PLACES, PROGRAMS, and PATTERNS maps the project directly onto Challenge 2 (The Hometown Success Engine), which explicitly asks for *"a tool that identifies 'Hubs' by correlating geography with the sports Team USA is present in"* and *"focus on the number of Olympians/Paralympians from hometowns instead of the number of medalists."*

4. **The constraint becomes a feature.** A named "NIL Redaction Layer" — a Python module that scans every text artifact for individual identification before it reaches a user-facing surface — turns the compliance burden into a visible trust signal. When the Evidence Drawer opens during the demo's trust-layer beat, the audit log shows *"4 individual references reviewed. 2 aggregated. 2 redacted. Cleared."* That visibility is what a thoughtful Google judge will credit.

**Root cause diagnosis:** The original concept was directionally right (AI newsroom; Olympic broadcast aesthetic; multi-agent; parity as system property) but the protagonist class was the wrong primitive under the rules. Switching the protagonist class from individuals to places preserves all the emotional power (NBC profiles always start with the hometown anyway) and makes the architecture stronger.

**What changed:**

- Concept locked as Pivot A+ (Place over Person). See PROJECT_BRIEF §0.
- Submission category locked as Challenge 2 (Hometown Success Engine). Direct alignment with sponsor-defined challenge instead of the Choose-Your-Own wildcard.
- All four project documents (Constitution, Project Brief, Vision Doc, Build Spec) drafted from the pivoted concept, not retrofitted from the original.
- The NIL Redaction Layer is now a named architectural feature with its own section in the Constitution (§7), full Python module spec in BUILD_SPEC §5.7, dedicated treatment in the Vision Doc, and visible audit-log presence in the demo storyboard.
- Demo voiceover framing is positive, not defensive: *"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin."* Saying "the rules don't allow us to..." in voiceover is on the Kill List.

**Constitutional frame:** This is governance, not orchestration. Python doesn't decide what places to investigate; it decides which texts can reach the user. The NIL Redaction Layer is the same kind of architectural protection as the Paralympic Equity Editor — both exist because the system structurally cares about something we don't trust prompts alone to enforce.

### Session 1 (2026-05-02) — Stack validation pass before any Day-1 code

**Trigger:** Charlie asked HoE Session 1 to read the four canonical docs, use subagents to research every component and technology, then synthesize and update BUILD_SPEC.md. The session is pre-build (no code yet); the goal is to get the spec ready before Day 1 GCP work begins.

**Approach:** Six research streams, originally scoped as parallel subagents:
1. Gemini model fleet validation (May 2026 IDs, voices, Deep Research, grounding, Nano Banana)
2. Google ADK + Cloud Run agent runtime
3. Frontend (Next.js 15 + SSE + Firestore + Framer Motion + D3 + TTS sync)
4. Image generation (Nano Banana Pro / 2)
5. NIL Redaction Layer (athlete data sources, name-match algorithms)
6. Independent BUILD_SPEC.md audit against CONSTITUTION + PROJECT_BRIEF

Two of the technical subagents hit a permissions wall (WebSearch / WebFetch denied in subagent sandbox). The frontend agent partially succeeded by drawing on platform knowledge. **Pivot:** the technical-validation work was completed in the parent HoE session via 9 parallel WebSearches across the same surface area; the spec-audit subagent (file-only, no web needed) ran in the background and returned a 38-finding punch list (10 P0 / 17 P1 / 11 P2).

**What we found (key technical corrections to v1.2):**

1. **`gemini-3-pro-preview` was discontinued 2026-03-26.** Recommended replacement: `gemini-3.1-pro-preview`. (Vertex AI release notes.)
2. **All Gemini 3 family preview models are GLOBAL-ENDPOINT ONLY.** Calls to `us-central1` return 404 model-not-found. The agent runtime must `vertexai.init(project=…, location='global')`. This is the most common Day 1 failure mode in 2026 per the GitHub gemini-cli issue tracker.
3. **The Gemini TTS voice list is 30 prebuilt voices**; v1.2's "Charon" / "Puck" placeholders need to be empirically verified against the API on Day 1 (pulled forward from Day 5/6).
4. **Gemini Deep Research has multi-minute latency** — incompatible with the 4-8s Wire pace. Wrap in 90s timeout with grounded-search fallback that becomes good Wire texture on stall.
5. **ADK has a `ParallelAgent` primitive** — exact fit for the four Scouts.
6. **Cloud Run hard 60-min request timeout** — long demo sessions need client-side reconnect with `Last-Event-ID` replay; heartbeat every 15s; HTTP/2 enabled to escape the 6-connection cap.
7. **`pyahocorasick` (or `ahocorasick_rs`)** for NIL direct-match scanning. Olympedia data via existing public CSV scrapes (`KeithGalli/Olympics-Dataset`, `chanronnie/Olympics`) + Wikidata SPARQL cross-reference + Team USA roster.

**What the audit caught (issues v1.2 had architecturally but didn't pin):**

1. **NIL Wire-level enforcement mechanism unspecified.** v1.2 said "pre-write guard on Firestore" but Firestore has no native pre-write hooks. If implemented as a `onCreate` Cloud Function trigger, the redacted name briefly hits the SSE stream — DQ risk. **Pinned (HOE-DEC-018):** in-process write-through proxy `wire.emit(event)`; direct `firestore.add('wire_events', …)` forbidden by CI lint rule.
2. **NIL Layer fail-open if registry empty.** **Pinned (HOE-DEC-019):** startup assertion ≥500 rows or runtime exits 1; `/health/nil` 503 until loaded.
3. **Visualizer "tool" unlocated** in file system and pipeline. **Pinned (HOE-DEC-020):** `/agents/publish_gate/visualizer.py`, called after NIL clearance + before Visual Review; max 3 regenerations then Day-9 fallback.
4. **Always-on loop unspecified.** **Pinned (HOE-DEC-022):** Editor owns `asyncio.create_task(autonomous_loop())` + Cloud Scheduler watchdog.
5. **High Narrative Density detection logic unspecified** despite a schema column and milestone Wire event. **Pinned (HOE-DEC-023):** ≥3-of-4 Scouts + 10-min window + ≥0.7 confidence each.
6. **"4× compressed time" mechanism unspecified.** **Pinned (HOE-DEC-021):** `compression_factor: float` per investigation context; live URL hero CTA passes 0.25; ambient continues at 1.0.
7. **No cost / observability / error-handling / dev-loop / deploy / IAM / test / SPOF / post-submission ops** — eight new top-level sections (§15-§22) added.

**Constitutional frame:** Every change in v1.3 is operability or correction — not concept drift. Pivot A+, the seven-agent cast, the NIL Redaction Layer as a named feature, the demo storyboard, and the five demo moments are unchanged. The HOE-DECs added (015-024) are tactical clarifications, not concept changes.

---

## 4. Decisions Log (Append-Only)

*Decisions are immutable. Only Charlie can reverse a decision. Append new ones with the next available number.*

| # | Decision | Reasoning | Date |
|---|----------|-----------|------|
| HOE-DEC-001 | Submission category = Challenge 2 (Hometown Success Engine), not Challenge 5 wildcard | Pivot A+ makes us directly aligned with sponsor-defined Challenge 2: hometown hubs, geographic correlation, counts of Olympians/Paralympians from hometowns. Cleaner Stage One vetting box than the wildcard. Submission text will mention parity (Challenge 1) and LA28 momentum (Challenge 3) as natural extensions of the architecture. | 2026-05-01 |
| HOE-DEC-002 | Strict NIL interpretation — no individual athlete names anywhere in user-facing output, including historical athletes | The rule's plain text doesn't carve out historical or deceased athletes. Strict reading is safer (Stage One DQ is unforgiving) AND makes the Echo Scout more sophisticated by forcing era/region/pattern parallels instead of famous-name shorthand. | 2026-05-01 |
| HOE-DEC-003 | Story units are PLACES, PROGRAMS, PATTERNS — never individuals | The protagonist primitive of the room. Pivot A+ baked into the Constitution as Law 4 (Place over Person), into the BUILD_SPEC's `candidates` table (`story_unit_type STRING NOT NULL`), and into every agent prompt. | 2026-05-01 |
| HOE-DEC-004 | NIL Redaction Layer is a named architectural feature, not a content review | Sub-stage 4 of the Publish Gate. Python module that scans every text artifact bound for a user-facing surface (Wire, Broadcast, demo). Three checks (direct match, near-identification, small-aggregate). Three actions (pass / aggregate / return-to-Storyteller). Audit log visible in the Evidence Drawer during the demo. The constraint becomes the credibility flex. | 2026-05-01 |
| HOE-DEC-005 | Demo seed prompt = "Find me a Team USA hometown story I've never heard before" | Aligns demo with Challenge 2 framing. "I've never heard before" creates curiosity. Not "Find me a Team USA story" (too generic), not "Find a hometown story Team USA fans should know" (too editorial-conferencey for the live-investigation moment). | 2026-05-01 |
| HOE-DEC-006 | Demo voiceover framing = positive, never defensive | "Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin." Saying "the rules don't allow us to..." in voiceover is on the Kill List. The architecture speaks for itself in the audit log. | 2026-05-01 |
| HOE-DEC-007 | Cast is locked at seven agents — no 8th, ever | Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate. Sub-scouts (Cinderella, Comeback, Hometown, Echo) live inside Scout Desk. Historian/Geographer/Trend Analyst impulses fold into Investigator as tools. Visualizer is a tool the Publish Gate calls. NIL Redaction Layer is a sub-stage of the Publish Gate. The judge can track 7 in 3 minutes; not 11. | 2026-05-01 |
| HOE-DEC-008 | Tech stack locked: ADK on Cloud Run, BigQuery + Firestore + Cloud Storage, Next.js 15, Gemini 3.1 family + Gemini 3 Flash + Flash-Lite + Deep Research + Nano Banana Pro/2 + Flash TTS | Locked to prevent re-litigation during the build. Re-litigating choices burns 11-day window time we don't have. Specific model assignments by agent role in BUILD_SPEC §3. | 2026-05-01 |
| HOE-DEC-009 | Do NOT use Veo 3.1 (video generation) | Slow, expensive, increases NIL risk. Stills with Ken Burns motion + Narrator voice gives the same emotional effect at lower cost and risk. The Olympic broadcast aesthetic doesn't need video. | 2026-05-01 |
| HOE-DEC-010 | Apache 2.0 license is Day 1 priority #1 — before any code | Stage One auto-DQ trigger if missing on submission day. Five-minute task. LICENSE file in repo root, GitHub License field set, badge visible in About sidebar, README first paragraph references it. Do this before writing any agent code. | 2026-05-01 |
| HOE-DEC-011 | Internal submission deadline = Sunday May 10 EOD (~24h before Devpost hard deadline May 11 5:00pm PT) | Devpost servers crowd at the buzzer. Cloud Run deployments can fail. Last-minute compliance discoveries need time to fix. Day 11 is buffer for the things that always go wrong. Submitting at Day 11 hour 7:59pm EDT is a failure mode. | 2026-05-01 |
| HOE-DEC-012 | Anchor story selected on Day 9 from organic discoveries — not pre-planned | The system runs continuously Day 8-9 and produces 15-25 organic place/program/pattern stories. Charlie picks the anchor by which one makes him sit back from the laptop. Pre-selecting the anchor before Day 9 violates this decision. The Equity Editor causing the anchor (via feed-drift detection promoting a Paralympic-anchored place) is also organic. | 2026-05-01 |
| HOE-DEC-013 | Honest production, not faked liveness — every Wire event has a `mode` field (`live | replay | published`) | The single live investigation in the demo runs at 4× compressed time with the honest label "Live investigation — playback at 4×." Olympic broadcasts run produced packages constantly. We do too, and we say so. Faked-live is broken. | 2026-05-01 |
| HOE-DEC-014 | NIL Redaction Layer enforcement runs at the Wire level too, not only at Publish Gate | The same Python module runs as a pre-write guard on Firestore `wire_events` before any Scout/Editor/Investigator message emits to the frontend. Direct matches at Wire level always trigger redaction. This prevents a Scout from leaking a name in an in-progress thinking message even if the Storyteller never sees that name. | 2026-05-01 |
| HOE-DEC-015 | Vertex AI calls use `location='global'`, not `us-central1` | All Gemini 3 family preview models (gemini-3.1-pro-preview, gemini-3-flash-preview, gemini-3.1-flash-lite-preview, gemini-3.1-flash-tts-preview, gemini-3-pro-image-preview, gemini-3.1-flash-image-preview) are global-endpoint only — regional endpoints return 404 model-not-found. The agent runtime calls `vertexai.init(project=..., location='global')` and sets `GOOGLE_CLOUD_LOCATION=global`. Cloud Run service deploys to `us-central1` for compute; the model call is what routes globally. | 2026-05-02 |
| HOE-DEC-016 | Use `gemini-3.1-pro-preview` (not `gemini-3-pro-preview` which was discontinued 2026-03-26) | Vertex AI release notes confirm the deprecation. New ID is the recommended successor. Day-1 gate `scripts/verify_models.py` confirms response on the global endpoint before any agent code lands. | 2026-05-02 |
| HOE-DEC-017 | Pull TTS voice verification forward from Day 5/6 to Day 1 | The Gemini 3.1 Flash TTS API has 30 prebuilt voices; v1.2's "Charon" / "Puck" placeholders are not assumed valid. Run `scripts/list_tts_voices.py` Day 1, audition 4-6 candidates per profile, pin the voice strings into BUILD_SPEC §3.5 and §5.6. The Narrator is the Broadcast's emotional spine — max iteration buffer is non-negotiable. (Closes audit P2-#35.) | 2026-05-02 |
| HOE-DEC-018 | Wire-level NIL guard is an in-process write-through proxy (`wire.emit(event)`); direct `firestore.add('wire_events', …)` is forbidden | Firestore has no native pre-write hooks. A Cloud Function `onCreate` trigger that mutates documents post-write would race the SSE stream — the redacted name briefly hits the frontend = DQ risk. The proxy at `/agents/wire/emit.py` invokes the NIL Redaction Layer synchronously before `firestore.add(...)`. CI lint rule `scripts/lint_no_direct_wire_writes.py` fails the build on direct calls. (Closes audit P0-#4.) | 2026-05-02 |
| HOE-DEC-019 | NIL Redaction Layer fails CLOSED, not open — runtime exits 1 if `athlete_registry` has <500 rows on startup | An empty registry would silently pass everything through, which is exactly the failure the Layer exists to prevent. `/health/nil` returns 503 until the registry loads. Refresh failures preserve the prior in-memory automaton. (Closes audit P0-#5.) | 2026-05-02 |
| HOE-DEC-020 | Visualizer is a Python tool at `/agents/publish_gate/visualizer.py`, called by Publish Gate after NIL clearance and before Visual Review (sub-stage 7); max 3 regenerations then `/data/fallback_heroes/` | v1.2 named the Visualizer as a tool but didn't pin file location, invocation order, or failure-mode behavior. The Day-9 pre-cache per anchor candidate guarantees no Day-10 demo failure due to repeated safety-filter rejections. (Closes audit P0-#6 and P1-#19.) | 2026-05-02 |
| HOE-DEC-021 | "4× compressed time" demo mechanism is `compression_factor: float` parameter on investigation context (default 1.0; live URL hero CTA passes 0.25) | Per-investigation, not global. Ambient Wire continues at 1.0 in parallel. Wire event `timestamp` reflects real wall-clock time; only the inter-emission cadence compresses. Per CONSTITUTION Rule 3 — "honest production, not faked liveness." (Closes audit P0-#10.) | 2026-05-02 |
| HOE-DEC-022 | Agent runtime always-on loop = `asyncio.create_task(autonomous_loop())` in the Editor + Cloud Scheduler 5-min watchdog | The Editor owns the loop. 30-90s think-cycle. Cloud Scheduler pings `/health/heartbeat` every 5 min; stale heartbeat triggers `gcloud run services update` to force a new revision. Loop exits cleanly on SIGTERM. (Closes audit P1-#11.) | 2026-05-02 |
| HOE-DEC-023 | High Narrative Density fires on **≥3-of-4 Scouts** writing a `LeadReport` for the same `story_unit_id` within a **rolling 10-minute window** AND **each Scout's confidence ≥0.7** | v1.2 had the schema column and the milestone Wire event but no detection logic. Detection lives at `/agents/scouts/hnd_detector.py`. HND firing is one of the strongest Wire moments — the spec must define it. (Closes audit P1-#12.) | 2026-05-02 |
| HOE-DEC-024 | Frontend uses server-side `onSnapshot → SSE` forwarding, not direct Firebase JS SDK subscription | Bundle weight (50-80KB), public security-rules complexity, ordering inconsistencies with `metadata.hasPendingWrites`, and the `<1s` first-paint pre-seed all argue for server-side. The Next.js Route Handler at `/web/app/api/wire/stream/route.ts` holds the `onSnapshot` listener and forwards events to clients over SSE. Firestore rules deny all client reads. | 2026-05-02 |
| HOE-DEC-025 | TTS voices pinned: Broadcast Narrator = `Algenib`, Wire Dispatcher = `Fenrir`, single-voice fallback = `Fenrir` | Day-1 audition complete (HOE-DEC-017). Six candidates auditioned (Charon, Algenib, Iapetus, Puck, Fenrir, Orus) reading the same place-only paragraph with `[short pause]` and `[emphasis]` inline tags, ~24s each, 24kHz 16-bit mono WAVs in `audio/voice_audition/`. Charlie's pick: Algenib (warm/mid-tone/documentary fit for Narrator) + Fenrir (clipped/lower-register fit for Dispatcher). Both used; Fenrir is the default if any future single-voice context arises. Pinned in BUILD_SPEC §3.5 + §5.6 and tech_snapshot.md §4. | 2026-05-03 |
| HOE-DEC-026 | FastAPI is the agent-runtime ASGI framework | Single uvicorn process per Cloud Run instance. Lifespan-managed boot/shutdown wires the seven-agent boot sequence + `/health/heartbeat`, `/health/nil`, `/health/agents` endpoints + the asyncio autonomous-loop task. No Flask/aiohttp alternatives; locked to prevent Day-2 relitigation. | 2026-05-03 |
| HOE-DEC-027 | `ahocorasick_rs` is the primary Aho-Corasick library; `pyahocorasick` is the fallback if Cloud Run base image lacks the rs wheel | Rust-backed, ~5× faster than `pyahocorasick` on the Wire-emit hot path. Manylinux wheels available for Python 3.12. Fallback decision (if needed) must be logged in `tech_snapshot.md` along with the reason. | 2026-05-03 |
| HOE-DEC-028 | Athlete registry seeded: 11,188 rows in `storytellers_room.athlete_registry` (production) and `storytellers_room_dev.athlete_registry` (dev), seeded 2026-05-03 | Loader at `data/load_athlete_registry/` (1,669 LOC + 30 unit tests, all passing). Sources: KeithGalli/Olympics-Dataset (11,167 Olympedia records filtered NOC=USA) + Wikidata SPARQL (31 medalist cross-reference rows for variant names). NIL Layer fail-closed assertion (≥500 rows, HOE-DEC-019) satisfied 22× over. Snapshot at `data/athlete_registry_snapshot/registry.2026-05-03.json` (gitignored, 5.4 MB). | 2026-05-03 |
| HOE-DEC-029 | Compressed-time pacing formula is **multiplicative**: `effective_delay = target_delay × compression_factor`. `compression_factor=0.25` → 4× faster (a 6s pause becomes 1.5s) | The v1.3 BUILD_SPEC §6.10 prose incorrectly said "target / compression_factor" (which would make 0.25 = 4× SLOWER, the opposite of HOE-DEC-021's intent). The worked example (6s → 1.5s at 0.25) was correct, and the implementation worker shipped multiplicative to match the worked example + HOE-DEC-021 (live URL CTA = 4× faster). Spec docs and `/agents/wire/pacing.py` now agree. `compression_factor` is bounded `[0.05, 1.0]`. | 2026-05-04 |
| HOE-DEC-030 | `GOOGLE_GENAI_USE_VERTEXAI=true` env var is REQUIRED at runtime boot, before any ADK `LlmAgent` construction | ADK 2.0 Beta uses the `google-genai` SDK internally. By default, `google-genai` Client() picks the Gemini Developer API path which requires an API key. Without `GOOGLE_GENAI_USE_VERTEXAI=true`, ADK Runner calls fail with `ValueError: No API key was provided.` even though `vertexai.init(project=..., location='global')` succeeded. Fix is set in `agents/runtime.py::_init_vertex_ai()` alongside the vertexai.init call. The Cloud Run deploy must also set this env var (see DEPLOYMENT.md update). Caught empirically Day-3 first live `think_once` smoke test. | 2026-05-04 |
| HOE-DEC-031 | FastAPI route handlers using framework-injected types (`Request`, `BackgroundTasks`, etc.) MUST have the type imported at MODULE LEVEL (not inside `_build_app()`) when `from __future__ import annotations` is in effect | PEP 563 makes annotations strings at runtime. FastAPI uses `inspect.get_type_hints(handler_func)` to resolve string annotations; `get_type_hints` looks up names via `handler_func.__globals__` — which is the module's globals dict, NOT the local scope of `_build_app()`. If `Request` is imported only inside `_build_app()`, FastAPI can't resolve `request: Request` and falls back to "must be a query parameter" → returns 422. Fix in `agents/runtime.py`: `_FastAPIRequest` aliased at module level (guarded import); handler signatures use `_FastAPIRequest` directly. The same trap applies to `Response` injection (already mitigated in /health/nil by using JSONResponse directly). Caught empirically Day-3 on POST /api/investigate. | 2026-05-04 |
| HOE-DEC-032 | Prompt files use `{snake_case}` placeholders for voice-fragment EXAMPLES, but `agents/prompts.py::load_prompts` rewrites them to `[snake_case]` at load time before passing to ADK `LlmAgent.instruction` | ADK 2.0 Beta's `LlmAgent.instruction` interprets `{name}` patterns as session-state context variables and raises `KeyError: 'Context variable not found'` at Runner invocation. Our prompts use `{place}`, `{region}`, `{n}`, `{sport-era}`, etc. as illustrative slots (the LLM imitates the pattern; nothing literal substitutes). Sanitization is regex-based, idempotent, and lowercase-only (preserves any legitimate capital-letter brace syntax). 10 unit tests in `agents/test_prompts.py`. Caught empirically Day-3 afternoon smoke test of full Editor→Scout cycle. | 2026-05-04 |
| HOE-DEC-033 | `CostCounter.assert_under_ceiling` accepts `sub_agent=` filter for per-sub-scout enforcement | Original signature only had `agent=`. The Scout Desk's `dispatch_one` legitimately wants per-Scout ceilings (e.g., Cinderella vs Hometown grounded-search budget). Added `sub_agent: SubAgentId | None = None` parameter; matches the existing key-shape `(date, agent, sub_agent, axis, model)` so the row-sum filter works. Caught empirically Day-3 afternoon smoke test as a `TypeError` from Scout Desk's call. | 2026-05-04 |

---

## 5. Lessons Learned (Append-Only)

*Lessons are durable patterns that should inform future sessions. Append new ones; only prune when superseded.*

1. **Read the rules before writing the spec.** The Pivot A+ moment came from re-reading the official rules in detail. The original "named-athlete newsroom" concept would have been disqualified at Stage One vetting. Reading the rules takes 30 minutes; rebuilding around a misread costs days. Hackathon rules are not a formality.

2. **Compliance constraints can become features when made architectural.** A content-review approach to NIL safety would have been invisible to the judges and brittle in implementation. A named "NIL Redaction Layer" with structured audit-log output is visible, testable, and turns the constraint into a trust signal. The same logic applies to the Paralympic Equity Editor's veto power — what could have been a prompt instruction is instead an agent with structural authority.

3. **The seven-agent cap is a UX constraint, not a code constraint.** Every impulse to add an 8th agent during the build will be a temptation. Fold it into an existing agent or sub-stage. A judge watching a 3-minute demo can track 7 named entities. They cannot track 11. Adding agents reduces clarity even if it adds capability.

4. **Hard things should look easy. Easy things should look hard.** The Buddy Rich principle. Database queries get wrapped in visible deliberation; multi-agent orchestration gets presented cleanly. The Wire's 70/30 thinking/milestone ratio is the implementation of this principle. A Wire that reads like a press release fails. A Wire that reads like sleeves rolled up wins.

5. **The Decision Filter saves time during the build.** "Does this serve one of the five demo moments?" is the only question worth asking when scope-cutting under pressure. Features that serve no demo moment do not ship, even if they would be technically interesting. The 11-day window does not have room for nice-to-haves.

6. **Validate the model-fleet docs before locking the spec.** v1.2's locked stack named "Gemini 3.1 Pro," "Nano Banana Pro," etc. as if they were stable production IDs. They're all preview, the IDs have churned (`gemini-3-pro-preview` was discontinued mid-flight), and the global-endpoint requirement is the single most common Day 1 failure mode in 2026. Half a session of Day-1 research catches it; a Day-2 standup catching it costs a day of debugging on the wrong endpoint.

7. **Compliance enforcement that depends on a Cloud Function trigger races the user-facing surface.** The audit caught that "pre-write guard on Firestore" in v1.2 was ambiguous — implementations using `onCreate` triggers post-write would briefly leak names. The fix is mechanical (in-process write-through proxy), but the lesson is durable: when the demo's trust signal is "the system policed itself," the policing must be synchronous-before, not asynchronous-after.

8. **Subagents inherit a different permission profile than the parent session.** Two of three technical-research subagents in HoE Session 1 hit a permissions wall (WebSearch / WebFetch denied) and could not complete. The parent session had the same tools available and could do the work directly. When a research task is web-heavy, validate the subagent has the permissions before launching, or do it in the parent. File-only audit subagents (which only need `Read`) work fine.

9. **The audit subagent caught architectural ambiguities the original author misses.** v1.2 was written after careful thought; HOE-DEC-018 (write-through proxy) and HOE-DEC-019 (fail-closed assertion) and HOE-DEC-022 (always-on loop) and HOE-DEC-023 (HND detection logic) were all things the original author "knew" but hadn't pinned to a file. An independent read with a "what would actually break this?" lens surfaces the implicit assumptions. Schedule one of these passes per major spec version.

10. **Implementation surfaces the spec bugs that review misses.** HOE-DEC-029 — the v1.3 compression-formula contradiction (prose said divide; worked example said multiply) — went through HoE Session 1's stack-validation pass, the audit subagent, the Plan-style worker, and HoE review of the plan, all without anyone noticing. The implementation worker caught it in 30 minutes by writing the test for a 6s/0.25 case. Lesson: a worked example with concrete numbers is worth more than a paragraph of prose. When pinning a quantitative architectural rule, always ship a worked example AND have the unit test reference the same numbers. Tests are spec.

11. **Smoke test against live infrastructure once the skeleton compiles.** HoE Session 2 caught two bugs the worker's environment couldn't (FastAPI Response signature; async on_snapshot NotImplementedError) by booting `uvicorn agents.runtime:app` against the actual GCP project once the skeleton landed. Worker sandboxes don't bind ports or install network deps; the production-equivalent boot is the HoE's job. Schedule one of these per major component delivery.

12. **Each fan-out of workers tends to surface ~2 integration bugs the workers' sandboxes can't catch.** Day-2 fan-out: FastAPI Response sig + async on_snapshot. Day-3 morning fan-out: GOOGLE_GENAI_USE_VERTEXAI env var + FastAPI Request annotation. Day-3 afternoon fan-out (3 workers in parallel): ADK instruction template parsing of `{slot}` patterns + CostCounter.assert_under_ceiling missing `sub_agent` parameter. Pattern: workers test against mocks; HoE smoke-tests against the live SDK. **Budget ~30 minutes per fan-out for HoE integration debugging; don't try to commit immediately after worker completion.**

13. **Three parallel workers can edit `agents/runtime.py` without conflicts if their changes are additive in distinct sections.** Day-3 afternoon's HND worker added `_build_firestore_sync_client` + `firestore_sync=` arg to HndDetector; Scout worker added `cost_counter=cost_counter` to the ScoutDesk constructor; vocabulary worker did NOT touch runtime.py. Both runtime.py edits landed cleanly because the two workers were modifying different lines that didn't conflict. **For future fan-outs that all touch the same file, give each worker explicit "modify only these lines" guardrails to keep diffs orthogonal.**

14. **Over-redaction is the right side to err on for the Day-2 NIL stub.** Day-3 smoke test showed `[redacted] State` and `[redacted]nitoring` — the model wrote "Penn State" and "Monitoring" and the Aho-Corasick automaton matched something in the registry (likely a name like "Penn" or short-token false positive on "Mo"). The full NIL Layer (Day-6/7) adds the 50-char context-window disambiguation pass that filters these false positives. For Day-2 stub: over-redaction is acceptable; under-redaction would be a DQ risk. Confirms HOE-DEC-019 fail-closed semantics are working as designed.

---

## 6. Work Log (Append-Only)

*Each session appends its work. Format: dated table of changes with "Deployed" column tracking whether the change is live on Cloud Run / live in production yet. Archive entries older than 5 days only if the doc is getting unwieldy — most of the build will fit in this section uncompressed.*

### 2026-05-01 — HoE Session 0 (Pre-build scaffolding)

| Change | Commit | Deployed |
|---|---|---|
| Project concept pivot from named-athlete newsroom to Place-over-Person broadcast room (Pivot A+) | N/A (pre-repo) | N/A |
| `CONSTITUTION.md` v1.1 drafted — six laws including Law 4 (Place over Person), NIL Redaction Layer named architectural feature | N/A (pre-repo) | N/A |
| `PROJECT_BRIEF.md` v1.1 drafted — Concept Lock §0, Challenge 2 submission, NIL strict interpretation, Pre-Submission Verification Checklist | N/A (pre-repo) | N/A |
| `What_is_The_Storytellers_Room.md` v1.1 drafted — vision narrative with Place over Person and NIL Redaction Layer threaded throughout | N/A (pre-repo) | N/A |
| `Docs/Engineering/BUILD_SPEC.md` v1.1 drafted — full agent specs, NIL Redaction Layer Python module spec, schemas, Wire vocabulary samples, demo storyboard, sound design, 11-day phasing, acceptance criteria | N/A (pre-repo) | N/A |
| `Docs/Engineering/HOE-HANDOFF.md` (this document) drafted — Session 0 baseline | N/A (pre-repo) | N/A |
| HOE-DEC-001 through HOE-DEC-014 logged | N/A (pre-repo) | N/A |
| Lessons 1-5 logged | N/A (pre-repo) | N/A |
| **Result:** All four project documents and the HoE handoff are drafted and ready for Charlie to copy into `/Users/charliereagan/projects/Google_Olympics_Hackathon`. No code yet. No GCP yet. Day 1 begins with Apache 2.0 license + GCP project + repo skeleton. | — | — |

### 2026-05-03 — HoE Session 2 (Day 1 provisioning)

| Change | Commit | Deployed |
|---|---|---|
| Role separation codified: HoE directs/reviews/tests/commits/deploys; worker agents write code. Workers never commit, never deploy. Logged as feedback memory and added to CLAUDE.md "Operating model — director, not coder" section. | (this session) | N/A |
| `CLAUDE.md` created at repo root — alignment prompt for every coding session. | (this session) | N/A |
| `DEPLOYMENT.md` created at repo root — deployment procedure document. | (this session) | N/A |
| `Docs/Engineering/tech_snapshot.md` created — runtime ground truth. | (this session) | N/A |
| `Docs/Engineering/backlog.md` created — ideas, bugs, deferred actions. | (this session) | N/A |
| GitHub repo created at https://github.com/charliereagan/Google_Olympics_Hackathon (PRIVATE). License badge auto-detected as Apache 2.0 by GitHub. Initial commit `9d48dd7`. | `9d48dd7` | N/A |
| ADC quota project switched to `predictive-fx-495200-j4` via `gcloud auth application-default set-quota-project` (no interactive login required). | (gcloud) | ✓ |
| 8 APIs enabled on hackathon project: aiplatform, firestore, run, secretmanager, cloudbuild, cloudscheduler, texttospeech, artifactregistry, billingbudgets. | (gcloud) | ✓ |
| Reachability sweep confirmed all 7 verified Gemini model IDs respond on `location='global'` and bill against `predictive-fx-495200-j4`. URL/version/verb shape per model documented in `tech_snapshot.md §3`. | (gcloud) | ✓ |
| 30 Gemini Chirp3 HD en-US voices enumerated. **v1.2 placeholders Charon and Puck both verified to exist.** Voice catalog in `tech_snapshot.md §4`. | (gcloud) | ✓ |
| 2 service accounts created: `agent-runtime@`, `web-frontend@`. (Note: `web` was below the 6-char SA-ID minimum; renamed `web-frontend`. Docs updated.) IAM bindings: `agent-runtime` got 8 roles (aiplatform.user, datastore.user, bigquery.dataViewer, bigquery.jobUser, storage.objectAdmin, secretmanager.secretAccessor, logging.logWriter, cloudtrace.agent); `web-frontend` got 4 (datastore.user, storage.objectViewer, logging.logWriter, run.invoker). | (gcloud) | ✓ |
| Firestore `(default)` database created in `nam5` (US multi-region), Native mode, `REALTIME_UPDATES_MODE_ENABLED`. | (gcloud) | ✓ |
| BigQuery: 2 datasets created (`storytellers_room`, `storytellers_room_dev`) in US multi-region; **14 tables created** (7 each: candidates, athlete_registry, historical_athletes, geography, championships, agent_call_counters, agent_errors). Schemas committed to `data/bq_schemas/*.json`. | (this session) | ✓ |
| Cloud Storage: 3 buckets created (`storytellers-room-hero-images`, `storytellers-room-audio`, `storytellers-room-fallback-heroes`) — US multi-region, uniform bucket-level access. | (gcloud) | ✓ |
| Artifact Registry: `storytellers-room` Docker repo created in `us-central1` for Cloud Run images. | (gcloud) | ✓ |
| Budget alerts: 3 created ($100 informational, $200 audit, $300 kill-switch) — each with 50%, 90%, 100%, and 100%-forecasted-spend thresholds. | (gcloud) | ✓ |
| `tech_snapshot.md` refreshed with the new ground-truth state. `DEPLOYMENT.md` updated for the `web-frontend` SA name. | (this session) | N/A |
| **Result:** Day 1 GCP provisioning complete. No code yet. Day 2 begins agent core: Editor, Investigator, four sub-scouts, Wire vocabulary, Wire stream rendering. Outstanding Day 1 task: Day-1 voice audition (`scripts/list_tts_voices.py` per HOE-DEC-017) and athlete registry seed loader. | — | — |
| Day-1 ops scripts shipped (worker delivered, HoE reviewed + ran + committed): `scripts/verify_models.py` (7/7 model probes green), `scripts/list_tts_voices.py` (6 audition WAVs in `audio/voice_audition/`), `scripts/check_license.sh` (Apache 2.0 CI gate, exit 0), `scripts/lint_no_direct_wire_writes.py` + matcher unit tests (HOE-DEC-018 enforcement). | `5dc81ef` | N/A |
| Voice audition completed; HOE-DEC-025 ratified: Broadcast Narrator = Algenib, Wire Dispatcher = Fenrir, single-voice fallback = Fenrir. Pinned in BUILD_SPEC §3.5 + §5.6, tech_snapshot.md §4, backlog.md, this handoff. | `298fc59` | N/A |
| Athlete registry seeded (HOE-DEC-028). Worker shipped `data/load_athlete_registry/` (1,669 LOC + 30 unit tests, all passing); HoE reviewed code, ran validation (pytest 30/30, lint clean, license clean), and ran the production load. **11,188 rows in both `storytellers_room.athlete_registry` (production) and `storytellers_room_dev.athlete_registry` (dev).** Snapshot artifact in `data/athlete_registry_snapshot/registry.2026-05-03.json` (gitignored). | (this commit) | ✓ |
| Agent-runtime skeleton plan delivered by Plan-style worker; HoE reviewed and amended with HOE-DEC-026 (FastAPI), HOE-DEC-027 (ahocorasick_rs primary), and `ATHLETE_REGISTRY_DATASET` env var. Plan saved to `Docs/Engineering/plans/agent-runtime-skeleton-v1.md` for the implementation worker to execute. | `aca01a2` | N/A |
| Day-2 agent-runtime skeleton implemented by worker `a186bc88791588810` per the saved plan. **4,137 LOC across ~30 files** in `/agents/`, `/prompts/`, `/data/streaming_profiles.json`, `/requirements.txt`. Topo-sorted from §H of the plan. Voice signatures from BUILD_SPEC §5.1/§5.2 reproduced verbatim in `/prompts/*.md`; Echo Scout's wrong-echo examples use `[named sprinter]` placeholders rather than historical names. ADK + Vertex AI imports are deferred (try/except ImportError) so unit tests run without the heavy deps; production deploy installs everything via `requirements.txt`. NIL Layer stub uses three-tier backend: `ahocorasick_rs` → `pyahocorasick` → pure-Python (logged on each path). | (this commit) | N/A |
| HoE review verification: **64 unit tests + 1 skipped (Firestore emulator)**, all green. `pytest agents/ tests/ data/load_athlete_registry/ scripts/tests/`. Lint clean (25 files scanned, 0 violations). License gate clean. **Live smoke test:** uvicorn against project `predictive-fx-495200-j4` + `ATHLETE_REGISTRY_DATASET=storytellers_room_dev` boots cleanly. `/health/heartbeat` 200 with `boot_time` populated → full lifespan completed. `/health/nil` 200 with `registry_size: 11188` → NIL Layer correctly bootstrapped against the 11,188-row registry. `/health/agents` 200 with all 7 cast members + 11 streaming profiles. **`ahocorasick_rs 1.0.3` installed cleanly; no fallback to `pyahocorasick` needed.** | (this commit) | ✓ locally |
| HoE one-line fix during review: `/health/nil` was using `async def health_nil(response: Response)` to mutate status code; FastAPI 0.136 interpreted that as a query parameter and returned 422. Replaced with explicit `JSONResponse(status_code=503, content=...)`. Logged in backlog. | (this commit) | N/A |
| Two known gaps logged in backlog: (1) `firestore_v1.AsyncCollectionReference.on_snapshot` raises NotImplementedError — HND detector falls back to stub mode at boot; Day-3 fix is the sync watcher on a thread per plan §G.2. (2) ADK UserWarning + authlib deprecation warning, both cosmetic. | `79a199c` | N/A |
| HoE doc fix: BUILD_SPEC §6.10 prose said "target / compression_factor" but the worked example said multiplicative. Implementation worker correctly shipped multiplicative to match worked example + HOE-DEC-021. HoE corrected the spec prose (HOE-DEC-029), added a worked-example callout, and noted the bound `[0.05, 1.0]`. Lessons 10 + 11 added: tests-are-spec; smoke-test-against-live-infra after each major component. | `39dbde0` | N/A |
| Day-3 morning: Editor `think_once` body + `POST /api/investigate` endpoint shipped by worker `ac6b5431bd2f642ca` per the saved plan. **Real ADK Runner integration:** uses `google.adk.Runner.run_async` against `gemini-3.1-pro-preview` on `vertexai.init(location='global')`. Tool binding via closures (sidesteps Pydantic v1/v2 question — ADK introspects function signatures directly). 22 unit tests added (5 think_once + 14 /api/investigate + 3 cost-counter). agents/editor/agent.py grew 96 → 680 LOC. Empirical findings on plan §G open questions: (1) `vertexai.init(location='global')` flows through ADK *with* `GOOGLE_GENAI_USE_VERTEXAI=true` env var (HOE-DEC-030); (2) ADK Runner auto-executes tool calls (no manual dispatch); (3) Pydantic v1/v2 non-issue with closure tool binding; (4) ADK module layout: `from google.adk import Runner; from google.adk.agents import LlmAgent; from google.adk.sessions import InMemorySessionService`; ADK rejects hyphens in `app_name` (caught empirically; using `storytellers_room`). | (this commit) | N/A |
| HoE smoke test on Day-3 worker output caught two bugs the worker's sandbox couldn't reproduce: (1) ADK Runner failed with `ValueError: No API key was provided` because `GOOGLE_GENAI_USE_VERTEXAI` env var wasn't set → fixed in `_init_vertex_ai()` (HOE-DEC-030); (2) `POST /api/investigate` returned 422 with `{loc: ["query", "request"]}` because `Request` was imported inside `_build_app()` and `from __future__ import annotations` + `get_type_hints()` resolves via module `__globals__` → fixed by hoisting `_FastAPIRequest` to module level (HOE-DEC-031). After fixes: live POST `/api/investigate` with seed prompt + compression_factor=0.25 returned **HTTP 202** with `investigation_id: inv-5a886e629d70`; `last_think_cycle` populated; Editor's `think_once` ran end-to-end against live `gemini-3.1-pro-preview`. | (this commit) | ✓ locally |
| Firestore composite index `wire_events:(mode ASC, timestamp DESC)` created via gcloud — required by Editor's `_read_recent_published` query. Index state: `CREATING` at commit time (5-15 min typical). Editor's exception handler catches `FailedPrecondition` and returns empty list during the build window — non-fatal. Same query pattern may need similar indexes on `lead_reports` (`status` filter) once Day-4 Scout writes land — defer until then. | `bd6ac3e` | ✓ creating |
| Firestore composite index `wire_events:(mode ASC, timestamp DESC, __name__ ASC)` finished building — index name `CICAgOjXh4EK`, state `READY`. Editor's `_read_recent_published` now runs natively. | `38bda52` | ✓ READY |
| Day-3 afternoon: three workers fanned out in parallel: (1) HND sync-watcher fix per plan §G.2, (2) Wire vocabulary library (558 fragments × 10 agents in `data/wire_vocabulary.json` + `agents/wire/vocabulary.py` loader/sampler), (3) Scout sub-agent bodies + ParallelAgent wire-up + `dispatch_scout` real call. All three landed in the working tree without conflicts. **+30 unit tests** (4 HND listener + 17 vocabulary + 9 Scout desk + 2 dispatch_scout in editor). Empirical findings: ADK 2.0 Beta's `ParallelAgent` doesn't aggregate sub-agent return values cleanly → ScoutDesk uses `asyncio.gather` over per-scout Runners, with `parallel_agent` property exposed on the desk for the future Floor view + agent-graph visualization. | (this commit) | N/A |
| HoE smoke test caught two more bugs the workers' sandboxes couldn't reproduce: (1) HOE-DEC-032: ADK `LlmAgent.instruction` parses `{slot}` patterns as session-state variables → `KeyError` at Runner invocation. Fixed by adding `_sanitize_for_adk` to `agents/prompts.py::load_prompts` (rewrites `{snake_case}` → `[snake_case]`). 10 unit tests added. (2) HOE-DEC-033: ScoutDesk's `dispatch_one` called `cost_counter.assert_under_ceiling(sub_agent=...)` but the method signature only accepted `agent=`. Fixed by adding the `sub_agent` filter; matches the existing key-shape. | (this commit) | N/A |
| **End-to-end Day-3 close-out smoke test (live infra):** boot completed; `last_think_cycle` populated; `POST /api/investigate {prompt: "Find me a Team USA hometown story...", compression_factor: 1.0}` → HTTP 202; **Editor dispatched Cinderella + Hometown Scouts**; both produced Lead Reports persisted to Firestore (`program_penn_state_wrestling [cinderella] confidence=0.84`; `program_illinois_wheelchair_basketball [hometown] confidence=1.0`); Editor emitted decision-class Wire events to Firestore reflecting queue state (`Queue healthy. Monitoring wrestling and wheelchair basketball programs.`). NIL Redaction Layer caught place-name false-positives (`[redacted] State`, `[redacted]nitoring`) and persisted redacted text — the write-through proxy worked exactly as designed. False-positive disambiguation is Day-6/7 work (full Layer adds 50-char context-window check). | `35d9ba6` | ✓ live |

### 2026-05-04 — Day 4 (Investigator + vocabulary consumers + HND verification + boot-warning filters)

| Change | Commit | Deployed |
|---|---|---|
| Three workers fanned out in parallel: (1) Investigator agent body; (2) Wire vocabulary consumer wiring; (3) HND firing integration test + probe script + boot-warning filters. All three landed in working tree without conflicts (each worker's runtime.py edits were in distinct sections). | (this commit) | N/A |
| **Investigator body** (worker a6de9d6ece7959d91): `agents/investigator/{__init__.py, agent.py, tools.py, test_agent.py, test_tools.py}` (~1,680 LOC). Real ADK Runner against `gemini-3.1-pro-preview`. Tools: `read_lead_report`, `grounded_search`, `query_historical_athletes` (aggregate-only — no athlete names cross the function boundary), `query_geography`, `call_deep_research` (stub — Vertex AI surface for Deep Research not yet stable in google-genai SDK; backlog), `write_investigation_packet`. Editor's `dispatch_investigator(lead_report_id)` tool wired to call `investigator.investigate()`. `prompts/investigator.md` shipped with §5.3 voice signature verbatim + place-over-person constraints. 18 unit tests + 2 Editor dispatch tests. | (this commit) | N/A |
| **Wire vocabulary consumers** (worker a02022b7a22d96902): `WireVocabulary` loaded at boot (Step 5b in lifespan); `wire_vocabulary` field added to `RuntimeState`; threaded into Editor + ScoutDesk constructors; `pull_vocabulary` tool added to Editor + each Scout (closure binds the right JSON key — `cinderella_scout`, etc.); `agents/wire/vocabulary.py::fill()` updated to handle BOTH `{snake_case}` and `[snake_case]` slot syntax (HOE-DEC-032 forward-compat). One tool-surface line added to each of the 5 prompt files. `/health/agents` returns `vocabulary_loaded: bool` + `vocabulary_fragment_count: int`. +9 tests. | (this commit) | N/A |
| **HND end-to-end test + probe + log filters** (worker a857fcd687a0545f6): `tests/integration/test_hnd_fires_end_to_end.py` (2 tests — positive 3-of-4 fire path, negative 2-of-4 no-fire). `scripts/probe_hnd.py` — operational probe that writes 3 synthetic Lead Reports to `lead_reports`, polls `wire_events` for the milestone, with cleanup. `runtime.py::_configure_logging()` surgically suppresses 3 cosmetic boot warnings (authlib.jose deprecation; ADK PLUGGABLE_AUTH UserWarning; google-genai non-text-parts message-level filter). Each filter is message-pattern-specific so future legitimate warnings still surface. | (this commit) | N/A |
| **End-to-end Day-4 smoke test (live infra):** boot completed cleanly (no warning noise); `/health/agents` shows **investigator: idle** (was 'shell' Day-3); `vocabulary_loaded: True, fragments: 558`. `POST /api/investigate` → 202; **Editor → Scout → Investigator chain captured live in Wire events:** `[editor] decision: [redacted] echo pattern found in [redacted] Placid. Investigator, 90 seconds.` → `[investigator] thinking: pulling sources. confirming geography and historical parallel...`. Echo Scout era-texture working: `this echoes the pre-war winter sports regional emergence`. Place-over-Person discipline 100% — `place_chula_vista`, `1932 pioneering foundation`, `1980 modernization`, zero athlete names. `investigation_packets` write didn't land within 90s wait window (Pro model deliberation + tools take longer); dispatch chain confirmed working. | (this commit) | ✓ live |

### 2026-05-02 — HoE Session 1 (Stack validation pass)

| Change | Commit | Deployed |
|---|---|---|
| `BUILD_SPEC.md` v1.2 → v1.3. Major changes: verified Vertex AI model IDs (replacing v1.2 placeholders), `location='global'` requirement pinned, NIL Wire-level enforcement mechanism pinned as in-process write-through proxy, NIL fail-closed startup assertion pinned, Visualizer file location and pipeline pinned, "4× compressed time" mechanism pinned, always-on loop pinned, HND detection logic pinned, server-side `onSnapshot → SSE` pattern pinned, Cloud Run config (min-instances=1, always-CPU, http2, timeout=3600s) pinned, ADK ParallelAgent for Scouts pinned, audio sync architecture (AudioContext master clock + embedded cues) added, reduced motion + WebVTT captions added, D3 Canvas rendering pinned for Floor. | N/A (pre-repo) | N/A |
| `BUILD_SPEC.md` v1.3 added 8 new top-level sections: §15 Cost guardrails + budget alerts, §16 Observability, §17 Error handling + graceful degradation, §18 Local development setup, §19 Deployment pipeline + IAM + secrets, §20 Test strategy, §21 Demo-day SPOFs + mitigations, §22 Post-submission ops + data destruction. Anti-patterns (was §15) → §23. Final reminder (was §16) → §24. Pointers (was §17) → §25. | N/A | N/A |
| `BUILD_SPEC.md` v1.3 §14.1 added 12 new measurable acceptance criteria (first-paint <1s, curtain-rise timing, 5s comprehension, half-second visual, voice-blind ≥18/21, Storyteller forbidden-words unit test, NIL fail-closed runtime exit, Wire write-through proxy lint, NIL max-revisions cap, Day-9 organic Equity intervention causal chain, HND fire ≥1, SSE reconnect with Last-Event-ID). | N/A | N/A |
| `BUILD_SPEC.md` v1.3 §23 anti-patterns added: direct `firestore.add('wire_events', …)`, missing `location='global'`, empty `athlete_registry` boot, Cloud Function `onCreate` trigger as NIL guard, live-regenerate hero during recording, fire Wire events before /health/nil is 200. | N/A | N/A |
| HOE-DEC-015 through HOE-DEC-024 logged in Decisions Log. | N/A | N/A |
| Lessons 6-9 logged. | N/A | N/A |
| `HOE-HANDOFF.md` Section 2 (Current State) overwritten; Section 3 (Investigation Narrative) appended with Session 1 entry; Section 7 (Active Priorities) overwritten. | N/A | N/A |
| **Result:** Spec is ready for Day 1. Day 1 hard gates are pinned: Apache 2.0 license CI gate, `scripts/verify_models.py` against `location='global'`, `scripts/list_tts_voices.py` for voice selection. No code yet. No GCP yet. Charlie can either copy the docs into a fresh repo and start Day 1 now, or schedule a fresh HoE Session 2 to begin Day 1 GCP provisioning + repo skeleton. | — | — |

---

## 7. Active Priorities (Overwrite Each Session)

**Last set:** 2026-05-02 (HoE Session 1 — Stack validation pass)

**Status boundary:** No code shipped. No GCP provisioned. All five project documents drafted and ready to commit. **BUILD_SPEC.md is now at v1.3** — all v1.2 ambiguities pinned, model IDs verified, operability sections added (§15-§22), 12 new measurable acceptance criteria. Day 1 priority is Apache 2.0 license + GCP project + Day-1 hard gates (`scripts/verify_models.py`, `scripts/list_tts_voices.py`) + repo skeleton + BigQuery schemas + athlete registry seed. Engineering work begins Day 2.

### What's proven:

| Area | Status |
|---|---|
| **Concept** | Pivot A+ (Place over Person) locked. Challenge 2 submission category locked. |
| **Architecture** | Seven-agent cast locked. Tech stack locked with verified Vertex AI model IDs (HoE Session 1). NIL Redaction Layer specified as a Python module with three checks and three actions; Wire-level enforcement pinned as in-process write-through proxy; fail-closed assertion pinned. Visualizer file location and pipeline pinned. "4× compressed time" mechanism pinned. Always-on loop pinned. HND detection logic pinned. Server-side `onSnapshot → SSE` streaming pattern pinned. ADK `ParallelAgent` for Scouts. |
| **Documents** | CONSTITUTION v1.2, PROJECT_BRIEF v1.1, What_is_The_Storytellers_Room v1.1, BUILD_SPEC **v1.3**, HOE-HANDOFF Session 1 baseline. |
| **Operability spec** | Cost guardrails (§15), Observability (§16), Error handling (§17), Local dev (§18), Deployment + IAM (§19), Test strategy (§20), Demo-day SPOFs (§21), Post-submission ops + data destruction (§22). All new in v1.3. |
| **Compliance posture** | NIL safety architectural (not content-review). Restricted terminology baked into Storyteller prompt + encouraged temporal phrasing list per VPS-DEC-033. Conditional phrasing required and enforced at Publish Gate Language Review sub-stage. No third-party logos other than Google Cloud. Place-as-subject in all generated images. |
| **Demo storyboard** | 3-minute video plan locked (BUILD_SPEC §11). Five demo moments identified. Anchor story selected organically on Day 9 with Day 8 evening soft-rank backstop. Live URL hero CTA at `compression_factor=0.25`. |

### Next priorities (Day 1 — 2026-05-03):

**1. Apache 2.0 license + GitHub repo setup (auto-DQ trigger if missed)**
- Create `LICENSE` file in repo root with full Apache 2.0 text
- Set the GitHub repository's License field to "Apache License 2.0"
- Verify the license badge is visible on the public repo's About sidebar
- Add license reference to the README's first paragraph
- **Wire `scripts/check_license.sh` into pre-commit + GitHub Actions CI** (BUILD_SPEC §13 Day-1 gate)
- 10-minute task. Do it before any other Day-1 work.

**2. GCP project + service enablement**
- Create or repurpose a GCP project for The Storyteller's Room
- Enable APIs: Vertex AI, BigQuery, Firestore (Native mode), Cloud Storage, Cloud Run, Cloud Logging, Cloud Monitoring, Secret Manager, Cloud Build, Cloud Scheduler
- Set up billing alerts: $100 informational / $200 audit / $300 kill switch (BUILD_SPEC §15.2)
- Service accounts created per BUILD_SPEC §19.1 (`agent-runtime@`, `web@`)

**3. Day-1 hard gates (block all downstream work until green)**
- **Model availability:** run `scripts/verify_models.py` to confirm all seven verified model IDs respond on `location='global'`. If any return 404, treat as P0 blocker.
- **TTS voices:** run `scripts/list_tts_voices.py`; audition 4-6 candidates each for Broadcast Narrator + Wire Dispatcher; pin chosen voice strings into BUILD_SPEC §3.5 and §5.6.
- **Apache 2.0 badge:** confirm visible on GitHub repo About sidebar.

**4. Repo skeleton**
- Folder structure per BUILD_SPEC §3.10:
  - `/agents` (with `/agents/wire/emit.py`, `/agents/publish_gate/nil_redaction_layer.py`, `/agents/publish_gate/visualizer.py`, `/agents/scouts/hnd_detector.py`, etc.)
  - `/web` (Next.js 15, with `/web/app/api/wire/stream/route.ts`, `/web/config/seed_prompt.ts`)
  - `/data` (BigQuery schemas, seed scripts, `wire_vocabulary.json`, `streaming_profiles.json`, `fallback_heroes/`)
  - `/audio` (TTS configs, sound design assets, `music_beds/LICENSES.md`)
  - `/scripts` (verify_models.py, list_tts_voices.py, check_license.sh, lint_no_direct_wire_writes.py, dress_rehearsal.sh, teardown_team_usa_data.sh, check_devpost_updates.py)
  - `/prompts` (versioned agent system prompts in markdown)
  - `/Docs/Engineering` (BUILD_SPEC + HOE-HANDOFF)
- README.md first paragraph references Apache 2.0 license
- `.gitignore` for Python, Node, GCP credentials, env files
- `cloudbuild.yaml` skeleton per BUILD_SPEC §19.4
- Initial commit on `main`

**5. BigQuery schemas deployed (per BUILD_SPEC §8)**
- `candidates` (story unit pool)
- `historical_athletes` (filtered Team USA only — strict scope)
- `geography`, `championships` (placement counts only, NO finish times, NO scoring data)
- `athlete_registry` (NIL Layer)
- `agent_call_counters` (per-axis cost ceilings tracked here)
- `agent_errors` (failure-mode logging per §17)

**6. Athlete registry seeded — fail-closed asserted**
- Loader at `/data/load_athlete_registry.py` pulls from Olympedia public CSV scrapes (`KeithGalli/Olympics-Dataset`, `chanronnie/Olympics`) filtered NOC=USA + Wikidata SPARQL cross-reference + Team USA roster scrape
- First names, last names, full names, known variants, Unicode-normalized
- **Verify ≥500 rows; the runtime startup assertion will fail-closed otherwise** (HOE-DEC-019)

**7. Local dev loop wired (per BUILD_SPEC §18)**
- Firestore emulator in Docker
- `make dev` boots emulator + agent runtime + Next.js dev server
- Hot reload on `/prompts/` edits

### Day 2-7 priorities (per BUILD_SPEC §13 phasing):

**Days 2-5:** Agent core. Editor (with always-on loop), Investigator (with Deep Research async wrapper), all 4 sub-scouts (wrapped in ADK `ParallelAgent`), Wire vocabulary + streaming profiles wired, candidate pool reads/writes, HND detector, Wire stream rendering with server-side `onSnapshot → SSE`, Wire pre-seed pattern. **Day 5: empirical Gemini TTS word-timing API check** — drives §7.6 sync implementation.

**Days 6-7:** Integrity & production layer. Paralympic Equity Editor (with rehearsed demo intervention). Storyteller (with full forbidden-words + encouraged temporal phrasing). Publish Gate with all 7 sub-stages. **NIL Redaction Layer Python module + write-through proxy + fail-closed startup assertion + lint rule**. **Visualizer at `/agents/publish_gate/visualizer.py` + max-3-regenerations + fallback path**. Narrator with verified voice configs + NarrationManifest (audio chunks + word timings + cues). Music bed candidates sourced + license receipts.

**Day 8:** Frontend ship. The Floor (D3 Canvas + particle pool + tool call cards). The Broadcast (curtain rise with AudioContext master clock + synchronized choreography + sentence highlighting + Hometown panel + Historical Echo panel + Evidence Drawer + reduced-motion + WebVTT captions). Live URL hero CTA at `compression_factor=0.25` + per-IP rate limit. **Day 8 EOD: anchor candidate soft-rank** (Charlie reviews top 3-5 per VPS-DEC-027).

**Day 9:** Run-and-discover. System runs continuously. 15-25 organic stories produced. **Pre-cache hero images per anchor candidate to `/data/fallback_heroes/`**. Anchor story selected from organic discoveries. **Day-9 dress rehearsal harness `scripts/dress_rehearsal.sh`** runs all 12 v1.3 measurable acceptance criteria (§14.1). Music bed final pick. Devpost text description refined.

**Day 10:** Demo video. Warm both Cloud Run URLs 5-30 min before recording. Record, edit, music, color, voiceover. Complete Pre-Submission Verification Checklist (PROJECT_BRIEF §14). **Submit by EOD.**

**Day 11:** Buffer. Fix anything that breaks. Monitor hosted URL. Begin §22 post-submission ops checklist.

### Do NOT do (additions for v1.3 in **bold**):

- Do not write any code before the Apache 2.0 license is in the repo and the badge is visible on the About sidebar (HOE-DEC-010)
- Do not name any individual Team USA athlete in user-facing output, ever, anywhere — including current, retired, and historical athletes (HOE-DEC-002, Constitution Law 4)
- Do not add an 8th visible agent (HOE-DEC-007)
- Do not introduce a new persistence layer, message queue, or workflow engine beyond BigQuery + Firestore + Cloud Storage (BUILD_SPEC Rule 5)
- Do not use Veo 3.1 (HOE-DEC-009)
- Do not generate hero images of identifiable people — subject is always a place, landscape, community, or facility (Constitution Law 6)
- Do not pre-select the demo's anchor story before Day 9 (HOE-DEC-012)
- Do not let Python decide WHAT a scout investigates (Constitution Law 1)
- Do not bypass the NIL Redaction Layer for "demo simplicity" or any other reason (HOE-DEC-004, HOE-DEC-014)
- Do not let the Equity Editor's interventions happen invisibly under the hood — they are visible on the Wire by design (Constitution Law 3)
- Do not use defensive demo voiceover ("the rules don't allow us to...") — frame the Place-over-Person move positively (HOE-DEC-006)
- Do not use "former Olympian," "past Olympian," NGB names where sport names belong, ambiguous Games references, or any predictive phrasing without conditional softening (PROJECT_BRIEF §10, §11)
- Do not introduce finish times or scoring results into any data layer or output (PROJECT_BRIEF §6 — auto-DQ trigger)
- Do not introduce any third-party corporate logo other than Google Cloud (PROJECT_BRIEF §7 — auto-DQ trigger)
- Do not share the project on social media before, during, or after the contest until the Sponsor explicitly authorizes it (PROJECT_BRIEF §12)
- Do not ship any feature that doesn't serve at least one of the five demo moments (Decision Filter, Constitution §0)
- **Do not call `firestore.add('wire_events', …)` directly from any agent — use `wire.emit(event)`. Lint rule fails the build on direct calls. (HOE-DEC-018.)**
- **Do not initialize Vertex AI without `location='global'` for any Gemini 3 family preview model — regional endpoints return 404. (HOE-DEC-015.)**
- **Do not let the agent runtime boot with an `athlete_registry` row count <500 — runtime exits 1; `/health/nil` returns 503. (HOE-DEC-019.)**
- **Do not implement the Wire-level NIL guard as a Cloud Function `onCreate` trigger — that races the SSE stream. (HOE-DEC-018.)**
- **Do not live-regenerate the Broadcast hero image during Day 10 demo recording — use the Day-9 pre-cached fallback per anchor candidate. (HOE-DEC-020.)**
- **Do not deploy Cloud Run services without `--min-instances=1`, `--cpu-always-allocated`, `--use-http2`, `--timeout=3600s` from Day 8 onward. (BUILD_SPEC §3.7.)**
- **Do not use `gemini-3-pro-preview` — it was discontinued 2026-03-26. Use `gemini-3.1-pro-preview`. (HOE-DEC-016.)**

---

## 8. Execution Session Playbook

### Claude Code Sessions (Preferred)

Charlie's preferred coding agent. Fits his thinking style. Use for most implementation work.

**How to direct:** Write a complete implementation prompt. Include:

- **Core docs preamble (MANDATORY):** Every prompt to an external coding agent must start with reading `PROJECT_BRIEF.md`, `CONSTITUTION.md`, and `Docs/Engineering/BUILD_SPEC.md`. These define the legal, architectural, and tactical boundaries the agent must not violate. Without them, coding agents make "reasonable" changes that gut the product (or, worse, silently introduce a NIL violation that DQ's the submission).
- Which implementation files to read next
- What to change (specific)
- What NOT to change (explicit — reference the Kill List in CONSTITUTION §8)
- How to verify (test commands, expected outcomes, manual smoke checks)
- Reminder of the Decision Filter

**Strengths:** Follows instructions precisely, stays in scope, produces clean minimal diffs.
**Weakness:** Can struggle with very large structural refactors. For large work, break into 3-4 scoped prompts.

### The Spec Principle

> *If the build failed, the spec was probably wrong. If the spec was wrong, the intent was probably unclear. If the intent was unclear, the operator hasn't finished thinking.*

The HoE's job is to think clearly enough that the implementation prompt is unambiguous. If the execution session asks clarifying questions or produces the wrong thing, the prompt was the failure — not the agent.

### Per-prompt checklist for execution sessions

Before sending a prompt to a coding agent:

- [ ] Did I include the core docs preamble (PROJECT_BRIEF, CONSTITUTION, BUILD_SPEC)?
- [ ] Did I name the specific files to read and the specific files to modify?
- [ ] Did I include the relevant Kill List items (CONSTITUTION §8)?
- [ ] Did I include verification steps (tests, smoke checks, manual probes)?
- [ ] Did I include the NIL safety reminder for any prompt touching user-facing text or generated images?
- [ ] Is the work in scope of the next 1-2 demo moments, not a nice-to-have?

---

## 9. Operational Gotchas (Check Before Debugging)

*This section will accumulate as the build runs. Initial entries:*

**1. Voice names in Gemini 3.1 Flash TTS need to be picked Day 1 from the live voice list.** v1.3 pulled this from Day 5/6 to Day 1 (HOE-DEC-017). Run `scripts/list_tts_voices.py`; audition 4-6 candidates each for Broadcast Narrator (warm/mid-tone/documentary) and Wire Dispatcher (clipped/lower-register/control-room); pin chosen voice strings into BUILD_SPEC §3.5 and §5.6. The v1.2 placeholders "Charon" and "Puck" are not assumed valid until verified.

**1b. Vertex AI calls MUST use `location='global'` for all Gemini 3 family preview models.** This is the most common Day 1 failure mode in 2026 — a regional endpoint (e.g., `us-central1`) returns 404 model-not-found. The Day-1 hard gate `scripts/verify_models.py` catches this. The Cloud Run service can deploy to `us-central1` for compute; the model call is what routes globally via `vertexai.init(location='global')`. (HOE-DEC-015.)

**1c. `gemini-3-pro-preview` was discontinued 2026-03-26.** Use `gemini-3.1-pro-preview`. (HOE-DEC-016.)

**1d. Gemini TTS word-level timing API surface needs empirical Day-5 verification.** v1.3 documents three fallback paths in BUILD_SPEC §3.5 (native word timing → sentence-level → estimated). Sentence-level highlighting is the load-bearing effect for the Broadcast page; word-level is bonus. Don't block Day 5 work on this — pick the path that matches the API and ship.

**2. Cloud Run cold starts can break the demo if the SSE connection takes too long to establish.** When recording the demo on Day 10, warm the service first by hitting the URL once before recording.

**3. BigQuery `athlete_registry` must be loaded BEFORE the NIL Redaction Layer is invoked at runtime.** If the registry table is empty, the Layer will pass everything through (false negative — names leak). Add a startup check that aborts if the registry has fewer than N rows (where N is, say, 100 — sanity check that loading actually happened).

**4. Firestore subscription limits.** The Wire SSE stream subscribes to `wire_events`. At ambient pace (4-8s per event), this is well within free tier. During the demo's 4× compressed live investigation, throughput temporarily spikes. Monitor and stay under the per-collection write rate.

**5. The Apache 2.0 license badge can disappear if Charlie accidentally changes the GitHub repo's License field. Re-verify the badge is visible on the About sidebar at the start of every session.** The cost of this check is 5 seconds; the cost of missing a license-badge regression on submission day is the entire prize.

---

## 10. How Charlie Works (Preserve Across Sessions)

- **Solo founder.** Building The Storyteller's Room with AI-first development. Every coding session is an AI agent. He directs and reviews; agents implement.
- **Tiered session model.** HoE session = strategic, long-lived, directs work. Execution sessions = fresh context, focused, receive scoped prompts from HoE. This is the same model as Neptune.
- **Constitutional thinker.** Charlie wrote The Storyteller's Room Constitution (and Neptune's). He thinks in terms of physics vs orchestration, governance vs flow control, system properties vs prompt instructions. When in doubt, apply the Constitutional test: *"Is Python deciding WHAT, or WHETHER?"*
- **Fix the system, then the symptoms.** Charlie's instinct is always "what product contract prevents this class of failure?" before "how do we patch this instance?" Example: the NIL Redaction Layer is a system contract that prevents the entire class of "name leaked through to user" failures.
- **Verify autonomously.** Charlie expects the HoE/coding agent to test its own work — run tests, check logs, hit endpoints, smoke-test the Wire and Broadcast pages manually. Never ask Charlie to manually verify something you can check yourself.
- **Direct communicator.** Prefers concise, direct answers. Lead with the conclusion, not the reasoning. Skip preamble.
- **The 11-day window is real but not an excuse for lower quality.** "We didn't have time" is not a valid reason to ship a half-baked Broadcast page. If we don't have time, we cut scope, not quality. The mediocre version of all five demo moments loses; the excellent version of three demo moments + the disciplined cut of the other two could win.
- **The Olympic broadcast aesthetic is the bar.** When in doubt, ask: would NBC's Olympic editorial team be embarrassed to air this? If yes, raise the bar. If no, ship.

---

## 11. Pointers to Other Documents

- **CONSTITUTION.md** (repo root) — creative and architectural principles. Re-read before each Claude Code session.
- **PROJECT_BRIEF.md** (repo root) — legal, compliance, submission requirements. **AUTHORITATIVE on rules.** Reference Sections 5, 7, 9, 10, 11 every coding session. Use Section 14 as the Pre-Submission Verification Checklist on Day 10. Use Section 15 as the per-commit checklist.
- **What_is_The_Storytellers_Room.md** (repo root) — descriptive vision doc for context.
- **Docs/Engineering/BUILD_SPEC.md** — tactical implementation spec. The single source of truth for build details (agent prompts, schemas, Wire vocabulary, demo storyboard, sound design, 11-day phasing, acceptance criteria).
- **Devpost rules** — https://vibecodeforgoldwithgoogle.devpost.com/rules
- **Devpost FAQs** — https://vibecodeforgoldwithgoogle.devpost.com/details/faqs

The repo lives at `/Users/charliereagan/projects/Google_Olympics_Hackathon`. This handoff lives at `Docs/Engineering/HOE-HANDOFF.md`. The BUILD_SPEC lives next to it at `Docs/Engineering/BUILD_SPEC.md`. The VPS handoff lives at `Docs/VPS/VPS-HANDOFF.md`. The Constitution, Project Brief, and Vision Doc live in the repo root.
