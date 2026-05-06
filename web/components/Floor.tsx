'use client';

/**
 * <Floor /> — editorial-celestial constellation of places. Day-9 lock:
 * a star field of PLACES, NOT a US map (Olympics are global). Canvas +
 * d3-force; gold-warm nodes, navy-light hairline edges, anchored hover
 * card, click-to-pin side panel with the verified-claims wire trail.
 * Demo moment #3 (Equity Editor caused the anchor story) mocked via a
 * scripted agitos-red pulse on `INTERVENTION_NODE_ID`.
 *
 * Spec: design-system.md §2/§3/§5/§7; BUILD_SPEC.md §9; PROJECT_BRIEF §6/§10.
 * Kill list: no SVG nodes, no shadows, no spinners, no new tokens, no map.
 */

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY,
  type SimulationLinkDatum, type SimulationNodeDatum,
} from 'd3-force';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  deriveEdges, deriveWireTrail, FLOOR_NODES,
  INTERVENTION_DELAY_MS, INTERVENTION_NODE_ID,
  type FloorEdge, type FloorNode,
} from '@/lib/floor-fixture';
import { WireRow } from './WireRow';

// Canvas needs raw rgba(); tokens mirror tailwind.config.ts §2.
const COLOR_GOLD_WARM = '212, 168, 74';
const COLOR_NAVY_LIGHT = '44, 62, 90';
const COLOR_AGITOS_RED = '200, 16, 46';

const ROOM_EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];
const NODE_R_BASE = 4, NODE_R_MAX = 18, NODE_R_MIN = 4;
const HALO_BLUR = 12;
// Pass-2: total reveal duration ~1500ms (was 800), giving the room a beat.
const MOUNT_ANIM_MS = 1500;
const PULSE_MS = 600;
// Pass-2: low-HND nodes (HND < 5) read as distant outliers — 0.4 alpha mult.
const HND_DIM_THRESHOLD = 5;
const HND_DIM_ALPHA = 0.4;
// Pass-2: top-K non-anchor nodes by HND that get ambient labels (3 anchors
// + this many non-anchors = 5 labeled stars total per F5).
const LABEL_TOP_NON_ANCHOR_COUNT = 2;

interface SimNode extends FloorNode, SimulationNodeDatum {
  /** Per-node mount stagger so the room "wakes up" rather than booting. */
  mountDelayMs: number;
  /** True for the 5 brightest stars (3 anchors + top-2 HND non-anchors). */
  showLabel: boolean;
}
type SimLink = SimulationLinkDatum<SimNode> & { id: string };
interface InterventionState { nodeId: string; startedAt: number }

function radiusForCount(count: number): number {
  return Math.max(NODE_R_MIN, Math.min(NODE_R_MAX, NODE_R_BASE + Math.sqrt(count)));
}

/**
 * Draw an UPPERCASE label with manual letter-spacing (em-units) — Canvas 2D's
 * `letterSpacing` property is experimental and absent from older browsers, so
 * we measure each glyph and advance by `width + emSpacing * fontSizePx`.
 * Mirrors the tracked-small-caps treatment used in CSS for caption tags.
 * Place strings are trimmed at the comma so labels read as city names, not
 * "City, State" — keeps the constellation editorially restrained per F5.
 */
function drawTrackedSmallCapsLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  emSpacing: number,
): void {
  const cityOnly = text.split(',')[0] ?? text;
  const upper = cityOnly.toUpperCase();
  // Match the font-size set by the caller (10px); keep this in sync.
  const fontSizePx = 10;
  const space = emSpacing * fontSizePx;
  let cursor = x;
  for (const ch of upper) {
    ctx.fillText(ch, cursor, y);
    cursor += ctx.measureText(ch).width + space;
  }
}

function hitTestNode(nodes: SimNode[], x: number, y: number): SimNode | null {
  for (let i = nodes.length - 1; i >= 0; i -= 1) {
    const n = nodes[i]!;
    if (n.x === undefined || n.y === undefined) continue;
    const r = radiusForCount(n.olympians_paralympians_count);
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy <= (r + 6) * (r + 6)) return n;
  }
  return null;
}

function useElementSize<T extends HTMLElement>(): [
  React.RefObject<T | null>, { width: number; height: number },
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

export function Floor() {
  const reduceMotion = useReducedMotion();
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const { simNodes, simLinks } = useMemo(() => {
    // Pass-2 (F4): reversed stagger — anchors land first, then non-anchors
    // sorted by HND DESC so major hubs come into focus before rural feeders.
    // The reveal tells a story: "Lake Placid, Chula Vista, Colorado Springs
    // anchor the room. The major hubs come into focus. And then the small
    // towns appear — the room finds rural places too."
    const anchorIds = new Set(FLOOR_NODES.filter((n) => n.pin).map((n) => n.id));
    const nonAnchorsByHndDesc = [...FLOOR_NODES]
      .filter((n) => !anchorIds.has(n.id))
      .sort((a, b) => b.hnd - a.hnd);

    // Pass-2 (F5): the 5 ambient labels = 3 anchors + 2 highest-HND non-anchors.
    const labelIds = new Set<string>([
      ...FLOOR_NODES.filter((n) => n.pin).map((n) => n.id),
      ...nonAnchorsByHndDesc.slice(0, LABEL_TOP_NON_ANCHOR_COUNT).map((n) => n.id),
    ]);

    // Total reveal arc: anchors enter in the first ~150ms (idx * 12 over 3
    // anchors = ~36ms span), then non-anchors fan out from ~150ms to ~1500ms.
    const ANCHOR_PHASE_MS = 150;
    const nonAnchorOrder = new Map<string, number>();
    nonAnchorsByHndDesc.forEach((n, idx) => nonAnchorOrder.set(n.id, idx));
    const nonAnchorCount = Math.max(1, nonAnchorsByHndDesc.length);
    const nonAnchorWindow = MOUNT_ANIM_MS - ANCHOR_PHASE_MS;

    const nodes: SimNode[] = FLOOR_NODES.map((n, idx) => {
      const isAnchor = !!n.pin;
      const mountDelayMs = isAnchor
        ? idx * 12 // existing behavior for the 3 anchors
        : ANCHOR_PHASE_MS
          + ((nonAnchorOrder.get(n.id) ?? 0) / nonAnchorCount) * nonAnchorWindow;
      return {
        ...n,
        mountDelayMs,
        showLabel: labelIds.has(n.id),
      };
    });
    const edges: FloorEdge[] = deriveEdges(FLOOR_NODES);
    const links: SimLink[] = edges.map((e) => ({ id: e.id, source: e.source, target: e.target }));
    return { simNodes: nodes, simLinks: links };
  }, []);

  const [hoverId, setHoverId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [intervention, setIntervention] = useState<InterventionState | null>(null);

  const simNodesRef = useRef<SimNode[]>(simNodes);
  const simLinksRef = useRef<SimLink[]>(simLinks);
  const startedAtRef = useRef<number>(0);

  useEffect(() => { simNodesRef.current = simNodes; simLinksRef.current = simLinks; },
    [simNodes, simLinks]);

  // d3-force lifecycle.
  useEffect(() => {
    if (size.width === 0 || size.height === 0) return;
    const cx = size.width / 2, cy = size.height / 2;
    const span = Math.min(size.width, size.height) * 0.4;
    for (const n of simNodesRef.current) {
      if (n.pin) { n.fx = cx + n.pin.x * span; n.fy = cy + n.pin.y * span; }
    }
    // Pass-2 (F1): disperse the constellation. forceCenter (hard gravity)
    // is replaced by weak forceX/forceY toward viewport center. Charge is
    // bumped to push nodes apart, link distance widens so connected clusters
    // breathe, and collide radius grows so the field reads as a sky, not a clump.
    const sim = forceSimulation<SimNode>(simNodesRef.current)
      .force('link', forceLink<SimNode, SimLink>(simLinksRef.current)
        .id((d) => d.id).distance(100).strength(0.16))
      .force('charge', forceManyBody<SimNode>().strength(-240))
      .force('x', forceX<SimNode>(cx).strength(0.02))
      .force('y', forceY<SimNode>(cy).strength(0.02))
      .force('collide', forceCollide<SimNode>().radius(
        (n) => radiusForCount(n.olympians_paralympians_count) + 18))
      .alpha(0.9).alphaDecay(0.04);
    return () => { sim.stop(); };
  }, [size.width, size.height]);

  // Scripted intervention pulse — demo moment #3.
  useEffect(() => {
    if (reduceMotion) return;
    const handle = window.setTimeout(() => {
      setIntervention({ nodeId: INTERVENTION_NODE_ID, startedAt: performance.now() });
    }, INTERVENTION_DELAY_MS);
    return () => window.clearTimeout(handle);
  }, [reduceMotion]);

  // Canvas paint loop.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(size.width * dpr));
    canvas.height = Math.max(1, Math.floor(size.height * dpr));
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    startedAtRef.current = performance.now();
    let raf = 0;

    const draw = (now: number) => {
      ctx.clearRect(0, 0, size.width, size.height);
      const elapsed = now - startedAtRef.current;
      const nodes = simNodesRef.current;
      const links = simLinksRef.current;

      // Edges: viewport-faded hairlines (never the full graph at once).
      ctx.lineWidth = 1;
      const cx = size.width / 2, cy = size.height / 2;
      const fadeRadius = Math.max(size.width, size.height) * 0.7;
      for (const link of links) {
        const s = typeof link.source === 'object' ? (link.source as SimNode) : null;
        const t = typeof link.target === 'object' ? (link.target as SimNode) : null;
        if (!s || !t || s.x === undefined || s.y === undefined || t.x === undefined || t.y === undefined) continue;
        const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
        const d = Math.hypot(mx - cx, my - cy);
        const fade = Math.max(0, 1 - Math.max(0, d - fadeRadius * 0.5) / (fadeRadius * 0.5));
        if (fade <= 0.02) continue;
        ctx.strokeStyle = `rgba(${COLOR_NAVY_LIGHT}, ${0.6 * fade})`;
        ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke();
      }

      // Nodes: two-pass halo (Pass-2 F1) — radial gradient background,
      // then filled disc foreground with 1px stroke. Anchors at full
      // saturation, low-HND nodes (HND < 5) at 0.4 alpha so outliers feel
      // distant. Labels for the 5 brightest stars (3 anchors + top-2 HND)
      // are drawn after all nodes so they layer cleanly above any halos.
      const labeledStars: { n: SimNode; r: number; alphaMult: number }[] = [];
      for (const n of nodes) {
        if (n.x === undefined || n.y === undefined) continue;
        const r = radiusForCount(n.olympians_paralympians_count);

        // Cube ease-out approximates the room cubic-bezier for the opacity ramp.
        const localElapsed = Math.max(0, elapsed - n.mountDelayMs);
        const tt = reduceMotion ? 1 : Math.min(1, localElapsed / MOUNT_ANIM_MS);
        const eased = reduceMotion ? 1 : 1 - Math.pow(1 - tt, 3);
        if (eased <= 0) continue;
        const isHover = n.id === hoverId || n.id === selectedId;
        // Anchors stay at full saturation; low-HND nodes dim across all passes.
        const isAnchor = !!n.pin;
        const alphaMult = isAnchor || n.hnd >= HND_DIM_THRESHOLD ? 1 : HND_DIM_ALPHA;

        let pulse = 0;
        if (intervention && intervention.nodeId === n.id) {
          const since = now - intervention.startedAt;
          if (since >= 0 && since <= PULSE_MS) pulse = Math.sin(Math.PI * (since / PULSE_MS));
        }

        // Pass 1 (background): radial gradient — gold-warm 0.18α at center
        // → 0α at r * 3. Reads as a light source, not a filled disc.
        const haloR = r * 3 * (isHover ? 1.4 : 1);
        if (pulse > 0) {
          // Intervention pulse: same gradient but agitos-red, scaled by pulse.
          const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, haloR);
          grad.addColorStop(0, `rgba(${COLOR_AGITOS_RED}, ${0.45 * pulse * eased * alphaMult})`);
          grad.addColorStop(1, `rgba(${COLOR_AGITOS_RED}, 0)`);
          ctx.fillStyle = grad;
        } else {
          const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, haloR);
          const centerAlpha = (isHover ? 0.32 : 0.18) * eased * alphaMult;
          grad.addColorStop(0, `rgba(${COLOR_GOLD_WARM}, ${centerAlpha})`);
          grad.addColorStop(1, `rgba(${COLOR_GOLD_WARM}, 0)`);
          ctx.fillStyle = grad;
        }
        ctx.beginPath();
        ctx.arc(n.x, n.y, haloR, 0, Math.PI * 2);
        ctx.fill();

        // Pass 2 (foreground): filled disc + 1px stroke. shadowBlur kept as
        // a soft glow on the disc so it still reads as a light source rather
        // than a flat dot. The radial gradient does most of the lift now.
        ctx.save();
        ctx.shadowColor = pulse > 0
          ? `rgba(${COLOR_AGITOS_RED}, ${0.45 * pulse * eased * alphaMult})`
          : `rgba(${COLOR_GOLD_WARM}, ${(isHover ? 0.2 : 0.08) * eased * alphaMult})`;
        ctx.shadowBlur = HALO_BLUR;
        ctx.fillStyle = pulse > 0
          ? `rgba(${COLOR_AGITOS_RED}, ${0.45 * pulse * eased * alphaMult})`
          : `rgba(${COLOR_GOLD_WARM}, ${0.45 * eased * alphaMult})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.lineWidth = 1;
        ctx.strokeStyle = pulse > 0
          ? `rgba(${COLOR_AGITOS_RED}, ${eased * alphaMult * (0.85 * pulse + 0.85 * (1 - pulse))})`
          : `rgba(${COLOR_GOLD_WARM}, ${0.85 * eased * alphaMult})`;
        ctx.stroke();

        if (n.showLabel && eased > 0) {
          labeledStars.push({ n, r, alphaMult });
        }
      }

      // Labels (Pass-2 F5): JetBrains Mono 10px, tracked-small-caps, gold-warm
      // 0.6α, drawn 14px to the right of the node. Always visible — these 5
      // stars orient the viewer regardless of hover/click state.
      ctx.font = '10px "JetBrains Mono", "Menlo", monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      for (const star of labeledStars) {
        const { n, r, alphaMult } = star;
        if (n.x === undefined || n.y === undefined) continue;
        const localElapsed = Math.max(0, elapsed - n.mountDelayMs);
        const tt = reduceMotion ? 1 : Math.min(1, localElapsed / MOUNT_ANIM_MS);
        const eased = reduceMotion ? 1 : 1 - Math.pow(1 - tt, 3);
        ctx.fillStyle = `rgba(${COLOR_GOLD_WARM}, ${0.6 * eased * alphaMult})`;
        drawTrackedSmallCapsLabel(ctx, n.place, n.x + r + 14, n.y, 0.08);
      }

      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size.width, size.height, hoverId, selectedId, intervention, reduceMotion]);

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    setHoverId(hitTestNode(simNodesRef.current, e.clientX - rect.left, e.clientY - rect.top)?.id ?? null);
  }
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const node = hitTestNode(simNodesRef.current, e.clientX - rect.left, e.clientY - rect.top);
    if (!node) { setSelectedId(null); return; }
    setSelectedId((prev) => (prev === node.id ? null : node.id));
  }

  const hoveredNode = useMemo(
    () => simNodes.find((n) => n.id === hoverId) ?? null, [hoverId, simNodes]);
  const selectedNode = useMemo(
    () => simNodes.find((n) => n.id === selectedId) ?? null, [selectedId, simNodes]);

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
          aria-label="Constellation map of places that have produced Olympians and Paralympians"
        />
        {hoveredNode && hoveredNode.x !== undefined && hoveredNode.y !== undefined && (
          <FloorNodeCard node={hoveredNode} x={hoveredNode.x} y={hoveredNode.y} />
        )}
      </div>

      <AnimatePresence>
        {selectedNode && (
          <motion.aside
            key={selectedNode.id}
            initial={{ x: 80, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 60, opacity: 0 }}
            transition={{ duration: 0.36, ease: ROOM_EASE }}
            aria-label={`Verified-claims trail for ${selectedNode.place}`}
            className="absolute right-0 top-0 z-20 flex h-full w-full max-w-md flex-col border-l border-navy-light bg-navy-deep/95 px-6 py-8"
          >
            <header className="mb-4">
              <p className="font-body text-caption uppercase tracking-[0.18em] text-slate-room">place</p>
              <h2 className="mt-1 font-italic italic text-italic-md text-cream">{selectedNode.place}</h2>
              <p className="mt-1 font-body text-body-sm text-wire-text">
                {selectedNode.olympians_paralympians_count} Olympians and Paralympians since {selectedNode.since_year}.
              </p>
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="mt-3 font-mono text-mono-sm uppercase tracking-[0.12em] text-gold-warm/80 hover:text-gold-warm"
                aria-label="Close panel"
              >
                close
              </button>
              <div aria-hidden="true" className="mt-4 h-px w-full bg-gold-warm/60" />
            </header>
            <div className="flex flex-col gap-2 overflow-y-auto pr-2">
              {deriveWireTrail(selectedNode).map((evt) => (
                <WireRow key={evt.id} {...evt} />
              ))}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}

interface FloorNodeCardProps { node: FloorNode; x: number; y: number }

function FloorNodeCard({ node, x, y }: FloorNodeCardProps) {
  const r = radiusForCount(node.olympians_paralympians_count);
  return (
    <motion.div
      key={node.id}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: ROOM_EASE }}
      style={{ position: 'absolute', left: `${x + r + 12}px`, top: `${y - 12}px`, maxWidth: '280px' }}
      className="pointer-events-none z-10 border-l border-gold-warm/80 bg-navy-mid/95 px-4 py-3"
    >
      <p className="font-italic italic text-italic-sm text-cream">{node.place}</p>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        <span className="font-mono text-caption uppercase tracking-[0.14em] text-gold-warm/85">place</span>
        <span className="font-mono text-caption uppercase tracking-[0.14em] text-wire-text/80">{node.programs[0] ?? 'program'}</span>
        <span className="font-mono text-caption uppercase tracking-[0.14em] text-wire-text/80">{node.patterns[0] ?? 'pattern'}</span>
      </div>
      <p className="mt-2 font-body text-body-sm text-cream">
        {node.olympians_paralympians_count} Olympians and Paralympians since {node.since_year}.
      </p>
    </motion.div>
  );
}

export default Floor;
