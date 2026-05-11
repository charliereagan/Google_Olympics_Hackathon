import { Layout } from '@/components/Layout';
import { AgentFloor } from '@/components/AgentFloor';

// `/floor` — BUILD_SPEC §9 agent-graph backstage view.
//
// Demo-moment-#2 surface ("the agents are truly agentic"). Seven agent
// nodes, hairline edges, particle handoffs traveling along the edges
// every time the agent runtime emits a structured handoff event, and a
// bottom-right tool-call card stack synthesizing the dispatch slip for
// each handoff.
//
// Server component shell. The Hi-DPI Canvas + d3-force simulation +
// particle pool + SSE subscription live in <AgentFloor />, which is a
// client component. The SSE bridge at `/api/wire/stream` already emits
// `event: handoff` and `event: handoff-preseed` frames sourced from the
// `agent_handoffs` Firestore collection (HOE-DEC-024 — the frontend
// never speaks to Firestore directly).
//
// Per CLAUDE.md decision filter: this surface IS demo-moment #2 ("agents
// are truly agentic") and carries demo-moment #3's structural cue (the
// Equity Editor's agitos-red flash when it intervenes via the
// `intervene_feed_drift` dispatch tool — BUILD_SPEC §9.5).

export default function FloorPage() {
  return (
    <Layout>
      <section
        aria-label="The Floor — agent graph of the seven-agent cast and the handoffs between them"
        className="relative h-[calc(100vh-6rem)] w-full"
      >
        <header className="pointer-events-none absolute left-6 top-4 z-20">
          <p
            className="font-mono text-mono-sm uppercase text-wire-time"
            style={{ letterSpacing: '0.22em' }}
          >
            GEMINI AGENTS
          </p>
          <div aria-hidden="true" className="mt-2 h-px w-8 bg-gold-warm/40" />
          <p
            className="mt-3 font-mono text-caption uppercase text-slate-room"
            style={{ letterSpacing: '0.18em' }}
          >
            the floor · seven agents
          </p>
          <p className="mt-1 font-italic italic text-italic-sm text-wire-text">
            The room thinking, in real time.
          </p>
        </header>
        <AgentFloor />
      </section>
    </Layout>
  );
}
