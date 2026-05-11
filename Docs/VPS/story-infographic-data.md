# Story Infographic Data — Hand-Authored (Day 7 / Submission Day)

**From:** VPS Session 2
**Date:** 2026-05-11
**Purpose:** Hand-authored structured data to drive infographic treatments on the four Broadcast pages displayed on the homepage. Post-submission, this becomes the output of a Gemini Pro structured-output pass after the Storyteller drafts prose (see "Post-submission automation" at the end).

**Stories covered:**
1. Minnesota (hero) — wheelchair basketball state league
2. Mount Pleasant, Iowa — small-town wrestling and adaptive sport pipeline
3. Park City, Utah — winter mountain town built around the Olympic Winter Games Salt Lake City 2002 legacy
4. Colorado Springs, Colorado — old air base, the residency campus

**Compliance check applied to every entry:** no athlete names, no NGB names as sport substitutes, no protected marks, no third-party logos, no timing/scoring data, conditional phrasing for any forward-looking claim. Resource links are to neutral educational / governmental / archival sources only.

---

## 1. Minnesota (hero)

**Story ID:** `organic-CcBLDJv0y0mLzmWpQF5W` (or whatever the canonical ID is)

```json
{
  "story_id": "organic-minnesota-state-league",
  "infographic": {
    "sport_tags": ["adapted floor hockey", "wheelchair basketball", "Paralympic"],
    "big_numbers": [
      {
        "value": "6",
        "label": "Paralympic roster spots from this regional pipeline since 2004"
      },
      {
        "value": "30",
        "label": "Years of sanctioned high school adaptive athletics"
      }
    ],
    "timeline": [
      { "year": "1992", "label": "Structural integration of adaptive sports into the state high school league" },
      { "year": "2002", "label": "First global representation, roughly a decade after integration" },
      { "year": "2004", "label": "First Paralympic roster spot from the pipeline" },
      { "year": "2024", "label": "Three decades of uninterrupted state-league operation" }
    ],
    "place_markers": [
      {
        "place": "Robbinsdale, Minnesota",
        "role": "High school district running varsity adapted floor hockey under the state league"
      },
      {
        "place": "Golden Valley, Minnesota",
        "role": "Courage Kenny Rehabilitation Institute — early community foundation, 1990s"
      },
      {
        "place": "Marshall, Minnesota",
        "role": "Southwest Minnesota State University — collegiate wheelchair basketball continuation"
      }
    ],
    "resources": [
      {
        "label": "Courage Kenny Rehabilitation Institute · adaptive sports programs",
        "url_hint": "couragekenny.org or allinahealth.org/courage-kenny",
        "verify": true
      },
      {
        "label": "Minnesota State High School League · adapted athletics",
        "url_hint": "mshsl.org/adapted-athletics",
        "verify": true
      },
      {
        "label": "Southwest Minnesota State Mustangs · wheelchair basketball",
        "url_hint": "smsumustangs.com",
        "verify": true
      },
      {
        "label": "Olympedia · global Paralympic results archive",
        "url_hint": "olympedia.org",
        "verify": false
      }
    ]
  }
}
```

---

## 2. Mount Pleasant, Iowa

**Story ID:** `fixture-mount-pleasant`

```json
{
  "story_id": "fixture-mount-pleasant",
  "infographic": {
    "sport_tags": ["wrestling", "adaptive sport", "Olympic and Paralympic"],
    "big_numbers": [
      {
        "value": "8",
        "label": "Olympians and Paralympians from Henry County since 1972"
      },
      {
        "value": "8,500",
        "label": "Population of Mount Pleasant"
      },
      {
        "value": "3",
        "label": "Generations of wrestling coaching lineage"
      }
    ],
    "timeline": [
      { "year": "1968", "label": "High school wrestling room enters continuous use" },
      { "year": "1972", "label": "First Olympian from Mount Pleasant" },
      { "year": "1988", "label": "Second Olympian — pattern starts to take shape" },
      { "year": "2004", "label": "Community college adaptive sport program founded" },
      { "year": "2020", "label": "First Paralympian sent to the Games (Tokyo cycle)" }
    ],
    "place_markers": [
      {
        "place": "Mount Pleasant, Iowa",
        "role": "Population 8,500 · the wrestling room and the courthouse square"
      },
      {
        "place": "Henry County, Iowa",
        "role": "20,000-person county that produced eight Olympians and Paralympians"
      },
      {
        "place": "Iowa Wesleyan, Mount Pleasant",
        "role": "Adaptive athletics program — three counties served, since 2004"
      }
    ],
    "resources": [
      {
        "label": "Mount Pleasant Community School District",
        "url_hint": "mtpleasant.k12.ia.us",
        "verify": true
      },
      {
        "label": "Henry County historical society",
        "url_hint": "henrycountyiowa.us/history or similar",
        "verify": true
      },
      {
        "label": "Quad-City Times · hometown coverage",
        "url_hint": "qctimes.com",
        "verify": false
      },
      {
        "label": "Olympedia · Team USA historical results",
        "url_hint": "olympedia.org",
        "verify": false
      }
    ]
  }
}
```

---

## 3. Park City, Utah

**Story ID:** `fixture-park-city-utah`

**Note to HoE:** I drafted this without the full transcript in hand. Numbers and timeline entries are based on the homepage dek and public knowledge of Park City's Olympic legacy. Charlie or HoE should sanity-check the specific counts against the actual prose before publishing.

```json
{
  "story_id": "fixture-park-city-utah",
  "infographic": {
    "sport_tags": ["alpine skiing", "snowboarding", "bobsled", "Olympic Winter and Paralympic Winter"],
    "big_numbers": [
      {
        "value": "1:00 PM",
        "label": "School-day dismissal during winter season — schedule bent around the chairlift"
      },
      {
        "value": "2002",
        "label": "Olympic Winter Games and Paralympic Winter Games Salt Lake City — alpine and freestyle events hosted in Park City"
      }
    ],
    "timeline": [
      { "year": "2002", "label": "Olympic Winter Games Salt Lake City — Park City hosts alpine and freestyle events" },
      { "year": "2002", "label": "Utah Olympic Park established as a permanent training facility" },
      { "year": "2026", "label": "Generation of athletes whose first memory of the Games is the 2002 cycle now mid-career" }
    ],
    "place_markers": [
      {
        "place": "Park City, Utah",
        "role": "Mountain town where the public-school calendar bends around the chairlift schedule"
      },
      {
        "place": "Utah Olympic Park, Park City",
        "role": "Legacy training facility for bobsled, luge, ski jump, freestyle aerials"
      },
      {
        "place": "Park City School District",
        "role": "Public schools running early dismissal during the winter competition season"
      }
    ],
    "resources": [
      {
        "label": "Utah Olympic Park · public training facility",
        "url_hint": "utaholympiclegacy.org",
        "verify": true
      },
      {
        "label": "Park City School District",
        "url_hint": "pcschools.us",
        "verify": true
      },
      {
        "label": "Olympedia · Winter Games results archive",
        "url_hint": "olympedia.org",
        "verify": false
      }
    ]
  }
}
```

---

## 4. Colorado Springs, Colorado

**Story ID:** `organic-colorado-springs-air-base` (or whatever the canonical ID is)

```json
{
  "story_id": "organic-colorado-springs",
  "infographic": {
    "sport_tags": ["endurance training", "swimming", "track and field", "wheelchair basketball", "Olympic and Paralympic"],
    "big_numbers": [
      {
        "value": "6,000+",
        "label": "Feet of elevation — the air that demands a tax on the lungs"
      },
      {
        "value": "1978",
        "label": "Amateur Sports Act — the federal legislation that built the residency campus"
      },
      {
        "value": "120",
        "label": "Athletes in residence by 1996, up from 50 in 1980"
      }
    ],
    "timeline": [
      { "year": "1976", "label": "Ent Air Force Base deactivates" },
      { "year": "1978", "label": "Amateur Sports Act passes; residency campus established on the former base" },
      { "year": "1980", "label": "Roughly 50 athletes in residence" },
      { "year": "1996", "label": "Roughly 120 athletes in residence" },
      { "year": "2026", "label": "A unified residency for Olympic and Paralympic training across multiple sports" }
    ],
    "place_markers": [
      {
        "place": "Colorado Springs, Colorado",
        "role": "Population approaching 500,000 · the Front Range city built around the residency"
      },
      {
        "place": "former Ent Air Force Base",
        "role": "Historical site — the residency campus sits on these grounds"
      }
    ],
    "resources": [
      {
        "label": "Colorado Springs Pioneers Museum · regional history",
        "url_hint": "cspm.org",
        "verify": true
      },
      {
        "label": "Amateur Sports Act of 1978 · federal text",
        "url_hint": "congress.gov or govinfo.gov",
        "verify": true
      },
      {
        "label": "Olympedia · Team USA historical results",
        "url_hint": "olympedia.org",
        "verify": false
      }
    ]
  }
}
```

---

## Frontend rendering spec (for the HoE worker)

The HoE's worker spec for rendering the infographic block on a Broadcast page:

**Where it renders:** After the prose body, before the verified-claims drawer. Same column width as the prose (max-width ~720px center-aligned). Single section labeled `THE PLACE · BY THE NUMBERS` in tracked-cap parchment, gold hairline above and below.

**Section order within the infographic block:**

1. **Sport tags** — single horizontal row, mono caps, parchment, separated by gold middle-dot. *"WRESTLING · ADAPTIVE SPORT · OLYMPIC AND PARALYMPIC."*

2. **Big numbers** — horizontal flex row, up to 3 across on desktop, 1-per-row on mobile. Each: large Playfair Display numeral (72pt desktop, 48pt mobile), tracked-cap dek below (`14px parchment`), gold hairline divider between items. Generous whitespace.

3. **Timeline** — horizontal strip on desktop (~120px tall), gold dots on year marks with vertical gold hairlines dropping to small mono-cap year labels above and italic Lora event-labels below. On mobile, collapse to a vertical list with the same visual rhythm.

4. **Place markers** — three (or four) compact cards, equal-width on desktop, stacked on mobile. Each card: gold-thin border, deep navy fill, place name in italic Lora (16pt), role in tracked-cap parchment (11px). Optional small gold dot at top-left of each card.

5. **Elsewhere / Resources** — labeled `ELSEWHERE` in tracked-cap gold, then a vertical list of text links. Each row: italic Lora label, faint gold underline on link text. No icons, no logos. Links open in a new tab (`target="_blank" rel="noopener"`).

**Mobile responsive (VPS-DEC-046):** all five sub-blocks reflow to single-column at <768px. Big-number numerals scale to 48pt. Timeline goes vertical. Place markers stack. Resources stay single column.

**Compliance enforcement at render time:**

- The frontend renders only the JSON it receives. NO additional data is fetched or synthesized at render time.
- The frontend MUST NOT render any field that contains a forbidden term — but this is a backstop; the hand-authored JSON above is pre-screened.
- External links open in new tabs. Add the `Elsewhere` block ONLY if `resources` has at least one entry.

---

## Worker prompt fragment for the HoE

```
Render an infographic block on the Broadcast page using the structured-data JSON
from Docs/VPS/story-infographic-data.md.

The block renders AFTER the prose body and BEFORE the verified-claims drawer.
Section title in tracked-cap parchment: "THE PLACE · BY THE NUMBERS"

Render five sub-blocks in order (skip any whose JSON field is empty):

1. sport_tags — horizontal row, mono caps, gold middle-dot separators
2. big_numbers — flex row up to 3 across desktop, single column mobile,
   large Playfair numeral + tracked-cap label
3. timeline — horizontal strip on desktop with gold dots and year/label pairs,
   vertical list on mobile
4. place_markers — compact gold-bordered cards, 3-4 per row desktop,
   stacked on mobile
5. resources (labeled "ELSEWHERE") — vertical list of italic Lora text links,
   gold underline, target=_blank rel=noopener, no icons no logos

Mobile responsive at <768px per VPS-DEC-046. Big-number numerals scale to 48pt mobile.

Hand-authored JSON for the four stories is in
Docs/VPS/story-infographic-data.md and should be loaded as story metadata
(static import or fixture map keyed by story_id is fine; this becomes a Firestore
field post-submission per VPS-DEC-XXX below).

For url_hint fields where verify=true, the HoE should manually verify the URL
resolves to a live page before shipping. If the resolved URL is dead or wrong,
omit that resource entry rather than ship a broken link.
```

---

## Compliance final pass

Restating because every new visible artifact must clear the same checks:

- ✓ No individual Team USA athlete names anywhere in this data
- ✓ No NGB names presented as sport substitutes — sport tags use official sport names ("wheelchair basketball", "adapted floor hockey", "alpine skiing", "track and field")
- ✓ No protected marks — no Olympic rings, Agitos, LA28 logomark, torch, Team USA marks
- ✓ No third-party corporate logos other than Google Cloud — text links only
- ✓ No timing or scoring data — only counts, populations, years, elevations
- ✓ Forbidden terminology absent — no "former Olympian", no "past Olympian"
- ✓ Encouraged temporal phrasing used — "first Olympian", "first Paralympian", "first global representation"
- ✓ Conditional phrasing — no predictive claims in the big-number or timeline labels
- ✓ Games references use official naming — "Olympic Winter Games Salt Lake City" rather than "Salt Lake 2002 Olympics"

---

## Post-submission automation (VPS-DEC-055 candidate)

The hand-authored JSON above is the v1 path. Post-submission, this becomes the output of a structured-output pass added to the Storyteller / Publish Gate chain:

After the Storyteller produces prose and the Publish Gate clears it, a Gemini Pro structured-output call reads the Investigation Packet + prose body + verified claims and emits the same JSON schema (`sport_tags`, `big_numbers`, `timeline`, `place_markers`, `resources`). The output is then validated against the same compliance checks (no athlete names, neutral resource sources, encouraged-list temporal phrasing) before being persisted on the `published_stories` document.

This is the post-hackathon scaling story: at <$0.10 per story for prose + ~$0.02 for structured extraction, the room can produce explorable, link-rich Broadcast pages at the cost of one journalist's hourly rate for hundreds of stories.

Worth ratifying as a new decision after submission. Drafting now to preserve the spec; will land in VPS-HANDOFF after the contest closes.
