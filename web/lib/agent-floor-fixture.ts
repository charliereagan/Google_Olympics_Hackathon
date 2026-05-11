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

// VPS-DEC-037 § "Tool call cards — cleanly labeled" (2026-05-11):
// every tool-call card's top line must name the actual Google service in
// use, not the internal handoff verb. This mapping converts a handoff's
// `tool_call_id` into a `SERVICE · MODEL` (or `SERVICE · TABLE`) string
// that a judge can read at a glance. Falls back to VERTEX AI · GEMINI
// 3.1 PRO — the dominant deliberation path — when the id is unknown
// (Editor / Storyteller / Investigator / Equity / Publish Gate
// deliberation cycles all hit Gemini 3.1 Pro on Vertex AI, per the
// dispatch tools in `agents/handoffs.py`).
export function gcpServiceLabel(toolCallId: string, fromAgent?: AgentId): string {
  // Direct matches — explicit operations whose service is unambiguous.
  switch (toolCallId) {
    case 'dispatch_scout_desk':
      return 'VERTEX AI · GEMINI 3 FLASH';
    case 'request_narrator':
      return 'VERTEX AI · GEMINI 3.1 FLASH TTS';
    case 'nano_banana_pro':
      return 'VERTEX AI · NANO BANANA PRO';
    case 'gemini_search_grounding':
      return 'GEMINI · GOOGLE SEARCH GROUNDING';
    case 'nil_redaction_layer':
      return 'NIL REDACTION LAYER · SCAN';
    case 'intervene_feed_drift':
    case 'request_equity_review':
      // Equity Editor deliberation is a Gemini 3.1 Pro call.
      return 'VERTEX AI · GEMINI 3.1 PRO';
    case 'request_publish_gate':
      return 'VERTEX AI · GEMINI 3.1 PRO';
    case 'dispatch_storyteller':
    case 'dispatch_investigator':
      return 'VERTEX AI · GEMINI 3.1 PRO';
    case 'bigquery_candidates':
      return 'BIGQUERY · CANDIDATES';
    default:
      break;
  }

  // Pattern matches — for handoff ids that aren't in the registry.
  if (toolCallId.startsWith('bigquery_')) {
    const table = toolCallId.slice('bigquery_'.length).toUpperCase();
    return `BIGQUERY · ${table}`;
  }
  if (toolCallId.startsWith('firestore_read_')) {
    const collection = toolCallId.slice('firestore_read_'.length).toUpperCase();
    return `FIRESTORE · ${collection} · READ`;
  }
  if (toolCallId.startsWith('firestore_write_')) {
    const collection = toolCallId.slice('firestore_write_'.length).toUpperCase();
    return `FIRESTORE · ${collection} · WRITE`;
  }
  if (toolCallId.includes('deep_research')) {
    return 'VERTEX AI · GEMINI DEEP RESEARCH';
  }
  if (toolCallId.includes('flash_lite') || toolCallId.includes('near_id')) {
    return 'VERTEX AI · GEMINI 3.1 FLASH-LITE';
  }
  if (toolCallId.includes('visual_review')) {
    return 'VISUAL REVIEW · STYLIZATION CHECK';
  }

  // Scout-desk-originated handoffs that aren't named explicitly default to
  // the parallel-Flash scout cycle path.
  if (fromAgent === 'scout_desk') {
    return 'VERTEX AI · GEMINI 3 FLASH';
  }
  // Narrator-originated handoffs default to the TTS render path.
  if (fromAgent === 'narrator') {
    return 'VERTEX AI · GEMINI 3.1 FLASH TTS';
  }

  // Fallback: the dominant deliberation path.
  return 'VERTEX AI · GEMINI 3.1 PRO';
}

// Stable lookup keyed by agent id. Frozen so callers can't mutate.
export const AGENT_BY_ID: Readonly<Record<AgentId, AgentNode>> = Object.freeze(
  Object.fromEntries(AGENT_NODES.map((n) => [n.id, n])) as Record<AgentId, AgentNode>,
);
