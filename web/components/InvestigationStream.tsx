'use client';

/**
 * <InvestigationStream /> — the fan-scoped Wire feed (VPS-DEC-045).
 *
 * Subscribes to /api/wire/stream via useWireStream(), filters to events
 * tagged with this page's investigation_id, and plays the result at
 * compressed time: 4× typewriter (via augmented streaming profile) and
 * a 200ms→50ms WireRow mount (via wrapping MotionConfig).
 *
 * Hard rules: no WireRow fork, no SSE bridge changes, no athlete names.
 * Refs: HOE-DEC-021 + HOE-DEC-029 (compression=0.25), VPS-DEC-046 (mobile).
 */

import { motion, MotionConfig, useReducedMotion } from 'framer-motion';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { WireRow } from '@/components/WireRow';
import { useWireStream } from '@/lib/wire-stream-client';
import { getStreamingProfile } from '@/lib/streaming-profiles';
import type { WireEvent } from '@/lib/wire-event';
import type { StreamingProfile } from '@/components/WireRow';
import ReadYourStoryCTA from '@/components/ReadYourStoryCTA';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

// Compression: 4× per VPS-DEC-045. Typewriter cps × 4; mount 200ms → 50ms.
const COMPRESSION_MULTIPLIER = 4;
const COMPRESSED_MOUNT_S = 0.05;

const AT_BOTTOM_THRESHOLD_PX = 48;
const SILENCE_TIMEOUT_MS = 60_000;

interface InvestigationStreamProps {
  investigationId: string;
}

type ChainStatus =
  | { kind: 'waiting' }
  | { kind: 'streaming' }
  | { kind: 'completed'; storyId: string | null }
  | { kind: 'failed'; reason: 'killed' | 'stalled' };

export default function InvestigationStream({
  investigationId,
}: InvestigationStreamProps) {
  const { events, state } = useWireStream();
  const reduceMotion = useReducedMotion();
  const searchParams = useSearchParams();

  // Fan's prompt rides through as ?q=... for the dek.
  const promptRaw = searchParams.get('q') ?? '';
  const promptTruncated = useMemo(() => truncate(promptRaw, 120), [promptRaw]);

  // Client-side filter to this investigation.
  const filtered = useMemo(
    () => events.filter((ev) => ev.investigation_id === investigationId),
    [events, investigationId],
  );

  // Chain completion: Editor milestone "Story published" → success.
  // Same family with "killed"/"stalled" → failure CTA back to `/`.
  const chainStatus: ChainStatus = useMemo(() => {
    for (const ev of filtered) {
      if (ev.agent !== 'editor' || ev.message_type !== 'milestone') continue;
      const m = ev.message.toLowerCase();
      if (m.includes('story published')) {
        return { kind: 'completed', storyId: ev.story_unit_id ?? null };
      }
      if (m.includes('killed') || m.includes('stalled')) {
        return {
          kind: 'failed',
          reason: m.includes('killed') ? 'killed' : 'stalled',
        };
      }
    }
    return filtered.length > 0 ? { kind: 'streaming' } : { kind: 'waiting' };
  }, [filtered]);

  // Silence detection — show "still scouting" after 60s of no events.
  const mountedAtRef = useRef<number>(Date.now());
  const [silentTooLong, setSilentTooLong] = useState<boolean>(false);
  useEffect(() => {
    if (filtered.length > 0) {
      setSilentTooLong(false);
      return;
    }
    const remaining =
      SILENCE_TIMEOUT_MS - (Date.now() - mountedAtRef.current);
    if (remaining <= 0) {
      setSilentTooLong(true);
      return;
    }
    const t = setTimeout(() => setSilentTooLong(true), remaining);
    return () => clearTimeout(t);
  }, [filtered.length]);

  // Stopwatch — elapsed seconds since page mount.
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  useEffect(() => {
    const id = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - mountedAtRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll: pin newest event to bottom only when user is already there.
  const isAtBottomRef = useRef<boolean>(true);
  const lastCountRef = useRef<number>(0);

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const dist = doc.scrollHeight - (window.scrollY + window.innerHeight);
      isAtBottomRef.current = dist <= AT_BOTTOM_THRESHOLD_PX;
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useLayoutEffect(() => {
    if (filtered.length === lastCountRef.current) return;
    lastCountRef.current = filtered.length;
    if (!isAtBottomRef.current) return;
    if (typeof window === 'undefined') return;
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [filtered.length, reduceMotion]);

  const isErrorish =
    state.kind === 'error' || state.kind === 'reconnecting';

  return (
    <div>
      {/* Header — kicker + (compression / stopwatch) + prompt dek.
          Mobile (375): the meta cluster wraps below the kicker so the
          investigation_id never truncates. sm+ returns to a single line. */}
      <header className="mb-8 sm:mb-12">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 sm:flex-nowrap sm:justify-between">
          <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">
            LIVE INVESTIGATION ·{' '}
            <span className="text-gold-warm/80">{investigationId}</span>
          </p>
          <div className="flex shrink-0 items-baseline gap-3 font-mono text-mono-sm tabular-nums text-gold-warm/60">
            <span aria-label={`compression ${COMPRESSION_MULTIPLIER}×`}>
              Compression: {COMPRESSION_MULTIPLIER}×
            </span>
            <span aria-hidden="true" className="text-navy-light">
              │
            </span>
            <span aria-label={`elapsed ${elapsedSec} seconds`}>
              {formatStopwatch(elapsedSec)}
            </span>
          </div>
        </div>

        {promptTruncated && (
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text">
            “{promptTruncated}”
          </p>
        )}
      </header>

      {chainStatus.kind === 'waiting' && silentTooLong && (
        <p
          className="my-12 text-center font-italic italic text-italic-md text-wire-text"
          role="status"
          aria-live="polite"
        >
          Hold on — the room is still scouting. This usually takes 8–12
          minutes.
        </p>
      )}

      {chainStatus.kind === 'waiting' && !silentTooLong && (
        <p
          className="my-12 text-center font-italic italic text-italic-md text-wire-text"
          role="status"
          aria-live="polite"
        >
          The room is taking your prompt. The wire opens shortly.
        </p>
      )}

      {filtered.length > 0 && (
        <div className="divide-y divide-navy-light">
          {filtered.map((ev) => (
            <CompressedRow key={ev.id} event={ev} />
          ))}
        </div>
      )}

      {isErrorish && filtered.length > 0 && (
        <p className="pt-6 font-italic italic text-body-sm text-wire-time">
          The line is down. Reconnecting…
        </p>
      )}

      {chainStatus.kind === 'failed' && (
        <FailureCard reason={chainStatus.reason} />
      )}

      {chainStatus.kind === 'completed' && (
        <ReadYourStoryCTA storyId={chainStatus.storyId} />
      )}
    </div>
  );
}

// CompressedRow — WireRow + 4× streaming profile + 50ms mount transition.
function CompressedRow({ event }: { event: WireEvent }) {
  const baseProfile = getStreamingProfile(event.agent, event.sub_agent);
  const compressedProfile: StreamingProfile = useMemo(
    () => ({
      ...baseProfile,
      base_chars_per_second:
        baseProfile.base_chars_per_second * COMPRESSION_MULTIPLIER,
      pause_min_ms: Math.round(baseProfile.pause_min_ms / COMPRESSION_MULTIPLIER),
      pause_max_ms: Math.round(baseProfile.pause_max_ms / COMPRESSION_MULTIPLIER),
    }),
    [baseProfile],
  );

  const isPreSeed = event.mode === 'replay' || event.mode === 'published';
  const isLive = event.mode === 'live';

  return (
    <MotionConfig
      transition={{
        duration: isPreSeed ? 0 : COMPRESSED_MOUNT_S,
        ease: ROOM_EASE,
      }}
    >
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
        compression_factor={event.compression_factor ?? 0.25}
        nil_redaction_log={event.nil_redaction_log}
        isLive={isLive}
        streamingProfile={compressedProfile}
      />
    </MotionConfig>
  );
}

function FailureCard({ reason }: { reason: 'killed' | 'stalled' }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: ROOM_EASE }}
      className="mt-12 border-y border-navy-light py-12 text-center sm:mt-16 sm:py-16"
    >
      <p className="font-italic italic text-italic-md text-wire-text">
        The room couldn’t tell this one.{' '}
        <span className="text-wire-time">
          ({reason === 'killed' ? 'investigation halted' : 'evidence stalled'})
        </span>
      </p>
      <Link
        href="/"
        className="mt-6 inline-block font-body text-caption uppercase tracking-[0.18em] text-gold-warm transition-colors duration-200 ease-room hover:text-gold-deep"
      >
        Try a different prompt →
      </Link>
    </motion.div>
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + '…';
}

function formatStopwatch(seconds: number): string {
  const mm = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const ss = (seconds % 60).toString().padStart(2, '0');
  return `${mm}:${ss}`;
}
