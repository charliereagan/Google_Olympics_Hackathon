# Day-5 HoE Directive — Audit Closures + Fan-Engagement Reframe

**From:** VPS Session 2 (Claude Opus 4.7) + Charlie Reagan
**Date:** 2026-05-06 (Day 5 of build)
**Audience:** Head of Engineering session (Claude Code)
**Supersedes:** Previous Day-5 HoE feedback (delivered earlier the same day in chat). The six audit closures still stand; front-door design is reframed; three new build items added; build sequence rewritten.

This document is the canonical Day-5 directive. Every prompt to a coding agent that touches the items below should reference it.

---

## 0 — Read these first, in order

1. `PROJECT_BRIEF.md` (legal/compliance — wins on rules questions)
2. `CONSTITUTION.md` v1.2 (terminology clarifier and autonomous-newsroom Kill List item are new)
3. `Docs/Engineering/BUILD_SPEC.md` v1.2 (Day-1 tightening pass landed; Day-5 additions pending — this directive enumerates them)
4. `Docs/VPS/VPS-HANDOFF.md` Sections 5 (Decisions VPS-DEC-035 through VPS-DEC-044) and 8 (Lessons 19–25). Every directive below traces back to a numbered decision with its reasoning preserved.

---

## 1 — Strategic frame: build the fan engagement product, not the demo

The build is **4–5 days ahead of schedule on craft**. Charlie's Day-5 strategic call is to stop optimizing for the 3-minute demo storyboard and start building the fan engagement site that someone would actually want to use. The contest brief makes this explicit (*"interactive tools for fans everywhere"*, *"Help fans find where excellence is fostered"*) and our locked Pivot A+ positioning matches it (*"Most fans of Team USA know the famous names. Far fewer know the towns that produced them"* — the locked Devpost opener at VPS-DEC-036).

If we build the right fan product, the demo writes itself by recording a fan's natural flow through it. The demo is downstream of the product; the product is not downstream of the demo.

**This shift does not change** Pivot A+, NIL strict reading, the seven-agent architecture, the Mount Pleasant Broadcast as the hero, or any compliance work. It changes what `/` looks like and adds new discovery surfaces. **Six Day-5 audit closures still stand** (Sections 6–7 below).

---

## 2 — The new front door (`/`) — fan-engagement first (VPS-DEC-041)

**Replaces** the previously-proposed Wire-two-thirds-left + Stack-right-column design. That design served judges (proving liveness) more than fans (delivering them to the hero piece). The new structure puts the hero — the actual story — at the center, keeps the room visibly alive via an ambient Wire band, and offers three discovery doors below.

```
┌─────────────────────────────────────────────────────────────────────┐
│ [Editorial masthead — tracked-cap "THE STORYTELLER'S ROOM" left,    │
│  date + "800 days to LA28" mono right; gold hairline below]         │
├─────────────────────────────────────────────────────────────────────┤
│ [Ambient Wire ticker band — 32px, horizontal scroll, persistent on  │
│  every page. Pre-seeded VPS-DEC-028 events on first paint, then     │
│  live SSE on top.]                                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│        [FULL-BLEED CINEMATIC HERO of latest published story]        │
│        Hero illustration (stylized place, no people)                │
│        Headline overlay (Playfair Display)                          │
│        Dek overlay (italic Lora, one sentence)                      │
│        Click → Broadcast (curtain rise, autoplay narration)         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  [Discovery row — three equal-weight cards, side by side]           │
│   THE MAP             THE FIELD            THE STORIES              │
│   "Find your region"  "Follow patterns"   "What the room has told"  │
├─────────────────────────────────────────────────────────────────────┤
│  [Seed-prompt CTA — full width, slightly darker band]               │
│   "Find me a Team USA hometown story I've never heard before…"      │
│   Submit (broadcast lower-third style)                              │
│   Hint: "or sit back and watch the room work"                       │
├─────────────────────────────────────────────────────────────────────┤
│  [Recent stories grid — 3–4 published stories as compact cards]     │
│   The Stack, made explicit and visual                               │
├─────────────────────────────────────────────────────────────────────┤
│ [Bottom-fixed nav strip — broadcast chrome, mono caps]              │
│ THE WIRE · THE MAP · THE FIELD · THE FLOOR · THE STORIES · THE GATE │
└─────────────────────────────────────────────────────────────────────┘
```

**Constitutional check:** Constitution §11 calls for *"cinematic hero (a stylized landscape, not a person). Wire beginning to scroll."* The story-hero IS a stylized-landscape hero. The ambient Wire band IS the Wire scrolling. *"No 'Welcome to' banner. No marketing copy."* — none added; the only typography on the page is editorial (story headline, masthead, surface labels), not marketing. The kicker/dek/hero-card landing-page pattern remains rejected per VPS-DEC-040.

**The dedicated full-page Wire view moves to `/wire`** for fans / judges who want to watch the room work in full. Same Wire stream, no other layout, no story hero, no discovery row — just the Wire and ambient broadcast chrome. This is where Demo Moment #1 ("the room is alive") gets its purest expression for any judge who clicks `THE WIRE` from the bottom nav.

**Optional discoverable "?" overlay:** approved (VPS-DEC-040). Top-right corner, gold character, hover-revealed, click → 3-paragraph editorial explainer. Never auto-opens.

---

## 3 — Three discovery surfaces, three fan motivations (VPS-DEC-042)

| Surface | Route | Fan motivation | Implementation notes |
|---|---|---|---|
| **The Map** | `/map` (NEW) | "Find your region" — geographic familiarity | Stylized US map, deep navy base, painterly aesthetic. **Do NOT use Google Maps or any third-party map tile provider** — third-party logos = auto-DQ per PROJECT_BRIEF §7. Custom SVG or D3-geo with public US state-boundary GeoJSON. Place dots in warm gold sized by Olympian/Paralympian count. Hover → tooltip with place name + story title. Click → Broadcast. |
| **The Field** | `/field` (RENAMED from current `/floor`) | "Follow the patterns" — abstract, non-geographic | Existing constellation, no functional change. Side-panel agent activity log on click stays. Update masthead to *"THE FIELD / places, programs, patterns"*. |
| **The Stories** | `/story` (already shipped) | "Read what's new" — chronological / editorial | Add facets per VPS-DEC-043 (Section 4 below). |

**Critical:** the constellation survives the rename — Charlie's instinct against forced-geographic-bias is right. The Map adds a *complementary* bias for fans who want it. Two siblings, not substitutes. (Lesson 25: a discovery surface's bias becomes a feature when sibling surfaces with complementary biases exist.)

**The seven-agent backstage `/floor` still gets built** at the now-vacated `/floor` route per BUILD_SPEC §9. This is Demo Moment #2 (proving the agentic claim). It's not a fan discovery surface — it's the proof-of-craft surface for any technical fan or judge who clicks `THE FLOOR` from the bottom nav.

---

## 4 — Story index facets (VPS-DEC-043)

The `/story` page is gorgeous as a chronological publication, but a motivated fan ("show me wrestling places," "show me Paralympic-anchored places") gets no help from chronological browsing. Add facets to convert it from archive into discovery tool.

**Facets, surfaced as a thin pill-toggle row below the page header:**

- **By sport** — wrestling, swimming, track and field, alpine, etc. Use *official sport names*, not NGB names (PROJECT_BRIEF §10). Dropdown or horizontal scroll of pills depending on count.
- **By era / decade** — 1960s, 1970s, 1980s, 1990s, 2000s, 2010s, 2020s. Use the encouraged temporal phrasing from CONSTITUTION Law 5 / VPS-DEC-033 — "first," "next," "newest" in tooltips and labels; never "former" or "past."
- **By type** — Olympic / Paralympic / Both. Three pills.

**Behavior:**

- Selecting a facet filters the story list inline (no full-page navigation; no spinner; instant filter on existing data).
- Multi-facet selection is allowed (e.g., wrestling + 1980s + Both).
- Facet state reflected in URL query params (`/story?sport=wrestling&type=paralympic&era=2020s`) so fans can share filtered views.
- Facet values populated from existing story metadata (`primary_sports`, `representation_history`, `olympic_or_paralympic` on the candidates table per BUILD_SPEC §8.1).

**Implementation:** facet bar should match the existing typography of `/story` (tracked-cap kickers, italic Lora deks). No bright pills — gold outline, deep navy fill on selected, parchment text. Match the publication aesthetic.

---

## 5 — Broadcast page autoplay (VPS-DEC-044)

The Mount Pleasant Broadcast page currently shows a play button at `00:00 / 02:59` requiring a click to begin. That's the safe webpage default. It is the wrong UX for a *broadcast*. A broadcast doesn't ask permission to begin.

**Implementation:**

1. **Primary path — fan navigates from front-door hero / Map / Field / Stories index → Broadcast.** The click that brought them to the page counts as user interaction in the same browser tab. Modern browsers permit autoplay-with-sound under that condition. Narration begins immediately as part of the curtain-rise choreography (BUILD_SPEC §7.1) — the page's first sound is the Narrator's audible breath at 0.8s, then the first word at 1.0s, then music bed at 1.5s. No visible play button needed (or very small, secondary).

2. **Fallback path — direct-link arrival** (shared URL, judge with bookmarked link, browser that's overly strict). Browser blocks autoplay-with-sound. Page falls back to **autoplay-muted with a prominent gold "BEGIN BROADCAST" overlay** centered on the player area. Single click → unmute and play from start. The overlay is intentionally visible — this is a broadcast experience and we want them to start it.

3. **Mute toggle — always visible, always obvious.** Top-right of the player area, gold icon, ~44×44px tap target. Never hidden behind a hover. The muted/unmuted state persists through the page session (e.g., a fan who mutes on Mount Pleasant and then navigates back to the front door and clicks into another story should arrive muted — until they unmute).

**The pacing of the curtain rise (BUILD_SPEC §7.1) does not change.** It remains 1.5–2.0 seconds of choreographed transition. Autoplay just removes the manual play-button click that was sitting between the navigation and the choreography starting.

---

## 6 — Three Constitutional drifts to close

These are unchanged from the original Day-5 audit. Repeating compactly because they're still the priority.

### Drift A — `/` shows "The room is quiet." on first paint

**Implement VPS-DEC-028 Wire pre-seed.** On page mount, before subscribing to live SSE, fetch most recent ~6 events from Firestore (`mode IN ('replay','published')`, ordered `timestamp DESC`), render into the ambient Wire ticker band, then subscribe live. The Wire is *ambient* now (top-of-page band, not centerpiece — see Section 2), but the pre-seed is still required. Hours of work.

### Drift B — `/floor` is a places-constellation, not the seven-agent graph

**Rename current `/floor` → `/field`** (VPS-DEC-038). **Build new `/floor`** as the seven-agent backstage view per BUILD_SPEC §9 (seven nodes, particle-stream handoffs, tool call cards stacking and fading at bottom-right, Equity Editor flashes Agitos-red on intervention). Estimated 2 days.

### Drift C — `/publish-gate` shows 0 redactions / 0 disambiguation hits

**Fix aggregation** to pull from real per-story audit footers (Mount Pleasant `[NIL: 2r/1a]`, etc.). **Verify** with the team whether Mount Pleasant's `2r/1a` reflects Layer work or Storyteller pre-redaction (Q11 in VPS-HANDOFF Section 6). If the Layer's actual work is zero because the Storyteller is well-disciplined, **engineer at least one demonstration story** whose source corpus contains athlete names so the Layer catches them and aggregates them. PROJECT_BRIEF §14: *"NIL Redaction Layer's audit log shows real redaction work (not all-zeros)"* — pre-DQ flag right now. 0.5–1 day.

---

## 7 — Three contest-brief items

Unchanged from the original Day-5 audit.

- **VPS-DEC-035 — establishing shot of the live-URL front door at 0:05–0:10 of the demo video** (with seed-prompt CTA and discovery row visible). No interaction shown. The new front-door design from Section 2 above IS what's on screen during this shot.
- **VPS-DEC-036 — Devpost text description leads with the locked fan-centric opener.** No code work; VPS owns drafting. Locked opener: *"Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling."*
- **VPS-DEC-037 — explicit GCP / Vertex AI / code shot in the demo video.** PIP cutaway during the new `/floor` (agent graph) segment. Clean tool-call-card labeling on the agent graph itself ("Vertex AI / Gemini 3.1 Pro," "Cloud Run agent runtime," "BigQuery: candidates," "NIL Redaction Layer (Python)," "Nano Banana Pro").

---

## 8 — Build sequence

Sequenced for impact and dependency. Ten items now (six audit closures + four reframe items). The reframe items are not "instead of" the audit closures — they're "in addition to," and the schedule slack absorbs them.

| # | Item | Closes | Estimate |
|---|---|---|---|
| 1 | **Wire pre-seed on `/` (now as ambient ticker band per VPS-DEC-041)** | Drift A | Hours |
| 2 | **Verify continuous operation is running**; if not, launch tonight | Strategic | Hours to launch; days to run |
| 3 | **Fix `/publish-gate` aggregation; diagnose Layer-vs-Storyteller; engineer demo story if needed** | Drift C | 0.5–1 day |
| 4 | **Rename current `/floor` → `/field`** | Drift B (part 1) | Hours |
| 5 | **Build new `/` per VPS-DEC-041:** masthead + ambient Wire band + full-bleed story hero + 3-card discovery row + seed-prompt CTA + recent stories grid + bottom nav. Move full Wire view to `/wire`. | Drift A (full) + Brief gap 1 + Reframe | 1–2 days |
| 6 | **Build new `/floor` (seven-agent graph) per BUILD_SPEC §9** | Drift B (part 2) | 2 days |
| 7 | **Build new `/map` per VPS-DEC-042** (custom SVG or D3-geo, no third-party tiles) | Reframe | 1–1.5 days |
| 8 | **Add facets to `/story` per VPS-DEC-043** (sport, era, type) | Reframe | 0.5–1 day |
| 9 | **Implement Broadcast autoplay-with-mute per VPS-DEC-044** | Reframe | Hours |
| 10 | **Optional "?" affordance** (top-right, hover-revealed, 3-paragraph overlay, never auto-opens) | Front-door comprehension | Hours |

Items 1–4 are highest priority; should land Day 6. Items 5, 7, 8, 9 are Day 6–8. Item 6 (agent-graph Floor) is Days 7–8. Day 9 is dress rehearsal across the full product flow (no longer the demo storyboard rehearsal — a fan's natural flow through Map → Broadcast, Field → Broadcast, Stories → filter → Broadcast, front-door hero → Broadcast).

---

## 9 — The continuous-operation question (the most important item)

VPS-DEC-008 / VPS-DEC-027 require the demo's anchor (and ideally most published stories) to come from organic system production. If everything on `/story` is still fixtures, the architecture has not yet been *proven* end-to-end.

**HoE Session 2's first job:** confirm continuous operation is running and producing organic stories. Three possible states:

- **Running and producing organic stories already** — proceed with audit closures and let the corpus build. Aim for 15+ organic stories by Day 8 evening.
- **Running but producing nothing useful** — diagnose. Probably an agent prompt or candidate pool issue. Fix today; we have the schedule slack.
- **Not running** — launch tonight. Even 2–3 days of continuous operation produces enough corpus for Day 8 evening soft-rank. We are 4–5 days ahead of schedule precisely so we can do this.

This is the part of the spec that decides whether the product is *"polished demo of an AI newsroom"* or *"actual working AI fan engagement product."* The latter wins.

---

## 10 — Compliance through every change

Restating because every reframe item touches user-facing surfaces:

- **No individual Team USA athlete names anywhere user-facing** — including in tooltip text on `/map` place hovers, in facet labels on `/story`, in the seven-agent `/floor` hover states, in the optional "?" overlay copy, anywhere.
- **No third-party logos other than Google Cloud** — specifically, the new `/map` must use custom SVG or D3-geo with public GeoJSON, NOT Google Maps / Mapbox / Leaflet-with-tile-provider. Tile-provider attribution = third-party logo = auto-DQ per PROJECT_BRIEF §7.
- The forbidden-words list (former, past, ex-, retired Olympian; inspirational; hero; overcame; warrior; wheelchair-bound) AND the encouraged temporal-phrasing list (first, next, newest, earliest Olympian) both apply to all new copy — masthead, surface labels, "?" overlay, facet labels, hover tooltips, fallback text, error states.
- Story facets must respect Olympic terminology rules (no NGB names; "swimming" not "USA Swimming," "track and field" not "USATF").
- Daily check on Devpost Updates and Discussions tabs (VPS-DEC-034).
- Apache 2.0 license badge still visible on GitHub repo About sidebar — re-verify before any commit.

---

## 11 — What to bring back to Charlie

After reading this, before starting work:

1. **Confirmation of build sequence** — any reordering you want.
2. **Status of continuous operation** (Section 9) — answer this *before* anything else.
3. **The publish-gate diagnostic** (Q11 — Layer or Storyteller pre-redaction?) — answer this before the publish-gate fix.
4. **Any spec questions or technical risks the directives raise** — VPS or Charlie will resolve.

The build is in extraordinary shape on craft. The Day-5 reframe makes it a fan engagement product first and a demo second. The demo will follow naturally from a fan's flow through the product — that's Charlie's strategic call and it's the right one. Spend the schedule slack building the version of itself the spec promised, plus the fan-engagement layer the contest brief asked for.

---

## Appendix — Decision and lesson cross-reference

All decisions and lessons cited above live in `Docs/VPS/VPS-HANDOFF.md` Sections 5 and 8.

**Decisions referenced:**
- VPS-DEC-006, 008 — original seed prompt + organic-anchor decisions
- VPS-DEC-027, 028 — Day 8 evening soft-rank backstop; Wire pre-seed on first paint
- VPS-DEC-029, 030 — Devpost text outline timing; seed prompt removed from demo video
- VPS-DEC-033 — encouraged temporal phrasing (first / next / newest / earliest)
- VPS-DEC-034 — daily Devpost Updates / Discussions monitor
- VPS-DEC-035 — establishing shot of front door at 0:05–0:10
- VPS-DEC-036 — Devpost text description fan-centric opener (locked text)
- VPS-DEC-037 — GCP console / AI Studio / code shot in demo
- VPS-DEC-038 — current `/floor` renamed to `/field`; new `/floor` = agent graph
- VPS-DEC-039 — `/publish-gate` aggregation fix + demonstration redaction story
- VPS-DEC-040 — kicker/dek/hero-card homepage rejected
- VPS-DEC-041 — fan-engagement front door (replaces VPS-DEC-040's alternative)
- VPS-DEC-042 — Map and Field as discovery siblings, not substitutes
- VPS-DEC-043 — `/story` index facets (sport, era, type)
- VPS-DEC-044 — Broadcast autoplay with obvious mute

**Lessons referenced:**
- Lesson 19 — audit against Constitution AND contest brief separately
- Lesson 20 — beautiful craft can move past spec without anyone noticing
- Lesson 21 — 0/0/0 is the failure mode of well-disciplined compliance
- Lesson 22 — HoE intuition on UX problem is usually right; their solution may not be
- Lesson 23 — live-URL first-paint is the demo video's epilogue
- Lesson 24 — vision narrative was written for the demo, not the product; Constitution wins
- Lesson 25 — a discovery surface's bias becomes a feature when sibling surfaces exist
