import { Suspense } from 'react';
import { Layout } from '@/components/Layout';
import WirePageBody from '@/components/WirePageBody';
import { TechStackStrip } from '@/components/TechStackStrip';

// `/wire` — the dedicated full-page Wire view.
//
// Per VPS-DEC-041: the SaaS-style "open feed" experience moves off `/` to
// here, so the front door can be fan-first. This is where fans and judges
// who want to watch the room work in full live.
//
// VPS treatment (2026-05-11 submission-day polish, /Docs/VPS/
// wire-and-publish-gate-treatment.md): the page now scrams "Google ADK /
// agentic AI" to match /floor. Sequence (top to bottom):
//   1. Production-Deck kicker + sub-kicker + Playfair title + Lora dek
//      naming seven Gemini agents and ADK
//   2. Left-column legend card with the seven-agent roster (sticky on
//      desktop, stacks above the feed on mobile) — in <WirePageBody />
//   3. Filter pills (ALL / EDITOR / SCOUTS / INVESTIGATOR / EQUITY EDITOR
//      / STORYTELLER / NARRATOR / PUBLISH GATE) above the feed
//   4. <WireFeed /> with per-event Gemini-model attribution
//   5. Tech-stack strip shared with /floor and /publish-gate
//
// The persistent ambient Wire ticker still lives in <Layout /> on every
// page; this view is the long-form expansion of the same data stream.

export const dynamic = 'force-dynamic';

export default function WirePage() {
  return (
    <Layout>
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        <header className="mb-10 sm:mb-12">
          <p
            className="font-mono text-mono-sm uppercase text-wire-time"
            style={{ letterSpacing: '0.22em' }}
          >
            BEHIND THE SCENES
          </p>
          <div aria-hidden="true" className="mt-2 h-px w-8 bg-gold-warm/40" />
          <p
            className="mt-4 font-mono text-mono-sm uppercase text-gold-warm"
            style={{ letterSpacing: '0.22em' }}
          >
            GOOGLE ADK &middot; LIVE AGENT FEED
          </p>
          <h1 className="mt-4 font-display text-display-md text-cream sm:text-display-lg">
            The room thinking, in real time.
          </h1>
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text leading-[1.55]">
            Every thought, every handoff, every decision &mdash; from seven
            Gemini agents orchestrated by Google&apos;s Agent Development Kit.
          </p>
          <div aria-hidden="true" className="mt-8 h-px w-full bg-gold-warm/60" />
        </header>

        {/* WirePageBody reads ?agent= via useSearchParams — wrap in Suspense
            so the server boundary is valid for Next.js App Router static
            analysis. */}
        <Suspense fallback={null}>
          <WirePageBody />
        </Suspense>
      </section>

      <TechStackStrip />
    </Layout>
  );
}
