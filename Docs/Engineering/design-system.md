# Design System — The Storyteller's Room

**Status:** v1.0 (Day-8 baseline). LIVING DOCUMENT — refined against the running build.
**Owner:** Charlie + HoE (collaborative refinement; see §11).
**Read order:** every frontend worker reads this AFTER `CLAUDE.md` and `BUILD_SPEC.md §10–§11`, BEFORE writing any code.

> _"NBC Olympic broadcast control room cross-bred with a Times print newsroom — editorial gravity, never SaaS, never chat."_

This document is the **canonical brand-consistency artifact** for the frontend. Every worker that touches `/web/`, Tailwind config, components, animations, or any visual surface reads this and aligns. Per the Anthropic Claude Design positioning that informed this build's UI approach: the moat is **fidelity to a defined design system, not bold one-off aesthetic choices**.

---

## 1. Aesthetic position (one sentence each)

| Surface | The visual archetype |
|---|---|
| **The Wire** | NBC lower-third nameplate, ticking. A broadcast graphic streaming downward. Not a chat. |
| **The Floor** | Control-room blueprint. Agent nodes on a navy field, gold particle handoffs along curved Bezier edges. |
| **The Broadcast** | Cinematic editorial page. Full-bleed hero, character-by-character headline, gold-underline sentence highlight that grows with the spoken word. |

These three surfaces share the same tokens but read as **three distinct rooms in the same building** — different camera angles on the same broadcast.

---

## 2. Color tokens (LOCKED)

```css
/* Navy field — the room's atmosphere */
--navy-deep:    #0A1428    /* page background, hero darken overlay */
--navy-mid:     #1A2740    /* panels, lower thirds, Floor node fill */
--navy-light:   #2C3E5A    /* hairline dividers, subtle borders */

/* Gold — the editorial mark */
--gold-warm:    #D4A84A    /* hairline rules, headlines, particle streaks */
--gold-deep:    #A8842F    /* hover states, active sentence underline */

/* Cream / parchment — body weight on navy */
--cream:        #F5EFE0    /* primary body text on navy */
--parchment:    #E8DDC4    /* Investigator agent color signature */

/* Accent */
--agitos-red:   #C8102E    /* Equity Editor — NEVER the actual logo */
--slate:        #5A6878    /* secondary text, tool-call cards */

/* Wire-specific */
--wire-text:    #B8C4D6    /* Wire body text — slightly desaturated cream */
--wire-time:    #7A8AA0    /* Wire timestamps in mono */
```

### Forbidden palette choices

- **No purple gradients.** Anywhere. (The single most "AI slop" tell.)
- **No actual Olympic ring colors used together** (red+blue+yellow+green+black). The Wire's Agitos-red accent stands alone.
- **No bright consumer-app palette** (no #007AFF iOS blue, no #1DA1F2 Twitter blue, no Stripe purple, no Tailwind default `bg-blue-500`).
- **No light mode.** The room is dark. Always.

---

## 3. Typography (LOCKED)

```css
--display:  "Playfair Display", "Times New Roman", serif       /* headlines, broadcast titles */
--italic:   "Lora", "Times New Roman", serif                   /* agent names, dek, italic emphasis */
--body:     "Inter", -apple-system, sans-serif                 /* Wire body, UI controls */
--mono:     "JetBrains Mono", "Menlo", monospace               /* timestamps, IDs, status */
```

Loaded via Next.js `next/font/google` with `display: 'block'` (NO FOIT — better to wait for the typeface than show fallback). Subset to Latin + numbers.

### Type scale

```
display-xl   72-96px   Playfair Display   Broadcast headlines
display-lg   48-64px   Playfair Display   Hero text, section heads
display-md   32-40px   Playfair Display   Subhead in Broadcast body
italic-md    20-24px   Lora italic        Dek, agent names (bigger contexts)
italic-sm    14-16px   Lora italic        Wire row agent name
body-md      16-18px   Inter              Wire body, Broadcast paragraph
body-sm      13-14px   Inter              Tool-call cards, secondary
caption      11-12px   Inter (tracked)    Small caps tags ("decision", "milestone")
mono-sm      12-13px   JetBrains Mono     Wire timestamps
```

### Forbidden type choices

- **No Inter as display.** Inter is body-only. Display = Playfair Display.
- **No system fonts.** No `-apple-system, sans-serif` as the primary stack. The fonts above are the design.
- **No Roboto, no Arial, no Helvetica, no Open Sans.** None of the AI-generic standards.
- **No Space Grotesk, no Geist, no Satoshi.** None of the AI-default "designer" picks either.
- **No Comic Sans.** (Self-evident. Listed for completeness.)
- **No emoji.** None. Anywhere. The Wire ban is total per CONSTITUTION §11.

---

## 4. Spatial composition

### The Wire

- Row min-height: 56px (room to read; the 4-8s pacing wants generous leading).
- Three-tier hierarchy per row:
  ```
  ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
    [mono-sm time] │ [italic-sm agent]                [caption tag]
                    ───── gold hairline 1px ──────
                    [body-md message text on cream-on-navy]
  └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  ```
- Sub-agents (Cinderella / Comeback / Hometown / Echo Scouts) recess: indent 24px, agent name in tracked-out small caps under "Scout Desk" parent.
- Scroll: smooth ease-out, 300ms per new event arriving.
- New event entry: subtle blur-fade-in over 200ms; older events compress slightly (5px translate-up) as new ones arrive.
- **Forbidden Wire patterns:** no chat bubbles, no avatars, no "User: / Assistant:" framing, no Discord/Slack-style message clusters, no reactions, no thread replies.

### The Floor

- D3 force on Canvas (per BUILD_SPEC §9.6).
- Agent nodes: **labeled rectangles** (not circles, not hexagons — both feel infographic). Each: 96×40px, navy-mid fill, 1px gold-warm border, agent name in italic-sm centered.
- Edges: curved Bezier between connected nodes. Idle edges: 1px navy-light. Active handoff: gold-warm pulse traveling along the curve over 800ms with motion-blur trail.
- Equity Editor's node: agitos-red corner accent (4px triangle in upper-right). When intervening: full node border flashes red over 600ms.
- Tool-call cards: lower-right stack, 240px wide, navy-mid fill, single gold-warm hairline rule on top, mono-sm content. Cards persist 3s after completion then fade.

### The Broadcast

- Full-bleed hero image (16:9 aspect at top). Subject ALWAYS a place / landscape / community / facility.
- Headline: display-xl Playfair Display, character-by-character reveal at ~30ms/char.
- Dek: italic-md Lora, restrained, single sentence.
- Body: body-md Inter, generous leading (1.7x line-height), max-width 680px (editorial measure — not container-fluid).
- Hometown panel: slides in from left over 600ms when Narrator says the place name. Stylized map illustration + place name + 50-75 word portrait.
- Historical Echo panel: slides in from right over 600ms when Narrator hits the era reference. Side-by-side era illustrations.
- Music bed at -25dB always. Mixed below the Narrator at 0dB reference.

---

## 5. Motion + animation

### Principles

1. **Audio is the master clock.** Visual choreography on the Broadcast page anchors to `audioContext.currentTime`, not `setTimeout` or Framer delays. Audio decode varies; visual timers don't. Visuals chase audio.
2. **Pacing is meditative, not snappy.** The Wire is 4-8s per event ambient. Curtain rise is 1.5-2.0s. Panel reveals are 600ms. Snappy = consumer-app. We are NBC.
3. **Easing: cubic-bezier(0.32, 0.72, 0, 1).** A custom curve — slower start, faster middle, gentle landing. Felt-time precision. NOT `ease-out` (Material Design's signature; too snappy for our register).
4. **Reduced motion respected.** `prefers-reduced-motion` disables Wire scroll animation, Ken Burns, headline typewriter, Floor particles. Curtain rise instant-cuts. Narration still plays.

### The curtain rise (BUILD_SPEC §7.1, anchored to audio)

```
t=0.0s   Wire blurs to 0.4 opacity; Wire ambient ducks to -20dB
t=0.2s   Screen darkens (overlay fade 400ms)
t=0.4s   Hero fade-in begins (800ms; subtle scale 1.0 → 1.04 Ken Burns)
t=0.8s   Narrator breath sample audible (~300ms)
t=1.0s   First narration word lands
t=1.2s   Headline character-by-character reveal (~30ms/char)
t=1.5s   Music bed enters at -25dB under narration
```

Implementation: schedule audio events absolutely on `audioContext.currentTime + 0.05`. Visuals use Framer Motion's `useAnimate` orchestrated sequence pegged to the same `t0`. Visual-only beats (overlay, blur) can stay on Framer's timer; audio-paired beats use the audio clock.

### Sentence highlight (Broadcast page)

**Gold underline that grows left-to-right** as the Narrator speaks each sentence — NOT a background fill (background fill = karaoke = wrong register). The underline is a 2px gold-warm hairline that draws across the active sentence's baseline, anchored to AudioContext.currentTime. When the sentence ends, it stays painted (history accumulates underneath the manuscript) and the next sentence starts.

```
"The town's first Olympian came in 1964."
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ← gold hairline grows with speech
```

After narration ends, the entire body text reads as a fully-underlined manuscript — like a librarian's annotation pass.

### Streaming cognition speed (Wire)

Per `data/streaming_profiles.json`:
- Editor: 50 chars/sec (fast, confident; jitter 0.15)
- Cinderella Scout: 25 cps (hesitant; mid-message-pause-chance 0.45)
- Echo Scout: 15 cps (slowest, most cryptic; mid-pause 0.55)
- Equity Editor: `arrival_style='instant'` — interventions arrive whole, never stream
- Investigator: 35 cps (precise, source-driven)

Each thinking message types out at the agent's rate; mid-message pauses (em-dash beats of 150-600ms) sprinkle in by chance. Milestones appear instant.

---

## 6. Visual details

- **Backgrounds**: layered. Base navy-deep + a subtle film-grain noise texture (5% opacity, monochrome) + a barely-visible vignette darkening corners (15%). NOT solid flat color.
- **Gold hairlines**: always 1px (or 2px for active sentence underline). Never thicker.
- **Shadows**: rare. Used only on the Broadcast page hero card and the tool-call cards. Subtle: `0 8px 32px rgba(0,0,0,0.4)`. Never the SaaS "card shadow" of Material Design.
- **Borders**: hairline only. 1px gold-warm or 1px navy-light. No 2-4px chunky borders.
- **Cursors**: default. NO custom cursor (a "designer" tell that always reads as showing off).
- **Icons**: minimal. The room runs on words; if we need icons, use Phosphor at thin weight, gold-warm color. NOT Lucide (over-deployed in 2025-2026 AI tooling), NOT Heroicons (signals "Tailwind starter").

---

## 7. The "AI slop to avoid" list

Anything on this list, reject. Hard rules.

| Visual pattern | Why we reject it |
|---|---|
| Purple gradients on white | The single most overused AI-generated UI tell |
| `Inter` as display font | Inter is body. Display = Playfair Display. |
| `Space Grotesk` as anything | The default "designer" pick for AI tools — converged everywhere |
| Light mode | The room is meditative + Olympic-broadcast — dark always |
| Chat bubbles | The Wire is a broadcast graphic, not a messaging UI |
| Avatars (circular profile pics) | We use lower-third nameplates; agents are not people |
| `bg-blue-500` / iOS blue | Consumer-app palette; we're navy + gold |
| Material Design "card shadow" | SaaS dashboard tell |
| Lucide icons | Over-deployed in 2026 AI tooling |
| Heroicons | "Tailwind starter" signal |
| Spinners (`animate-spin`) | Per CONSTITUTION §11 — agents visibly think, never spin |
| Emoji | Total ban per CONSTITUTION §5 (Wire) and §11 (visual) |
| Glassmorphism / frosted blur | 2020-era trend; not editorial |
| Neumorphism | Same |
| Tailwind default `font-sans` stack | We override globally to Inter |
| Gradient borders | Decorative AI tell |
| Hover-scale buttons (`hover:scale-105`) | SaaS tell |
| Toast notifications top-right | Consumer-app tell |
| Hamburger menus | We have three views, not a nav tree |

---

## 8. Component patterns

### `<WireRow>` — the canonical broadcast graphic

The single most opinionated component. Every Wire event renders as one of these. Three-tier hierarchy:

1. **Header row**: mono-sm timestamp + italic-sm agent name + caption tag
2. **Hairline rule**: 1px gold-warm, 80% width, gold-deep on dim mode
3. **Body**: body-md cream-on-navy message text

Variants:
- `agent="editor"` — gold-warm timestamp accent
- `agent="equity_editor"` — agitos-red corner accent on the row left edge
- `sub_agent="cinderella"|"comeback"|"hometown"|"echo"` — recessed indent + tracked small caps under parent
- `message_type="thinking"` — typewriter effect at agent's streaming profile
- `message_type="milestone"` — instant render
- `message_type="intervention"` — instant render + 600ms gold-warm border pulse + agitos-red corner if Equity
- `message_type="decision"` — instant render + bold body text

### `<FloorAgentNode>` — labeled rectangle

96×40px, navy-mid fill, 1px gold-warm border, italic-sm agent name centered. Status dot (4px filled circle) lower-right: idle = gold-warm dim, thinking = gold-warm pulse, error = agitos-red.

### `<BroadcastHero>` — full-bleed cinematic header

Full-width image, 16:9 aspect, Ken Burns scale 1.0 → 1.04 over 90s (the narration length). Headline overlaid bottom-left, display-xl Playfair Display, character-by-character reveal at narration start. Dek below in italic-md Lora.

### `<EvidenceDrawer>` — collapsible audit log

Bottom-of-Broadcast collapsible panel. When opened: shows the 7 Publish Gate sub-stages as a horizontal stripe. Each sub-stage: a navy-mid block with the count summary in mono-sm + a passed/failed dot. Tap to expand a sub-stage's details (NIL Layer's redacted-counts visible here is the demo's trust-signal moment).

---

## 9. Accessibility (don't compromise the aesthetic by ignoring this)

- `prefers-reduced-motion`: disables Wire scroll animation, Ken Burns, headline typewriter, Floor particles, sentence-highlight underline animation. Narration still plays; sentence highlight becomes instant on word boundaries.
- WebVTT captions: derived from the Narrator's word-timing data. Track attached to the audio element as `<track kind="captions">`. Default off; toggle in lower-right.
- Color contrast: cream on navy-deep is 11.2:1 (AAA). Gold-warm on navy-deep is 6.4:1 (AA Large). Both clear AAA / AA respectively for body text and headlines.
- Keyboard nav: all interactive elements (the live URL CTA input, the Evidence Drawer toggle, the play/pause control) reachable via `Tab`; visible focus rings (2px gold-warm, 4px offset).
- Screen reader: agents have `role="article"` per Wire row with `aria-label="{agent name} — {message type} — {timestamp}"`. The Broadcast hero image has descriptive alt text generated from the place_type + environmental_cue.

---

## 10. Build cadence (Day-8 plan)

Per the Anthropic Claude Design positioning: **first output is a starting point, not a finished artifact**. Every Day-8 step is followed by a refinement pass.

**Day-8 morning (worker fan-out):**
1. **Worker A**: Next.js 15 skeleton + Tailwind config + the four Google Fonts wired via `next/font/google` + the locked tokens above as CSS variables + a `<Layout>` shell.
2. **Worker B**: `<WireRow>` component (static render, no SSE yet) + storybook-style fixture page that renders 8-10 sample rows showcasing every variant (each agent + each message_type + sub-scout indent + Equity intervention).
3. **Worker C**: SSE Route Handler at `/web/app/api/wire/stream/route.ts` — server-side `onSnapshot → SSE` per HOE-DEC-024. Heartbeat every 15s. Last-Event-ID replay on reconnect.

After workers A/B/C land: **HoE refinement pass #1** (per §11 below). I review every diff, run the dev server, take screenshots, hand-tune spacing/easing/type-scale.

**Day-8 afternoon:**
4. **Worker D**: Wire stream renderer that consumes the SSE bridge, calls `<WireRow>` for each event, applies streaming-profile-driven typing effect.
5. **Worker E**: `<Layout>` polish — film-grain background, vignette, days-to-LA28 counter (no marketing copy, no welcome banner), live URL CTA seed-prompt input.

**HoE refinement pass #2** end of Day-8. We talk through what feels right and what doesn't. (See §11.)

**Day-9:**
- Floor (D3 Canvas, particle handoffs, tool-call cards)
- Broadcast (curtain rise + hero + headline reveal + sentence highlight + Hometown panel + Historical Echo panel + Evidence Drawer)
- Audio (AudioContext bus, three GainNodes, NarrationManifest sync)
- HoE refinement pass #3

**Day-10**: Recording.

---

## 11. The Charlie + HoE refinement loop

This is the load-bearing collaboration mechanism. The Anthropic article framed it as "comment inline on specific elements, edit text directly, or use adjustment knobs to tweak spacing, color, and layout live." Adapted for our build:

### After each worker's commit lands, the HoE will:

1. **Boot the dev server** (`npm run dev` in `/web`) and capture screenshots of every relevant view at desktop resolution (1440×900) and the demo recording resolution (1920×1080).
2. **Drop the screenshots into `/Docs/Engineering/refinement/dayN-passM/`** with filenames like `wire-row-editor-decision.png`, `floor-idle.png`, `broadcast-curtain-rise-t0.4s.png`.
3. **Write a short review note** alongside the screenshots in `Docs/Engineering/refinement/dayN-passM/review.md` flagging:
   - What works
   - What feels off (specific: "the gold hairline reads too thick at 16px viewport"; "the Editor's caption tag is too tight against the agent name")
   - Specific tweaks to try
4. **Tag you in the review note** — `@charlie: question on the sentence-highlight underline weight — 2px or 1px?` style.
5. **Push the screenshots + review** to a `refinement/` git branch (or a draft PR) so they're easy for you to scroll through.

### Charlie's loop:

1. **Open the screenshots** + the review note.
2. **Comment inline** on `review.md` with `[charlie]` tags — direct edits or notes — or via Slack/text/voice.
3. **Approve refinements OR redirect** — "yes try 1px"; "actually let's go karaoke fill instead of underline"; "the Floor nodes feel cold — warm them up."

### HoE applies:

1. Apply the requested refinements directly (small CSS tweaks) OR spawn a refinement worker for anything substantive.
2. Re-screenshot, re-push, tag again.
3. Iterate until you say "ship it" on each surface.

**Refinement passes are NOT new feature work.** They're meticulous polish. Budget at minimum:
- Day-8 evening: 1 pass on Wire
- Day-9 morning: 1 pass on Floor
- Day-9 afternoon: 1 pass on Broadcast curtain rise
- Day-9 evening: 1 pass on full chain (Wire → Floor → Broadcast click → Broadcast page)

Total: 4 explicit refinement passes between code-landing and demo-recording.

### One-line decisions you'll be asked to make on Day-8

A short list of "answer when ready" calls — I'll batch these and ask up front so I can build to spec without blocking on each:

1. **Sentence highlight on Broadcast**: gold underline grows L→R (editorial — proposed) vs. gold background fade-in (karaoke — easier to read in low-attention demo viewing)?
2. **Wire row gold hairline**: under the agent name (proposed) vs. above it vs. omit and use weight contrast only?
3. **Equity intervention pulse color**: agitos-red border flash (proposed) vs. agitos-red ROW BACKGROUND wash (more attention-grabbing)?
4. **Floor agent node shape**: labeled rectangles (proposed — broadcast graphic) vs. labeled circles (more classic graph)?
5. **Days-to-LA28 counter placement**: top-right under Wire mini-header (proposed) vs. bottom-left as a discrete watermark (less marketing-y)?

I'll tee these up in the Day-8 morning briefing message with my recommendation + the alternative for each.

---

## 12. Refinement loop directory structure

```
Docs/Engineering/refinement/
├── day8-pass1/
│   ├── review.md
│   ├── wire-row-editor-decision.png
│   ├── wire-row-cinderella-thinking.png
│   ├── wire-row-equity-intervention.png
│   ├── wire-row-publish-gate-milestone.png
│   ├── wire-stream-static-fixture.png
│   └── layout-shell-1440.png
├── day8-pass2/
│   └── ...
├── day9-pass1-floor/
└── day9-pass2-broadcast/
```

The refinement directory is **gitignored** for screenshots (PNGs balloon repo size); `review.md` files are committed.

---

## 13. Doc usage

- **For frontend workers**: this doc is your brand-consistency contract. Every component you build references the §2-§4 tokens and §8 component patterns. Any deviation requires HoE approval.
- **For the HoE**: refinement passes per §11 are scheduled, not optional. Budget them in the day-of phasing.
- **For Charlie**: §11.5 ("one-line decisions") and §11 (the refinement loop) are your touch points. The rest is reference.

This doc is editable. As we discover what the Wire actually feels like in motion, what the Broadcast page actually feels like at full curtain rise, this doc absorbs the lessons. Bump version on substantive change.
