/**
 * Client-side accessor for the per-agent streaming-cognition profiles.
 *
 * Source of truth: /data/streaming_profiles.json (committed at repo root,
 * mirrored into web/data for App Router static import).
 *
 * Spec:
 *   - BUILD_SPEC §6.5 (variable cognition speed)
 *   - BUILD_SPEC §6.11 (streaming profile schema)
 *   - design-system.md §5 (motion + streaming cognition speed)
 *
 * The runtime serves the same data via /health/agents (BUILD_SPEC §6.11);
 * for the static fixture page we import the JSON directly so the design
 * review doesn't require a backend.
 */

import streamingProfiles from '@/data/streaming_profiles.json';
import type { StreamingProfile, AgentId, SubAgentId } from '@/components/WireRow';

// ---------------------------------------------------------------------------
// Mapping: a Wire event with sub_agent='cinderella' should resolve to the
// 'cinderella' profile in the JSON, not 'scout_desk'. Sub-scouts have their
// own keys; the parent Scout Desk has its own. The lookup precedence is:
//
//   1. If sub_agent is set → use sub_agent key (cinderella/comeback/hometown/echo)
//   2. Else → use agent key
// ---------------------------------------------------------------------------

type ProfileMap = Record<string, StreamingProfile>;

const PROFILES = streamingProfiles as ProfileMap;

const FALLBACK: StreamingProfile = PROFILES.editor ?? {
  agent: 'editor',
  base_chars_per_second: 30,
  jitter: 0.15,
  mid_message_pause_chance: 0.15,
  pause_min_ms: 150,
  pause_max_ms: 350,
  arrival_style: 'streamed',
};

/**
 * Resolve the streaming profile for a Wire event.
 *
 * @param agent     Top-level agent id
 * @param subAgent  Optional sub-scout id; takes precedence when present
 * @returns         The matching StreamingProfile, or the editor fallback
 */
export function getStreamingProfile(
  agent: AgentId,
  subAgent?: SubAgentId,
): StreamingProfile {
  const key = subAgent ?? agent;
  return PROFILES[key] ?? FALLBACK;
}

/** All known profiles, keyed by their JSON identifier. */
export function getAllProfiles(): ReadonlyMap<string, StreamingProfile> {
  return new Map(Object.entries(PROFILES));
}
