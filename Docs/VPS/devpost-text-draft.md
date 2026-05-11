# Devpost text — DRAFT for submission

**Status:** scaffold prepared by HoE on submission day; Charlie / VPS to polish + ship.

**Public URL:** _<placeholder — fill after Cloud Run deploy lands>_

**GitHub repo:** https://github.com/charliereagan/Google_Olympics_Hackathon (Apache 2.0)

---

## Opening (VPS-DEC-036 — LOCKED, do not edit)

> Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling.

---

## Challenge 2 alignment (per VPS-DEC-029 ordering)

The Team USA × Google Cloud Hackathon's Challenge 2 is _"The Hometown Success Engine"_ — interactive tools for fans that help them find where excellence is fostered. The Storyteller's Room is built for that brief end-to-end:

- **Interactive**: fans submit a seed prompt on the front door and watch the room investigate in compressed-time, then read the finished story (VPS-DEC-045 `/investigation/[id]` surface).
- **Tools for fans**: three discovery surfaces — `/map` (find your region), `/field` (follow patterns), `/story` (browse what the room has told, filterable by sport / era / Olympic|Paralympic).
- **Help fans find where excellence is fostered**: the entire system's protagonist class is **place, program, and pattern** — never the individual athlete. By architecture, not by policy.

Natural extensions to Challenges 1 (Paralympic Parity) and 3 (LA28 Momentum) emerge from the same architecture:
- The **Paralympic Equity Editor** is a structurally-empowered agent that reviews every story for coverage parity and can return the draft if Paralympic depth is shallow.
- A **"800 days to LA28" counter** is the editorial anchor on every page — every story is shaped by the question _"what is this place producing on the road to LA28?"_

## The seven-agent cast

Seven coordinated Gemini agents on Google Cloud:

| Agent | Model | Role |
|---|---|---|
| **Editor** | Gemini 3.1 Pro | Always-on autonomous loop. Scans the queue, dispatches sub-agents, makes editorial decisions. Locked voice — terse, procedural. |
| **Scout Desk** (4 sub-scouts) | Gemini 3 Flash × 4 | Cinderella / Comeback / Hometown / Echo. Surface candidate places from the corpus in parallel. |
| **Investigator** | Gemini 3.1 Pro | Grounded research. Pulls historical context from BigQuery + grounded search. Writes investigation packets. |
| **Paralympic Equity Editor** | Gemini 3.1 Pro | Reviews every story for coverage parity. Can return drafts or block publication. Voice locked to coverage-equity language, never apology. |
| **Storyteller** | Gemini 3.1 Pro | Writes the prose. Calibrated against the Mount Pleasant exemplar (VPS-DEC-052). |
| **Publish Gate** | Gemini 3.1 Pro + Flash-Lite | Seven sub-stages: Fact Check, Source Review, Parity Review, NIL Redaction, Safety Review, Language Review, Visual Review. Returns drafts on failure; clears on pass. |
| **Narrator** | Algenib (Gemini 3.1 Flash TTS) | Synthesizes Broadcast narration. Documentary register, not stadium PA. |

## The NIL Redaction Layer — compliance as architecture

The contest's NIL clause forbids individual athlete naming. We made it a Python module, not a content-review policy.

The **NIL Redaction Layer** runs as a write-through proxy in front of every agent's Wire emit. Every utterance the system produces — agent thinking, decisions, milestones, story bodies, narration text — goes through it. Direct matches against an 11,188-row athlete registry are redacted; ambiguous near-identifications are disambiguated by Gemini Flash-Lite; small aggregates ("Phelps and Lochte") are replaced with counts. The audit log on every published story shows the Layer's work: _claims checked, redactions performed, disambiguation hits_.

By architecture, not by policy. A judge can inspect the audit and see real work happening.

## Multi-model orchestration (VPS-DEC-048)

The cast spans 5 Gemini models tuned for cost / latency / capability:

- **Gemini 3.1 Pro** for deliberation-heavy roles (Editor, Investigator, Equity Editor, Storyteller, Publish Gate Fact Check)
- **Gemini 3 Flash** ×4 for the parallel Scout sub-agents (fast pattern recognition)
- **Gemini 3.1 Flash-Lite** for the NIL Layer's near-id disambiguation and Publish Gate Safety Review (low-latency structured calls)
- **Gemini 3.1 Flash-Image (Nano Banana Pro)** for stylized hero illustrations — places, never people
- **Gemini 3.1 Flash TTS** (Algenib voice) for Broadcast narration

All Vertex AI on `location='global'` per Gemini 3 family preview requirements. Cloud Run hosts both services with `--min-instances=1 --cpu-always-allocated`. BigQuery holds the candidate pool and athlete registry. Firestore streams agent activity to the web via server-side `onSnapshot → SSE`.

## What runs at the URL

| Surface | What you'll see |
|---|---|
| `/` | Editorial masthead, ambient Wire ticker scrolling agent activity, full-bleed cinematic hero of the latest published story, three discovery cards (THE MAP / THE FIELD / THE STORIES), seed-prompt CTA, recent stories grid. |
| `/wire` | The room thinking, in full. Live SSE stream of every agent's wire events. |
| `/map` | Stylized US map (custom D3-geo, no third-party tiles). Place dots sized by Olympian + Paralympian count. Hover for place + count; click for the Broadcast. |
| `/field` | The constellation. Same data as the map, presented as an editorial-celestial graph — pattern over geography. |
| `/floor` | The seven-agent backstage. D3 force on Canvas. Particle handoffs flowing between agents in real time. Equity Editor flashes agitos-red on intervention. |
| `/story` | The Stack — published stories with facet filters (sport / era / Olympic-Paralympic). |
| `/story/[id]` | The Broadcast. Stylized hero illustration, Playfair Display headline, italic Lora dek, body prose, pull quote, verified-claim ribbons, Publish Gate signature footer. Algenib narration autoplays on click-navigated arrival. |
| `/publish-gate` | The trust panel. Aggregate audit stats. Recent decisions feed. The Disambiguation Trace marquee — a story whose audit shows the Layer's reasoning step-by-step. |
| `/investigation/[id]` | The fan's submitted prompt rendered as a live compressed-time investigation. _"Read your story"_ CTA appears when the chain clears Publish Gate. |

## Three demo stories

The published corpus blends hand-curated calibration anchors with organically-produced stories from the system:

- **Mount Pleasant, IA** — _"A small town builds a generation."_ Wrestling tradition + adaptive sport program. The editorial calibration anchor.
- **Park City, UT** — _"A school day that ends at one in the afternoon."_ Alpine + freestyle skiing.
- **Birmingham, AL** — _"A city remade for the rest of itself."_ Adaptive sports + Lakeshore Foundation. Paralympic-anchored.
- _(Plus organic stories produced by the system itself during the build — visible at `/story`)_

Each story shipped with a stylized Nano Banana Pro hero (never people, never logos), Algenib narration, structured verified claims, and a Publish Gate audit signature.

## Post-hackathon thesis

At ~$0.08 per Storyteller draft, the cost of producing one editorial-grade story is roughly 1/3000th of a journalist's day rate. We are not optimizing for one beautiful demo — we are building the architecture for a class of AI-native sports newsroom that produces editorial-grade place-stories at the cost of energy.

Beyond Team USA: the same architecture, with a different athlete registry and a different vocabulary library, becomes a hometown-stories engine for any league, any country, any sport. The seven-agent contract is the physics; the data is configuration.

This is what we mean by _"designed for models that don't exist yet."_ Every year the underlying Gemini family improves; the architectural contract stays. The system gets better without us touching code.

---

## Submission checklist (per PROJECT_BRIEF §14)

- [ ] Apache 2.0 license badge visible on GitHub About sidebar
- [ ] GitHub repo public
- [ ] All seven Vertex AI model IDs verified on `location='global'`
- [ ] Cloud Run services running (`--min-instances=1`)
- [ ] No individual Team USA athlete names in any user-facing surface
- [ ] No finish times or scoring results
- [ ] No third-party logos other than Google Cloud
- [ ] No predictive phrasing without conditional softening
- [ ] NIL Redaction Layer audit log shows real redaction work (not all-zeros) — VERIFY before submit
- [ ] Demo video uploaded (3 min, contains GCP/AI-Studio shot per VPS-DEC-037)
- [ ] Devpost text description leads with VPS-DEC-036 locked opener
- [ ] Hero screenshots at 1920×1080 of each surface
- [ ] Submission posted by 2026-05-11, 5:00pm PT
