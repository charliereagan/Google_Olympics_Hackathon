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
  // Mount Pleasant, Iowa — fixture story, wrestling room + adaptive
  // sport pipeline in a small Henry County town. VPS Session 2 data,
  // §2 of Docs/VPS/story-infographic-data.md.
  'fixture-mount-pleasant': {
    sport_tags: ['wrestling', 'adaptive sport', 'Olympic and Paralympic'],
    big_numbers: [
      {
        value: '8',
        label: 'Olympians and Paralympians from Henry County since 1972',
      },
      {
        value: '8,500',
        label: 'Population of Mount Pleasant',
      },
      {
        value: '3',
        label: 'Generations of wrestling coaching lineage',
      },
    ],
    timeline: [
      {
        year: '1968',
        label: 'High school wrestling room enters continuous use',
      },
      {
        year: '1972',
        label: 'First Olympian from Mount Pleasant',
      },
      {
        year: '1988',
        label: 'Second Olympian — pattern starts to take shape',
      },
      {
        year: '2004',
        label: 'Community college adaptive sport program founded',
      },
      {
        year: '2020',
        label: 'First Paralympian sent to the Games (Tokyo cycle)',
      },
    ],
    place_markers: [
      {
        place: 'Mount Pleasant, Iowa',
        role: 'Population 8,500 · the wrestling room and the courthouse square',
      },
      {
        place: 'Henry County, Iowa',
        role:
          '20,000-person county that produced eight Olympians and Paralympians',
      },
      {
        place: 'Iowa Wesleyan, Mount Pleasant',
        role: 'Adaptive athletics program · three counties served · 2004–2023',
      },
    ],
    resources: [
      {
        label: 'Mount Pleasant Community School District',
        url: 'https://mtpcsd.org',
      },
      {
        label: 'Henry County, Iowa · official county government',
        url: 'https://henrycounty.iowa.gov/',
      },
      {
        label: 'Quad-City Times · hometown coverage',
        url: 'https://qctimes.com/',
      },
      {
        label: 'Olympedia · Team USA historical results',
        url: 'https://www.olympedia.org',
      },
    ],
  },
  // Birmingham, Alabama — fixture story, south-side adaptive-sports
  // training campus + city infrastructure pattern. Paralympic-anchored.
  // Authored from the fixture prose body and `claims` slugs in
  // story-fixture.ts (campus_continuous_since_1980s,
  // accessibility_retrofit_1993, first_paralympian_1996,
  // greenway_connector_2006, low_floor_bus_route_2014,
  // paralympian_to_olympian_ratio). VPS skipped this entry in
  // Docs/VPS/story-infographic-data.md; HoE authored 2026-05-11 from the
  // claims-verified prose so all 4 homepage stories carry treatment.
  'fixture-birmingham-alabama': {
    sport_tags: [
      'adaptive cycling',
      'wheelchair rugby',
      'paratriathlon',
      'sled hockey',
      'Paralympic',
    ],
    big_numbers: [
      {
        value: '5 AM',
        label:
          'The bus route, the swim block, the door rolling up — the time the campus begins, every day',
      },
      {
        value: '120',
        label:
          'City blocks of accessibility retrofit committed by Birmingham in 1993',
      },
      {
        value: '3',
        label:
          'Paralympians produced per Olympian — the inverse of the national ratio',
      },
    ],
    timeline: [
      {
        year: 'late 1980s',
        label:
          'South-side adaptive-sports training campus enters continuous operation',
      },
      {
        year: '1993',
        label:
          'City of Birmingham commits to a multi-decade accessibility retrofit across 120 city blocks',
      },
      {
        year: '1996',
        label: 'First Paralympian from the program comes home',
      },
      {
        year: '2006',
        label:
          'Wheelchair-accessible greenway opens, connecting the campus to the medical district',
      },
      {
        year: '2014',
        label:
          'Low-floor public bus route to the campus begins, 20-minute headway from 5 a.m.',
      },
    ],
    place_markers: [
      {
        place: 'South-side training campus, Birmingham',
        role:
          '40-acre facility · hardwood, indoor track, cycling loop, swimming pool, strength room',
      },
      {
        place: 'Birmingham–Medical District greenway',
        role:
          'Wheelchair-accessible greenway connector since 2006 · roughly four miles',
      },
      {
        place: 'Birmingham–Jefferson County Transit Authority',
        role:
          'Public transit operating the 5 a.m. low-floor bus route to the training campus since 2014',
      },
    ],
    resources: [
      {
        label: 'City of Birmingham, Alabama · official city government',
        url: 'https://www.birminghamal.gov/',
      },
      {
        label:
          'MAX Transit (Birmingham–Jefferson County Transit Authority) · regional public transit',
        url: 'https://maxtransit.org/',
      },
      {
        label: 'Olympedia · Paralympic results archive',
        url: 'https://www.olympedia.org',
      },
    ],
  },
  // Park City, Utah — fixture story, winter mountain town anchored to
  // the Olympic Winter Games Salt Lake City 2002 legacy. VPS Session 2
  // data, §3 of Docs/VPS/story-infographic-data.md. (VPS flagged the
  // section as drafted without full transcript; Charlie authorized
  // shipping as-is.)
  'fixture-park-city-utah': {
    sport_tags: [
      'alpine skiing',
      'snowboarding',
      'bobsled',
      'Olympic Winter and Paralympic Winter',
    ],
    big_numbers: [
      {
        value: '1:00 PM',
        label:
          'School-day dismissal during winter season — schedule bent around the chairlift',
      },
      {
        value: '2002',
        label:
          'Olympic Winter Games and Paralympic Winter Games Salt Lake City — alpine and freestyle events hosted in Park City',
      },
    ],
    timeline: [
      {
        year: '1992',
        label: 'Utah Olympic Park opens as a training facility',
      },
      {
        year: '2002',
        label:
          'Olympic Winter Games Salt Lake City — Park City hosts alpine and freestyle events',
      },
      {
        year: '2026',
        label:
          'A generation of athletes whose first Games memory is the 2002 cycle, now mid-career',
      },
    ],
    place_markers: [
      {
        place: 'Park City, Utah',
        role:
          'Mountain town where the public-school calendar bends around the chairlift schedule',
      },
      {
        place: 'Utah Olympic Park, Park City',
        role:
          'Legacy training facility for bobsled, luge, ski jump, freestyle aerials',
      },
      {
        place: 'Park City School District',
        role:
          'Public schools running early dismissal during the winter competition season',
      },
    ],
    resources: [
      {
        label: 'Utah Olympic Park · public training facility',
        url: 'https://utaholympiclegacy.org/',
      },
      {
        label: 'Park City School District',
        url: 'https://www.pcschools.us/',
      },
      {
        label: 'Olympedia · Winter Games results archive',
        url: 'https://www.olympedia.org',
      },
    ],
  },
};

/**
 * Lookup hand-authored infographic data for a story id.
 * Returns null when no data has been authored — the Broadcast page
 * then renders without the infographic block (graceful no-op).
 */
export function getInfographic(storyId: string): StoryInfographic | null {
  return STORY_INFOGRAPHICS[storyId] ?? null;
}
