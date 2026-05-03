# What is The Storyteller's Room

The Storyteller's Room is a live AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians. Olympic and Paralympic representation get equal weight, not as a feature, but as a property of the system. Individual athlete identity gets equal weight as a property of the system too, but in the opposite direction — protected by architecture, never exposed.

Not a dashboard. Not a chatbot. Not "Olympic data analytics with AI sprinkled on top." A coordinated team of seven Gemini agents — Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate — that operates continuously, scouts public data for emotionally resonant story units (places, programs, patterns), fact-checks every claim, enforces parity, redacts individual identification, and produces narrated Olympic-broadcast-style story pages in real time. The user does not run queries. The user watches a newsroom work.

---

## The idea

Every Olympic Games, NBC's editorial team produces dozens of athlete stories that change how Americans feel about sport. The stories almost always start in the same place: a hometown. A small town in Iowa. A neighborhood in Detroit. A high school gym in rural Oregon. Reporters fly out, interview the parents and the coach, walk through the local landscape, then narrate the journey in voiceover — *"This is where it began."* That hometown moment is the emotional doorway into the entire Games.

NBC has roughly 100 producers, editors, and field crews. Team USA has 600+ athletes across Olympic and Paralympic disciplines. The math doesn't work. NBC covers maybe 50 athletes deeply. The other 550 — and the hundreds of *places* behind them, the regional sport ecosystems, the community programs, the geographic patterns nobody tracks — never get the broadcast treatment. Their stories exist in fragments: hometown papers, World Championship archives, Team USA roster pages, public school records.

The insight isn't "AI can write articles." It's that the right unit of AI-native sports storytelling isn't a single athlete profile or a dashboard. It's a *room*. A coordinated agent system that does what NBC's editorial process does — scouting, investigating, fact-checking, narrating — but at the scale and pace AI makes possible. And critically, the room tells a different kind of story: not *about the famous athlete*, but *about the place that produced them, and the place producing the next ones nobody's heard of yet*.

The Olympics are not the scoreboard. The Olympics are the stories. And the stories don't begin at the medal stand. They begin in a town. This room exists to find those towns.

---

## How it works

When you open The Storyteller's Room, you don't see a welcome screen. You see The Wire — a live editorial feed, scrolling in real time, ambient. Scouts are surfacing leads. The Investigator is pulling sources. The Paralympic Equity Editor just intervened to push a wheelchair rugby pipeline story to the top of the queue. The Wire moves at four to eight seconds per event, the deliberate cadence of a working newsroom, not a chat app.

You can ask the room a question — "Find me a Team USA hometown story I've never heard before" — and watch a fresh investigation begin. Or you can sit back. The room is autonomous. It works whether you're watching or not. Stories surface. Drafts get rejected. Confidence scores climb and fall. Sometimes a story dies. Sometimes three different scouts independently converge on the same place and the room flags High Narrative Density.

When a story finishes, it appears at the top of the Stack — a recently-published feed below the Wire. Click it.

The Wire fades. The screen darkens. A hero illustration begins to fade in with slow Ken Burns motion — a stylized landscape, a small-town main street at dusk, an empty high school gym, a community track. Never a person. The Narrator's breath is audible before the first word. The headline arrives, character by character: *"The Town Behind the Starting Line."* A music bed enters under the first sentence. This is The Broadcast — the produced story page where the room performs. The Narrator reads in a warm, mid-tone, documentary register. The current sentence highlights as it's spoken. A stylized hometown map zooms when the place name lands. A historical echo panel slides in when an era reference arrives. It is 90 seconds of Olympic-broadcast production value, generated end-to-end by the room, telling the story of a place that has quietly produced eight Olympians and Paralympians over five decades.

When the narration ends, the Evidence Drawer is one click away. Seven sub-stages of the Publish Gate's audit log — Fact Check, Source Review, Parity Review, **NIL Redaction Review**, Safety Review, Language Review, Visual Review — show every claim verified, every source cited, every individual reference redacted, every revision the Equity Editor required. Trust is not a promise. Trust is a receipt.

Then back to The Wire. The room is finding the next one.

---

## The operating model: how the agents work

The room's seven agents are not steps in a pipeline. They are a coordinated cast, each with its own goal, voice, and tool surface. They write to each other through Firestore and BigQuery, hand off through events on the Wire, and operate continuously rather than on user request.

**The Editor** is the orchestrator. It decomposes user prompts into investigation assignments, manages the queue, accepts or overrides Paralympic Equity Editor recommendations, and decides what gets published. Its voice on the Wire is terse and decisive. *"Going with Mount Pleasant. Investigator, 90 seconds."*

**The Scout Desk** is a swarm of four sub-scouts — Cinderella, Comeback, Hometown, Echo — each obsessed with a different narrative shape, all looking for *story units* (places, programs, patterns) rather than individual athletes. Cinderella looks for places and programs that punched above their weight. Comeback looks for regional pipelines that disappeared and returned. Hometown looks for towns whose representation in Team USA is disproportionate to their size. Echo looks for modern patterns that rhyme with iconic Olympic eras (never iconic individuals — *"this echoes a 1960 Rome sprint-era pattern,"* never *"this rhymes with Wilma Rudolph"*). The scouts run in parallel against the candidate pool and Gemini's grounded search. They write Lead Reports with confidence scores that update visibly as evidence accumulates. *"Confidence 0.62 → 0.74. The Mount Pleasant pipeline is real."* The Scout Desk's voice is the messiest on the Wire — slightly skeptical, building or losing belief in real time.

**The Investigator** takes a Lead Report and turns it into a full Investigation Packet: sources, evidence, narrative spine, geography, historical context, trend signals — all about the place, program, or pattern. It calls Gemini's grounded search for recent news about regions, BigQuery for historical Team USA representation by hometown, and Gemini Deep Research for anchor stories that need multi-source synthesis. Its voice is precise and source-driven. *"Pulling sources. Quad-City Times has hometown coverage going back to 1996. Eight Olympians and Paralympians from this town since 1976. Olympedia confirms the pattern."*

**The Paralympic Equity Editor** is the impact lever, and it has veto power. It operates at three levels: feed-level (if the last four stories were Olympic-heavy, it promotes a Paralympic-anchored place to top of queue), story-level (if a Storyteller draft has shallow Paralympic context for a place's representation, it returns the draft for revision), and safety-level (if a draft frames Paralympic athletes from a place as inspiration porn rather than as athletes who came from a community, it blocks publication). Its voice is blunt and disciplined. *"Feed drift detected. Last four published places are Olympic-heavy. Promoting a Paralympic pipeline lead next."* The room policing itself is visible to the user. That visibility is the product.

**The Storyteller** writes the final 400–700 word narrative from the Investigation Packet. The narrative is about the place, program, or pattern — never an individual. Athletes appear as counts, as roles, as parts of a community. Names never appear. Its voice is literary and restrained — documentary journalism, not sportscaster hype. It does not use *inspirational*, *hero*, *overcame*, *warrior*, *wheelchair-bound*, or any of the standard sports-media tropes. It does not use *former Olympian* or *past Olympian* (per restricted terminology). It trusts the reader. After drafting, its output goes to the Equity Editor for review, then to the Publish Gate.

**The Publish Gate** runs seven sub-stages on every story before it ships: Fact Check (every claim verified against the Investigation Packet), Source Review (sources counted, citations attached), Parity Review (Equity Editor sign-off confirmed), **NIL Redaction Review** (the named architectural feature — see below), Safety Review (no invented quotes, no private medical information), Language Review (conditional phrasing where required, restricted terminology check), Visual Review (no photorealistic likenesses, no Olympic rings, no Agitos, no protected marks). Its voice is procedural and calm. *"Fourteen claims checked. Two removed. One softened. Four individual references reviewed by NIL Redaction Layer — two aggregated, two redacted. Cleared."* The Publish Gate calls the Visualizer (Nano Banana Pro for hero images, Nano Banana 2 for utility graphics) as a tool. The Visualizer is not a separate agent.

**The Narrator** converts the published story into broadcast voice. It calls Gemini 3.1 Flash TTS with two distinct voice configurations — the Broadcast Narrator (warm, documentary, the emotional spine of the Broadcast page) and the Wire Dispatcher (clipped, recessed, control-room energy for ambient Wire narration). The Narrator returns word-level timing maps that the frontend uses to choreograph sentence highlighting and panel reveals.

These seven agents are the entire visible cast. The judges see seven roles. They do not see eleven. When the room wants to add an Adversity Scout, a Historian, a Geographer, or a Compliance Editor, those impulses fold into existing agents as tools or sub-stages, not as new visible roles. Seven is the upper limit of what a human can track in a three-minute demo.

---

## The parity architecture

Every product that mentions Paralympic representation treats it as a feature: a toggle, a tab, a card on the dashboard. The Storyteller's Room treats it as a property of the system.

The Paralympic Equity Editor is not a prompt instruction. It is a dedicated agent with structural authority. It has veto power over publication. It can return drafts. It can promote leads. It operates at three levels — feed, story, safety — and writes its decisions to the Publish Gate's audit log where they are visible to the user.

This is the difference between "we tried" and "the system itself cares." The Olympic/Paralympic balance of the feed is not a thing the team remembered to monitor. It is a thing an agent is paid to enforce. When the feed drifts Olympic-heavy, an intervention happens. When a Storyteller draft has eight sources of Olympic context for a place and two sources of Paralympic context, the draft does not ship. When a draft uses Paralympic representation in a place as inspiration porn, the draft is blocked.

These interventions are visible on the Wire. They are the most visually distinctive events in the room — they arrive rather than stream, they pause the surrounding Wire activity, they carry the Agitos red color signature. A user watching the Wire for thirty seconds will see at least one Equity Editor intervention. The user does not need to be told that parity is a system property. They watch it happen.

This is what wins the Impact axis. Not a dashboard chart of representation ratios. The visible behavior of an agent whose only job is enforcement.

---

## The NIL Redaction Layer

The Paralympic Equity Editor's twin. Where parity is the impact lever, NIL safety is the trust lever — and like parity, we made it architecture rather than content review.

The NIL Redaction Layer is a named sub-stage of the Publish Gate. Sub-stage 4 of 7. Its job is structural: maintain a registry of all athlete names that appear in the internal corpus, and scan every text artifact bound for a user-facing surface (Wire, Broadcast, demo) before it emits. It detects three classes of individual identification: direct name matches against the registry, near-identifications (fact combinations that uniquely identify one person — sport plus hometown plus event plus year often equals a single athlete), and small-aggregate identifications (lists of three or four named athletes from a single place).

It takes one of three actions. *Pass* if no individual references exist. *Aggregate* if individual references can be replaced with counts ("eight Olympians" instead of a list of names). *Return* to the Storyteller if redaction would damage narrative coherence and the draft needs rewriting at the source.

The Layer's work is logged in structured form: *"Four individual references reviewed. Two aggregated. Two redacted. Cleared."* When the Evidence Drawer opens during the demo's trust-layer beat, those numbers are visible alongside the Fact Check counts and the Equity Editor's parity sign-off.

The implementation rule is the same as the implementation rule for the parity work: **we do not trust the LLM to enforce its own constraints**. The redaction logic lives in Python, queries BigQuery for the athlete registry, and operates on the Storyteller's text output before that output ever reaches the Broadcast renderer or the Wire stream. The agent doesn't have to remember the rule. The system enforces it structurally.

This matters because the hackathon's NIL prohibition is one of three immediate-disqualification triggers. We did not bolt on a content review. We built an architectural protection. The constraint is the credibility flex.

---

## The architecture philosophy

The Storyteller's Room follows a set of principles captured in the project Constitution. They govern every engineering, research, and design decision.

**Emotion is the metric.** The judging rubric is 40% Impact, 30% Technical Depth, 30% Presentation Quality. All three depend on whether a human watching a three-minute video feels something. Every decision passes through a single filter: does this serve one of the five demo moments? If not, cut it.

**Place over Person.** The room's protagonists are places, programs, and patterns. Athletes are protected by architecture, not by content review. This is both the legal requirement under the hackathon's NIL rule and the creative discipline that makes the storytelling more original — most fan coverage starts with famous athletes; we start one layer deeper, with the communities that produce them.

**Show the labor, hide the lookup.** The Buddy Rich principle. When the system does something easy (a database query, a Gemini call), it is wrapped in deliberation — a Scout scoring leads, weighing evidence, rejecting four candidates to surface a fifth. When the system does something hard (multi-agent orchestration, parity enforcement, real-time grounding, NIL redaction), it is presented cleanly — a calm Wire that simply flows. Hard things look easy. Easy things look hard. The judge cannot tell which is which. They only know they are watching something they have not seen before.

**Voice signatures are sacred.** Each of the seven agents speaks differently. The Editor is terse. Cinderella Scout is hesitant. Echo Scout is cryptic. Hometown Scout is place-textural. The Investigator is source-driven. The Equity Editor is blunt. The Storyteller is literary. The Narrator is paced. The Publish Gate is procedural. If two agents sound alike on the Wire, the room has died.

**Documentary, not sportscaster.** The Storyteller and Narrator do not use *inspirational*, *hero*, *overcame*, *despite*, *warrior*, *fighter*, *wheelchair-bound*, *suffers from*, *former Olympian*, or *past Olympian*. They use place names, sensory details, dates, and public quotes from documented sources (only when those sources name non-athletes — coaches, town officials, historians). The voice is *The Daily*, not stadium PA. *30 for 30*, not pre-game hype.

**Stylized, never photorealistic.** Every generated image is editorial illustration in the Sports Illustrated tradition. Hero images depict places, landscapes, communities, facilities, equipment, silhouettes — never identifiable people. NIL safety is enforced at the prompt layer (Nano Banana prompts demand stylization and place-subjects) and re-enforced at the publication layer (Visual Review can reject and regenerate). Compliance is architecture, not afterthought.

**Honest production, not faked liveness.** Every Wire event has a `mode` field: `live | replay | published`. Cached content is labeled. Replayed investigations are labeled. The single live investigation triggered during the demo runs at four times compressed time, with the honest label *"Live investigation — playback at 4×."* Olympic broadcasts run produced packages constantly. The Storyteller's Room does too, and says so. Pre-recorded is not broken. Faked-live is broken.

**Markdown and prompts are the system.** Agent behavior lives in prompts and markdown files. To change what an agent does, edit the prompt — not the Python. The Wire vocabulary library is a JSON file. The Storyteller's forbidden words list is in the Storyteller's system prompt. The athlete-name registry is a versioned BigQuery table with a JSON snapshot. None of this is conditional logic. If behavior cannot be changed without redeploying code, the design is wrong.

---

## What's actually built

The Storyteller's Room is being built for the Team USA × Google Cloud Hackathon. Submission deadline: May 11, 2026. Submission category: **Challenge 2 — The Hometown Success Engine**. Prize structure: $15,000 grand prize, $8,000 per challenge, plus Google Cloud credits. The room is being built solo, by Charlie Reagan, using Claude Code as the primary engineering agent.

**The technology stack is locked.** Gemini 3.1 Pro powers the Editor, Storyteller, Equity Editor, Investigator, and Publish Gate. Gemini 3 Flash powers the four parallel scouts. Gemini 3.1 Flash-Lite handles utility calls and Wire vocabulary generation. Gemini Deep Research is a tool the Investigator calls for anchor stories. Nano Banana Pro generates the cinematic hero illustrations on the Broadcast page (places, landscapes, communities, never people). Nano Banana 2 generates utility visuals. Gemini 3.1 Flash TTS generates both the Broadcast Narrator voice and the Wire Dispatcher voice. The agent platform is the Google Agent Development Kit (ADK) running on Cloud Run. BigQuery holds the historical Team USA corpus, the candidate pool of story units, and the athlete-name registry that powers the NIL Redaction Layer. Firestore holds live agent state, Wire events, and audit logs. Cloud Storage holds generated images and audio. Gemini's built-in Google Search grounding handles all real-time scouting.

**The build runs eleven days.** Days 1–2 are foundation: repo with Apache 2.0 license, GCP project setup, ADK environment, Next.js skeleton with SSE plumbing, BigQuery schema deployed, athlete-name registry loaded. Days 3–5 build the agent core: Editor, Investigator, all four sub-scouts, Wire vocabulary, candidate pool writes/reads, High Narrative Density detection. Days 6–7 add the integrity and production layer: Equity Editor with feed-drift and draft-review behavior, Storyteller, Publish Gate with all seven sub-stages including NIL Redaction Layer, Visualizer tool calls, Narrator with both voice configs. Day 8 ships the Floor (D3 agent graph with particle handoffs) and the Broadcast (curtain rise, synchronized choreography, sentence highlighting). Day 9 runs the system continuously, lets it produce a real corpus of place/program/pattern stories, and selects the demo's anchor story from organic discoveries. Day 10 is the demo video. Day 11 is submission, with a buffer for the things that always go wrong at the buzzer.

**The demo storyboard is the spine.** The three-minute video opens on a black screen with a single line of voiceover: *"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds those places."* Then the Wire, alive, with an Equity Editor intervention visible in its recent history. Then The Floor, showing real tool calls and agent handoffs. Then a click into a published story that the Equity Editor caused — a place, not a person. Then ninety seconds of pure Broadcast — narration about a hometown, choreography, hometown panel, historical echo, music bed, no presenter voice. Then the Evidence Drawer to prove the trust layer, with the NIL Redaction Layer's audit visible alongside the Fact Check and Parity Review. Then back to the Wire. *"Right now, the room is finding the next one."* Hard cut.

The system is being built to serve five demo moments: the room is alive, the agents are truly agentic, the Equity Editor caused the anchor story, the Broadcast lands emotionally, the Publish Gate (with the NIL Redaction Layer) proves trust. Every line of code passes that filter.

---

## What this could become

The hackathon submission is the proof of concept. The bigger thesis is what AI-native sports storytelling looks like at scale.

NBC's Olympic editorial operation produces a finite number of stories per Games. The constraint is not creativity. The constraint is staff hours, camera crews, production capacity. AI-native storytelling has different constraints. It can investigate every hometown in America that has ever produced an Olympian or Paralympian. It can produce stories continuously across the four-year cycle, not just during the two weeks of the Games. It can find the small-town pipeline in October that wouldn't get a profile until July, if ever. It can give Paralympic-producing places the same depth of treatment as Olympic-producing places, not because someone remembered to, but because the system structurally requires it.

The Storyteller's Room as a hackathon submission is one room finding hometown stories for one country's Olympic team. The Storyteller's Room as a product is an editorial layer that runs alongside every major sporting body — USOPC, USA Swimming, USA Track & Field, US Soccer, the WNBA, NCAA athletics — finding the *places* the existing media apparatus misses, producing them at broadcast quality, and giving communities the recognition their representation has earned. The same architecture. Different corpus. Different scouts. Same room.

For the Games specifically, the room is also a tool the official broadcasters could use. NBC's editorial team identifies fifty athletes to profile. The room identifies the hundreds of places those athletes came from — and the hundreds of other places quietly producing the next generation — and produces draft packages NBC's team can review, refine, and air. The room is not the replacement for human Olympic storytelling. It is the discovery engine that makes human storytelling reach further than it ever has, while protecting individual athlete identity by architecture.

That is the post-hackathon vision. Right now, in the present tense, what matters is eleven days, seven agents, one anchor hometown story, and a three-minute video that makes a Google judge feel something they did not expect to feel — about a place they had never heard of.

---

## Who's behind this

The Storyteller's Room is built by Charlie Reagan, the operator behind Neptune AI. Solo founder. AI-native engineering throughout. Based in Falling Waters, West Virginia. The same agentic-architecture principles that govern Neptune's persistent agent fleet govern this room: let the agents cook, markdown is the system, governance constrains without orchestrating, design for models that don't exist yet.

The Storyteller's Room is not a product yet. It is a submission, a demo, and a thesis. If the thesis lands with the judges, the post-hackathon path opens. If it doesn't, the architecture is portable, the Constitution is reusable, and the lessons compound into the next room.

Either way, the places that produce Olympians deserve to be known. This is one way to find them.
