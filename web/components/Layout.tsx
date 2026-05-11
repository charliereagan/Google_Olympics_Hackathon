import { ReactNode } from 'react';
import { AmbientTickerSwitch } from './AmbientTickerSwitch';
import { BroadcastNav } from './BroadcastNav';
import { FooterCredit } from './FooterCredit';
import { GrainOverlay } from './GrainOverlay';
import { HelpOverlay } from './HelpOverlay';
import { Masthead } from './Masthead';
import { Vignette } from './Vignette';
import { getRecentStories } from '@/lib/published-stories';
import type { BroadcastStory } from '@/lib/story-fixture';

// design-system.md + VPS-DEC-041 — page chrome composition.
// VPS-DEC-054 (2026-05-11): the ambient ticker is now route-aware. FOH pages
// see the story-headlines ticker; PD pages see the live agent Wire feed.
//
// Order, top to bottom on every page:
//   1. <Masthead />              — tracked-cap wordmark + days-to-LA28 + hairline
//   2. <AmbientTickerSwitch />   — 32px persistent ticker; story headlines on
//                                  FOH routes, agent Wire on PD routes
//   3. <main>{children}</main>   — page-specific content
//   4. <FooterCredit />          — VPS-DEC-049 mono-caps tech-stack credit
//   5. <BroadcastNav />          — fixed-bottom THE WIRE / MAP / FIELD / STORIES / GATE
//   6. <HelpOverlay />           — VPS-DEC-050 "?" affordance + closed-by-default overlay
//   7. <GrainOverlay /> + <Vignette /> — atmospheric layers (pointer-events:none)
//
// The bottom nav is `fixed` at z-30; we reserve 56px of `pb-` on the page
// wrapper so content doesn't sit behind it. CONSTITUTION §4 Rule 6: a judge
// must understand the chrome within 5 seconds. No hamburger. No logo. No
// "Welcome to" copy.

interface LayoutProps {
  children: ReactNode;
}

export async function Layout({ children }: LayoutProps) {
  // Best-effort fetch of recent published stories for the FOH ticker. If
  // Firestore is unreachable, getRecentStories already falls back to the
  // in-repo fixtures; we catch defensively just in case the helper changes
  // shape. The ticker handles an empty list gracefully ("The room is
  // connecting…"), and the PD branch ignores `stories` entirely.
  const { hero, recent } = await getRecentStories(10).catch(() => ({
    hero: null as unknown as BroadcastStory | null,
    recent: [] as BroadcastStory[],
  }));

  // Combine hero + recent, dedupe by id, sort by published_at DESC.
  const seen = new Set<string>();
  const merged: BroadcastStory[] = [];
  for (const s of [hero, ...recent]) {
    if (!s) continue;
    if (seen.has(s.id)) continue;
    seen.add(s.id);
    merged.push(s);
  }
  merged.sort((a, b) => (a.published_at < b.published_at ? 1 : -1));
  const stories = merged.slice(0, 10);

  return (
    <div className="relative flex min-h-screen flex-col">
      {/* Persistent chrome — top */}
      <Masthead />
      <AmbientTickerSwitch stories={stories} />

      {/* Main content — above grain + vignette, padded to clear the
          bottom-fixed BroadcastNav. */}
      <main className="relative z-10 flex-1 pb-20 sm:pb-16">{children}</main>

      {/* Persistent chrome — bottom */}
      <FooterCredit />
      <BroadcastNav />

      {/* Help overlay — closed by default; "?" trigger fixed top-right. */}
      <HelpOverlay />

      {/* Atmospheric overlays — pointer-events-none, low opacity. */}
      <GrainOverlay />
      <Vignette />
    </div>
  );
}
