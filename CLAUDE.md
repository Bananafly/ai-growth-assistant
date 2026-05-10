# Personal Growth Assistant

A long-running, per-area learning system. Each Sunday evening (or on-demand) the
user invokes `/growth-week <area>` to get a curated EPUB delivered to their Kobo
Clara HD for the week ahead.

The bottleneck this addresses is **curation and delivery**, not consumption. The
user reads on Kobo when material is in front of them; they don't read when
material is scattered across browser tabs and newsletters.

## Layout

```
areas/<area>.yaml            ← goal, current_level, constraints, seed_sources (human-authored)
state/<area>.yaml            ← v1.5+: progress notes, EOW review output (append-only)
weeks/YYYY-Www-<area>.md     ← drafted reading (markdown source of truth)
weeks/YYYY-Www-<area>.epub
weeks/YYYY-Www-<area>.kepub.epub  ← sync this to Kobo

.claude/skills/growth-week/  ← the weekly drafting skill
.claude/skills/epub-pack/    ← markdown → EPUB → KEPUB packager
```

## Skills

- **`/growth-week <area>`** — plans the upcoming week's reading for `<area>`,
  sources material (seed sources first, narrow web search second, allowlist
  filter), drafts `weeks/YYYY-Www-<area>.md`, then invokes `epub-pack` to render
  it. Use when the user says "draft this week", "growth week", or names an area.
- **`epub-pack`** — markdown → `.epub` → `.kepub.epub`. Invoked by `growth-week`
  but can be run standalone for any markdown file.

## Conventions

- **Read-time target:** ~220 wpm against `area.constraints.week_length_minutes`,
  ±20%. If over, drop the lowest-priority source. 3 focused > 5 padded.
- **Source allowlist:** `arxiv.org` + every domain in `area.seed_sources` +
  well-known author blogs. Reject aggregators, marketing posts, and paywalled
  content with no preview. Log skipped sources as HTML comments in the markdown.
- **Per-source structure in the EPUB:** title, author/site, one-paragraph
  framing from the assistant, source body (full text or excerpt+link), 2–3
  synthesis questions. Book closes with 3–5 cross-cutting questions. No answer
  keys (those live in conversation, post-read).
- **State is version-controlled.** `areas/` and `state/` are YAML, committed.
  `weeks/` artifacts are committed too — they're the reading log.

## Verification

After every `/growth-week` run, open the `.kepub.epub` in Calibre's viewer
before claiming success. Sourcing quality + rendering quality are both checked
manually for v1; no automated quality gate.
