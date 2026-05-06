'use client';

/**
 * <WireFeed /> — the live root view of the room.
 *
 * Subscribes to the SSE bridge at `/api/wire/stream` via `useWireStream()`
 * and renders each `WireEvent` as a `<WireRow />`. Three visible states:
 *
 *   - empty + connected  → "The room is quiet."  (italic Lora, centered)
 *   - error / reconnecting → "The line is down. Reconnecting…"
 *                            with a 1px gold-warm/40 hairline progress bar
 *                            that loops on the room cubic-bezier
 *   - streaming           → ordered list of <WireRow /> rows, newest at
 *                            the bottom, auto-scroll only when the user is
 *                            already pinned to the bottom (don't yank scroll
 *                            if they're reading earlier rows)
 *
 * Mount entry animation contract (design-system.md §5):
 *   - Live arrivals animate in (opacity 0, y 8, blur 2px → settled, 200ms,
 *     room cubic-bezier). The `<WireRow />` component already implements
 *     this on its root motion.article.
 *   - Pre-seed rows (mode === 'replay' | 'published') are history, not
 *     arrivals — they should mount settled. We achieve this without
 *     mutating the frozen <WireRow /> by wrapping pre-seed rows in a
 *     <MotionConfig transition={{ duration: 0 }}>, which zero-collapses
 *     the inner motion.article transition so the row snaps to its target
 *     state on first paint.
 *
 * NIL-compliance: this component renders only what the SSE bridge emits.
 * The Publish Gate's NIL Redaction Layer runs server-side before any
 * event is written to Firestore (HOE-DEC-018, BUILD_SPEC §6.13). We do
 * NOT inspect or transform message text on the client.
 */

import { motion, MotionConfig, useReducedMotion } from 'framer-motion';
import { useEffect, useLayoutEffect, useRef } from 'react';
import { useWireStream } from '@/lib/wire-stream-client';
import { WireRow } from '@/components/WireRow';
import { getStreamingProfile } from '@/lib/streaming-profiles';
import type { WireEvent } from '@/lib/wire-event';

// design-system.md §5.3 — the room's signature easing curve.
const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

// Auto-scroll threshold in pixels. Below this, treat the user as "at bottom"
// and follow new arrivals; above it, leave their scroll position alone so
// they can read older events without being yanked.
const AT_BOTTOM_THRESHOLD_PX = 48;

export default function WireFeed() {
  const { events, state } = useWireStream();
  const reduceMotion = useReducedMotion();

  // Pin newest-arrival auto-scroll to "user is at bottom".
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const isAtBottomRef = useRef<boolean>(true);
  const lastEventCountRef = useRef<number>(0);

  // Track scroll position so we know whether to auto-follow new rows.
  useEffect(() => {
    // Window scrolls (the page itself is the scroll container at this layout
    // depth) — listen on window, measure against documentElement.
    const onScroll = () => {
      const doc = document.documentElement;
      const distanceFromBottom =
        doc.scrollHeight - (window.scrollY + window.innerHeight);
      isAtBottomRef.current = distanceFromBottom <= AT_BOTTOM_THRESHOLD_PX;
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // When new events arrive AND the user is already pinned to the bottom,
  // scroll to keep the newest row visible. Use useLayoutEffect so the scroll
  // happens before the browser paints the new height.
  useLayoutEffect(() => {
    if (events.length === lastEventCountRef.current) return;
    lastEventCountRef.current = events.length;
    if (!isAtBottomRef.current) return;

    // Smooth on the room ease — but keep it short so the cadence feels alive.
    if (typeof window === 'undefined') return;
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [events.length, reduceMotion]);

  // ---- Render branches ---------------------------------------------------

  const isErrorish =
    state.kind === 'error' || state.kind === 'reconnecting';

  if (events.length === 0 && !isErrorish) {
    return (
      <div
        ref={scrollRef}
        className="flex min-h-[60vh] items-center justify-center"
        role="status"
        aria-live="polite"
      >
        <p className="font-italic italic text-italic-md text-wire-text">
          The room is quiet.
        </p>
      </div>
    );
  }

  if (events.length === 0 && isErrorish) {
    return (
      <div
        ref={scrollRef}
        className="flex min-h-[60vh] flex-col items-center justify-center gap-6"
        role="status"
        aria-live="polite"
      >
        <p className="font-italic italic text-italic-md text-wire-text">
          The line is down. Reconnecting…
        </p>
        {/* Hairline progress bar — 1px gold-warm/40, room ease loop.
            Indicates the reconnect is in motion without raising anxiety. */}
        <div
          aria-hidden="true"
          className="h-px w-48 overflow-hidden bg-gold-warm/15"
        >
          {!reduceMotion && (
            <motion.div
              className="h-full w-1/3 bg-gold-warm/40"
              initial={{ x: '-100%' }}
              animate={{ x: '300%' }}
              transition={{
                duration: 2.4,
                ease: ROOM_EASE,
                repeat: Infinity,
              }}
            />
          )}
        </div>
      </div>
    );
  }

  // Streaming state (or error after we already have history): render the
  // event list. The hook appends events in arrival order, so iterating is
  // already chronological — newest at the bottom.
  return (
    <div ref={scrollRef} className="divide-y divide-navy-light">
      {events.map((ev) => (
        <FeedRow key={ev.id} event={ev} />
      ))}
      {/* Soft reconnect indicator beneath the feed when we have history but
          the connection has dropped. Quiet — does not yank attention from
          the rows above. */}
      {isErrorish && (
        <div className="pt-4">
          <p className="font-italic italic text-body-sm text-wire-time">
            The line is down. Reconnecting…
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * One Wire event rendered as a <WireRow />.
 *
 * Pre-seed events (mode === 'replay' | 'published') mount settled — they're
 * history. Live events (mode === 'live') inherit the <WireRow /> default
 * 200ms room-ease entry animation. We collapse the pre-seed transition via
 * <MotionConfig> rather than mutate the frozen WireRow component.
 */
function FeedRow({ event }: { event: WireEvent }) {
  const isPreSeed = event.mode === 'replay' || event.mode === 'published';
  const isLive = event.mode === 'live';
  const profile = getStreamingProfile(event.agent, event.sub_agent);

  const row = (
    <WireRow
      id={event.id}
      timestamp={event.timestamp}
      agent={event.agent}
      sub_agent={event.sub_agent}
      message={event.message}
      message_type={event.message_type}
      confidence={event.confidence}
      story_unit_id={event.story_unit_id}
      mode={event.mode}
      visual_treatment={event.visual_treatment}
      compression_factor={event.compression_factor}
      nil_redaction_log={event.nil_redaction_log}
      isLive={isLive}
      streamingProfile={profile}
    />
  );

  if (isPreSeed) {
    // Zero-collapse the inner motion transition so the row mounts settled.
    return (
      <MotionConfig transition={{ duration: 0 }}>
        {row}
      </MotionConfig>
    );
  }

  return row;
}
