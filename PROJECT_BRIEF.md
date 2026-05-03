# THE STORYTELLER'S ROOM — PROJECT BRIEF

**Version:** 1.1 (Pivot A+ — Place over Person)
**Last Updated:** May 1, 2026
**Updated by:** Charlie Reagan + Claude Opus 4.7
**Sources:** [Official Rules](https://vibecodeforgoldwithgoogle.devpost.com/rules) and [FAQs](https://vibecodeforgoldwithgoogle.devpost.com/details/faqs)
**Status:** AUTHORITATIVE on legal, compliance, and submission requirements. Overrides BUILD_SPEC.md and CONSTITUTION.md if they conflict on these matters.

> _The judges will not award a prize to a project that breaks the rules — no matter how moving the demo._

---

## 0. CONCEPT LOCK — Pivot A+ (Place over Person)

The original product concept (an AI newsroom that finds and tells the stories of overlooked individual Team USA athletes) **conflicts with the hackathon's NIL rule**. That conflict was identified before any code was written. The pivot is locked.

### What the rules say (verbatim, with sources)

From the Official Rules, Section 6 ("Athlete Name, Image, and Likeness Protection") — https://vibecodeforgoldwithgoogle.devpost.com/rules:
> "There is a strict prohibition on the use of any athlete's Name, Image, or Likeness (NIL) in your submission. Your project can analyze data that is associated with an athlete by name, but the output should not be at the individual level."

From the FAQs ("Can I use any Olympics / IOC Content in my Project?") — https://vibecodeforgoldwithgoogle.devpost.com/details/faqs:
> "Likeness: No names, photos, or video of specific Team USA athletes."

From Section 6 ("Generative Media Restrictions"):
> "Submissions must not feature real people or any likeness of actual individuals whatsoever."

From Section 19:
> "Immediate disqualification will occur for any submission deemed inappropriate by Sponsor, or for those violating NIL, Brand, or Timing Data guidelines."

### The locked product

**The Storyteller's Room** is an AI broadcast room that finds, verifies, and tells the **hometown stories behind Team USA** — the places, programs, and patterns that produce Olympians and Paralympians. Not the athletes themselves. The communities that build them.

**Submission category:** **Challenge 2 — The Hometown Success Engine.** Direct alignment with the sponsor-defined challenge. Challenge 2 explicitly asks for "a tool that identifies 'Hubs' by correlating geography with the sports Team USA is present in" and to "focus on the number of Olympians/Paralympians from hometowns instead of the number of medalists."

**Story units are one of three types:**
- **Places** — towns, regions, geographic ecosystems (e.g., "Mount Pleasant, Iowa, eight Olympians since 1976")
- **Programs** — community sport infrastructure, training ecosystems, school/club pipelines (e.g., "an adaptive rowing program in Birmingham")
- **Patterns** — generational trends, regional clusters, sport-level momentum (e.g., "wheelchair rugby's Midwest pipeline since 2010")

**Why this works under the rules:** The output is at the place/program/pattern level, never the individual athlete level. Internal analysis can still query athlete-level data (the FAQ explicitly permits this); the user-facing output never exposes individual names.

**Why this works for the demo:** Places have stories. Communities have stories. Towns punching above their weight is itself a Cinderella narrative. The emotional Olympic hook survives intact. The Hometown Scout becomes the lead scout. The Paralympic Equity Editor still works — parity in *which places get covered* and depth of Paralympic context within each story.

### Why this could be stronger than the original concept

- **Direct Challenge 2 alignment** — competing in a sponsor-defined category instead of the Choose-Your-Own wildcard. Stage One vetting is cleaner.
- **The constraint becomes a trust signal** — the NIL Redaction Layer (see §5) is a named architectural feature that Google judges will *credit* rather than penalize.
- **Less crowded competitively** — most Challenge 2 submissions will be dashboards. We're submitting an AI broadcast room. The format differential is the moat.
- **The thesis is more original** — *"Most fan coverage starts with famous athletes. The Storyteller's Room starts one layer deeper — with the places that make Team USA possible."*

### The demo positioning line

In the demo voiceover, frame the pivot positively, not defensively:

> _"Every Team USA athlete comes from somewhere. We built an AI newsroom that finds the places where Team USA stories begin."_

**Do not** say *"The rules don't allow us to tell individual athlete stories."* That reads constrained or sour-grapes. Let the architecture speak. The Publish Gate's NIL Redaction Layer (visible in the audit log) is the trust signal — judges will notice it without being told.

---

## 1. EXECUTIVE SUMMARY — THE TEN THINGS THAT MATTER MOST

These are the items that, if we get any of them wrong, sink the submission. In rough order of severity.

1. **NIL prohibition.** No names, photos, or video of specific Team USA athletes in the output — including current, retired, and historical athletes. (Section 5.)
2. **Apache 2.0 license at the top of the README, visible in the GitHub About section.** Auto-DQ trigger if missing on Day 1. (Section 8.)
3. **No timing or scoring data.** Placement (1st, 2nd, 3rd) and medals are permitted. Finish times and specific scores are prohibited. (Section 6.)
4. **No corporate logos other than Google Cloud.** No NBC, no IOC, no Paralympic Agitos, no LA28 logomark, no torch, no rings. (Section 7.)
5. **Generative media must be animations only.** No photorealistic real people. (Section 9.)
6. **Restricted terminology must be honored.** Specific naming conventions for Games and athletes. Never "former" or "past" Olympian/Paralympian. (Section 10.)
7. **Public Team USA data only.** US scope only. Approved sources only. (Section 6.)
8. **Submit under Challenge 2 (Hometown Success Engine).** Direct alignment, not the wildcard. (Section 3.)
9. **No social media sharing during the contest.** Repo public for licensing, demo video unlisted on YouTube only. (Section 12.)
10. **Submit at least 24 hours before the deadline.** Deadline: May 11, 2026 at 5:00pm PT (8:00pm ET). Servers crowd at the buzzer. (Section 13.)

---

## 2. THE HACKATHON IN ONE PAGE

| Item | Value |
|---|---|
| Hackathon name | Team USA × Google Cloud Hackathon: Become a Team USA Analyst with Gemini |
| Sponsor | Google LLC |
| Administrator | Devpost, Inc. |
| Contest start | March 24, 2026 (already begun) |
| **Submission deadline** | **May 11, 2026 at 5:00pm PT (8:00pm ET)** |
| Judging period | May 12 – June 10, 2026 |
| Winners announced | On or around June 16, 2026 |
| Eligibility | Located in the United States, above age of majority |
| Total prize fund | $75,000 USD |
| Grand Prize | $15,000 USD + $3,000 GCP credits + swag + Google coffee |
| Challenge winners (5) | $8,000 USD + $2,000 GCP credits + swag + Google coffee |
| Honorable Mentions (4) | $5,000 USD + $1,000 GCP credits + swag |
| Submission cap | A submission can win one major cash prize maximum |

Three judging axes:

| Criterion | Weight | What it measures |
|---|---|---|
| Impact | 40% | Fan-centric question solved? Vision inspiring? Strong Paralympic representation? |
| Technical Depth & Execution | 30% | Does it work? Real or faked? Use of Gemini's advanced capabilities. New uses of Gemini and Google Cloud. |
| Presentation Quality | 30% | Video tells a powerful story? Demonstrates UX clearly? Viral potential? Respects content restrictions? |

---

## 3. CHALLENGE SELECTION — CHALLENGE 2

We submit under **Challenge 2: The Hometown Success Engine.** From the Rules:

> "Build a tool that identifies 'Hubs' by correlating geography with the sports Team USA is present in. Focus on the number of Olympians/Paralympians from hometowns instead of the number of medalists to be inclusive of all athletes. Avoid implying that geography guarantees results; use conditional phrasing like 'could help find'."

### Why Challenge 2 is the primary fit

- **Place-as-protagonist storytelling is exactly what Challenge 2 asks for.** Hometown hubs. Geographic correlation. Counts of Olympians and Paralympians from hometowns.
- **The "could help find" conditional phrasing requirement** maps cleanly to our Storyteller's existing constraints (no predictive language).
- **The "inclusive of all athletes" framing** maps cleanly to the Paralympic Equity Editor's parity work.

### What we say in the submission text description

The submission is a Challenge 2 entry, but we explicitly note that **the product also addresses parity (Challenge 1) and LA28 momentum (Challenge 3)** as natural byproducts of the architecture. That gives judges multiple reasons to give us a high score on Impact.

---

## 4. MANDATORY SUBMISSION COMPONENTS

Per Official Rules Section 6, every submission must include:

- [ ] A working Project built primarily on Google Cloud, using at least one Gemini model.
- [ ] **Hosted URL** — live, working, accessible to judges. Cloud Run.
- [ ] **Public code repository** with **Apache 2.0 license** detectable in the About section.
- [ ] **Comprehensive text description** in English — features, functionality, technologies used, data sources, findings.
- [ ] **Demo video, max 3 minutes**, English or with English subtitles, unlisted on YouTube.
- [ ] Demo video must show: (a) live demo of the project, (b) Gemini and Google Cloud usage, with the GCP console, AI Studio, or code visible at some point.
- [ ] Demo video and thumbnail must comply with all NIL and content restrictions.
- [ ] Selected challenge category: **Challenge 2 (Hometown Success Engine)**.

---

## 5. THE NIL RULE — STRICT INTERPRETATION

This is the most consequential rule for this project. It deserves its own section.

### What is prohibited (in any user-facing surface)

- **No athlete names** — current, retired, or historical. This includes:
  - Active Team USA athletes (any sport, any era)
  - Retired Team USA Olympians and Paralympians (any era)
  - Historical American Olympic figures (Wilma Rudolph, Jesse Owens, Jim Thorpe, etc.) — strict reading; no carve-out for deceased athletes
- **No photos** of any Team USA athlete (real or AI-generated).
- **No videos** of any Team USA athlete (real or AI-generated).
- **No likenesses** of any Team USA athlete — including stylized illustrations recognizable as a specific person.
- **No biographical detail combinations that uniquely identify** an individual athlete.

### What is permitted

- **Internal analysis by name** — agents can query data tagged with athlete names, look up named athletes' public records, and reason about specific individuals internally. This stays inside the system.
- **Aggregate references** — counts, patterns, regional data, archetypes, sport-level trends. *"Mount Pleasant has produced 8 Olympians and Paralympians since 1976."*
- **Source links to public articles** — the Publish Gate's audit log can include URLs to source articles that name athletes (those articles are public). The audit drawer doesn't censor source URLs. **But the Storyteller never quotes or names the athletes from those sources.**
- **Place names, town names, region names, sport names, era references, Games references** — all fully permitted.
- **Coach names and other non-athlete public figures** — *only when their public role is non-athletic*. Naming a coach + a place + a sport may indirectly identify the athletes the coach trained. The NIL Redaction Layer's near-identification check should catch this.

### The Echo Scout under the strict reading

The Echo Scout's job is to find modern stories that rhyme with iconic Olympic moments. Under strict NIL, the Echo Scout cites **eras, Games, regions, sports, and patterns** — never named athletes.

| Old (prohibited) | New (compliant) |
|---|---|
| "This rhymes with Wilma Rudolph 1960." | "This echoes a 1960 Rome sprint-era pattern." |
| "The arc matches Jesse Owens 1936." | "This echoes the pre-war track-and-field era when American regional systems became global stories." |
| "This is the Kerri Strug story." | "This is a 1996 gymnastics-era moment of competing-through-injury that defined the public memory of those Games." |

This actually makes the Echo Scout *more* sophisticated — less dependent on famous-name shorthand, more grounded in historical patterns and place-based dynamics.

### The NIL Redaction Layer (architectural enforcement)

The NIL Redaction Layer is a named architectural feature of The Storyteller's Room. It is sub-stage 4 of the Publish Gate's audit log. **See CONSTITUTION.md §7 and BUILD_SPEC.md for the full implementation specification.** Its job:

1. Maintain a registry of all athlete names from the internal corpus (BigQuery `athlete_registry`).
2. Scan every text artifact bound for a user-facing surface (Wire, Broadcast, demo).
3. Detect direct name matches, near-identifications, and small-aggregate identifications.
4. Take one of three actions: pass / aggregate / return-to-Storyteller for revision.
5. Log structured audit entries: *"4 individual references reviewed. 2 aggregated. 2 redacted. Cleared."*

When the demo's trust-layer beat opens the Evidence Drawer, the NIL Redaction Layer's work is visible. **The constraint becomes the credibility flex.** Architectural compliance is the trust signal a thoughtful Google judge will credit.

### The Publish Gate's audit log structure

Per BUILD_SPEC.md §5.7, the Publish Gate's audit log shows seven sub-stages:

1. **Fact Check** — claims verified against the Investigation Packet's sources.
2. **Source Review** — public sources cited, citations attached.
3. **Parity Review** — Paralympic Equity Editor sign-off confirmed.
4. **NIL Redaction Review** — *(named architectural feature; see above)* individual references reviewed, aggregated, or redacted.
5. **Safety Review** — invented quotes check, private-info check.
6. **Language Review** — restricted terminology check, conditional phrasing softening.
7. **Visual Review** — generated images checked for photorealism, athlete likenesses, protected marks.

---

## 6. APPROVED DATA SOURCES AND DATA RULES

### Approved sources (per Official Rules and FAQ)

- **Official Team USA website** — [www.teamusa.com](http://www.teamusa.com). Results data, athlete profiles, blog content.
- **Open source repositories** — historical athlete performance and macro Olympics data, **filtered for Team USA athletes only**.
- **Public weather data** — NOAA and similar open-source sources.

### Data scope rules

- **US scope only.** International Olympic and Paralympic datasets are prohibited *unless filtered for US athletes only*. If we ingest Olympedia or any global source, the BigQuery loader must filter to Team USA before any agent queries the data.
- **Public data only.** Private records, leaked data, or anything requiring authentication is prohibited.

### Permitted data fields

- Finish placement (1st, 2nd, 3rd) — permitted.
- Medals (gold, silver, bronze) — permitted.
- Athlete biographical data from public sources — permitted internally; output cannot be individual-level.
- Hometown geography, population, regional data — permitted (this is the heart of Pivot A+).
- World Championship placement counts — permitted.
- Public school records, community programs, local press coverage — permitted as place/program context.

### Prohibited data fields (auto-DQ if used)

- **Finish times.** Any specific time (e.g., "9.79 seconds") is prohibited.
- **Specific scoring results.** Any specific score (e.g., "16.733 in vault execution") is prohibited.
- **Team USA multimedia showing athlete name, image, or likeness.**

### Confidentiality

- Team USA data is confidential per Section 11 of the Rules.
- Cannot be used for commercial purposes during or after the hackathon.
- Must be destroyed at conclusion of the hackathon.
- Cannot be shared with third parties.

---

## 7. BRANDING AND TRADEMARK RULES

### Strict ban on the following marks (auto-DQ if used)

- **Olympic rings** — five-ring logo, in any color, in any context.
- **Olympic torch** — official torch imagery.
- **Paralympic Agitos** — three-crescent logo.
- **LA28 logomark** — official LA28 graphic identity.
- **USOPC logos** or marks.
- **Team USA logos** — strict prohibition unless rules confirm permission (they do not).
- **Any third-party corporate logo or trademark** — including but not limited to NBC, ESPN, sport equipment brands, sponsor logos.

### What is permitted

- **Google Cloud branding** — required to be visible in the demo video.
- **Generic graphic design** in the spirit of Olympic broadcast — deep navy color schemes, gold accents, editorial typography, lower-third graphics. We borrow the *visual language* of Olympic broadcast without lifting any specific mark.

### Practical implications for our build

- **The Broadcast page's hero illustration must not contain any of the above marks.** The Visualizer's prompts to Nano Banana Pro and Nano Banana 2 must be written to explicitly exclude rings, Agitos, torch, LA28 logomark, Team USA logos. The Visual Review sub-stage of the Publish Gate must check generated images for accidental inclusion.
- **The Wire and Floor must not contain any of the above marks** in their UI chrome, agent nameplates, or graph nodes.
- **The demo video must not show any third-party logo** other than Google Cloud — including in the background of any screen recording. Be careful about screen captures that include browser bookmarks bars, notifications, or other ambient UI.
- **The app title is "The Storyteller's Room"** — not "Olympic Storyteller's Room" or anything containing "Olympic" or "Paralympic" as part of the title (per FAQ guidance).

---

## 8. APACHE 2.0 LICENSE — DAY 1 REQUIREMENT

Per Official Rules Section 6 and FAQ guidance:

> The code repository must be licensed under the Apache License 2.0. **This license should be detectable and visible at the top of the repository page (in the About section).**

### Day 1 actions

- [ ] Create a `LICENSE` file in the repo root containing the full Apache 2.0 license text.
- [ ] Set the GitHub repository's License field (in repo Settings or via the About sidebar) to "Apache License 2.0" so the badge appears in the About section.
- [ ] Verify the license badge is visible on the public repo page.
- [ ] Add a license header comment to the top of significant source files (optional but recommended).
- [ ] Note in the README's first paragraph: "Licensed under Apache License 2.0."

### Why this is high-priority

The Stage One vetting will check this. A missing or incorrectly-displayed license is a Stage One failure, and Stage One failures don't get judged at Stage Two regardless of how good the project is. This is a 5-minute Day 1 task. Do it before writing any code.

---

## 9. GENERATIVE MEDIA RULES

### What the Rules and FAQs say (verbatim):

> **Generative Media Restrictions:** For any generative media (AI-generated images or video), participants must use animations only. Submissions must not feature real people or any likeness of actual individuals whatsoever.

> **Q: Can I use GenAI to create images for my project?**
> A: Yes, however all GenAI Media MUST be animations ONLY (ie: no real people/athletes).

### Our approach

To be maximally safe under both possible interpretations of "animations only":

- **All generated images are stylized, illustrative, painterly** — Sports Illustrated cover style, Olympic broadcast opening package style. Never photorealistic.
- **Hero images depict places, landscapes, communities, facilities, equipment, silhouettes** — not identifiable individuals.
- **Hero illustrations include subtle Ken Burns motion** in the frontend — this satisfies "animation" under one interpretation without requiring full video generation.
- **No use of Veo 3.1** (video generation) — adds complexity and risk without benefit.

### Visualizer prompt rules

Every prompt sent to Nano Banana Pro or Nano Banana 2 must include explicit constraints:

- "stylized illustration, NOT photorealistic"
- "no identifiable faces, no likenesses of any real person"
- "no Olympic rings, no Paralympic Agitos, no torch, no LA28 logomark, no Team USA marks, no corporate logos"
- "subject is a place / landscape / community / training facility / equipment — NOT a portrait of a person"

The Publish Gate's Visual Review sub-stage validates the output against these constraints. Failed images regenerate with a more restrictive prompt.

---

## 10. RESTRICTED TERMINOLOGY

The rules specify exact terminology for referring to Games and athletes.

### Games naming conventions

| Reference | Required form | Approved secondary |
|---|---|---|
| Winter Games | "Olympic Winter Games [City] [Year]" e.g., "Olympic Winter Games Beijing 2022" | "The Winter Olympics" or "[City] [Year]" |
| Winter Paralympic Games | "Paralympic Winter Games [City] [Year]" | — |
| Summer Games (non-LA) | "Olympic Games [City] [Year]" e.g., "Olympic Games Paris 2024" | — |
| LA28 | "LA28 Games" or "LA28 Olympic and Paralympic Games" | — |

### Athlete terminology

- **Never "former Olympian"** or **"past Olympian"** — once an athlete is an Olympian/Paralympian, they are always one.
- **Same rule applies to "former Paralympian" and "past Paralympian."**
- **Also forbidden:** "ex-Olympian," "retired Olympian" (when used as a label of identity), and any equivalent construction that frames the status as ended.

### Temporal phrasing about places, programs, and patterns (encouraged)

The forbidden-words list above bans constructions that frame an *athlete's identity* as ended. It does NOT ban temporal phrasing about places, programs, or patterns — and the Pivot A+ place stories actively need that phrasing to land.

- **Encouraged:** "first," "next," "newest," "earliest," "most recent," "oldest" applied to a place's or program's representation. Examples:
  - *"The town's first Olympian came in 1964."*
  - *"The program's next Olympian arrived two decades later."*
  - *"The newest Paralympian from this region competed in 2024."*
  - *"The earliest documented Team USA pipeline in this county dates to 1932."*
- **Forbidden (as above):** "former Olympian," "past Olympian," "ex-Olympian," "retired Olympian," and equivalents.

The Storyteller's prompt must include BOTH lists. The Publish Gate's Language Review sub-stage flags violations of the forbidden list but should NOT flag the encouraged constructions. (Cross-ref: VPS-DEC-033, CONSTITUTION Law 5.)

### Sport names

- Use the **official sport name**, not the National Governing Body name.
- Example: "swimming" — not "USA Swimming."
- Example: "track and field" — not "USATF."

### Implementation in the Storyteller's prompt

The Storyteller's system prompt must include a hard constraint listing these rules. The Publish Gate's Language Review sub-stage must check for violations.

---

## 11. CONDITIONAL PHRASING (No predictions, no guarantees)

Per the challenge descriptions and the Rules' Section 6, the project must use conditional phrasing for any forward-looking or interpretive claim.

Challenge 2's specific guidance: *"Avoid implying that geography guarantees results; use conditional phrasing like 'could help find'."*

### Required phrasing

- "could lead to"
- "may indicate"
- "has historically aligned with"
- "could help find"
- "may suggest"
- "tends to correlate with"

### Prohibited phrasing

- "will result in"
- "guarantees"
- "predicts"
- "ensures"
- "this means"
- "this proves"

The Storyteller's prompt enforces this. The Publish Gate's Language Review sub-stage validates and softens any predictive language.

---

## 12. SOCIAL MEDIA AND SHARING RESTRICTIONS

Per the Rules and FAQ:

> Participants are strictly prohibited from publicly sharing project details, source code, or demo videos including on any social media platform (including LinkedIn, X, and YouTube) **except the demo video as unlisted on YouTube for the purposes of submission** or unless otherwise authorized by the Sponsor.

### What is prohibited

- **No tweets, X posts, LinkedIn updates, or other social media** about the project, the build, the architecture, or the demo before, during, or after the contest period (unless explicitly authorized).
- **No public YouTube videos** about the project. The demo video must be unlisted.
- **No blog posts, podcasts, or media interviews** discussing the project.
- **No "I'm building..." progress updates** on social media.

### What is permitted

- The **public code repository** with Apache 2.0 license (required for submission).
- The **unlisted YouTube demo video** linked from the Devpost submission.
- **Private conversations** — internal notes, this brief, the Constitution, the BUILD_SPEC, communication with collaborators are all fine.

### Why this is tricky

- Charlie (and Neptune) has a public profile. The temptation to share progress is real. **It must not happen** for this project.
- Coding agents may suggest social media drafts, README entries that double as marketing copy, or "share-this-on-Twitter" buttons. Reject these suggestions.
- The README itself is the one public artifact we control. It can describe the project clearly but should be written as documentation, not marketing.

### After winning

If we win, the Sponsor may authorize specific social media messaging. Until that authorization arrives, even winning is silent.

---

## 13. SUBMISSION DEADLINE AND TIMING

### The hard deadline

**May 11, 2026 at 5:00pm Pacific Time = 8:00pm Eastern Time.**

### Our internal deadline

**Submit by end of day Sunday, May 10, 2026.** Approximately 24 hours of buffer.

### Why the buffer matters

- Devpost servers crowd at the buzzer.
- Last-minute compliance discoveries need time to fix.
- Cloud Run deployments can fail. If the deployment goes down on the morning of submission, we need time to redeploy.

### The judging period considerations

- The hosted project must remain live through **June 10, 2026**. Do not tear down infrastructure before then.
- Google Cloud credits must last through judging. Set budget alerts.
- Per FAQ: judges may test the project but are not required to. Many will judge based on the video and text description alone. The video is the primary judged artifact.

---

## 14. PRE-SUBMISSION VERIFICATION CHECKLIST

Run this checklist before clicking submit. Every item must be verified.

### License and repo
- [ ] Apache 2.0 license file in repo root
- [ ] License badge visible on the public GitHub repo's About section
- [ ] Repo is public
- [ ] README references the license in the first paragraph
- [ ] No competitor logos, IOC marks, or third-party trademarks in any committed file
- [ ] No hardcoded individual athlete names in any user-facing code path or test fixture

### Hosted project
- [ ] Hosted URL is live and accessible without authentication
- [ ] All seven agents are operational
- [ ] BigQuery, Firestore, Cloud Storage are in active use (visible in GCP console)
- [ ] No errors in Cloud Run logs
- [ ] Budget alerts configured
- [ ] NIL Redaction Layer is wired into both the Wire emission path and the Broadcast publish path

### Demo video
- [ ] Maximum 3:00 in length
- [ ] Uploaded to YouTube as **unlisted** (not public, not private)
- [ ] English audio or English subtitles
- [ ] Shows live demo of the project (not mockups)
- [ ] Shows Google Cloud console, AI Studio, or code at some point
- [ ] Contains no athlete names, photos, or likenesses
- [ ] Contains no Olympic rings, torch, Paralympic Agitos, or LA28 logomark
- [ ] Contains no third-party corporate logos other than Google Cloud
- [ ] Uses only royalty-free music (Epidemic Sound, Artlist, or equivalent license confirmed)
- [ ] Contains no Games footage from any past Olympics or Paralympics
- [ ] Uses approved Games terminology throughout
- [ ] Does not use "former" or "past" Olympian/Paralympian
- [ ] Does not use NGB names where sport names belong
- [ ] Uses conditional phrasing for any analytical claim
- [ ] The framing line is positive (*"Every Team USA athlete comes from somewhere..."*) not defensive (*"The rules don't allow us to..."*)

### NIL safety (specific to Pivot A+)
- [ ] No athlete names in any UI shown in the video
- [ ] No athlete names in any Broadcast page output rendered in the video
- [ ] No athlete photos or videos shown
- [ ] No identifiable athletic likenesses generated in hero images
- [ ] Hero images show places, landscapes, communities, facilities, equipment, silhouettes — never portraits
- [ ] NIL Redaction Layer's audit log shows real redaction work (not all-zeros)
- [ ] Browser tabs, bookmarks, and notifications are hidden in screen recordings

### Submission form
- [ ] Challenge category selected: **Challenge 2 (Hometown Success Engine)**
- [ ] Hosted URL filled in
- [ ] Public repo URL filled in
- [ ] Text description complete in English (features, functionality, technologies, data sources, findings)
- [ ] Text description mentions parity (Challenge 1) and LA28 momentum (Challenge 3) as natural extensions of the architecture
- [ ] Demo video URL (unlisted YouTube) filled in
- [ ] All required fields complete

### Final
- [ ] All four documents (Constitution, Build Spec, Vision Doc, Project Brief) reflect the final project state
- [ ] No changes pending in the working tree of the repo
- [ ] Final commit is on `main` and deployed
- [ ] Saved a screenshot of the GitHub repo About section showing the Apache 2.0 badge for our records

---

## 15. DAILY / PER-COMMIT CHECKLIST FOR CLAUDE CODE

Every coding session, every commit, every pull request:

- [ ] **Check the Devpost Updates and Discussions tabs** at https://vibecodeforgoldwithgoogle.devpost.com/updates and https://vibecodeforgoldwithgoogle.devpost.com/discussions for any new sponsor clarifications. The contest is mid-flight; rules clarifications can land any day. Five-minute check, catches a class of late-breaking compliance shifts. (VPS-DEC-034.)
- [ ] No individual athlete names introduced in user-facing strings, prompts, UI components, or test data
- [ ] No Olympic-restricted terminology used incorrectly (forbidden: "former Olympian," "past Olympian," "ex-Olympian," "retired Olympian"; encouraged for places: "first," "next," "newest," "earliest")
- [ ] No new third-party logos introduced
- [ ] No new public-data sources outside the approved list
- [ ] No finish times or scoring results introduced into BigQuery schemas or sample data
- [ ] No predictive phrasing without conditional softening
- [ ] No social-media-share buttons, no marketing copy, no "tell your friends" UX
- [ ] **No typed user prompt added to the demo video.** The seed prompt lives only on the live URL hero. (VPS-DEC-030.)
- [ ] If a generated image is committed, it has been visually verified to contain no real-person likenesses or restricted marks
- [ ] If a Storyteller prompt is updated, it still includes the forbidden-words list (Section 10), the encouraged temporal-phrasing list (Section 10), and the Place-over-Person constraint (Section 5)
- [ ] If the Publish Gate's audit log structure is changed, it still produces output for all 7 sub-stages including NIL Redaction Review
- [ ] The NIL Redaction Layer is invoked on every path that emits text to a user-facing surface (Wire, Broadcast, demo)
- [ ] On URL load, the Wire is pre-seeded with recent published events (`mode: replay`) so the room "scrolls" within <1s of arrival. (VPS-DEC-028.)

---

## 16. RULE-CONFLICT RESOLUTION

If any document or instruction conflicts with this brief on legal or compliance matters:

- **This Project Brief wins** for legal/compliance/submission requirements.
- **The Constitution wins** for creative/architectural principles.
- **The Build Spec wins** for tactical implementation.
- **The Vision Doc** is descriptive, not prescriptive, and never overrides any of the above.

If something seems to conflict and isn't covered above, escalate to Charlie before proceeding.

---

## 17. INTELLECTUAL PROPERTY NOTES

- **We retain ownership** of our project's intellectual property and the source code (per Section 13 of the Rules).
- **We grant Google a license** under Apache 2.0 for the non-proprietary aspects of the submission and source code, as required for the contest.
- **We grant Google and the Supporting Parties** a perpetual, irrevocable, worldwide, royalty-free license to use, reproduce, distribute, and create derivative works from the demo video — for evaluation and for promotional purposes.
- **We do not acquire any rights** in Team USA Data. The data must be destroyed at the end of the contest.

The Apache 2.0 license is required and it does not prevent us from commercializing the project after the hackathon. The Supporting Parties (USOPC, LA28) are explicitly **not sponsors** of the hackathon, so winning does not create any partnership or endorsement relationship with them.

---

## 18. POST-SUBMISSION

Between submission (May 11) and winners announcement (June 16):

- Keep the hosted project live through **June 10, 2026** at minimum.
- Monitor Cloud Run logs for outages.
- Do not modify the submission unless explicitly authorized by the Sponsor.
- Do not share the project on social media unless explicitly authorized.
- Be prepared to provide the Required Forms (W-9 for US residents) within 10 business days of being notified as a winner.

After winners are announced (on or around June 16):

- Authorized social sharing may be permitted by the Sponsor — wait for explicit authorization.
- Cash prizes are delivered within 60 days of the Required Forms being received.

---

## DOCUMENT USAGE

- **For the operator (Charlie):** Read before submission. Re-read on Day 10 before final pre-submission verification.
- **For Claude Code:** Reference Sections 5, 7, 9, 10, 11 every coding session. Use Section 15 as a per-commit checklist. The CONCEPT LOCK in Section 0 is final — Pivot A+ is binding.
- **For research and content agents:** Reference Sections 5, 6, 10, 11 for every research task.
- **For the demo video editor:** Reference Section 14 before exporting the final cut.

---

**Final reminder:**

> _The judges will not award a prize to a project that breaks the rules. The Stage One vetting is pass/fail and unforgiving._
>
> _Disqualification triggers — NIL, brands, timing data — are not edge cases. They are systematically checked._
>
> _When in doubt, cut the offending element. The room can succeed without naming a single athlete. It cannot succeed if it gets disqualified._

Compliance is the floor.
Excellence is the ceiling.
The NIL Redaction Layer is the trust signal that makes them the same surface.
