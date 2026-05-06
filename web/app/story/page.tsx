import Link from 'next/link';
import { Layout } from '@/components/Layout';
import { ALL_FIXTURE_STORIES } from '@/lib/story-fixture';

// /story — index of available Broadcast pages.
//
// For Day-8 / Day-9 fixture state, this lists the fixture stories so a
// judge clicking the live URL can land on a Broadcast that always
// renders. Once the agent runtime persists `published_stories`, this
// page will additionally read recent docs from Firestore. For now the
// fixture is sufficient for demo moment #4.
//
// Aesthetic: hairline-only ribbon list — same register as the
// VerifiedClaims component on the Broadcast page itself. No card
// shadows. No grid of teasers. Editorial.

export default function StoryIndexPage() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-24">
        <header className="mb-12 sm:mb-16">
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

        <ul className="divide-y divide-navy-light border-y border-navy-light">
          {ALL_FIXTURE_STORIES.map((story) => (
            <li key={story.id}>
              <Link
                href={`/story/${story.id}`}
                className="group block py-8 transition-colors duration-200 ease-room"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <span className="font-mono text-mono-sm uppercase tracking-[0.16em] text-gold-warm/80">
                    {story.kicker_place}
                  </span>
                  <span className="shrink-0 font-mono text-mono-sm text-wire-time">
                    {new Date(story.published_at)
                      .toISOString()
                      .slice(0, 10)}
                  </span>
                </div>
                <h2 className="mt-3 font-display text-display-md leading-tight text-cream group-hover:text-gold-warm">
                  {story.headline}
                </h2>
                <p className="mt-3 max-w-2xl font-italic italic text-italic-md text-wire-text">
                  {story.dek}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </Layout>
  );
}
