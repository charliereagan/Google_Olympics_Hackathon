---
title: Day 8 — Pass 2 — The Wire (refinement review)
date: 2026-05-05
author: HoE
viewport_captured: 1440×900 (laptop) — visual mobile via static HTML inspection
routes_captured:
  - /fixture/wire (top, middle, bottom — re-captured)
  - / (root placeholder — unchanged from Pass 1)
---

# Day 8 — Pass 2 — The Wire

Pass 2 closes the open Pass-1 questions and adds mobile responsive support. Two workers ran in parallel; both returned clean diffs.

## What landed

### Worker A — counter fix + Equity Editor voice lock

**Counter fix (Q5).** `web/components/DaysToLA28.tsx` — replaced `Math.floor((target - now) / day_ms)` with a UTC-midnight day-diff helper (`daysUntilUtcMidnight`). Old behavior: drifted from 801 → 800 mid-day. New: stable 801 all day. Verified in browser — top-right counter now reads **"801 days to LA28"**.

> Correction: I mis-stated the value as 803 in Pass 1. The mathematically correct count from 2026-05-05 to 2028-07-14 is 801. Worker A produced the correct number.

**Equity Editor no-apology lock (Q4).** `prompts/equity_editor.md` now contains an explicit **No-apology rule** under Voice signature:

> Never begin an utterance with `Sorry`, `I apologize`, `I'm sorry`, `My apologies`, `Apologies`, `Unfortunately`, `I regret`, `I hate to`. The Equity Editor states facts about coverage parity. The room does not apologize for caring about parity.

`tests/test_equity_editor_voice.py` — 10 fixture-driven test cases assert (a) the prompt does not instruct apology, (b) the no-apology rule is present, (c) every Equity Editor message in `web/app/fixture/wire/page.tsx` is clean against the 8 forbidden prefixes. **All 10 passing locally** (`pytest tests/test_equity_editor_voice.py` — 10 passed in 0.01s).

### Worker B — mobile responsive sweep (Q2)

Tailwind responsive prefixes only — no new tokens, no new fonts, no color changes. Layout / DaysToLA28 / tailwind.config untouched.

**Files changed (4):**
- `web/components/WireRow.tsx` — header row uses `flex-wrap items-baseline justify-between gap-x-3 gap-y-1 sm:flex-nowrap`. Below 640px the caption tag (`THINKING` / `MILESTONE` / `DECISION` / `INTERVENTION`) wraps to its own line under the timestamp+agent cluster. The three-tier hierarchy survives — timestamp+agent / hairline / body — caption stacks instead of compressing.
- Sub-agent indent: `pl-4 sm:pl-5 md:pl-6` (16 / 20 / 24px). Tracked-small-cap sub-name (CINDERELLA SCOUT etc.) stays above its body even at 375px.
- `web/app/fixture/wire/page.tsx` — container `px-4 py-12 sm:px-6 sm:py-16 md:py-20`; header/footer margins compress on mobile.
- `web/app/fixture/page.tsx` — same container tightening; type-scale samples step `display-xl → display-md` and `display-lg → display-md` on mobile so the 96px specimen never overflows 375px.
- `web/app/page.tsx` — root container `px-4 py-16 sm:px-6 sm:py-24`.

**Build verification:** `npm run typecheck` clean, `npm run lint` clean. The responsive classes are confirmed present in the rendered HTML at runtime: `sm:flex-nowrap`, `sm:pl-5`, `md:pl-6`, `sm:px-6`, `sm:py-16`, `md:py-20` all emit.

## Visual verification at 1440×900

Re-captured `/fixture/wire` top → middle → bottom. Everything from Pass 1 is unchanged at desktop:
- Display-xl Playfair "The Wire." headline + Lora dek
- Three-tier broadcast hierarchy with right-gutter caption tags
- Sub-scout treatment (CINDERELLA / COMEBACK / HOMETOWN / ECHO)
- Equity Editor INTERVENTION with red left edge + outer frame (kept per Q3 → option a)
- Editor DECISION with gold timestamp + medium-weight body
- Publish Gate row with `[NIL: 2r/1a]` mono badge inline
- Footer attribution masthead in tracked small caps
- **Counter: 801 days to LA28** (Q5 verified)

## Mobile verification (375×812)

The chrome MCP's `resize_window` resizes the OS window but doesn't change the inner viewport on macOS, so live device-frame screenshots weren't possible from this session. Instead I verified by:
1. Inspecting the prerendered HTML at runtime — every responsive class string emits as expected.
2. Reading the diffs against the design-system.md §4 contract — no regressions.

**@charlie — to test mobile yourself:**
- Open Chrome DevTools (Cmd+Opt+I), click the device toolbar (Cmd+Shift+M), pick iPhone 12/13/14 (390×844) or iPhone SE (375×667)
- Hit `/fixture/wire`, `/fixture`, and `/`
- The right-gutter caption tag should stack below the agent name on those widths; everything else should look identical to desktop

I'll capture mobile-frame screenshots in Pass 3 if you want them.

## Open items

@charlie **Q-new-1 — root route (Q6 Day-9 plan).** You said you want `/` to show prod data when you record the demo. That's a Day-9 task: wire `/` to the live SSE stream from Cloud Run, with a fail-closed empty state if the stream is down. Want me to scope that as the first Day-9 worker, or hold for a later session?

@charlie **Q-new-2 — agent-specific tests directory.** Worker A put `test_equity_editor_voice.py` at top-level `tests/` (cross-cutting voice/fixture lock). The agent's unit tests live at `agents/equity_editor/test_*.py`. I think top-level `tests/` is right because this asserts both the prompt AND the frontend fixture stay clean, but if you want it co-located with the agent unit tests, easy move.

## What's frozen

- Counter math (UTC-midnight day-diff)
- Equity Editor no-apology rule (lives in the prompt + has a passing test guarding it)
- All 11 design tokens, 9 type-scale entries, room easing
- Wire row variants (8): editor / equity_editor / sub_agent / thinking / milestone / intervention / decision and the NIL-badge inline treatment

## Next

Pass 3 (or Day 9, depending on your call):
- Wire `/` to live prod SSE stream (Q-new-1)
- Live-frame mobile screenshots (cosmetic verification)
- Anything you flag in Pass 2 review

— HoE
