# The Storyteller's Room

Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling.

*Built on Google's brand-new **Agent Development Kit (ADK)** — the Gemini Enterprise Agent Platform — with five Gemini models (3.1 Pro, 3 Flash, 3.1 Flash-Lite, Deep Research, 3.1 Flash TTS), Nano Banana Pro for imagery, Cloud Run, BigQuery, Firestore, and Cloud Storage. The year of agents — fully on display.*

---

## What the room does

The Storyteller's Room operates continuously. Seven coordinated Gemini agents scout public data, investigate leads, verify claims, enforce Olympic and Paralympic parity, and produce narrated broadcast-style story pages about the *places* that quietly produce Team USA. The user does not run queries. They open the page and watch a working newsroom: a small town in Iowa surfaces; a regional pipeline disappears for nineteen years and returns; an old air base outside Colorado Springs reveals itself as a unified residency for endurance athletes. The protagonists are places, programs, and patterns — never named individuals.

Four fan-facing surfaces frame the experience:

- **The Wire** — agents thinking and handing off to each other in real time.
- **The Field** — the universe of places under investigation, rendered as a constellation.
- **The Map** — geographic discovery for fans whose entry point is *"what about my region?"*
- **The Broadcast** — narrated, illustrated, source-verified story pages about each place, with the system's audit trail one click away.

A seed-prompt CTA lets any fan ask the room to find a story they've never heard. The investigation streams in compressed time; a finished story is one click away.

---

## Challenge 2 — and beyond

Submitted to **Challenge 2: The Hometown Success Engine.** The Storyteller's Room is the literal definition: it identifies hubs by correlating geography with Team USA representation, focuses on counts of Olympians and Paralympians from hometowns rather than medal counts, uses conditional phrasing throughout, and is inclusive of all athletes by treating Paralympic representation as a structural system property rather than a toggle or a tab.

The architecture also addresses **Challenge 1 (parity)** through the Paralympic Equity Editor's veto authority, and **Challenge 3 (LA28 momentum)** through the trend signals the Investigator captures in every Investigation Packet. These are natural extensions of the architecture, not feature additions.

---

## Agentic AI tech, mapped to the contest's asks

The brief was specific. *"Fan-centric problem."* *"Interactive tools for fans."* *"Strong Paralympic representation."* *"Inclusive of all athletes."* *"Conditional phrasing — could help find."* *"Strict prohibition on athlete name, image, and likeness."* Every piece of new agentic Google Cloud technology in this build maps directly to one of those asks. Here is the mapping.

**The brief asks for strong Paralympic representation. We used the Agent Development Kit.**
The Paralympic Equity Editor is a structurally distinct agent with veto authority over publication — possible only because **ADK** lets us define agent boundaries and editorial authority at the platform level, not at the prompt level. The Equity Editor monitors feed drift across published places, returns drafts with shallow Paralympic context, and blocks any draft that frames disability as inspiration porn. Parity is a system property, not a prompt instruction.

**The brief's NIL prohibition is strict. We used ADK to make compliance architectural.**
ADK's agent boundary contracts let us insert the **NIL Redaction Layer** — a Python module that maintains a registry of 11,000+ athletes — between the Storyteller agent's output and any user-facing surface. Direct matches redacted. Near-identifications returned. Small-aggregate identifications rewritten as counts. Without ADK's agent contracts, this would have to be a brittle prompt instruction. With ADK, it's a structural guarantee enforced at the platform layer. Every Broadcast page's audit footer shows the Layer's work in concrete numbers. The constraint became the credibility flex.

**The brief asks for interactive tools for fans. We used Gemini 3.1 Flash TTS to make the stories audible.**
The Narrator agent calls **Gemini 3.1 Flash TTS** (Algenib voice — part of the new expressive voice library released this year) to produce documentary-register narration directly from the Storyteller's prose, with audio cached in Cloud Storage. Stories aren't just read — they're heard. NBC's Olympic editorial team employs voice talent and recording studios for narration. We used a Gemini API call.

**The brief asks for visual storytelling. We used Nano Banana Pro for every hero illustration.**
Each Broadcast page's hero is generated by **Nano Banana Pro** — Google's new stylized image-generation model. The Visualizer is a tool the Publish Gate calls, with prompts that mandate stylized illustration and forbid identifiable people. Where NBC's editorial team commissions illustrators, we used a Gemini API call.

**The brief asks for new uses of Gemini and Google Cloud. We orchestrated five Gemini models in concert.**
**Gemini 3.1 Pro** for the deliberation agents (Editor, Storyteller, Paralympic Equity Editor, Investigator, Publish Gate). **Gemini 3 Flash** for the four parallel Scouts (Cinderella, Comeback, Hometown, Echo). **Gemini 3.1 Flash-Lite** for utility calls and the NIL Layer's near-identification check. **Gemini Deep Research** as a tool the Investigator calls for high-priority leads. **Gemini 3.1 Flash TTS** for the Narrator's voice. **Gemini Google Search grounding** for real-time investigation across the open web. Each agent uses the model best suited to its cognition profile. None used as a single LLM in costume.

**The brief asks for conditional phrasing. We used the Publish Gate's Language Review sub-stage.**
The Publish Gate's Language Review sub-stage runs every Storyteller draft through Gemini 3.1 Pro for predictive-frame detection. *"Will result in,"* *"guarantees,"* *"predicts"* — drafts containing these are returned to the Storyteller, not softened and passed. Enforced before publication. Architecture, not editorial pass.

---

## Seven agents, distinct voices

The Storyteller's Room is genuinely multi-agent — not a single Gemini call in costume. Seven coordinated agents, each with a distinct voice on the Wire and each running under ADK:

- **Editor** — terse, decisive orchestrator. Gemini 3.1 Pro.
- **Scout Desk** — four sub-scouts (Cinderella, Comeback, Hometown, Echo) hunting different narrative shapes. Gemini 3 Flash.
- **Investigator** — precise, source-driven; calls Gemini Deep Research for high-priority leads. Gemini 3.1 Pro + Deep Research as a tool.
- **Paralympic Equity Editor** — blunt and disciplined. Veto power over publication. Gemini 3.1 Pro.
- **Storyteller** — literary, restrained. Documentary register, never sportscaster. Gemini 3.1 Pro, anchored on a calibration exemplar quoted verbatim in its prompt.
- **Narrator** — warm mid-tone broadcast voice. Gemini 3.1 Flash TTS (Algenib).
- **Publish Gate** — procedural and calm. Runs seven sub-stages of audit before publication, including the NIL Redaction Layer. Gemini 3.1 Pro plus a Python-enforced compliance guard.

---

## The platform — the Gemini Enterprise Agent Platform, end to end

**ADK** is the agent runtime. **Vertex AI** hosts the Gemini family. **Cloud Run** runs the agent service and the Next.js frontend, both `--min-instances=1` always-on. **BigQuery** holds the historical Team USA corpus, the candidate pool of place / program / pattern story units, and the athlete registry that powers the NIL Redaction Layer. **Firestore** carries live agent state, Wire events, audit logs, and the SSE handoff stream that powers the live agent-graph view. **Cloud Storage** holds generated hero illustrations (Nano Banana Pro) and narration audio (Flash TTS). **This is the year of agents, and the room is built on every piece of agentic infrastructure Google has shipped.**

---

## Data sources

US-scope only. Public Team USA roster pages, Olympedia entries filtered for Team USA athletes, public hometown press coverage and historical society archives, public school district and community records, public geographic and weather data. No private records. No finish times. No medal scores. No third-party logos other than Google Cloud. Internal analysis can query data tagged with athlete names; user-facing output never exposes individual identity.

---

## Findings

The Storyteller's Room produces editorial-grade stories at a marginal cost of less than ten cents each, with end-to-end latency under five minutes per investigation. The seven-agent architecture proved more than the sum of its parts: the Paralympic Equity Editor's interventions on the feed and on individual drafts are visible on the Wire as the system polices itself; the NIL Redaction Layer's audit trail shows the work of compliance rather than asserting it; the Storyteller, anchored on a calibration exemplar, generalizes structural patterns across radically different places without producing template prose.

Some stories in this index are calibration anchors — hand-curated to demonstrate the editorial standard the system is tuning toward. The remainder were published organically by the room as it ran during the build. The architecture is the constant; the voice tunes. We chose to keep both visible. Pretending the system arrived at literary standard fully-formed would be a lie about how AI systems become editorial systems.

---

## What this could become

NBC's Olympic editorial team profiles roughly fifty athletes per Games. The Storyteller's Room can investigate every hometown in America that has ever produced an Olympian or Paralympian — at a cost of less than ten cents per editorial-grade story. The same architecture could run alongside USOPC, NCAA athletics, and league offices: finding the places the existing media apparatus misses, producing them at broadcast quality, giving communities the recognition their representation has earned.

Different corpus. Different scouts. Same room.

---

Every Team USA athlete comes from somewhere. We built a place where any fan can find them.
