'use client';

/**
 * <MapView /> — stylized US map of places that have produced Team USA
 * Olympians and Paralympians. NBC-broadcast-graphic aesthetic, NOT a tile-map
 * clone (PROJECT_BRIEF §7 auto-DQ: third-party tile providers = third-party
 * logos). VPS-DEC-042.
 *
 * Implementation:
 * - D3-geo Albers USA projection rendered on Canvas (mirrors Field.tsx).
 * - State boundaries from `us-atlas` TopoJSON (public-domain Census data).
 * - Place dots in --gold-warm, sized by olympians_paralympians_count.
 * - Hover: anchored tooltip card with place + count (NEVER an athlete name).
 * - Click: routes to /story/[id] if the place has a published Broadcast.
 *
 * Spec: design-system.md §2/§5; PROJECT_BRIEF §6/§7/§10; Field.tsx pattern.
 * Kill list: no Mapbox/Leaflet/Google Maps, no tile services, no shadows
 * beyond the dot halo, no athlete names anywhere in tooltip / DOM.
 */

import { useRouter } from 'next/navigation';
import { geoAlbersUsa, geoPath, type GeoPath } from 'd3-geo';
import { useEffect, useMemo, useRef, useState } from 'react';
import { feature } from 'topojson-client';
// us-atlas ships a JSON file; the resolveJsonModule tsconfig flag lets us
// import it directly. The shape is TopoJSON; topojson-client.feature()
// converts it to GeoJSON for d3-geo.
import statesTopo from 'us-atlas/states-10m.json';
import { MAP_PLACES, type MapPlace } from '@/lib/map-fixture';

// Tokens (raw rgb triples to permit alpha via rgba()).
// design-system.md §2 — locked palette.
const COLOR_GOLD_WARM = '212, 168, 74';
const COLOR_NAVY_MID = '26, 39, 64';
const COLOR_NAVY_LIGHT = '44, 62, 90';

// Dot sizing mirrors Field.tsx: r = base + sqrt(count), clamped 4-18.
const NODE_R_BASE = 4;
const NODE_R_MIN = 4;
const NODE_R_MAX = 18;
const HIT_PAD = 6;

function radiusForCount(count: number): number {
  const r = NODE_R_BASE + Math.sqrt(count);
  return Math.max(NODE_R_MIN, Math.min(NODE_R_MAX, r));
}

// Geometry collection from us-atlas. The TopoJSON type is intentionally loose
// here — `feature()` returns a GeoJSON FeatureCollection that d3-geo's path
// generator accepts as a `GeoPermissibleObjects` argument.
interface UsStatesGeo {
  type: 'FeatureCollection';
  features: unknown[];
}
const STATES_FEATURE: UsStatesGeo = feature(
  statesTopo as unknown as Parameters<typeof feature>[0],
  // The 'states' object key matches the us-atlas TopoJSON schema.
  (statesTopo as { objects: { states: unknown } }).objects.states as Parameters<typeof feature>[1],
) as unknown as UsStatesGeo;

function useElementSize<T extends HTMLElement>(): [
  React.RefObject<T | null>,
  { width: number; height: number },
] {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (cr) setSize({ width: cr.width, height: cr.height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return [ref, size];
}

interface ProjectedPlace extends MapPlace {
  /** Projected pixel x. May be null when projection drops a point (e.g. unsupported region). */
  px: number | null;
  py: number | null;
}

export function MapView() {
  const router = useRouter();
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [hoverId, setHoverId] = useState<string | null>(null);

  // Build the projection + path generator once per container resize.
  // geoAlbersUsa fits Alaska + Hawaii into composited insets at native scale.
  const { projection, path, projected } = useMemo(() => {
    if (size.width === 0 || size.height === 0) {
      return { projection: null, path: null, projected: [] as ProjectedPlace[] };
    }
    const proj = geoAlbersUsa().fitSize(
      [size.width, size.height],
      STATES_FEATURE as unknown as Parameters<GeoPath['bounds']>[0],
    );
    // The path generator is built without a context for now; the draw loop
    // attaches a Canvas 2D context before calling path(feature).
    const p = geoPath(proj);
    const places: ProjectedPlace[] = MAP_PLACES.map((place) => {
      const xy = proj([place.lng, place.lat]);
      return {
        ...place,
        px: xy ? xy[0] : null,
        py: xy ? xy[1] : null,
      };
    });
    return { projection: proj, path: p, projected: places };
  }, [size.width, size.height]);

  const projectedRef = useRef<ProjectedPlace[]>(projected);
  useEffect(() => {
    projectedRef.current = projected;
  }, [projected]);

  // Canvas paint — re-run whenever size or hover state changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !projection || !path || size.width === 0 || size.height === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(size.width * dpr));
    canvas.height = Math.max(1, Math.floor(size.height * dpr));
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, size.width, size.height);

    // STATE BOUNDARIES — navy-mid fill, navy-light stroke. Subtle; the dots
    // are the story. design-system.md §2.
    ctx.beginPath();
    // Reattach the path generator's context to draw into Canvas.
    const ctxPath = geoPath(projection, ctx);
    ctxPath(STATES_FEATURE as unknown as Parameters<typeof ctxPath>[0]);
    ctx.fillStyle = `rgba(${COLOR_NAVY_MID}, 0.55)`;
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = `rgba(${COLOR_NAVY_LIGHT}, 0.85)`;
    ctx.stroke();

    // DOTS — two-pass halo, mirror Field.tsx visual language.
    for (const place of projectedRef.current) {
      if (place.px === null || place.py === null) continue;
      const r = radiusForCount(place.count);
      const isHover = place.id === hoverId;

      // Outer halo: radial gradient gold-warm 0.15α → 0α.
      const haloR = r * 3 * (isHover ? 1.4 : 1);
      const grad = ctx.createRadialGradient(place.px, place.py, 0, place.px, place.py, haloR);
      const centerAlpha = isHover ? 0.32 : 0.18;
      grad.addColorStop(0, `rgba(${COLOR_GOLD_WARM}, ${centerAlpha})`);
      grad.addColorStop(1, `rgba(${COLOR_GOLD_WARM}, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(place.px, place.py, haloR, 0, Math.PI * 2);
      ctx.fill();

      // Inner disc: gold-warm 0.45α with subtle glow.
      ctx.save();
      ctx.shadowColor = `rgba(${COLOR_GOLD_WARM}, ${isHover ? 0.2 : 0.08})`;
      ctx.shadowBlur = 12;
      ctx.fillStyle = `rgba(${COLOR_GOLD_WARM}, 0.45)`;
      ctx.beginPath();
      ctx.arc(place.px, place.py, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Stroke: 1px gold-warm 0.85α.
      ctx.lineWidth = 1;
      ctx.strokeStyle = `rgba(${COLOR_GOLD_WARM}, 0.85)`;
      ctx.beginPath();
      ctx.arc(place.px, place.py, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  }, [size.width, size.height, hoverId, projection, path]);

  // HIT TESTING — simple Euclidean distance to dot center, with HIT_PAD slop.
  function hitTest(x: number, y: number): ProjectedPlace | null {
    const places = projectedRef.current;
    for (let i = places.length - 1; i >= 0; i -= 1) {
      const p = places[i]!;
      if (p.px === null || p.py === null) continue;
      const r = radiusForCount(p.count);
      const dx = x - p.px;
      const dy = y - p.py;
      if (dx * dx + dy * dy <= (r + HIT_PAD) * (r + HIT_PAD)) return p;
    }
    return null;
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    setHoverId(hit?.id ?? null);
  }
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (!hit) return;
    if (hit.story_id) {
      router.push(`/story/${hit.story_id}`);
    }
    // If no story_id, no-op — the tooltip already shows "investigating…".
  }

  const hovered = useMemo(
    () => projected.find((p) => p.id === hoverId) ?? null,
    [hoverId, projected],
  );

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="relative h-full w-full"
        style={{ cursor: hoverId ? 'pointer' : 'default' }}
        onPointerMove={onPointerMove}
        onPointerLeave={() => setHoverId(null)}
        onPointerDown={onPointerDown}
      >
        <canvas
          ref={canvasRef}
          aria-label="Stylized map of the United States with dots marking places that have produced Olympians and Paralympians"
        />
        {hovered && hovered.px !== null && hovered.py !== null && (
          <MapTooltip place={hovered} containerHeight={size.height} />
        )}
      </div>
    </div>
  );
}

interface MapTooltipProps {
  place: ProjectedPlace;
  containerHeight: number;
}

function MapTooltip({ place, containerHeight }: MapTooltipProps) {
  if (place.px === null || place.py === null) return null;
  const r = radiusForCount(place.count);

  // Anchor above the dot when there's not enough room below — keeps the
  // tooltip clear of the bottom area where broadcast nav may live (VPS-DEC-046
  // mobile-responsive: 375px viewports show nav at bottom).
  const TOOLTIP_HEIGHT_PX = 110;
  const SAFE_BOTTOM_PX = 96;
  const wouldOverflowBottom = place.py + r + 12 + TOOLTIP_HEIGHT_PX > containerHeight - SAFE_BOTTOM_PX;
  const top = wouldOverflowBottom ? place.py - r - 12 - TOOLTIP_HEIGHT_PX : place.py + r + 12;
  const left = place.px + 12;

  return (
    <div
      role="tooltip"
      style={{ position: 'absolute', left: `${left}px`, top: `${top}px`, maxWidth: '280px' }}
      className="pointer-events-none z-10 border-l border-gold-warm/80 bg-navy-mid/95 px-4 py-3"
    >
      <p className="font-mono text-caption uppercase tracking-[0.16em] text-gold-warm/85">
        {place.state.toUpperCase()}
      </p>
      <p className="mt-1 font-italic italic text-italic-sm text-cream">{place.name}</p>
      {place.headline ? (
        <p className="mt-2 font-display text-body-md leading-tight text-cream">
          {place.headline}
        </p>
      ) : (
        <p className="mt-2 font-mono text-caption uppercase tracking-[0.14em] text-wire-text/70">
          investigating…
        </p>
      )}
      <p className="mt-2 font-mono text-caption uppercase tracking-[0.14em] text-wire-text/80">
        {place.count} Olympians and Paralympians
      </p>
    </div>
  );
}

export default MapView;
