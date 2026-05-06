---
title: Day 8 — Pass 1 — The Wire (refinement review)
date: 2026-05-02
author: HoE
viewport_captured: 1440×900 (laptop) — 1920×1080 capture deferred to Pass 2
routes_captured:
  - /fixture/wire (top, middle, bottom)
  - /fixture (color tokens, type scale)
  - / (root Wire placeholder)
---

# Day 8 — Pass 1 — The Wire

This is the first refinement pass per `design-system.md` §11. Three workers (A/B/C) shipped the foundation: token layer, `<WireRow />` component with all 8 variants, and the SSE stream client. The fixture pages render. Pixels are on the screen.

What follows is my own review (HoE), and a list of `@charlie` tags where I want your read before Pass 2.

## What's working (no decisions needed)

**Type voice.** The display-xl Playfair Display specimen — _"A small town builds a generation."_ — reads exactly like the editorial promise we wrote in `design-system.md` §1. Generous, confident, cinematic. The italic-md Lora dek lines underneath the display tier do the editorial follow-through. This is the look I'd want on a print broadsheet about Team USA. We did not converge on Inter-as-display.

**Color discipline.** All 11 tokens render as locked. Navy-deep page, gold-warm hairline accents, agitos-red reserved for Equity Editor only. No purple gradients, no shadcn cards, no chat bubbles. The "AI slop" kill list in §7 held.

**Wire row hierarchy.** The three-tier read works: mono timestamp + italic agent name + tracked-small-cap caption tag in the right gutter, hairline rule, body underneath. Variants are legible at a glance:
- DECISION rows: gold timestamp + medium-weight body (Editor "Going with Mount Pleasant. Investigator, 90 seconds.")
- INTERVENTION rows: 2px agitos-red left edge + container frame (Equity Editor "Feed drift detected.")
- THINKING rows: caption right-aligned, body recessed, no decoration
- MILESTONE rows: instant arrival, caption tag, no animation
- Sub-scout treatment: tracked-small-cap sub-name beneath parent agent (CINDERELLA SCOUT / COMEBACK SCOUT / HOMETOWN SCOUT / ECHO SCOUT under Scout Desk), 28px body indent

**NIL trust signal.** The Publish Gate row carries `[NIL: 2r/1a]` inline in mono after the timestamp, between the timestamp and the agent name. Reads as a wire indicator — like a slug — not as a UI badge. This is the editorial signal Charlie asked for: the room shows you it caught the redactions, in-line, the way an old wire service would.

**Footer attribution.** "WIRE ROW SPEC · DESIGN-SYSTEM.MD §4 + §8 · BUILD_SPEC §6" in tracked small caps reads as masthead-style. Sets the tone for what this surface is.

**Top-right counter.** "800 days to LA28" in JetBrains Mono cream-dim sits in the upper-right corner of every page. Quiet, ambient, anchors the project to its deadline. Not in the way.

## Open questions for Charlie

@charlie **Q1 — Caption tag placement.** Right now the caption tag (THINKING / MILESTONE / DECISION / INTERVENTION) lives in the right gutter. It reads cleanly but it visually competes with the agent name in the left column. Two alternates:
  - (a) keep it as-is — right gutter, fully aligned
  - (b) drop it under the agent name in the same line as the sub-scout treatment, so all metadata stacks left and the right gutter is reserved for things like NIL badges
  - I lean (a) — it gives the row a "wire ticker" cadence and the right gutter never disappears. But happy to try (b) next pass if you want it more compressed.

@charlie **Q2 — Sub-scout indent depth.** Current indent is 28px (matches §4.2 in design-system.md). On a 1440 viewport it reads cleanly, but on smaller laptops it could compress to 20px. Is the current depth right, or do you want me to bump it to 32–36px to make the sub-scout grouping even more pronounced?

@charlie **Q3 — INTERVENTION container frame.** The Equity Editor row uses both a 2px agitos-red left edge AND a thin frame around the entire row (cream-dim border). That's two visual cues to say "the room intervened." It's strong, maybe too strong if interventions are common. Two options:
  - (a) keep both — the intervention is meant to be an event
  - (b) drop the outer frame, keep only the red left edge — same meaning, less visual noise
  - I lean (a) for now because Equity Editor interventions are rare (once per story, max) and the moment should hit.

@charlie **Q4 — Equity Editor headline copy ban.** The body of the Equity Editor row in the fixture says _"Feed drift detected. Last 4 places Olympic-heavy. Promoting Paralympic-anchored lead next."_ That's the literal voice we want — coverage-equity language, never apology. Want me to lock this voice as a constraint in `prompts/equity_editor.md` (it's already there) and add a fixture-driven test that fails if Equity Editor's output starts with "Sorry," "I apologize," or a hedge?

@charlie **Q5 — Top-right counter precision.** "800 days to LA28" right now ticks at midnight UTC (today is 2026-05-02 → LA28 opens 2028-07-14 → 803 days, displaying 800 because we have a day-flooring bug to fix in the timer). Want me to fix the off-by-3 in Pass 2?

@charlie **Q6 — Root route placeholder.** `/` currently shows _"The room is loading."_ in italic Lora with a body explaining what `<WireRow />` will populate. It's an honest placeholder until Day 9 wires the live SSE stream. Want me to leave it as-is for the demo recording, or replace it with the static fixture content as a fallback so a recording never lands on placeholder copy?

@charlie **Q7 — Display-xl size on laptop.** "The Storyteller's Room" headline at 96px on a 1440 viewport is generous but eats two-thirds of the page. On the project hero (Day 9) we may want it at 80px. Want me to add a `display-hero` token at 80/72/-0.02em, or keep display-xl as the project's North Star?

## Things I noticed but did NOT change

- **Next.js dev indicator (small "N" pill in the lower-left)** is dev-only, never ships. Ignore in screenshots.
- **Storyteller THINKING row** is showing the THINKING caption on the right. Spec said no caption on thinking rows from the Storyteller — this is a fixture data choice, not a component bug. Will fix in fixture if Q1 lands on (a).
- **Dim background vignette** at the corners on `/` is from a single radial-gradient layer in `app/globals.css`. Subtle. Reads as atmosphere. Not a bug.

## What's next

Pass 2 will be driven by your answers above. My pre-commitments:
1. If Q1 → (a), keep caption-right; if (b), refactor `<WireRow />` to stack metadata left.
2. Fix the top-right counter off-by-3 regardless of Q5 (it's a bug).
3. Re-capture at 1920×1080 (recording resolution) once the answers above are in.
4. Wire the live SSE stream into `/` (Day 9) only after this surface reads right at fixture.

Refinement directory: `Docs/Engineering/refinement/day8-pass1-wire/`
Branch: stay on `main` (no PR yet — this is fixture-only, no production code path).

— HoE
