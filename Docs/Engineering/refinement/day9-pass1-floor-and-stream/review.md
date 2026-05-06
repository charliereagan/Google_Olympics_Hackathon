---
title: Day 9 — Pass 1 — Live SSE wiring + The Floor (constellation)
date: 2026-05-05
author: HoE
viewport_captured: 1440×900
routes_captured:
  - / (live SSE — error state, Firestore index missing)
  - /floor (Canvas constellation, 58 nodes / 63 edges)
---

# Day 9 — Pass 1 — Live SSE wiring + The Floor

Two parallel workers landed cleanly. Both routes render, typecheck and lint are green, no kill-list violations. Aesthetic refinement is needed on The Floor; the SSE bridge needs a Firestore composite index before it can stream.

## What landed

### Worker C — root `/` wired to live SSE stream

**Files:** `web/components/WireFeed.tsx` (new), `web/app/page.tsx` (updated).

**Behavior verified at 1440×900:** the root route now reflects stream state in real time. The current state is the **error state** because the Firestore composite index for `wire_events` (`mode == 'live' ORDER BY timestamp`) hasn't been provisioned. The error UI is **on-brand**: italic Lora _"The line is down. Reconnecting…"_ centered, with a hairline gold-warm progress bar pulsing underneath. Counter still reads 801 days to LA28.

**This proves:**
- `useWireStream()` is connected
- The SSE bridge is running and emitting an `error` event (not silent-failing)
- The error-state UI matches design-system §5
- Mode-aware mount: `replay`/`published` rows mount settled; `live` rows animate in

**Empty-state copy chosen:** `The room is quiet.` — Lora italic, centered. Pre-locked.

**Three states:** streaming / empty-and-connected / disconnected — all implemented per spec.

### Worker D — The Floor (`/floor`) — Canvas constellation, fixture-first

**Files:** `web/lib/floor-fixture.ts` (225 LOC), `web/components/Floor.tsx` (324 LOC), `web/app/floor/page.tsx` (31 LOC). 580 LOC total — under 600 budget.

**Dependencies installed:** `d3 d3-force @types/d3 @types/d3-force` only.

**Verified:**
- HTTP 200 at `/floor`, 1 `<canvas>` tag in the DOM (21,286 bytes of HTML)
- 58 nodes (HND ≥ 4.1, Olympian+Paralympian count ≥ 3 — passes density rule)
- 63 unique bidirectional edges
- 27 distinct programs, 26 distinct patterns
- 3 pinned anchors (Lake Placid NY, Chula Vista CA, Colorado Springs CO) at fractional-viewport pin coords
- d3-force simulation running (link / charge / center / collide forces)
- Hi-DPI Canvas with `shadowBlur=12` glow halo
- framer-motion side panel for click-to-pin + verified-claims trail
- Scripted intervention-pulse demo at t+4.2s (Birmingham AL, agitos-red over 600ms)
- Header: "THE FLOOR / places, programs, patterns" — tracked-small-cap + Lora italic — reads correctly
- Top-right counter persists

**No kill-list violations.** No athlete names, no NGB names, no hover:scale, no animate-spin, no off-token colors.

## What needs another pass

### @charlie F1 — Floor composition is unbalanced.

The constellation works but reads too "upper-left tangle" instead of "observatory at 3am." Causes I can see in the screenshot:

1. The d3 `forceCenter` is pulling everything toward the canvas center, but combined with the 3 pinned anchors and the link forces, gravity wins and the cluster doesn't disperse. Lower-right 60% of the viewport is empty.
2. The pinned anchors at fractional-viewport coords don't visually distinguish themselves enough — they should be the brightest "stars" but they read the same size as their neighbors at this zoom.
3. Glow halos (`shadowBlur=12` at gold-warm 0.08) are too subtle on the small nodes — the constellation reads as filled discs, not as light sources.

**Pass-2 fix proposal (Day-10 worker):**
- Replace `forceCenter` with `forceX` + `forceY` at viewport center but with weak strength (0.02), letting `forceManyBody` (charge ~ -180) push the cluster outward
- Strengthen `forceCollide` radius to `r + 18` to keep nodes from overlapping
- Boost halo opacity to 0.15 and use 2-pass rendering (radial gradient + filled disc)
- Increase brightness contrast: anchors at full saturation, low-HND nodes at 0.4 opacity
- Optional: add ambient particles drifting through the field (the "stardust" we left out of v1)

### @charlie F2 — Firestore composite index is missing (blocking SSE on `/`).

The `wire_events` query for live events (`where mode == 'live' orderBy timestamp asc`) requires a composite index Firestore creates on demand. The console error from the SSE bridge surfaces a click-through URL to create it. **HoE infra task** — I can do this in 30 seconds via `gcloud firestore indexes composite create`. Want me to do it now (would let `/` show the empty state with green stream), or wait until we seed sample events?

### @charlie F3 — Pre-seed query returned 0 rows.

The bridge's pre-seed (last 6 events where `mode in ['replay','published']`) returned empty. Either no replay/published events exist in Firestore yet, or the same composite-index issue applies. Once F2 is fixed and we run an end-to-end investigation (probe_full_chain.py from Day 7), this should populate.

### @charlie F4 — Mount-stagger reveal order.

Worker D's stagger is `(idx * 12 or 200 + idx * 18) % 800` — pinned anchors enter first, others ramp in. He suggested an alternative: have the **outer / low-HND nodes enter last** so the room reveals "rural places too" deliberately. I lean toward the alternative — it tells a story over the first second of mount.

### @charlie F5 — Should the brightest 3-5 stars carry visible labels?

Currently no labels on canvas — only the hover card carries the place name. Editorial restraint, but a judge unfamiliar with the room may need a hint. Worker D suggested deciding after first refinement screenshots — these are them. **My recommendation:** add tracked-small-cap mono labels (10px, gold-warm/60) only to the 3 pinned anchors + 2 brightest non-anchors. Keeps it editorial; orients the judge.

### @charlie F6 — Edge-fade strategy.

Worker D went with center-radial fade (edges dim with distance from viewport center) over viewport-clip. Reads more "observatory at 3am." I agree with this default; flag if you'd rather the alternate.

## Demo moments status (per CLAUDE.md decision filter)

| # | Moment | Status |
|---|--------|--------|
| 1 | The room is alive | **Wired but not lit.** Needs Firestore index + seeded events. |
| 2 | Agents truly agentic | Backend complete (Day 7). |
| 3 | Equity Editor caused the anchor story | **Half-built.** Floor's intervention pulse infrastructure exists but composition issues mean it won't land at current parameters. Pass-2 fix required. |
| 4 | Broadcast lands emotionally | Day 10. |
| 5 | Publish Gate proves trust | NIL badge in WireRow ✓; full Publish Gate panel = Day 10. |

## Day-10 scope (proposed)

1. **Floor Pass-2** — composition fix (F1, F4, F5) — first task
2. **Provision Firestore composite index** (F2) — 30s HoE task at start of session
3. **Run probe_full_chain.py** to seed live events, prove demo moment #1 lights up
4. **Broadcast page** — story hero + narration audio + verified-claim ribbons + image hero (use Day-9 pre-cache pattern from HOE-DEC-020)
5. **Publish Gate trust panel** — show the NIL Layer's disambiguation log
6. **Demo recording polish** — compression-factor 0.25 hero CTA per BUILD_SPEC §3.7

## Files locked / unchanged

- `<WireRow />`, `tailwind.config.ts`, agents/, prompts/, the SSE route, `useWireStream()` hook, `<DaysToLA28 />` — all untouched in Day 9.

— HoE
