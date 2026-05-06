'use client';

/**
 * <BroadcastPage> — client-side renderer for /story/[id]. Demo moment #4.
 *
 * Spec: design-system.md §4-§6, BUILD_SPEC §3.7 + §7.1 (compression_factor
 * 0.25 hero = slow opacity 0→1 over 800ms + 2s scale 1.05→1.00 with room
 * cubic-bezier — documentary cold-open pacing). Atmosphere only — the
 * fixture hero is CSS gradients + the <Layout> grain overlay; never a
 * portrait, never a person, never AI-generated faces.
 */

import { motion, useReducedMotion } from 'framer-motion';
import type { BroadcastStory } from '@/lib/story-fixture';
import { AudioBar } from '@/components/AudioBar';
import { VerifiedClaims } from '@/components/VerifiedClaims';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];

interface BroadcastPageProps {
  story: BroadcastStory;
}

const pad = (n: number) => n.toString().padStart(2, '0');

/** ISO → `HH:MM:SS` (kicker) and `YYYY-MM-DD HH:MM:SS UTC` (footer). */
function formatTimes(iso: string): { hms: string; full: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { hms: '--:--:--', full: iso };
  const hms = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  const date = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  return { hms, full: `${date} ${hms} UTC` };
}

export function BroadcastPage({ story }: BroadcastPageProps) {
  const reduceMotion = useReducedMotion();
  const { hms: kickerTime, full: footerTime } = formatTimes(story.published_at);

  // Drop-cap split — first letter styled separately from the remainder.
  const firstParagraph = story.body_paragraphs[0] ?? '';
  const dropCap = firstParagraph.slice(0, 1);
  const firstParaRest = firstParagraph.slice(1);
  const remainingParagraphs = story.body_paragraphs.slice(1);
  const pullQuoteAfter = story.pull_quote_after_paragraph;

  return (
    <article
      data-story-id={story.id}
      className="relative w-full"
      aria-labelledby="broadcast-headline"
    >
      {/* ---- HERO — full-bleed, ~85vh ---- */}
      <header className="relative h-[85vh] min-h-[560px] w-full overflow-hidden">
        {/* Atmosphere only: when a stylized hero image is present
            (PROJECT_BRIEF §6 — places/facilities, never people), render
            it under the gradient overlays. When null, the gradient itself
            is the hero (editorial fallback). The grain overlay in
            <Layout> provides film-grain texture in either path. */}
        {story.hero_image_url ? (
          <motion.img
            aria-hidden="true"
            src={story.hero_image_url}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            initial={reduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 1.05 }}
            animate={{ opacity: 1, scale: 1.0 }}
            transition={{
              // Documentary cold-open pacing per BUILD_SPEC §3.7 / §7.1.
              opacity: { duration: 0.8, ease: ROOM_EASE },
              scale: { duration: 2.0, ease: ROOM_EASE },
            }}
          />
        ) : (
          <motion.div
            aria-hidden="true"
            className="absolute inset-0"
            initial={reduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 1.05 }}
            animate={{ opacity: 1, scale: 1.0 }}
            transition={{
              opacity: { duration: 0.8, ease: ROOM_EASE },
              scale: { duration: 2.0, ease: ROOM_EASE },
            }}
            style={{
              // Warm gold lens flare upper-left + deep navy horizon
              // lower-right + base navy-deep→navy-mid→navy-deep wash.
              backgroundImage:
                'radial-gradient(ellipse 60% 45% at 18% 28%, rgba(212,168,74,0.18), transparent 70%), ' +
                'radial-gradient(ellipse 80% 55% at 80% 90%, rgba(10,20,40,0.95), transparent 70%), ' +
                'linear-gradient(180deg, #0A1428 0%, #1A2740 60%, #0A1428 100%)',
            }}
          />
        )}

        {/* Soft bottom-anchored darken so text always reads. */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-1/2"
          style={{
            background:
              'linear-gradient(180deg, rgba(10,20,40,0) 0%, rgba(10,20,40,0.85) 100%)',
          }}
        />

        {/* Bottom-left content stack — kicker / title / dek. Tight max-width. */}
        <motion.div
          className="absolute bottom-6 left-6 right-6 max-w-3xl sm:bottom-12 sm:left-12 sm:right-12 lg:bottom-20 lg:left-20"
          initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            // Stagger matches BUILD_SPEC §7.1 curtain rise t=1.2s.
            duration: 1.2,
            delay: reduceMotion ? 0 : 0.6,
            ease: ROOM_EASE,
          }}
        >
          <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-gold-warm">
            {story.kicker_place} · {kickerTime}
          </p>
          <h1
            id="broadcast-headline"
            className="mt-4 font-display text-display-md text-cream sm:text-display-lg lg:text-display-xl"
          >
            {story.headline}
          </h1>
          <p className="mt-4 max-w-2xl font-italic italic text-italic-md text-wire-text">
            {story.dek}
          </p>
        </motion.div>
      </header>

      {/* ---- NARRATION AUDIO BAR — sticky just below hero ---- */}
      <div className="sticky top-0 z-10 bg-navy-deep/95 backdrop-blur-[2px]">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <AudioBar
            src={story.narration.audio_url}
            duration_s_fallback={story.narration.duration_s}
            voice_name={story.narration.voice_name}
          />
        </div>
      </div>

      {/* ---- BODY — editorial measure, generous vertical rhythm ---- */}
      <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20 lg:py-24">
        <div className="space-y-8">
          {/* Drop cap: Playfair Display, gold-warm, floated. The cap is
              the ornament — no boxing, no background. */}
          <p className="font-body text-body-md leading-[1.75] text-cream">
            <span
              aria-hidden="true"
              className="float-left mr-3 font-display text-[64px] leading-[0.9] text-gold-warm sm:text-[80px]"
              style={{ marginTop: '0.1em' }}
            >
              {dropCap}
            </span>
            {/* Visible cap is aria-hidden; sr-only companion preserves
                the full first character for screen readers. */}
            <span className="sr-only">{dropCap}</span>
            {firstParaRest}
          </p>

          {remainingParagraphs.map((paragraph, idx) => {
            // idx within remaining is shifted by 1 vs body_paragraphs.
            const showQuote =
              story.pull_quote != null &&
              pullQuoteAfter != null &&
              idx + 1 === pullQuoteAfter + 1;
            return (
              <div key={`para-${idx}`} className="space-y-8">
                {showQuote && story.pull_quote && <PullQuote text={story.pull_quote} />}
                <p className="font-body text-body-md leading-[1.75] text-cream">{paragraph}</p>
              </div>
            );
          })}

          {/* Pull-quote after the final paragraph */}
          {story.pull_quote &&
            pullQuoteAfter != null &&
            pullQuoteAfter + 1 >= story.body_paragraphs.length && (
              <PullQuote text={story.pull_quote} />
            )}
        </div>

        <VerifiedClaims
          claims={story.claims}
          total_checked={story.claims_checked}
          total_passed={story.claims_passed}
          total_removed={story.claims_removed}
        />

        {/* Publish Gate signature footer */}
        <footer className="mt-16 sm:mt-20">
          <div
            aria-hidden="true"
            className="h-px w-full bg-navy-light"
          />
          <div className="mt-4 space-y-1">
            <p className="font-mono text-[11px] tracking-tight text-wire-time">
              [NIL: {story.nil_log.direct_matches_redacted}r/
              {story.nil_log.aggregations_applied}a] ·{' '}
              {story.publish_gate_audit.total_claims_checked} claims checked ·{' '}
              NIL Redaction Layer{' '}
              {story.publish_gate_audit.nil_layer_passed ? 'passed' : 'failed'}{' '}
              · Publish Gate{' '}
              {story.publish_gate_audit.publish_gate_cleared
                ? 'cleared'
                : 'returned'}
            </p>
            <p className="font-mono text-[11px] tracking-tight text-wire-time">
              Published {footerTime} · Story ID: {story.id}
            </p>
          </div>
        </footer>
      </section>
    </article>
  );
}

/**
 * Inline pull-quote — Lora italic, italic-md, indented with hairlines
 * above and below per the design-system §6 hairline rule.
 */
function PullQuote({ text }: { text: string }) {
  return (
    <figure className="my-2 px-4 sm:px-10">
      <div aria-hidden="true" className="h-px w-16 bg-gold-warm/70" />
      <blockquote className="my-5 font-italic italic text-italic-md leading-[1.5] text-cream">
        {text}
      </blockquote>
      <div aria-hidden="true" className="h-px w-16 bg-gold-warm/70" />
    </figure>
  );
}

export default BroadcastPage;
