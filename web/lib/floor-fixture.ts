// Floor fixture — synthetic constellation data for the editorial-celestial
// Floor. PLACES, NOT a US map (Olympics are global). PROJECT_BRIEF §6 + §10
// strict: no individual names, no times, no scoring results, no "former
// Olympian" phrasing. Density rule: HND >= 3 only.

import type { WireEventProps } from '@/components/WireRow';

export interface FloorNode {
  id: string;
  place: string;
  region: string;
  programs: string[];
  patterns: string[];
  /** Combined Olympic + Paralympic count produced since `since_year`. */
  olympians_paralympians_count: number;
  /** Hometown narrative density score; the fixture filter is HND >= 3. */
  hnd: number;
  since_year: number;
  /** Bidirectional adjacency to other node ids (clustered by region/program). */
  edges_to: string[];
  /** Optional pinned coordinates in unit-square space [-1, 1]. */
  pin?: { x: number; y: number };
}

// Tuple shape: [id, place, region, programs[], patterns[], count, hnd,
//   since, edges_to[], pinX?, pinY?]. Keeps the catalog dense.
type Row = [
  string,
  string,
  string,
  string[],
  string[],
  number,
  number,
  number,
  string[],
  number?,
  number?,
];

const PROGRAM = {
  alpine: 'alpine training corridor', bob: 'bobsled and skeleton track', bsl: 'biathlon corridor',
  xc: 'cross-country skiing', free: 'freestyle aerials academy', swim: 'swim-club pipeline',
  row: 'rowing club', fence: 'fencing salle', gym: 'gymnastics development',
  wrest: 'high-school wrestling tradition', cwrest: 'collegiate wrestling pipeline',
  tnf: 'track-and-field development', arch: 'archery development', sail: 'sailing development',
  shoot: 'shooting sports', curl: 'curling clubs', hock: 'ice hockey development',
  otc: 'Olympic and Paralympic training center', alt: 'altitude training',
  mil: 'military-anchored athletics', tkd: 'tae kwon do academy', snow: 'snowboard pipeline',
  wrugby: 'wheelchair rugby program', wbball: 'wheelchair basketball',
  acycle: 'adaptive-cycling program', arow: 'adaptive-rowing program',
  asport: 'adaptive sports outreach',
};

const PATTERN = {
  twiceHost: 'twice-host pipeline', winter: 'winter-sport feeder', multi: 'multi-sport residency',
  border: 'binational border pipeline', hub: 'hub-and-spoke residency',
  adapt: 'adaptive-sport gravity', greatLakes: 'great-lakes winter pipeline',
  school: 'school-to-team handoff', legacy: 'legacy-venue retention', rural: 'rural feeder pattern',
  multigen: 'multi-generation participation', univ: 'university-anchored development',
  wHd: 'winter-sport hometown density', rink: 'rink-density correlation',
  mtn: 'mountain-town feeder', altRes: 'altitude residency', parity: 'paralympic equity cluster',
  ruralRoute: 'rural-route feeder', urban: 'urban club density',
  yearWater: 'year-round-water access', suburb: 'suburban club density',
  arctic: 'arctic-pipeline anomaly', mlbase: 'military-base feeder',
  navfeed: 'naval-academy feeder', coast: 'coastal-pipeline cluster',
  townSki: 'town-built ski venue',
};

// id, place, region, programs, patterns, count, hnd, since_year, edges_to, pinX, pinY
const ROWS: Row[] = [
  ['lake-placid-ny', 'Lake Placid, New York', 'New York', [PROGRAM.alpine, PROGRAM.bob], [PATTERN.twiceHost, PATTERN.winter], 24, 9.4, 1932, ['marquette-mi', 'park-city-ut', 'duluth-mn'], -0.05, -0.45],
  ['chula-vista-ca', 'Chula Vista, California', 'California', [PROGRAM.otc, PROGRAM.arch], [PATTERN.multi, PATTERN.border], 31, 9.7, 1995, ['colorado-springs-co', 'san-marcos-ca', 'imperial-valley-ca'], -0.55, 0.35],
  ['colorado-springs-co', 'Colorado Springs, Colorado', 'Colorado', [PROGRAM.alt, PROGRAM.wrugby], [PATTERN.hub, PATTERN.adapt], 28, 9.2, 1978, ['chula-vista-ca', 'park-city-ut', 'fountain-co'], 0.55, 0.05],
  ['marquette-mi', 'Marquette, Michigan', 'Michigan', [PROGRAM.xc, PROGRAM.bsl], [PATTERN.greatLakes, PATTERN.school], 11, 7.8, 1976, ['lake-placid-ny', 'duluth-mn', 'grand-rapids-mn']],
  ['park-city-ut', 'Park City, Utah', 'Utah', [PROGRAM.free, PROGRAM.alpine], [PATTERN.legacy, PATTERN.school], 19, 8.6, 1988, ['lake-placid-ny', 'colorado-springs-co', 'truckee-ca']],
  ['mount-pleasant-ia', 'Mount Pleasant, Iowa', 'Iowa', [PROGRAM.wrest], [PATTERN.rural, PATTERN.multigen], 4, 5.1, 1984, ['iowa-city-ia', 'cedar-falls-ia']],
  ['iowa-city-ia', 'Iowa City, Iowa', 'Iowa', [PROGRAM.cwrest, PROGRAM.row], [PATTERN.univ], 9, 6.7, 1980, ['mount-pleasant-ia', 'cedar-falls-ia', 'state-college-pa']],
  ['cedar-falls-ia', 'Cedar Falls, Iowa', 'Iowa', [PROGRAM.wrest], [PATTERN.rural], 3, 4.4, 1992, ['mount-pleasant-ia', 'iowa-city-ia']],
  ['duluth-mn', 'Duluth, Minnesota', 'Minnesota', [PROGRAM.curl, PROGRAM.xc], [PATTERN.wHd], 8, 6.3, 1976, ['marquette-mi', 'grand-rapids-mn', 'bemidji-mn']],
  ['grand-rapids-mn', 'Grand Rapids, Minnesota', 'Minnesota', [PROGRAM.hock], [PATTERN.rink], 5, 5.6, 1980, ['duluth-mn', 'bemidji-mn']],
  ['bemidji-mn', 'Bemidji, Minnesota', 'Minnesota', [PROGRAM.curl, PROGRAM.xc], [PATTERN.wHd], 6, 5.9, 1988, ['duluth-mn', 'grand-rapids-mn']],
  ['truckee-ca', 'Truckee, California', 'California', [PROGRAM.alpine], [PATTERN.mtn], 7, 6.2, 1984, ['park-city-ut', 'mammoth-lakes-ca']],
  ['mammoth-lakes-ca', 'Mammoth Lakes, California', 'California', [PROGRAM.free], [PATTERN.mtn, PATTERN.altRes], 5, 5.8, 1992, ['truckee-ca', 'big-bear-ca']],
  ['big-bear-ca', 'Big Bear, California', 'California', [PROGRAM.snow], [PATTERN.altRes], 4, 5.0, 2002, ['mammoth-lakes-ca', 'san-marcos-ca']],
  ['san-marcos-ca', 'San Marcos, California', 'California', [PROGRAM.acycle], [PATTERN.parity], 4, 5.4, 2008, ['chula-vista-ca', 'big-bear-ca', 'imperial-valley-ca']],
  ['imperial-valley-ca', 'Imperial Valley, California', 'California', [PROGRAM.tnf], [PATTERN.ruralRoute], 3, 4.2, 1988, ['chula-vista-ca', 'san-marcos-ca']],
  ['fountain-co', 'Fountain, Colorado', 'Colorado', [PROGRAM.mil, PROGRAM.asport], [PATTERN.parity], 3, 4.6, 2000, ['colorado-springs-co']],
  ['state-college-pa', 'State College, Pennsylvania', 'Pennsylvania', [PROGRAM.cwrest], [PATTERN.univ], 6, 6.0, 1980, ['stillwater-ok', 'iowa-city-ia']],
  ['stillwater-ok', 'Stillwater, Oklahoma', 'Oklahoma', [PROGRAM.cwrest], [PATTERN.univ], 7, 6.4, 1976, ['state-college-pa', 'norman-ok']],
  ['norman-ok', 'Norman, Oklahoma', 'Oklahoma', [PROGRAM.gym], [PATTERN.univ], 5, 5.7, 1988, ['stillwater-ok']],
  ['eugene-or', 'Eugene, Oregon', 'Oregon', [PROGRAM.tnf], [PATTERN.legacy], 13, 7.5, 1976, ['portland-or', 'tacoma-wa']],
  ['portland-or', 'Portland, Oregon', 'Oregon', [PROGRAM.tnf, PROGRAM.row], [PATTERN.urban], 8, 6.5, 1980, ['eugene-or', 'tacoma-wa']],
  ['tacoma-wa', 'Tacoma, Washington', 'Washington', [PROGRAM.row, PROGRAM.arow], [PATTERN.parity], 6, 5.9, 1992, ['eugene-or', 'portland-or', 'spokane-wa']],
  ['fort-lauderdale-fl', 'Fort Lauderdale, Florida', 'Florida', [PROGRAM.swim], [PATTERN.yearWater], 11, 7.1, 1976, ['orlando-fl', 'miami-fl']],
  ['orlando-fl', 'Orlando, Florida', 'Florida', [PROGRAM.swim, PROGRAM.tkd], [PATTERN.urban], 7, 6.3, 1984, ['fort-lauderdale-fl', 'miami-fl']],
  ['miami-fl', 'Miami, Florida', 'Florida', [PROGRAM.swim, PROGRAM.sail], [PATTERN.urban], 9, 6.9, 1980, ['fort-lauderdale-fl', 'orlando-fl', 'charleston-sc']],
  ['mission-viejo-ca', 'Mission Viejo, California', 'California', [PROGRAM.swim], [PATTERN.suburb], 14, 7.6, 1976, ['chula-vista-ca']],
  ['fairbanks-ak', 'Fairbanks, Alaska', 'Alaska', [PROGRAM.bsl, PROGRAM.xc], [PATTERN.arctic], 4, 5.3, 1980, ['anchorage-ak']],
  ['anchorage-ak', 'Anchorage, Alaska', 'Alaska', [PROGRAM.xc], [PATTERN.arctic], 5, 5.6, 1976, ['fairbanks-ak']],
  ['columbus-ga', 'Columbus, Georgia', 'Georgia', [PROGRAM.mil, PROGRAM.shoot], [PATTERN.mlbase], 5, 5.5, 1984, ['savannah-ga']],
  ['boston-ma', 'Boston, Massachusetts', 'Massachusetts', [PROGRAM.row, PROGRAM.fence], [PATTERN.urban], 12, 7.2, 1976, ['providence-ri', 'new-haven-ct', 'lebanon-nh']],
  ['providence-ri', 'Providence, Rhode Island', 'Rhode Island', [PROGRAM.row], [PATTERN.urban], 4, 5.1, 1988, ['boston-ma']],
  ['new-haven-ct', 'New Haven, Connecticut', 'Connecticut', [PROGRAM.fence, PROGRAM.row], [PATTERN.univ], 6, 5.9, 1980, ['boston-ma']],
  ['houston-tx', 'Houston, Texas', 'Texas', [PROGRAM.gym, PROGRAM.swim], [PATTERN.urban], 16, 7.9, 1976, ['dallas-tx', 'austin-tx']],
  ['dallas-tx', 'Dallas, Texas', 'Texas', [PROGRAM.gym, PROGRAM.tkd], [PATTERN.urban], 10, 7.0, 1980, ['houston-tx', 'austin-tx']],
  ['austin-tx', 'Austin, Texas', 'Texas', [PROGRAM.swim], [PATTERN.urban], 7, 6.4, 1988, ['houston-tx', 'dallas-tx']],
  ['indianapolis-in', 'Indianapolis, Indiana', 'Indiana', [PROGRAM.swim, PROGRAM.wrugby], [PATTERN.parity], 9, 6.8, 1984, ['louisville-ky', 'cincinnati-oh']],
  ['louisville-ky', 'Louisville, Kentucky', 'Kentucky', [PROGRAM.row, PROGRAM.gym], [PATTERN.urban], 5, 5.7, 1992, ['indianapolis-in', 'cincinnati-oh']],
  ['cincinnati-oh', 'Cincinnati, Ohio', 'Ohio', [PROGRAM.gym], [PATTERN.urban], 6, 6.0, 1980, ['indianapolis-in', 'louisville-ky', 'cleveland-oh']],
  ['cleveland-oh', 'Cleveland, Ohio', 'Ohio', [PROGRAM.hock, PROGRAM.fence], [PATTERN.urban], 7, 6.3, 1976, ['cincinnati-oh', 'pittsburgh-pa']],
  ['pittsburgh-pa', 'Pittsburgh, Pennsylvania', 'Pennsylvania', [PROGRAM.gym], [PATTERN.urban], 6, 6.0, 1984, ['state-college-pa', 'cleveland-oh']],
  ['baltimore-md', 'Baltimore, Maryland', 'Maryland', [PROGRAM.swim], [PATTERN.urban], 8, 6.7, 1976, ['annapolis-md', 'philadelphia-pa']],
  ['annapolis-md', 'Annapolis, Maryland', 'Maryland', [PROGRAM.sail], [PATTERN.navfeed], 5, 5.8, 1980, ['baltimore-md']],
  ['philadelphia-pa', 'Philadelphia, Pennsylvania', 'Pennsylvania', [PROGRAM.row, PROGRAM.fence], [PATTERN.urban], 9, 6.9, 1976, ['baltimore-md']],
  ['charleston-sc', 'Charleston, South Carolina', 'South Carolina', [PROGRAM.sail], [PATTERN.coast], 3, 4.5, 1996, ['savannah-ga']],
  ['savannah-ga', 'Savannah, Georgia', 'Georgia', [PROGRAM.row], [PATTERN.coast], 3, 4.3, 2000, ['charleston-sc', 'columbus-ga']],
  ['jackson-wy', 'Jackson, Wyoming', 'Wyoming', [PROGRAM.alpine], [PATTERN.mtn], 4, 5.1, 1992, ['park-city-ut', 'sun-valley-id']],
  ['sun-valley-id', 'Sun Valley, Idaho', 'Idaho', [PROGRAM.alpine], [PATTERN.mtn], 5, 5.4, 1980, ['park-city-ut', 'jackson-wy']],
  ['bozeman-mt', 'Bozeman, Montana', 'Montana', [PROGRAM.xc], [PATTERN.mtn], 3, 4.4, 2002, ['sun-valley-id', 'jackson-wy']],
  ['fargo-nd', 'Fargo, North Dakota', 'North Dakota', [PROGRAM.wrest], [PATTERN.rural], 3, 4.2, 1996, ['bemidji-mn', 'sioux-falls-sd']],
  ['sioux-falls-sd', 'Sioux Falls, South Dakota', 'South Dakota', [PROGRAM.wrest], [PATTERN.rural], 3, 4.1, 2000, ['fargo-nd']],
  ['burlington-vt', 'Burlington, Vermont', 'Vermont', [PROGRAM.alpine, PROGRAM.xc], [PATTERN.mtn], 7, 6.4, 1976, ['lake-placid-ny', 'lebanon-nh']],
  ['lebanon-nh', 'Lebanon, New Hampshire', 'New Hampshire', [PROGRAM.xc], [PATTERN.school], 4, 5.0, 1984, ['burlington-vt', 'boston-ma', 'rumford-me']],
  ['rumford-me', 'Rumford, Maine', 'Maine', [PROGRAM.bsl], [PATTERN.townSki], 3, 4.7, 1988, ['lebanon-nh']],
  ['leavenworth-wa', 'Leavenworth, Washington', 'Washington', [PROGRAM.xc, PROGRAM.bsl], [PATTERN.townSki], 4, 5.2, 1992, ['tacoma-wa', 'spokane-wa']],
  ['spokane-wa', 'Spokane, Washington', 'Washington', [PROGRAM.arow, PROGRAM.wbball], [PATTERN.parity], 5, 5.6, 1996, ['leavenworth-wa', 'tacoma-wa']],
  ['birmingham-al', 'Birmingham, Alabama', 'Alabama', [PROGRAM.wrugby, PROGRAM.acycle], [PATTERN.parity], 6, 6.1, 1996, ['nashville-tn']],
  ['nashville-tn', 'Nashville, Tennessee', 'Tennessee', [PROGRAM.wbball, PROGRAM.arow], [PATTERN.parity], 4, 5.0, 2000, ['birmingham-al']],
];

export const FLOOR_NODES: FloorNode[] = ROWS.map((r) => {
  const node: FloorNode = {
    id: r[0],
    place: r[1],
    region: r[2],
    programs: r[3],
    patterns: r[4],
    olympians_paralympians_count: r[5],
    hnd: r[6],
    since_year: r[7],
    edges_to: r[8],
  };
  if (r[9] !== undefined && r[10] !== undefined) {
    node.pin = { x: r[9], y: r[10] };
  }
  return node;
});

// ---------------------------------------------------------------------------
// Edge derivation. Stable id per alphabetically-sorted endpoint pair.
// ---------------------------------------------------------------------------

export interface FloorEdge {
  id: string;
  source: string;
  target: string;
}

export function deriveEdges(nodes: FloorNode[]): FloorEdge[] {
  const ids = new Set(nodes.map((n) => n.id));
  const seen = new Set<string>();
  const edges: FloorEdge[] = [];
  for (const node of nodes) {
    for (const otherId of node.edges_to) {
      if (!ids.has(otherId)) continue;
      const [a, b] = [node.id, otherId].sort();
      const id = `${a}--${b}`;
      if (seen.has(id)) continue;
      seen.add(id);
      edges.push({ id, source: a, target: b });
    }
  }
  return edges;
}

// ---------------------------------------------------------------------------
// Synthetic Wire trail per node — rendered via <WireRow /> inside the side
// panel. Strict adherence to PROJECT_BRIEF §6 + §10. No individual names,
// no times, no scoring results. Voice signatures match agent prompts.
// ---------------------------------------------------------------------------

export function deriveWireTrail(node: FloorNode): WireEventProps[] {
  const program0 = node.programs[0] ?? 'a recurring program';
  const pattern0 = node.patterns[0] ?? 'a recurring pattern';
  return [
    {
      id: `${node.id}-trail-0`,
      timestamp: '2026-05-05T08:14:02Z',
      agent: 'scout_desk',
      sub_agent: 'hometown',
      message: `Pattern surfaces around ${node.place} — ${program0} recurring across ${node.olympians_paralympians_count} Team USA appearances since ${node.since_year}.`,
      message_type: 'thinking',
      mode: 'replay',
    },
    {
      id: `${node.id}-trail-1`,
      timestamp: '2026-05-05T08:14:21Z',
      agent: 'investigator',
      message: `Cross-checked the ${node.region} state athletic association archives and the ${program0} club registry. The continuity reads as a real lineage, not a single-cohort spike.`,
      message_type: 'thinking',
      mode: 'replay',
    },
    {
      id: `${node.id}-trail-2`,
      timestamp: '2026-05-05T08:14:48Z',
      agent: 'editor',
      message: `${node.place}: hometown narrative density ${node.hnd.toFixed(1)}. Holding for parity review before promoting.`,
      message_type: 'decision',
      mode: 'replay',
    },
    {
      id: `${node.id}-trail-3`,
      timestamp: '2026-05-05T08:15:04Z',
      agent: 'equity_editor',
      message: `Parity check on ${node.place}: the ${pattern0} pattern is documented on both Olympic and Paralympic sides. Cleared for the Floor.`,
      message_type: 'intervention',
      mode: 'replay',
    },
  ];
}

// Scripted "Equity Editor caused the anchor story" demo pulse.
export const INTERVENTION_NODE_ID = 'birmingham-al';
export const INTERVENTION_DELAY_MS = 4200;
