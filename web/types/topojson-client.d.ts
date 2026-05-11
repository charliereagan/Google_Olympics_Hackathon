// Minimal type declaration for `topojson-client`. The published package
// does not ship its own types and there is no @types/topojson-client on
// npm. We only use the `feature()` conversion fn, so a narrow declaration
// is enough to satisfy strict TypeScript without pulling in a heavy GeoJSON
// type dependency. (VPS-DEC-042 / `/map` route.)

declare module 'topojson-client' {
  // The real signatures take a TopoJSON Topology and either a GeometryObject
  // or a name-string. We accept `unknown` on both sides and return `unknown`
  // — the MapView component narrows the result to the GeoJSON shape it needs.
  export function feature(topology: unknown, object: unknown): unknown;
  export function mesh(topology: unknown, object: unknown, filter?: unknown): unknown;
  export function meshArcs(topology: unknown, object: unknown, filter?: unknown): unknown;
  export function merge(topology: unknown, objects: unknown): unknown;
  export function mergeArcs(topology: unknown, objects: unknown): unknown;
  export function neighbors(objects: unknown): unknown;
  export function quantile(topology: unknown, p: number): unknown;
}
