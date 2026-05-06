// Synthetic NIL Redaction Layer decision feed for the /publish-gate trust panel.
//
// FIXTURE-ONLY. There is no dedicated `nil_decisions` collection in this
// build; the only persisted NIL state lives on `wire_events.nil_redaction_log`
// (thin two-field record). The /api/publish-gate/recent route folds those
// sparse records into the richer NilDecision shape and falls back to this
// fixture when Firestore is unreachable or empty.
//
// PROJECT_BRIEF §6 (NIL prohibition) compliance: every name token below is a
// fictional placeholder (`[athlete:A]`, `[athlete:B]`, `[redacted]`) or a
// place name ("Mount Pleasant" — canonical place example from §0/§3).

export type NilDecisionStatus = 'PASS' | 'REDACTED' | 'DISAMBIGUATED' | 'AGGREGATED' | 'RETURNED';

export interface NilDecision {
  id: string;
  timestamp: string;
  surface: 'wire' | 'broadcast';
  claim: string;
  status: NilDecisionStatus;
  reason: string;
}

// Tuple form: [id, timestamp, surface, status, claim, reason]
type DecisionTuple = [string, string, NilDecision['surface'], NilDecisionStatus, string, string];

const _DECISIONS: DecisionTuple[] = [
  ['fx_001', '2026-05-05T14:22:08Z', 'broadcast', 'PASS', 'Eight Olympians and Paralympians from this town since 1976.', 'no surface matches; no near-identification; passed through'],
  ['fx_002', '2026-05-05T14:22:14Z', 'broadcast', 'PASS', 'The town\'s newest Olympian came up through the same school program.', 'place-level reference; no individual identification'],
  ['fx_003', '2026-05-05T14:22:21Z', 'wire', 'REDACTED', 'Surface match on candidate token at offset 47; word-boundary clean.', 'matched athlete registry entry; replaced with [redacted]'],
  ['fx_004', '2026-05-05T14:22:33Z', 'broadcast', 'DISAMBIGUATED', 'Mount Pleasant has produced a generation of Team USA athletes.', 'ambiguous surname token in candidate set; resolved as place reference (Iowa town, not [athlete:A])'],
  ['fx_005', '2026-05-05T14:22:41Z', 'broadcast', 'AGGREGATED', 'Three names appeared in the draft list — two were registered athletes.', 'small-aggregate pattern (3 names, 2 in registry); rewrote as "three Olympians from this town"'],
  ['fx_006', '2026-05-05T14:22:48Z', 'wire', 'REDACTED', '"Sarah won bronze in Tokyo." — flagged for context check.', 'common given name + sport context (won, bronze, Tokyo) within 50-char window'],
  ['fx_007', '2026-05-05T14:22:55Z', 'broadcast', 'PASS', 'Sarah\'s Diner anchors the corner of Main and Second.', 'common given name without sport context; place-level usage preserved'],
  ['fx_008', '2026-05-05T14:23:02Z', 'broadcast', 'RETURNED', 'A swimmer from Birmingham, age 19, qualified at the 2024 trials in Indianapolis.', 'near-identification: sport + hometown + year uniquely identifies an individual; draft returned to Storyteller'],
  ['fx_009', '2026-05-05T14:23:09Z', 'wire', 'PASS', 'Substring inside a longer word; not a name boundary.', 'rejected on word-boundary discipline (3-char needle inside compound)'],
  ['fx_010', '2026-05-05T14:23:17Z', 'broadcast', 'PASS', 'The wheelchair rugby pipeline runs through three Midwest clubs.', 'program-level reference; no individual identification'],
  ['fx_011', '2026-05-05T14:23:24Z', 'wire', 'REDACTED', 'Initial-pattern match: "M. [athlete:B]" inside a quoted source.', 'initial-pattern relief valve allowed short last-name match; redacted to [redacted]'],
  ['fx_012', '2026-05-05T14:23:31Z', 'broadcast', 'PASS', 'An adaptive rowing program in Birmingham now feeds the national team.', 'no surface matches; near-id check returned empty; passed through'],
];

/** Twelve representative decisions covering every NilRedactionLayer outcome. */
export const PUBLISH_GATE_FIXTURE_DECISIONS: NilDecision[] = _DECISIONS.map(
  ([id, timestamp, surface, status, claim, reason]) => ({ id, timestamp, surface, status, claim, reason }),
);

export interface PublishGateAggregateStats {
  total_claims: number;
  total_redactions: number;
  disambiguations: number;
  stories_cleared: number;
  stories_blocked: number;
}

/** Pinned counts so the demo renders stable numbers even when sliced. */
export const PUBLISH_GATE_FIXTURE_STATS: PublishGateAggregateStats = {
  total_claims: 847,
  total_redactions: 112,
  disambiguations: 39,
  stories_cleared: 23,
  stories_blocked: 1,
};

export interface PublishGateFooterMeta {
  athlete_registry_size: number;
  last_updated: string;
  matcher: string;
}

export const PUBLISH_GATE_FIXTURE_FOOTER: PublishGateFooterMeta = {
  athlete_registry_size: 11188,
  last_updated: '2026-05-05',
  matcher: 'aho-corasick',
};

/** Derive aggregate counts from a decision array (used by the route handler). */
export function deriveStats(decisions: NilDecision[]): PublishGateAggregateStats {
  let redactions = 0;
  let disambiguations = 0;
  let returned = 0;
  for (const d of decisions) {
    if (d.status === 'REDACTED' || d.status === 'AGGREGATED') redactions += 1;
    if (d.status === 'DISAMBIGUATED') disambiguations += 1;
    if (d.status === 'RETURNED') returned += 1;
  }
  return {
    total_claims: decisions.length,
    total_redactions: redactions,
    disambiguations,
    stories_cleared: Math.max(0, decisions.length - redactions - returned),
    stories_blocked: returned,
  };
}
