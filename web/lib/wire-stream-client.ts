// Client-side SSE consumer hook for the Wire stream.
//
// Pairs with `/web/app/api/wire/stream/route.ts`. The Route Handler emits
// three named events:
//   - `preseed`     — one of the pre-seeded historical events (§6.9)
//   - `preseed-end` — boundary marker; subsequent `wire` events are live
//   - `wire`        — a newly-emitted live event
//
// We use `@microsoft/fetch-event-source` instead of the browser-native
// `EventSource` for two reasons:
//   1. Custom request headers (we send `last-event-id` ourselves on reconnect).
//   2. Explicit reconnect contract — the lib retries on network errors with
//      backoff, and we update the connection-state UI accordingly.
//
// The hook is intentionally append-only over `events`. Wire events are never
// modified or removed; rendering is "scroll up forever".

'use client';

import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useEffect, useRef, useState } from 'react';
import type { WireEvent } from '@/lib/wire-event';

export type WireConnectionState =
  | { kind: 'connecting' }
  | { kind: 'preseeding'; count: number }
  | { kind: 'live' }
  | { kind: 'reconnecting'; lastEventId: string | null }
  | { kind: 'error'; message: string };

export interface UseWireStreamResult {
  events: WireEvent[];
  state: WireConnectionState;
}

export function useWireStream(): UseWireStreamResult {
  const [events, setEvents] = useState<WireEvent[]>([]);
  const [state, setState] = useState<WireConnectionState>({
    kind: 'connecting',
  });
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();

    const headers: Record<string, string> = {};
    if (lastEventIdRef.current) {
      headers['last-event-id'] = lastEventIdRef.current;
    }

    fetchEventSource('/api/wire/stream', {
      signal: ctrl.signal,
      headers,
      // Keep the stream alive when the tab is backgrounded — judges will
      // tab-switch during the demo and we don't want to drop the room.
      openWhenHidden: true,

      async onopen(res) {
        if (res.status >= 400) {
          setState({ kind: 'error', message: `HTTP ${res.status}` });
          return;
        }
        setState({ kind: 'preseeding', count: 0 });
      },

      onmessage(msg) {
        if (msg.id) {
          lastEventIdRef.current = msg.id;
        }

        if (msg.event === 'preseed') {
          const ev = JSON.parse(msg.data) as WireEvent;
          setEvents((prev) => [...prev, ev]);
          setState((s) => ({
            kind: 'preseeding',
            count: s.kind === 'preseeding' ? s.count + 1 : 1,
          }));
          return;
        }

        if (msg.event === 'preseed-end') {
          setState({ kind: 'live' });
          return;
        }

        if (msg.event === 'wire') {
          const ev = JSON.parse(msg.data) as WireEvent;
          setEvents((prev) => [...prev, ev]);
          // Promote to 'live' if we somehow missed the preseed-end boundary.
          setState((s) => (s.kind === 'live' ? s : { kind: 'live' }));
          return;
        }

        if (msg.event === 'error' || msg.event === 'preseed-error') {
          let message = 'unknown';
          try {
            const data = JSON.parse(msg.data) as { message?: string };
            message = data.message ?? message;
          } catch {
            message = msg.data;
          }
          setState({ kind: 'error', message });
          return;
        }
      },

      onerror() {
        setState({
          kind: 'reconnecting',
          lastEventId: lastEventIdRef.current,
        });
        // Returning undefined uses the lib's default backoff and retry.
      },
    }).catch(() => {
      // AbortError on unmount; ignore.
    });

    return () => ctrl.abort();
  }, []);

  return { events, state };
}
