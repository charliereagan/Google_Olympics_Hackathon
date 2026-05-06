// SSE bridge: Firestore `wire_events` + `agent_handoffs` -> Server-Sent Events.
//
// Per HOE-DEC-024 the frontend does NOT speak to Firestore directly. This
// Route Handler is the single bridge. It:
//
//   1. Pre-seeds the last 6 `replay`/`published` wire events on connect
//      (BUILD_SPEC §6.9 — "the room is scrolling within <1s of arrival"),
//      plus the last 6 replay/published `agent_handoffs` for the agent-graph
//      Floor (BUILD_SPEC §9.6).
//   2. Attaches an Admin-SDK `onSnapshot` listener for `mode == 'live'`
//      wire events and forwards each newly-added doc as `event: wire`.
//   3. Attaches a SECOND `onSnapshot` listener for `mode == 'live'`
//      `agent_handoffs` and forwards each newly-added doc as `event: handoff`
//      (separate event type so the agent-graph Floor can subscribe
//      independently of the Wire feed).
//   4. Emits a heartbeat comment every 15s to defeat idle proxy timeouts
//      (BUILD_SPEC §4 "How the SSE connection survives a 60-minute Cloud
//      Run timeout"). Cloud Run's hard cap is 3600s; `maxDuration` matches.
//   5. Honors `Last-Event-ID` on reconnect: resumes the live cursor after
//      the last seen doc when present (wire_events only — handoff events
//      are append-only metadata; reconnect re-attaches to the live edge).
//
// Append-only: both `wire_events` and `agent_handoffs` documents are never
// modified or removed; we ignore those snapshot change types.
//
// Runtime is Node.js (NOT Edge) — the `@google-cloud/firestore` Admin SDK
// uses gRPC and Node-only APIs.

import type { NextRequest } from 'next/server';
import { getFirestore } from '@/lib/firestore-admin';
import type { WireEvent } from '@/lib/wire-event';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
// Cloud Run hard request-timeout cap is 3600s (BUILD_SPEC §3.7).
export const maxDuration = 3600;

const HEARTBEAT_MS = 15_000; // Per BUILD_SPEC §4 — defeat idle proxy timeouts.
const PRE_SEED_LIMIT = 6;    // Per BUILD_SPEC §6.9 — first-paint window.
// Per Day-10 D7: clamp the live feed to the last hour so multi-day stale
// rows (and pre-Day-7 over-redacted events) never hit the wire UI.
const LIVE_WINDOW_MS = 60 * 60 * 1000;

// Shape of an agent-handoff document. Mirrors `agents/handoffs.py::emit_handoff`.
// Inline rather than importing because the agent-graph Floor frontend (which
// will own the canonical TS type) ships in a later worker.
type AgentHandoff = {
  id: string;
  from_agent: string;
  to_agent: string;
  tool_call_id: string;
  story_unit_id: string | null;
  investigation_id: string | null;
  timestamp: string;
  mode: 'live' | 'replay' | 'published';
};

export async function GET(req: NextRequest) {
  const db = getFirestore();
  const lastEventId = req.headers.get('last-event-id');

  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      let unsubscribeWire: (() => void) | null = null;
      let unsubscribeHandoff: (() => void) | null = null;
      let heartbeat: ReturnType<typeof setInterval> | null = null;

      const enqueue = (chunk: string) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(chunk));
        } catch {
          // Controller already closed by client disconnect; treat as cleanup.
          cleanup();
        }
      };

      const send = (
        event: string | null,
        data: unknown,
        id?: string,
      ) => {
        let chunk = '';
        if (id) chunk += `id: ${id}\n`;
        if (event) chunk += `event: ${event}\n`;
        chunk += `data: ${JSON.stringify(data)}\n\n`;
        enqueue(chunk);
      };

      const cleanup = () => {
        if (closed) return;
        closed = true;
        if (heartbeat) {
          clearInterval(heartbeat);
          heartbeat = null;
        }
        if (unsubscribeWire) {
          try {
            unsubscribeWire();
          } catch {
            // best-effort
          }
          unsubscribeWire = null;
        }
        if (unsubscribeHandoff) {
          try {
            unsubscribeHandoff();
          } catch {
            // best-effort
          }
          unsubscribeHandoff = null;
        }
        try {
          controller.close();
        } catch {
          // already closed
        }
      };

      // Cleanup on client disconnect.
      req.signal.addEventListener('abort', cleanup);

      // Heartbeat: SSE comment line keeps the connection warm through
      // any intermediate idle-proxy timeout (Cloud Run / load balancer /
      // browser HTTP idle).
      heartbeat = setInterval(() => {
        enqueue(`: heartbeat ${Date.now()}\n\n`);
      }, HEARTBEAT_MS);

      // -- 1a. PRE-SEED: last 6 wire_events replay/published (BUILD_SPEC §6.9) ---
      try {
        const preSeedSnap = await db
          .collection('wire_events')
          .where('mode', 'in', ['replay', 'published'])
          .orderBy('timestamp', 'desc')
          .limit(PRE_SEED_LIMIT)
          .get();

        // Reverse so they render oldest-first -> newest-last (top of feed).
        const preSeedDocs = preSeedSnap.docs.slice().reverse();
        for (const doc of preSeedDocs) {
          const data = doc.data();
          if (!data) continue;
          const event: WireEvent = {
            id: doc.id,
            ...(data as Omit<WireEvent, 'id'>),
          };
          send('preseed', event, doc.id);
        }
        send('preseed-end', { count: preSeedDocs.length });
      } catch (err) {
        // Pre-seed failure is non-fatal — the live stream can still attach.
        send('preseed-error', { message: String(err) });
      }

      // -- 1b. PRE-SEED: last 6 agent_handoffs replay/published (BUILD_SPEC §9.6) ---
      try {
        const handoffSeedSnap = await db
          .collection('agent_handoffs')
          .where('mode', 'in', ['replay', 'published'])
          .orderBy('timestamp', 'desc')
          .limit(PRE_SEED_LIMIT)
          .get();

        const handoffSeedDocs = handoffSeedSnap.docs.slice().reverse();
        for (const doc of handoffSeedDocs) {
          const data = doc.data();
          if (!data) continue;
          const handoff: AgentHandoff = {
            id: doc.id,
            ...(data as Omit<AgentHandoff, 'id'>),
          };
          send('handoff-preseed', handoff, doc.id);
        }
        send('handoff-preseed-end', { count: handoffSeedDocs.length });
      } catch (err) {
        // Pre-seed failure is non-fatal — the live stream can still attach.
        send('handoff-preseed-error', { message: String(err) });
      }

      if (closed) return;

      // -- 2. LIVE STREAM: wire_events onSnapshot listener ---------------
      try {
        // Day-10 D7: clamp the live feed to events emitted in the last
        // hour. `timestamp` is stored as an ISO 8601 string by
        // `agents/wire/emit.py`, so a string comparison is chronologically
        // correct for UTC ISO strings.
        const liveCutoff = new Date(Date.now() - LIVE_WINDOW_MS).toISOString();
        let liveQuery = db
          .collection('wire_events')
          .where('mode', '==', 'live')
          .where('timestamp', '>=', liveCutoff)
          .orderBy('timestamp', 'asc');

        // On reconnect with Last-Event-ID, resume after that doc when we can
        // resolve it. Best-effort — if the doc is gone, attach to live.
        if (lastEventId) {
          try {
            const lastDoc = await db
              .collection('wire_events')
              .doc(lastEventId)
              .get();
            if (lastDoc.exists) {
              liveQuery = liveQuery.startAfter(lastDoc);
            }
          } catch {
            // ignore — fall through and attach to live
          }
        }

        unsubscribeWire = liveQuery.onSnapshot(
          (snap) => {
            for (const change of snap.docChanges()) {
              // Wire events are append-only; ignore modified / removed.
              if (change.type !== 'added') continue;
              const event: WireEvent = {
                id: change.doc.id,
                ...(change.doc.data() as Omit<WireEvent, 'id'>),
              };
              send('wire', event, change.doc.id);
            }
          },
          (err) => {
            send('error', { message: String(err) });
            // Don't tear down — let the client decide via reconnect.
          },
        );
      } catch (err) {
        send('error', { message: `live stream init: ${String(err)}` });
      }

      // -- 3. LIVE STREAM: agent_handoffs onSnapshot listener (BUILD_SPEC §9.6)
      // Separate event type (`event: handoff`) so the agent-graph Floor can
      // subscribe independently of the Wire feed via `useWireStream`. Same
      // 1-hour live window; no `Last-Event-ID` resume (handoffs are
      // best-effort metadata; the Floor re-attaches to the live edge on
      // reconnect).
      try {
        const liveCutoff = new Date(Date.now() - LIVE_WINDOW_MS).toISOString();
        const handoffQuery = db
          .collection('agent_handoffs')
          .where('mode', '==', 'live')
          .where('timestamp', '>=', liveCutoff)
          .orderBy('timestamp', 'asc');

        unsubscribeHandoff = handoffQuery.onSnapshot(
          (snap) => {
            for (const change of snap.docChanges()) {
              // Handoffs are append-only; ignore modified / removed.
              if (change.type !== 'added') continue;
              const handoff: AgentHandoff = {
                id: change.doc.id,
                ...(change.doc.data() as Omit<AgentHandoff, 'id'>),
              };
              send('handoff', handoff, change.doc.id);
            }
          },
          (err) => {
            send('handoff-error', { message: String(err) });
            // Don't tear down — let the client decide via reconnect.
          },
        );
      } catch (err) {
        send('handoff-error', { message: `handoff stream init: ${String(err)}` });
      }
    },

    cancel() {
      // Stream cancelled by the client; abort signal handler does cleanup.
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      // Disable proxy buffering so chunks flush immediately.
      'X-Accel-Buffering': 'no',
    },
  });
}
