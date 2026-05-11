import { Layout } from '@/components/Layout';
import WireFeed from '@/components/WireFeed';

// `/wire` — the dedicated full-page Wire view.
//
// Per VPS-DEC-041: the SaaS-style "open feed" experience moves off `/` to
// here, so the front door can be fan-first. This is where fans and judges
// who want to watch the room work in full live. Same <WireFeed /> that
// used to be at `/` — SSE bridge, pre-seed, room-quiet/down states.
//
// The persistent ambient Wire ticker lives in <Layout /> on every page;
// this view is the long-form expansion of the same data stream.
//
// Container: max-w-3xl with the Pass-2 mobile-sweep rhythm matches the
// prior `/` rhythm so visual continuity is preserved when the route moves.

export const dynamic = 'force-dynamic';

export default function WirePage() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
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
            The Wire
          </p>
          <div aria-hidden="true" className="mt-3 h-px w-16 bg-gold-warm/70" />
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text">
            The room, working.
          </p>
        </header>
        <WireFeed />
      </section>
    </Layout>
  );
}
