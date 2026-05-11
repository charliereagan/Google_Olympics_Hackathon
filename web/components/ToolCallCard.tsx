'use client';

/**
 * <ToolCallCard /> — bottom-right Floor card showing one dispatch tool call.
 *
 * BUILD_SPEC §9.4: when an agent calls a tool, a card slides in from the
 * right, persists ~3s, then fades out. design-system.md §4: 240px wide,
 * navy-mid fill, single gold-warm hairline rule on top, mono-sm content.
 *
 * Day-7 simplification (per worker brief): we synthesize one card per
 * agent handoff (rather than tracking real tool-call lifecycles). The
 * card reads as "running" for ~600ms (long enough to see the dot pulse),
 * then "complete" until the parent's AnimatePresence removes it at ~3s.
 *
 * Visual register: editorial dispatch slip. Not a Slack toast, not a
 * SaaS success-snackbar — a tracked-cap broadcast credit. The status dot
 * is the only color signal; the rest stays mono + cream.
 */

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import type { AgentHandoffEvent } from '@/lib/agent-floor-fixture';
import { AGENT_BY_ID, toolDisplayName, EQUITY_INTERVENE_TOOL_CALL } from '@/lib/agent-floor-fixture';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

interface ToolCallCardProps {
  handoff: AgentHandoffEvent;
}

export function ToolCallCard({ handoff }: ToolCallCardProps) {
  // Cards arrive "running"; flip to "complete" after a short beat so the
  // viewer sees the dot transition before the card fades. The 3s lifetime
  // and unmount is owned by the parent's AnimatePresence.
  const [status, setStatus] = useState<'running' | 'complete'>('running');
  useEffect(() => {
    const t = window.setTimeout(() => setStatus('complete'), 700);
    return () => window.clearTimeout(t);
  }, []);

  const from = AGENT_BY_ID[handoff.from_agent];
  const to = AGENT_BY_ID[handoff.to_agent];
  const isIntervention =
    handoff.tool_call_id === EQUITY_INTERVENE_TOOL_CALL &&
    handoff.from_agent === 'equity_editor';

  // Status dot color: running → from-agent color; complete → gold-warm.
  // Intervention cards stay agitos-red the whole way through.
  const dotRgb = isIntervention
    ? '200, 16, 46'
    : status === 'running'
      ? from.rgb
      : '212, 168, 74';

  return (
    <motion.div
      layout
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 40, opacity: 0 }}
      transition={{ duration: 0.42, ease: ROOM_EASE }}
      className="pointer-events-auto w-full border-t border-gold-warm/60 bg-navy-mid/95 px-4 py-3 sm:w-[260px]"
      role="status"
      aria-label={`${from.label} dispatched ${toolDisplayName(handoff.tool_call_id)} to ${to.label}`}
    >
      <div className="flex items-center justify-between">
        <p
          className="font-mono text-mono-sm uppercase text-cream"
          style={{ letterSpacing: '0.14em' }}
        >
          {toolDisplayName(handoff.tool_call_id)}
        </p>
        <span
          aria-hidden="true"
          className="ml-3 inline-block h-2 w-2 rounded-full"
          style={{
            backgroundColor: `rgba(${dotRgb}, ${status === 'running' ? 0.95 : 0.7})`,
            boxShadow:
              status === 'running'
                ? `0 0 6px rgba(${dotRgb}, 0.8)`
                : 'none',
            transition: 'background-color 240ms cubic-bezier(0.32, 0.72, 0, 1), box-shadow 240ms',
          }}
        />
      </div>
      <p className="mt-1.5 font-mono text-caption uppercase text-slate-room" style={{ letterSpacing: '0.16em' }}>
        {from.label} <span className="text-gold-warm/70">·</span> {to.label}
      </p>
      <p className="mt-2 font-body text-body-sm text-wire-text">
        {status === 'running' ? 'dispatching…' : isIntervention ? 'parity hold — feed drift caught' : 'handoff complete'}
      </p>
    </motion.div>
  );
}

export default ToolCallCard;
