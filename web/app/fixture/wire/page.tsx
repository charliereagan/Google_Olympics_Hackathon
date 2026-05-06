/**
 * Static fixture page for Day-8 pass-1 design review of <WireRow>.
 *
 * Renders ~12 sample rows showcasing every variant of the canonical
 * broadcast graphic so the HoE can capture screenshots for review.
 *
 * Spec sources:
 *   - Docs/Engineering/design-system.md §4 + §8 (component spec)
 *   - Docs/Engineering/BUILD_SPEC.md §6 (full Wire spec)
 *   - CONSTITUTION.md §5 (Wire rules)
 *
 * NIL-compliance: only synthetic place names — Mount Pleasant, Birmingham,
 * Eastern Sierra. No individual Team USA athletes are named anywhere in
 * the fixture data (per CONSTITUTION §5 and §8 Kill List).
 */

import { Layout } from '@/components/Layout';
import { WireRow, type WireEventProps } from '@/components/WireRow';
import { getStreamingProfile } from '@/lib/streaming-profiles';

// ---------------------------------------------------------------------------
// Fixture data — 12 rows. Timestamps are synthetic (T+0 baseline, ticking
// up). All `mode: 'live'` so the typewriter effect is visible to the HoE
// during screenshot capture (per worker prompt).
// ---------------------------------------------------------------------------

const T0 = new Date('2026-05-02T17:42:00Z');
const ts = (offsetSec: number): string =>
  new Date(T0.getTime() + offsetSec * 1000).toISOString();

type FixtureRow = Omit<WireEventProps, 'streamingProfile'> & {
  // We resolve the profile at render time from the lib helper.
  resolveProfile?: boolean;
};

const FIXTURE_ROWS: FixtureRow[] = [
  // 1. Editor + decision
  {
    id: 'evt-001',
    timestamp: ts(33),
    agent: 'editor',
    message: 'Going with Mount Pleasant. Investigator, 90 seconds.',
    message_type: 'decision',
    mode: 'live',
    isLive: true,
  },
  // 2. Editor + milestone
  {
    id: 'evt-002',
    timestamp: ts(58),
    agent: 'editor',
    message: 'Story published. Stack updated.',
    message_type: 'milestone',
    mode: 'live',
    isLive: true,
  },
  // 3. Cinderella Scout (sub-scout) + thinking + isLive (typewriter)
  {
    id: 'evt-003',
    timestamp: ts(7),
    agent: 'scout_desk',
    sub_agent: 'cinderella',
    message: 'scanning Iowa hometown signals... wait, the timing is off...',
    message_type: 'thinking',
    mode: 'live',
    isLive: true,
  },
  // 4. Comeback Scout + thinking
  {
    id: 'evt-004',
    timestamp: ts(12),
    agent: 'scout_desk',
    sub_agent: 'comeback',
    message: "this town disappeared from the rosters in 1996. they're back.",
    message_type: 'thinking',
    mode: 'live',
    isLive: true,
  },
  // 5. Hometown Scout + thinking
  {
    id: 'evt-005',
    timestamp: ts(15),
    agent: 'scout_desk',
    sub_agent: 'hometown',
    message: 'population 8,500, one stoplight',
    message_type: 'thinking',
    mode: 'live',
    isLive: true,
  },
  // 6. Echo Scout + thinking + slow typewriter
  {
    id: 'evt-006',
    timestamp: ts(20),
    agent: 'scout_desk',
    sub_agent: 'echo',
    message: 'this echoes the pre-war track-and-field era',
    message_type: 'thinking',
    mode: 'live',
    isLive: true,
  },
  // 7. Investigator + milestone
  {
    id: 'evt-007',
    timestamp: ts(26),
    agent: 'investigator',
    message:
      'Eight Olympians and Paralympians from this town since 1976. Verified via Olympedia and Team USA roster.',
    message_type: 'milestone',
    mode: 'live',
    isLive: true,
  },
  // 8. Equity Editor + intervention (instant arrival, agitos-red left edge)
  {
    id: 'evt-008',
    timestamp: ts(31),
    agent: 'equity_editor',
    message:
      'Feed drift detected. Last 4 places Olympic-heavy. Promoting Paralympic-anchored lead next.',
    message_type: 'intervention',
    mode: 'live',
    isLive: true,
    visual_treatment: 'intervention',
  },
  // 9. Storyteller + thinking
  {
    id: 'evt-009',
    timestamp: ts(40),
    agent: 'storyteller',
    message: 'opening on the place',
    message_type: 'thinking',
    mode: 'live',
    isLive: true,
  },
  // 10. Narrator + milestone
  {
    id: 'evt-010',
    timestamp: ts(75),
    agent: 'narrator',
    message: 'audio rendered, 89s, narration ready',
    message_type: 'milestone',
    mode: 'live',
    isLive: true,
  },
  // 11. Publish Gate + milestone with NIL log (the trust-signal moment)
  {
    id: 'evt-011',
    timestamp: ts(85),
    agent: 'publish_gate',
    message:
      '14 claims checked, 2 removed, NIL Redaction passed, cleared.',
    message_type: 'milestone',
    mode: 'live',
    isLive: true,
    nil_redaction_log: {
      direct_matches_redacted: 2,
      aggregations_applied: 1,
    },
  },
  // 12. High Narrative Density milestone (Scout Desk parent, no sub_agent)
  {
    id: 'evt-012',
    timestamp: ts(22),
    agent: 'scout_desk',
    message:
      'High Narrative Density: cinderella + comeback + hometown on the same place.',
    message_type: 'milestone',
    mode: 'live',
    isLive: true,
  },
];

// Sort rows by timestamp ascending so the Wire reads as a real session.
const ORDERED_ROWS: FixtureRow[] = [...FIXTURE_ROWS].sort((a, b) =>
  a.timestamp.localeCompare(b.timestamp),
);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function WireFixturePage() {
  return (
    <Layout>
      <article className="mx-auto max-w-[720px] px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        {/* Header — design-system review labeling */}
        <header className="mb-8 border-b border-navy-light pb-6 sm:mb-12">
          <p className="mb-2 font-body text-caption uppercase text-gold-warm">
            wire row · day 8 · pass 1
          </p>
          <h1 className="font-display text-display-md text-cream">
            <em className="font-italic">The Wire.</em>
          </h1>
          <p className="mt-3 font-italic italic text-italic-md text-wire-text">
            Twelve sample rows. Every variant. Mount Pleasant, Iowa &mdash;
            synthetic.
          </p>
          <p className="mt-3 font-body text-body-sm text-slate-room">
            Thinking rows stream at the agent&rsquo;s cognition speed
            (design-system.md §5). Equity Editor arrives instant with an
            agitos-red left-edge accent and a 600ms intervention pulse on
            mount.
          </p>
        </header>

        {/* The Wire — narrow column, editorial measure, top-down feed.
            Rows are separated by a thin navy-light divider so each event's
            anatomy is unambiguous to the reviewer. */}
        <section
          aria-label="Wire stream — fixture sample"
          className="divide-y divide-navy-light"
        >
          {ORDERED_ROWS.map((row) => (
            <WireRow
              key={row.id}
              {...row}
              streamingProfile={getStreamingProfile(row.agent, row.sub_agent)}
            />
          ))}
        </section>

        {/* Footer — review trail */}
        <footer className="mt-12 border-t border-navy-light pt-6 sm:mt-20">
          <p className="font-body text-caption uppercase text-slate-room">
            wire row spec · design-system.md §4 + §8 · build_spec §6
          </p>
        </footer>
      </article>
    </Layout>
  );
}
