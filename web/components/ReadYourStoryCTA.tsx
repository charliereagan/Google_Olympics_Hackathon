'use client';

/**
 * <ReadYourStoryCTA /> — the post-completion call-to-action.
 *
 * Renders below the Wire feed when the chain finishes (Editor milestone
 * "Story published" detected by InvestigationStream). Centered band slightly
 * darker than navy-deep; display-md headline, italic-md dek, gold-warm
 * button. Mount animation: 600ms fade + 16px y-shift with room ease, per
 * VPS-DEC-045.
 *
 * Routing: when story_id is known, push to `/story/<id>`. When the
 * milestone arrived without a `story_unit_id` (graceful degradation),
 * route to `/story` (the index) so the fan still gets a destination.
 */

import { motion, useReducedMotion } from 'framer-motion';
import { useRouter } from 'next/navigation';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

interface ReadYourStoryCTAProps {
  storyId: string | null;
}

export default function ReadYourStoryCTA({ storyId }: ReadYourStoryCTAProps) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();

  const href = storyId ? `/story/${storyId}` : '/story';

  return (
    <motion.section
      role="region"
      aria-label="Your story is ready"
      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: ROOM_EASE }}
      // navy-deep is the page base; we want the CTA band to read a tick
      // darker — use a translucent black overlay rather than introducing
      // a new color token. Top + bottom 1px gold-warm hairlines bracket
      // the band the way a lower-third bracket would on broadcast.
      className="mt-12 border-y border-gold-warm/60 bg-black/30 px-4 py-12 text-center sm:mt-16 sm:px-8 sm:py-16"
    >
      <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">
        publish gate cleared
      </p>
      <h2 className="mt-4 font-display text-display-md leading-tight text-cream sm:text-display-lg">
        Your story is ready.
      </h2>
      <p className="mx-auto mt-4 max-w-xl font-italic italic text-italic-md text-wire-text">
        The room has finished telling it. Read what it found.
      </p>

      <button
        type="button"
        onClick={() => router.push(href)}
        className={[
          'mt-8 inline-flex w-full max-w-sm items-center justify-center',
          'px-8 py-4',
          'sm:w-auto',
          'bg-gold-warm text-navy-deep',
          'font-body text-caption uppercase tracking-[0.18em]',
          'transition-colors duration-200 ease-room',
          'hover:bg-gold-deep',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-gold-warm focus-visible:ring-offset-4 focus-visible:ring-offset-navy-deep',
        ].join(' ')}
      >
        Read your story →
      </button>
    </motion.section>
  );
}
