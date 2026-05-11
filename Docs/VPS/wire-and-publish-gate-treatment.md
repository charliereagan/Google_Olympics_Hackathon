# `/wire` and `/publish-gate` — Agentic AI / ADK Treatment Spec

**Purpose:** Bring both Production Deck pages up to the same ADK-forward, judge-legible standard as the `/floor` treatment. Frame each for a Google judge in 5 seconds; name the tech explicitly; map each page's content to the contest's judging axes.

**Companion docs:**
- `/Docs/VPS/floor-agentic-treatment.md` — the parent spec for the agent-graph page
- `/Docs/VPS/story-infographic-data.md` — story-page treatments (Front of House counterpart)

**Strategic frame:** The three Production Deck pages each prove a different thing:

| Page | What it proves to a judge | Contest axis it earns |
|---|---|---|
| `/floor` | Seven ADK agents orchestrating with real handoffs and real tool calls | Technical Depth (30%) — "truly agentic" |
| `/publish-gate` | Architectural NIL compliance via the 11,188-entry registry + disambiguation reasoning shown in full | Technical Depth + content-restriction credit |
| `/wire` | Live agent thinking tagged with Gemini model attribution on every event | Technical Depth + "real, not faked" |

Three pages, three different proofs, one consistent ADK framing across all of them.

---

# Part 1 — `/publish-gate`

## Current state (Day 7 evening, May 11)

What's working (per screenshot):
- ✓ Title and dek read editorially: *"What the room caught. Every claim, every redaction, every name disambiguated. The room shows its work."*
- ✓ Production Deck signal via the `BEHIND THE SCENES` kicker — already in place
- ✓ Big numbers are real and non-zero: **2,933 claims checked · 152 redactions performed · 39 disambiguation hits · 23/1 cleared/blocked**. PROJECT_BRIEF §14 verification passes.
- ✓ Disambiguation trace at the bottom is **the strongest single piece of content on the page** — Step 1 surface match → Step 2 context vector → Step 3 candidate ranking → Step 4 resolution. Real AI reasoning shown in full.
- ✓ Footer attribution: *"athlete_registry: 11,188 entries · last_updated: 2026-05-06 · matcher: aho-corasick"*

What needs work:
- The page doesn't explicitly explain WHY the NIL Redaction Layer matters or that it's enforced via ADK
- The "PASS" column in Recent Decisions is contradictory on entries that actually got returned or revised
- The disambiguation trace is below the fold — it's the strongest content but appears last

## Three additions

### Addition 1 — Framing card at top, below the kicker

Insert a three-paragraph framing card between the dek and the big-number bar. Same role as the `/floor` explainer card. Copy verbatim:

```
WHY THIS PAGE EXISTS

The hackathon's strictest rule: no individual Team USA athlete may be named
in user-facing output. Most submissions handle this with a content review at
the end. We made it architecture.

Every text the Storyteller writes passes through the NIL Redaction Layer
— a Python module running between the Storyteller agent and any reader,
querying an 11,188-entry athlete registry on every claim. Direct matches
are redacted. Near-identifications are returned to the Storyteller for
revision. Ambiguous tokens are disambiguated against context (see the trace
below).

Compliance, made structural by Google's Agent Development Kit. The
constraint became the credibility flex.
```

**Typography:** italic Lora body, parchment text on slightly-lighter-navy card with a gold hairline. Two-column width same as the big-number bar above and below it. **The final sentence** — *"Compliance, made structural by Google's Agent Development Kit. The constraint became the credibility flex."* — should be set in a slightly larger or bolder treatment so it lands as the page's thesis.

### Addition 2 — Fix the PASS-column ambiguity in Recent Decisions

Right now the Recent Decisions list shows entries like:

- *"nil redaction: near-identification flagged, returning"* → **PASS**
- *"publish decision: revise"* → **PASS**
- *"returned at fact_check for revision"* → **PASS**

This reads contradictory. *Returning* and *revise* are not pass states. Two ways to fix:

**Option A (light touch):** Rename the column header from `PASS` to `OK` — meaning "operation completed without error." The current column is reporting *operational success*, not *decision outcome*. Renaming clarifies that without restructuring the data.

**Option B (stronger):** Show the actual decision in that column: `PASS` / `REDACT` / `AGGREGATE` / `RETURN` / `REVISE` / `BLOCK`. This converts the column from operational telemetry to **the Layer's decisions, visible in scroll form** — which is what a judge wants to see.

**Strongly prefer Option B.** A judge reading *"23 cleared / 1 blocked"* in the big-number bar and then seeing the Recent Decisions list reveal which specific drafts got returned, which got redacted, which got blocked — that's the trust signal at full strength. The page becomes a live receipt of the Layer's judgment, not just its activity.

If the worker can't do Option B in time, Option A is the safety net.

### Addition 3 — Promote the disambiguation trace above the Recent Decisions list

Currently the page order is:
1. Big numbers
2. Recent Decisions list (long)
3. Disambiguation trace (below the fold)

Reorder to:
1. Big numbers
2. Framing card (new — Addition 1)
3. **Disambiguation trace** (promoted)
4. Recent Decisions list

The trace is the most compelling content. Make a judge see it on first paint, not after scrolling through 12 decisions. Add a small section header above it: `DISAMBIGUATION TRACE · ONE AMBIGUOUS SPAN, FOUR STEPS, ONE CLEARED SENTENCE`.

### Optional Addition 4 — Tech-stack strip at bottom

Same strip as `/floor`:

```
BUILT ON GOOGLE ADK · 5 GEMINI MODELS · VERTEX AI · CLOUD RUN · BIGQUERY · FIRESTORE · CLOUD STORAGE · NANO BANANA PRO · GEMINI GOOGLE SEARCH GROUNDING
```

Above the bottom nav. Single line, mono caps, parchment, gold middle-dots. Cross-page consistency.

---

# Part 2 — `/wire`

## Current state

What's working:
- ✓ The Wire ticker filter shipped earlier — fan-readable timestamps and headlines instead of engineering debug
- ✓ Pre-seed on first paint (VPS-DEC-028) so the page never says *"the room is quiet"*
- ✓ Documentary register on event copy

What needs work:
- The page doesn't explain itself — a judge lands here and sees a scrolling list of agent thoughts with no context
- Events don't show which Gemini model produced them
- No agent legend / role explanation visible
- No ADK attribution anywhere on the page
- No filter affordance to isolate, say, *"all Equity Editor interventions"*

## Five additions

### Addition 1 — Page header rename and framing

**Current:** probably reads as *"The Wire"* or similar shorthand.

**Replace with:**

```
[Production Deck kicker, tracked caps, slate]
BEHIND THE SCENES

[Sub-kicker, tracked caps, gold]
GOOGLE ADK · LIVE AGENT FEED

[Big title, Playfair Display, ~48pt]
The room thinking, in real time.

[Dek, italic Lora]
Every thought, every handoff, every decision — from seven Gemini agents
orchestrated by Google's Agent Development Kit.
```

The Production Deck kicker stays consistent with `/publish-gate` and `/floor` (the three pages get the same shape). The big title preserves the broadcast-poetic voice. The dek explicitly names ADK and seven agents.

### Addition 2 — Left-column legend / explainer

The page has a long vertical stream of events but the left half of the screen has unused real estate. Use it for a persistent legend card:

```
WHAT YOU'RE LOOKING AT

This is the raw working-room feed of seven Gemini agents orchestrated by
Google's Agent Development Kit (ADK). Every thought, every handoff, every
decision the room makes — in the order it happens.

The ambient ticker on every page shows the curated highlights. This page
shows everything.

THE AGENTS

· Editor                    Gemini 3.1 Pro      Orchestrator
· Scout Desk                Gemini 3 Flash ×4   Lead-finders (Cinderella,
                                                Comeback, Hometown, Echo)
· Investigator              Gemini 3.1 Pro      Source verification +
                            + Deep Research      Investigation Packets
· Paralympic Equity Editor  Gemini 3.1 Pro      Parity enforcement (veto)
· Storyteller               Gemini 3.1 Pro      Literary drafts
· Narrator                  Gemini 3.1 Flash    Broadcast voice (Algenib)
                            TTS
· Publish Gate              Gemini 3.1 Pro      7-stage audit including
                            + Python NIL Layer   NIL Redaction
```

**Typography:** card sits at the top-left, persistent (doesn't scroll). Italic Lora for the explainer paragraphs; mono caps for `THE AGENTS` header; mono parchment for the agent table. Gold hairline border. Width ~30% of viewport on desktop; stacks above the event feed on mobile.

This is the same seven-agent legend that lives on `/floor`. Cross-page consistency. A judge clicking between `/floor` and `/wire` sees the same agent roster framed the same way.

### Addition 3 — Model attribution on every event

Every event in the feed currently shows: `timestamp · agent · message`. Add the model used:

```
17:19:41 · Editor (Gemini 3.1 Pro)
Storyteller stalled. Re-dispatching the Rust Belt rowing draft.

17:20:37 · Equity Editor (Gemini 3.1 Pro)
Cleared. Paralympic depth equal to Olympic for this place.

17:21:14 · Hometown Scout (Gemini 3 Flash)
Population 4,200. First Paralympian since 1992. Confidence 0.74.

17:21:48 · Investigator (Gemini Deep Research)
Pulling sources. Quad-City Times has hometown coverage going back to 1996.

17:22:03 · Publish Gate (Gemini 3.1 Pro + NIL Redaction Layer)
4 individual references reviewed. 2 aggregated. 2 redacted. Cleared.
```

**Typography:** the `(Gemini 3.1 Pro)` parenthetical in mono caps, deep parchment, smaller than the agent name. Subtle but every event becomes a visible Gemini API attribution.

Across a typical page of 50–100 scrolling events, that's 50–100 visible model attributions. The *"five Gemini models in concert"* claim lands not as a sentence in marketing copy, but as ambient visible texture in every line. **This is the single highest-leverage edit for the page's Technical Depth signal.**

### Addition 4 — Filter affordance (optional, time permitting)

Pill toggles at the top of the event feed:

```
ALL · EDITOR · SCOUTS · INVESTIGATOR · EQUITY EDITOR · STORYTELLER · NARRATOR · PUBLISH GATE
```

Click one → filter events to just that agent. URL query param so a filtered view is shareable (`/wire?agent=equity_editor`).

This lets a judge isolate, for example, *"show me everything the Equity Editor did today"* and see a clean run of parity interventions — proving the parity-as-system-property claim at full strength.

**Priority:** Lower than additions 1–3. Add only if time after the rest of the Production Deck work lands. Approve Option A on `/publish-gate` PASS column before this.

### Addition 5 — Tech-stack strip at bottom

Same strip as `/floor` and (Optional Addition 4 of) `/publish-gate`:

```
BUILT ON GOOGLE ADK · 5 GEMINI MODELS · VERTEX AI · CLOUD RUN · BIGQUERY · FIRESTORE · CLOUD STORAGE · NANO BANANA PRO · GEMINI GOOGLE SEARCH GROUNDING
```

Cross-page consistency. Three Production Deck pages, one strip. A judge sees it three times across their visit; the GCP stack gets etched in.

---

# Part 3 — Compliance pass (both pages)

- ✓ No athlete names anywhere — placeholder names like `[athlete:A]` in the disambiguation trace are *intentional* (they're how the Layer represents redaction candidates and they're already there).
- ✓ No protected marks — only Google products named.
- ✓ No NGB names presented as sport substitutes.
- ✓ The Mount Pleasant disambiguation trace example uses the place name; that's encouraged (place over person).
- ✓ Mobile responsive at <768px: legend cards stack above feeds; tool-call cards become single column; tech-stack strip wraps to 2–3 lines.
- ✓ Forbidden temporal phrasing absent; encouraged phrasing where applicable.
- ✓ Conditional phrasing not needed (no predictive claims).

---

# Part 4 — Worker prompt fragment for the HoE

```
Refresh /publish-gate and /wire to scream Google ADK / agentic AI, matching
the treatment shipped on /floor. Use the spec at
Docs/VPS/wire-and-publish-gate-treatment.md.

----- /publish-gate -----

1. Insert a 3-paragraph framing card between the existing dek and the
   big-number bar. Copy verbatim is in the spec ("WHY THIS PAGE EXISTS").
   Italic Lora on slightly-lighter-navy card with gold hairline.

2. In the Recent Decisions list, replace the "PASS" column with the actual
   decision: PASS / REDACT / AGGREGATE / RETURN / REVISE / BLOCK. If that's
   too risky to refactor today, fall back to renaming the column header
   from "PASS" to "OK" so it stops reading contradictorily on entries that
   were returned or revised.

3. Reorder the page sections so the disambiguation trace appears BEFORE the
   Recent Decisions list, immediately after the framing card and big-number
   bar. Add a small section header above it:
   "DISAMBIGUATION TRACE · ONE AMBIGUOUS SPAN, FOUR STEPS, ONE CLEARED
   SENTENCE"

4. Add the tech-stack strip above the bottom nav (single line, mono caps,
   parchment, gold middle-dots):
   "BUILT ON GOOGLE ADK · 5 GEMINI MODELS · VERTEX AI · CLOUD RUN ·
   BIGQUERY · FIRESTORE · CLOUD STORAGE · NANO BANANA PRO · GEMINI GOOGLE
   SEARCH GROUNDING"

----- /wire -----

1. Replace the current page header with:
   - Kicker (tracked caps, slate): "BEHIND THE SCENES"
   - Sub-kicker (tracked caps, gold): "GOOGLE ADK · LIVE AGENT FEED"
   - Title (Playfair Display, large): "The room thinking, in real time."
   - Dek (italic Lora): "Every thought, every handoff, every decision —
     from seven Gemini agents orchestrated by Google's Agent Development
     Kit."

2. Add a persistent left-column legend card. Content in the spec ("WHAT
   YOU'RE LOOKING AT" plus the THE AGENTS table). Width ~30% on desktop;
   stacks above the feed on mobile. Stays fixed; does not scroll with the
   event feed.

3. On every event in the feed, append the Gemini model used in mono caps
   parentheses after the agent name. Examples:
   - "Editor (Gemini 3.1 Pro)"
   - "Hometown Scout (Gemini 3 Flash)"
   - "Investigator (Gemini Deep Research)"
   - "Narrator (Gemini 3.1 Flash TTS)"
   - "Publish Gate (Gemini 3.1 Pro + NIL Redaction Layer)"
   
   Mapping from internal agent_id to display string should be a static
   table in the frontend, not synthesized.

4. Add filter pills at the top of the feed (only if time):
   "ALL · EDITOR · SCOUTS · INVESTIGATOR · EQUITY EDITOR · STORYTELLER ·
   NARRATOR · PUBLISH GATE"
   URL query param for filtered view (?agent=equity_editor).

5. Add the same tech-stack strip above the bottom nav.

Mobile responsive at <768px for both pages: cards stack, columns collapse,
strip wraps. No horizontal scroll.

Don't touch:
- The disambiguation trace content on /publish-gate (it's already gold)
- The pre-seeded Wire ticker behavior on /wire
- The bottom-nav strip on either page
- Existing SSE subscriptions
```

---

# Part 5 — Why this is worth doing now

Two pages, three additions each. Maybe 90 minutes of worker time. The leverage:

- **`/publish-gate`** becomes the page that proves compliance is structural, not a content-review afterthought. The framing card + non-zero numbers + promoted disambiguation trace tells a complete trust story in 30 seconds of judge time.
- **`/wire`** becomes the live ADK-attribution receipt. Every event tagged with its Gemini model means every line of scrolling text is a visible Gemini API call. A judge skimming for 60 seconds sees dozens of Gemini-model attributions — the "year of agents" claim made unrelenting.

Combined with `/floor` (already specced), the three Production Deck pages now hit the Technical Depth axis (30% of judging) from three different angles. The Front of House surfaces stay editorial; the Production Deck pages tell the Google story.
