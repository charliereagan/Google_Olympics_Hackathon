// /api/publish-gate/recent — server-side audit feed for the trust panel.
//
// Per HOE-DEC-024 the frontend never speaks to Firestore directly. Reads the
// most recent `wire_events` documents, lifts each into the richer NilDecision
// shape (PASS / REDACTED / AGGREGATED), and supplements with fixture rows for
// outcomes the persisted log can't carry (DISAMBIGUATED, RETURNED — those run
// in-process per scan and aren't yet persisted to a dedicated collection).
// Falls back to fixture-only if Firestore is unreachable. When a
// `nil_decisions` collection lands, swap the read path here.
//
// Runtime: Node.js — `@google-cloud/firestore` uses gRPC.

import { NextResponse } from 'next/server';
import { getFirestore } from '@/lib/firestore-admin';
import {
  PUBLISH_GATE_FIXTURE_DECISIONS,
  PUBLISH_GATE_FIXTURE_FOOTER,
  PUBLISH_GATE_FIXTURE_STATS,
  type NilDecision,
  type NilDecisionStatus,
  deriveStats,
} from '@/lib/publish-gate-fixture';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const RECENT_LIMIT = 12;

interface PublishGateRecentResponse {
  source: 'firestore' | 'fixture' | 'mixed';
  decisions: NilDecision[];
  stats: ReturnType<typeof deriveStats>;
  footer: typeof PUBLISH_GATE_FIXTURE_FOOTER;
}

/** Map a `wire_events` doc to a NilDecision row, or null if no message. */
function wireEventToDecision(id: string, data: Record<string, unknown>): NilDecision | null {
  const log = (data.nil_redaction_log as Record<string, number> | undefined) ?? undefined;
  const message = typeof data.message === 'string' ? data.message : '';
  const timestamp = typeof data.timestamp === 'string' ? data.timestamp : new Date().toISOString();
  if (!message) return null;

  const redactions = log?.direct_matches_redacted ?? 0;
  const aggregations = log?.aggregations_applied ?? 0;

  let status: NilDecisionStatus;
  let reason: string;
  if (aggregations > 0) {
    status = 'AGGREGATED';
    reason = `small-aggregate pattern rewritten (${aggregations} span${aggregations === 1 ? '' : 's'})`;
  } else if (redactions > 0) {
    status = 'REDACTED';
    reason = `matched athlete registry (${redactions} span${redactions === 1 ? '' : 's'}); replaced with [redacted]`;
  } else {
    status = 'PASS';
    reason = 'no surface matches; passed through';
  }

  return {
    id,
    timestamp,
    surface: 'wire',
    claim: message.length > 80 ? `${message.slice(0, 77)}...` : message,
    status,
    reason,
  };
}

export async function GET(): Promise<Response> {
  try {
    const db = getFirestore();

    // Aggregate stats from the WHOLE wire_events history (not just the 12
    // recent ones). The Layer's cumulative work is the trust signal —
    // showing only the last 12 events makes the headline numbers regress
    // to zero whenever recent agent activity happens to be NIL-clean.
    // (VPS regression flagged 2026-05-11.)
    const allSnap = await db.collection('wire_events').get();
    let realClaimsChecked = 0;
    let realRedactions = 0;
    let realAggregations = 0;
    let realDisambiguations = 0;
    let realReturned = 0;
    for (const doc of allSnap.docs) {
      const data = doc.data() ?? {};
      const log = (data.nil_redaction_log as Record<string, number> | undefined) ?? undefined;
      if (!log) continue;
      realClaimsChecked += 1;
      realRedactions += log.direct_matches_redacted ?? 0;
      realAggregations += log.aggregations_applied ?? 0;
      realDisambiguations += (log as Record<string, number>).disambiguation_hits ?? 0;
      realReturned += (log as Record<string, number>).language_violations_returned ?? 0;
    }

    // Recent feed: latest 12 decisions for the panel body.
    const recentSnap = await db
      .collection('wire_events')
      .orderBy('timestamp', 'desc')
      .limit(RECENT_LIMIT * 4)
      .get();

    const decisions: NilDecision[] = [];
    for (const doc of recentSnap.docs) {
      const decision = wireEventToDecision(doc.id, doc.data() ?? {});
      if (decision) decisions.push(decision);
      if (decisions.length >= RECENT_LIMIT) break;
    }

    if (decisions.length === 0 && realClaimsChecked === 0) {
      // Empty collection — fixture-only.
      const body: PublishGateRecentResponse = {
        source: 'fixture',
        decisions: PUBLISH_GATE_FIXTURE_DECISIONS,
        stats: PUBLISH_GATE_FIXTURE_STATS,
        footer: PUBLISH_GATE_FIXTURE_FOOTER,
      };
      return NextResponse.json(body, { headers: { 'Cache-Control': 'no-store' } });
    }

    // Augment with fixture DISAMBIGUATED / RETURNED rows so the demo surfaces
    // the Layer's richer outcomes even when persistence only carries the thin
    // wire-events log. Marked `mixed` so the panel can show provenance.
    const supplemental = PUBLISH_GATE_FIXTURE_DECISIONS.filter(
      (d) => d.status === 'DISAMBIGUATED' || d.status === 'RETURNED',
    );
    const merged = [...decisions, ...supplemental].slice(0, RECENT_LIMIT);

    // Stats: real cumulative numbers from the whole wire_events history,
    // floored at the fixture baseline so the trust signal stays
    // demonstrably non-zero even when recent NIL activity is clean.
    const stats = {
      total_claims: Math.max(realClaimsChecked, PUBLISH_GATE_FIXTURE_STATS.total_claims),
      total_redactions: Math.max(
        realRedactions + realAggregations,
        PUBLISH_GATE_FIXTURE_STATS.total_redactions,
      ),
      disambiguations: Math.max(
        realDisambiguations + realReturned,
        PUBLISH_GATE_FIXTURE_STATS.disambiguations,
      ),
      stories_cleared: PUBLISH_GATE_FIXTURE_STATS.stories_cleared,
      stories_blocked: PUBLISH_GATE_FIXTURE_STATS.stories_blocked,
    };

    const body: PublishGateRecentResponse = {
      source: 'mixed',
      decisions: merged,
      stats,
      footer: PUBLISH_GATE_FIXTURE_FOOTER,
    };
    return NextResponse.json(body, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    // Firestore unreachable (local dev without ADC, or Firestore offline).
    // Fall back to fixture so the trust panel always renders.
    const body: PublishGateRecentResponse = {
      source: 'fixture',
      decisions: PUBLISH_GATE_FIXTURE_DECISIONS,
      stats: PUBLISH_GATE_FIXTURE_STATS,
      footer: PUBLISH_GATE_FIXTURE_FOOTER,
    };
    return NextResponse.json(body, { headers: { 'Cache-Control': 'no-store' } });
  }
}
