'use client';

/**
 * <AgentFloor /> — BUILD_SPEC §9 agent-graph backstage view.
 *
 * Seven agent nodes (CONSTITUTION Rule 2), hairline edges, and a particle
 * stream traveling each edge every time the agent runtime emits a handoff.
 * Mirrors <Field />'s D3-on-Canvas pattern — Hi-DPI Canvas + d3-force +
 * analytical particle positions (no SVG, no `getPointAtLength`, per §9.6).
 * Subscribes to `event: handoff` / `event: handoff-preseed` from the
 * already-existing SSE bridge at `/api/wire/stream` (HOE-DEC-024).
 * Day-7 simplification: one tool-call card per handoff (real lifecycle
 * tracking is Day-8 polish; visual rhythm is what matters now).
 */

import { fetchEventSource } from '@microsoft/fetch-event-source';
import { AnimatePresence } from 'framer-motion';
import {
  forceLink, forceManyBody, forceSimulation, forceX, forceY,
  type SimulationLinkDatum, type SimulationNodeDatum,
} from 'd3-force';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AGENT_BY_ID, AGENT_EDGES, AGENT_NODES,
  COLOR_AGITOS_RED, COLOR_GOLD_WARM, COLOR_NAVY_LIGHT,
  EQUITY_INTERVENE_TOOL_CALL,
  type AgentHandoffEvent, type AgentId, type AgentNode,
} from '@/lib/agent-floor-fixture';
import { ToolCallCard } from './ToolCallCard';

interface SimNode extends AgentNode, SimulationNodeDatum {}
type SimLink = SimulationLinkDatum<SimNode> & { id: string };

interface Particle {
  fromId: AgentId;
  toId: AgentId;
  /** rgb triple ("r, g, b") matching the from-agent (or agitos-red for EE intervention). */
  rgb: string;
  /** ms timestamp (performance.now()) when the particle was spawned. */
  startedAt: number;
}

interface InterventionFlash {
  startedAt: number;
}

// Visual constants — kept top-of-module per Field.tsx's pattern.
const PARTICLE_MS = 800;          // BUILD_SPEC §9.3 — particle travel duration.
const PARTICLE_R_DESKTOP = 2.5;   // 5px diameter on desktop (task brief says 4px; tuned for halo).
const PARTICLE_R_MOBILE = 2;
const PULSE_MS = 600;             // BUILD_SPEC §9.5 — Equity Editor flash duration.
const CARD_LIFETIME_MS = 3000;    // BUILD_SPEC §9.4 — cards persist ~3s after completion.
const MAX_CARDS = 6;              // Bottom-right stack cap (mobile clamps further).
const MAX_PARTICLES = 60;         // Backpressure: drop the oldest when exceeded.

// Cube ease-out — matches the BUILD_SPEC §9.6 analytical position formula.
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

// Manual tracked-cap label, mirroring Field.tsx's helper. Canvas 2D's
// `letterSpacing` is experimental, so we measure each glyph and advance.
function drawTrackedCapsLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  y: number,
  fontSizePx: number,
  emSpacing: number,
): void {
  const upper = text.toUpperCase();
  const widths: number[] = [];
  let total = 0;
  const advance = emSpacing * fontSizePx;
  for (const ch of upper) {
    const w = ctx.measureText(ch).width;
    widths.push(w);
    total += w + advance;
  }
  total -= advance; // no trailing space after the last glyph
  let cursor = cx - total / 2;
  for (let i = 0; i < upper.length; i += 1) {
    ctx.fillText(upper[i]!, cursor, y);
    cursor += widths[i]! + advance;
  }
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

export function AgentFloor() {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Sim nodes + links — built once. Pinned positions get rewritten on
  // viewport resize via fx/fy.
  const { simNodes, simLinks } = useMemo(() => {
    const nodes: SimNode[] = AGENT_NODES.map((n) => ({ ...n }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const links: SimLink[] = AGENT_EDGES.map(([a, b]) => ({
      id: `${a}|${b}`,
      source: byId.get(a)!,
      target: byId.get(b)!,
    }));
    return { simNodes: nodes, simLinks: links };
  }, []);

  const simNodesRef = useRef<SimNode[]>(simNodes);
  const simLinksRef = useRef<SimLink[]>(simLinks);
  useEffect(() => {
    simNodesRef.current = simNodes;
    simLinksRef.current = simLinks;
  }, [simNodes, simLinks]);

  // Live particle pool — mutated in-place inside the raf loop (no React
  // state for per-frame data, per Field.tsx pattern).
  const particlesRef = useRef<Particle[]>([]);
  const interventionRef = useRef<InterventionFlash | null>(null);

  // Tool-call card stack — React state because Framer Motion's
  // AnimatePresence drives slide/fade choreography.
  const [cards, setCards] = useState<AgentHandoffEvent[]>([]);
  // Track per-card lifetime timeouts so we can clear on unmount.
  const cardTimeoutsRef = useRef<Map<string, number>>(new Map());

  /** Push a handoff onto the visual pipeline: particle + card + flash. */
  function ingestHandoff(handoff: AgentHandoffEvent) {
    if (!AGENT_BY_ID[handoff.from_agent] || !AGENT_BY_ID[handoff.to_agent]) return;

    const isEquityIntervention =
      handoff.from_agent === 'equity_editor' &&
      handoff.tool_call_id === EQUITY_INTERVENE_TOOL_CALL;

    // Particle: from-agent color (or agitos-red for EE intervention).
    const rgb = isEquityIntervention ? COLOR_AGITOS_RED : AGENT_BY_ID[handoff.from_agent].rgb;
    particlesRef.current.push({
      fromId: handoff.from_agent,
      toId: handoff.to_agent,
      rgb,
      startedAt: performance.now(),
    });
    if (particlesRef.current.length > MAX_PARTICLES) {
      particlesRef.current.splice(0, particlesRef.current.length - MAX_PARTICLES);
    }

    // Equity flash — drive the node pulse for PULSE_MS.
    if (isEquityIntervention) {
      interventionRef.current = { startedAt: performance.now() };
    }

    // Card stack — append, schedule removal at CARD_LIFETIME_MS.
    setCards((prev) => {
      const next = [...prev, handoff];
      // Cap visible cards — drop the oldest.
      while (next.length > MAX_CARDS) {
        const dropped = next.shift();
        if (dropped) {
          const tid = cardTimeoutsRef.current.get(dropped.id);
          if (tid !== undefined) {
            window.clearTimeout(tid);
            cardTimeoutsRef.current.delete(dropped.id);
          }
        }
      }
      return next;
    });
    const tid = window.setTimeout(() => {
      setCards((prev) => prev.filter((c) => c.id !== handoff.id));
      cardTimeoutsRef.current.delete(handoff.id);
    }, CARD_LIFETIME_MS);
    cardTimeoutsRef.current.set(handoff.id, tid);
  }

  // SSE subscription — `event: handoff` (live) + `event: handoff-preseed`
  // (initial replay). The existing /api/wire/stream route already emits
  // both event types — we just consume them.
  useEffect(() => {
    const ctrl = new AbortController();
    // Capture the timeout map so the cleanup closure can drain it even if
    // the ref's `.current` is reassigned by a future refactor — addresses
    // the react-hooks/exhaustive-deps lint warning.
    const timeoutsMap = cardTimeoutsRef.current;
    fetchEventSource('/api/wire/stream', {
      signal: ctrl.signal,
      openWhenHidden: true,
      onmessage(msg) {
        if (msg.event !== 'handoff' && msg.event !== 'handoff-preseed') return;
        try {
          const handoff = JSON.parse(msg.data) as AgentHandoffEvent;
          ingestHandoff(handoff);
        } catch {
          // Malformed payload — drop the frame.
        }
      },
      onerror() {
        // Let the lib's default backoff retry. No UI panic.
      },
    }).catch(() => {
      // AbortError on unmount; ignore.
    });
    return () => {
      ctrl.abort();
      // Flush card timeouts so an unmount during card-life doesn't leak.
      timeoutsMap.forEach((tid) => window.clearTimeout(tid));
      timeoutsMap.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // d3-force simulation — pinned coords, gentle charge so the seven nodes
  // breathe rather than bouncing. forceCenter is intentionally absent
  // (every node is pinned via fx/fy).
  useEffect(() => {
    if (size.width === 0 || size.height === 0) return;
    const cx = size.width / 2;
    const cy = size.height / 2;
    const span = Math.min(size.width, size.height) * 0.42;
    for (const n of simNodesRef.current) {
      n.fx = cx + n.pin.x * span;
      n.fy = cy + n.pin.y * span;
    }
    const sim = forceSimulation<SimNode>(simNodesRef.current)
      .force('link', forceLink<SimNode, SimLink>(simLinksRef.current)
        .id((d) => d.id).distance(180).strength(0.1))
      .force('charge', forceManyBody<SimNode>().strength(-350))
      .force('x', forceX<SimNode>(cx).strength(0.04))
      .force('y', forceY<SimNode>(cy).strength(0.04))
      .alpha(0.6)
      .alphaDecay(0.05);
    return () => { sim.stop(); };
  }, [size.width, size.height]);

  // Mobile breakpoint detection — drives node radius + particle radius.
  const isMobile = size.width > 0 && size.width < 640;
  const nodeRadius = isMobile ? 30 : 40; // 60px / 80px diameter per the brief
  const particleRadius = isMobile ? PARTICLE_R_MOBILE : PARTICLE_R_DESKTOP;

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

    let raf = 0;

    const draw = (now: number) => {
      ctx.clearRect(0, 0, size.width, size.height);
      const nodes = simNodesRef.current;
      const links = simLinksRef.current;

      // -- Edges: hairline navy-light, 60% alpha. ---------------------
      ctx.lineWidth = 1;
      ctx.strokeStyle = `rgba(${COLOR_NAVY_LIGHT}, 0.6)`;
      ctx.beginPath();
      for (const link of links) {
        const s = typeof link.source === 'object' ? (link.source as SimNode) : null;
        const t = typeof link.target === 'object' ? (link.target as SimNode) : null;
        if (!s || !t || s.x === undefined || s.y === undefined || t.x === undefined || t.y === undefined) continue;
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
      }
      ctx.stroke();

      // -- Particles: analytical position per BUILD_SPEC §9.6. -------
      // Pool is mutated in-place; we splice expired particles in a second
      // pass to avoid re-allocating per frame.
      const pool = particlesRef.current;
      let writeIdx = 0;
      for (let i = 0; i < pool.length; i += 1) {
        const p = pool[i]!;
        const elapsed = now - p.startedAt;
        const tt = elapsed / PARTICLE_MS;
        if (tt >= 1) continue; // drop — don't copy forward
        const a = AGENT_BY_ID[p.fromId];
        const b = AGENT_BY_ID[p.toId];
        const aNode = nodes.find((n) => n.id === a.id);
        const bNode = nodes.find((n) => n.id === b.id);
        if (!aNode || !bNode || aNode.x === undefined || aNode.y === undefined
          || bNode.x === undefined || bNode.y === undefined) {
          pool[writeIdx++] = p; // keep — sim not settled yet
          continue;
        }
        const eased = easeOutCubic(tt);
        const px = aNode.x + (bNode.x - aNode.x) * eased;
        const py = aNode.y + (bNode.y - aNode.y) * eased;

        // Trail glow — small radial gradient at the particle.
        const trail = ctx.createRadialGradient(px, py, 0, px, py, particleRadius * 4);
        trail.addColorStop(0, `rgba(${p.rgb}, 0.55)`);
        trail.addColorStop(1, `rgba(${p.rgb}, 0)`);
        ctx.fillStyle = trail;
        ctx.beginPath();
        ctx.arc(px, py, particleRadius * 4, 0, Math.PI * 2);
        ctx.fill();

        // Solid head.
        ctx.fillStyle = `rgba(${p.rgb}, 0.95)`;
        ctx.beginPath();
        ctx.arc(px, py, particleRadius, 0, Math.PI * 2);
        ctx.fill();

        pool[writeIdx++] = p;
      }
      // Truncate the pool after the in-place compaction.
      pool.length = writeIdx;

      // -- Equity flash: drive the EE node's outer ring. ------------
      let equityPulse = 0;
      if (interventionRef.current) {
        const since = now - interventionRef.current.startedAt;
        if (since >= 0 && since <= PULSE_MS) {
          // Sin envelope, 0 → 1 → 0 over PULSE_MS.
          equityPulse = Math.sin(Math.PI * (since / PULSE_MS));
        } else if (since > PULSE_MS) {
          interventionRef.current = null;
        }
      }

      // -- Nodes: 80px circle (60px on mobile), 1px stroke, status dot.
      for (const n of nodes) {
        if (n.x === undefined || n.y === undefined) continue;
        const r = nodeRadius;
        const isEquity = n.id === 'equity_editor';

        // Outer flash ring for the Equity Editor (BUILD_SPEC §9.5).
        if (isEquity && equityPulse > 0) {
          const flashR = r + 6 + equityPulse * 6;
          ctx.lineWidth = 2;
          ctx.strokeStyle = `rgba(${COLOR_AGITOS_RED}, ${0.4 + 0.6 * equityPulse})`;
          ctx.beginPath();
          ctx.arc(n.x, n.y, flashR, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Fill — navy-mid for Scout Desk (deep navy per the brief), the
        // agent rgb at low alpha for the rest. The stroke carries the
        // identity color cleanly without making nodes look like buttons.
        ctx.fillStyle = `rgba(${n.rgb}, ${n.id === 'scout_desk' ? 0.9 : 0.18})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fill();

        // 1px stroke in the agent color.
        ctx.lineWidth = 1;
        ctx.strokeStyle = `rgba(${n.rgb}, ${isEquity && equityPulse > 0 ? 1 : 0.85})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.stroke();

        // Status dot inside the node (4px). Thinking pulse for ambient
        // life — sin envelope on a 1.6s loop. Equity dot turns red during
        // the intervention pulse.
        const pulseT = (now % 1600) / 1600;
        const dotAlpha = 0.5 + 0.4 * Math.sin(2 * Math.PI * pulseT);
        ctx.fillStyle = isEquity && equityPulse > 0
          ? `rgba(${COLOR_AGITOS_RED}, ${0.7 + 0.3 * equityPulse})`
          : `rgba(${COLOR_GOLD_WARM}, ${dotAlpha})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y - 1, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Label — tracked-cap mono, just below the node.
        const fontPx = isMobile ? 9 : 10;
        ctx.font = `${fontPx}px "JetBrains Mono", "Menlo", monospace`;
        ctx.fillStyle = `rgba(${COLOR_GOLD_WARM}, 0.78)`;
        ctx.textAlign = 'left'; // drawTrackedCapsLabel re-centers manually
        ctx.textBaseline = 'top';
        drawTrackedCapsLabel(ctx, n.label, n.x, n.y + r + 8, fontPx, 0.12);
      }

      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size.width, size.height, isMobile, nodeRadius, particleRadius]);

  // Card stack — clamp to 3 on mobile so the canvas keeps room to breathe.
  const visibleCards = useMemo(() => {
    const cap = isMobile ? 3 : MAX_CARDS;
    return cards.slice(-cap);
  }, [cards, isMobile]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="relative h-full w-full">
        <canvas
          ref={canvasRef}
          aria-label="Agent graph — seven agents and the handoff streams between them"
        />
      </div>

      {/* Bottom-right tool-call card stack. AnimatePresence drives the
          slide-in / fade-out per BUILD_SPEC §9.4. Mobile: card column
          spans most of the viewport width, capped at 3 visible. */}
      <div
        aria-live="polite"
        aria-label="Active dispatches"
        className="pointer-events-none absolute bottom-4 right-4 z-10 flex w-[calc(100%-2rem)] flex-col gap-2 sm:right-6 sm:w-auto sm:max-w-xs"
      >
        <AnimatePresence initial={false}>
          {visibleCards.map((handoff) => (
            <ToolCallCard key={handoff.id} handoff={handoff} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default AgentFloor;
