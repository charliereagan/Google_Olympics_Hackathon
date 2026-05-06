// TypeScript shape for a single Wire event.
//
// Mirrors `agents/wire/types.py::WireEvent` (a `TypedDict` with `total=False`).
// Every Wire event flows: agent code -> `wire.emit()` proxy -> Firestore
// (`wire_events` collection) -> SSE Route Handler -> SSE consumer hook ->
// `<WireRow>` component. This type is the contract between the SSE bridge
// and Worker B's `<WireRow>` props.
//
// Fields marked optional here correspond to Python-side `total=False` fields
// that may or may not be present on a given document. The proxy guarantees
// `id`, `timestamp`, `agent`, `message`, `message_type`, and `mode` on every
// emitted document.

export type AgentId =
  | 'editor'
  | 'scout_desk'
  | 'investigator'
  | 'equity_editor'
  | 'storyteller'
  | 'narrator'
  | 'publish_gate';

export type SubAgentId = 'cinderella' | 'comeback' | 'hometown' | 'echo';

export type MessageType =
  | 'thinking'
  | 'milestone'
  | 'intervention'
  | 'decision';

export type Mode = 'live' | 'replay' | 'published';

export type VisualTreatment = 'normal' | 'highlighted' | 'intervention';

export interface NilRedactionLog {
  direct_matches_redacted: number;
  aggregations_applied: number;
}

export interface WireEvent {
  /** Firestore document id. */
  id: string;
  /** ISO 8601 timestamp; rendered as HH:MM:SS in the row header. */
  timestamp: string;
  agent: AgentId;
  sub_agent?: SubAgentId;
  /** Post-NIL-redaction text. Never the pre-redaction string. */
  message: string;
  message_type: MessageType;
  confidence?: number;
  confidence_delta?: number;
  story_unit_id?: string;
  investigation_id?: string;
  evidence_refs?: string[];
  mode: Mode;
  visual_treatment?: VisualTreatment;
  /** Per BUILD_SPEC §6.10 — `1.0` ambient, `0.25` for the 4× live CTA. */
  compression_factor?: number;
  nil_redaction_log?: NilRedactionLog;
}
