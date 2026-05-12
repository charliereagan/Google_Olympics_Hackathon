# The Storyteller's Room

> An AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians.

Submission to the **Team USA × Google Cloud Hackathon** · Challenge 2 — *The Hometown Success Engine*.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## Live URL

🔴 **[https://web-615585524733.us-central1.run.app](https://web-615585524733.us-central1.run.app)**

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

## Testing & verification

**Fastest path:** open the [live URL](https://web-615585524733.us-central1.run.app) above and click through the surfaces. No setup required.

### Demo-moment quick links

| Moment | URL on the live site |
|---|---|
| Cinematic hero + broadcast narration + infographic | [`/story/organic-CcBLDJv0y0mLzmWpQF5W`](https://web-615585524733.us-central1.run.app/story/organic-CcBLDJv0y0mLzmWpQF5W) (Minnesota) |
| Seven-agent ADK orchestration | [`/floor`](https://web-615585524733.us-central1.run.app/floor) |
| NIL Redaction Layer audit | [`/publish-gate`](https://web-615585524733.us-central1.run.app/publish-gate) |
| Live agent feed with Gemini-model attribution | [`/wire`](https://web-615585524733.us-central1.run.app/wire) |
| Stylized US map of Olympian/Paralympian production | [`/map`](https://web-615585524733.us-central1.run.app/map) |

### Run the test suite locally

```bash
git clone https://github.com/charliereagan/Google_Olympics_Hackathon.git
cd Google_Olympics_Hackathon

# Python — agent runtime + NIL Layer + chain probes
pytest -x

# Next.js — type safety + lint
npm --prefix web ci
npm --prefix web run typecheck
npm --prefix web run lint
```

### Run the frontend locally

```bash
cd web
npm ci
npm run dev                         # → http://localhost:3000
```

The frontend reads from Firestore via Application Default Credentials. For the live organic story and audit data:

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=predictive-fx-495200-j4
```

Without GCP credentials the frontend falls back to in-repo story fixtures — the homepage, three fixture broadcast pages, `/map`, `/field`, and `/floor` all still render normally (the NIL Redaction Layer audit panel falls back to fixture data too).

### What success looks like

- `pytest -x` — all suites green (Python 3.11+)
- `npm run typecheck` — zero TypeScript errors (strict mode)
- `npm run lint` — zero ESLint errors
- Visiting `/` after `npm run dev` — full homepage with hero, story stack, ambient ticker
- Visiting `/floor` — particle handoffs traveling along edges every ~1.5s, GCP-service-labeled tool cards stacking on the right, REPLAY label fading in after ~60s of agent-runtime idle (every event labeled `live | replay | published` per the project's honesty contract)

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
```

## License

Apache License 2.0. See [`LICENSE`](LICENSE) for the full text.

---

*Built with [Claude Code](https://claude.com/claude-code).*
