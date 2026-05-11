# The Storyteller's Room

Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling.

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

## Seven agents, five Gemini models in concert

The Storyteller's Room is genuinely multi-agent — not a single Gemini call in costume. Seven coordinated agents, each with a distinct voice on the Wire:

- **Editor** — terse, decisive orchestrator.
- **Scout Desk** — four sub-scouts (Cinderella, Comeback, Hometown, Echo) hunting different narrative shapes.
- **Investigator** — precise, source-driven; calls Gemini Deep Research for high-priority leads.
- **Paralympic Equity Editor** — blunt and disciplined. Has veto power over publication.
- **Storyteller** — literary, restrained. Documentary register, never sportscaster.
- **Narrator** — warm mid-tone broadcast voice via Gemini 3.1 Flash TTS.
- **Publish Gate** — procedural and calm. Runs seven sub-stages of audit before publication, including the NIL Redaction Layer.

**Five Gemini models in concert:** Gemini 3.1 Pro for deliberation (Editor, Storyteller, Equity Editor, Investigator, Publish Gate), Gemini 3 Flash for the four parallel Scouts, Gemini 3.1 Flash-Lite for utility calls, Gemini Deep Research as an Investigator tool, and Gemini 3.1 Flash TTS for the Narrator. Each agent uses the model best suited to its cognition speed and depth. Hero illustrations are generated with Nano Banana Pro — always a stylized place, landscape, facility, or community, never a person.

---

## Compliance as architecture

The hackathon's prohibition on athlete name, image, and likeness is strict. The Storyteller's Room enforces it not as content-review afterthought but as a named architectural feature: the **NIL Redaction Layer**, sub-stage 4 of the Publish Gate. A Python module between the Storyteller's output and any user-facing surface, it maintains a registry of all athletes appearing in the source corpus, scans every text artifact for direct names, near-identifications, and small-aggregate identifications, and either passes, aggregates (*"eight Olympians"* instead of a list), or returns drafts to the Storyteller for revision. Every Broadcast page's audit footer shows the Layer's work in concrete numbers.

The same architectural pattern enforces parity: the Paralympic Equity Editor is an agent with structural authority, not a prompt instruction. The same pattern enforces editorial standard: a calibration anchor story is quoted verbatim in the Storyteller's prompt as the bar against which all output is measured.

The constraint became the credibility flex.

---

## Built on Google Cloud, end to end

- **Vertex AI** for the Gemini family.
- **Cloud Run** for the agent runtime and the Next.js frontend, both `--min-instances=1` always-on.
- **BigQuery** for the historical Team USA corpus, the candidate pool of place / program / pattern story units, and the athlete registry that powers the NIL Redaction Layer.
- **Firestore** for live agent state, Wire events, audit logs, and the SSE handoff stream that powers the live agent-graph view.
- **Cloud Storage** for generated hero illustrations and narration audio.
- **Gemini Google Search grounding** for real-time investigation.
- **Google Agent Development Kit (ADK)** as the agent runtime framework.

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
