'use client';

/**
 * <AudioBar> — narration audio player for the Broadcast page.
 *
 * Spec: design-system.md §2/§6/§7 + BUILD_SPEC §7.6. Hand-drawn 22×22
 * SVG play/pause glyph (no icon library). 1px hairline progress track
 * in --navy-light, filled in --gold-warm. JetBrains Mono `current / total`
 * MM:SS, tabular-nums. Stroke-only icon; gold-warm → gold-deep on hover.
 */

import { useEffect, useRef, useState } from 'react';

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
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  // Use fixture fallback until audio element supplies real `duration`
  // (returns NaN before metadata loads).
  const [duration, setDuration] = useState(duration_s_fallback);
  const [seekable, setSeekable] = useState(false);

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
      play: () => setIsPlaying(true),
      pause: () => setIsPlaying(false),
      ended: () => setIsPlaying(false),
      // Fixture audio may not exist; bar stays visible but inert.
      error: () => {
        setIsPlaying(false);
        setSeekable(false);
      },
    };
    for (const [k, h] of Object.entries(handlers)) el.addEventListener(k, h);
    return () => {
      for (const [k, h] of Object.entries(handlers)) el.removeEventListener(k, h);
    };
  }, [src]);

  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    // Autoplay block / 404 → degrade silently; the bar stays visible.
    if (el.paused) el.play().catch(() => setIsPlaying(false));
    else el.pause();
  };

  const progress = duration > 0 ? Math.min(currentTime / duration, 1) : 0;

  return (
    <div className="border-y border-navy-light/70">
      {/* preload="metadata" so duration appears without full download */}
      <audio ref={audioRef} src={src} preload="metadata" />

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
          onClick={(e) => {
            const el = audioRef.current;
            if (!el || !seekable || duration <= 0) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - rect.left) / rect.width;
            el.currentTime = Math.max(0, Math.min(duration, ratio * duration));
          }}
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
      </div>

      {/* Caption row below the bar */}
      <div className="px-1 pb-3">
        <span className="font-body text-caption uppercase tracking-[0.18em] text-slate-room">
          narration · {voice_name}
        </span>
      </div>
    </div>
  );
}

export default AudioBar;
