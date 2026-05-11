// Story infographic fixture — hand-authored structured data that drives the
// "BY THE NUMBERS" block on Broadcast pages (VPS Session 2, 2026-05-11).
//
// Side-table keyed by `story_id`. Does NOT modify the `published_stories`
// Firestore schema or the `BroadcastStory` type. Post-submission, this
// becomes the output of a Gemini Pro structured-output pass run after the
// Storyteller drafts prose (VPS-DEC-055 candidate).
//
// Compliance: no athlete names, no NGB names as sport substitutes, no
// protected marks, no third-party logos, no timing/scoring data, no
// predictive phrasing. Resources are governmental / educational /
// archival / institutional sources only. Each `url` was HTTP-verified
// before being committed; unverified candidates were dropped.

export interface InfographicBigNumber {
  value: string;
  label: string;
}

export interface InfographicTimelineEntry {
  year: string;
  label: string;
}

export interface InfographicPlaceMarker {
  place: string;
  role: string;
}

export interface InfographicResource {
  label: string;
  url: string;
}

export interface StoryInfographic {
  sport_tags: string[];
  big_numbers: InfographicBigNumber[];
  timeline: InfographicTimelineEntry[];
  place_markers: InfographicPlaceMarker[];
  resources: InfographicResource[];
}

// Keyed by the canonical Firestore document id (or fixture id) of the
// story. Only stories with hand-authored data appear here; everything
// else falls through to `null` and renders no infographic block.
export const STORY_INFOGRAPHICS: Record<string, StoryInfographic> = {
  // Minnesota — homepage hero, organic Firestore story.
  // The route at /story/[id] receives the raw Firestore doc id in the
  // URL (CcBLDJv0y0mLzmWpQF5W), but synthesizes story.id as
  // `organic-<docId>` when persisting the BroadcastStory object
  // (app/story/[id]/page.tsx:69). The infographic lookup runs against
  // story.id, so we key on the synthesized form.
  'organic-CcBLDJv0y0mLzmWpQF5W': {
    sport_tags: ['adapted floor hockey', 'wheelchair basketball', 'Paralympic'],
    big_numbers: [
      {
        value: '6',
        label: 'Paralympic roster spots from this regional pipeline since 2004',
      },
      {
        value: '30',
        label: 'Years of sanctioned high school adaptive athletics',
      },
    ],
    timeline: [
      {
        year: '1992',
        label:
          'Structural integration of adaptive sports into the state high school league',
      },
      {
        year: '2002',
        label:
          'First global representation, roughly a decade after integration',
      },
      {
        year: '2004',
        label: 'First Paralympic roster spot from the pipeline',
      },
      {
        year: '2024',
        label: 'Three decades of uninterrupted state-league operation',
      },
    ],
    place_markers: [
      {
        place: 'Robbinsdale, Minnesota',
        role:
          'High school district running varsity adapted floor hockey under the state league',
      },
      {
        place: 'Golden Valley, Minnesota',
        role:
          'Courage Kenny Rehabilitation Institute — early community foundation, 1990s',
      },
      {
        place: 'Marshall, Minnesota',
        role:
          'Southwest Minnesota State University — collegiate wheelchair basketball continuation',
      },
    ],
    // Resource URLs were HTTP-verified before commit. Candidates that
    // returned 4xx/5xx or did not resolve were dropped, even if VPS
    // had marked them with `verify: true`. Better fewer working links
    // than more broken ones.
    resources: [
      {
        label:
          'Courage Kenny Rehabilitation Institute · adaptive sports programs',
        url: 'https://www.allinahealth.org/courage-kenny-rehabilitation-institute',
      },
      {
        label: 'Minnesota State High School League · adapted athletics',
        url: 'https://www.mshsl.org',
      },
      {
        label: 'Southwest Minnesota State Mustangs · wheelchair basketball',
        url: 'https://www.smsumustangs.com',
      },
      {
        label: 'Olympedia · global Paralympic results archive',
        url: 'https://www.olympedia.org',
      },
    ],
  },
  // Mount Pleasant, Park City, Colorado Springs — slots reserved for
  // the next iteration. Intentionally absent; `getInfographic` returns
  // null and `<BroadcastPage>` renders no infographic block until VPS's
  // hand-authored data lands here.
};

/**
 * Lookup hand-authored infographic data for a story id.
 * Returns null when no data has been authored — the Broadcast page
 * then renders without the infographic block (graceful no-op).
 */
export function getInfographic(storyId: string): StoryInfographic | null {
  return STORY_INFOGRAPHICS[storyId] ?? null;
}
