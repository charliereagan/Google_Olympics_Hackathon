import { Layout } from '@/components/Layout';
import { AgentFloor } from '@/components/AgentFloor';
import { TechStackStrip } from '@/components/TechStackStrip';

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
//
// VPS treatment (2026-05-11 submission-day polish, /Docs/VPS/
// floor-agentic-treatment.md): the page now scrams "Google ADK in
// production." A primary title naming the Agent Development Kit, an
// explainer card narrating what the viewer is watching, per-agent
// captions with Gemini-model attributions (rendered inside <AgentFloor />
// as absolute-positioned overlays anchored to the pinned node coords),
// per-card GCP-service top lines, and a 9-product tech-stack strip above
// the bottom nav.

export default function FloorPage() {
  return (
    <Layout>
      <section
        aria-label="The Floor — agent graph of the seven-agent cast and the handoffs between them"
        className="relative h-[calc(100vh-12rem)] w-full"
      >
        {/* Page title — VPS treatment. The kicker line was previously
            "GEMINI AGENTS"; replaced with "PRODUCTION DECK · LIVE" to
            signal the behind-the-scenes register without doubling up on
            the Gemini-model attribution that now lives in the per-agent
            captions below each node. Primary title names the actual ADK
            product; subtitle confirms agent count + live operation. */}
        <header className="pointer-events-none absolute left-6 top-4 z-20 max-w-[640px]">
          <p
            className="font-mono text-mono-sm uppercase text-wire-time"
            style={{ letterSpacing: '0.22em' }}
          >
            PRODUCTION DECK · LIVE
          </p>
          <div aria-hidden="true" className="mt-2 h-px w-8 bg-gold-warm/40" />
          <p
            className="mt-3 font-mono uppercase text-gold-warm"
            style={{ fontSize: '26px', letterSpacing: '0.18em', lineHeight: 1.1 }}
          >
            GOOGLE AGENT DEVELOPMENT KIT
          </p>
          <p className="mt-2 font-italic italic text-italic-md text-cream/90">
            Seven Gemini agents · Live agentic orchestration
          </p>
        </header>

        {/* Explainer card — VPS § "Explainer card". Three short paragraphs
            answering "what am I looking at?" Sits in the left column of
            the canvas wrapper, vertically anchored ~28vh from the top so
            it lives BELOW the page title without crowding the graph. On
            mobile the card stacks above the canvas via normal flow (the
            absolute positioning is only applied at the `sm:` breakpoint). */}
        <aside
          aria-label="What you're looking at"
          className="relative z-10 mx-4 mb-4 max-w-[360px] border border-gold-warm/40 bg-navy-deep/85 px-6 py-5 sm:absolute sm:left-6 sm:top-[16vh] sm:mx-0 sm:mb-0"
        >
          <p
            className="font-mono text-mono-sm uppercase text-parchment"
            style={{ letterSpacing: '0.22em' }}
          >
            WHAT YOU&apos;RE LOOKING AT
          </p>
          <div aria-hidden="true" className="mt-3 h-px w-8 bg-gold-warm/60" />
          <p className="mt-4 font-italic italic text-[15px] leading-[1.55] text-parchment/90">
            Seven Gemini agents, orchestrated by Google&apos;s new Agent
            Development Kit (ADK). Each agent has its own model, its own
            role, and its own tool surface — and they hand off work to
            each other in real time, over Firestore events on Google
            Cloud Run.
          </p>
          <p className="mt-3 font-italic italic text-[15px] leading-[1.55] text-parchment/90">
            This page is what built every story you&apos;ve read on this
            site. Watch a handoff fire: a particle flows along the edge
            from the source agent to the target. Watch a tool call: a
            card slides in from the right showing the specific Google
            service in use.
          </p>
          <p className="mt-3 font-italic italic text-[15px] leading-[1.55] text-parchment/90">
            This is how the room finds, verifies, and tells hometown
            stories — and how it does it without ever naming an
            individual athlete.
          </p>
        </aside>

        <AgentFloor />
      </section>

      {/* Tech-stack strip — VPS § "Tech-stack strip". Single horizontal
          line naming 9 Google products. Lives in normal flow BELOW the
          agent-graph section so it never overlays the explainer card —
          with ~24-32px of vertical breathing room above and below so the
          band reads as its own "credit roll" register, separate from the
          fixed BroadcastNav. Mobile wraps; never scrolls horizontally.
          Shared component so /publish-gate and /wire stay byte-identical. */}
      <TechStackStrip />
    </Layout>
  );
}
