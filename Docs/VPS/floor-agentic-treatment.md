# `/floor` — Agentic AI / ADK Treatment Spec

**Purpose:** Convert the `/floor` page from "slick animation of seven nodes with intermittent cards" to "Google ADK in production — the agentic claim, made undeniable."

**Strategic frame:** This is the single most concentrated ADK proof point in the product. Technical Depth axis (30% of judging) lives here. Right now the page whispers; we make it scream — without breaking the broadcast aesthetic.

**Companion doc:** `/Docs/VPS/story-infographic-data.md` (the same treatment philosophy applied to story pages).

---

## Page structure — full real estate, top to bottom

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [Editorial masthead: "THE STORYTELLER'S ROOM" left · "BROADCAST · 2026 · 795d to LA28" │
│  right · "?"]                                                                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [Ambient Wire ticker band — already exists, persistent across pages]                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌──────────────────────────────────┐                                                 │
│  │ GOOGLE AGENT DEVELOPMENT KIT     │  <- new big tracked-cap title, gold              │
│  │ Seven Gemini agents · Live       │     italic Lora subtitle                          │
│  │ agentic orchestration            │                                                  │
│  └──────────────────────────────────┘                                                 │
│                                                                                        │
│  ┌─ EXPLAINER CARD ──────────────┐    ┌─ AGENT GRAPH (existing, enhanced) ─────────┐  │
│  │                               │    │                                            │  │
│  │ Three short paragraphs        │    │       [EDITOR]                             │  │
│  │ (see Copy section below)      │    │            │                               │  │
│  │                               │    │   [SCOUT DESK]─[INVESTIGATOR]─[NARRATOR]   │  │
│  │ Optional: small               │    │            ↓                               │  │
│  │ "now investigating" status    │    │      [EQUITY EDITOR]                       │  │
│  │ line                          │    │            ↓                               │  │
│  │                               │    │      [STORYTELLER]─[PUBLISH GATE]          │  │
│  └───────────────────────────────┘    │                                            │  │
│                                       │  particle handoffs flowing                 │  │
│                                       │  Equity Editor flashes Agitos-red          │  │
│                                       │  on intervention                           │  │
│                                       └────────────────────────────────────────────┘  │
│                                                                                        │
│                                       ┌─ TOOL CALL FEED (right, fixed) ──┐            │
│                                       │ VERTEX AI · Gemini 3.1 Pro · 1.2s│            │
│                                       │ Editor → deliberation             │            │
│                                       │                                   │            │
│                                       │ BIGQUERY · candidates · 0.04s    │            │
│                                       │ Investigator → query              │            │
│                                       │                                   │            │
│                                       │ NANO BANANA PRO · 4.3s           │            │
│                                       │ Publish Gate → hero illustration  │            │
│                                       │                                   │            │
│                                       │ NIL REDACTION LAYER · scan       │            │
│                                       │ Publish Gate → 17 names checked  │            │
│                                       │                                   │            │
│                                       │ ... up to 5 cards, fade after 3s │            │
│                                       └───────────────────────────────────┘            │
│                                                                                        │
│  ┌─ TECH STACK STRIP (bottom) ──────────────────────────────────────────────────┐    │
│  │ Built on Google ADK · 5 Gemini models · Vertex AI · Cloud Run · BigQuery ·   │    │
│  │ Firestore · Cloud Storage · Nano Banana Pro · Gemini Google Search grounding │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [Bottom-fixed nav strip — same as every page]                                          │
│ THE WIRE · THE MAP · THE FIELD · THE FLOOR · THE STORIES · THE GATE                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Copy — every text element specified

### Page title (replaces "THE FLOOR · SEVEN AGENTS / The room thinking, in real time")

**Primary:** `GOOGLE AGENT DEVELOPMENT KIT` (tracked-cap, gold, ~28pt mono or Lora bold)

**Subtitle:** *Seven Gemini agents · Live agentic orchestration* (italic Lora, parchment, ~16pt)

**Optional small kicker above:** `PRODUCTION DECK · LIVE` (tracked-cap, slate, ~11pt) — signals this is the behind-the-scenes page per Charlie's *"these sections are where we show our work"* framing.

### Explainer card (new — left column, beside the graph)

```
WHAT YOU'RE LOOKING AT

Seven Gemini agents, orchestrated by Google's new Agent Development Kit (ADK).
Each agent has its own model, its own role, and its own tool surface — and
they hand off work to each other in real time, over Firestore events on
Google Cloud Run.

This page is what built every story you've read on this site. Watch a
handoff fire: a particle flows along the edge from the source agent to the
target. Watch a tool call: a card slides in from the right showing the
specific Google service in use.

This is how the room finds, verifies, and tells hometown stories — and how
it does it without ever naming an individual athlete.
```

Three short paragraphs. Italic Lora, parchment text on deep-navy card with a gold hairline. Sits in the left column where the page is currently empty.

### Per-agent treatment

Each node in the graph gets a permanent caption underneath, three lines:

| Node | Caption format |
|---|---|
| EDITOR | **EDITOR** · Orchestrator · *Gemini 3.1 Pro* |
| SCOUT DESK | **SCOUT DESK** · 4 sub-scouts · *Gemini 3 Flash ×4* |
| INVESTIGATOR | **INVESTIGATOR** · Source verification · *Gemini 3.1 Pro + Deep Research* |
| EQUITY EDITOR | **PARALYMPIC EQUITY EDITOR** · Parity enforcement · *Gemini 3.1 Pro* |
| STORYTELLER | **STORYTELLER** · Literary drafts · *Gemini 3.1 Pro* |
| NARRATOR | **NARRATOR** · Broadcast voice · *Gemini 3.1 Flash TTS (Algenib)* |
| PUBLISH GATE | **PUBLISH GATE** · 7-stage audit · *Gemini 3.1 Pro + Python NIL Layer* |

Line 1: agent name (tracked caps, parchment, bold). Line 2: role one-liner (mono, slate). Line 3: model attribution (italic, gold).

**Hover state** (extra credit if time): hover an agent → small panel appears showing 1–2 sentence detailed role description. Examples below — these can also live as tooltips:

- **Editor:** *"Decomposes user prompts, manages the queue, dispatches investigations, accepts or overrides Equity Editor recommendations. Terse and decisive."*
- **Scout Desk:** *"Four sub-scouts in parallel — Cinderella (places that punched above their weight), Comeback (programs that returned after disappearing), Hometown (small-town origins), Echo (modern patterns that rhyme with iconic Olympic eras). Cites places and eras, never named athletes."*
- **Investigator:** *"Takes a Scout lead and builds an Investigation Packet — sources, evidence, narrative spine. Calls Gemini Deep Research for high-priority leads."*
- **Paralympic Equity Editor:** *"The impact lever. Has veto power over publication. Monitors feed drift, returns drafts with shallow Paralympic context, blocks any draft that frames disability as inspiration porn. Parity is a system property."*
- **Storyteller:** *"Writes 400–500 word literary drafts in documentary register. Anchored on a calibration exemplar quoted verbatim in its prompt. Never names individual athletes."*
- **Narrator:** *"Converts the Storyteller's prose into spoken broadcast narration via Gemini 3.1 Flash TTS. Warm mid-tone, deliberate breath. The audio you hear on every Broadcast page."*
- **Publish Gate:** *"Runs seven sub-stages before publication — Fact Check, Source Review, Parity Review, NIL Redaction, Safety Review, Language Review, Visual Review. The compliance backbone."*

### Tool call cards — cleanly labeled (existing UI, refined content)

When an agent calls a tool, the card that slides in on the right must show the actual GCP service in use. Required label format:

```
┌───────────────────────────────────┐
│ VERTEX AI · GEMINI 3.1 PRO        │  ← tool/service in mono caps gold
│ Editor → deliberation              │  ← agent + operation in parchment
│ 1.2s · complete                    │  ← duration + status in slate
└───────────────────────────────────┘
```

Labels for each tool type (the worker should map agent operations to these strings):

| Operation | Card top line |
|---|---|
| Editor / Storyteller / Equity Editor / Investigator / Publish Gate deliberation | `VERTEX AI · GEMINI 3.1 PRO` |
| Scout Desk scout cycle | `VERTEX AI · GEMINI 3 FLASH` |
| NIL near-id check | `VERTEX AI · GEMINI 3.1 FLASH-LITE` |
| Investigator deep-research call | `VERTEX AI · GEMINI DEEP RESEARCH` |
| Narrator TTS render | `VERTEX AI · GEMINI 3.1 FLASH TTS` |
| Hero illustration generation | `VERTEX AI · NANO BANANA PRO` |
| Grounded web search | `GEMINI · GOOGLE SEARCH GROUNDING` |
| BigQuery read | `BIGQUERY · {table_name}` |
| Firestore write | `FIRESTORE · {collection_name} · WRITE` |
| Firestore read | `FIRESTORE · {collection_name} · READ` |
| NIL Layer scan | `NIL REDACTION LAYER · scan` |
| Visual Review | `VISUAL REVIEW · stylization check` |

Cards persist ~3s after completion, then fade. Up to 5 cards visible at once. Cards stack bottom-up; oldest fades first.

This is the directive from VPS-DEC-037 *"clean tool-call-card labeling"* — fully specified.

### Tech-stack strip (bottom of page, above bottom nav)

Single horizontal line, mono caps, parchment, separated by gold middle-dots:

```
BUILT ON GOOGLE ADK · 5 GEMINI MODELS · VERTEX AI · CLOUD RUN · BIGQUERY · FIRESTORE · CLOUD STORAGE · NANO BANANA PRO · GEMINI GOOGLE SEARCH GROUNDING
```

That's 9 Google products named in one strip. A judge skimming sees the whole Google Cloud surface area at a glance.

---

## What this delivers

| Judge question | Page answer |
|---|---|
| *"What is this page?"* | The big title and explainer card answer in 5 seconds: ADK orchestration, seven agents, what built the stories. |
| *"Are these really separate agents?"* | Per-agent captions show name + role + Gemini model. Seven different model assignments visible. |
| *"Is this real or a single LLM in costume?"* | Tool call cards on the right show actual Vertex AI / BigQuery / Nano Banana Pro / Firestore calls happening, with durations. |
| *"What Google tech are they using?"* | The bottom tech-stack strip names 9 Google products explicitly. |
| *"Why does this matter?"* | Explainer card paragraph 2: *"This page is what built every story you've read on this site."* |
| *"How does parity get enforced?"* | Equity Editor node + caption + the "Parity is a system property" hover description. |

Five demo moments mapped:
- **Demo Moment #1 (room is alive):** ambient Wire ticker still scrolls at top + tool cards stream on the right
- **Demo Moment #2 (truly agentic):** THE WHOLE PAGE. This is where #2 lives.
- **Demo Moment #3 (Equity Editor caused anchor):** Equity Editor's Agitos-red flash on intervention + caption naming its veto authority
- **Demo Moment #4 (Broadcast):** referenced in explainer card paragraph 2 (this is what built the stories)
- **Demo Moment #5 (Publish Gate trust):** Publish Gate node + caption naming "7-stage audit" + tool cards showing NIL Redaction Layer scan operations

---

## Compliance pass

- ✓ No athlete names anywhere — agent captions, hover text, tool call labels all describe places and roles, not individuals
- ✓ No protected marks — Google product names only
- ✓ No NGB names — agent roles describe what they do, not who they work for
- ✓ Conditional phrasing not needed (no predictive claims on this page)
- ✓ The Agitos-red color signature on Equity Editor is per BUILD_SPEC color tokens (`#C8102E`) — a color, NOT the Paralympic Agitos logomark itself
- ✓ Mobile responsive (VPS-DEC-046): the graph reflows or scales; explainer card stacks above; tool call cards become a single-column list below the graph

---

## Worker prompt fragment for the HoE

```
Refresh /floor to scream Google ADK / agentic AI. Use the spec at
Docs/VPS/floor-agentic-treatment.md.

Specific changes:

1. Replace the current page title ("THE FLOOR · SEVEN AGENTS / The room thinking,
   in real time") with:
   - Primary: "GOOGLE AGENT DEVELOPMENT KIT" (tracked caps, gold, ~28pt)
   - Subtitle: "Seven Gemini agents · Live agentic orchestration"
   - Optional kicker above: "PRODUCTION DECK · LIVE" (tracked caps, slate, small)

2. Add an explainer card in the left column (currently empty real estate).
   Use the three-paragraph copy in the spec verbatim.

3. Add permanent captions under each of the 7 agent nodes — three lines:
   agent name (tracked caps), role one-liner (mono), Gemini model (italic gold).
   Exact strings in the spec.

4. Refine the existing tool-call cards on the right so the top line is
   the actual GCP service in use ("VERTEX AI · GEMINI 3.1 PRO", "BIGQUERY ·
   candidates", "NANO BANANA PRO", etc.). Mapping table in the spec.

5. Add a bottom tech-stack strip above the page footer:
   "BUILT ON GOOGLE ADK · 5 GEMINI MODELS · VERTEX AI · CLOUD RUN · BIGQUERY ·
   FIRESTORE · CLOUD STORAGE · NANO BANANA PRO · GEMINI GOOGLE SEARCH GROUNDING"

6. Keep "The Floor" alive in the bottom nav strip and the URL (`/floor`) only.
   Page header is ADK.

7. Hover state on each agent node (extra credit if time): show a 1–2 sentence
   detailed role description. Copy in the spec.

Mobile responsive at <768px: graph scales, explainer card stacks above,
tool call cards become a single-column list below.

Don't touch the existing particle handoffs, the Equity Editor Agitos-red
flash on intervention, or the SSE handoff stream subscription — those are
already working.
```

---

## Two micro-edits to other docs once this lands

1. The Devpost text description currently doesn't mention `/floor` by name as a surface. Could add a line in the *"What the room does"* section: *"And one surface — `/floor` — exists for the curious fan or technical judge who wants to see the agents at work: a live agent graph showing the seven ADK agents handing off work in real time, with every Vertex AI / BigQuery / Nano Banana Pro call labeled."*

2. The demo script's 2:10–2:35 segment (the agentic-claim beat) already mentions ADK explicitly. Once the page treatment lands, the visual is finally worthy of the voiceover.

---

## Why this is worth 20 minutes

Right now `/floor` is the most-impressive-on-paper part of the architecture and the least-legible-on-screen. Charlie's observation is right: judges land here and see a slick animation. With this treatment, they land here and read: *"this is Google's Agent Development Kit running seven Gemini agents in production, and here is exactly what each one is doing right now."* The Technical Depth axis (30% of judging) shifts from inferred to demonstrated. The *"year of agents"* claim becomes visible, not implied.
