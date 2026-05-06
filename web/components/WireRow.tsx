'use client';

/**
 * <WireRow> — the canonical broadcast graphic for the Storyteller's Room.
 *
 * Spec sources:
 *   - Docs/Engineering/design-system.md §4 (spatial composition / The Wire)
 *   - Docs/Engineering/design-system.md §5 (motion + streaming cognition speed)
 *   - Docs/Engineering/design-system.md §7 (AI slop to avoid)
 *   - Docs/Engineering/design-system.md §8 (component patterns)
 *   - Docs/Engineering/BUILD_SPEC.md §6.2 (Wire message structure)
 *   - Docs/Engineering/BUILD_SPEC.md §6.5 (variable cognition speed)
 *   - Docs/Engineering/BUILD_SPEC.md §6.11 (streaming profile schema)
 *   - CONSTITUTION.md §5 (Wire rules) + §8 (Kill List)
 *
 * Hard rules enforced here:
 *   - No chat bubbles. No avatars. No "User:/Assistant:" framing.
 *   - No icons (Lucide / Heroicons / emoji — banned).
 *   - No spinners. No hover-scale. No card shadows. No purple gradients.
 *   - All color/type tokens come from the locked Tailwind config.
 */

import { motion, useReducedMotion } from 'framer-motion';
import { useEffect, useMemo, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types — mirror agents/wire/types.py (TypedDict WireEvent)
// ---------------------------------------------------------------------------

export type AgentId =
  | 'editor'
  | 'scout_desk'
  | 'investigator'
  | 'equity_editor'
  | 'storyteller'
  | 'narrator'
  | 'publish_gate';

export type SubAgentId = 'cinderella' | 'comeback' | 'hometown' | 'echo';

export type MessageType = 'thinking' | 'milestone' | 'intervention' | 'decision';

export type Mode = 'live' | 'replay' | 'published';

export type VisualTreatment = 'normal' | 'highlighted' | 'intervention';

export interface NilRedactionLog {
  direct_matches_redacted: number;
  aggregations_applied: number;
}

export interface StreamingProfile {
  agent: string;
  base_chars_per_second: number;
  jitter: number;
  mid_message_pause_chance: number;
  pause_min_ms: number;
  pause_max_ms: number;
  arrival_style: 'streamed' | 'instant';
}

export interface WireEventProps {
  id: string;
  timestamp: string; // ISO 8601
  agent: AgentId;
  sub_agent?: SubAgentId;
  message: string;
  message_type: MessageType;
  confidence?: number;
  story_unit_id?: string;
  mode?: Mode;
  visual_treatment?: VisualTreatment;
  compression_factor?: number;
  nil_redaction_log?: NilRedactionLog;
  // Streaming control
  isLive?: boolean;
  streamingProfile?: StreamingProfile;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  editor: 'Editor',
  scout_desk: 'Scout Desk',
  investigator: 'Investigator',
  equity_editor: 'Equity Editor',
  storyteller: 'Storyteller',
  narrator: 'Narrator',
  publish_gate: 'Publish Gate',
};

const SUB_AGENT_DISPLAY_NAMES: Record<SubAgentId, string> = {
  cinderella: 'Cinderella Scout',
  comeback: 'Comeback Scout',
  hometown: 'Hometown Scout',
  echo: 'Echo Scout',
};

const MESSAGE_TYPE_TAG: Record<MessageType, string> = {
  thinking: 'thinking',
  milestone: 'milestone',
  intervention: 'intervention',
  decision: 'decision',
};

/** Render an ISO 8601 timestamp as HH:MM:SS in 24-hour. */
function formatHHMMSS(iso: string): string {
  // Tolerate bad input — the Wire never crashes on a malformed ts.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '--:--:--';
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  const ss = d.getSeconds().toString().padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

/** Render the NIL redaction log as a compact mono badge: `[NIL: 2r/1a]`. */
function formatNilBadge(log: NilRedactionLog | undefined): string | null {
  if (!log) return null;
  const r = log.direct_matches_redacted ?? 0;
  const a = log.aggregations_applied ?? 0;
  if (r === 0 && a === 0) return null;
  return `[NIL: ${r}r/${a}a]`;
}

// ---------------------------------------------------------------------------
// Easing — cubic-bezier(0.32, 0.72, 0, 1) per design-system.md §5.3
// ---------------------------------------------------------------------------

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

// ---------------------------------------------------------------------------
// Typewriter hook — RAF-driven state machine.
//
// Per spec (§5 streaming cognition speed):
//   - Each character lands at 1000 / base_chars_per_second ms with
//     ±jitter * 100% random variance.
//   - With mid_message_pause_chance probability per char, insert a
//     longer pause of pause_min_ms..pause_max_ms.
//   - Use requestAnimationFrame, NOT setInterval (interval drift is
//     visible at the 4-8s ambient cadence).
//   - prefers-reduced-motion → instant render.
// ---------------------------------------------------------------------------

interface TypewriterArgs {
  fullText: string;
  profile: StreamingProfile;
  enabled: boolean; // false → render the whole string immediately
}

interface TypewriterState {
  visible: string;
  done: boolean;
}

function useTypewriter({ fullText, profile, enabled }: TypewriterArgs): TypewriterState {
  const [visible, setVisible] = useState<string>(enabled ? '' : fullText);
  const [done, setDone] = useState<boolean>(!enabled);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // If streaming is disabled (replay, instant arrival, reduced motion),
    // paint the full message immediately and bail.
    if (!enabled) {
      setVisible(fullText);
      setDone(true);
      return;
    }

    // Reset state when a new event arrives.
    setVisible('');
    setDone(false);

    const cps = Math.max(profile.base_chars_per_second, 1);
    const baseDelayMs = 1000 / cps;
    const jitter = Math.max(0, profile.jitter);
    const pauseChance = Math.max(0, profile.mid_message_pause_chance);
    const pauseMin = Math.max(0, profile.pause_min_ms);
    const pauseMax = Math.max(pauseMin, profile.pause_max_ms);

    let cancelled = false;
    let charIndex = 0;
    let nextLandAt = performance.now();

    // Compute the delay until the next character should land.
    const computeNextDelay = (): number => {
      // ±jitter * 100% per-char variance, multiplicative.
      const jitterMultiplier = 1 + (Math.random() * 2 - 1) * jitter;
      let delay = baseDelayMs * jitterMultiplier;
      // Roll for a mid-message pause beat.
      if (Math.random() < pauseChance) {
        const pauseMs = pauseMin + Math.random() * (pauseMax - pauseMin);
        delay += pauseMs;
      }
      return Math.max(0, delay);
    };

    nextLandAt = performance.now() + computeNextDelay();

    const tick = (now: number) => {
      if (cancelled) return;

      // Advance one character per landed-deadline. A single RAF tick can
      // catch up multiple chars if the tab was throttled.
      while (now >= nextLandAt && charIndex < fullText.length) {
        charIndex += 1;
        nextLandAt += computeNextDelay();
      }

      // Commit visible substring once per RAF (prevents thrash on long text).
      setVisible(fullText.slice(0, charIndex));

      if (charIndex >= fullText.length) {
        setDone(true);
        rafRef.current = null;
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // Re-run whenever the message identity or streaming params change.
  }, [
    fullText,
    enabled,
    profile.base_chars_per_second,
    profile.jitter,
    profile.mid_message_pause_chance,
    profile.pause_min_ms,
    profile.pause_max_ms,
  ]);

  return { visible, done };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WireRow(props: WireEventProps) {
  const {
    timestamp,
    agent,
    sub_agent,
    message,
    message_type,
    mode = 'live',
    nil_redaction_log,
    isLive = false,
    streamingProfile,
  } = props;

  const reduceMotion = useReducedMotion();

  // ---- Decide whether to typewriter-stream this row -----------------------
  // Per spec: only thinking + isLive + streamed arrival_style + not replay.
  const profile: StreamingProfile = streamingProfile ?? FALLBACK_PROFILE;
  const isInstantArrival = profile.arrival_style === 'instant';
  const isReplay = mode === 'replay' || mode === 'published';
  const shouldStream =
    message_type === 'thinking' &&
    isLive &&
    !isInstantArrival &&
    !isReplay &&
    !reduceMotion;

  const { visible } = useTypewriter({
    fullText: message,
    profile,
    enabled: shouldStream,
  });

  // ---- Visual variant flags ----------------------------------------------
  const isEditor = agent === 'editor';
  const isEquity = agent === 'equity_editor';
  const isIntervention = message_type === 'intervention';
  const isMilestone = message_type === 'milestone';
  const isDecision = message_type === 'decision';

  const nilBadge = useMemo(() => formatNilBadge(nil_redaction_log), [nil_redaction_log]);
  const formattedTime = useMemo(() => formatHHMMSS(timestamp), [timestamp]);
  const ariaLabel = `${
    sub_agent ? SUB_AGENT_DISPLAY_NAMES[sub_agent] : AGENT_DISPLAY_NAMES[agent]
  } — ${MESSAGE_TYPE_TAG[message_type]} — ${formattedTime}`;

  // ---- Mount entry animation (design-system.md §4 / §5) -------------------
  // initial: opacity 0, y 8, blur 2px → animate to settled, 200ms, room ease.
  const entryInitial = reduceMotion
    ? { opacity: 1, y: 0, filter: 'blur(0px)' }
    : { opacity: 0, y: 8, filter: 'blur(2px)' };
  const entryAnimate = { opacity: 1, y: 0, filter: 'blur(0px)' };

  // ---- Intervention pulse (mount-only, 600ms) -----------------------------
  // Gold-warm ring for non-Equity, agitos-red for Equity. Implemented as an
  // absolutely-positioned overlay div that fades from full to zero, so it
  // never intrudes on layout.
  const pulseColor = isEquity ? 'rgba(200, 16, 46, 0.85)' : 'rgba(212, 168, 74, 0.85)';

  // ---- Body text class composition ---------------------------------------
  // - default: wire-text (slightly desaturated cream)
  // - milestone: cream (slightly brighter)
  // - decision: medium weight bump
  const bodyToneClass = isMilestone ? 'text-cream' : 'text-wire-text';
  const bodyWeightClass = isDecision ? 'font-medium' : 'font-normal';

  // ---- Timestamp tone -----------------------------------------------------
  const timestampTone = isEditor ? 'text-gold-warm' : 'text-wire-time';

  // ---- Sub-agent recess (responsive per design-system.md §4) -------------
  // Spec calls for 24px indent on the sub-agent body. On tablet portrait we
  // compress to 20px; on mobile (375×812) we compress to 16px so the body
  // measure stays legible inside the narrowed container padding. Tradeoff
  // documented per worker prompt: visual sub-scout grouping is still clear
  // because the tracked-small-cap sub-agent label sits above the body.
  const bodyIndentClass = sub_agent ? 'pl-4 sm:pl-5 md:pl-6' : '';

  return (
    <motion.article
      role="article"
      aria-label={ariaLabel}
      data-agent={agent}
      data-sub-agent={sub_agent ?? ''}
      data-message-type={message_type}
      initial={entryInitial}
      animate={entryAnimate}
      transition={{ duration: 0.2, ease: ROOM_EASE }}
      className={[
        'relative w-full',
        'min-h-[56px]',
        'py-3',
        // Equity Editor row: 2px agitos-red left edge accent. Never paint
        // the entire row red.
        isEquity ? 'border-l-2 border-agitos-red pl-4' : 'pl-2',
      ].join(' ')}
    >
      {/* Intervention pulse overlay — 600ms ring fade from edge inward.
          Pointer-events:none so it never blocks interaction. */}
      {isIntervention && !reduceMotion && (
        <motion.div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          initial={{
            opacity: 0.9,
            boxShadow: `inset 0 0 0 2px ${pulseColor}`,
          }}
          animate={{
            opacity: 0,
            boxShadow: `inset 0 0 0 0px ${pulseColor}`,
          }}
          transition={{ duration: 0.6, ease: ROOM_EASE }}
        />
      )}

      {/* ---- Header row -------------------------------------------------- */}
      {/* Mobile tradeoff (design-system.md §4): on the iPhone breakpoint the
          right-gutter caption tag is allowed to wrap to its own line under
          the left cluster (flex-wrap) — the three-tier hierarchy is still
          intact (timestamp + agent / caption / hairline / body), the right
          gutter is just folded into a stacked second line so the agent name
          is never truncated. From sm: upward the caption returns to the
          right gutter as the canonical broadcast graphic intends. */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 sm:flex-nowrap">
        <div className="flex items-baseline gap-2 min-w-0">
          {/* Timestamp — JetBrains Mono, tabular-nums for ticking stability */}
          <span
            className={[
              'font-mono',
              'text-mono-sm',
              'tabular-nums',
              'whitespace-nowrap',
              timestampTone,
            ].join(' ')}
          >
            {formattedTime}
          </span>

          {/* NIL redaction badge — appears immediately right of timestamp.
              The trust-signal-at-a-glance for the Publish Gate. */}
          {nilBadge && (
            <span
              className="font-mono text-mono-sm text-slate-room whitespace-nowrap"
              aria-label={`NIL redaction log: ${nil_redaction_log?.direct_matches_redacted ?? 0} direct redactions, ${nil_redaction_log?.aggregations_applied ?? 0} aggregations`}
            >
              {nilBadge}
            </span>
          )}

          {/* Vertical bar separator */}
          <span aria-hidden="true" className="text-navy-light font-mono text-mono-sm">
            │
          </span>

          {/* Agent name — Lora italic */}
          <span className="font-italic italic text-italic-sm text-cream truncate">
            {AGENT_DISPLAY_NAMES[agent]}
          </span>
        </div>

        {/* Message-type tag — small caps, slate-room, tracked */}
        <span
          className={[
            'font-body',
            'text-caption',
            'uppercase',
            'tracking-[0.12em]',
            'text-slate-room',
            'whitespace-nowrap',
            'shrink-0',
          ].join(' ')}
        >
          {MESSAGE_TYPE_TAG[message_type]}
        </span>
      </div>

      {/* ---- Sub-agent name (recessed under parent) --------------------- */}
      {/* Indent matches body (responsive per design-system.md §4): 16px /
          20px / 24px at sm / md+ — keeps the sub-scout grouping aligned
          with its body at every viewport. */}
      {sub_agent && (
        <div className="mt-0.5 pl-4 sm:pl-5 md:pl-6">
          <span
            className={[
              'font-body',
              'text-caption',
              'uppercase',
              'tracking-[0.18em]',
              'text-slate-room',
            ].join(' ')}
          >
            {SUB_AGENT_DISPLAY_NAMES[sub_agent]}
          </span>
        </div>
      )}

      {/* ---- Hairline rule — 1px gold-warm/80, 80% width ---------------- */}
      <div
        aria-hidden="true"
        className="my-2 h-px w-4/5 bg-gold-warm/80"
      />

      {/* ---- Body — body-md, leading 1.7, wire-text-on-navy ------------- */}
      <div
        className={[
          'font-body',
          'text-body-md',
          'leading-[1.7]',
          bodyToneClass,
          bodyWeightClass,
          bodyIndentClass,
        ].join(' ')}
      >
        {shouldStream ? (
          <>
            {visible}
            {/* No blinking cursor — would read as terminal-emulator chrome,
                not a broadcast graphic. The cadence is the cue. */}
          </>
        ) : (
          message
        )}
      </div>
    </motion.article>
  );
}

// ---------------------------------------------------------------------------
// Fallback profile — if no streamingProfile is supplied (e.g. an unknown
// agent slipped through), default to a sensible mid-rate streamed profile
// (~30 cps, light jitter, modest pause chance) per spec.
// ---------------------------------------------------------------------------

const FALLBACK_PROFILE: StreamingProfile = {
  agent: 'fallback',
  base_chars_per_second: 30,
  jitter: 0.15,
  mid_message_pause_chance: 0.15,
  pause_min_ms: 150,
  pause_max_ms: 350,
  arrival_style: 'streamed',
};

export default WireRow;
