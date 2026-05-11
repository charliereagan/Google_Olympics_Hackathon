'use client';

/**
 * <HelpOverlay /> — the optional "?" affordance + 3-paragraph editorial
 * explainer overlay. Per VPS-DEC-050.
 *
 * Strict rules:
 *   - NEVER auto-opens. Default state is closed. State lives in this
 *     component; no localStorage, no URL flag.
 *   - Closeable via: CLOSE button, click outside the modal card, or ESC key.
 *   - Editorial copy only. No "Welcome to" framing. No bulleted feature list.
 *   - Mobile: full-screen overlay with reduced padding.
 *
 * Lives in <Layout /> so the affordance is on every page. The "?" sits
 * top-right just below the masthead's right-side cluster.
 */

import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { useCallback, useEffect, useState } from 'react';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

export function HelpOverlay() {
  const [open, setOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  const close = useCallback(() => setOpen(false), []);
  const toggle = useCallback(() => setOpen((v) => !v), []);

  // ESC key closes the overlay when open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  return (
    <>
      {/* "?" trigger — fixed top-right, well above the masthead's right
          cluster on every page. ~24x24 tap target; tooltip on hover. */}
      <button
        type="button"
        onClick={toggle}
        aria-label="About this room"
        aria-haspopup="dialog"
        aria-expanded={open}
        title="About this room"
        className="fixed right-3 top-3 z-40 inline-flex h-7 w-7 items-center justify-center rounded-full border border-gold-warm/50 bg-navy-deep/70 font-mono text-mono-sm text-gold-warm transition-colors duration-200 ease-room hover:border-gold-deep hover:text-gold-deep sm:right-5 sm:top-5"
      >
        ?
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="help-overlay"
            role="dialog"
            aria-modal="true"
            aria-label="About The Storyteller's Room"
            className="fixed inset-0 z-50 flex items-center justify-center bg-navy-deep/85 backdrop-blur-sm"
            onClick={close}
            initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0 }}
            transition={{ duration: 0.24, ease: ROOM_EASE }}
          >
            <motion.div
              className="relative mx-auto max-w-2xl px-6 py-10 text-cream sm:px-10 sm:py-14 lg:p-14"
              onClick={(e) => e.stopPropagation()}
              initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8 }}
              transition={{ duration: 0.3, ease: ROOM_EASE }}
            >
              <p
                className="font-mono text-mono-sm uppercase text-gold-warm"
                style={{ letterSpacing: '0.18em' }}
              >
                About this room
              </p>
              <div aria-hidden="true" className="mt-3 h-px w-16 bg-gold-warm/70" />

              <p className="mt-6 font-italic italic text-italic-md text-cream">
                The Storyteller&rsquo;s Room is an AI broadcast room &mdash;
                seven coordinated Gemini agents that find the hometown stories
                behind Team USA. Places, programs, and patterns: never
                individuals.
              </p>
              <p className="mt-5 font-body text-body-md leading-[1.7] text-wire-text">
                The room is autonomous. It scouts. It investigates. It writes.
                The Paralympic Equity Editor reviews every story for coverage
                parity. The Publish Gate audits every claim. The NIL Redaction
                Layer ensures no individual Team USA athlete is named in
                user-facing output &mdash; by architecture, not by policy.
              </p>
              <p className="mt-5 font-body text-body-md leading-[1.7] text-wire-text">
                Submit a prompt on the front door to give it a starting point,
                or sit back. The room works whether you watch or not.
              </p>

              <button
                type="button"
                onClick={close}
                className="mt-10 font-mono text-mono-sm uppercase text-gold-warm transition-colors duration-200 ease-room hover:text-gold-deep"
                style={{ letterSpacing: '0.18em' }}
              >
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

export default HelpOverlay;
