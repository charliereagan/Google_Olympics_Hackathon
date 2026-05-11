// Map fixture — geographic coordinates for the 58 places in field-fixture.ts,
// keyed by FieldNode.id. PROJECT_BRIEF §6/§10 strict: no individual names, no
// times, no scoring results. Lat/lng are approximate city-center values for a
// stylized broadcast map — accuracy is not load-bearing.
//
// VPS-DEC-042: /map renders one dot per place, sized by olympians_paralympians_count,
// hover = place name + aggregate count, click = /story/[id] when published.
// Story linkage maps three field nodes to the existing fixture broadcasts.

import { FIELD_NODES, type FieldNode } from './field-fixture';

export interface MapPlace {
  /** FieldNode.id passthrough. */
  id: string;
  /** "City, State" — same shape as FieldNode.place. */
  name: string;
  /** State name, derived from FieldNode.region. */
  state: string;
  /** Olympic + Paralympic count since since_year. */
  count: number;
  /** Approximate city-center latitude (WGS84). */
  lat: number;
  /** Approximate city-center longitude (WGS84). */
  lng: number;
  /** /story/[id] target when a Broadcast is published for this place. */
  story_id: string | null;
  /** Optional published Broadcast headline for the hover card. */
  headline: string | null;
}

// id → [lat, lng]. Order matches field-fixture.ts ROWS for review.
const COORDS: Record<string, [number, number]> = {
  'lake-placid-ny': [44.2795, -73.9799],
  'chula-vista-ca': [32.6401, -117.0842],
  'colorado-springs-co': [38.8339, -104.8214],
  'marquette-mi': [46.5436, -87.3954],
  'park-city-ut': [40.6461, -111.4980],
  'mount-pleasant-ia': [40.9636, -91.5557],
  'iowa-city-ia': [41.6611, -91.5302],
  'cedar-falls-ia': [42.5278, -92.4453],
  'duluth-mn': [46.7867, -92.1005],
  'grand-rapids-mn': [47.2372, -93.5302],
  'bemidji-mn': [47.4716, -94.8829],
  'truckee-ca': [39.3280, -120.1833],
  'mammoth-lakes-ca': [37.6485, -118.9721],
  'big-bear-ca': [34.2439, -116.9114],
  'san-marcos-ca': [33.1434, -117.1661],
  'imperial-valley-ca': [32.8475, -115.5694],
  'fountain-co': [38.6822, -104.7008],
  'state-college-pa': [40.7934, -77.8600],
  'stillwater-ok': [36.1156, -97.0584],
  'norman-ok': [35.2226, -97.4395],
  'eugene-or': [44.0521, -123.0868],
  'portland-or': [45.5152, -122.6784],
  'tacoma-wa': [47.2529, -122.4443],
  'fort-lauderdale-fl': [26.1224, -80.1373],
  'orlando-fl': [28.5383, -81.3792],
  'miami-fl': [25.7617, -80.1918],
  'mission-viejo-ca': [33.6000, -117.6720],
  'fairbanks-ak': [64.8378, -147.7164],
  'anchorage-ak': [61.2181, -149.9003],
  'columbus-ga': [32.4609, -84.9877],
  'boston-ma': [42.3601, -71.0589],
  'providence-ri': [41.8240, -71.4128],
  'new-haven-ct': [41.3083, -72.9279],
  'houston-tx': [29.7604, -95.3698],
  'dallas-tx': [32.7767, -96.7970],
  'austin-tx': [30.2672, -97.7431],
  'indianapolis-in': [39.7684, -86.1581],
  'louisville-ky': [38.2527, -85.7585],
  'cincinnati-oh': [39.1031, -84.5120],
  'cleveland-oh': [41.4993, -81.6944],
  'pittsburgh-pa': [40.4406, -79.9959],
  'baltimore-md': [39.2904, -76.6122],
  'annapolis-md': [38.9784, -76.4922],
  'philadelphia-pa': [39.9526, -75.1652],
  'charleston-sc': [32.7765, -79.9311],
  'savannah-ga': [32.0809, -81.0912],
  'jackson-wy': [43.4799, -110.7624],
  'sun-valley-id': [43.6963, -114.3520],
  'bozeman-mt': [45.6770, -111.0429],
  'fargo-nd': [46.8772, -96.7898],
  'sioux-falls-sd': [43.5446, -96.7311],
  'burlington-vt': [44.4759, -73.2121],
  'lebanon-nh': [43.6423, -72.2518],
  'rumford-me': [44.5531, -70.5536],
  'leavenworth-wa': [47.5963, -120.6614],
  'spokane-wa': [47.6588, -117.4260],
  'birmingham-al': [33.5186, -86.8104],
  'nashville-tn': [36.1627, -86.7816],
};

// FieldNode.id → published story id (BroadcastStory.id). Three nodes map to
// the three fixture stories. Anything else: null → no click navigation.
const STORY_LINKS: Record<string, { story_id: string; headline: string }> = {
  'mount-pleasant-ia': {
    story_id: 'fixture-mount-pleasant',
    headline: 'A small town builds a generation.',
  },
  'park-city-ut': {
    story_id: 'fixture-park-city-utah',
    headline: 'A school day that ends at one in the afternoon.',
  },
  'birmingham-al': {
    story_id: 'fixture-birmingham-alabama',
    headline: 'A city remade for the rest of itself.',
  },
};

function buildPlace(node: FieldNode): MapPlace {
  const coords = COORDS[node.id];
  const link = STORY_LINKS[node.id] ?? null;
  // Fallback to (0, 0) only if the table is missing an id — never expected
  // in practice; flagged in dev so anyone adding a new FIELD_NODE remembers
  // to add coordinates here as well.
  if (!coords && typeof console !== 'undefined') {
    console.warn(`[map-fixture] missing coordinates for ${node.id}`);
  }
  const [lat, lng] = coords ?? [0, 0];
  return {
    id: node.id,
    name: node.place,
    state: node.region,
    count: node.olympians_paralympians_count,
    lat,
    lng,
    story_id: link?.story_id ?? null,
    headline: link?.headline ?? null,
  };
}

export const MAP_PLACES: MapPlace[] = FIELD_NODES
  .filter((n) => COORDS[n.id])
  .map(buildPlace);
