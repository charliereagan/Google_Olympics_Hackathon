import { Layout } from '@/components/Layout';

// Static fixture for Day-8 pass-1 design review. Renders every locked token
// from design-system.md §2 and §3 visible at once: 11-color swatch grid,
// the 9 type-scale samples, sample headings, body, captions, mono
// timestamps. The HoE screenshots this for review.

const COLORS: Array<{ name: string; varName: string; hex: string; note: string }> = [
  { name: 'navy-deep', varName: '--navy-deep', hex: '#0A1428', note: 'page background, hero darken' },
  { name: 'navy-mid', varName: '--navy-mid', hex: '#1A2740', note: 'panels, lower thirds, Floor node fill' },
  { name: 'navy-light', varName: '--navy-light', hex: '#2C3E5A', note: 'hairline dividers, subtle borders' },
  { name: 'gold-warm', varName: '--gold-warm', hex: '#D4A84A', note: 'hairline rules, headlines, particles' },
  { name: 'gold-deep', varName: '--gold-deep', hex: '#A8842F', note: 'hover states, active sentence underline' },
  { name: 'cream', varName: '--cream', hex: '#F5EFE0', note: 'primary body text on navy' },
  { name: 'parchment', varName: '--parchment', hex: '#E8DDC4', note: 'Investigator agent color signature' },
  { name: 'agitos-red', varName: '--agitos-red', hex: '#C8102E', note: 'Equity Editor — never the actual logo' },
  { name: 'slate-room', varName: '--slate-room', hex: '#5A6878', note: 'secondary text, tool-call cards' },
  { name: 'wire-text', varName: '--wire-text', hex: '#B8C4D6', note: 'Wire body text, slightly desaturated cream' },
  { name: 'wire-time', varName: '--wire-time', hex: '#7A8AA0', note: 'Wire timestamps in mono' },
];

const TYPE_SAMPLES: Array<{
  name: string;
  className: string;
  family: string;
  spec: string;
  text: string;
}> = [
  {
    name: 'display-xl',
    // Mobile step-down (design-system.md §4 / worker prompt): on iPhone the
    // 96px specimen overflows the 375px viewport — step to display-md, then
    // display-lg at sm:, full display-xl at md:. Tokens themselves are
    // unchanged; only the sample's applied size scales with viewport.
    className:
      'font-display text-display-md sm:text-display-lg md:text-display-xl',
    family: 'Playfair Display',
    spec: '96px / 1.05 / -0.02em',
    text: 'A small town builds a generation.',
  },
  {
    name: 'display-lg',
    className: 'font-display text-display-md sm:text-display-lg',
    family: 'Playfair Display',
    spec: '64px / 1.10 / -0.015em',
    text: 'Where Team USA stories begin.',
  },
  {
    name: 'display-md',
    className: 'font-display text-display-md',
    family: 'Playfair Display',
    spec: '40px / 1.15 / -0.01em',
    text: 'The geography of a quiet pipeline.',
  },
  {
    name: 'italic-md',
    className: 'font-italic italic text-italic-md',
    family: 'Lora italic',
    spec: '22px / 1.4',
    text: 'A dek-style sentence in restrained editorial italic.',
  },
  {
    name: 'italic-sm',
    className: 'font-italic italic text-italic-sm',
    family: 'Lora italic',
    spec: '15px / 1.4',
    text: 'Hometown Scout',
  },
  {
    name: 'body-md',
    className: 'font-body text-body-md',
    family: 'Inter',
    spec: '17px / 1.7',
    text: 'Wire body and broadcast paragraphs sit at this measure. Generous leading; long-form readability.',
  },
  {
    name: 'body-sm',
    className: 'font-body text-body-sm',
    family: 'Inter',
    spec: '13px / 1.5',
    text: 'Tool-call cards and secondary metadata read at this size.',
  },
  {
    name: 'caption',
    className: 'font-body text-caption uppercase',
    family: 'Inter (tracked, small caps)',
    spec: '11px / 1.3 / 0.12em',
    text: 'decision · milestone · intervention',
  },
  {
    name: 'mono-sm',
    className: 'font-mono text-mono-sm tabular-nums',
    family: 'JetBrains Mono',
    spec: '12px / 1.4 / 0.02em',
    text: '14:23:08 utc · evt_8a4f2c · 11,188 rows',
  },
];

const CAPTION_TAGS = ['decision', 'milestone', 'intervention', 'thinking', 'handoff'];

const TIMESTAMPS = ['14:23:08', '14:23:11', '14:23:14', '14:23:19', '14:23:24'];

export default function FixturePage() {
  return (
    <Layout>
      <article className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16 md:px-8 md:py-20">
        {/* Header */}
        <header className="mb-10 border-b border-navy-light pb-6 sm:mb-16 sm:pb-8">
          <p className="mb-3 font-body text-caption uppercase text-gold-warm">
            design system · day 8 · pass 1
          </p>
          <h1 className="font-display text-display-md text-cream sm:text-display-lg">
            The Storyteller&rsquo;s Room
          </h1>
          <p className="mt-3 max-w-2xl font-italic italic text-italic-md text-wire-text">
            Locked tokens. Every color and every type sample below is a hard
            constraint on every component that follows.
          </p>
        </header>

        {/* Colors */}
        <section className="mb-20">
          <h2 className="mb-2 font-display text-display-md text-cream">
            Colors
          </h2>
          <p className="mb-8 font-body text-body-sm text-slate-room">
            design-system.md §2 — 11 locked tokens. Every UI surface uses these
            and only these.
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {COLORS.map((c) => (
              <div
                key={c.name}
                className="overflow-hidden border border-navy-light"
              >
                <div
                  className="h-24 w-full"
                  style={{ background: c.hex }}
                  aria-hidden="true"
                />
                <div className="bg-navy-mid p-4">
                  <div className="flex items-baseline justify-between">
                    <span className="font-italic italic text-italic-sm text-cream">
                      {c.name}
                    </span>
                    <span className="font-mono text-mono-sm text-wire-time">
                      {c.hex}
                    </span>
                  </div>
                  <p className="mt-2 font-body text-body-sm text-slate-room">
                    {c.note}
                  </p>
                  <p className="mt-1 font-mono text-mono-sm text-wire-time">
                    {c.varName}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Type scale */}
        <section className="mb-20">
          <h2 className="mb-2 font-display text-display-md text-cream">
            Type scale
          </h2>
          <p className="mb-8 font-body text-body-sm text-slate-room">
            design-system.md §3 — 9 size + family pairings. Display = Playfair
            Display. Body = Inter. Italic = Lora italic. Mono = JetBrains
            Mono. No system fonts. No Inter as display.
          </p>
          <div className="space-y-12">
            {TYPE_SAMPLES.map((s) => (
              <div
                key={s.name}
                className="border-l border-gold-warm/40 pl-6"
              >
                <div className="mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
                  <span className="font-italic italic text-italic-sm text-cream">
                    {s.name}
                  </span>
                  <span className="font-mono text-mono-sm text-wire-time">
                    {s.family}
                  </span>
                  <span className="font-mono text-mono-sm text-wire-time">
                    {s.spec}
                  </span>
                </div>
                <p className={`${s.className} text-cream`}>{s.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Sample composition: heading + dek + body */}
        <section className="mb-20">
          <h2 className="mb-2 font-display text-display-md text-cream">
            Editorial composition
          </h2>
          <p className="mb-8 font-body text-body-sm text-slate-room">
            How the type scale stacks in a Broadcast page.
          </p>
          <div className="border border-navy-light bg-navy-mid p-6 sm:p-10">
            <p className="mb-4 font-body text-caption uppercase text-gold-warm">
              hometown · iowa
            </p>
            <h3 className="font-display text-display-md text-cream sm:text-display-lg">
              Eight Olympians since 1976.
            </h3>
            <p className="mt-4 max-w-xl font-italic italic text-italic-md text-wire-text">
              A river town of 8,500 people has produced a generation of Team
              USA athletes &mdash; and the program that built them is still
              quietly running.
            </p>
            <div className="mt-8 max-w-prose font-body text-body-md text-cream">
              <p>
                The first Olympian came in 1964 from a high school program
                that had been running, in some form, for two decades. The
                next arrived in 1972. By the time the seventh came through
                in 1996, the town had built something none of its neighbors
                had: a continuous adaptive-sport pipeline, two coaching
                lineages, and a community memory of how to send a kid to the
                Games.
              </p>
            </div>
            {/* Gold hairline like the WireRow */}
            <div className="mt-10 h-px w-4/5 bg-gold-warm/70" aria-hidden="true" />
          </div>
        </section>

        {/* Caption tags */}
        <section className="mb-20">
          <h2 className="mb-2 font-display text-display-md text-cream">
            Caption tags
          </h2>
          <p className="mb-8 font-body text-body-sm text-slate-room">
            design-system.md §3 caption — Inter, tracked-out small caps, 11px.
            The vocabulary of the Wire&rsquo;s lower-third nameplates.
          </p>
          <div className="flex flex-wrap gap-3">
            {CAPTION_TAGS.map((tag) => (
              <span
                key={tag}
                className="border border-navy-light bg-navy-mid px-3 py-2 font-body text-caption uppercase text-gold-warm"
              >
                {tag}
              </span>
            ))}
          </div>
        </section>

        {/* Mono timestamps */}
        <section className="mb-20">
          <h2 className="mb-2 font-display text-display-md text-cream">
            Mono timestamps
          </h2>
          <p className="mb-8 font-body text-body-sm text-slate-room">
            JetBrains Mono, tabular-nums. Wire row time column.
          </p>
          <div className="flex flex-col gap-2">
            {TIMESTAMPS.map((t) => (
              <span
                key={t}
                className="font-mono text-mono-sm tabular-nums text-wire-time"
              >
                {t} utc
              </span>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-24 border-t border-navy-light pt-6">
          <p className="font-body text-caption uppercase text-slate-room">
            design-system.md · v1.0 · day-8 baseline
          </p>
        </footer>
      </article>
    </Layout>
  );
}
