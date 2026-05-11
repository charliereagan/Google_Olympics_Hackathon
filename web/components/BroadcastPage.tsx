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

import type { CSSProperties } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import type { BroadcastStory } from '@/lib/story-fixture';
import { AudioBar } from '@/components/AudioBar';
import { VerifiedClaims } from '@/components/VerifiedClaims';
import {
  getInfographic,
  type StoryInfographic as StoryInfographicData,
} from '@/lib/story-infographic-fixture';

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
  // Hand-authored "BY THE NUMBERS" data, side-table keyed by story id.
  // Null = no infographic block renders (graceful no-op for stories
  // we have not authored yet). VPS Session 2, 2026-05-11.
  const infographic = getInfographic(story.id);

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

        {/* Right-edge gradient scrim — pulls the painterly hero down behind
            the hero infographic on the right so the cream/gold typography
            reads cleanly on top of the image. Covers the right ~50% of the
            hero only; the bottom scrim (above) handles the left-side
            headline darken. Desktop only — on mobile the infographic
            renders BELOW the hero, so no overlay scrim is needed. */}
        {infographic && (
          <div
            aria-hidden="true"
            className="absolute inset-y-0 right-0 hidden w-1/2 sm:block"
            style={{
              background:
                'linear-gradient(270deg, rgba(10,20,40,0.85) 0%, rgba(10,20,40,0.40) 55%, rgba(10,20,40,0) 100%)',
            }}
          />
        )}

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

        {/* Right-side hero infographic overlay — desktop only. The same
            <HeroInfographic /> renders below the hero on mobile (see the
            <section> just outside this <header>). Hidden when there is
            no hand-authored infographic for the story. */}
        {infographic && (
          <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-[36%] pr-6 pt-[8vh] sm:flex sm:flex-col sm:pr-12 lg:pr-16 lg:pt-[10vh]">
            <div className="pointer-events-auto">
              <HeroInfographic data={infographic} />
            </div>
          </div>
        )}
      </header>

      {/* Mobile-only mirror of the hero infographic — drops below the
          hero image when the right-side overlay is hidden by the
          `sm:` breakpoint. Same component, full-width, stacked. */}
      {infographic && (
        <div className="block bg-navy-deep px-6 pt-10 sm:hidden">
          <HeroInfographic data={infographic} mobile />
        </div>
      )}

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

        {/* Hand-authored infographic, ELSEWHERE half — place markers +
            resources only. The "BY THE NUMBERS" half (sport tags / big
            numbers / timeline) lives on the hero now via
            <HeroInfographic />. Renders only when STORY_INFOGRAPHICS has
            an entry for this story id. */}
        {infographic && <ElsewhereInfographic data={infographic} />}

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

/**
 * Animation delay table for the hero infographic staggered rise.
 *
 *   Sport tags ........................ 1.5s  (single block)
 *   Big numbers ....................... 2.5s, then +0.3s cascade per item
 *   Timeline .......................... 4.0s, then +0.3s cascade per row
 *
 * Each item uses the `hero-info-rise` keyframe (globals.css), 600ms
 * ease-room, `both` fill so items stay hidden until their delay
 * elapses. The existing curtain rise (kicker + headline + dek) finishes
 * at t=+1.2s, so the sport tags at +1.5s arrive just after.
 *
 * `prefers-reduced-motion` is honored globally in globals.css by
 * clamping animation-duration to 0.01ms, which collapses the keyframe
 * end-to-end and lands every item in its final state immediately.
 */
const HERO_INFO_KEYFRAME = 'hero-info-rise';
const HERO_INFO_DURATION_MS = 600;
const HERO_INFO_EASING = 'cubic-bezier(0.32, 0.72, 0, 1)'; // ease-room
const HERO_INFO_SPORT_DELAY_S = 1.5;
const HERO_INFO_BIG_NUM_BASE_S = 2.5;
const HERO_INFO_BIG_NUM_CASCADE_S = 0.3;
const HERO_INFO_TIMELINE_BASE_S = 4.0;
const HERO_INFO_TIMELINE_CASCADE_S = 0.3;

function heroInfoRise(delaySeconds: number): CSSProperties {
  return {
    animation: `${HERO_INFO_KEYFRAME} ${HERO_INFO_DURATION_MS}ms ${HERO_INFO_EASING} both`,
    animationDelay: `${delaySeconds}s`,
  };
}

/**
 * <HeroInfographic /> — the three visually striking sub-blocks
 * (sport_tags, big_numbers, timeline) that overlay the painterly hero
 * image on the right edge (desktop) or stack below the hero (mobile).
 *
 * Renders directly on the hero — no panel background, no border. A
 * right-edge gradient scrim (declared on the hero <header>) provides
 * readability for the cream/gold typography on the image.
 *
 * `mobile=true` is rendered by the `block sm:hidden` mirror below the
 * hero. The desktop overlay uses `mobile=false`. Both paths share the
 * same DOM structure and animation delays so the choreography is
 * identical whichever path the breakpoint chooses.
 *
 * Compliance: no athlete names, no logos. The hand-authored data in
 * story-infographic-fixture.ts is pre-screened (NIL-clean by
 * construction).
 */
function HeroInfographic({
  data,
  mobile = false,
}: {
  data: StoryInfographicData;
  mobile?: boolean;
}) {
  const { sport_tags, big_numbers, timeline } = data;

  // Mobile layout drops below the hero — left-aligned, full-width.
  // Desktop overlay is right-anchored on the hero image. Internals are
  // identical otherwise (always left-aligned within the column).
  const wrapperClass = mobile
    ? 'w-full max-w-md'
    : 'ml-auto w-full max-w-[320px] lg:max-w-[360px]';

  return (
    <div
      aria-label="Story infographic"
      className={wrapperClass}
    >
      {/* 1. Sport tags — horizontal row of mono caps with gold
          middle-dot separators. May wrap if the column is narrow. */}
      {sport_tags.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-mono-sm uppercase tracking-[0.18em] text-parchment"
          style={heroInfoRise(HERO_INFO_SPORT_DELAY_S)}
        >
          {sport_tags.map((tag, idx) => (
            <span key={`tag-${idx}`} className="inline-flex items-center gap-x-3">
              <span>{tag}</span>
              {idx < sport_tags.length - 1 && (
                <span aria-hidden="true" className="text-gold-warm">·</span>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Hairline divider between sport tags and big numbers. */}
      {sport_tags.length > 0 && big_numbers.length > 0 && (
        <div
          aria-hidden="true"
          className="mb-6 mt-6 h-px w-8 bg-gold-warm/40"
          style={heroInfoRise(HERO_INFO_SPORT_DELAY_S)}
        />
      )}

      {/* 2. Big numbers — stacked vertically, left-aligned. Each fades
          in on its own cascade delay. */}
      {big_numbers.length > 0 && (
        <div className="flex flex-col">
          {big_numbers.map((num, idx) => {
            const delay =
              HERO_INFO_BIG_NUM_BASE_S + idx * HERO_INFO_BIG_NUM_CASCADE_S;
            return (
              <div
                key={`num-${idx}`}
                className={
                  'flex flex-col items-start ' +
                  (idx < big_numbers.length - 1 ? 'pb-5' : '')
                }
                style={heroInfoRise(delay)}
              >
                <div className="font-display text-[40px] leading-none text-cream sm:text-[56px]">
                  {num.value}
                </div>
                <div className="mt-2 max-w-[280px] font-mono text-[11px] uppercase tracking-[0.18em] leading-snug text-cream/70 sm:text-[12px]">
                  {num.label}
                </div>
                {idx < big_numbers.length - 1 && (
                  <div
                    aria-hidden="true"
                    className="mt-5 h-px w-6 bg-gold-warm/30"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Hairline divider between big numbers and timeline. */}
      {big_numbers.length > 0 && timeline.length > 0 && (
        <div
          aria-hidden="true"
          className="mb-6 mt-6 h-px w-8 bg-gold-warm/40"
          style={heroInfoRise(
            HERO_INFO_BIG_NUM_BASE_S +
              (big_numbers.length - 1) * HERO_INFO_BIG_NUM_CASCADE_S,
          )}
        />
      )}

      {/* 3. Timeline — vertical: year | dot | label rows. Each row
          fades in on its own cascade delay. */}
      {timeline.length > 0 && (
        <ul className="flex flex-col gap-y-[12px]">
          {timeline.map((entry, idx) => {
            const delay =
              HERO_INFO_TIMELINE_BASE_S + idx * HERO_INFO_TIMELINE_CASCADE_S;
            return (
              <li
                key={`tl-${idx}`}
                className="flex items-baseline gap-x-3"
                style={heroInfoRise(delay)}
              >
                <span className="w-12 shrink-0 font-mono text-mono-sm uppercase tracking-[0.12em] tabular-nums text-gold-warm">
                  {entry.year}
                </span>
                <span
                  aria-hidden="true"
                  className="inline-block h-1.5 w-1.5 shrink-0 translate-y-[-2px] rounded-full bg-gold-warm"
                />
                <span className="font-italic italic text-[13px] leading-snug text-cream">
                  {entry.label}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/**
 * <ElsewhereInfographic /> — the pared-down half of the legacy
 * <StoryInfographic />. Renders place markers + resources between the
 * prose body and <VerifiedClaims />. The visually striking half (sport
 * tags / big numbers / timeline) has moved to the hero — see
 * <HeroInfographic />.
 *
 * Section header is "ELSEWHERE" — the "BY THE NUMBERS" framing belongs
 * with the numbers, which are no longer here. Gold hairlines above and
 * below the header preserve the existing editorial cap.
 *
 * Compliance: external resource links open in new tabs with
 * rel="noopener noreferrer". The hand-authored JSON is pre-screened
 * (no athlete names, no logos, governmental / educational /
 * institutional sources only).
 */
function ElsewhereInfographic({ data }: { data: StoryInfographicData }) {
  const { place_markers, resources } = data;
  if (place_markers.length === 0 && resources.length === 0) return null;

  return (
    <section aria-label="Elsewhere" className="mt-16 sm:mt-20">
      {/* Section header — tracked-cap parchment, gold hairlines above
          and below. Header text dropped "THE PLACE · BY THE NUMBERS"
          because the numbers now live on the hero. */}
      <div className="flex flex-col items-center">
        <div aria-hidden="true" className="h-px w-12 bg-gold-warm/40" />
        <h2 className="my-4 text-center font-mono text-mono-sm uppercase tracking-[0.18em] text-parchment">
          Elsewhere
        </h2>
        <div aria-hidden="true" className="h-px w-12 bg-gold-warm/40" />
      </div>

      <div className="mt-12 space-y-14 sm:mt-16 sm:space-y-16">
        {/* Place markers — compact cards, 3-4 across desktop, stacked
            on mobile. Thin gold border, navy-mid fill. */}
        {place_markers.length > 0 && (
          <div
            className={
              'grid grid-cols-1 gap-4 sm:gap-5 ' +
              (place_markers.length >= 4
                ? 'sm:grid-cols-2 lg:grid-cols-4'
                : 'sm:grid-cols-2 lg:grid-cols-3')
            }
          >
            {place_markers.map((marker, idx) => (
              <div
                key={`pm-${idx}`}
                className="relative border border-gold-warm/40 bg-navy-mid px-4 py-4"
              >
                <span
                  aria-hidden="true"
                  className="absolute left-2 top-2 inline-block h-1.5 w-1.5 rounded-full bg-gold-warm/80"
                />
                <p className="pl-3 font-italic italic text-[16px] leading-snug text-cream">
                  {marker.place}
                </p>
                <p className="mt-2 pl-3 font-mono text-[11px] uppercase tracking-[0.14em] leading-snug text-parchment">
                  {marker.role}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Resources — italic-Lora text links with gold-warm/40
            underline that thickens to gold-warm on hover. */}
        {resources.length > 0 && (
          <ul className="space-y-3">
            {resources.map((resource, idx) => (
              <li key={`r-${idx}`}>
                <a
                  href={resource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-italic italic text-[15px] leading-snug text-cream underline decoration-gold-warm/40 underline-offset-4 transition-colors duration-200 ease-room hover:text-cream hover:decoration-gold-warm"
                >
                  {resource.label}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default BroadcastPage;
