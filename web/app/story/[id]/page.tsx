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

async function tryFetchFromFirestore(id: string): Promise<BroadcastStory | null> {
  try {
    const db = getFirestore();
    const snap = await db.collection('published_stories').doc(id).get();
    if (!snap.exists) return null;
    const data = snap.data() as Partial<BroadcastStory> | undefined;
    if (!data) return null;
    // Validate minimum surface — fall back rather than render half-broken.
    if (
      typeof data.id === 'string' &&
      typeof data.headline === 'string' &&
      Array.isArray(data.body_paragraphs) &&
      Array.isArray(data.claims) &&
      data.narration != null &&
      data.nil_log != null &&
      data.publish_gate_audit != null
    ) {
      return data as BroadcastStory;
    }
    return null;
  } catch {
    // No ADC / CI / Firestore unavailable — fixture path is the contract.
    return null;
  }
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
