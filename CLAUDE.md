# CLAUDE.md — The Storyteller's Room

This file is the alignment prompt that every Claude Code session reads before doing any work in this repo. Keep it tight; deeper context lives in the canonical docs linked below.

## Project in one paragraph

The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the **places, programs, and patterns** that produce Olympians and Paralympians, **never individuals**. A coordinated team of seven Gemini agents (Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate) operates continuously: scouting public data, verifying claims, enforcing parity, redacting individual identification by architecture, and producing narrated Olympic-broadcast-style story pages. Submission category: **Challenge 2 — The Hometown Success Engine** of the Team USA × Google Cloud Hackathon. Hard deadline: **May 11, 2026 at 5:00pm PT**. Internal deadline: **May 10 EOD**. Solo builder + Claude Code.

## Read these first, in order, every session

1. **[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md)** — legal, compliance, submission requirements. Wins on rules questions. Reference §5, §7, §9, §10, §11 every coding session; use §15 as the per-commit checklist.
2. **[`CONSTITUTION.md`](CONSTITUTION.md)** — creative and architectural principles. Six laws + the Code Review Kill List in §8.
3. **[`Docs/Engineering/BUILD_SPEC.md`](Docs/Engineering/BUILD_SPEC.md)** — tactical implementation spec (v1.3). The single source of truth for build details.
4. **[`Docs/Engineering/HOE-HANDOFF.md`](Docs/Engineering/HOE-HANDOFF.md)** — Head of Engineering session handoff. The HoE's running memory. Read for what's been decided and what's active.
5. **[`Docs/Engineering/tech_snapshot.md`](Docs/Engineering/tech_snapshot.md)** — ground truth: what's provisioned, what model IDs respond, what env vars are set. Refreshed on every infra change.
6. **[`Docs/Engineering/backlog.md`](Docs/Engineering/backlog.md)** — ideas, bugs, deferred actions. Anything not actively in flight.
7. **[`What_is_The_Storytellers_Room.md`](What_is_The_Storytellers_Room.md)** — vision narrative for context.

**Document hierarchy:** PROJECT_BRIEF wins on legal/compliance. CONSTITUTION wins on creative/architectural principles. BUILD_SPEC wins on tactical implementation. tech_snapshot wins on "what's actually deployed right now." HOE-HANDOFF is the running operational log. The vision doc is descriptive, not prescriptive.

## The Decision Filter (overrides everything below)

> Does this serve one of the five demo moments?
> 1. The room is alive.
> 2. The agents are truly agentic.
> 3. The Equity Editor caused the anchor story.
> 4. The Broadcast lands emotionally.
> 5. The Publish Gate (with the NIL Redaction Layer) proves trust.

If yes → proceed. If no → cut it. There is no third option.

## Things to never do (auto-DQ or Constitution-breaking)

- Never name any individual Team USA athlete in user-facing output — current, retired, or historical. The protagonist class is **places, programs, patterns**.
- Never call `firestore.add('wire_events', …)` directly from any agent — use `wire.emit(event)` only. The proxy invokes the NIL Redaction Layer; bypassing it is a DQ risk. (HOE-DEC-018; CI lint rule fails on direct calls.)
- Never initialize Vertex AI without `location='global'` for any Gemini 3 family model — regional endpoints return 404. (HOE-DEC-015.)
- Never let the agent runtime boot with `athlete_registry` <500 rows — the NIL Layer fails closed. (HOE-DEC-019.)
- Never use `gemini-3-pro-preview` (discontinued 2026-03-26) — use `gemini-3.1-pro-preview`. (HOE-DEC-016.)
- Never add an 8th visible agent. (CONSTITUTION Rule 2.)
- Never use Veo 3.1 (video generation). (HOE-DEC-009.)
- Never use "former Olympian," "past Olympian," NGB names where sport names belong, predictive phrasing without conditional softening, or any forbidden Storyteller word. (PROJECT_BRIEF §10–11.)
- Never introduce finish times or scoring results into any data layer or output. (PROJECT_BRIEF §6 — auto-DQ.)
- Never use third-party corporate logos other than Google Cloud. (PROJECT_BRIEF §7 — auto-DQ.)
- Never share the project on social media before the Sponsor explicitly authorizes it. (PROJECT_BRIEF §12.)
- Never let Python decide WHAT a scout investigates (orchestration). Python decides WHETHER text reaches the user (governance). The line matters.

## Operating model — director, not coder

The HoE session (this Claude Code session) **directs and reviews; does not write production code directly**. The role separation is binding:

**The HoE session owns:**
- Architectural decisions, spec edits, and documentation (BUILD_SPEC, HOE-HANDOFF, DEPLOYMENT, tech_snapshot, backlog, CLAUDE.md)
- Reviewing all worker-agent output before it lands in the repo (read every diff; don't trust summaries)
- **All git commits and pushes** — workers never commit
- **All deployments** (Cloud Run, gcloud, Cloud Build, infra changes) — workers never deploy
- Provisioning, IAM, Secret Manager, billing alerts
- Test execution and verification (run pytest, hit endpoints with curl, take screenshots)
- Updating HOE-HANDOFF after every session and tech_snapshot after every infra change

**Worker agents own:**
- Implementation plans (spawn a Plan-style agent first when the work is non-trivial)
- Writing code in scoped commits (the agent produces the code; HoE reviews and commits)
- Research and exploration (Explore agent for codebase questions; general-purpose for web research, given the parent-session permission caveat from HoE Session 1 Lesson 8)

**How HoE delegates:** every worker-agent prompt includes (1) the core docs preamble (PROJECT_BRIEF + CONSTITUTION + BUILD_SPEC), (2) the specific files to read and modify, (3) the Kill List items relevant to the work, (4) verification steps the worker must run before declaring done, (5) the explicit instruction *"do not run git commit, git push, gcloud deploy, or any infra-changing command — return your changes for HoE review."*

**Why this matters for context:** worker agents have their own context windows. Pushing implementation work to them keeps the HoE's context clean for orchestration, review, and the strategic picture. The HoE doesn't need to remember every line of code — only what was decided, what shipped, and what's next.

## How to work in this repo

- **Tech stack:** Google Agent Development Kit (ADK Python 2.0 Beta) on Cloud Run + Vertex AI Gemini 3.x family + BigQuery + Firestore (Native mode) + Cloud Storage + Next.js 15 (App Router) + Tailwind + Framer Motion + D3 (Canvas-rendered). Verified model IDs and URL shapes in `tech_snapshot.md`.
- **Markdown is the system.** Agent behavior lives in `/prompts/*.md`. To change what an agent does, edit a prompt file — never the Python.
- **The seven-agent cast is locked.** Sub-scouts (Cinderella, Comeback, Hometown, Echo) live inside Scout Desk. Visualizer is a tool the Publish Gate calls (`/agents/publish_gate/visualizer.py`). NIL Redaction Layer is a sub-stage of the Publish Gate (`/agents/publish_gate/nil_redaction_layer.py`).
- **Cloud Run config** for both services: `--min-instances=1 --cpu-always-allocated --use-http2 --timeout=3600s`. (BUILD_SPEC §3.7.)
- **Streaming pattern:** server-side `onSnapshot → SSE`. The frontend does NOT use the Firebase JS SDK directly. (HOE-DEC-024.)
- **Voice signatures are sacred.** If two agents sound alike on the Wire, the room has died. Voice work is in agent system prompts.
- **Documentary, not sportscaster.** *The Daily*, not stadium PA. *30 for 30*, not pre-game hype.
- **Stylized, never photorealistic.** Hero images depict places, landscapes, communities, facilities, equipment, silhouettes — never identifiable people.
- **Honest production, not faked liveness.** Every Wire event has a `mode` field (`live | replay | published`). Compressed-time mode (`compression_factor: float`) is per-investigation; the live URL hero CTA passes 0.25.

## Verify your own work (autonomous testing)

Per the global rule (`~/.claude/rules/autonomous-verification.md`): never ask Charlie to test, verify, or check something you can do yourself.

- After agent code changes: `pytest -x` from the repo root.
- After frontend changes: `npm --prefix web run typecheck && npm --prefix web run lint`, then run the dev server and verify the feature in a browser.
- After infra changes: hit the affected endpoint with `curl` and verify response shape; check Cloud Logging for errors.
- After prompt changes: run a 3-5 persona test harness against the live model and capture output to a markdown file before declaring success.
- For UI work: take screenshots and inspect them yourself.

## Communication conventions

- Lead with the conclusion, not the reasoning. Skip preamble.
- Use the file_path:line_number format when referencing code locations so Charlie can jump to them.
- Concise > verbose. End-of-turn summaries are one or two sentences.
- Mark progress in `Docs/Engineering/HOE-HANDOFF.md` Section 6 (Work Log) at the end of each session.
- Open questions and deferred work go to `Docs/Engineering/backlog.md`.

## Daily / per-commit compliance checklist

Before every commit, verify (PROJECT_BRIEF §15):
- [ ] No individual athlete names in user-facing strings, prompts, UI, or test data
- [ ] No forbidden Storyteller terminology ("former Olympian," etc.); encouraged temporal phrasing ("first/next/newest Olympian" applied to a place) preserved
- [ ] No third-party logos
- [ ] No finish times or scoring results
- [ ] No predictive phrasing without conditional softening
- [ ] NIL Redaction Layer invoked on every path that emits text to a user-facing surface
- [ ] Apache 2.0 license badge still visible on the GitHub About sidebar

## Apache 2.0

This repo is licensed under [Apache License 2.0](LICENSE). The badge must remain visible in the GitHub repo's About sidebar — auto-DQ trigger if missing on submission day.
