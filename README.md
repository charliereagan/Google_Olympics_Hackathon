# The Storyteller's Room

> An AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians.

Submission to the **Team USA × Google Cloud Hackathon** · Challenge 2 — *The Hometown Success Engine*.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## Live URL

🔴 **[storytellers-room.run.app](https://web-PLACEHOLDER.us-central1.run.app)** *(public URL pinned at submission)*

Demo video: see Devpost submission.

---

## What it does

Seven coordinated Gemini agents on Google Cloud — autonomous, continuous, editorial.

The Editor scans an always-on queue of place candidates. Four sub-scouts surface leads in parallel. The Investigator runs grounded research. The Storyteller writes editorial-grade prose calibrated against a hand-authored anchor. The Paralympic Equity Editor reviews every story for coverage parity and can return the draft. The seven-stage Publish Gate audits every claim. The Narrator renders Algenib voice for the Broadcast.

The protagonist class is **place, program, pattern** — never the individual athlete. By architecture, not policy. The NIL Redaction Layer runs as a write-through proxy in front of every emit; an 11,188-row registry catches direct matches, near-identifications, and small aggregates.

## How to experience it

| Surface | URL | What you'll see |
|---|---|---|
| Front door | `/` | Editorial masthead, ambient Wire ticker, hero of latest story, three discovery cards, seed-prompt CTA, recent stories grid |
| The Wire | `/wire` | The room thinking, in full |
| The Map | `/map` | Stylized US map (custom D3-geo, no third-party tiles); place dots sized by Olympian + Paralympian count |
| The Field | `/field` | The constellation — pattern over geography |
| The Floor | `/floor` | Seven-agent backstage — D3 force on Canvas, particle handoffs |
| The Stories | `/story` | The Stack, filterable by sport / era / type |
| Broadcast | `/story/[id]` | Full story page — stylized hero, Algenib narration, verified claims, audit signature |
| The Gate | `/publish-gate` | NIL Redaction Layer audit, disambiguation showcase |
| Investigation | `/investigation/[id]` | Live compressed-time view of your submitted seed prompt being investigated |

## Architecture

```
Vertex AI (location='global')        Cloud Run (us-central1)         Web
─────────────────────────────        ────────────────────────        ───
Gemini 3.1 Pro       ──────────────► agent-runtime ── Firestore ── Next.js 15 (SSE bridge)
  (Editor / Investigator                              wire_events
   / Equity / Storyteller                             agent_handoffs
   / Publish Gate)                                    publish_audits
Gemini 3 Flash ×4    ──────────────►                  published_stories  ── public URL
  (Cinderella / Comeback
   / Hometown / Echo)
Gemini 3.1 Flash-Lite ─────────────►              ── BigQuery
  (NIL near-id / Safety)                              athlete_registry (11,188 rows)
Nano Banana Pro      ──────────────►                  candidates
  (stylized place hero)                               historical_athletes
Gemini 3.1 Flash TTS ──────────────►              ── Cloud Storage
  (Algenib narration)                                 hero-images / audio
```

## Compliance posture

- **Apache 2.0** (top of this README; full text in [`LICENSE`](LICENSE))
- **No individual Team USA athlete names** in any user-facing surface — enforced architecturally by the NIL Redaction Layer
- **No finish times, no scoring results** — enforced by the Publish Gate's Fact Check sub-stage
- **No third-party corporate logos** other than Google Cloud — enforced by Visual Review sub-stage
- **No predictive phrasing without conditional softening** — enforced by Language Review sub-stage

## Repository structure

```
agents/                seven-agent runtime (FastAPI + ADK + Vertex AI)
  editor/              always-on autonomous loop
  scouts/              4 parallel sub-scouts + Scout Desk
  investigator/        grounded research + packet writer
  equity_editor/       Paralympic parity reviewer
  storyteller/         editorial prose writer (calibrated against Mount Pleasant exemplar)
  publish_gate/        7 sub-stages including the NIL Redaction Layer
  narrator/            Algenib TTS narration
  handoffs.py          structured agent-graph event emitter
  wire/                Wire emit proxy (HOE-DEC-018)
prompts/               agent system prompts (markdown — editable, version-controlled)
data/                  BigQuery schemas + athlete-registry loader
web/                   Next.js 15 frontend
  app/                 routes: /, /wire, /map, /field, /floor, /story, /story/[id],
                       /publish-gate, /investigation/[id]
  components/          WireRow, BroadcastPage, AudioBar, Floor, Field, MapView, ...
  lib/                 story-fixture, field-fixture, map-fixture, agent-floor-fixture
scripts/               ops + tests
  probe_full_chain.py          end-to-end chain probe
  test_storyteller_prompt.py   single-Pro-call prompt iteration harness
  generate_demo_*.py           Nano Banana Pro + Algenib asset generation
  seed_equity_editor_demo.py   Equity Editor intervention demo seed
  run_bounded_batch.sh         bounded organic-op driver
tests/                 pytest suite (340+ tests passing)
Docs/                  Engineering + VPS handoffs + refinement reviews
```

## Documents

- [`CONSTITUTION.md`](CONSTITUTION.md) — creative + architectural principles
- [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) — legal, compliance, submission requirements (authoritative on rules)
- [`What_is_The_Storytellers_Room.md`](What_is_The_Storytellers_Room.md) — vision narrative
- [`Docs/Engineering/BUILD_SPEC.md`](Docs/Engineering/BUILD_SPEC.md) — tactical implementation spec
- [`Docs/Engineering/HOE-HANDOFF.md`](Docs/Engineering/HOE-HANDOFF.md) — engineering institutional memory
- [`Docs/Engineering/design-system.md`](Docs/Engineering/design-system.md) — design tokens + visual contract
- [`Docs/VPS/VPS-HANDOFF.md`](Docs/VPS/VPS-HANDOFF.md) — strategic decisions log

## License

Apache License 2.0. See [`LICENSE`](LICENSE) for the full text.

---

*Built with [Claude Code](https://claude.com/claude-code).*
