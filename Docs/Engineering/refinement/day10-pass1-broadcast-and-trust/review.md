---
title: Day 10 — Pass 1 — Floor Pass 2 + Broadcast + Publish Gate (the room is alive)
date: 2026-05-05
author: HoE
viewport_captured: 1440×900 (laptop)
routes_captured:
  - / (LIVE SSE STREAMING — demo moment #1 lit ✅)
  - /floor (constellation, settled, 4/5 labels visible)
  - /story/fixture-mount-pleasant (Broadcast page — moment #4 ✅)
  - /publish-gate (audit panel — moment #5 ✅)
---

# Day 10 — Pass 1 — The room is alive

This is the day the room woke up. Three parallel workers shipped clean diffs (Floor Pass-2, Broadcast page, Publish Gate trust panel), the Firestore composite index landed, and the live SSE stream now drives `/` with real wire events from the agent backend. Four of the five demo moments are now landing.

## What's live (verified visually at 1440×900)

### `/` — The Wire (live)

Live wire events stream through the canonical `<WireRow />` component. Captured at 14:27–23:21 timestamps, multiple agents visible: **Editor** (gold timestamp DECISION rows), **Investigator** (THINKING rows in italic Lora), **Scout Desk** with **HOMETOWN SCOUT** sub-agent treatment, **Storyteller**. The `[NIL: Nr/Na]` mono badge renders inline after timestamps when NIL state is non-zero (e.g., `[NIL: 3r/0a]`).

**Demo moment #1 ("the room is alive") — LIVES.**

### `/floor` — Constellation (Pass 2)

Massive composition improvement. Anchor triangle holds (Lake Placid upper-third, Chula Vista bottom-center, Colorado Springs right-of-center). Brightness contrast lands: anchors at full saturation, low-HND nodes at 0.4 alpha, halos visibly glowing. **4 of 5 labels visible** at 1440×900: PARK CITY, LAKE PLACID, CHULA VISTA, COLORADO SPRINGS (HOUSTON is in the upper-left cluster). Tracked-small-cap mono labels in gold-warm/60.

Force config (final): `forceManyBody.strength(-240)`, `forceCollide.radius(r+18)`, `forceX/Y(0.02)` replacing `forceCenter`, `forceLink.distance(100).strength(0.16)`. Mount stagger 1500ms total — anchors first 150ms, then non-anchors HND-descending.

### `/story/fixture-mount-pleasant` — Broadcast page

The hero is a documentary cold open. Display-xl Playfair _"A small town builds a generation."_ left-aligned. Italic Lora dek: _"Eight thousand five hundred people. A wrestling room older than most of its kids. And a quiet pipeline that keeps sending its newest Olympian to the Games."_ Tracked-small-cap kicker `PUBLISHED · MOUNT PLEASANT · IOWA · 13:43:25`. Compression-factor 0.25 hero CTA implemented as opacity 0→1 (800ms) + scale 1.05→1.00 (2s) with room cubic-bezier.

Sticky audio bar: hand-drawn 22×22 SVG play triangle, hairline progress track, mono `00:00 / 02:18`, `NARRATION · ALGENIB` caption — restrained, editorial, no shadcn / no material UI.

Body: drop-cap "T" in gold Playfair, Inter cream prose with the wrestling-room paragraph hitting hard ("The mats have been replaced. The lights have been replaced. The roof has been replaced twice. The room has not."). Pull-quote in italic Lora framed by hairlines: _"Eight Olympians and Paralympians from a county of twenty thousand. The pattern stopped looking like luck a long time ago."_

Verified-claim ribbons: hairline-only editorial table with mono claim slug, body claim text, mono source citation. Publish Gate footer: `[NIL: 2r/1a] · 14 claims checked · NIL Redaction Layer passed · Publish Gate cleared` + `Published 2026-05-05 13:43:25 UTC · Story ID: fixture-mount-pleasant`.

**Auto-DQ scan: clean.** Every proper noun in body prose audited. Zero athlete names.

**Demo moment #4 ("Broadcast lands emotionally") — LIVES.**

### `/publish-gate` — Trust panel

`PUBLISH GATE · NIL REDACTION LAYER · AUDIT` kicker. Display-md Playfair _"What the room caught."_ Italic Lora dek _"Every claim, every redaction, every name disambiguated. The room shows its work."_

Aggregate stats strip (4 columns): **12 claims checked**, **3 redactions performed**, **0 disambiguation hits**, **9 / 0 cleared / blocked** — these are derived from the live Firestore wire_events plus fixture-supplemented DISAMBIGUATED/RETURNED rows. The header tag `live + fixture · mixed` honestly labels provenance.

Recent decisions feed shows real wire events: _"IHSA pipeline confirmed. pulling geographic data for Champa…"_ → PASS, _"hold on — checking IHSA Road to Champaign high school to …"_ → PASS, with timestamps in mono and italic Lora reasons.

The marquee — **Disambiguation Trace** — renders Mount Pleasant as the example with the ambiguous span underlined gold-warm, four steps each with a vertical hairline rule (surface match → context vector → candidate ranking → resolution), `[athlete:A]` / `[athlete:B]` placeholder tokens (never a real athlete name), and the cleared sentence in italic. Footer: `athlete_registry: 11,188 entries · last_updated: 2026-05-05 · matcher: aho-corasick`.

**Demo moment #5 ("Publish Gate proves trust") — LIVES.**

## Demo-moment scoreboard

| # | Moment | Status |
|---|--------|--------|
| 1 | The room is alive | ✅ Live SSE streaming on `/` |
| 2 | Agents truly agentic | ✅ Backend complete; visible on `/` in real time |
| 3 | Equity Editor caused the anchor story | ⚠️  Pulse infrastructure exists on Floor; live data hasn't shown an Equity Editor intervention yet (need to seed one) |
| 4 | Broadcast lands emotionally | ✅ `/story/fixture-mount-pleasant` |
| 5 | Publish Gate proves trust | ✅ `/publish-gate` |

## Critical regression to flag

@charlie **R1 — NIL Layer over-redaction.** The live wire feed shows the Day-3 over-redaction bug back: `[redacted]la [redacted]ta` (Chula Vista) and `[redacted]ad acquired` (Lead). The Day-7 disambiguation pass either isn't being applied to message text on emit, or these specific events were written before the fix landed and never got rewritten. Two paths to investigate:
1. Is `agents/wire/emit.py` invoking the full disambiguation Layer on every emit, or only the surface-match Layer?
2. Are the offending events from before the Day-7 patch deployed (timestamps suggest yes — events from 2026-05-04T16:10)?

Either way, this needs a **Day-11 priority fix** before submission. The Disambiguation Trace on `/publish-gate` is selling a promise the live wire is currently not keeping.

## Open questions

@charlie **D1 — Floor: persistent upper-left cluster.** Even after Pass 2 force tuning, ~25 of 58 nodes still bunch in the upper-left. Worker E suggested charge `-200` if `-240` distorts on smaller viewports; we may need `-280` instead at 1440×900. One more tuning pass would be cheap.

@charlie **D2 — Floor header z-index.** "THE FLOOR" header is being clipped by a node at canvas top-left. 1-line CSS fix (header `z-20`, canvas `z-0`).

@charlie **D3 — Equity Editor demo seed.** To land moment #3, we need at least one Equity Editor INTERVENTION event in Firestore so the agitos-red pulse fires on a Floor node and the Wire shows the intervention. Want me to author a seed script that writes 3-4 demo wire_events covering an EE intervention, or trigger via probe_full_chain.py with the right prompt?

@charlie **D4 — Hero image asset.** `/story/fixture-mount-pleasant` currently uses a CSS gradient as the hero. The visualizer pipeline (Day-7) generates real hero images via Nano Banana Pro but timed out at 120s. Options for demo day:
  - (a) Pre-generate 3 demo hero images now (one for fixture-mount-pleasant, two more for variety) and serve from `/web/public/fixture/heroes/*.png`
  - (b) Keep the gradient — it's editorial and reads well at 1440
  - I lean (a). The hero image is the documentary cold open's anchor frame.

@charlie **D5 — Narration audio asset.** Same pattern — `/web/public/fixture/narration-placeholder.mp3` doesn't exist. AudioBar degrades gracefully (button inert) but for demo we want one real narration to play. Want me to call the Algenib TTS pipeline once and save the output?

@charlie **D6 — Sticky audio bar background.** Worker F used `bg-navy-deep/95 backdrop-blur-[2px]` — confirms acceptable per design-system.md §7? It's whisper-thin but technically uses the glassmorphism pattern the kill list excludes. I think the 2px is restrained enough; flag if you want it dropped to a solid bg-navy-deep.

@charlie **D7 — Multi-day timestamps in wire feed.** The live feed at `/` shows events with timestamps from 2026-05-04, 2026-05-05, and 2025-12 (sort order is `timestamp asc`, so all historical data is interleaved). For demo, we probably want only "today's room" — last hour or last 50 events. Want me to add a `where('timestamp', '>=', oneHourAgo)` clause to the SSE bridge live query?

## What's frozen for submission

- All 11 design tokens, 9 type-scale entries, room cubic-bezier
- WireRow variants (8) + sub-scout treatment + NIL inline badge
- Counter math (UTC-midnight day-diff)
- Equity Editor no-apology rule + test guarding it
- Floor force config (subject to D1 if you want a tweak)
- Broadcast page structure (subject to D4/D5 asset adds)

## Files added in Day 10

```
web/components/Floor.tsx          324 → 441 LOC
web/lib/floor-fixture.ts          (anchor coords rebalanced)
web/components/BroadcastPage.tsx  216 LOC (new)
web/components/AudioBar.tsx       151 LOC (new)
web/components/VerifiedClaims.tsx  75 LOC (new)
web/lib/story-fixture.ts           87 LOC (new)
web/app/story/[id]/page.tsx        62 LOC (new)
web/app/story/[id]/loading.tsx     16 LOC (new)
web/app/story/[id]/not-found.tsx   25 LOC (new)
web/app/story/page.tsx             64 LOC (new)
web/components/PublishGatePanel.tsx       203 LOC (new)
web/components/DisambiguationTrace.tsx    125 LOC (new)
web/lib/publish-gate-fixture.ts            93 LOC (new)
web/app/publish-gate/page.tsx              13 LOC (new)
web/app/api/publish-gate/recent/route.ts  122 LOC (new)
```

Plus: Firestore composite index `wire_events: mode + timestamp` (READY).

## Day 11 (suggested last-day scope)

1. **Fix R1 NIL over-redaction** — first task, blocking. Check that `agents/wire/emit.py` applies full disambiguation, OR backfill the offending wire events to use the disambiguated payload.
2. **Seed Equity Editor intervention** (D3) — at least one EE event in Firestore so demo moment #3 lights up.
3. **Generate hero image + narration assets** (D4 + D5) — one full asset set for `fixture-mount-pleasant`.
4. **Wire feed time-window** (D7) — one-hour window in SSE bridge.
5. **Floor tuning + z-index** (D1 + D2).
6. **Demo recording rehearsal** — record 2-3 takes against `/`, `/floor`, `/story/fixture-mount-pleasant`, `/publish-gate` showing the room from cold-start to broadcast.
7. **Apache 2.0 license badge check** — verify the GitHub About sidebar still has it.
8. **Submission package** — README, screenshots, video, links.

— HoE
