// Recent published-stories fetch helper for the front door.
//
// Strategy: best-effort Firestore against `published_stories` (the shape
// `/story/[id]/page.tsx` already understands), merged with the in-repo
// fixture stories. The fixtures guarantee the front door always renders
// even without ADC / Firestore reachable.
//
// NIL compliance: Firestore-side text is post-NIL-redacted by architecture
// (HOE-DEC-018). Fixtures were authored without individual athlete names.
// Either path is auto-DQ-safe.
//
// PROJECT_BRIEF §6 / §10–§11: no athlete names, no times, no scoring
// results, no NGB substitution. Already enforced upstream.

import { ALL_FIXTURE_STORIES, type BroadcastStory } from '@/lib/story-fixture';
import { getFirestore } from '@/lib/firestore-admin';

// Pull a wider window so that even if Firestore picks up surprise writes
// (e.g. a runtime re-deploy emits a few orphan docs without hero images),
// the gate below has plenty of qualifying candidates to choose from.
const MAX_RECENT = 12;

/**
 * Demo-safety gate. An organic story must carry every field the home-page
 * hero and the Stack depend on — INCLUDING a non-empty `hero_image_url` —
 * before it can enter the candidate pool. Stories without a hero image
 * cause a blank-hero regression on `/`, and there's no graceful fallback
 * (the gradient placeholder reads as broken on the cinematic homepage).
 *
 * The agent-runtime Cloud Run service was deleted post-submission so this
 * gate is defense-in-depth: if anything ever writes a partial doc into
 * `published_stories`, it's silently filtered out of the homepage feed.
 * (Submission day 2026-05-11.)
 */
function isUsableStory(data: Partial<BroadcastStory>): boolean {
  return (
    typeof data.headline === 'string' &&
    typeof data.kicker_place === 'string' &&
    typeof data.published_at === 'string' &&
    typeof data.dek === 'string' &&
    typeof data.hero_image_url === 'string' &&
    data.hero_image_url.length > 0
  );
}

async function tryFetchOrganic(): Promise<BroadcastStory[]> {
  try {
    const db = getFirestore();
    const snap = await db
      .collection('published_stories')
      .orderBy('published_at', 'desc')
      .limit(MAX_RECENT)
      .get();

    if (snap.empty) return [];

    const out: BroadcastStory[] = [];
    snap.forEach((doc) => {
      const data = doc.data() as Partial<BroadcastStory> | undefined;
      if (!data || !isUsableStory(data)) return;
      const synthesized: Partial<BroadcastStory> = { ...data };
      if (typeof synthesized.id !== 'string' || synthesized.id.length === 0) {
        synthesized.id = `organic-${doc.id}`;
      }
      if (!synthesized.source) synthesized.source = 'organic';
      out.push(synthesized as BroadcastStory);
    });
    return out;
  } catch {
    return [];
  }
}

/**
 * Returns the latest hero story + up to (N-1) additional recent stories.
 * The hero is the most-recently-published story by `published_at` (ISO).
 * If Firestore is unavailable, falls back to the in-repo fixtures with
 * Mount Pleasant as the hero (per worker brief).
 */
export async function getRecentStories(limit = 4): Promise<{
  hero: BroadcastStory;
  recent: BroadcastStory[];
}> {
  const organic = await tryFetchOrganic();

  // Merge organic + fixtures, de-duplicated by id; sort by published_at desc.
  const seen = new Set<string>();
  const merged: BroadcastStory[] = [];
  for (const s of [...organic, ...ALL_FIXTURE_STORIES]) {
    if (seen.has(s.id)) continue;
    seen.add(s.id);
    merged.push(s);
  }
  merged.sort((a, b) => (a.published_at < b.published_at ? 1 : -1));

  // Hero rule: per worker brief, default to Mount Pleasant if Firestore is
  // empty. Otherwise the freshest organic story takes the hero slot.
  const heroIsFixture = organic.length === 0;
  const hero = heroIsFixture
    ? ALL_FIXTURE_STORIES.find((s) => s.id === 'fixture-mount-pleasant') ?? merged[0]
    : merged[0];

  const recent = merged.filter((s) => s.id !== hero.id).slice(0, limit);
  return { hero, recent };
}
