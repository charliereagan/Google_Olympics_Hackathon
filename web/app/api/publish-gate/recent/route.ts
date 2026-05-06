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
    const snap = await db
      .collection('wire_events')
      .orderBy('timestamp', 'desc')
      .limit(RECENT_LIMIT * 4) // over-fetch; many ambient events have no NIL log
      .get();

    const decisions: NilDecision[] = [];
    for (const doc of snap.docs) {
      const decision = wireEventToDecision(doc.id, doc.data() ?? {});
      if (decision) decisions.push(decision);
      if (decisions.length >= RECENT_LIMIT) break;
    }

    if (decisions.length === 0) {
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

    const body: PublishGateRecentResponse = {
      source: 'mixed',
      decisions: merged,
      stats: deriveStats(merged),
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
