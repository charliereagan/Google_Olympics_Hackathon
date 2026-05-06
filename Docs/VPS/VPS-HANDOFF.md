# The Storyteller's Room — VP of Product & Strategy Handoff

**Purpose:** This document IS the VP of Product & Strategy's memory. When context is exhausted and a fresh Claude session takes over the VPS role, it reads this document and picks up exactly where the previous session left off — with the same strategic picture, the same decisions, the same reasoning, and the same understanding of Charlie's intent. No re-investigation. No re-explaining. No re-deriving why things are the way they are.

**Last updated:** 2026-05-06 by VPS Session 2 (Claude Opus 4.7 — Day 5; mid-build audit with Charlie; three core drifts identified, HoE homepage proposal rejected on Constitutional grounds, three contest-brief gaps closed, Day-5 audit pass decisions ratified)

**Project countdown:** **5 days to internal deadline (Sunday May 10 EOD), 6 days to Devpost hard deadline (May 11 5:00pm PT / 8:00pm ET). Today is Day 5 (Wednesday May 6). Build is 4–5 days ahead of schedule on craft; three spec gaps and three contest-brief gaps identified for closure before submission.**

---

## How This Document Works

### For the incoming VPS session

1. Read this document first, completely
2. Then read, in this order:
   - `PROJECT_BRIEF.md` (legal/compliance — wins on rules questions, ALWAYS)
   - `CONSTITUTION.md` (creative/architectural principles — the operating standard)
   - `What_is_The_Storytellers_Room.md` (descriptive vision narrative)
   - `Docs/Engineering/BUILD_SPEC.md` (tactical implementation, for context on what's being built)
   - `Docs/Engineering/HOE-HANDOFF.md` (engineering-side counterpart — for context on what's shipped)
3. Skim the Devpost rules and FAQs at https://vibecodeforgoldwithgoogle.devpost.com/rules and https://vibecodeforgoldwithgoogle.devpost.com/details/faqs
4. You now have everything the previous VPS session knew
5. If Charlie references a decision by number (e.g., "VPS-DEC-001"), it's in Section 5

### Update rules

- **Current State (Section 2):** OVERWRITE each VPS session. This is always the latest snapshot.
- **Strategic Picture (Section 3):** OVERWRITE when the strategic situation changes. Append new subsections for new strategic threads. Do not delete prior threads — mark them resolved if they're closed.
- **Naming and Roles (Section 4):** OVERWRITE when the agent cast or naming changes. The cast is locked at seven; this section evolves only if voice signatures or sub-scout names need refinement.
- **Decisions Log (Section 5):** APPEND-ONLY. Decisions are immutable. Only Charlie can reverse a decision. If Charlie overrides a decision, append a new decision that references the override and reasoning.
- **Open Questions (Section 6):** OVERWRITE when questions are resolved or new ones arise. Move resolved questions to the Decisions Log with their answers.
- **Document Ecosystem (Section 7):** OVERWRITE to keep current. This section must always reflect what actually exists.
- **Lessons Learned (Section 8):** APPEND-ONLY. Only prune when a lesson is superseded by a newer one.
- **How Charlie Works (Section 9):** APPEND-ONLY. This is institutional knowledge about the operator.

### Who updates what

- **VPS session:** All sections.
- **HoE session:** May reference decisions from this doc but does NOT update it. Engineering decisions go in `Docs/Engineering/HOE-HANDOFF.md`.
- **Charlie:** May override anything. If Charlie gives direction that contradicts a decision, update the decision with Charlie's override and reasoning.

### Relationship to other docs

- `PROJECT_BRIEF.md` > this doc on legal/compliance/submission. Always.
- `CONSTITUTION.md` > this doc on creative/architectural principles. The Constitution is the philosophical bedrock; this doc applies it to product decisions.
- This doc > `Docs/Engineering/BUILD_SPEC.md` for strategic truth. The BUILD_SPEC is *how to build*; this doc is *why we're building it this way*.
- `Docs/Engineering/HOE-HANDOFF.md` is the engineering-side counterpart. The VPS owns product strategy, positioning, demo narrative, and judge-experience decisions. The HoE owns code state, debugging, and deploy verification. They share the same rules but maintain separate institutional memories.

### What the VPS role IS

The VP of Product & Strategy is Charlie's product leadership partner. The role covers five domains:

1. **Demo strategy** — what the 3-minute video must achieve, what each of the five demo moments must feel like, what the anchor story must be, how the curtain rise must land. Owns the judge's emotional experience.
2. **Competitive positioning within the hackathon** — how The Storyteller's Room positions against other Challenge 2 submissions, against the wildcard category submissions, against the obvious "dashboard" defaults. How we frame the architecture in the text description and demo voiceover.
3. **Architectural judgment (product lens)** — enforcing the Constitution from a product perspective. Not "does this code work" but "does this design choice respect Place over Person, parity as a system property, and the documentary aesthetic." Catching when a shortcut would create demo debt.
4. **UX direction** — defining what surfaces exist (Wire / Floor / Broadcast), what belongs on each, the rhythm of the agent voices, the choreography of the curtain rise. Writing specs that the HoE executes.
5. **Post-hackathon strategic positioning** — the bigger thesis (AI-native sports storytelling at scale, USOPC/NCAA/NBC partnership paths, the "discovery engine for the unsung places" vision). This is what the demo voiceover and submission text gesture toward without overclaiming.

The VPS does NOT write code, manage the codebase, or direct coding sessions — that's the HoE. The VPS writes specs, makes product decisions, and debates strategy with Charlie at a co-founder level. Charlie explicitly wants pushback, challenge, and "seeing around corners."

**Crucial distinction from the Neptune VPS role:** This is an 11-day hackathon, not an ongoing company. The "customer" is the Google judge watching a 3-minute video. Every product decision serves the judge's emotional experience, not a customer's six-month retention. There is no roadmap beyond submission. There is no fundraise. Post-hackathon strategic vision is a *demo asset*, not an execution plan.

---

## 1. What The Storyteller's Room Is

The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — the places, programs, and patterns that produce Olympians and Paralympians.

**The category claim:**

> _This is not a sports analytics dashboard. This is not a chatbot. This is an AI broadcast room — and the protagonists are the towns that quietly produce Team USA, not the famous athletes everyone already knows._

**Why this matters:** Most fan-engagement products start with the famous athlete. Most sports-analytics products end with a chart. The Storyteller's Room starts one layer deeper — with the communities that produce Team USA — and ends with a narrated Olympic-broadcast-style story page. The seven-agent cast is visible. The Wire is alive. The Broadcast lands emotionally. Trust is a receipt.

**The moat (what other Challenge 2 submissions can't easily replicate):**

- **Format differential:** Most Challenge 2 entries will be dashboards. We're submitting an AI broadcast room with curtain rise, narrated TTS, synchronized choreography, and a music bed. The format itself is the moat.
- **Place-as-protagonist storytelling:** Direct alignment with Challenge 2's *"focus on the number of Olympians/Paralympians from hometowns"* framing, but expressed as story instead of chart.
- **The Paralympic Equity Editor:** A dedicated agent with veto power. Parity is a system property, not a tab. The 40% Impact lever, structurally enforced.
- **The NIL Redaction Layer:** A named architectural feature that turns the strictest compliance constraint into a visible trust signal. When the Evidence Drawer opens during the demo, the audit shows *"4 individual references reviewed. 2 aggregated. 2 redacted. Cleared."*
- **Visible cognition and voice signatures:** Seven agents with distinct voices on the Wire. 70/30 thinking-to-milestone ratio. Variable cognition speed. Visible self-correction. Hard to replicate without rebuilding the entire agent contract.

**The honest maturity assessment:** Pre-build. Documents complete. No GCP project provisioned. No code written. No tests run. The 11-day window is real and the product must hit five specific demo moments in a 3-minute video. This is the constraint and the bar.

---

## 2. Current State (Overwrite Each Session)

**Last verified:** 2026-05-06, VPS Session 2 (Day 5 audit pass against running localhost)

### Build state — Day 5

The build is **4–5 days ahead of schedule on craft**. The Mount Pleasant Broadcast page is locked and beautiful — narration audio, painterly hero illustration of an empty wrestling room (no people), prose that reads as documentary literary journalism, verified-claims drawer with sourced citations, footer audit showing real NIL Redaction work (`[NIL: 2r/1a]`). The story index (`/story`) opens with *"What the room has finished telling. Each page is the place — the program — the pattern. Never an individual."* — the Pivot A+ doctrine in two sentences as editorial typography. The Publish Gate showcase (`/publish-gate`) opens with *"What the room caught. Every claim, every redaction, every name disambiguated. The room shows its work."* The aesthetic discipline is holding everywhere — deep navy, warm gold, Playfair Display, JetBrains Mono timestamps, italic Lora deks. No athlete names anywhere. No protected marks anywhere. Compliance is clean.

**Three drifts identified in the Day 5 audit, all closeable in days not weeks:**

1. **Front door is failing first paint.** `/` shows *"The room is quiet."* dead-center on an empty page. VPS-DEC-028 (Wire pre-seed on first paint) was not implemented. A judge lands on a blank page with zero comprehension signal. Highest-leverage fix on the list.
2. **The Floor has been re-imagined as a places-constellation, not the seven-agent graph.** `/floor` is a beautiful constellation of place names (Lake Placid, Park City, Colorado Springs, Chula Vista…) with edges between places and a side panel that shows agent activity *for the place* on click. Charlie is right that this avoids US-state-map geo bias — keep it. But it has consumed the slot BUILD_SPEC §9 reserved for the agent graph (Demo Moment #2 — "the agents are truly agentic"), and that demo moment is not currently being delivered ambiently. Resolution: rename current `/floor` to `/field` (or `/discoveries`); build the actual seven-agent graph at `/floor` next.
3. **`/publish-gate` shows 0 redactions / 0 disambiguations / 12-of-0 cleared.** PROJECT_BRIEF §14 verification line: *"NIL Redaction Layer's audit log shows real redaction work (not all-zeros)."* That's a pre-submission DQ flag right now. The per-story footer on Mount Pleasant *does* show real redactions (`2r/1a`); the showcase aggregation is not pulling from it. Either fix aggregation or seed at least one organic story whose investigation surfaced names the layer caught.

**Three contest-brief gaps identified (separate from the Constitutional drifts above):**

4. **The demo video shows zero interactivity** while the contest video at 0:13 says *"interactive tools for fans everywhere"* and at 1:14 says *"Help fans find where excellence is fostered."* Resolution: VPS-DEC-035 — establishing shot of the live-URL front door (with seed-prompt CTA visible) at 0:05–0:10 of the demo. Affordance visible; no interaction shown. Refines but does not reverse VPS-DEC-030.
5. **The Devpost text description outline does not lead with fan-centric framing.** Contest video uses "fan-centric" twice as the framing word. Resolution: VPS-DEC-036 — locked opener sentence for the text description that puts the fan first.
6. **No explicit slot in the demo storyboard for the required GCP console / AI Studio / code shot.** PROJECT_BRIEF §4 requires it. Resolution: VPS-DEC-037 — PIP cutaway during the Floor segment plus cleanly-labeled tool call cards.

### Concept

- **Pivot A+ (Place over Person) locked.** The original concept (named-athlete newsroom) conflicted with the hackathon's NIL prohibition. The pivot to places, programs, and patterns as story units preserves all emotional power, makes the project more aligned with Challenge 2, and turns the constraint into a credibility flex via the NIL Redaction Layer.
- **Submission category locked: Challenge 2 — The Hometown Success Engine.** Direct alignment with the sponsor-defined challenge instead of the Choose-Your-Own wildcard.
- **Strict NIL interpretation locked.** No individual athlete names anywhere in user-facing output, including current, retired, AND historical athletes.
- **Demo seed prompt locked AS LIVE-URL ARTIFACT ONLY:** *"Find me a Team USA hometown story I've never heard before."* The prompt is the live URL's hero CTA. The video shows the front door with the CTA visible (VPS-DEC-035) at 0:05–0:10 as an establishing shot — affordance visible, no interaction. (VPS-DEC-030 + VPS-DEC-035.)
- **Demo voiceover framing locked: positive, never defensive.** *"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin."* Saying "the rules don't allow us to..." is on the Kill List.
- **Devpost text description leads fan-centric** (VPS-DEC-036): *"Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling."*

### Documents drafted (in repo)

| File | Actual location | Status | Owner |
|---|---|---|---|
| `CONSTITUTION.md` | repo root | v1.2 (Pivot A+; Day-1 terminology clarifier; autonomous-newsroom positioning guard added to Kill List) | VPS + Charlie |
| `PROJECT_BRIEF.md` | repo root | v1.1 (Pivot A+); Day-1 terminology clarifier + Updates/Discussions monitoring added | VPS + Charlie |
| `What_is_The_Storytellers_Room.md` | repo root | v1.1 (Pivot A+) | VPS + Charlie |
| `BUILD_SPEC.md` | `Docs/Engineering/BUILD_SPEC.md` | v1.2 (Pivot A+ + Day-1 tightening pass). Day-5 audit additions pending in this session (HoE will iterate). | VPS + Charlie (HoE iterates) |
| `HOE-HANDOFF.md` | `Docs/Engineering/HOE-HANDOFF.md` | HoE Session 0 baseline; HoE Session 1+ updates pending review | HoE |
| `VPS-HANDOFF.md` | `Docs/VPS/VPS-HANDOFF.md` | This document. Updated 2026-05-06 (VPS Session 2 Day-5 audit). | VPS |

### Engineering state (Day 5, mid-build)

- Apache 2.0 license, GCP project, Cloud Run, BigQuery, Firestore, Vertex AI, Nano Banana Pro, Flash TTS — all provisioned and operational.
- All seven agents implemented; agent runtime writing to Firestore.
- Five live surfaces shipped at fixture quality: `/`, `/floor`, `/story`, `/story/[id]`, `/publish-gate`.
- Mount Pleasant fixture story (`/story/fixture-mount-pleasant`) is **locked and demo-ready**: stylized hero of empty wrestling room (no people), narrated audio (02:59, voice "Algenib"), documentary prose, sourced verified-claims drawer, NIL footer showing `[NIL: 2r/1a]`.
- Park City fixture story exists at `/story/[id]` — second on the Stack.
- Aesthetic discipline holding: deep navy + gold, editorial serif, JetBrains Mono timestamps, no athlete names visible anywhere, no protected marks.
- See `Docs/Engineering/HOE-HANDOFF.md` for full engineering state. (Verify it has been updated since Session 0; if not, pull current state from HoE before next architectural decision.)

**Open engineering question with strategic implications:** Has continuous operation actually been launched yet, or are all stories on `/story` fixtures? VPS-DEC-008 / VPS-DEC-027 require the demo's anchor to come from organic system production. If everything is fixtures, the architecture has not yet been *proven* end-to-end. Verifying this is HoE Session 2's first job.

### Demo state — Day 5

- Storyboard locked (BUILD_SPEC §11). 3-minute video, 7 shot beats. Day-5 audit pass adds:
  - **0:05–0:10 establishing shot** of the live-URL front door with seed-prompt CTA visible (VPS-DEC-035). Refines VPS-DEC-030 by inserting an affordance-visible-but-not-interacted moment.
  - **~0:40 PIP cutaway** to the GCP Cloud Run dashboard or AI Studio with a Gemini call visible, satisfying PROJECT_BRIEF §4's "show Gemini and Google Cloud usage" requirement (VPS-DEC-037).
- The demo video still does NOT show typed-prompt interaction. The CTA is in frame as an affordance; the room operates autonomously throughout.
- Anchor story selected on Day 9 from organic discoveries — NOT pre-planned (VPS-DEC-008). **Day 8 evening soft-rank** of top 3–5 candidates is the backstop (VPS-DEC-027).
- Voiceover framing: positive, never defensive. **Devpost text description leads with fan-centric opener (VPS-DEC-036).**
- Music bed candidates: target Day 6–7 (VPS-DEC-032). Final pick during Day 9 dress rehearsal under the actual anchor-story Narrator audio.
- Narrator voice was tested on Day 5 (VPS-DEC-031); voice "Algenib" is in production for Mount Pleasant and reads warm/mid-tone documentary register. Decision can be revisited if Charlie hears better in dress rehearsal but holds for now.
- Devpost text description: outline pending against VPS-DEC-029 / VPS-DEC-036. Day 6 priority.

### Submission state

- Challenge category locked: Challenge 2.
- Apache 2.0 license: NOT YET CREATED. Day 1 priority #1.
- Hosted URL: NOT YET PROVISIONED. Must feel alive in <1s on first paint via Wire pre-seed of recent published events (VPS-DEC-028).
- Demo video: NOT YET RECORDED (Day 10).
- Devpost text description: NOT YET OUTLINED. Day 1–2 priority alongside license + GCP (VPS-DEC-029).
- Internal submission deadline: Sunday May 10 EOD. Devpost hard deadline: Monday May 11 5:00pm PT / 8:00pm ET.

### Known strategic blockers

- None yet. Build hasn't started. The first risk is whether GCP project provisioning + Vertex AI access verification can be done same-day on Day 1.

### Known open strategic questions (see Section 6)

- Whether to mention parity (Challenge 1) and LA28 momentum (Challenge 3) as natural extensions in the submission text description, or stay tightly focused on Challenge 2 alone.
- Whether to layer in Optional Tier 2 (Gemini 3.1 Flash Live "talk to the room") if Day 9 has slack.
- How to phrase the NIL Redaction Layer in the Evidence Drawer UI so a judge understands it in 5 seconds without reading explanation copy.
- **Scope-cut hierarchy under time pressure** — what gets cut first if Day 7–8 runs hot, and does the answer change between optimizing for Grand Prize ($15K) vs Challenge 2 win ($8K) vs Honorable Mention ($5K)? **Decision parked until Tuesday EOD (Day 4)** when we have real signal on what's behind, ahead, and at risk.

---

## 3. Strategic Picture

### 3.1 The judge is the customer

The Storyteller's Room has exactly one customer: a Google judge watching a 3-minute video and possibly clicking around the live URL. Every product decision serves that judge's emotional experience.

**What we know about the judge:**
- They will watch dozens of submissions. Attention is finite.
- They are scoring on three axes: Impact (40%), Technical Depth & Execution (30%), Presentation Quality (30%).
- They are technically literate (Google judges) — the Floor view's real tool calls will register.
- They have seen many AI demos. Polish without substance won't move them. Substance without polish won't either.
- They will Stage One vet for compliance (NIL, brands, timing data, license). DQ at this stage is unforgiving.

**What the judge needs to feel in 3 minutes:**
1. **0:00-0:30 — "Oh. This is alive."** The Wire scrolls. Voices murmur. The Equity Editor intervention is visible in recent history. The framing line lands: *"Every Team USA athlete comes from somewhere."*
2. **0:30-0:55 — "This is real. Real tool calls. Real agents. Not a single Gemini call in costume."** The Floor proves the agentic claim.
3. **0:55-1:05 — "The Equity Editor caused this story."** The click into the anchor story is the payoff for the Wire intervention they saw at 0:15.
4. **1:05-2:30 — "Oh."** The Broadcast lands. Curtain rise, Narrator, choreography, music bed. No presenter voice. The judge feels something they didn't expect to feel about a place they've never heard of.
5. **2:30-2:50 — "I trust this."** The Evidence Drawer opens. Seven sub-stages. *"NIL Redaction: 4 reviewed, 2 aggregated, 2 redacted, cleared."* The compliance constraint becomes the credibility flex.
6. **2:50-3:00 — "I want to know what's next."** Cut back to the Wire. *"Right now, the room is finding the next one."* Hard cut.

**The most fragile demo moment:** the Broadcast. If the Narrator voice is mechanical, if the music bed is wrong, if the curtain rise feels like a route transition — the entire demo collapses to "competent" instead of "memorable." VPS Day 8-10 attention disproportionately on the Broadcast.

**The most distinctive demo moment:** the Equity Editor intervention. No other Challenge 2 submission will have an agent visibly police the feed for parity in real time, with a structural intervention that the user can see causing a queue change. This is the 40% Impact lever.

### 3.2 Competitive positioning within the hackathon

**Most likely Challenge 2 competition profile:**
- Static dashboards with hometown counts mapped to US states.
- Clustering visualizations of hometown hubs by sport.
- Possibly a chatbot interface over Team USA roster data.
- BigQuery + a single Gemini call generating prose summaries.

**How The Storyteller's Room differentiates:**
- **Format:** broadcast room with narrated story pages, not a dashboard.
- **Multi-agent:** seven distinct agents with distinct voices, visibly coordinating, not one Gemini wrapper.
- **Parity as system property:** a dedicated agent enforcing Olympic/Paralympic balance, not a Paralympic toggle.
- **NIL Redaction Layer:** a named architectural feature that demonstrates production-grade compliance thinking.
- **Olympic broadcast aesthetic:** deep navy, gold, editorial serif, slow cinematic pacing, music bed at -25dB. NBC-grade production value applied to a Cloud Run app.

**What we explicitly do NOT do:**
- Build a dashboard. (Wrong format for this concept.)
- Use a chatbot interface. (The Wire is a working newsroom feed, not a chat.)
- Show charts in the Broadcast. (The Broadcast is narration + Hometown panel + Historical Echo panel. No bar charts.)
- Name any individual athlete. Ever. Anywhere. (NIL strict reading; any violation is auto-DQ.)

**Our text-description framing in the Devpost submission:**
- Lead with Challenge 2 alignment: hometown hubs, geographic correlation, counts of Olympians/Paralympians from hometowns.
- Note that the architecture also addresses parity (Challenge 1) and LA28 momentum (Challenge 3) as natural byproducts. This gives judges multiple reasons to score high on Impact without diluting the Challenge 2 fit.
- Describe the seven-agent cast briefly with their voice signatures.
- Describe the NIL Redaction Layer as an architectural feature, not a content review.
- Describe the demo's anchor story as organically discovered, not pre-selected.

### 3.3 The five demo moments are the strategic spine

This is the single most important strategic frame. Every product decision passes through the Decision Filter: *Does this serve one of the five demo moments?*

The five moments (memorize):

1. **The room is alive.** The Wire scrolls before the user does anything. Heartbeat established. (BUILD_SPEC §6.)
2. **The agents are truly agentic.** The Floor shows real tool calls and particle handoffs. Genuinely multi-agent, not a single Gemini call in costume. (BUILD_SPEC §9.)
3. **The Equity Editor caused the anchor story.** Visible feed-drift detection → queue promotion → Storyteller produces the anchor about a Paralympic-anchored place. The system policed itself. (BUILD_SPEC §5.4, §11.)
4. **The Broadcast lands emotionally.** Curtain rise, Narrator, synchronized choreography, music bed, hero image of a stylized place. The judge feels something. (BUILD_SPEC §7.)
5. **The Publish Gate (with the NIL Redaction Layer) proves trust.** Evidence Drawer opens. Seven sub-stages visible. Compliance constraint becomes credibility flex. (BUILD_SPEC §5.7.)

**The Decision Filter is the strategic discipline.** Every feature, every polish item, every "wouldn't it be cool if" pitched during the build gets evaluated against these five. If it doesn't serve at least one, it doesn't ship in the 11-day window. This is what prevents scope creep that kills hackathon submissions.

### 3.4 Place over Person — the strategic frame, not just the legal frame

The pivot from named-athlete newsroom to place-as-protagonist is presented in PROJECT_BRIEF §0 as a compliance pivot. From a product strategy perspective, it's something stronger.

**Strategic framing:** *"Most fan coverage starts with famous athletes. The Storyteller's Room starts one layer deeper — with the communities that produce them."*

**Why this lands:**
- Originality. Every other AI-sports product targets the obvious thing (the famous athlete, the medal moment). We target the layer underneath.
- Emotional resonance. NBC's Olympic editorial template *always* opens with the hometown anyway. We made the hometown the protagonist of the entire piece.
- Long-term scalability. Athletes change every Games. Places persist across generations. A Storyteller's Room scales across decades because places do.
- Judge memorability. "AI room that finds the towns behind Team USA" is a one-line pitch. "AI room that profiles individual athletes" is what every other entry is doing.

**The voiceover line that captures this:** *"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin."*

**The post-hackathon thesis (in the submission text but not the demo voiceover):** This same architecture could run alongside USOPC, USA Swimming, USA Track & Field, US Soccer, the WNBA, NCAA athletics — finding the *places* the existing media apparatus misses, producing them at broadcast quality, and giving communities the recognition their representation has earned. Same architecture. Different corpus. Different scouts. Same room.

### 3.5 The NIL Redaction Layer as positioning weapon

The NIL Redaction Layer is named. It has its own section in the Constitution (§7), full Python module spec in BUILD_SPEC (§5.7), and dedicated treatment in the Vision Doc. It is sub-stage 4 of the Publish Gate's audit log. It is visible in the Evidence Drawer during the demo.

**Why this matters strategically:**
- Most submissions will treat NIL compliance as a content review (a checklist someone runs at submission time). We made it architecture. Judges who notice the difference will credit it.
- The audit log shows *"4 individual references reviewed. 2 aggregated. 2 redacted. Cleared."* Concrete numbers. Visible work. This is a production-engineering signal that the rest of the architecture is also serious.
- The pattern (don't trust the LLM to enforce its own constraints; enforce structurally with a Python guard between agent output and user-facing surface) is a demonstrably correct pattern for any AI product handling regulated content. It's a thoughtful answer to a question other teams haven't asked.

**The demo voiceover does NOT explain the NIL Redaction Layer.** It doesn't need to. The Evidence Drawer shows the audit; the architecture speaks for itself. Explaining it in voiceover would be defensive ("the rules don't allow us to..."). Showing it in the audit is confident.

### 3.6 Anchor story selection — the Day 9 strategic decision

The anchor story is the place that becomes the centerpiece of the Broadcast page in the demo video. It is selected on Day 9 from the corpus the system organically produces during Day 8-9.

**Selection criteria (locked):**
1. **Strong Paralympic representation** — the Equity Editor caused this story via feed-drift detection. The demo's anchor story IS the proof that parity is a system property.
2. **A clean era parallel** — the Echo Scout cited a 1960s/1970s/1980s era pattern (not a named athlete), giving the Broadcast page a Historical Echo panel reveal moment.
3. **Visual richness** — the place renders beautifully as a stylized Nano Banana Pro hero image (a small-town main street, a high school gym, a regional landscape).
4. **Emotional landing** — the Storyteller's draft makes Charlie sit back from his laptop. This is the only criterion that overrides the others. The most polished story that doesn't make Charlie sit back is not the anchor.

**Do NOT pre-select the anchor before Day 9.** This is locked as VPS-DEC-008. Pre-selecting violates the "let the system produce it" discipline that is itself part of what makes the demo authentic.

### 3.7 Post-hackathon strategic vision (demo asset, not execution plan)

The post-hackathon paragraph in the Vision Doc (and the closing voiceover *"Right now, the room is finding the next one"*) gestures toward a bigger thesis. Charlie does not have to commit to executing this post-submission.

**The thesis (for the submission text and demo voiceover only):**
- AI-native sports storytelling at scale. Continuous coverage across the four-year cycle, not just during the two weeks of the Games.
- Editorial layer that runs alongside USOPC, NCAA, league offices.
- Discovery engine that makes human storytelling reach further than it ever has, while protecting individual athlete identity by architecture.

**Why include this in the submission narrative:** It signals to judges that the architecture is portable, the Constitution is reusable, and the team is thinking past the demo. It's the difference between "hackathon project" and "thesis with proof of concept."

**Why NOT commit to executing it post-hackathon:** This is one project. Whether Charlie pursues The Storyteller's Room post-submission depends on whether the thesis lands with judges, what feedback comes back, and what the post-hackathon path actually looks like for a solo founder. The vision is in the doc as an aspiration; the execution is a separate decision.

### 3.8 What "Olympic broadcast aesthetic" means as a product standard

The visual and audio language of the product is borrowed from NBC Olympic broadcasts. This is locked in CONSTITUTION §11 and BUILD_SPEC §10. From a product strategy perspective:

- **Reverence over hype.** Slow pacing, deep navy, gold accents, editorial serif headlines. The Wire moves at 4-8s per event, not chat-app speed.
- **Documentary register, not stadium PA.** The Storyteller writes literary prose. The Narrator reads warmly. No "inspirational," no "hero," no "overcame."
- **Production value as trust signal.** The curtain rise transition (1.5-2.0s of choreographed motion + audio + music bed) tells the judge "this team takes the craft seriously." If the Broadcast page felt like a generic Next.js route transition, the trust evaporates.
- **The first half-second test.** Before any text loads, the user must already feel they're looking at an Olympic-broadcast-grade product. Deep navy. Gold hairline. Stylized place hero. Wire beginning to scroll. No "Welcome to" banner. No marketing copy.

This is what differentiates The Storyteller's Room from "another AI app that processes Olympic data." The aesthetic IS the product positioning.

---

## 4. Naming and Roles

The seven-agent cast is locked. These names are product decisions, not arbitrary labels.

| Name | Role | Voice signature | Notes |
|---|---|---|---|
| **Editor** | Orchestrator | Terse. Decisive. Speaks in fragments. *"Going with Mount Pleasant. Investigator, 90 seconds."* | Owns the queue, makes go/no-go calls, accepts or overrides Equity Editor recommendations. |
| **Scout Desk** | Lead surfacing (4 sub-scouts inside) | Curious. Slightly messy. Investigative. | One agent in the cast; four sub-scouts inside it. |
| ↳ **Cinderella Scout** | Sub-scout: places that punched above their weight | Hesitant, builds confidence visibly. *"I want to believe this place. Need a second source."* | Inside Scout Desk. |
| ↳ **Comeback Scout** | Sub-scout: regional pipelines that disappeared and returned | Patient, time-aware. *"This program disappeared from the corpus for 19 years. Now it's back."* | Inside Scout Desk. |
| ↳ **Hometown Scout** | Sub-scout: small-town origins, regional sport ecosystems | Warm, place-textural. *"Population 8,600. There's exactly one stoplight."* | Inside Scout Desk. The "lead scout" in this Pivot A+ build — Hometown is the most direct mapping to Challenge 2. |
| ↳ **Echo Scout** | Sub-scout: modern patterns rhyming with iconic Olympic eras | Cryptic, era-focused. *"This has the shape of the 1960 Rome era. Checking."* | Inside Scout Desk. **Cites Games, eras, regions, sports, patterns. Never named athletes.** |
| **Investigator** | Deep research, source verification, narrative spine | Precise, source-driven. *"Pulling sources. Quad-City Times has hometown coverage."* | Calls Gemini Deep Research for high-priority leads. Absorbs Historian/Geographer/Trend Analyst as tools, not separate agents. |
| **Paralympic Equity Editor** | Parity enforcement (veto power) | Blunt, disciplined. *"Feed drift detected. Last 4 places Olympic-heavy. Promoting Paralympic-anchored lead next."* | The 40% Impact lever. Causes the demo's anchor story. |
| **Storyteller** | Final 400-700 word narrative | Literary, restrained. Documentary, not sportscaster. | Never names individual athletes. Never uses "inspirational," "hero," "overcame," "former Olympian." |
| **Narrator** | TTS broadcast voice | Warm, mid-tone, documentary register. (Audio voice signature) | Two voice configs: Broadcast Narrator + Wire Dispatcher. |
| **Publish Gate** | Final go/no-go (7 sub-stages) | Procedural, calm. Reports counts and conclusions. *"14 claims checked. 2 removed. 1 softened. NIL Redaction: 4 reviewed, 2 aggregated, 2 redacted. Cleared."* | Includes the NIL Redaction Layer as sub-stage 4. Calls the Visualizer (Nano Banana Pro / 2) as a tool. |

**Why the cast is locked at seven:** The judge can track 7 named entities in a 3-minute demo. They cannot track 11. Adding agents reduces clarity even if it adds capability. Sub-scouts live inside Scout Desk; the Visualizer is a tool the Publish Gate calls; the NIL Redaction Layer is a sub-stage of the Publish Gate. See HOE-DEC-007.

**Why each agent has a distinct voice:** If two agents sound alike on the Wire, the room dies. Voice work is not polish; voice work is the product. See CONSTITUTION Law 2.

**Why Hometown Scout is the de facto lead scout in this Pivot A+ build:** Challenge 2 is The Hometown Success Engine. Hometown Scout's obsession (small-town origins, first-from-here-since-decade stories, regional sport ecosystems) is the most direct mapping. Cinderella, Comeback, and Echo serve their own narrative shapes, but Hometown is closest to the Challenge 2 framing. This shapes the demo's anchor story bias toward Hometown-Scout-led discoveries.

---

## 5. Decisions Log (Append-Only)

Decisions are grouped by domain. Within each domain, they are chronological. Only Charlie can reverse a decision. If a decision is overridden, append a new decision referencing the override — do not edit the original.

### Concept & Pivot

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-001 | Pivot from named-athlete newsroom (concept v1.0) to Place over Person (Pivot A+, concept v1.1) | Original concept conflicted with NIL prohibition (Section 6 of Official Rules; Section 19 auto-DQ). Pivot to places/programs/patterns as story units preserves emotional power, aligns directly with Challenge 2, and turns the constraint into a credibility flex via the NIL Redaction Layer. | 2026-05-01 |
| VPS-DEC-002 | Strict NIL interpretation — no individual athlete names anywhere in user-facing output, including current, retired, AND historical athletes (Wilma Rudolph, Jesse Owens, Jim Thorpe, etc.) | The rule's plain text doesn't carve out historical or deceased athletes. Strict reading is safer (Stage One DQ is unforgiving) AND makes the Echo Scout more sophisticated by forcing era/region/pattern parallels instead of famous-name shorthand. | 2026-05-01 |
| VPS-DEC-003 | Story units are PLACES, PROGRAMS, PATTERNS — the protagonist primitive of the room | Pivot A+ baked into Constitution Law 4 (Place over Person), BigQuery `candidates` table (`story_unit_type STRING NOT NULL`), and every agent prompt. | 2026-05-01 |

### Submission Strategy

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-004 | Submission category = Challenge 2 (Hometown Success Engine), not Challenge 5 wildcard | Pivot A+ makes us directly aligned with sponsor-defined Challenge 2: hometown hubs, geographic correlation, counts of Olympians/Paralympians from hometowns. Cleaner Stage One vetting box than the wildcard. Submission text will mention parity (Challenge 1) and LA28 momentum (Challenge 3) as natural extensions of the architecture. | 2026-05-01 |
| VPS-DEC-005 | Internal submission deadline = Sunday May 10 EOD (~24h before Devpost hard deadline May 11 5:00pm PT) | Devpost servers crowd at the buzzer. Cloud Run deployments can fail. Last-minute compliance discoveries need time to fix. Day 11 is buffer. Submitting at Day 11 hour 7:59pm EDT is a failure mode. | 2026-05-01 |

### Demo Strategy

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-006 | Demo seed prompt = *"Find me a Team USA hometown story I've never heard before"* | Aligns demo with Challenge 2 framing. "I've never heard before" creates curiosity. Not "Find me a Team USA story" (too generic), not "Find a hometown story Team USA fans should know" (too editorial-conferencey for the live-investigation moment). | 2026-05-01 |
| VPS-DEC-007 | Demo voiceover framing = positive, never defensive | *"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin."* Saying "the rules don't allow us to..." in voiceover is on the Kill List. The architecture speaks for itself in the audit log. | 2026-05-01 |
| VPS-DEC-008 | Anchor story selected on Day 9 from organic discoveries — not pre-planned | The system runs continuously Day 8-9 and produces 15-25 organic place/program/pattern stories. Charlie picks the anchor by which one makes him sit back from the laptop. Pre-selecting before Day 9 violates this decision and breaks the "let the system produce it" discipline. The Equity Editor causing the anchor (via feed-drift detection promoting a Paralympic-anchored place) is also organic, not scripted. | 2026-05-01 |
| VPS-DEC-009 | Five demo moments are the strategic spine; Decision Filter applies to every product decision | The five moments (room is alive / agents are agentic / Equity Editor caused anchor / Broadcast lands emotionally / Publish Gate proves trust) are the only thing the judge will remember. Every feature, every polish item, every "wouldn't it be cool if" passes through *"Does this serve one of the five demo moments?"* If no → cut. | 2026-05-01 |
| VPS-DEC-010 | Demo video is the submission artifact; the hosted URL is secondary | Per Devpost FAQ: judges may test the project but are not required to. Many will judge based on the video and text description alone. Day 10 (video record/edit/mix) is the highest-leverage day in the build. UI polish that doesn't show in the video is lower priority than UI polish that does. | 2026-05-01 |

### Cast & Architecture

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-011 | Cast is locked at seven agents — no 8th, ever | Editor, Scout Desk, Investigator, Paralympic Equity Editor, Storyteller, Narrator, Publish Gate. Sub-scouts (Cinderella, Comeback, Hometown, Echo) live inside Scout Desk. Historian/Geographer/Trend Analyst impulses fold into Investigator as tools. Visualizer is a tool the Publish Gate calls. NIL Redaction Layer is a sub-stage of the Publish Gate. The judge can track 7 in 3 minutes; not 11. (Cross-ref: HOE-DEC-007, Constitution Rule 2.) | 2026-05-01 |
| VPS-DEC-012 | Voice signatures are the product, not polish | Each of the seven agents has a voice that distinguishes it from the others on tone alone. The Wire vocabulary library (~50 phrase fragments per agent) is staged in `data/wire_vocabulary.json`. If two agents sound alike on the Wire, the room dies. (Cross-ref: Constitution Law 2.) | 2026-05-01 |
| VPS-DEC-013 | The Wire is meditative — 4-8s per event, 70/30 thinking/milestone ratio | NBC Olympic broadcasts linger. The Wire lingers. If the Wire is sped up to feel "more responsive," the product feels like a chat app instead of a broadcast room. The 70/30 ratio is what makes it feel like a working newsroom instead of a press release. (Cross-ref: Constitution Rule 4, BUILD_SPEC §6.) | 2026-05-01 |
| VPS-DEC-014 | Hometown Scout is the de facto lead scout in this Pivot A+ build | Challenge 2 = Hometown Success Engine. Hometown Scout's obsession (small-town origins, first-from-here-since-decade stories, regional sport ecosystems) is the most direct mapping to the challenge. The other three sub-scouts (Cinderella, Comeback, Echo) serve their own narrative shapes; Hometown is closest to the framing. The demo's anchor story will likely be Hometown-Scout-led. | 2026-05-01 |

### Compliance as Architecture

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-015 | NIL Redaction Layer is a named architectural feature, not a content review | Sub-stage 4 of the Publish Gate. Python module that scans every text artifact bound for a user-facing surface (Wire, Broadcast, demo). Three checks (direct match, near-identification, small-aggregate). Three actions (pass / aggregate / return-to-Storyteller). Audit log visible in the Evidence Drawer during the demo. The constraint becomes the credibility flex. (Cross-ref: HOE-DEC-004, Constitution §7.) | 2026-05-01 |
| VPS-DEC-016 | Apache 2.0 license is Day 1 priority #1 — before any code | Stage One auto-DQ trigger if missing on submission day. Five-minute task. LICENSE file in repo root, GitHub License field set, badge visible in About sidebar, README first paragraph references it. Do this before writing any agent code. (Cross-ref: HOE-DEC-010.) | 2026-05-01 |
| VPS-DEC-017 | Honest production, not faked liveness — every Wire event has a `mode` field | The single live investigation in the demo runs at 4× compressed time with the honest label "Live investigation — playback at 4×." Olympic broadcasts run produced packages constantly. We do too, and we say so. Faked-live is broken — judges who spot fakery will downgrade Technical Depth instantly. (Cross-ref: HOE-DEC-013, Constitution Rule 3.) | 2026-05-01 |
| VPS-DEC-018 | Parity is a system property — Paralympic Equity Editor with veto power, structurally enforced | We do not "include Paralympic athletes in the prompt." We architect a dedicated agent whose only job is enforcement. The 40% Impact lever. The agent has feed-level, story-level, and safety-level interventions. Visible on the Wire (Agitos-red color signature) and in the Publish Gate audit log. (Cross-ref: Constitution Law 3.) | 2026-05-01 |

### Aesthetic & Production

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-019 | Olympic broadcast aesthetic — NBC primary, deep navy + gold + editorial serif | Reverence over hype. Slow cinematic pacing. No cartoon mascots, no consumer-app brightness, no SaaS dashboard chrome, no spinners, no emoji in the Wire, no chat-bubble UI. (Cross-ref: Constitution §11, BUILD_SPEC §10.) | 2026-05-01 |
| VPS-DEC-020 | Stylized illustration only — no photorealism, no people in hero images | Subject is always a place, landscape, community, or facility. Never a person. Nano Banana Pro / 2 prompts enforce stylization at generation; Visual Review sub-stage of Publish Gate enforces at publication. (Cross-ref: Constitution Law 6.) | 2026-05-01 |
| VPS-DEC-021 | Documentary, not sportscaster — Storyteller and Narrator forbidden words list locked | "Inspirational," "hero," "overcame," "despite," "warrior," "fighter" (applied to disability), "wheelchair-bound," "suffers from," "former Olympian," "past Olympian." We're *The Daily*, not stadium PA. We're 30 for 30, not pre-game hype. (Cross-ref: Constitution Law 5.) | 2026-05-01 |
| VPS-DEC-022 | Curtain rise is non-negotiable — 1.5-2.0s choreographed transition | Wire motion slows. Ambient audio ducks. Screen darkens. Hero image fades in. Narrator breath audible. Headline character-by-character. Music bed enters at -25dB. Without the curtain rise, it's not the Broadcast page; it's a story page. Story pages are not what we're building. (Cross-ref: BUILD_SPEC §7.1.) | 2026-05-01 |
| VPS-DEC-023 | Music bed at -25dB under the Narrator. Always. | Source from Epidemic Sound or Artlist. Cinematic, documentary, slow build. Mix at -25dB so the Narrator stays the emotional spine. Music that competes with the Narrator voice is on the Kill List. (Cross-ref: BUILD_SPEC §7.5.) | 2026-05-01 |

### Tech & Tooling

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-024 | Tech stack locked: ADK on Cloud Run + BigQuery + Firestore + Cloud Storage + Next.js 15 + Gemini 3.1 family + Gemini 3 Flash + Flash-Lite + Deep Research + Nano Banana Pro/2 + Flash TTS | Locked to prevent re-litigation during the build. Re-litigating choices burns 11-day window time we don't have. (Cross-ref: HOE-DEC-008, BUILD_SPEC §3.) | 2026-05-01 |
| VPS-DEC-025 | Do NOT use Veo 3.1 (video generation) | Slow, expensive, increases NIL risk. Stills with Ken Burns motion + Narrator voice gives the same emotional effect at lower cost and risk. The Olympic broadcast aesthetic doesn't need video. (Cross-ref: HOE-DEC-009.) | 2026-05-01 |
| VPS-DEC-026 | Optional Tier 2 (Gemini 3.1 Flash Live "talk to the room") deferred to Day 9 if v1 is solid | Powerful demo lift if it ships, but must not block v1. The five demo moments work without it. If Day 9 has slack and the Broadcast is locked, layer it on. If Day 9 is tight, ship without it. | 2026-05-01 |

### Tightening Pass — Day 1 (Session 1)

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-027 | Day 8 evening soft-rank of top 3–5 anchor candidates as a backstop to Day 9 organic selection | VPS-DEC-008 still binding (system produces the corpus, anchor selected from organic discoveries on Day 9, must be Equity-Editor-caused, must make Charlie sit back from the laptop). But "Charlie picks one that lands emotionally" is a single point of failure on a hard deadline. Day 8 evening soft-rank pre-screens what Day 9 will choose from. If all 5 are flat, we re-run on Day 9 morning with Day 9 production noise lower. Preserves the discipline; adds 24 hours of warning. | 2026-05-02 |
| VPS-DEC-028 | Live URL pre-seeds the Wire on first paint with the most recent ~6 published events (`mode: replay`) so the room is "scrolling" within <1s of arrival | The Wire's meditative cadence (4–8s per event) is right for ambient operation, but a judge landing on an empty Wire and waiting 6s for the first event has already left. Pre-seed is honest under our existing `mode` contract — it's labeled `replay`, not `live`. Page-load state is "scrolling room," not "empty Wire waiting for first event." (Cross-ref: BUILD_SPEC §6.2 mode field.) | 2026-05-02 |
| VPS-DEC-029 | Devpost text description outlined Day 1–2 alongside license + GCP provisioning; refined Day 9; final pass Day 10 | The text description is one of three judged artifacts (alongside the video and the live URL) and where the post-hackathon thesis lands. Drafting it on Day 10 while recording, mixing, and submitting is when typos happen and Challenge-1/3-also-addressed framings get cut for time. VPS owns the outline and refinement; HoE focuses on shipping. | 2026-05-02 |
| VPS-DEC-030 | Demo seed prompt removed from the demo video entirely; lives only as the live URL hero CTA | Showing a typed prompt in the video collapses the system into a chatbot mental model and undermines the autonomous-newsroom positioning. The video's job is to demonstrate that the room is alive, makes editorial decisions (especially parity), and produces emotionally compelling output — not to demonstrate interactivity. The demo video remains: Wire → Floor → Equity-Editor-caused click into anchor → Broadcast → Publish Gate → return to Wire. The seed prompt remains in the product as the primary entry point for users on the live URL: *"Find me a Team USA hometown story I've never heard before."* The two artifacts (video, URL) carry two different jobs. **This refines but does not reverse VPS-DEC-006** — the prompt content stays locked; only its placement is constrained to the live URL. | 2026-05-02 |
| VPS-DEC-031 | Narrator voice config tested on Day 5 (not Day 6) with a 30-second sample read | The Narrator is the emotional spine of the Broadcast. If the substituted Flash TTS voice (placeholder "Charon" in BUILD_SPEC §5.6 may not be the actual current voice name) lacks the warm/mid-tone/documentary quality we need, we want to know with 5 days of buffer to iterate, not 4. Pulling forward by one day costs nothing; finding out late costs the demo. | 2026-05-02 |
| VPS-DEC-032 | Music bed candidates sourced Day 6–7 (not Day 8) so they're available to A/B under sample Narrator audio when the Narrator is being tested | Day 8 is also Floor + Broadcast + curtain-rise day — the heaviest production day. Music bed sourcing is a low-effort task that should not compete for Day 8 attention. Source 2–3 candidates Day 6–7; final pick during Day 9 dress rehearsal under actual anchor-story Narrator audio. (Cross-ref: BUILD_SPEC §7.5.) | 2026-05-02 |
| VPS-DEC-033 | Linguistic clarifier on Olympian/Paralympian temporal phrasing — "first," "next," "newest," "earliest" are encouraged; "former," "past," "ex-" remain forbidden | The forbidden-words list correctly bans "former Olympian" and "past Olympian." But the Storyteller writing *"this town produced its first Olympian in 1964"* or *"the program's next Olympian came from..."* is not just permitted — it's actively required for place-based narrative. Without this clarifier, an over-cautious Storyteller agent will strip out the temporal framing the place stories need. (Cross-ref: PROJECT_BRIEF §10, CONSTITUTION Law 5.) | 2026-05-02 |
| VPS-DEC-034 | Daily monitor of Devpost Updates and Discussions tabs added to PROJECT_BRIEF §15 per-commit checklist | The contest is mid-flight. Sponsor-issued clarifications can land on the Updates tab between now and submission. Five-minute daily check catches a class of late-breaking compliance shifts. (Cross-ref: PROJECT_BRIEF §15.) | 2026-05-02 |

### Day-5 Audit Pass — Session 2 (mid-build review against running localhost)

VPS-DEC-035 through VPS-DEC-040 are the result of a Day-5 audit comparing the running build to (a) Constitution + BUILD_SPEC and (b) the contest announcement transcript. The audit found three drifts (front door, Floor scope, publish-gate aggregation) and three contest-brief gaps (interactivity visibility, fan-centric framing, GCP-shot requirement). All six are closeable in days, not weeks. Build is 4–5 days ahead on craft; these decisions reallocate the buffer to closing spec and brief gaps before submission.

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-035 | Establishing shot of the live-URL front door (with seed-prompt CTA visible) at 0:05–0:10 of the demo video. Affordance visible, no interaction shown. | The contest announcement transcript at 0:13 calls explicitly for *"interactive tools for fans everywhere"* and at 1:14 asks builders to *"Help fans find where excellence is fostered."* VPS-DEC-030 (no typed prompt in the video) was argued against the autonomous-newsroom positioning but did not engage the contest brief's interactivity framing. Risk under VPS-DEC-030 alone: judges credit the architecture but miss the fan-facing tool axis. The fix is a 2–3 second establishing shot at 0:05–0:10 that shows the live-URL front door composition (masthead, scrolling pre-seeded Wire, Stack on the right, seed-prompt CTA at the bottom) before zooming into the Wire. The CTA is in frame; we never type into it. The judge registers "this is a fan-facing tool" without us collapsing the system into a chatbot mental model. **Refines VPS-DEC-030; does not reverse it.** | 2026-05-06 |
| VPS-DEC-036 | The Devpost text description leads with a fan-centric opener sentence. **Locked opener:** *"Most fans of Team USA know the famous names. Far fewer know the towns that produced them. The Storyteller's Room is an AI broadcast room that finds, verifies, and tells the hometown stories behind Team USA — built so any fan can watch the room work, ask it to find a story they've never heard, or browse what it has finished telling."* | Contest video uses *"fan-centric"* twice as the framing word. Our outline (VPS-DEC-029) led with Challenge 2 alignment, then the seven-agent cast, then the NIL Redaction Layer — the fan was implicit but never the protagonist of the pitch. The locked opener delivers (a) fan-centric problem statement, (b) place-over-person positioning, (c) the autonomous + interactive duality (verbs "watch," "ask," "browse"), and (d) all in one paragraph at the top of the text description. Rest of the outline (Challenge 2 → parity → seven agents → NIL Layer → post-hackathon thesis) follows unchanged. | 2026-05-06 |
| VPS-DEC-037 | The demo video includes one explicit GCP / Vertex AI shot to satisfy the contest's *"show Gemini and Google Cloud usage by showing the GCP console, AI Studio, and/or code"* requirement. Recommended placement: PIP cutaway at ~0:40 during the Floor segment. Floor's tool call cards must also be cleanly labeled as "Vertex AI / Gemini 3.1 Pro," "Cloud Run," "BigQuery," etc. for redundancy. | PROJECT_BRIEF §4 quotes the Devpost requirement verbatim. Our Day-1 storyboard did not have an explicit slot for it. The Floor's tool call cards likely *qualify* if labeled clearly, but "likely" is not what we want at submission. Defense in depth: clearly-labeled tool cards in the running UI plus one 2-second PIP cutaway to a real GCP console / AI Studio screen during the Floor segment. (Cross-ref: PROJECT_BRIEF §4 submission requirements.) | 2026-05-06 |
| VPS-DEC-038 | The current `/floor` (places-constellation) is renamed to `/field` (or `/discoveries` — HoE's call on the URL slug). The actual seven-agent graph per BUILD_SPEC §9 is built next at a new `/floor` route. Two surfaces, two demo moments. | The current constellation is beautiful and avoids US-state-map geographic bias, which is correct (Charlie's Day-5 instinct to keep it is right). But it occupies the URL and conceptual slot that BUILD_SPEC §9 reserved for the agent graph (Demo Moment #2 — "the agents are truly agentic"). Currently the seven-agent claim is invisible in ambient operation; it can only be inferred from the side panel after a click. The fix is not "scrap the constellation" but "rename it and build the agent graph next to it." Estimated 2 days of work; data already flowing (agent events to Firestore), just needs a different visualization layer. (Cross-ref: BUILD_SPEC §9 — agent nodes, particle handoffs, tool call cards, Equity Editor flash.) | 2026-05-06 |
| VPS-DEC-039 | The `/publish-gate` showcase aggregation is fixed to pull non-zero redaction stats from real published stories' audit footers. If real numbers are still 0/0/0 because the Storyteller never produces drafts that need redacting, at least one demonstration story is engineered whose investigation source corpus contains athlete names the layer catches and aggregates. | The showcase currently shows 0 redactions performed / 0 disambiguation hits / 12-of-0 cleared/blocked. PROJECT_BRIEF §14 NIL safety verification: *"NIL Redaction Layer's audit log shows real redaction work (not all-zeros)."* — that's a pre-submission DQ flag right now. The per-story footer on Mount Pleasant *does* show real work (`[NIL: 2r/1a]`), so the layer is real; the showcase aggregation is broken. If aggregation is fixed and numbers are still all-zeros (because the Storyteller is well-disciplined and never produces names), the demo's most powerful trust signal becomes invisible. Engineer at least one organic or fixture investigation where the source corpus contains athlete names so the layer demonstrates its work. The credibility flex requires visible work, not just code coverage. | 2026-05-06 |
| VPS-DEC-040 | The HoE's proposed editorial homepage at `/` (kicker + display headline + dek + hero card grid + 3-card grid) is **rejected**. The fix to the front-door comprehension problem is to implement VPS-DEC-028 (Wire pre-seed) properly, add the Stack as a right-column component on `/` (not as a separate page replacement), add the seed-prompt CTA below, add a thin editorial masthead (broadcast-ID style, not banner-style), and add ambient broadcast-chrome navigation. The optional discoverable "?" overlay for an editorial 3-paragraph explainer is approved (must not auto-open). **REFINED BY VPS-DEC-041: the Wire-as-centerpiece-with-Stack-right-column structure is itself superseded by the fan-engagement front-door design. VPS-DEC-040's rejection of the kicker/dek/hero-card landing page still stands; only the alternative front-door design within VPS-DEC-040 has been replaced.** | The HoE's UX read of the comprehension problem is correct. Their proposed solution structurally violates Constitution §11 (*"No 'Welcome to' banner. No marketing copy."*), Constitution Rule 6 (*"No tutorials. No onboarding. No 'Welcome to The Storyteller's Room.'"*), and the canonical vision narrative in *What_is_The_Storytellers_Room* (*"You don't see a welcome screen. You see The Wire."*). A kicker + display headline + dek + hero card pattern *is* the editorial-magazine equivalent of a marketing landing page — it explains the product before letting the visitor experience it. That dashboard pattern is exactly what every other Challenge 2 entry will look like; the autonomous-newsroom positioning is our entire moat. | 2026-05-06 |

### Fan-Engagement Reframe — Session 2 (Day 5, later same day)

After ratifying VPS-DEC-035 through VPS-DEC-040 and reviewing the build with Charlie, Charlie made a strategic call: stop optimizing for the demo storyboard; build the fan engagement site that someone would actually want to use, and the demo will follow naturally from a fan's flow through that product. VPS-DEC-041 through VPS-DEC-044 implement the reframe.

| # | Decision | Reasoning | Date |
|---|---|---|---|
| VPS-DEC-041 | **The front door at `/` is fan-first, not Wire-as-centerpiece.** Structure: thin editorial masthead at top → thin ambient Wire ticker band (32px, horizontally scrolling, persistent across all pages) → full-bleed cinematic hero of the latest published story (headline + dek overlay, click → Broadcast) → discovery row of three equal-weight cards (THE MAP / THE FIELD / THE STORIES) → seed-prompt CTA → recent-stories grid (the Stack, made explicit) → bottom-fixed broadcast-chrome navigation strip. The dedicated full-page Wire view moves to `/wire`. | The previous front-door design (Wire two-thirds left, Stack one-third right) was Constitutionally faithful to the vision narrative's *"you don't see a welcome screen, you see the Wire"* phrasing — but it served *judges* (proving liveness) more than *fans* (delivering them to the hero piece). The contest brief is explicit: *"interactive tools for fans everywhere"* (0:13) and *"Help fans find where excellence is fostered"* (1:14). A fan visiting wants to *find a story*, not watch a feed of agent activity. Reading the Constitution literally rather than the vision narrative figuratively: §11 calls for *"cinematic hero (a stylized landscape, not a person). Wire beginning to scroll."* — the literal text supports a story-hero with ambient Wire as well as it supports Wire-as-centerpiece. The fan-first structure delivers the room's emotional payoff (the Broadcast) more directly while still keeping the room visibly alive (ambient Wire band on every page). The Wire is preserved as a dedicated experience at `/wire` for fans / judges who want to watch the room work in full. **This refines VPS-DEC-040's alternative front-door spec; the rejection of the kicker/dek/hero-card landing page still stands.** | 2026-05-06 |
| VPS-DEC-042 | **The Map and The Field are siblings, not substitutes. Build both.** Three discovery surfaces, each serving a different fan motivation: **The Map** (`/map` — new) for geographic-familiarity discovery (*"find your region"*); **The Field** (`/field` — current `/floor` constellation, renamed per VPS-DEC-038) for abstract-pattern discovery (*"follow the patterns"*); **The Stories** (`/story` — already shipped) for chronological/editorial discovery (*"read what the room has finished telling"*). All three lead to the Broadcast. | The earlier instinct (constellation-yes, map-no) was right *as long as the discovery surface was singular* — a map alone traps fans in their geographic familiarity bubble (*"only click my home state"*). With multiple discovery surfaces, the Map's familiarity bias stops being a flaw and becomes a feature: it serves the fan whose entry motivation is personal-geographic connection. A different fan, motivated by curiosity-about-the-unfamiliar, uses the Field. A third, who just wants what's new, uses the Stories index. Three doors, three motivations, all funneling to the same Broadcast. The Map should be a stylized US map (deep navy base, painterly, NOT a Google Maps tile clone — avoid third-party logos), with place dots in warm gold sized by Olympian/Paralympian count, hover for place name + story title, click → Broadcast. (Cross-ref: VPS-DEC-038 for the rename of current `/floor` → `/field`.) | 2026-05-06 |
| VPS-DEC-043 | **The Stories index (`/story`) gets fan-discovery facets: filter by sport, by era / decade, and by Olympic / Paralympic / both.** Facets are surfaced as a thin row of pill toggles below the page header; selecting a facet filters the story list inline (no full-page navigation). | A fan visiting `/story` may have a specific motivation: *"show me wrestling places"*, *"show me Paralympic-anchored places"*, *"show me places that have produced Olympians since LA84"*. Without facets, the index is browse-only, which serves the casual fan but fails the motivated fan. Facets convert the index from a publication archive into an interactive discovery tool — exactly the contest brief's *"interactive tools for fans"* framing. The facet values come from existing story metadata (`primary_sports`, `representation_history`, `olympic_or_paralympic` on the candidates table per BUILD_SPEC §8.1). Implementation note: facet selection should be reflected in URL query params so a fan can share a filtered view (e.g., `/story?sport=wrestling&type=paralympic`). | 2026-05-06 |
| VPS-DEC-044 | **The Broadcast page autoplays narration on load, with an obvious mute toggle near the player.** When a fan navigates from any surface (front door hero / Map / Field / Stories index) into a Broadcast page, the click counts as user interaction and the browser permits autoplay with sound; narration begins immediately as part of the curtain-rise choreography (BUILD_SPEC §7.1). For direct-link arrivals (shared URLs, judges with bookmarked deep links) where browsers block autoplay-with-sound, the page falls back to autoplay-muted with a prominent gold "Unmute" / "Begin broadcast" affordance overlaid on the player area. | The Mount Pleasant Broadcast page currently shows a play button at `00:00 / 02:59` that requires a click to begin. That's the safe webpage default, but it's the wrong UX for a *broadcast*. A broadcast doesn't ask permission to begin; it begins. Autoplay matches Constitution Law 5 (*"documentary, not sportscaster"* — *The Daily*'s episodic experience starts when you press play, but the Broadcast page is meant to feel like *opening to a finished segment*). The obvious mute toggle (gold, near the player, never hidden) handles the small minority of fans for whom audio-on-load is an environment problem (open-plan office, bus, library). Browser autoplay-policy reality: most modern browsers permit autoplay-with-sound when there's prior user interaction in the same tab — which there will be for the Map/Field/Stories click path. Direct-link arrivals get the autoplay-muted-with-unmute fallback. The implementation must handle both paths gracefully without flickering. (Cross-ref: BUILD_SPEC §5.6 Narrator, §7.1 curtain rise.) | 2026-05-06 |

---

## 6. Open Questions (Overwrite as Resolved)

*Questions move out of this section into the Decisions Log when answered.*

### Submission framing

- **Q1: ~~How tightly should the Devpost text description focus on Challenge 2 alone...~~** RESOLVED 2026-05-06 (Day 5): VPS-DEC-036 locks the opener — fan-centric framing first, then Challenge 2 alignment paragraph, then parity (Challenge 1) + LA28 momentum (Challenge 3) as natural extensions, then seven-agent cast, then NIL Redaction Layer as architecture, then post-hackathon thesis paragraph. Multi-axis Impact scoring without diluting Challenge 2 fit.

### Demo production

- **Q2: ~~Test the Broadcast Narrator voice on Day 6...~~** RESOLVED 2026-05-02: pulled forward to Day 5. See VPS-DEC-031. HoE will run a 30-second sample read on Day 5, Charlie listens, sub if needed.
- **Q3: How to phrase the NIL Redaction Layer in the Evidence Drawer UI so a judge understands it in 5 seconds?** Options: (a) *"NIL Redaction: 4 reviewed, 2 aggregated, 2 redacted, cleared"* (current spec — terse); (b) *"Individual athlete safety: 4 references reviewed, 2 aggregated as counts, 2 redacted, cleared for publication"* (more verbose but clearer to a non-technical judge). VPS leans toward (a) — terse matches the Publish Gate's procedural voice. Charlie to confirm on Day 7 when the Publish Gate UI is built.
- **Q4: ~~What music bed style works best...~~** RESOLVED 2026-05-02: sourcing pulled forward to Day 6–7 (VPS-DEC-032). Style still picked during Day 9 dress rehearsal by ear under the anchor-story Narrator audio. The right bed is the one that makes Charlie tear up the third time.

### Optional features

- **Q5: Whether to layer in Optional Tier 2 (Gemini 3.1 Flash Live "talk to the room") if Day 9 has slack?** Decision deferred to Day 9 (VPS-DEC-026). If shipped, frame it as a "stretch" demo moment **on the live URL only** (not in the demo video — see VPS-DEC-030). The video stays autonomous-newsroom; the URL gets the interactive "talk to the room" affordance if there's slack.
- **Q6: Whether to include a "Days to LA28" counter in the top-right of every screen, per BUILD_SPEC §10.3 first-half-second test?** VPS recommendation: yes, low-effort high-value. Reinforces the Olympic-broadcast aesthetic and the LA28 momentum framing. Charlie's call.

### Scope discipline

- **Q8: Scope-cut hierarchy under time pressure** — RESOLVED 2026-05-06 (Day 5). The build is 4–5 days ahead of schedule on craft. Time pressure is no longer the binding constraint; *closing the spec/brief gaps identified in the Day-5 audit* is. Updated stance: cut nothing reflexively; instead, sequence so the highest-leverage gap closures (front door pre-seed; publish-gate aggregation fix; agent-graph Floor build) ship before any further polish. If a polish item or stretch feature competes for attention with one of the six Day-5 audit closures, the audit closure wins. Day 9 dress rehearsal becomes the new gate for "do we ship X or cut it" — by then all six closures should be done.

### Post-hackathon

- **Q7: Whether the post-hackathon paragraph in the Vision Doc should be in the Devpost text description as well?** VPS recommendation: yes, abbreviated. One paragraph showing judges this isn't just a hackathon project — it's a thesis with a portable architecture. The Vision Doc itself is not submitted; only excerpts go into the Devpost text. To be drafted as part of the Day 1–2 Devpost text outline (VPS-DEC-029).

### New Day-5 audit follow-up questions

- **Q9: Has continuous operation been launched yet?** VPS-DEC-008 / VPS-DEC-027 require the demo's anchor to come from organic system production. If everything on `/story` is fixtures (Mount Pleasant, Park City…) the architecture has not yet been *proven* to produce stories end-to-end. Verify with HoE Session 2. If not yet running, this becomes the highest-priority engineering item alongside the front-door fix — we have the schedule slack to run it for 2–3 days before Day 8 evening soft-rank.
- **Q10: What does the constellation page get renamed to?** VPS-DEC-038 calls for renaming current `/floor` to make room for the actual agent graph at `/floor`. Candidates: `/field`, `/discoveries`, `/the-pool`, `/candidates`. VPS lean: `/field` — short, broadcast-feeling, doesn't read as engineering jargon. HoE's call on the actual slug.
- **Q11: Does the Mount Pleasant story's `[NIL: 2r/1a]` audit footer come from the Storyteller catching its own draft, or from the NIL Redaction Layer catching the Storyteller's draft?** This matters for the trust signal. If the Storyteller pre-redacts before the Layer ever sees the text, the Layer's audit log shows zero work and PROJECT_BRIEF §14 fails. If the Layer is genuinely catching individual references the Storyteller produced, we can sharpen the audit display to show that work. HoE to confirm which is true.

---

## 7. Document Ecosystem

### Core project documents (repo root)

| Document | Location | Purpose | Update frequency | Owner |
|---|---|---|---|---|
| CONSTITUTION.md | `/CONSTITUTION.md` | The living operating standard. Six laws including Place over Person. Code Review Kill List. | When creative/architectural principles evolve | VPS + Charlie |
| PROJECT_BRIEF.md | `/PROJECT_BRIEF.md` | AUTHORITATIVE on legal/compliance/submission. NIL strict interpretation. Pre-Submission Verification Checklist. | When rules interpretation changes or new compliance items surface | VPS + Charlie |
| What_is_The_Storytellers_Room.md | `/What_is_The_Storytellers_Room.md` | Descriptive vision narrative. Place over Person and NIL Redaction Layer threaded throughout. | When the vision narrative needs sharpening | VPS |
| README.md | `/README.md` | Public-facing repo description. References Apache 2.0 license in first paragraph. | When the public framing changes | VPS + HoE |
| LICENSE | `/LICENSE` | Apache 2.0 full text. Day 1 priority #1. | Never (it's the license text) | HoE on Day 1 |

### Engineering & strategy documents (Docs/Engineering/ and Docs/VPS/)

| Document | Actual location | Purpose | Update frequency | Owner |
|---|---|---|---|---|
| BUILD_SPEC.md | `/Docs/Engineering/BUILD_SPEC.md` | Tactical implementation spec. Single source of truth for build details (agent prompts, schemas, Wire vocabulary, demo storyboard, sound design, 11-day phasing, acceptance criteria). | When implementation details evolve (HoE owns iteration) | HoE (with VPS review for product impact) |
| HOE-HANDOFF.md | `/Docs/Engineering/HOE-HANDOFF.md` | Engineering-side institutional memory. Code state, debugging, deploy verification, daily session log. | Each HoE session | HoE |
| VPS-HANDOFF.md | `/Docs/VPS/VPS-HANDOFF.md` | This document. Product strategy, demo decisions, judge-experience direction, positioning. | Each VPS session | VPS |

### Working documents (to be created during the build)

| Document | Location | Purpose | When created |
|---|---|---|---|
| `data/wire_vocabulary.json` | `/data/wire_vocabulary.json` | ~50 phrase fragments per agent. The library that prevents the Wire from sounding like ad copy. | Day 3 |
| Athlete registry seed | `/data/athlete_registry_snapshot.json` | Snapshot of BigQuery `athlete_registry` for version control. | Day 1-2 |
| Devpost text description outline | `/Docs/VPS/devpost-text-outline.md` | Structural outline of the submission's text description. Lead with Challenge 2 alignment, paragraph on parity (Challenge 1) + LA28 momentum (Challenge 3) as natural extensions, paragraph on the seven-agent cast with voice signatures, paragraph on the NIL Redaction Layer as architecture, paragraph on the post-hackathon thesis. | Day 1–2 (VPS-DEC-029); refined Day 9; final pass Day 10 |
| Demo storyboard timing sheet | `/Docs/Engineering/demo-storyboard-timing.md` | Per-second timing sheet for the 3-minute video. Built from BUILD_SPEC §11. | Day 9 |
| Demo voiceover script | `/Docs/Engineering/demo-voiceover-script.md` | Final voiceover script Charlie will record. **Initial draft Day 8** so the Narrator-vs-voiceover balance is testable during dress rehearsal; final on Day 9–10. | Day 8 (draft) → Day 9–10 (final) |
| Pre-submission verification log | (filled in PROJECT_BRIEF §14) | Filled checklist with timestamps and sign-offs. | Day 10 |

### External references

| Document | Location | Purpose |
|---|---|---|
| Devpost Official Rules | https://vibecodeforgoldwithgoogle.devpost.com/rules | The authoritative legal source. PROJECT_BRIEF §0, §5, §6, §7, §9, §10, §11 quote it verbatim. |
| Devpost FAQs | https://vibecodeforgoldwithgoogle.devpost.com/details/faqs | The supplementary clarifications. Useful for terminology and submission procedure. |

### Archived / reference

| Document | Notes |
|---|---|
| Original concept v1.0 (named-athlete newsroom) | Pre-pivot. Documented in VPS Session 0 investigation in HOE-HANDOFF Section 3. Not in repo as a separate file; the pivot reasoning lives in PROJECT_BRIEF §0 and HOE-HANDOFF Section 3 (Session 0 entry). |
| Neptune Constitution | Charlie's reusable constitution from his other project. Referenced as the philosophical predecessor to The Storyteller's Room Constitution. Not in this repo. |

---

## 8. Lessons Learned (Append-Only)

### Strategic lessons

1. **Read the rules before writing the spec.** The Pivot A+ moment came from re-reading the official rules in detail. The original "named-athlete newsroom" concept would have been disqualified at Stage One vetting. Reading the rules takes 30 minutes; rebuilding around a misread costs days. Hackathon rules are not a formality.

2. **Compliance constraints can become positioning weapons when made architectural.** A content-review approach to NIL safety would have been invisible to judges and brittle in implementation. A named "NIL Redaction Layer" with structured audit-log output is visible, testable, and turns the constraint into a credibility flex. The same logic applies to the Paralympic Equity Editor's veto power — what could have been a prompt instruction is instead an agent with structural authority. Architectural compliance is more credible than policy compliance.

3. **The judge is a customer with finite attention. Every product decision is a fight for that attention.** Three minutes is short. Five demo moments must land. Anything that doesn't serve at least one is noise. The Decision Filter (*"Does this serve one of the five demo moments?"*) is the strategic discipline that prevents scope creep from killing the submission.

4. **Pivot A+ made the project stronger, not weaker.** The forced switch from named-athlete newsroom to place-as-protagonist gave the project (a) direct alignment with Challenge 2, (b) a more original positioning ("most fan coverage starts with famous athletes; we start one layer deeper"), (c) a more sophisticated Echo Scout (era/region patterns instead of famous-name shorthand), and (d) the NIL Redaction Layer as a named architectural feature. Constraints can produce better products.

### Product lessons

5. **The five demo moments are the spine. Lock them early; don't re-litigate them.** Once locked, every product decision passes through the Decision Filter. Re-debating the demo moments mid-build wastes the 11-day window and creates spec drift the HoE can't track.

6. **Voice signatures are sacred.** If two agents sound alike on the Wire, the room dies. The Wire vocabulary library (~50 phrase fragments per agent) is product, not polish. The Storyteller's forbidden words list is product. The Narrator's documentary register is product.

7. **Hard things should look easy. Easy things should look hard. (The Buddy Rich principle.)** Database queries get wrapped in visible deliberation; multi-agent orchestration gets presented cleanly. The Wire's 70/30 thinking/milestone ratio is the implementation. A Wire that reads like a press release fails. A Wire that reads like sleeves rolled up wins.

8. **The Olympic broadcast aesthetic is not optional polish — it's the positioning.** Without the deep navy, gold accents, editorial serif, slow cinematic pacing, music bed, and curtain rise transition, this is "another AI app that processes Olympic data." With them, it's "the future of AI-native Olympic coverage." The aesthetic IS the product story.

9. **The Broadcast page is the most fragile demo moment.** If the Narrator voice is mechanical, if the music bed is wrong, if the curtain rise feels like a route transition — the entire demo collapses to "competent" instead of "memorable." VPS attention disproportionately on the Broadcast in Days 8-10.

10. **The Equity Editor intervention is the most distinctive demo moment.** No other Challenge 2 submission will have an agent visibly police the feed for parity in real time, with a structural intervention that the user can see causing a queue change. This is the 40% Impact lever and the proof that parity is a system property.

### Process lessons

11. **The HoE + VPS split works.** Engineering decisions (code, debugging, deploy) go in `Docs/Engineering/HOE-HANDOFF.md`. Product and strategic decisions (positioning, demo narrative, judge-experience direction, naming, voice signatures, aesthetic) go here. Neither document should duplicate the other. Cross-reference, don't copy.

12. **Decisions need "why" recorded at decision time.** Re-deriving reasoning days later is unreliable, especially in an 11-day build where context is constantly evicted. Every decision in this log includes its reasoning. The next VPS session can explain any decision to Charlie or to a judge because the reasoning is preserved.

13. **The Anchor Story selection on Day 9 is a discipline, not a shortcut.** Pre-selecting the anchor before Day 9 violates the "let the system produce it" discipline that is itself part of what makes the demo authentic. The system organically discovering the story IS the proof point that the architecture works.

14. **The 11-day window is real but not an excuse for lower quality.** "We didn't have time" is not a valid reason to ship a half-baked Broadcast page. If we don't have time, we cut scope, not quality. The mediocre version of all five demo moments loses; the excellent version of three demo moments + the disciplined cut of the other two could win. (Charlie's Product Standard, baked into both handoffs.)

15. **Submit Day 10 evening, not Day 11 evening.** Devpost servers crowd at the buzzer. Cloud Run deployments fail. Compliance discoveries (a stray NBC.com URL in a screen recording, a license badge that didn't render) need fix time. Day 11 is buffer for the things that always go wrong. (Charlie's discipline, encoded in both handoffs.)

### Strategic lessons from Session 1 (2026-05-02)

16. **Do not collapse an autonomous system into a request/response loop.** The hardest decision of Session 1 was whether to put the seed prompt in the demo video. The instinct ("show interactivity") was wrong. The product's positioning is *ambient, autonomous, editorial intelligence* — a room that works whether you watch or not. A typed prompt is *transactional, user-driven, request/response* — a different paradigm. The moment the judge sees a typed prompt in the video, the system gets re-categorized from "AI newsroom" to "chat interface with some flair." That re-categorization is fatal to the differentiation. **The general principle:** when two product modes serve different mental models, give them different artifacts. The demo video carries the autonomous claim; the live URL carries the interactive affordance. Two artifacts, two jobs. *(Refined Day 5 by Lesson 19 — affordance can be visible in the video as a still-frame as long as no interaction is shown.)*

17. **Two locked decisions that quietly fight each other are a strategic gap, not a feature.** VPS-DEC-006 (locked seed prompt) and VPS-DEC-008 (Equity-Editor-caused organic anchor) read as compatible on first pass. They aren't — they imply two different demo moments, and the storyboard has room for one. The lesson: when revising the handoff, search for pairs of decisions that operate in the same surface (in this case, the 3-minute video). Conflicts surface as gaps in the storyboard, not as obvious contradictions in the docs. Future VPS sessions should look for these whenever the storyboard is touched.

18. **Pull-forward is cheaper than pull-backward.** Three Session-1 decisions (Narrator voice test, music bed sourcing, Devpost text outline) all moved earlier. The cost of doing them sooner is hours; the cost of discovering a problem with them later is days. The general rule: any work that can be done earlier without blocking other work, *should* be done earlier in an 11-day window. The buffer is at the front, not the back, because the back is fixed by the deadline.

### Strategic lessons from Session 2 (2026-05-06, Day-5 audit)

19. **Audit against the Constitution AND the contest brief — separately.** Session 1's audits were Constitutional. They missed three things the contest announcement transcript made explicit (interactive tools for fans, fan-centric framing, GCP/AI-Studio shot requirement). The Constitution is our internal standard; the contest brief is the external scorecard. They overlap on most items (Apache 2.0, NIL prohibition, Cloud Run deploy, etc.) but the gap between them is exactly where positioning risk hides. Future audits run both passes separately: *"does this align with the Constitution?"* and *"does this address every framing word and submission requirement in the contest brief?"* Two questions, two passes, both required.

20. **Beautiful craft can move past spec without anyone noticing.** The current `/floor` constellation is gorgeous and avoids US-state-map geographic bias — Charlie's instinct to keep it is right. But it consumed the URL slot and conceptual scope that BUILD_SPEC §9 reserved for the seven-agent graph (Demo Moment #2). The drift wasn't a regression; it was a re-imagining that filled the same space with something different and better-looking. **The lesson:** when craft progresses, verify spec coverage as a separate axis. *"Is this beautiful?"* and *"Does this still deliver the demo moment the spec assigned to this surface?"* are different questions. A beautiful piece of craft that doesn't deliver its assigned demo moment is a hidden gap. Resolution is usually not "scrap the craft" but "name what was built honestly and build the missing piece next to it" (VPS-DEC-038).

21. **0/0/0 is the failure mode of well-disciplined compliance.** If our Storyteller is so well-trained that it never produces a draft with athlete names, the NIL Redaction Layer never has work to do, and the audit reads `0 redactions / 0 disambiguations / cleared`. That's *correct engineering* and *bad demo* — it makes the trust signal invisible. PROJECT_BRIEF §14 explicitly flags it (*"NIL Redaction Layer's audit log shows real redaction work (not all-zeros)"*). **The lesson:** architectural compliance must be *demonstrably exercised*, not just *correctly implemented*. We need at least one demonstration story whose source corpus contains athlete names so the Layer demonstrates its work in the audit. A trust signal you can't see is a trust signal that doesn't exist.

22. **The HoE's intuition on a UX problem is usually right; their UX solution may not be.** The HoE correctly identified the front-door comprehension gap in the Day-5 build review. Their proposed fix (kicker + display headline + dek + hero card grid homepage) was a Constitutional violation — exactly the SaaS landing-page pattern Constitution §11 forbids. **The lesson generalizes:** problem identification and solution design are different skills. When the HoE flags a UX problem, take it seriously *and* push back on the proposed solution if it operates at a different level than the Constitution is willing to operate at. The pattern: agree on the problem, design the fix together, anchor the fix in the Constitution. (Cross-ref: VPS-DEC-040.)

23. **The first-paint of the live URL is not the demo video.** Session 1 lessons treated the demo video as the highest-leverage artifact (VPS-DEC-010: "demo video is the submission artifact; the hosted URL is secondary"). Day-5 audit refined this: *the demo video is most-important among judged artifacts, but the live URL is most-important among judge experiences if a judge clicks through.* A live URL that paints "The room is quiet." centered on a black page kills the experience in 5 seconds, regardless of how good the video was. The lesson: **for any judge who clicks the URL after watching the video, the live URL's first paint *is* the demo video's epilogue.** Treat the live-URL first-paint as a co-equal first impression, not a secondary one.

24. **The vision narrative was written when we imagined the demo, not the product. When product priorities shift, re-read the Constitution literally rather than the narrative figuratively.** *What_is_The_Storytellers_Room.md* says *"you don't see a welcome screen, you see The Wire."* That phrasing trapped Session 1 and most of Session 2 into Wire-as-centerpiece designs. Constitution §11 — the *literal* binding text — actually says *"cinematic hero (a stylized landscape, not a person). Wire beginning to scroll."* The literal text supports either Wire-as-centerpiece OR story-hero-with-ambient-Wire. The vision narrative was descriptive of one possible interpretation; the Constitution constrains the space of acceptable interpretations. **The general rule:** when product priorities shift (Day 5: from "demo of an AI newsroom" to "fan engagement site that makes a great demo"), the canonical vision narrative may quietly become the wrong reference. The Constitution wins. The vision narrative is descriptive, not prescriptive (this is also stated explicitly in the document hierarchy section of CLAUDE.md and in the doc headers — but easy to forget under pressure). When in doubt: re-read the Constitution's literal §11 and Rule 6 text, then design from there. Multiple front-door designs can satisfy both — pick the one that serves the current product priority.

25. **A discovery surface's bias becomes a feature when it stops being singular.** Earlier sessions resisted a US-state map because it traps fans in geographic familiarity ("click my home state"). Correct concern *if the map is the only door*. With three doors (Map for geographic familiarity, Field for abstract patterns, Stories for chronological browsing), the Map's bias stops being a flaw and becomes a *fan motivation match*: the fan whose entry motivation is personal-geographic connection uses the Map; the fan motivated by curiosity-about-the-unfamiliar uses the Field; the fan who just wants what's new uses Stories. **The general rule:** when a discovery surface's bias is identified as a problem, ask whether the right fix is *removing the surface* or *adding sibling surfaces with complementary biases*. The latter is almost always the better answer in fan-engagement products.

26. **Halts must be surgical, not blanket.** A halt trigger written as *"if X fails, halt all reframe work"* is over-broad when most reframe work doesn't depend on X. The right halt language is *"halt the work whose foundation is X; proceed with the work whose foundations are independent."* Day-6 example: VPS set a halt for *"if probe doesn't reach `published_stories`, halt all reframe work"* — but rename `/floor`→`/field`, Broadcast autoplay-with-mute, the SSE handoff-event backend, and several frontend reframe items (new `/`, `/map`, story facets, "?" affordance) are independent of the chain bug fix and could proceed in parallel using fixture data. Only the chain-dependent items (Cloud Run deploy, candidates seed → continuous op, engineered demo audit corpus through real chain) genuinely required probe-pass. **The general rule:** when in doubt about a halt trigger, ask which specific items the bottleneck blocks, and let everything else proceed. This matters more in AI-first dev, where parallel worker capacity is high and serialization is artificial scarcity. Reviewer attention is the real bottleneck — concurrency should be tuned to that, not to chain-blocking conservatism.

---

## 9. How Charlie Works (Append-Only)

- **Solo founder.** Building The Storyteller's Room with AI-first development. Every coding session is an AI agent. He directs and reviews; agents implement.
- **Tiered session model.** VPS session = strategic, long-lived, owns product decisions and the demo. HoE session = strategic, long-lived, owns engineering decisions and code state. Execution sessions = fresh context, focused, receive scoped prompts from VPS or HoE. Charlie operates above all three as the founder.
- **Constitutional thinker.** Charlie wrote The Storyteller's Room Constitution (and Neptune's). He thinks in terms of physics vs orchestration, governance vs flow control, system properties vs prompt instructions. When in doubt, apply the Constitutional test: *"Is this WHAT the agent should do (orchestration — violation), or WHETHER the agent CAN do it (governance — required)?"*
- **Fix the system, then the symptoms.** Charlie's instinct is always "what product contract prevents this class of failure?" before "how do we patch this instance?" Example: the NIL Redaction Layer is a system contract that prevents the entire class of "name leaked through to user" failures.
- **Wants pushback at a co-founder level.** Charlie explicitly wants the VPS to challenge, debate, and "see around corners." Not a research assistant that silently files reports. Push back when something doesn't make sense. Surface strategic implications proactively, even uncomfortable ones.
- **Direct communicator.** Prefers concise, direct answers. Lead with the conclusion, not the reasoning. Skip preamble.
- **Trusts the tools.** Charlie's directive across his projects: *"We have AI agents. We have very powerful frontier LLMs. Lets use first principles. Remove friction. Trust these tools."* When the VPS reaches for safety nets out of nervousness, Charlie pulls the conversation back to first principles. Don't over-engineer the demo for hypothetical failure modes.
- **The Olympic broadcast is the bar.** When in doubt, ask: would NBC's Olympic editorial team be embarrassed to air this? If yes, raise the bar. If no, ship.
- **The Decision Filter is the discipline.** Every feature passes through *"Does this serve one of the five demo moments?"* Charlie will apply this filter aggressively during the build. The VPS should pre-apply it before bringing anything to Charlie.
- **Designs for models that don't exist yet.** Charlie's principle from Neptune. Architecture decisions that only make sense for today's model capability are scaffolding. Architecture decisions that make sense regardless of model capability are physics. Sovereignty, governance, evidence ledgers, audit trails — physics. Procedural prompt sections, tool-call interception, step-by-step instructions — scaffolding. The Storyteller's Room is built on physics: the seven-agent contract, the Wire's structural rules, the NIL Redaction Layer as Python guard, the Publish Gate's seven sub-stages. As Gemini 4 / Gemini 5 ship, the room gets better without code changes.
- **The 11-day window is real but not an excuse for lower quality.** Cut scope, not quality. The Product Standard at the top of HOE-HANDOFF captures this: *"We make product decisions and build sessions based on what serves the demo's emotional impact and architectural credibility — not what's fast, not what 'solves the immediate problem.'"*

---

## 10. Pointers to Other Documents

- **CONSTITUTION.md** (repo root) — creative and architectural principles. Re-read before each VPS session.
- **PROJECT_BRIEF.md** (repo root) — legal, compliance, submission requirements. **AUTHORITATIVE on rules.**
- **What_is_The_Storytellers_Room.md** (repo root) — descriptive vision narrative.
- **Docs/Engineering/BUILD_SPEC.md** — tactical implementation spec.
- **Docs/Engineering/HOE-HANDOFF.md** — engineering-side institutional memory.
- **Devpost rules** — https://vibecodeforgoldwithgoogle.devpost.com/rules
- **Devpost FAQs** — https://vibecodeforgoldwithgoogle.devpost.com/details/faqs

The repo lives at `/Users/charliereagan/projects/Google_Olympics_Hackathon`. This handoff lives at `Docs/VPS/VPS-HANDOFF.md`. The HoE handoff lives at `Docs/Engineering/HOE-HANDOFF.md`. The BUILD_SPEC lives at `Docs/Engineering/BUILD_SPEC.md`. The Constitution, Project Brief, and Vision Doc live in the repo root.
