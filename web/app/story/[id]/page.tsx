import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Layout } from '@/components/Layout';
import { BroadcastPage } from '@/components/BroadcastPage';
import { getFixtureStory, type BroadcastStory } from '@/lib/story-fixture';
import { getFirestore } from '@/lib/firestore-admin';

// /story/[id] — the Broadcast surface (demo moment #4).
//
// Server component. Fixture lookup wins (so the demo route always
// renders). Then best-effort Firestore against `published_stories`. On
// any error / missing doc → notFound().
//
// PROJECT_BRIEF §6 makes the story surface auto-DQ if any athlete name
// renders. The fixture was authored without one; Firestore persists
// post-NIL-Layer text by architecture (HOE-DEC-018). Either is safe.
// `published_stories` is the BUILD_SPEC §8 forward shape; today the
// agent runtime persists `story_drafts` + `wire_events` with
// `mode='published'` (agents/editor/agent.py:759).

interface PageProps {
  // Next.js 15: dynamic route params are async.
  params: Promise<{ id: string }>;
}

/**
 * Validate a Firestore-backed published_story doc against the
 * `BroadcastStory` shape. Returns the list of missing/invalid fields so
 * the route can log a tight diff (helps debug Worker-E-style schema drift
 * without triggering a silent 404).
 */
function findMissingBroadcastFields(data: Partial<BroadcastStory>): string[] {
  const missing: string[] = [];
  if (typeof data.headline !== 'string') missing.push('headline');
  if (!Array.isArray(data.body_paragraphs)) missing.push('body_paragraphs');
  if (!Array.isArray(data.claims)) missing.push('claims');
  if (typeof data.claims_checked !== 'number') missing.push('claims_checked');
  if (typeof data.claims_passed !== 'number') missing.push('claims_passed');
  if (typeof data.claims_removed !== 'number') missing.push('claims_removed');
  if (data.narration == null) missing.push('narration');
  if (data.nil_log == null) missing.push('nil_log');
  if (data.publish_gate_audit == null) missing.push('publish_gate_audit');
  if (typeof data.kicker_place !== 'string') missing.push('kicker_place');
  if (typeof data.published_at !== 'string') missing.push('published_at');
  return missing;
}

async function tryFetchFromFirestore(id: string): Promise<BroadcastStory | null> {
  try {
    // Organic doc URLs follow the `organic-<doc_id>` convention so we can
    // distinguish them from in-repo fixtures by URL alone. Strip the
    // prefix before the Firestore lookup; reattach it on the synthesized
    // `id` field so consumers (e.g. data-story-id attributes) read a
    // stable value regardless of doc-id format.
    const isOrganicPrefixed = id.startsWith('organic-');
    const docId = isOrganicPrefixed ? id.slice('organic-'.length) : id;
    if (!docId) return null;

    const db = getFirestore();
    const snap = await db.collection('published_stories').doc(docId).get();
    if (!snap.exists) return null;
    const data = snap.data() as Partial<BroadcastStory> | undefined;
    if (!data) return null;

    // Synthesize `id` from the doc id when the field is absent (Narrator
    // writes via auto-id, so `id` lives on the doc envelope, not the body).
    const synthesized: Partial<BroadcastStory> = { ...data };
    if (typeof synthesized.id !== 'string' || synthesized.id.length === 0) {
      synthesized.id = `organic-${snap.id}`;
    }
    if (!synthesized.source) synthesized.source = 'organic';

    const missing = findMissingBroadcastFields(synthesized);
    if (missing.length > 0) {
      // eslint-disable-next-line no-console
      console.warn(
        `[story/${id}] published_stories doc ${snap.id} missing fields: ${missing.join(',')}`,
      );
      return null;
    }
    return synthesized as BroadcastStory;
  } catch {
    // No ADC / CI / Firestore unavailable — fixture path is the contract.
    return null;
  }
}

// VPS-DEC-047: per-Broadcast Open Graph + Twitter Card metadata. Lets
// `/story/<id>` URLs render rich previews on Twitter/LinkedIn/iMessage
// when the Sponsor authorizes post-contest sharing.
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const story = getFixtureStory(id) ?? (await tryFetchFromFirestore(id));
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://localhost:3000';
  if (!story) {
    return { title: "Story not found — The Storyteller's Room" };
  }
  const heroAbs =
    story.hero_image_url == null
      ? `${siteUrl}/og-default.png`
      : story.hero_image_url.startsWith('http')
        ? story.hero_image_url
        : `${siteUrl}${story.hero_image_url}`;
  const pageUrl = `${siteUrl}/story/${id}`;
  return {
    title: `${story.headline} — The Storyteller's Room`,
    description: story.dek,
    openGraph: {
      title: story.headline,
      description: story.dek,
      images: [{ url: heroAbs, width: 1376, height: 768, alt: 'Stylized hero illustration' }],
      type: 'article',
      siteName: "The Storyteller's Room",
      url: pageUrl,
      locale: 'en_US',
    },
    twitter: {
      card: 'summary_large_image',
      title: story.headline,
      description: story.dek,
      images: [heroAbs],
    },
  };
}

export default async function StoryPage({ params }: PageProps) {
  const { id } = await params;
  const story = getFixtureStory(id) ?? (await tryFetchFromFirestore(id));
  if (!story) notFound();
  return (
    <Layout>
      <BroadcastPage story={story} />
    </Layout>
  );
}

export const dynamic = 'force-dynamic';
