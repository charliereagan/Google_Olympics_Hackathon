'use client';

/**
 * <SeedPromptCTA /> — the broadcast-lower-third seed-prompt band on `/`.
 *
 * Per VPS-DEC-041: a full-width band, slightly darker than navy-deep, with
 * an editorial input + tracked-cap SUBMIT button. The hint line below sets
 * expectations ("or sit back and watch the room work") — the room is
 * autonomous; the prompt is a starting point, not a request/response chat.
 *
 * Submit flow (stubbed for F4):
 *   - On submit, we route to `/investigation/pending` with the prompt as a
 *     `q=` query param. Worker F4 will wire `/investigation/[id]` to a
 *     POST against the agent runtime; for now this is a stub that lets the
 *     front door's chrome land without backend dependency.
 *   - Empty submits no-op.
 *
 * Constitutional notes:
 *   - CONSTITUTION §8 / §11: chat-style UI is forbidden. This is a single
 *     prompt field, not a conversation thread. No history. No avatars. No
 *     reply chips.
 *   - The hint is italic Lora — editorial voice, not call-to-action voice.
 */

import { useRouter } from 'next/navigation';
import { useState } from 'react';

export function SeedPromptCTA() {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length === 0) return;
    setSubmitting(true);
    // Worker F4 owns the real POST. For now route to the stubbed pending
    // page so the front-door interaction lands end-to-end.
    const params = new URLSearchParams({ q: trimmed });
    router.push(`/investigation/pending?${params.toString()}`);
  };

  return (
    <section
      aria-label="Submit a story seed"
      className="w-full border-t border-navy-light/60 bg-navy-mid"
    >
      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16 lg:px-10">
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-3 sm:flex-row sm:items-stretch sm:gap-0"
        >
          <label htmlFor="seed-prompt" className="sr-only">
            Find me a Team USA hometown story
          </label>
          <input
            id="seed-prompt"
            name="seed-prompt"
            type="text"
            autoComplete="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Find me a Team USA hometown story I&rsquo;ve never heard before…"
            className="flex-1 border border-gold-warm/40 bg-navy-deep px-5 py-4 font-italic italic text-italic-md text-cream placeholder:text-wire-time focus:border-gold-warm focus:outline-none focus:ring-0"
          />
          <button
            type="submit"
            disabled={submitting || value.trim().length === 0}
            className="border border-gold-warm/60 border-l-0 bg-navy-deep px-6 py-4 font-mono text-mono-sm uppercase text-gold-warm transition-colors duration-200 ease-room hover:border-gold-warm hover:text-gold-deep disabled:cursor-not-allowed disabled:opacity-50 sm:px-10"
            style={{ letterSpacing: '0.22em' }}
          >
            {submitting ? 'Sending' : 'Submit'}
          </button>
        </form>
        <p className="mt-4 font-italic italic text-italic-sm text-wire-time sm:mt-5">
          or sit back and watch the room work.
        </p>
      </div>
    </section>
  );
}

export default SeedPromptCTA;
