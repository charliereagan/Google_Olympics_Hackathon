'use client';

/**
 * <WirePageBody /> — the client tail of /wire below the static header.
 *
 * Owns:
 *   - The persistent left-column legend card ("WHAT YOU'RE LOOKING AT" +
 *     THE AGENTS table). Sticky on desktop so it stays in view as the
 *     feed scrolls; stacks above the feed on mobile via normal flow.
 *   - The filter pill row (ALL / EDITOR / SCOUTS / INVESTIGATOR /
 *     EQUITY EDITOR / STORYTELLER / NARRATOR / PUBLISH GATE). Updates
 *     the URL `?agent=` query param so a filtered view is shareable.
 *   - The <WireFeed /> itself, filtered by the active pill.
 *
 * Server header lives in app/wire/page.tsx so the title / dek render in
 * the initial HTML and judges see something on first paint even before
 * hydration. Everything that needs URL state lives here.
 */

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useMemo } from 'react';
import WireFeed from '@/components/WireFeed';
import {
  AGENT_DISPLAY_NAMES,
  AGENT_MODEL_LABEL,
  WIRE_FILTER_PILLS,
  type WireFilterId,
} from '@/lib/agent-models';

function isFilterId(value: string | null): value is WireFilterId {
  if (!value) return false;
  return WIRE_FILTER_PILLS.some((p) => p.id === value);
}

/**
 * The seven-agent legend table. Each row maps an agent to its Gemini
 * model + role. Same roster as /floor. Source of truth for what runs
 * the room.
 */
const LEGEND_ROWS: ReadonlyArray<{ name: string; model: string; role: string }> = [
  { name: AGENT_DISPLAY_NAMES.editor, model: AGENT_MODEL_LABEL.editor, role: 'Orchestrator' },
  { name: 'Scout Desk', model: 'Gemini 3 Flash x4', role: 'Lead-finders (Cinderella, Comeback, Hometown, Echo)' },
  { name: AGENT_DISPLAY_NAMES.investigator, model: AGENT_MODEL_LABEL.investigator, role: 'Source verification + Investigation Packets' },
  { name: AGENT_DISPLAY_NAMES.equity_editor, model: AGENT_MODEL_LABEL.equity_editor, role: 'Parity enforcement (veto)' },
  { name: AGENT_DISPLAY_NAMES.storyteller, model: AGENT_MODEL_LABEL.storyteller, role: 'Literary drafts' },
  { name: AGENT_DISPLAY_NAMES.narrator, model: AGENT_MODEL_LABEL.narrator, role: 'Broadcast voice (Algenib)' },
  { name: AGENT_DISPLAY_NAMES.publish_gate, model: AGENT_MODEL_LABEL.publish_gate, role: '7-stage audit including NIL Redaction' },
];

export default function WirePageBody() {
  const searchParams = useSearchParams();
  const filterParam = searchParams?.get('agent') ?? null;
  const activeFilter: WireFilterId = isFilterId(filterParam) ? filterParam : 'all';

  /**
   * Build pill links. `?agent=all` collapses to no query param so the
   * canonical /wire URL stays clean for the default view.
   */
  const pills = useMemo(
    () =>
      WIRE_FILTER_PILLS.map((p) => ({
        id: p.id,
        label: p.label,
        href: p.id === 'all' ? '/wire' : `/wire?agent=${p.id}`,
        active: p.id === activeFilter,
      })),
    [activeFilter],
  );

  return (
    <div className="grid grid-cols-1 gap-8 sm:grid-cols-12 sm:gap-10">
      {/* Legend card — left column on desktop, stacks on mobile. Sticky
          on desktop so the agent roster stays visible as the feed
          scrolls. Width ~30% of the row via 4/12 grid columns. */}
      <aside
        aria-label="What you're looking at"
        className="sm:col-span-4 sm:sticky sm:top-[10vh] sm:self-start"
      >
        <div className="border border-gold-warm/40 bg-navy-mid/85 px-5 py-5 sm:px-6 sm:py-6">
          <p
            className="font-mono text-mono-sm uppercase text-parchment"
            style={{ letterSpacing: '0.22em' }}
          >
            WHAT YOU&apos;RE LOOKING AT
          </p>
          <div aria-hidden="true" className="mt-3 h-px w-8 bg-gold-warm/60" />
          <p className="mt-4 font-italic italic text-[14px] leading-[1.55] text-parchment/90">
            The raw working-room feed of seven Gemini agents orchestrated
            by Google&apos;s Agent Development Kit (ADK). Every thought,
            every handoff, every decision the room makes &mdash; in the
            order it happens.
          </p>
          <p className="mt-3 font-italic italic text-[14px] leading-[1.55] text-parchment/90">
            The ambient ticker on every page shows the curated highlights.
            This page shows everything.
          </p>

          <p
            className="mt-6 font-mono text-mono-sm uppercase text-gold-warm"
            style={{ letterSpacing: '0.22em' }}
          >
            THE AGENTS
          </p>
          <div aria-hidden="true" className="mt-2 h-px w-8 bg-gold-warm/60" />
          <ul className="mt-3 space-y-3">
            {LEGEND_ROWS.map((row) => (
              <li key={row.name}>
                <p className="font-mono text-mono-sm uppercase text-cream tracking-[0.04em]">
                  {row.name}
                </p>
                <p className="mt-0.5 font-mono text-mono-sm uppercase text-wire-time tracking-[0.04em]">
                  {row.model}
                </p>
                <p className="mt-0.5 font-italic italic text-[12px] leading-[1.5] text-parchment/80">
                  {row.role}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Feed column — filter pills + WireFeed. */}
      <div className="sm:col-span-8">
        {/* Filter pills — VPS Addition 4. URL-driven so a filtered view
            is shareable. Active pill rendered with a gold underline. */}
        <nav
          aria-label="Filter the Wire by agent"
          className="mb-6 flex flex-wrap items-baseline gap-x-1 gap-y-2"
        >
          {pills.map((pill, idx) => (
            <span key={pill.id} className="inline-flex items-baseline">
              {idx > 0 && (
                <span aria-hidden="true" className="mx-1 text-gold-warm/40">
                  &middot;
                </span>
              )}
              <Link
                href={pill.href}
                className={[
                  'font-mono text-mono-sm uppercase tracking-[0.18em]',
                  pill.active
                    ? 'text-gold-warm border-b border-gold-warm pb-0.5'
                    : 'text-parchment/70 hover:text-cream',
                ].join(' ')}
              >
                {pill.label}
              </Link>
            </span>
          ))}
        </nav>

        <WireFeed agentFilter={activeFilter} />
      </div>
    </div>
  );
}
