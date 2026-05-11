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
import { TechStackStrip } from './TechStackStrip';

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

/**
 * Map the persisted past-tense NilDecisionStatus to the imperative
 * decision-label spec (PASS / REDACT / AGGREGATE / RETURN / REVISE / BLOCK)
 * the VPS treatment asks for. Static table, no synthesis. The fixture
 * status set today is PASS / REDACTED / DISAMBIGUATED / AGGREGATED /
 * RETURNED — REVISE and BLOCK exist in the spec but no fixture row uses
 * them yet, so they're listed here for future-proofing only.
 *
 * Color discipline:
 *   - PASS                 → text-gold-warm   (cleared / no intervention)
 *   - REDACT / AGGREGATE   → text-gold-warm   (the Layer acted; clean outcome)
 *   - DISAMBIGUATE         → text-parchment   (resolved an ambiguity)
 *   - RETURN / REVISE      → text-orange-300  (sent back for rework)
 *   - BLOCK                → text-agitos-red  (final negative decision)
 *
 * "orange-300" is not in the Tailwind palette this project uses; the
 * design tokens that survive review are gold-warm, agitos-red, parchment,
 * cream, wire-text, slate-room. Per the worker prompt ("Do NOT introduce
 * a new color token") RETURN/REVISE map to a slightly desaturated cream
 * (text-cream/70) — readable but visually subordinate to BLOCK red and
 * to the gold-warm Layer-acted family.
 */
function decisionLabel(status: NilDecisionStatus): string {
  switch (status) {
    case 'PASS':
      return 'PASS';
    case 'REDACTED':
      return 'REDACT';
    case 'AGGREGATED':
      return 'AGGREGATE';
    case 'DISAMBIGUATED':
      return 'DISAMBIG.';
    case 'RETURNED':
      return 'RETURN';
    default:
      return status;
  }
}

function decisionToneClass(status: NilDecisionStatus): string {
  switch (status) {
    case 'RETURNED':
      return 'text-cream/70';
    case 'DISAMBIGUATED':
      return 'text-parchment';
    case 'PASS':
    case 'REDACTED':
    case 'AGGREGATED':
    default:
      return 'text-gold-warm';
  }
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
        className={`font-mono text-mono-sm uppercase tracking-[0.18em] md:col-span-2 ${decisionToneClass(decision.status)}`}
      >
        {decisionLabel(decision.status)}
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
    <>
      <article className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16 md:px-8 md:py-20">
        <header>
          <p
            className="font-mono text-mono-sm uppercase text-wire-time"
            style={{ letterSpacing: '0.22em' }}
          >
            BEHIND THE SCENES
          </p>
          <div aria-hidden="true" className="mt-2 h-px w-8 bg-gold-warm/40" />
          <p className="mt-4 font-body text-caption uppercase tracking-[0.18em] text-gold-warm">
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

        {/* Framing card — VPS § "/publish-gate · Three additions" Addition 1.
            Sits between the dek and the big-number bar. Italic Lora on
            bg-navy-mid/85 card with gold hairline. The final sentence
            "Compliance, made structural by Google's Agent Development Kit.
            The constraint became the credibility flex." is the page's thesis
            and is set in a slightly larger / cream-bright treatment to land
            as such. */}
        <aside
          aria-label="Why this page exists"
          className="mt-10 border border-gold-warm/40 bg-navy-mid/85 px-6 py-6 sm:px-8 sm:py-7"
        >
          <p
            className="font-mono text-mono-sm uppercase text-parchment"
            style={{ letterSpacing: '0.22em' }}
          >
            WHY THIS PAGE EXISTS
          </p>
          <div aria-hidden="true" className="mt-3 h-px w-8 bg-gold-warm/60" />
          <p className="mt-4 font-italic italic text-[15px] leading-[1.6] text-parchment/90">
            The hackathon&apos;s strictest rule: no individual Team USA athlete
            may be named in user-facing output. Most submissions handle this
            with a content review at the end. We made it architecture.
          </p>
          <p className="mt-3 font-italic italic text-[15px] leading-[1.6] text-parchment/90">
            Every text the Storyteller writes passes through the NIL
            Redaction Layer &mdash; a Python module running between the
            Storyteller agent and any reader, querying an 11,188-entry
            athlete registry on every claim. Direct matches are redacted.
            Near-identifications are returned to the Storyteller for
            revision. Ambiguous tokens are disambiguated against context
            (see the trace below).
          </p>
          <p className="mt-4 font-italic italic text-[17px] leading-[1.55] text-cream">
            Compliance, made structural by Google&apos;s Agent Development
            Kit. The constraint became the credibility flex.
          </p>
        </aside>

        <AggregateStrip stats={stats} />

        {/* Disambiguation trace — VPS Addition 3 promotes this section
            ABOVE the Recent Decisions list because the trace is the
            strongest single piece of content on the page. Small section
            header (tracked-cap parchment, gold hairline below) sits above
            the DisambiguationTrace block; the trace component itself is
            unchanged. */}
        <section aria-labelledby="disambig-section-heading" className="mt-16 sm:mt-20">
          <p
            id="disambig-section-heading"
            className="font-mono text-mono-sm uppercase text-parchment"
            style={{ letterSpacing: '0.22em' }}
          >
            DISAMBIGUATION TRACE &middot; ONE AMBIGUOUS SPAN, FOUR STEPS, ONE CLEARED SENTENCE
          </p>
          <div aria-hidden="true" className="mt-3 h-px w-full bg-gold-warm/60" />
          <DisambiguationTrace />
        </section>

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

        <footer className="mt-20 border-t border-navy-light pt-6 sm:mt-24">
          <p className="font-mono text-mono-sm tracking-[0.02em] text-slate-room">
            athlete_registry: {footer.athlete_registry_size.toLocaleString('en-US')} entries
            &nbsp;&middot;&nbsp; last_updated: {footer.last_updated}
            &nbsp;&middot;&nbsp; matcher: {footer.matcher}
          </p>
        </footer>
      </article>

      {/* Tech-stack strip — VPS Optional Addition 4, promoted to required
          for cross-page consistency with /floor and /wire. Lives outside
          the max-w-4xl article so it can center on the full page width
          like /floor does. */}
      <TechStackStrip />
    </>
  );
}

export default PublishGatePanel;
