'use client';

/**
 * <AmbientStoryTicker /> — the Front-of-House persistent 32px ticker band.
 * VPS-DEC-054 (2026-05-11).
 *
 * Sibling to <AmbientWireTicker />. Same visual chrome — 32px tall, navy-mid
 * fill, gold-warm/40 top + bottom hairlines, CSS marquee (60s linear infinite,
 * group-hover pauses, motion-reduce respects). Difference is the payload: this
 * ticker scrolls late-breaking PUBLISHED STORY HEADLINES rather than raw
 * agent activity. The agent feed stays on Production Deck surfaces via
 * <AmbientWireTicker />; the consumer audience never has to parse the
 * engineering view.
 *
 * Line shape (Format A): `2h AGO · MOUNT PLEASANT · IOWA · A small town builds a generation.`
 *
 * No client-side data fetching — stories arrive pre-fetched from the
 * server-component Layout via props.
 */

import { useMemo } from 'react';
import Link from 'next/link';
import type { BroadcastStory } from '@/lib/story-fixture';

const PLACE_PREFIX_RE = /^\s*PUBLISHED\s*·\s*/i;
const HEADLINE_MAX_CHARS = 90;
const MAX_STORIES = 10;

/**
 * Compact broadcast-style relative time: `JUST NOW`, `5m AGO`, `2h AGO`,
 * `3d AGO`. Past 7 days → short uppercase date with no leading zero
 * (`MAY 5`). Pure function of an ISO timestamp + `Date.now()`.
 */
function formatRelativeCompact(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diff = Date.now() - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'JUST NOW';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m AGO`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h AGO`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d AGO`;
  return new Date(iso)
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    .toUpperCase();
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)).trimEnd() + '…';
}

function stripPublishedPrefix(kicker: string): string {
  return kicker.replace(PLACE_PREFIX_RE, '').trim();
}

export function AmbientStoryTicker({ stories }: { stories: BroadcastStory[] }) {
  // Defensive cap — caller is responsible for ordering. If a longer array
  // slips in, take the first MAX_STORIES silently. Same insertion order is
  // preserved.
  const items = useMemo(() => stories.slice(0, MAX_STORIES), [stories]);

  // Duplicate the list so the marquee loops seamlessly: when the first copy
  // scrolls off the left, the second copy is in identical position and the
  // animation restart is invisible.
  const looped = useMemo(() => [...items, ...items], [items]);

  return (
    <div
      role="complementary"
      aria-label="Recent published stories"
      className="group relative w-full overflow-hidden border-b border-t border-gold-warm/40 bg-navy-mid"
      style={{ height: '32px' }}
    >
      {items.length === 0 ? (
        <div className="flex h-full items-center px-4">
          <span className="font-italic italic text-italic-sm text-wire-time">
            The room is connecting…
          </span>
        </div>
      ) : (
        <div
          className="flex h-full items-center whitespace-nowrap will-change-transform group-hover:[animation-play-state:paused] motion-reduce:!animate-none"
          style={{
            animation: 'wire-marquee 60s linear infinite',
          }}
        >
          {looped.map((story, idx) => {
            const time = formatRelativeCompact(story.published_at);
            const place = stripPublishedPrefix(story.kicker_place);
            const headline = truncate(story.headline, HEADLINE_MAX_CHARS);
            return (
              <Link
                key={`${story.id}-${idx}`}
                href={`/story/${story.id}`}
                className="inline-flex items-baseline gap-2 px-6"
              >
                <span
                  className="font-mono text-mono-sm uppercase tabular-nums text-wire-time"
                  style={{ letterSpacing: '0.18em' }}
                >
                  {time}
                </span>
                <span aria-hidden="true" className="text-navy-light font-mono text-mono-sm">
                  ·
                </span>
                <span className="font-italic italic text-italic-sm text-cream">
                  {place}
                </span>
                <span aria-hidden="true" className="text-navy-light font-mono text-mono-sm">
                  ·
                </span>
                <span className="font-body text-body-sm text-wire-text group-hover:text-cream">
                  {headline}
                </span>
              </Link>
            );
          })}
        </div>
      )}

      {/* Keyframes — kept inline so the component is self-contained, matching
          the pattern in <AmbientWireTicker />. The width of one loop equals
          the rendered events copy; we shift by 50% (one copy) so the second
          copy seamlessly takes over at the loop boundary. */}
      <style>{`
        @keyframes wire-marquee {
          0%   { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}

export default AmbientStoryTicker;
