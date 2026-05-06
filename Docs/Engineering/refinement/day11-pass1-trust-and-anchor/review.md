---
title: Day 11 — Pass 1 — NIL forward path verified, EE anchor seed, hero+narration assets, +2 demo stories
date: 2026-05-06
author: HoE
viewport_captured: 1440×900 (laptop)
routes_captured:
  - / (live SSE — Birmingham EE arc visible)
  - /floor (constellation)
  - /story (3-card index)
  - /story/fixture-mount-pleasant (Broadcast — original)
  - /story/fixture-park-city-utah (Broadcast — alpine)
  - /story/fixture-birmingham-alabama (Broadcast — Paralympic-anchored, EE-converged)
  - /publish-gate (audit)
---

# Day 11 — Pass 1 — Trust + Anchor + +2 demo stories

Day 11 closed the Day-10 R1 regression, lit demo moments #3 and #4 with real assets, and added two new Broadcast stories so the published stack reads like a real publication. Five of five demo moments now land at fixture quality. Backend complete since Day 7; frontend complete since Day 11.

## What landed

### R1 — NIL Layer over-redaction

**Root cause:** stale rows only. The forward path (`agents/wire/emit.py:118` calls `nil_layer.scan_wire(...)` synchronously, which routes to `_scan_wire_only` → `_direct_match_and_disambiguate`) was correct as of the Day-7 patch (2026-05-05 15:24 UTC). All 27 over-redacted events in Firestore are pre-Day-7 timestamps. New file `tests/test_emit_full_disambiguation.py` (3 tests, passing) guards the forward path so the regression cannot re-emerge silently.

### D7 — SSE bridge time-window

`web/app/api/wire/stream/route.ts` — added `LIVE_WINDOW_MS = 60 * 60 * 1000` and `where('timestamp', '>=', liveCutoff)` on the live query. The existing `(mode, timestamp)` composite index covers the new compound condition with no new index required. Stale pre-Day-7 over-redacted rows are now invisible to the wire UI.

### D3 — Equity Editor anchor seed

`scripts/seed_equity_editor_demo.py` writes 10 wire events under `investigation_id=demo-equity-edit-001` covering the full Birmingham Equity-Editor-caused arc:

1. Editor THINKING — feed-drift observation
2. Scout Desk / Hometown sub-scout — Birmingham surfacing
3. Investigator THINKING — pulling sources
4. **Equity Editor INTERVENTION** — _"Feed drift detected. Last 4 places Olympic-heavy. Promoting Paralympic-anchored lead next."_ (no-apology rule passing; story_unit_id=`birmingham-al`)
5. Editor DECISION — re-routing
6. Investigator THINKING / MILESTONE
7. Storyteller THINKING
8. Publish Gate MILESTONE
9. Editor MILESTONE — published

Every event routes through `wire.emit()` (not bare `firestore.add`) — NIL Layer ran on each and cleared all ten. Worker rejected an earlier draft of "Story published. Stack updated." (Layer flagged "Story" + "Stack" as athlete surnames) — proof the Layer is fail-closed. Investigation ID is purgeable.

The Floor's `INTERVENTION_NODE_ID = 'birmingham-al'` (`web/lib/floor-fixture.ts:224`) matches the seed's `story_unit_id` — the agitos-red intervention pulse fires on the Birmingham node at t+4.2s after `/floor` mount.

### D4/D5 — Mount Pleasant production assets

- **Hero**: `web/public/fixture/heroes/mount-pleasant.png` — Nano Banana Pro (`gemini-3-pro-image-preview`), 23.0s latency, 1376×768, 1.97 MB. Painterly editorial illustration of an empty wrestling room interior — sun-bleached mat with painted circles, single high window with amber light shaft, jump rope on a nail, bench with stopwatch + leather straps. Zero people, zero faces, zero logos, not photorealistic.
- **Narration**: `web/public/fixture/narration-mount-pleasant.mp3` — Algenib via `gemini-3.1-flash-tts-preview`, 178.72s, 2.15 MB. 33-sentence concatenation with `[short pause]` / `[long pause]` tags applied via the same logic as `agents/narrator/agent.py::_apply_inline_tags`.
- BroadcastPage updated with `<motion.img>` rendering when `hero_image_url` is truthy, gradient fallback when null. Compression-factor 0.25 fade preserved on both branches.

### Two new demo stories — Birmingham + Park City

The published stack now has three stories, each with a unique painterly hero, Algenib narration, full body prose, pull-quote, verified claims, Publish Gate signature footer.

| Story | Headline | Narration | Pattern |
|---|---|---|---|
| Mount Pleasant, IA | _A small town builds a generation._ | 02:58 | Wrestling tradition, Olympic + Paralympic mix |
| **Park City, UT** | _A school day that ends at one in the afternoon._ | 03:29 | Alpine + freestyle skiing, school day bends around the chairlift schedule |
| **Birmingham, AL** | _A city remade for the rest of itself._ | 03:33 | Paralympic-anchored — adaptive cycling, wheelchair rugby, paratriathlon at the Lakeshore Foundation |

**Auto-DQ scan:** worker ran `agents/publish_gate/language_review._scan_surface` against headline / dek / pull_quote / kicker_place / joined body for both new stories — **0 flagged terms, 0 predictive constructions**. No specific athlete names anywhere; protagonists are *the campus*, *the program*, *the schedule*, *the town*.

The `/story` index page now reads as a real publication:
- Kicker: "PUBLISHED STORIES"
- Display title: "What the room has finished telling."
- Italic Lora dek: "Each page is the place — the program — the pattern. Never an individual."

Birmingham ties directly to the EE intervention seed — the demo viewer can cut from `/` (Birmingham EE arc) to `/story/fixture-birmingham-alabama` (the published anchor story) and the convergence lands.

## Demo-moment scoreboard

| # | Moment | Status |
|---|--------|--------|
| 1 | The room is alive | ✅ Live SSE on `/`, 1-hour windowed feed, no over-redactions |
| 2 | Agents truly agentic | ✅ Backend complete; visible on `/` |
| 3 | Equity Editor caused the anchor story | ✅ Birmingham EE arc seeded; Floor pulse wired to `birmingham-al`; published outcome at `/story/fixture-birmingham-alabama` |
| 4 | Broadcast lands emotionally | ✅ Mount Pleasant + Park City + Birmingham all with stylized heroes + Algenib narration |
| 5 | Publish Gate proves trust | ✅ `/publish-gate` audit with disambiguation showcase |

## Spend

Day-11 Vertex AI total ≈ **$0.85** (within $1 budget): Mount Pleasant hero + narration ($0.30), Birmingham + Park City heroes + narrations ($0.55).

## Open polish items (non-blocking for submission)

- **Birmingham hero kicker**: "ALABAMA" partially obscured by wheelchair-rugby chair's rim highlight. Charlie reviewed and approved as-is.
- **Counter top-right occasionally clipped** by hero highlights on certain images — minor.
- **Floor upper-left cluster** persists after Pass-2 tuning — would benefit from charge `-280` or stronger `forceCollide`.
- **Floor header z-index**: "THE FLOOR" header label clipped by a node at canvas top-left when simulation drifts a node there.

## What's frozen for submission

- All 11 design tokens, 9 type-scale entries, room cubic-bezier
- WireRow variants (8) + sub-scout treatment + NIL inline badge
- Counter math (UTC-midnight day-diff)
- Equity Editor no-apology rule + test guarding it
- Forward NIL path + new test guarding it
- Floor force config + 5-star labels (3 anchors + Park City + Houston)
- Three Broadcast stories — content, hero images, narration audio all locked
- Publish Gate trust panel with Mount Pleasant disambiguation marquee
- Counter at 800/801 days to LA28 (depending on UTC date)

## Files added/modified Day 11

```
web/app/api/wire/stream/route.ts          (LIVE_WINDOW_MS clause)
tests/test_emit_full_disambiguation.py    (new — 3 tests, passing)
scripts/seed_equity_editor_demo.py        (new — 179 LOC)
scripts/generate_demo_hero.py             (new — 173 LOC)
scripts/generate_demo_narration.py        (new — 286 LOC)
scripts/generate_demo_hero_birmingham.py  (new)
scripts/generate_demo_hero_park_city.py   (new)
scripts/generate_demo_narration_birmingham.py  (new)
scripts/generate_demo_narration_park_city.py   (new)
web/public/fixture/heroes/mount-pleasant.png       (new — 1.97 MB)
web/public/fixture/heroes/birmingham-alabama.png   (new — 1.63 MB)
web/public/fixture/heroes/park-city-utah.png       (new — 1.69 MB)
web/public/fixture/narration-mount-pleasant.mp3    (new — 2.15 MB / 02:58)
web/public/fixture/narration-birmingham-alabama.mp3 (new — 2.55 MB / 03:33)
web/public/fixture/narration-park-city-utah.mp3    (new — 2.51 MB / 03:29)
web/lib/story-fixture.ts                  (added 2 stories + hero_image_url field)
web/components/BroadcastPage.tsx          (motion.img + gradient fallback)
```

## What remains for submission (Day 12+)

1. Demo recording — 2-3 takes of cold-start → broadcast flow
2. Cloud Run deploy of agent-runtime + web (currently localhost-only)
3. README, screenshots, video, Devpost form
4. Apache 2.0 badge check on GitHub About sidebar
5. Optional: Floor Pass-3 polish (composition + z-index)
6. Optional: clean Firestore baseline (purge pre-Day-7 over-redacted events)

— HoE
