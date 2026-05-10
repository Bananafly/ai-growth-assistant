---
name: growth-week
description: |
  Plan and draft a week of focused reading for one personal growth area. Sources
  high-quality material from a per-area trusted-domain list, drops it into a
  markdown file, then renders to EPUB + KEPUB for Kobo. Use when the user says
  "growth week", "draft this week's reading", "/growth-week", or names an area
  they want curated reading for (e.g. "draft ai-future for next week").
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - WebFetch
  - WebSearch
---

# growth-week

Generate one week's curated reading for a single growth area. Output is a
markdown file under `weeks/` and matching `.epub` + `.kepub.epub` artifacts.

## Invocation

User runs `/growth-week <area>` where `<area>` matches a file at
`areas/<area>.yaml`. If no `<area>` given, list available areas and ask which.

## Steps

### 1. Load the area definition

Read `areas/<area>.yaml`. If any REQUIRED field is missing or still says
`TODO_FILL_THIS_IN`, **stop** and tell the user the file isn't ready yet —
they need to fill it in before the skill can produce useful reading.

### 2. Determine the week's focus

Compute the ISO week tag: `date +%G-W%V` → e.g. `2026-W19`. (`%G` is the
ISO week-numbering year, which can differ from `%Y` at year boundaries.)

Pick this week's focus:
- If `state/<area>.yaml` exists and has a `wants_next_week` field, use that.
- Else, advance through `area.focus_areas` (cycle: pick the one that hasn't
  been used recently — check `weeks/` filenames or `state/` for prior focuses).
- Else, default to the first item in `area.focus_areas`.

### 3. Calibrate difficulty (probe what the user knows BEFORE sourcing)

Do not skip this step. The user's growth happens at the edge of what they
already know; reading pitched too high lands as jargon, pitched too low
produces no movement. Aim for "one notch above current confidence."

Ask the user 2–3 short questions about this week's focus, mixing open and
calibrated:

- **Open:** "What's your current mental model of `<focus>`? One or two sentences."
- **Calibrated:** "Confidence 1–5 on each of: `<3-5 sub-concepts within the focus>`."
- **Anchor (optional):** "Anything related you DO know well that this might
  connect to?"

Use the answers to set difficulty:
- If confidence is 1–2 → start with introductions / "what is X" pieces, then
  one step into mechanism. Avoid papers.
- If confidence is 3 → mix one explanation/intro with one practitioner post
  and one paper or current research piece.
- If confidence is 4–5 → skip the introductions; go straight to current
  research, postmortems, and contested takes.

Never pitch two notches above current confidence — produces frustration, not
growth. If unsure, err one notch low and let the user signal "harder next
time" via the EOW review.

If `state/<area>.yaml` exists, append the probe Q&A to it as a dated entry.
This becomes the running record of how the user's mental model evolves.

### 4. Source candidate reading (the central technical risk)

In strict priority order:

**a) Seed sources first.** For each entry in `area.seed_sources`, `WebFetch`
its index/feed (try `/feed`, `/feed.xml`, `/atom.xml`, `/rss`, or the bare
domain). Scan titles + dates for posts matching this week's focus. Keep 1–2
strong matches per seed source.

**b) Targeted search second.** Run `WebSearch` with a narrow query that names
the focus concretely (not "AI evals" — "designing offline evals for tool-using
LLM agents"). For each result, **only accept the URL if its domain is in the
allowlist**:
- `arxiv.org`
- Every domain in `area.seed_sources`
- Well-known author personal sites you recognize as authoritative for this
  area (use judgment; reject anything you're unsure about)

Reject anything in `area.exclude_domains`. Reject aggregators (HN, Reddit,
Twitter), marketing/SEO blogs, and paywalled posts with no preview.

**c) Stop early.** If you have 3–5 quality sources, stop searching. **3
focused beats 5 padded.** Don't fill space.

### 5. Read and assemble

For each accepted source:
- `WebFetch` the full article. If it's paywalled or JS-heavy and the fetch
  returns junk, log it as `<!-- skipped: paywalled --> <url>` in the markdown
  and substitute the next-best candidate.
- Capture: title, author/site, publication date, full text (or representative
  excerpt + link if very long).

### 6. Compute read-time and trim

Count total words across all source bodies + your framings (use `wc -w` on the
draft, or estimate). Target `area.constraints.week_length_minutes × 220` words
±20%. If over, drop the lowest-priority source. If far under, search for one
more source — but only if quality holds.

### 7. Draft `weeks/<week-tag>-<area>.md`

Use this structure exactly:

```markdown
---
title: "Growth Week <week-tag> — <focus>"
author: "Personal Growth Assistant"
subtitle: "<area> · <focus>"
lang: en
---

# Growth Week <week-tag>

<2-4 sentence intro: what the focus is this week, why these sources, what
the user should take away by the end. Match the area's `style` constraint
(terse / academic / conversational).>

## <Source 1 title>

*<author/site> · <pub date> · <url>*

> <Your one-paragraph framing: why this source, what to look for, how it
> connects to the focus. Italics or quote-block for visual separation.>

<Full source body or excerpt+link.>

### Test yourself

1. <synthesis question 1>
2. <synthesis question 2>
3. <optional question 3>

## <Source 2 title>

...repeat...

## Cross-cutting questions

1. <question that bridges 2+ sources>
2. <question on what would change your approach>
3. <question on what to try this week>
4. <optional>
5. <optional>
```

Notes:
- No answer keys. Questions are open-ended; the user reflects on Kobo, then
  discusses with you in conversation later (v1.5 EOW review).
- If you skipped any sources for paywall/quality, leave the
  `<!-- skipped: ... -->` lines in the markdown (visible only to future you,
  not in the rendered EPUB — markdown comments don't render).

### 8. Render to EPUB + KEPUB

Invoke epub-pack:

```bash
uv run .claude/skills/epub-pack/pack.py weeks/<week-tag>-<area>.md
```

This writes `weeks/<week-tag>-<area>.epub` and `weeks/<week-tag>-<area>.kepub.epub`.

### 9. Report to the user

Tell the user:
- Path to the `.kepub.epub` (the file they sync to Kobo)
- This week's focus + which sources made it in (titles + domains)
- Anything you skipped and why
- Estimated read time (word count ÷ 220, in minutes)
- Reminder: open the `.kepub.epub` in Calibre's viewer before syncing if they
  want to spot-check.

## Failure modes to watch for

- **Seed source has nothing on this week's focus.** Don't force it. Skip that
  seed source for this week.
- **Web search returns 0 allowlisted results.** Don't lower the bar. Tell the
  user you couldn't find quality sources for this focus and propose either
  (a) shifting focus this week or (b) the user adding new domains to seed_sources.
- **Article is mostly images / charts / interactive widgets.** Won't render
  well on Kobo Clara HD (greyscale, slow). Skip or substitute.
- **Recursion / paywall walls.** WebFetch returning a "subscribe" stub instead
  of the article. Detect via short body length or "subscribe"/"sign in"
  keywords. Skip and substitute.
