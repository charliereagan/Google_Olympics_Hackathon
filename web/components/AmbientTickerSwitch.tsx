'use client';

/**
 * <AmbientTickerSwitch /> — route-aware selector between the two ticker
 * variants. VPS-DEC-054 (2026-05-11).
 *
 * Front-of-House routes (/, /map, /field, /story, /story/[id],
 *   /investigation/[id]) → <AmbientStoryTicker /> with the latest published
 *   story headlines.
 * Production Deck routes (/wire, /floor, /publish-gate) →
 *   <AmbientWireTicker /> with the live agent feed.
 * Unknown routes default to the FOH variant (FOH is the bigger audience).
 *
 * Stories arrive pre-fetched from the server-component <Layout />; this
 * switch is a thin client-side router-aware shell that picks the right
 * ticker without forcing the consumer ticker to ever subscribe to the SSE
 * stream.
 */

import { usePathname } from 'next/navigation';
import { AmbientWireTicker } from './AmbientWireTicker';
import { AmbientStoryTicker } from './AmbientStoryTicker';
import type { BroadcastStory } from '@/lib/story-fixture';

// Routing source of truth: kept in one place so future BroadcastNav route
// changes are a single edit. Match by `startsWith` to cover nested routes
// (e.g. `/publish-gate/audit/abc`) without enumerating every child.
const PD_PATH_PREFIXES = ['/wire', '/floor', '/publish-gate'];

function isProductionDeck(pathname: string | null): boolean {
  if (!pathname) return false;
  return PD_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + '/'),
  );
}

export function AmbientTickerSwitch({ stories }: { stories: BroadcastStory[] }) {
  const pathname = usePathname();
  if (isProductionDeck(pathname)) return <AmbientWireTicker />;
  return <AmbientStoryTicker stories={stories} />;
}

export default AmbientTickerSwitch;
