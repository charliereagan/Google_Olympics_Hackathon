/**
 * Static mapping from internal agent_id (and sub_agent_id) to the Gemini
 * model that backs that agent in production, plus the formatted display
 * label rendered on /wire and in any agent caption strip.
 *
 * This is the single source of truth for "which Gemini model runs which
 * agent" in the frontend. The model attribution rendered on every Wire
 * event is read from here — NOT synthesized per event, per the VPS
 * treatment spec (Addition 3 of /wire).
 *
 * Mirror of the model-router config on the agent runtime side
 * (HOE-DEC-016 / tech_snapshot.md). If a model is swapped in production,
 * this table is the canonical place to update on the frontend.
 */

import type { AgentId, SubAgentId } from './wire-event';

/** Display name for the top-level agent (no model). */
export const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  editor: 'Editor',
  scout_desk: 'Scout Desk',
  investigator: 'Investigator',
  equity_editor: 'Equity Editor',
  storyteller: 'Storyteller',
  narrator: 'Narrator',
  publish_gate: 'Publish Gate',
};

/** Display name for a sub-scout (no model). */
export const SUB_AGENT_DISPLAY_NAMES: Record<SubAgentId, string> = {
  cinderella: 'Cinderella Scout',
  comeback: 'Comeback Scout',
  hometown: 'Hometown Scout',
  echo: 'Echo Scout',
};

/** Gemini-model attribution string in parentheses on each agent. */
export const AGENT_MODEL_LABEL: Record<AgentId, string> = {
  editor: 'Gemini 3.1 Pro',
  scout_desk: 'Gemini 3 Flash',
  investigator: 'Gemini 3.1 Pro + Deep Research',
  equity_editor: 'Gemini 3.1 Pro',
  storyteller: 'Gemini 3.1 Pro',
  narrator: 'Gemini 3.1 Flash TTS',
  publish_gate: 'Gemini 3.1 Pro + NIL Redaction Layer',
};

/** All four sub-scouts run on the same Gemini 3 Flash backbone. */
export const SUB_AGENT_MODEL_LABEL: Record<SubAgentId, string> = {
  cinderella: 'Gemini 3 Flash',
  comeback: 'Gemini 3 Flash',
  hometown: 'Gemini 3 Flash',
  echo: 'Gemini 3 Flash',
};

/**
 * Get the (display name, model label) pair for an event. If a sub_agent
 * is set, use that — otherwise fall back to the top-level agent.
 */
export function getAgentAttribution(
  agent: AgentId,
  sub_agent?: SubAgentId,
): { name: string; model: string } {
  if (sub_agent) {
    return {
      name: SUB_AGENT_DISPLAY_NAMES[sub_agent],
      model: SUB_AGENT_MODEL_LABEL[sub_agent],
    };
  }
  return {
    name: AGENT_DISPLAY_NAMES[agent],
    model: AGENT_MODEL_LABEL[agent],
  };
}

/**
 * Filter-pill set for /wire's optional filter affordance. Maps pill id
 * (URL query param `?agent=`) to the set of internal agent ids that
 * pill should include.
 *
 * "scouts" expands to scout_desk PLUS any event tagged with a sub_agent
 * (Cinderella / Comeback / Hometown / Echo).
 */
export type WireFilterId =
  | 'all'
  | 'editor'
  | 'scouts'
  | 'investigator'
  | 'equity_editor'
  | 'storyteller'
  | 'narrator'
  | 'publish_gate';

export const WIRE_FILTER_PILLS: ReadonlyArray<{ id: WireFilterId; label: string }> = [
  { id: 'all', label: 'ALL' },
  { id: 'editor', label: 'EDITOR' },
  { id: 'scouts', label: 'SCOUTS' },
  { id: 'investigator', label: 'INVESTIGATOR' },
  { id: 'equity_editor', label: 'EQUITY EDITOR' },
  { id: 'storyteller', label: 'STORYTELLER' },
  { id: 'narrator', label: 'NARRATOR' },
  { id: 'publish_gate', label: 'PUBLISH GATE' },
];

/** Return true if the event matches the active filter pill. */
export function matchesWireFilter(
  filter: WireFilterId,
  agent: AgentId,
  sub_agent?: SubAgentId,
): boolean {
  if (filter === 'all') return true;
  if (filter === 'scouts') {
    return agent === 'scout_desk' || sub_agent !== undefined;
  }
  return agent === filter;
}
