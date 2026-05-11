'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import type { BroadcastStory } from '@/lib/story-fixture';

// VPS-DEC-043 + VPS-DEC-046: fan-discovery facets on `/story`.
//
// Thin row of pill toggles above the story list. Filter by sport, by
// era / decade, and by Olympic / Paralympic / both. Multi-facet allowed.
// URL query params reflect state so filtered views are shareable.
//
// AND across categories, OR within a category. "All" = no filter.
// Stories missing a given facet field don't appear when that filter is
// active (graceful exclusion, not crash).
//
// Sport names are OFFICIAL. PROJECT_BRIEF §10 — never NGB names.
//
// Mobile (VPS-DEC-046): pill rows become horizontal scroll-strips at
// 375px, wrap on tablet+, stay tight at desktop.

type FacetType = 'olympic' | 'paralympic' | 'both';

interface StoryFacetsProps {
  stories: BroadcastStory[];
}

// Era buckets are decade floors derived from `earliest_year`.
const ERA_BUCKETS: { label: string; floor: number; ceiling: number }[] = [
  { label: '1950s', floor: 1950, ceiling: 1959 },
  { label: '1960s', floor: 1960, ceiling: 1969 },
  { label: '1970s', floor: 1970, ceiling: 1979 },
  { label: '1980s', floor: 1980, ceiling: 1989 },
  { label: '1990s', floor: 1990, ceiling: 1999 },
  { label: '2000s', floor: 2000, ceiling: 2009 },
  { label: '2010s', floor: 2010, ceiling: 2019 },
  { label: '2020s', floor: 2020, ceiling: 2029 },
];

const TYPE_PILLS: { value: FacetType; label: string }[] = [
  { value: 'olympic', label: 'Olympic' },
  { value: 'paralympic', label: 'Paralympic' },
  { value: 'both', label: 'Both' },
];

function parseList(raw: string | null): string[] {
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

// Story matches the active facet set:
// AND across categories, OR within a category.
function storyMatches(
  story: BroadcastStory,
  sports: string[],
  eras: string[],
  types: string[],
): boolean {
  if (sports.length > 0) {
    const storySports = (story.primary_sports ?? []).map((s) => s.toLowerCase());
    if (!sports.some((s) => storySports.includes(s))) return false;
  }
  if (eras.length > 0) {
    const year = story.earliest_year;
    if (year == null) return false;
    const matched = ERA_BUCKETS.some(
      (b) => eras.includes(b.label.toLowerCase()) && year >= b.floor && year <= b.ceiling,
    );
    if (!matched) return false;
  }
  if (types.length > 0) {
    const t = story.representation_type;
    if (!t) return false;
    if (!types.includes(t)) return false;
  }
  return true;
}

interface PillProps {
  label: string;
  selected: boolean;
  onClick: () => void;
  title?: string;
}

function Pill({ label, selected, onClick, title }: PillProps) {
  // Default: gold-warm outline 1px, navy-deep fill, parchment text.
  // Selected: gold-warm fill, navy-deep text.
  // Hover: gold-deep outline.
  const base =
    'shrink-0 cursor-pointer rounded-full border px-3 py-1 font-mono text-[12px] uppercase tracking-[0.14em] transition-colors duration-200 ease-room';
  const state = selected
    ? 'border-gold-warm bg-gold-warm text-navy-deep'
    : 'border-gold-warm bg-navy-deep text-parchment hover:border-gold-deep';
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={selected}
      className={`${base} ${state}`}
    >
      {label}
    </button>
  );
}

export function StoryFacets({ stories }: StoryFacetsProps) {
  const router = useRouter();
  const params = useSearchParams();

  // Derive the union of sports across all stories — drives the pill list.
  const allSports = useMemo(() => {
    const set = new Set<string>();
    for (const s of stories) {
      for (const sport of s.primary_sports ?? []) {
        set.add(sport.toLowerCase());
      }
    }
    return Array.from(set).sort();
  }, [stories]);

  const selectedSports = parseList(params.get('sport'));
  const selectedEras = parseList(params.get('era'));
  const selectedTypes = parseList(params.get('type'));

  const anyActive =
    selectedSports.length + selectedEras.length + selectedTypes.length > 0;

  // Push URL state. Shallow replace so back-button works; no scroll jump.
  const updateParam = useCallback(
    (key: 'sport' | 'era' | 'type', next: string[]) => {
      const url = new URLSearchParams(params.toString());
      if (next.length === 0) {
        url.delete(key);
      } else {
        url.set(key, next.join(','));
      }
      const qs = url.toString();
      router.push(qs ? `/story?${qs}` : '/story', { scroll: false });
    },
    [params, router],
  );

  const toggle = useCallback(
    (key: 'sport' | 'era' | 'type', value: string) => {
      const current =
        key === 'sport' ? selectedSports : key === 'era' ? selectedEras : selectedTypes;
      const v = value.toLowerCase();
      const next = current.includes(v)
        ? current.filter((x) => x !== v)
        : [...current, v];
      updateParam(key, next);
    },
    [selectedSports, selectedEras, selectedTypes, updateParam],
  );

  const clearAll = useCallback(() => {
    router.push('/story', { scroll: false });
  }, [router]);

  const filtered = useMemo(
    () => stories.filter((s) => storyMatches(s, selectedSports, selectedEras, selectedTypes)),
    [stories, selectedSports, selectedEras, selectedTypes],
  );

  return (
    <>
      {/* Facet panel — three rows, each a horizontal scroll-strip on
          mobile, wrapping on tablet+. Hairline divider between rows. */}
      <div className="mb-10 border-y border-navy-light/60 py-6 sm:mb-12">
        <FacetRow label="Sport">
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
            {allSports.map((sport) => (
              <Pill
                key={sport}
                label={sport}
                selected={selectedSports.includes(sport)}
                onClick={() => toggle('sport', sport)}
              />
            ))}
          </div>
        </FacetRow>

        <FacetRow label="Era">
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
            {ERA_BUCKETS.map((b) => (
              <Pill
                key={b.label}
                label={b.label}
                selected={selectedEras.includes(b.label.toLowerCase())}
                onClick={() => toggle('era', b.label)}
                title={`Places where the earliest Olympian or Paralympian arrived in the ${b.label}.`}
              />
            ))}
          </div>
        </FacetRow>

        <FacetRow label="Type" last>
          <div className="flex items-center justify-between gap-4">
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
              {TYPE_PILLS.map((t) => (
                <Pill
                  key={t.value}
                  label={t.label}
                  selected={selectedTypes.includes(t.value)}
                  onClick={() => toggle('type', t.value)}
                />
              ))}
            </div>
            {anyActive && (
              <button
                type="button"
                onClick={clearAll}
                className="shrink-0 cursor-pointer font-mono text-[11px] uppercase tracking-[0.16em] text-wire-time transition-colors duration-200 ease-room hover:text-gold-warm"
              >
                Clear filters
              </button>
            )}
          </div>
        </FacetRow>
      </div>

      {/* Filtered list. Empty state preserves editorial register — no
          shrugging illustration; one italic line. */}
      {filtered.length === 0 ? (
        <p className="py-12 font-italic italic text-italic-md text-wire-text">
          No published stories match these filters yet.
        </p>
      ) : (
        <ul className="divide-y divide-navy-light border-y border-navy-light">
          {filtered.map((story) => (
            <li key={story.id}>
              <Link
                href={`/story/${story.id}`}
                className="group block py-8 transition-colors duration-200 ease-room"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <span className="font-mono text-mono-sm uppercase tracking-[0.16em] text-gold-warm/80">
                    {story.kicker_place}
                  </span>
                  <span className="shrink-0 font-mono text-mono-sm text-wire-time">
                    {new Date(story.published_at).toISOString().slice(0, 10)}
                  </span>
                </div>
                <h2 className="mt-3 font-display text-display-md leading-tight text-cream group-hover:text-gold-warm">
                  {story.headline}
                </h2>
                <p className="mt-3 max-w-2xl font-italic italic text-italic-md text-wire-text">
                  {story.dek}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

interface FacetRowProps {
  label: string;
  last?: boolean;
  children: React.ReactNode;
}

function FacetRow({ label, last, children }: FacetRowProps) {
  return (
    <div className={last ? '' : 'mb-5'}>
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-wire-time">
        {label}
      </div>
      {children}
    </div>
  );
}
