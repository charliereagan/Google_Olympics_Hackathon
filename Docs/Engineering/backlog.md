# backlog.md — Ideas, bugs, deferred actions

This file is the catch-all for anything not actively in flight: ideas, bugs, deferred actions, "we'll come back to this," post-submission roadmap items.

**Conventions:**
- One entry per bullet. Lead with the noun.
- Tag with `[idea]`, `[bug]`, `[defer]`, `[post-submit]`, `[research]`, or `[polish]`.
- Date entries when added. Strike through (`~~text~~`) and date when resolved/dropped — don't delete (the historical reasoning has value).
- Move to `BUILD_SPEC.md` when an item becomes scoped work. Move to `HOE-HANDOFF.md` Decisions Log when an item becomes a binding decision.

When the build spec is fully delivered, archive it to `Docs/Engineering/archive/BUILD_SPEC-final.md` and any remaining work moves here.

---

## Active

### Day-1 verification gates (P0; tracked here until scripts land in repo)

- [defer 2026-05-02] **`scripts/verify_models.py`** — Day-1 hard gate that hits each of the seven verified model IDs on `location='global'` and asserts they respond. Currently verified manually via curl (see `tech_snapshot.md §3`). Convert to a checked-in script so future sessions can re-verify without re-thinking the URL shapes.
- ~~[defer 2026-05-02] **`scripts/list_tts_voices.py`** — Day-1 audition script that pulls the 30 Gemini Chirp3 HD en-US voices, generates a 30-second sample of each reading the same Broadcast paragraph, and saves them to `/audio/voice_audition/` for Charlie to A/B. Currently a manual Vertex AI curl. (HOE-DEC-017.)~~ **DONE 2026-05-03.** Worker shipped `scripts/list_tts_voices.py` (251 lines); 6 candidates auditioned; Charlie picked **Algenib** (Broadcast Narrator) + **Fenrir** (Wire Dispatcher + single-voice fallback) — HOE-DEC-025. Pinned in BUILD_SPEC §3.5 + §5.6 and tech_snapshot.md §4.
- [defer 2026-05-02] **`scripts/check_license.sh`** — pre-commit + GH Actions CI gate per BUILD_SPEC §13 Day-1.
- [defer 2026-05-02] **`scripts/lint_no_direct_wire_writes.py`** — CI lint rule per HOE-DEC-018.
- [defer 2026-05-02] **`scripts/dress_rehearsal.sh`** — Day-9 demo path harness per BUILD_SPEC §20.3.
- [defer 2026-05-02] **`scripts/teardown_team_usa_data.sh`** — post-judging data destruction per PROJECT_BRIEF §6 (run on or after June 16, 2026).
- [defer 2026-05-02] **`scripts/check_devpost_updates.py`** — daily 8am cron / GH Action per BUILD_SPEC §20.4.

### Athlete-registry coverage gaps (2026-05-03; from HOE-DEC-028 loader review)

- [defer 2026-05-03] **Paralympic coverage in the registry is thin (~19 records).** The KeithGalli Olympedia scrape is Olympic-only; Wikidata's `wdt:P166` Paralympic-medal triples are sparse. Total registry is 11,188 rows but Paralympic representation is under-covered. **Risk:** the NIL Layer has higher false-negative risk on Paralympic athlete names. **Mitigation:** layer Team USA roster scrape (`teamusa.com/athletes`) onto the loader during Days 2-3 to extend Paralympic coverage. Tracked here until done.
- [defer 2026-05-03] **Sport-name variants normalized to "Aquatics" instead of "Swimming"** in some Olympedia records (Phelps shows `sport='Aquatics'`). Affects Investigator queries that filter by sport family. Easy fix in `data/load_athlete_registry/fetch_olympedia.py::_enrich_with_results` (one-line tweak in the family-name extraction). Defer until Day 3 when Investigator code lands.
- [defer 2026-05-03] **`era_or_decade` is birth-decade, not competition-decade** in the registry. BUILD_SPEC §5.7's near-id heuristic (sport + hometown + event + year) implies birth-decade is acceptable, but if the Day-6/7 Layer wants competition-decade for tighter near-id checks, change `merge._from_olympedia` to use `min(games_years)` instead of `birth_year`. Tracked.
- [defer 2026-05-03] **Birth year missing for ~25% of Olympedia records** triggers loose-match dedup (first, last) without year. May cause minor over-merging of distinct same-named athletes, which is preferable to under-coverage. Backlog item: revisit if Day-9 spot-checks find specific over-merge cases.

### Day-4 work surfaced from Day-3 Editor smoke test (2026-05-04)

- [defer 2026-05-04] **Editor's `dispatch_scout` tool is a stub.** The bound tool records the dispatch but does NOT call `scout_desk.run_pass([story_unit_id], ctx=...)`. The Editor's Pro model can decide to dispatch; the dispatch logs but Scouts don't actually run yet. **Day-4 priority #1: wire the Scout Desk body** so the full Editor → Scout → wire.emit cycle exercises live Gemini. (Plan §A.6.)
- [defer 2026-05-04] **Editor's `accept_equity_recommendation` and `read_recent_published`/`read_queue` are partial stubs.** The internal context-snapshot reads from Firestore correctly; the LLM-facing tool versions return defaults until Day-4/6.
- [defer 2026-05-04] **Day-3 spawned a real Gemini Pro call from `editor.think_once`.** Cost-counter increment fires; verify `agent_call_counters` BigQuery row by Day-4 morning.
- [defer 2026-05-04] **Firestore composite index `lead_reports:(status array-contains-any [investigating, promoted])`** likely needed once Day-4 Scout writes start populating `lead_reports`. The Editor's `_read_queue` uses a `where('status', 'in', [...])` filter. Watch for `FailedPrecondition` once data starts flowing; if it surfaces, create via `gcloud firestore indexes composite create`.
- [defer 2026-05-04] **Worker host: `GOOGLE_GENAI_USE_VERTEXAI` not in env.** Implementation worker's isolated test script must have set it manually (worker reported `vertexai.init flows through ADK cleanly`); but in the runtime context, the boot path didn't set it until HOE-DEC-030. Future workers should know that running `agents/runtime.py` requires this env var.

### Day-3 work surfaced from Day-2 skeleton smoke test (2026-05-04)

- [defer 2026-05-04] **HND detector async on_snapshot gap.** `firestore_v1.AsyncCollectionReference.on_snapshot` raises `NotImplementedError` in the current SDK. The detector falls back to stub mode at boot (logged). Day-3 fix per plan §G.2: run a sync `firestore_v1.Client.collection('lead_reports').on_snapshot(callback)` watcher on a separate thread and marshal callbacks back to the asyncio loop via `asyncio.run_coroutine_threadsafe`. Unit tests drive `record_lead_report` directly, so the detection logic is correctness-complete; just the production listener path needs wiring.
- [defer 2026-05-04] **`/health/nil` FastAPI signature** — initial worker code used `async def health_nil(response: Response)` to mutate status code; FastAPI 0.136 interprets that as a query parameter and returns 422. Fixed to use `JSONResponse(status_code=503, content=...)` directly. Lesson: prefer JSONResponse over Response-mutation for non-200 health endpoints. Already fixed; logged here so future workers don't hit the same trap.
- [defer 2026-05-04] **`google-adk` UserWarning at boot:** `[EXPERIMENTAL] feature FeatureName.PLUGGABLE_AUTH is enabled.` Cosmetic; suppress in production logging config or pin to a stable ADK version once 2.0 GA lands.
- [defer 2026-05-04] **`authlib` deprecation warning:** `authlib.jose module is deprecated, please use joserfc instead.` From an `authlib` transitive dep of `google-adk`. Cosmetic. Will resolve when ADK pulls in `joserfc` directly.

### Day-2 implementation handoff prep (2026-05-03)

- [defer 2026-05-03] **Agent-runtime skeleton plan ready at `Docs/Engineering/plans/agent-runtime-skeleton-v1.md`.** When ready, spawn an implementation worker with that plan as the binding spec. Worker writes files in the topo-sorted order from §H. HoE reviews + tests + commits. Each step independently testable with `pytest -x`.
- [defer 2026-05-03] **`ATHLETE_REGISTRY_DATASET` env var** added to the plan's §E. Default `storytellers_room` (production); override `storytellers_room_dev` for local. NIL Layer reads from this.

### Spec corrections from reachability sweep (2026-05-02)

- [defer 2026-05-02] **BUILD_SPEC §3.1 — note Vertex API version split.** Verified probes show `gemini-3.1-pro-preview` is on `v1` while the rest of the Gemini 3 family (Flash, Flash-Lite, Image variants, TTS) are on `v1beta1`. Default the agent runtime SDK calls to `v1beta1` for safety; override to `v1` only for Pro. (Currently the spec doesn't pin a version.)
- [defer 2026-05-02] **BUILD_SPEC §3.5 — TTS bare voice name vs FQN.** Vertex AI Gemini TTS uses bare voice names (`"Charon"`); Cloud TTS uses the FQN (`"en-US-Chirp3-HD-Charon"`). Both refer to the same voice. Note this in §3.5 to prevent confusion when copying voice names from the catalog.
- [defer 2026-05-02] **BUILD_SPEC §3.4 — image gen requires `responseModalities: ["IMAGE"]`.** The Pro Image / Flash Image probes return 400 INVALID_ARGUMENT without it. Pin in §3.4.
- [defer 2026-05-02] **BUILD_SPEC §5.6 — Reasoning is on by default for Pro 3.1.** Empty Pro response with `MAX_TOKENS=8` finish indicates thought-token consumption. Either set `thinkingConfig` to disable reasoning for low-latency calls (Wire vocabulary fills, etc.), or budget for it. Worth a dedicated §3.x note.

### Things to know about Gemini 3.x ecosystem (research, ongoing)

- [research 2026-05-02] **Word-level timing in Gemini TTS response.** Empirical Day-5 verification still pending. If absent, may be available via the audio metadata (chunk durations, sentence boundaries from prompt structure).
- [research 2026-05-02] **ADK + ParallelAgent on Cloud Run with min-instances=1 + cpu-always-allocated** — verify the long-running asyncio loop pattern doesn't conflict with ADK's Runner abstraction. May need to construct the Runner once at container init and reuse across the loop.
- [research 2026-05-02] **Deep Research API integration** — the spec assumes Deep Research is callable as a tool. Need to verify the actual API shape on Vertex AI (vs Gemini Enterprise Agent Platform). May need to use the Gemini Enterprise route.

### Frontend polish (P1/P2; mostly post-Day 8)

- [polish 2026-05-02] **View Transitions API** for the Wire→Broadcast crossfade — Chrome 111+, Safari 18 mature in 2026. Free animated transition at zero JS cost; pair with Framer for choreographed beats. (Frontend agent recommendation.)
- [polish 2026-05-02] **`<dialog>` element for Broadcast modal** — gets focus trap + Escape-to-close for free vs custom z-index stack.
- [polish 2026-05-02] **`navigator.connection.saveData` + `effectiveType`** — if judge is on flaky conf-room wifi, switch Wire from 4s to 8s pacing so SSE backlogs don't pile up.
- [polish 2026-05-02] **Captions track for Narrator (WebVTT)** — derived from the same word-timings data; ~30 lines of code; meaningfully ups perceived production value AND a11y. Tied to BUILD_SPEC §7.7.
- [polish 2026-05-02] **`prefers-reduced-motion` fallback** — disable Wire scroll, Ken Burns, headline typewriter, Floor particles. Tied to BUILD_SPEC §7.7.
- [polish 2026-05-02] **SynthID disclosure in Evidence Drawer** — note that Narrator audio is AI-generated and SynthID-watermarked. Adds to the trust signal.

### Demo-day risks tracked but not yet mitigated in code

- [bug-pending 2026-05-02] **No quota pre-flight check yet.** BUILD_SPEC §21 calls for Day-10 pre-flight asserting Vertex AI quota >2× expected demo burn. Need to write the check. Could be `scripts/preflight.sh`.

### Post-submission ideas

- [post-submit 2026-05-02] **NBC editorial integration thesis.** Vision doc closes with this. After winners announcement (June 16), explore whether the post-hackathon path involves a real conversation with Olympic broadcasters.
- [post-submit 2026-05-02] **Other sports bodies.** USA Swimming, USA Track & Field, US Soccer, WNBA, NCAA athletics — same architecture, different corpus, different scouts. Roadmap for the Storyteller's Room as a product.
- [post-submit 2026-05-02] **The Floor as a debugging tool.** During the build, the Floor was always meant as a demo surface. After submission, repurpose as the operator's live-debug view of the agent fleet.
- [post-submit 2026-05-02] **Multi-language Narrator.** Cloud TTS has 70+ languages; the same architecture could produce broadcasts about Team USA places narrated in Spanish, Mandarin, Hindi for diaspora audiences.

---

## Resolved / Dropped

(empty — entries get struck through with date when closed, not deleted)

---

## How this file works with the others

- **`BUILD_SPEC.md`** — when an idea here becomes scoped work, write it into the spec and remove the `[idea]` entry here (or strike it through).
- **`HOE-HANDOFF.md`** — when work in this backlog gets decided binding, log it as an HOE-DEC and move the entry to "Resolved."
- **`tech_snapshot.md`** — when a `[research]` item resolves and changes the runtime ground truth, update tech_snapshot too.
- **This file** — the place ideas live before they're scoped, the place bugs live before they're fixed, the place "we'll come back to this" lives without losing track.
