// Story fixture — synthetic published story for `/story/fixture-mount-pleasant`.
// Always renders even without Firestore. PROJECT_BRIEF §6/§10–11 compliant:
// no athlete names, no times, no scoring, no NGB substitution, no forbidden
// Storyteller words. Shape mirrors agents/storyteller StoryDraft + Narrator
// manifest + publish_gate audit, reduced to what the frontend renders.

export interface StoryClaim {
  slug: string;     // mono slug, audit-grade identifier
  text: string;     // human-readable claim sentence
  source: string;   // citation string, right-aligned
}

export interface StoryNarrationMeta {
  voice_name: string;      // BUILD_SPEC §3.6: `Algenib` for Broadcast
  duration_s: number;      // fallback duration before audio metadata loads
  audio_url: string;       // may 404 in fixture; player degrades gracefully
}

export interface StoryNilLog {
  direct_matches_redacted: number;
  aggregations_applied: number;
}

export interface BroadcastStory {
  id: string;
  kicker_place: string;             // "PUBLISHED · MT PLEASANT · IOWA"
  published_at: string;             // ISO 8601
  headline: string;                 // Playfair Display, 8-12 words
  dek: string;                      // Lora italic, one sentence
  hero_image_url: string | null;    // /public path; null = use CSS gradient fallback
  body_paragraphs: string[];        // body-md cream
  pull_quote: string | null;        // optional inline italic quote
  pull_quote_after_paragraph: number | null;
  claims_checked: number;
  claims_passed: number;
  claims_removed: number;
  claims: StoryClaim[];
  narration: StoryNarrationMeta;
  nil_log: StoryNilLog;
  publish_gate_audit: {
    total_claims_checked: number;
    nil_layer_passed: boolean;
    publish_gate_cleared: boolean;
  };
}


// FIXTURE: Mount Pleasant, Iowa — small-town wrestling pipeline story.
// Synthetic prose; place names are real-sounding. No athlete names. No
// NGB names. No medal counts. No times. No scoring results.

export const FIXTURE_MOUNT_PLEASANT: BroadcastStory = {
  id: 'fixture-mount-pleasant',
  kicker_place: 'PUBLISHED · MOUNT PLEASANT · IOWA',
  published_at: '2026-05-05T13:43:25Z',
  headline: 'A small town builds a generation.',
  dek: 'Eight thousand five hundred people. A wrestling room older than most of its kids. And a quiet pipeline that keeps sending its newest Olympian to the Games.',
  hero_image_url: '/fixture/heroes/mount-pleasant.png',
  body_paragraphs: [
    "The wrestling room at the high school in Mount Pleasant, Iowa, has been in the same place since 1968. The mats have been replaced. The lights have been replaced. The roof has been replaced twice. The room has not. It sits on the south end of the building, two doors down from a janitor's closet, and at four in the afternoon on most weekdays of the school year a particular sound comes out of it: the scuff of bare feet on canvas, the slap of a body landing flat, the long exhalation of a kid who has just been turned over and is deciding whether to stand back up.",
    "The town's first Olympian came home in 1972. The next came in 1988. By the time the room produced its newest Olympian for the Tokyo cycle, the pattern had stopped looking like luck. Eight Olympians and Paralympians have come from a county of twenty thousand people. None of them had quite the same path. All of them passed through the same room, taught by a coaching lineage three generations deep.",
    "What Mount Pleasant has is not a secret. The town is unremarkable in the ways small Midwestern towns are unremarkable. There is a courthouse square. There is a community college. There is a river ten miles east and a county fair every August. What it has is a wrestling tradition that did not die when the rural population thinned, an adaptive sport program at the community college that began in 2004 and now serves three counties, and a pattern of older athletes coming back to coach the next class without anyone asking them to.",
    "The adaptive program is the part of the story most outside the county does not know. It started with a single athlete and a coach who was willing to read the rulebook on a Sunday afternoon. By 2014 it had its own dedicated practice slot, its own travel budget, and its own line item in the college's athletic department. By 2020 it had sent its first Paralympian to the Games. The program runs alongside the able-bodied wrestling pipeline, not under it. Practice schedules overlap. Coaches move between rooms. Athletes from both sides have, on quiet nights, drilled the same takedown.",
    "What the room produces is not Olympians, exactly. The room produces a habit. The habit is to come back tomorrow. The habit is to drill the same setup three hundred times in a winter. The habit is, when an older kid comes home for Thanksgiving in their first year out of college, to walk into the room and put their shoes on. Eight Olympians and Paralympians is a number. The habit is the thing.",
  ],
  pull_quote: 'Eight Olympians and Paralympians from a county of twenty thousand. The pattern stopped looking like luck a long time ago.',
  pull_quote_after_paragraph: 1,
  claims_checked: 14,
  claims_passed: 12,
  claims_removed: 2,
  claims: [
    { slug: 'olympians_count_since_1972', text: 'Eight Olympians and Paralympians have come from Mount Pleasant and surrounding Henry County since 1972.', source: 'olympedia.org · Team USA roster · Henry County historical society' },
    { slug: 'wrestling_room_continuity', text: 'The high school wrestling room has been in continuous use since 1968.', source: 'Mount Pleasant Community School District archives' },
    { slug: 'adaptive_program_founded_2004', text: 'The community college adaptive sport program was founded in 2004 and now serves three counties.', source: 'Iowa Wesleyan adaptive athletics program records' },
    { slug: 'first_paralympian_2020', text: 'The adaptive program sent its first Paralympian to the Games in the 2020 cycle.', source: 'Team USA Paralympic roster · regional press archive' },
    { slug: 'coaching_lineage_three_generations', text: 'The coaching lineage in the wrestling room runs three generations deep, with returning athletes regularly stepping in as assistant coaches.', source: 'Henry County school district · oral history project' },
  ],
  narration: { voice_name: 'Algenib', duration_s: 179, audio_url: '/fixture/narration-mount-pleasant.mp3' },
  nil_log: { direct_matches_redacted: 2, aggregations_applied: 1 },
  publish_gate_audit: { total_claims_checked: 14, nil_layer_passed: true, publish_gate_cleared: true },
};

// FIXTURE: Birmingham, Alabama — adaptive-sports facility + city
// infrastructure pattern. Paralympic-anchored. The published outcome of
// the Equity Editor demo intervention. Synthetic prose; no athlete
// names; no NGB names; no medal counts; no times; no scoring results.

export const FIXTURE_BIRMINGHAM_ALABAMA: BroadcastStory = {
  id: 'fixture-birmingham-alabama',
  kicker_place: 'PUBLISHED · BIRMINGHAM · ALABAMA',
  published_at: '2026-05-05T13:38:11Z',
  headline: 'A city remade for the rest of itself.',
  dek: 'A campus on the south side, a bus route that runs at five in the morning, and three decades of policy decisions that turned a regional facility into a Paralympic pipeline.',
  hero_image_url: '/fixture/heroes/birmingham-alabama.png',
  body_paragraphs: [
    "The warehouse door at the south-side training campus rolls up at six in the morning with a squeal that has not been fixed in eighteen years. The staff like the squeal. It tells them the door is open. By six-fifteen the indoor track is in use; by six-thirty the rugby court is in use; by seven the swimming pool smells the way pools smell — chlorine and rubber wheel-tread, wet concrete, the faint copper of a railing that gets gripped a thousand times a day.",
    "What Birmingham has is not a facility. It is a forty-acre campus with a hardwood gymnasium painted with the four try zones of wheelchair rugby, an indoor track resurfaced in 2019, an outdoor cycling loop that connects via curb-cut sidewalk to a city greenway, a swimming pool sized to international competition spec, and a strength room with floor-anchored equipment built for athletes who train from a chair. The campus has been continuously operating since the late 1980s. It is one of four facilities in the country that produces more Paralympians than Olympians. The room is showing you why.",
    "The pipeline did not start with a building. It started with a sidewalk. In 1993 the city committed to a multi-decade accessibility retrofit — curb cuts, transit ramps, sidewalk grade corrections on roughly a hundred and twenty blocks of the city's south side. By 2006 a downtown bike-and-wheelchair greenway connected the training campus directly to the medical district four miles north. By 2014 a low-floor public bus route ran from the campus to the airport every twenty minutes from five a.m. The athletes did not arrive because someone built a gym. They arrived because they could get to the gym at five in the morning without asking anyone for a ride.",
    "The programs that the campus sustains are concrete and unromantic. Adaptive cycling on the outdoor loop. Wheelchair rugby on the hardwood. Paratriathlon training that uses the pool, the loop, and the track in a single morning. Sled hockey at a partner rink eleven miles east, on ice time the campus pays for. The schedules are posted on a corkboard inside the main entrance. The corkboard has been replaced. The schedule has not — the same five a.m. swim block has held since 2002, and the staff have been told, more than once, not to move it.",
    "What the campus produces is a number the rest of the country does not quite know how to read. Roughly three Paralympians have come out of this program for every Olympian — the inverse of the national ratio. The first Paralympian came home in 1996. The newest came home in the Paris cycle. There have been twenty-one in between, across seven sports. The pattern is not the people. The pattern is the sidewalk, the schedule, the bus, and the door that opens at six.",
  ],
  pull_quote: 'The athletes did not arrive because someone built a gym. They arrived because they could get to the gym at five in the morning without asking anyone for a ride.',
  pull_quote_after_paragraph: 2,
  claims_checked: 16,
  claims_passed: 14,
  claims_removed: 2,
  claims: [
    { slug: 'campus_continuous_since_1980s', text: 'The south-side adaptive-sports training campus has been continuously operating since the late 1980s.', source: 'Birmingham regional adaptive athletics archive · municipal records' },
    { slug: 'four_facilities_paralympic_majority', text: 'The campus is one of four U.S. facilities where Paralympian production exceeds Olympian production.', source: 'Team USA roster aggregation · 1988–2024 cycles' },
    { slug: 'accessibility_retrofit_1993', text: 'In 1993 the city committed to a multi-decade accessibility retrofit covering approximately 120 city blocks of the south side.', source: 'City of Birmingham public works · 1993 capital plan' },
    { slug: 'greenway_connector_2006', text: 'A downtown wheelchair-accessible greenway connecting the training campus to the medical district opened in 2006.', source: 'Jefferson County transit authority records' },
    { slug: 'low_floor_bus_route_2014', text: 'A low-floor public bus route serving the campus on a twenty-minute headway from 5 a.m. has operated since 2014.', source: 'Birmingham-Jefferson County Transit Authority service plans' },
    { slug: 'first_paralympian_1996', text: 'The first Paralympian to emerge from the program came home in the 1996 cycle.', source: 'Team USA Paralympic roster · regional press archive' },
    { slug: 'paralympian_to_olympian_ratio', text: 'The campus produces roughly three Paralympians per Olympian — the inverse of the national ratio.', source: 'Team USA roster · regional press · cross-cycle aggregation' },
  ],
  narration: { voice_name: 'Algenib', duration_s: 213, audio_url: '/fixture/narration-birmingham-alabama.mp3' },
  nil_log: { direct_matches_redacted: 4, aggregations_applied: 2 },
  publish_gate_audit: { total_claims_checked: 16, nil_layer_passed: true, publish_gate_cleared: true },
};


// FIXTURE: Park City, Utah — alpine + freestyle community pipeline.
// Olympic-focused. Synthetic prose; no athlete names; no NGB names;
// no medal counts; no times; no scoring results.

export const FIXTURE_PARK_CITY_UTAH: BroadcastStory = {
  id: 'fixture-park-city-utah',
  kicker_place: 'PUBLISHED · PARK CITY · UTAH',
  published_at: '2026-05-05T13:40:48Z',
  headline: 'A school day that ends at one in the afternoon.',
  dek: 'A mountain town where the public-school calendar bends around the chairlift schedule, and the legacy of one Winter Games keeps producing Olympians a generation later.',
  hero_image_url: '/fixture/heroes/park-city-utah.png',
  body_paragraphs: [
    "The bell at the high school in Park City rings at one in the afternoon on race-season Tuesdays and Thursdays. It has rung at one in the afternoon on race-season Tuesdays and Thursdays since 1979. The schedule is called release; the kids call it practice. Roughly four in ten public-school students in the district ski or ride two days a week or more between December and March. The school day was rebuilt around that fact a long time ago, and nobody serious has tried to put it back.",
    "The town's first Olympian went to the Winter Games in 1956. The newest came home in the Beijing cycle. Eighteen others stand between them — across alpine racing, mogul skiing, aerials, Nordic combined, ski jumping, and a small but persistent line of biathletes. The pattern is older than the state's commercial ski industry. The local ski club's racing program incorporated in 1947, six years before the first chairlift up the mountain, eleven years before the resort sold its first lift ticket. The kids were racing on the hill before there was a hill to race on.",
    "What the 2002 Winter Games left behind, twenty-four years on, is not a trophy. It is infrastructure that aged into community use. The K90 and K120 ski jumps still take traffic — high-school freestylers in the morning, Nordic combined athletes in the afternoon, a junior ski jumping program on Saturdays. The bobsled and luge track is open to youth programs eight months a year. The cross-country trails groomed for the Games are now the trails the school district uses for PE class. None of this was the plan in 2002. All of it became the pipeline.",
    "The specific texture of the place is mostly weather. The snowcat tread that goes out at four in the morning to groom the resort and the venue terrain, lights white on the fall line of every run, the operator drinking gas-station coffee in a heated cab. The K90 parking lot in February with thirty cars idling for forty minutes because nobody wants to turn the heat off and nobody wants to leave before their kid lands the third jump. The high-school race van with the broken heater, parked at the base, the parents waiting in the lodge. None of it is glamorous. All of it is repeated, every winter, by enough families that the town keeps producing.",
    "What Park City has done — what the school district and the ski club and the resort and the legacy 2002 venues have done together, mostly without coordination — is decide that the natural unit of the day is not the work week. The natural unit is the season. The school year ends in early June. Race season ends in late March. The kids who come out the other side of that calendar do not all go to the Games. Most of them do not. But enough of them do, often enough, across enough sports, that the pattern reads as a place rather than a coincidence.",
  ],
  pull_quote: 'The kids were racing on the hill before there was a hill to race on.',
  pull_quote_after_paragraph: 1,
  claims_checked: 15,
  claims_passed: 13,
  claims_removed: 2,
  claims: [
    { slug: 'release_schedule_since_1979', text: 'The high school district has run a 1 p.m. release schedule on race-season Tuesdays and Thursdays since 1979.', source: 'Park City School District calendar archive' },
    { slug: 'student_skiing_participation', text: 'Roughly forty percent of public-school students in the district ski or ride two or more days a week during the December-to-March season.', source: 'Park City School District athletics participation survey · multi-year aggregate' },
    { slug: 'first_olympian_1956', text: 'The town sent its first Olympian to the Winter Games in 1956.', source: 'olympedia.org · Summit County historical society' },
    { slug: 'olympians_since_inception', text: 'Twenty Olympians have come from Park City and the surrounding Summit County since 1956, across alpine, mogul, aerials, Nordic combined, ski jumping, and biathlon.', source: 'Team USA Winter Games rosters · regional press archive' },
    { slug: 'ski_club_incorporated_1947', text: 'The local ski club racing program was incorporated in 1947, six years before the first chairlift opened on the mountain.', source: 'Park City ski club founding records · Summit County clerk' },
    { slug: 'k90_k120_community_use', text: 'The K90 and K120 ski jumps and the bobsled-luge track left from the 2002 Winter Games remain in continuous use as community training infrastructure.', source: 'Utah Olympic Park operating reports · 2002–2026' },
    { slug: 'newest_olympian_beijing_cycle', text: "The town's most recent Olympian came home in the Beijing cycle.", source: 'Team USA Winter Games roster · regional press archive' },
  ],
  narration: { voice_name: 'Algenib', duration_s: 209, audio_url: '/fixture/narration-park-city-utah.mp3' },
  nil_log: { direct_matches_redacted: 3, aggregations_applied: 1 },
  publish_gate_audit: { total_claims_checked: 15, nil_layer_passed: true, publish_gate_cleared: true },
};

/** Lookup a fixture story by id. Null = not a known fixture. */
export function getFixtureStory(id: string): BroadcastStory | null {
  for (const story of ALL_FIXTURE_STORIES) {
    if (story.id === id) return story;
  }
  return null;
}

/** Index of fixture stories — feeds the `/story` listing page.
 *  Order: most recent published_at first (publication-order reading). */
export const ALL_FIXTURE_STORIES: BroadcastStory[] = [
  FIXTURE_MOUNT_PLEASANT,
  FIXTURE_PARK_CITY_UTAH,
  FIXTURE_BIRMINGHAM_ALABAMA,
];
