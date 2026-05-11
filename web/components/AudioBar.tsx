'use client';

/**
 * <AudioBar> — narration audio player for the Broadcast page.
 *
 * Spec: design-system.md §2/§6/§7 + BUILD_SPEC §7.6 + VPS-DEC-044.
 * A broadcast doesn't ask permission to begin. On mount we attempt
 * autoplay-with-sound (permitted in the click-navigated path because
 * the click counts as same-tab user interaction). If the browser
 * rejects, we fall back to autoplay-MUTED + a centered gold
 * "BEGIN BROADCAST" overlay; one click resets to t=0 and unmutes.
 *
 * State machine:
 *   loading → autoplaying           (with-sound autoplay succeeded)
 *           → direct-link-fallback  (with-sound rejected, muted preroll)
 *   autoplaying / direct-link-fallback → playing
 *   playing ↔ paused                (manual pause/resume after first start)
 *
 * Mute is per-page only — NOT persisted across navigations. A broadcast
 * page must greet every visitor with sound; persisting a stale "muted"
 * pref across navs would make the page silent on arrival even when the
 * click-navigation path grants the browser permission to autoplay with
 * sound. Users who silence one story start fresh on the next.
 *
 * Hand-drawn 22×22 SVG play/pause and 24×24 mute toggle (no icon library).
 * Stroke-only; gold-warm → gold-deep on hover. 1px hairline progress.
 */

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useCallback, useEffect, useRef, useState } from 'react';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

type PlaybackState =
  | 'loading'
  | 'autoplaying'
  | 'direct-link-fallback'
  | 'playing'
  | 'paused';

interface AudioBarProps {
  src: string;                   // narration audio URL (may 404 in fixture)
  duration_s_fallback: number;   // displayed before audio metadata loads
  voice_name: string;            // shown below the bar — `Algenib`
}

/** mm:ss formatter; tolerates NaN / negative / non-finite inputs. */
function formatMmSs(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '00:00';
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60).toString().padStart(2, '0');
  const s = (total % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export function AudioBar({ src, duration_s_fallback, voice_name }: AudioBarProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const reduceMotion = useReducedMotion();

  const [state, setState] = useState<PlaybackState>('loading');
  const [muted, setMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  // Use fixture fallback until audio element supplies real `duration`
  // (returns NaN before metadata loads).
  const [duration, setDuration] = useState(duration_s_fallback);
  const [seekable, setSeekable] = useState(false);

  const isPlaying = state === 'autoplaying' || state === 'playing';
  const showBeginOverlay = state === 'direct-link-fallback';

  // Native listeners — graceful 404 degradation (BUILD_SPEC §7.6).
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const handlers: Record<string, () => void> = {
      timeupdate: () => setCurrentTime(el.currentTime),
      loadedmetadata: () => {
        if (Number.isFinite(el.duration) && el.duration > 0) {
          setDuration(el.duration);
          setSeekable(true);
        }
      },
      pause: () => setState((prev) => (prev === 'autoplaying' || prev === 'playing' ? 'paused' : prev)),
      play: () => setState((prev) => (prev === 'paused' ? 'playing' : prev)),
      ended: () => setState('paused'),
      // Fixture audio may not exist; bar stays visible but inert.
      error: () => {
        setSeekable(false);
        setState('paused');
      },
    };
    for (const [k, h] of Object.entries(handlers)) el.addEventListener(k, h);
    return () => {
      for (const [k, h] of Object.entries(handlers)) el.removeEventListener(k, h);
    };
  }, [src]);

  // Curtain-rise autoplay attempt. Runs once on mount per `src`.
  // Cancellation guard prevents state writes after unmount mid-play.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    let cancelled = false;

    // Always start unmuted — the click-navigated path (homepage CTA)
    // gives the browser a fresh user gesture, so with-sound autoplay
    // is permitted. We never carry a stale "muted" pref into a new
    // story page; mute is per-page only.
    el.muted = false;
    setMuted(false);

    const tryAutoplay = async () => {
      try {
        // Attempt 1: with sound.
        await el.play();
        if (cancelled) return;
        setState('autoplaying');
      } catch {
        if (cancelled) return;
        // Browser blocked autoplay-with-sound (NotAllowedError typical
        // for direct-link / refresh visits with no recent gesture).
        // Fall back to muted preroll + BEGIN BROADCAST overlay.
        el.muted = true;
        setMuted(true);
        try {
          await el.play();
          if (cancelled) return;
          setState('direct-link-fallback');
        } catch {
          if (cancelled) return;
          // Even muted playback rejected (rare — file 404, etc.).
          setState('paused');
        }
      }
    };

    void tryAutoplay();

    return () => {
      cancelled = true;
      // Pause to release the audio decoder and avoid orphaned playback
      // if the page unmounts mid-curtain-rise.
      try {
        el.pause();
      } catch {
        /* no-op */
      }
    };
  }, [src]);

  // BEGIN BROADCAST handler — restart from 0 with sound. The muted
  // preroll has already advanced currentTime; rewinding ensures fans
  // hear the Narrator's breath at t=0 (BUILD_SPEC §7.1).
  const handleBeginBroadcast = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    el.muted = false;
    setMuted(false);
    el.currentTime = 0;
    el.play()
      .then(() => setState('playing'))
      .catch(() => setState('paused'));
  }, []);

  const togglePlay = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      // Pressing play is an explicit "I want to hear this" gesture.
      // If the element is currently muted (from a manual toggle or a
      // muted-preroll fallback), unmute it so the user hears sound on
      // the very first click of the play button — not the second.
      if (el.muted) {
        el.muted = false;
        setMuted(false);
      }
      el.play()
        .then(() => setState('playing'))
        .catch(() => setState('paused'));
    } else {
      el.pause();
    }
  }, []);

  const toggleMute = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    const next = !el.muted;
    el.muted = next;
    setMuted(next);
  }, []);

  const handleSeek = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      const el = audioRef.current;
      if (!el || !seekable || duration <= 0) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const ratio = (e.clientX - rect.left) / rect.width;
      el.currentTime = Math.max(0, Math.min(duration, ratio * duration));
    },
    [seekable, duration],
  );

  const progress = duration > 0 ? Math.min(currentTime / duration, 1) : 0;
  const enterTransition = reduceMotion ? { duration: 0 } : { duration: 0.2, ease: ROOM_EASE };
  const exitTransition = reduceMotion ? { duration: 0 } : { duration: 0.15, ease: ROOM_EASE };

  return (
    <div className="relative border-y border-navy-light/70">
      {/* preload="metadata" so duration appears without full download.
          `playsInline` lets iOS Safari play inline rather than entering
          the native fullscreen player on autoplay. */}
      <audio ref={audioRef} src={src} preload="metadata" playsInline />

      <div className="flex h-16 w-full items-center gap-4 px-1">
        {/* Play / Pause — 22×22 inline SVG, stroke-only, no icon lib */}
        <button
          type="button"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause narration' : 'Play narration'}
          aria-pressed={isPlaying}
          className="group flex h-10 w-10 shrink-0 items-center justify-center"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 22 22"
            fill="none"
            aria-hidden="true"
            className="text-gold-warm transition-colors duration-200 ease-room group-hover:text-gold-deep group-focus-visible:text-gold-deep"
          >
            {isPlaying ? (
              // Pause: two stroked rectangles — broadcast glyph register.
              <>
                <rect x="6" y="3" width="3" height="16" rx="0.5" stroke="currentColor" strokeWidth="1.5" />
                <rect x="13" y="3" width="3" height="16" rx="0.5" stroke="currentColor" strokeWidth="1.5" />
              </>
            ) : (
              // Play: rounded stroke-only triangle.
              <path d="M6 3.5 L18 11 L6 18.5 Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
            )}
          </svg>
        </button>

        {/* Progress: 1px hairline, gold-warm fill, click-to-seek when ready */}
        <button
          type="button"
          aria-label="Seek narration"
          disabled={!seekable}
          onClick={handleSeek}
          className="relative flex h-10 flex-1 items-center disabled:cursor-default"
        >
          <div
            aria-hidden="true"
            className="relative h-px w-full bg-navy-light"
          >
            <div
              className="absolute inset-y-0 left-0 bg-gold-warm transition-[width] duration-100 ease-room"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        </button>

        {/* Time: mono, tabular-nums, wire-time, `current / total` */}
        <div className="shrink-0 font-mono text-mono-sm tabular-nums text-wire-time">
          {formatMmSs(currentTime)} / {formatMmSs(duration)}
        </div>

        {/* Mute toggle — always visible, ~44×44 tap target (iOS HIG min) */}
        <button
          type="button"
          onClick={toggleMute}
          aria-label={muted ? 'Unmute narration' : 'Mute narration'}
          aria-pressed={muted}
          className="group flex h-11 w-11 shrink-0 items-center justify-center"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
            className="text-gold-warm transition-colors duration-200 ease-room group-hover:text-gold-deep group-focus-visible:text-gold-deep"
          >
            {/* Speaker body — common to both states */}
            <path
              d="M4 9 L4 15 L8 15 L13 19 L13 5 L8 9 Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {muted ? (
              // Muted: diagonal slash through the speaker
              <path
                d="M16 8 L22 16"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            ) : (
              // Unmuted: three sound waves arcing right
              <>
                <path
                  d="M16 9 Q17.5 12 16 15"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M18.5 7 Q21 12 18.5 17"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Caption row below the bar */}
      <div className="px-1 pb-3">
        <span className="font-body text-caption uppercase tracking-[0.18em] text-slate-room">
          narration · {voice_name}
        </span>
      </div>

      {/* BEGIN BROADCAST overlay — direct-link-fallback only.
          Local scrim over the player area; click anywhere on the
          overlay starts narration from t=0 with sound. */}
      <AnimatePresence>
        {showBeginOverlay && (
          <motion.button
            type="button"
            onClick={handleBeginBroadcast}
            aria-label="Begin broadcast"
            className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-navy-deep/40 backdrop-blur-[2px]"
            initial={{ opacity: reduceMotion ? 1 : 0 }}
            animate={{ opacity: 1, transition: enterTransition }}
            exit={{ opacity: 0, transition: exitTransition }}
          >
            {/* 56×56 play triangle ringed by a hairline gold-warm circle */}
            <svg
              width="56"
              height="56"
              viewBox="0 0 56 56"
              fill="none"
              aria-hidden="true"
              className="text-gold-warm"
            >
              <circle
                cx="28"
                cy="28"
                r="26"
                stroke="currentColor"
                strokeOpacity="0.4"
                strokeWidth="1"
              />
              <path
                d="M22 17 L40 28 L22 39 Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </svg>
            <span className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">
              Begin broadcast
            </span>
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

export default AudioBar;
