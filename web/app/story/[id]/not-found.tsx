import Link from 'next/link';
import { Layout } from '@/components/Layout';

// Editorial 404: kicker, headline, dek, hairline, link back to index.

export default function StoryNotFound() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-24 sm:px-6 sm:py-32">
        <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">story · not found</p>
        <h1 className="mt-4 font-display text-display-md text-cream sm:text-display-lg">The room has no record of that story.</h1>
        <p className="mt-4 font-italic italic text-italic-md text-wire-text">
          The Wire keeps a live feed of every agent decision; published stories settle into their own pages once the Publish Gate clears them.
        </p>
        <div aria-hidden="true" className="mt-10 h-px w-16 bg-gold-warm/70" />
        <Link
          href="/story"
          className="mt-6 inline-block font-body text-body-md text-cream underline decoration-gold-warm/60 underline-offset-4 hover:decoration-gold-warm"
        >
          Back to the published stories
        </Link>
      </section>
    </Layout>
  );
}
