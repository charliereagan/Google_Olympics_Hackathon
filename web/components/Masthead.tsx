'use client';

/**
 * <Masthead /> — thin editorial broadcast-ID strip at the top of every page.
 *
 * Per VPS-DEC-041 + CONSTITUTION §11 / §4 Rule 6:
 *   - Left: tracked-cap "THE STORYTELLER'S ROOM" in gold-warm.
 *   - Right: "BROADCAST · 2026" + the <DaysToLA28 /> counter.
 *   - 1px gold-warm/60 hairline beneath.
 *
 * No logo. No "welcome to" copy. No marketing copy. This is a broadcast
 * lower-third for the publication itself — a wordmark in editorial register.
 *
 * Implemented as a client component because <DaysToLA28 /> needs a client
 * boundary (interval timer); ditto the link wrapping the wordmark.
 */

import Link from 'next/link';
import { DaysToLA28 } from './DaysToLA28';

export function Masthead() {
  return (
    <header className="relative z-20 w-full">
      <div className="flex flex-wrap items-baseline justify-between gap-3 px-4 pb-3 pt-4 sm:px-6 sm:pt-5 lg:px-10">
        <Link
          href="/"
          className="font-mono text-mono-sm uppercase text-gold-warm transition-colors duration-200 ease-room hover:text-gold-deep"
          style={{ letterSpacing: '0.18em' }}
        >
          The Storyteller&rsquo;s Room
        </Link>
        <div className="flex items-baseline gap-3 sm:gap-4">
          <span
            className="hidden font-mono text-mono-sm uppercase text-wire-time sm:inline"
            style={{ letterSpacing: '0.18em' }}
          >
            Broadcast &middot; 2026
          </span>
          <DaysToLA28 />
        </div>
      </div>
      {/* Hairline divider — 1px gold-warm/60, full width. */}
      <div aria-hidden="true" className="h-px w-full bg-gold-warm/60" />
    </header>
  );
}

export default Masthead;
