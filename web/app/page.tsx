import Link from 'next/link';
import { Layout } from '@/components/Layout';
import { SeedPromptCTA } from '@/components/SeedPromptCTA';
import { getRecentStories } from '@/lib/published-stories';
import type { BroadcastStory } from '@/lib/story-fixture';

// `/` — the fan-first front door. VPS-DEC-041.
//
// Composition (top → bottom; <Layout /> owns persistent chrome — masthead,
// ambient Wire ticker, footer credit, bottom nav, help overlay):
//   1. Full-bleed cinematic hero of the latest published story
//   2. Discovery row — 3 equal-weight cards (THE MAP / THE FIELD / THE STORIES)
//   3. Seed-prompt CTA band
//   4. Recent-stories grid — the Stack, made explicit
//
// Server component: fetches stories via `getRecentStories()` which best-
// efforts Firestore and falls back to fixtures. No client-side data
// boundary needed at this depth — the SeedPromptCTA is the only piece of
// client-state on the page.
//
// VPS-DEC-040 is honored: no kicker + display headline + dek + hero card
// grid. The hero IS a published story, not an explainer for the product.
// CONSTITUTION §11: "cinematic hero (a stylized landscape, not a person).
// Wire beginning to scroll." Both conditions met by composition.

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const { hero, recent } = await getRecentStories(4);

  return (
    <Layout>
      <HeroSection story={hero} />
      <DiscoveryRow />
      <SeedPromptCTA />
      <RecentStoriesGrid stories={recent} />
    </Layout>
  );
}

// ---------------------------------------------------------------------------
// Hero — full-bleed cinematic, ~75vh, click → /story/[id]
// ---------------------------------------------------------------------------

// Relative-time helper for the LATEST STORY lower-third dateline. Returns
// short broadcast-style strings ("JUST NOW", "2 HOURS AGO"); falls back to a
// "MAY 5"-shape short date past 7 days. Server-renderable (no `Date.now`-only
// branches — both sides of the comparison are absolute ms since epoch).
function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diff = Date.now() - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'JUST NOW';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} MINUTE${min === 1 ? '' : 'S'} AGO`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} HOUR${hr === 1 ? '' : 'S'} AGO`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} DAY${day === 1 ? '' : 'S'} AGO`;
  return new Date(iso)
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    .toUpperCase();
}

function HeroSection({ story }: { story: BroadcastStory }) {
  // Render as a Link so the entire hero is one tap target. Documentary
  // pacing on the image: animation lives on the inner motion via the
  // BroadcastPage spec; here we keep the entry calm and let the page
  // beneath inherit the same easing curve when the route transitions.
  const heroBackgroundStyle = story.hero_image_url
    ? { backgroundImage: `url(${story.hero_image_url})` }
    : {
        backgroundImage:
          'radial-gradient(ellipse 60% 45% at 18% 28%, rgba(212,168,74,0.18), transparent 70%), ' +
          'radial-gradient(ellipse 80% 55% at 80% 90%, rgba(10,20,40,0.95), transparent 70%), ' +
          'linear-gradient(180deg, #0A1428 0%, #1A2740 60%, #0A1428 100%)',
      };

  return (
    <Link
      href={`/story/${story.id}`}
      aria-label={`Read: ${story.headline}`}
      className="group relative block w-full overflow-hidden"
      style={{ height: '75vh', minHeight: '480px' }}
    >
      {/* Background image / gradient layer */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-cover bg-center transition-transform duration-[1200ms] ease-room group-hover:scale-[1.02]"
        style={heroBackgroundStyle}
      />

      {/* Bottom scrim — matches BroadcastPage scrim for visual continuity */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 h-2/3"
        style={{
          background:
            'linear-gradient(180deg, rgba(10,20,40,0) 0%, rgba(10,20,40,0.85) 70%, rgba(10,20,40,0.95) 100%)',
        }}
      />

      {/* Bottom-left content stack */}
      <div className="absolute inset-x-0 bottom-0 px-4 pb-10 sm:px-10 sm:pb-14 lg:px-16 lg:pb-20">
        <div className="max-w-3xl">
          {/* Broadcast lower-third dateline. Smaller + dimmer than the kicker
              so the visual hierarchy reads: dateline → kicker → headline. */}
          <p
            className="mb-3 font-mono text-[11px] uppercase text-cream/60"
            style={{ letterSpacing: '0.18em' }}
          >
            LATEST STORY · {formatRelative(story.published_at)}
          </p>
          <p
            className="font-mono text-mono-sm uppercase text-gold-warm"
            style={{ letterSpacing: '0.18em' }}
          >
            {story.kicker_place}
          </p>
          <h1 className="mt-4 font-display text-display-md leading-[1.05] text-cream transition-colors duration-300 ease-room group-hover:text-gold-warm/95 sm:text-display-lg lg:text-display-xl">
            {story.headline}
          </h1>
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text sm:mt-5">
            {story.dek}
          </p>
          {/* CTA — visually a button, semantically a <span> because the
              entire <Link> wrapping the hero is already the click target.
              Nesting <a> or <button> here would be invalid interactive
              nesting. The arrow nudges right + a gold hairline grows
              beneath the text on group-hover, signaling clickability
              without competing with the existing image scale animation. */}
          <span
            role="presentation"
            className="relative mt-7 inline-block font-mono uppercase text-gold-warm sm:mt-8"
            style={{
              letterSpacing: '0.22em',
              fontSize: '15px', // text-mono-md isn't a token; use the design-system body-sm-adjacent size that reads as a CTA at hero scale.
            }}
          >
            <span className="relative inline-block">
              BEGIN BROADCAST{' '}
              <span className="inline-block transition-transform duration-300 ease-room group-hover:translate-x-1">
                ▸
              </span>
              <span
                aria-hidden="true"
                className="absolute -bottom-1 left-0 h-px w-0 bg-gold-warm transition-[width] duration-500 ease-room group-hover:w-full"
              />
            </span>
          </span>
        </div>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Discovery row — 3 cards: THE MAP / THE FIELD / THE STORIES
// ---------------------------------------------------------------------------

interface DiscoveryCard {
  href: string;
  title: string;
  dek: string;
}

const DISCOVERY_CARDS: DiscoveryCard[] = [
  {
    href: '/map',
    title: 'The Map',
    dek: 'Find your region.',
  },
  {
    href: '/field',
    title: 'The Field',
    dek: 'Follow the patterns.',
  },
  {
    href: '/story',
    title: 'The Stories',
    dek: 'What the room has told.',
  },
];

function DiscoveryRow() {
  return (
    <section
      aria-label="Discover the room"
      // grid-cols-1 lg:grid-cols-3 with `gap-px` + bg-gold-warm/30 produces
      // a hairline divider between cards on lg — pure layout, no extra DOM.
      className="grid grid-cols-1 gap-px bg-gold-warm/30 lg:grid-cols-3"
    >
      {DISCOVERY_CARDS.map((card) => (
        <Link
          key={card.href}
          href={card.href}
          className="group flex flex-col gap-3 bg-navy-deep px-6 py-10 transition-colors duration-200 ease-room hover:bg-navy-mid sm:px-10 sm:py-14"
        >
          <span
            className="font-mono text-mono-sm uppercase text-gold-warm transition-colors duration-200 ease-room group-hover:text-gold-deep"
            style={{ letterSpacing: '0.22em' }}
          >
            {card.title}
          </span>
          <span className="font-italic italic text-italic-md text-wire-text">
            {card.dek}
          </span>
        </Link>
      ))}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Recent stories — 3-4 compact cards. The Stack, made explicit.
// ---------------------------------------------------------------------------

function RecentStoriesGrid({ stories }: { stories: BroadcastStory[] }) {
  if (stories.length === 0) return null;
  return (
    <section
      aria-label="Recent stories"
      className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20 lg:px-10"
    >
      <header className="mb-8 sm:mb-12">
        <p
          className="font-mono text-mono-sm uppercase text-gold-warm"
          style={{ letterSpacing: '0.22em' }}
        >
          The Stack
        </p>
        <div aria-hidden="true" className="mt-3 h-px w-16 bg-gold-warm/70" />
      </header>

      <ul className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {stories.map((story) => (
          <li key={story.id}>
            <RecentStoryCard story={story} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecentStoryCard({ story }: { story: BroadcastStory }) {
  const heroBackgroundStyle = story.hero_image_url
    ? { backgroundImage: `url(${story.hero_image_url})` }
    : {
        backgroundImage:
          'radial-gradient(ellipse 60% 45% at 20% 30%, rgba(212,168,74,0.20), transparent 70%), linear-gradient(180deg, #0A1428 0%, #1A2740 100%)',
      };

  const truncated =
    story.dek.length > 120 ? story.dek.slice(0, 119).trimEnd() + '…' : story.dek;

  return (
    <Link
      href={`/story/${story.id}`}
      className="group block"
      aria-label={`Read: ${story.headline}`}
    >
      <div
        aria-hidden="true"
        className="aspect-[16/10] w-full overflow-hidden border border-gold-warm/30 bg-cover bg-center transition-colors duration-200 ease-room group-hover:border-gold-warm"
        style={heroBackgroundStyle}
      />
      <div className="mt-4">
        <p
          className="font-mono text-mono-sm uppercase text-gold-warm/90"
          style={{ letterSpacing: '0.18em' }}
        >
          {story.kicker_place}
        </p>
        <h3 className="mt-2 font-display text-display-md leading-[1.15] text-cream transition-colors duration-200 ease-room group-hover:text-gold-warm sm:text-[28px]">
          {story.headline}
        </h3>
        <p className="mt-2 font-italic italic text-italic-sm text-wire-text">
          {truncated}
        </p>
      </div>
    </Link>
  );
}
