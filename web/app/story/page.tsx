import { Suspense } from 'react';
import { Layout } from '@/components/Layout';
import { StoryFacets } from '@/components/StoryFacets';
import { ALL_FIXTURE_STORIES } from '@/lib/story-fixture';

// /story — index of available Broadcast pages.
//
// For Day-8 / Day-9 fixture state, this lists the fixture stories so a
// judge clicking the live URL can land on a Broadcast that always
// renders. Once the agent runtime persists `published_stories`, this
// page will additionally read recent docs from Firestore. For now the
// fixture is sufficient for demo moment #4.
//
// VPS-DEC-043: fan-discovery facets (sport / era / type) sit between
// the page header and the story list. Filtering is inline; query
// params reflect facet state so a fan can share a filtered view.
//
// Aesthetic: hairline-only ribbon list — same register as the
// VerifiedClaims component on the Broadcast page itself. No card
// shadows. No grid of teasers. Editorial.

export default function StoryIndexPage() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-24">
        <header className="mb-10 sm:mb-12">
          <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">
            published stories
          </p>
          <h1 className="mt-4 font-display text-display-md text-cream sm:text-display-lg">
            What the room has finished telling.
          </h1>
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text">
            Each page is the place — the program — the pattern. Never an
            individual.
          </p>
        </header>

        {/* useSearchParams() requires a Suspense boundary in Next.js 15. */}
        <Suspense fallback={<StoryFacetsFallback />}>
          <StoryFacets stories={ALL_FIXTURE_STORIES} />
        </Suspense>
      </section>
    </Layout>
  );
}

// Pre-hydration skeleton — preserves layout height so the page doesn't
// jump when facets mount. Hairline-only register; no shimmer.
function StoryFacetsFallback() {
  return (
    <div
      aria-hidden="true"
      className="mb-10 h-[180px] border-y border-navy-light/60"
    />
  );
}
