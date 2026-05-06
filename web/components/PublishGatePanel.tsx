'use client';

/**
 * <PublishGatePanel> — the Publish Gate trust panel (demo moment #5).
 *
 * The audit-trail surface: every claim, every redaction, every name
 * disambiguated. All hairline rules; mono-heavy; two-tone status (gold-warm
 * for cleared, agitos-red for blocking). No real Team USA athlete surnames
 * appear in any rendered string (PROJECT_BRIEF §6 NIL prohibition).
 */

import { useEffect, useMemo, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import {
  PUBLISH_GATE_FIXTURE_DECISIONS,
  PUBLISH_GATE_FIXTURE_FOOTER,
  PUBLISH_GATE_FIXTURE_STATS,
  type NilDecision,
  type NilDecisionStatus,
  type PublishGateAggregateStats,
  type PublishGateFooterMeta,
} from '@/lib/publish-gate-fixture';
import { DisambiguationTrace } from './DisambiguationTrace';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

interface RecentResponse {
  source: 'firestore' | 'fixture' | 'mixed';
  decisions: NilDecision[];
  stats: PublishGateAggregateStats;
  footer: PublishGateFooterMeta;
}

function formatHHMMSS(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '--:--:--';
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  const ss = d.getSeconds().toString().padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function truncateClaim(claim: string, max = 60): string {
  if (claim.length <= max) return claim;
  return `${claim.slice(0, max - 1)}…`;
}

function statusToneClass(status: NilDecisionStatus): string {
  if (status === 'REDACTED' || status === 'RETURNED') return 'text-agitos-red';
  if (status === 'DISAMBIGUATED') return 'text-parchment';
  return 'text-gold-warm';
}

function AggregateStrip({ stats }: { stats: PublishGateAggregateStats }) {
  const cells: Array<{ label: string; value: string }> = [
    { label: 'Claims checked', value: stats.total_claims.toLocaleString('en-US') },
    { label: 'Redactions performed', value: stats.total_redactions.toLocaleString('en-US') },
    { label: 'Disambiguation hits', value: stats.disambiguations.toLocaleString('en-US') },
    { label: 'Cleared / blocked', value: `${stats.stories_cleared} / ${stats.stories_blocked}` },
  ];
  return (
    <div className="mt-10 grid grid-cols-1 gap-y-8 sm:grid-cols-2 sm:gap-x-10 lg:grid-cols-4 lg:gap-x-0">
      {cells.map((cell, idx) => (
        <div
          key={cell.label}
          className={[
            'pl-0',
            // Hairline rule between columns at lg.
            idx > 0 ? 'lg:border-l lg:border-navy-light lg:pl-8' : 'lg:pl-0',
          ].join(' ')}
        >
          <p className="font-display text-display-md text-cream tabular-nums">
            {cell.value}
          </p>
          <p className="mt-2 font-body text-caption uppercase tracking-[0.18em] text-slate-room">
            {cell.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function DecisionRow({ decision, isFirst }: { decision: NilDecision; isFirst: boolean }) {
  const reduceMotion = useReducedMotion();
  const initial = reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 4 };
  return (
    <motion.li
      initial={initial}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: ROOM_EASE }}
      className={[
        'grid grid-cols-1 gap-y-2 py-5 md:grid-cols-12 md:gap-x-6',
        isFirst ? '' : 'border-t border-navy-light',
      ].join(' ')}
    >
      <p className="font-mono text-mono-sm leading-[1.55] text-gold-warm/70 md:col-span-6">
        {truncateClaim(decision.claim)}
      </p>
      <p
        className={`font-mono text-mono-sm uppercase tracking-[0.18em] md:col-span-2 ${statusToneClass(decision.status)}`}
      >
        {decision.status.toLowerCase()}
      </p>
      <p className="font-italic italic text-italic-sm leading-[1.55] text-wire-text md:col-span-3">
        {decision.reason}
      </p>
      <p className="font-mono text-mono-sm tabular-nums text-wire-time md:col-span-1 md:text-right">
        {formatHHMMSS(decision.timestamp)}
      </p>
    </motion.li>
  );
}

export function PublishGatePanel() {
  const [data, setData] = useState<RecentResponse>({
    source: 'fixture',
    decisions: PUBLISH_GATE_FIXTURE_DECISIONS,
    stats: PUBLISH_GATE_FIXTURE_STATS,
    footer: PUBLISH_GATE_FIXTURE_FOOTER,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/publish-gate/recent', { cache: 'no-store' });
        if (!res.ok) return;
        const body = (await res.json()) as RecentResponse;
        if (cancelled) return;
        if (Array.isArray(body.decisions) && body.decisions.length > 0) {
          setData(body);
        }
      } catch {
        // Keep fixture state — the panel always renders.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const { decisions, stats, footer, source } = data;

  const sourceLabel = useMemo(() => {
    switch (source) {
      case 'firestore':
        return 'live · firestore wire_events';
      case 'mixed':
        return 'live + fixture · mixed';
      case 'fixture':
      default:
        return 'fixture';
    }
  }, [source]);

  return (
    <article className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16 md:px-8 md:py-20">
      <header>
        <p className="font-body text-caption uppercase tracking-[0.18em] text-gold-warm">
          Publish Gate &middot; NIL Redaction Layer &middot; Audit
        </p>
        <h1 className="mt-4 font-display text-display-md text-cream sm:text-display-lg">
          What the room caught.
        </h1>
        <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text leading-[1.55]">
          Every claim, every redaction, every name disambiguated. The room shows its work.
        </p>
        <div aria-hidden="true" className="mt-8 h-px w-full bg-gold-warm/60" />
      </header>

      <AggregateStrip stats={stats} />

      <section aria-labelledby="recent-heading" className="mt-16 sm:mt-20">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <p id="recent-heading" className="font-body text-caption uppercase tracking-[0.18em] text-gold-warm">
            Recent decisions
          </p>
          <p className="font-mono text-mono-sm tracking-[0.02em] text-slate-room">{sourceLabel}</p>
        </div>
        <div aria-hidden="true" className="mt-4 h-px w-full bg-navy-light" />
        <ul className="mt-2">
          {decisions.map((decision, idx) => (
            <DecisionRow key={decision.id} decision={decision} isFirst={idx === 0} />
          ))}
        </ul>
        <div aria-hidden="true" className="mt-2 h-px w-full bg-navy-light" />
      </section>

      <DisambiguationTrace />

      <footer className="mt-20 border-t border-navy-light pt-6 sm:mt-24">
        <p className="font-mono text-mono-sm tracking-[0.02em] text-slate-room">
          athlete_registry: {footer.athlete_registry_size.toLocaleString('en-US')} entries
          &nbsp;&middot;&nbsp; last_updated: {footer.last_updated}
          &nbsp;&middot;&nbsp; matcher: {footer.matcher}
        </p>
      </footer>
    </article>
  );
}

export default PublishGatePanel;
