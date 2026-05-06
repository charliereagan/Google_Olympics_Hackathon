'use client';

/**
 * <DisambiguationTrace> — one detailed Layer trace, inline.
 *
 * The marquee moment of /publish-gate: ambiguous span underlined gold-warm,
 * four-step rationale, cleared sentence. All hairline rules; mono labels;
 * italic-Lora detail. Fictional surname tokens only (`[athlete:A]`,
 * `[athlete:B]`) — PROJECT_BRIEF §6.
 */

import { motion, useReducedMotion } from 'framer-motion';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

interface DisambiguationStep {
  label: string;
  detail: string;
}

const TRACE_STEPS: DisambiguationStep[] = [
  {
    label: 'Step 1 — surface match',
    detail: '3 candidates found in athlete_registry on the token "Mount Pleasant".',
  },
  {
    label: 'Step 2 — context vector',
    detail: 'Surrounding 50-char window tokens: [town, Iowa, population, school, since, 1976].',
  },
  {
    label: 'Step 3 — candidate ranking',
    detail: '0.91 place (Mount Pleasant, IA) · 0.06 [athlete:A] · 0.03 [athlete:B].',
  },
  {
    label: 'Step 4 — resolution',
    detail: 'Place. No redaction required. Sentence cleared for publish.',
  },
];

const ORIGINAL_SENTENCE_BEFORE = 'A river town of 8,500 — ';
const AMBIGUOUS_SPAN = 'Mount Pleasant';
const ORIGINAL_SENTENCE_AFTER = ', Iowa — has produced eight Olympians and Paralympians since 1976.';

const CLEARED_SENTENCE = '"A river town of 8,500 — Mount Pleasant, Iowa — has produced eight Olympians and Paralympians since 1976."';

export function DisambiguationTrace() {
  const reduceMotion = useReducedMotion();
  const initial = reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 };

  return (
    <section
      aria-labelledby="disambig-heading"
      className="mt-16 border-t border-navy-light pt-10 sm:mt-20 sm:pt-14"
    >
      <p
        id="disambig-heading"
        className="font-body text-caption uppercase tracking-[0.18em] text-gold-warm"
      >
        Disambiguation trace
      </p>
      <p className="mt-3 font-italic italic text-italic-md text-wire-text max-w-2xl">
        One ambiguous span, four steps, one cleared sentence. The Layer&rsquo;s reasoning is shown in full.
      </p>

      {/* Hairline rule above the original sentence */}
      <div aria-hidden="true" className="mt-8 h-px w-4/5 bg-gold-warm/60" />

      {/* Original sentence with the ambiguous span underlined gold-warm */}
      <motion.p
        initial={initial}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: ROOM_EASE }}
        className="mt-6 font-body text-body-md leading-[1.7] text-cream max-w-3xl"
      >
        <span className="text-slate-room">draft &mdash; </span>
        {ORIGINAL_SENTENCE_BEFORE}
        <span
          className="border-b border-gold-warm pb-px"
          aria-label={`ambiguous span: ${AMBIGUOUS_SPAN}`}
        >
          {AMBIGUOUS_SPAN}
        </span>
        {ORIGINAL_SENTENCE_AFTER}
      </motion.p>

      {/* The four steps — hairline-indented, mono labels, Lora detail */}
      <ol className="mt-10 space-y-5 sm:space-y-6 max-w-3xl">
        {TRACE_STEPS.map((step, idx) => (
          <motion.li
            key={step.label}
            initial={initial}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: ROOM_EASE, delay: 0.05 * (idx + 1) }}
            className="border-l border-navy-light pl-5 sm:pl-6"
          >
            <p className="font-mono text-mono-sm tracking-[0.04em] text-gold-warm/80">
              {step.label}
            </p>
            <p className="mt-1 font-italic italic text-italic-sm text-wire-text leading-[1.55]">
              {step.detail}
            </p>
          </motion.li>
        ))}
      </ol>

      {/* Hairline rule before the cleared sentence */}
      <div aria-hidden="true" className="mt-10 h-px w-4/5 bg-gold-warm/60" />

      {/* The cleared sentence — italicized */}
      <motion.p
        initial={initial}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: ROOM_EASE, delay: 0.3 }}
        className="mt-6 font-italic italic text-italic-md text-cream leading-[1.6] max-w-3xl"
      >
        <span className="not-italic font-body text-caption uppercase tracking-[0.18em] text-gold-warm">
          cleared &nbsp;&middot;&nbsp;
        </span>
        {CLEARED_SENTENCE}
      </motion.p>
    </section>
  );
}

export default DisambiguationTrace;
