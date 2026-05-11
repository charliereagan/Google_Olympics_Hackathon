// Floor fixture — the seven-agent cast for BUILD_SPEC §9.
//
// Locked by CONSTITUTION Rule 2 (sub-scouts live inside Scout Desk, never
// as separate Floor nodes). Colors are direct design-system.md §2 tokens
// expressed as rgba() triples for Canvas. Pin coords are unit-vectors
// against viewport center; AgentFloor scales by `span` so the composition
// is stable across breakpoints.

export type AgentId =
  | 'editor'
  | 'scout_desk'
  | 'investigator'
  | 'equity_editor'
  | 'storyteller'
  | 'narrator'
  | 'publish_gate';

export interface AgentNode {
  /** Stable id matching `agents/handoffs.py::AGENT_IDS`. */
  id: AgentId;
  /** Tracked-cap label drawn under the node (e.g. "EQUITY EDITOR"). */
  label: string;
  /** rgba() triple — no alpha, no `#`. Direct tokens from design-system §2. */
  rgb: string;
  /** Unit-vector pin against viewport center. */
  pin: { x: number; y: number };
}

// design-system.md §2 — the locked palette, expressed as rgba() triples
// for Canvas (which cannot consume Tailwind class names directly).
export const COLOR_GOLD_WARM = '212, 168, 74'; // editor
export const COLOR_NAVY_MID = '26, 39, 64'; // scout_desk fill (deep navy)
export const COLOR_NAVY_LIGHT = '44, 62, 90'; // hairline edges
export const COLOR_PARCHMENT = '232, 221, 196'; // investigator
export const COLOR_AGITOS_RED = '200, 16, 46'; // equity_editor
export const COLOR_CREAM = '245, 239, 224'; // storyteller (warm cream)
export const COLOR_DEEP_BLUE = '74, 110, 168'; // narrator (deeper blue)
export const COLOR_SLATE = '90, 104, 120'; // publish_gate

// Pin coords (unit vectors). Editor center-top, Storyteller center-bottom,
// Investigator left, Equity Editor right-of-center, Publish Gate right,
// Narrator far-right, Scout Desk far-left. Per the task brief.
export const AGENT_NODES: AgentNode[] = [
  { id: 'editor',        label: 'EDITOR',        rgb: COLOR_GOLD_WARM, pin: { x: 0.0,  y: -0.62 } },
  { id: 'scout_desk',    label: 'SCOUT DESK',    rgb: COLOR_NAVY_MID,  pin: { x: -0.9, y: -0.05 } },
  { id: 'investigator',  label: 'INVESTIGATOR',  rgb: COLOR_PARCHMENT, pin: { x: -0.45, y: 0.35 } },
  { id: 'equity_editor', label: 'EQUITY EDITOR', rgb: COLOR_AGITOS_RED, pin: { x: 0.25, y: 0.05 } },
  { id: 'publish_gate',  label: 'PUBLISH GATE',  rgb: COLOR_SLATE,     pin: { x: 0.62, y: 0.35 } },
  { id: 'narrator',      label: 'NARRATOR',      rgb: COLOR_DEEP_BLUE, pin: { x: 0.9,  y: -0.05 } },
  { id: 'storyteller',   label: 'STORYTELLER',   rgb: COLOR_CREAM,     pin: { x: 0.0,  y: 0.62 } },
];

// Edge pairs — Editor connects to all six others (the orchestrator); the
// remaining pairs encode organizational flow (Scout → Investigator;
// Investigator ↔ Equity; Investigator → Storyteller; Storyteller →
// Publish Gate + Narrator; Publish Gate ↔ Narrator). Undirected visually;
// particles travel either way along the same line.
export const AGENT_EDGES: ReadonlyArray<readonly [AgentId, AgentId]> = [
  // Editor as the hub.
  ['editor', 'scout_desk'],
  ['editor', 'investigator'],
  ['editor', 'equity_editor'],
  ['editor', 'storyteller'],
  ['editor', 'narrator'],
  ['editor', 'publish_gate'],
  // Organizational flow.
  ['scout_desk', 'investigator'],
  ['investigator', 'equity_editor'],
  ['investigator', 'storyteller'],
  ['storyteller', 'publish_gate'],
  ['storyteller', 'narrator'],
  ['publish_gate', 'narrator'],
];

/** Handoff event shape — mirrors the SSE bridge's `event: handoff` payload. */
export interface AgentHandoffEvent {
  id: string;
  from_agent: AgentId;
  to_agent: AgentId;
  tool_call_id: string;
  story_unit_id: string | null;
  investigation_id: string | null;
  timestamp: string;
  mode: 'live' | 'replay' | 'published';
}

// Demo-moment-#3 trigger: handoff `from_agent='equity_editor'` AND
// `tool_call_id===EQUITY_INTERVENE_TOOL_CALL` flashes the EE node red.
export const EQUITY_INTERVENE_TOOL_CALL = 'intervene_feed_drift';

// Friendly display labels for common dispatch tools. Falls back to the raw
// `tool_call_id` (with underscores spaced) when not found.
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  dispatch_scout_desk: 'Dispatch · Scout Desk',
  dispatch_investigator: 'Dispatch · Investigator',
  dispatch_storyteller: 'Dispatch · Storyteller',
  request_equity_review: 'Equity · Parity Review',
  intervene_feed_drift: 'Equity · Intervene (Feed Drift)',
  request_publish_gate: 'Publish Gate · Audit',
  request_narrator: 'Narrator · Synthesize',
  bigquery_candidates: 'BigQuery · Candidates',
  gemini_search_grounding: 'Gemini · Search Grounding',
  nano_banana_pro: 'Nano Banana Pro · Hero',
  nil_redaction_layer: 'NIL Redaction Layer',
};

export function toolDisplayName(id: string): string {
  return TOOL_DISPLAY_NAMES[id] ?? id.replace(/_/g, ' ');
}

// Stable lookup keyed by agent id. Frozen so callers can't mutate.
export const AGENT_BY_ID: Readonly<Record<AgentId, AgentNode>> = Object.freeze(
  Object.fromEntries(AGENT_NODES.map((n) => [n.id, n])) as Record<AgentId, AgentNode>,
);
