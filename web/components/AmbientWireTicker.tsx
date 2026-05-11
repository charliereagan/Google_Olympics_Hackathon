'use client';

/**
 * <AmbientWireTicker /> — the persistent 32px Wire ticker band.
 * VPS-DEC-041 + CONSTITUTION §11 ("Wire beginning to scroll").
 *
 * Production Deck routes only. Subscribes via useWireStream(); renders the
 * last 6 events as a CSS-marquee strip (60s linear loop, group-hover pauses,
 * no JS RAF). 32px tall, navy-mid fill, gold hairlines.
 *
 * VPS-DEC-054 (2026-05-11): consumer (FOH) routes no longer see this ticker;
 * they get <AmbientStoryTicker /> with late-breaking story headlines.
 * <AmbientTickerSwitch /> picks the right ticker by route. The PD audience
 * wants the full agent-named feed — no fan rewriting here.
 */

import { useMemo } from 'react';
import { useWireStream } from '@/lib/wire-stream-client';
import type { WireEvent, AgentId, SubAgentId } from '@/lib/wire-event';

// FILTER: ambient ticker shows ONLY milestone / intervention / decision
// events. Raw `thinking` events (engineering debug like "draft body word
// count out of bounds") stay visible on the dedicated /wire page but never
// leak onto the ambient strip, even on PD routes — the strip is meant to
// read as a heartbeat, not a debug stream.
const FAN_VISIBLE_TYPES = new Set(['milestone', 'intervention', 'decision']);

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
  cinderella: 'Cinderella',
  comeback: 'Comeback',
  hometown: 'Hometown',
  echo: 'Echo',
};

function formatHHMMSS(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '--:--:--';
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  const ss = d.getSeconds().toString().padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)).trimEnd() + '…';
}

function agentLabel(ev: WireEvent): string {
  if (ev.sub_agent && SUB_AGENT_DISPLAY_NAMES[ev.sub_agent]) {
    return SUB_AGENT_DISPLAY_NAMES[ev.sub_agent];
  }
  return AGENT_DISPLAY_NAMES[ev.agent] ?? ev.agent;
}

export function AmbientWireTicker() {
  const { events } = useWireStream();

  // Last 6 events of the visible types. Render order is kept deterministic
  // so the CSS animation doesn't reset on every push.
  const recent = useMemo<WireEvent[]>(() => {
    if (events.length === 0) return [];
    return events.filter((e) => FAN_VISIBLE_TYPES.has(e.message_type)).slice(-6);
  }, [events]);

  // Duplicate the list so the marquee loops seamlessly: when the first copy
  // scrolls fully off the left edge, the second copy is in identical
  // position, and the animation restart is invisible.
  const looped = useMemo(() => [...recent, ...recent], [recent]);

  return (
    <div
      role="complementary"
      aria-label="Ambient Wire activity"
      className="group relative w-full overflow-hidden border-b border-t border-gold-warm/40 bg-navy-mid"
      style={{ height: '32px' }}
    >
      {/* Marquee strip — group-hover pauses animation. */}
      {recent.length === 0 ? (
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
          {looped.map((ev, idx) => (
            <span
              key={`${ev.id}-${idx}`}
              className="inline-flex items-baseline gap-2 px-6"
            >
              <span className="font-mono text-mono-sm tabular-nums text-wire-time">
                {formatHHMMSS(ev.timestamp)}
              </span>
              <span aria-hidden="true" className="text-navy-light font-mono text-mono-sm">
                ·
              </span>
              <span className="font-italic italic text-italic-sm text-cream">
                {agentLabel(ev)}
              </span>
              <span aria-hidden="true" className="text-navy-light font-mono text-mono-sm">
                ·
              </span>
              <span className="font-body text-body-sm text-wire-text">
                {truncate(ev.message ?? '', 140)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Keyframes — pure CSS, no RAF. The width of one loop equals the
          width of the rendered events copy; we shift by 50% (one copy) so
          the second copy seamlessly takes over at the loop boundary. */}
      <style>{`
        @keyframes wire-marquee {
          0%   { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}

export default AmbientWireTicker;
