# Personal Growth Assistant

A long-running, per-area learning system. Define an area you want to go
deeper on, then run `/growth-week <area>` each Sunday (or whenever) to get a
curated, calibrated EPUB delivered to your e-reader for the week ahead.

The bottleneck this addresses is **curation and delivery**, not consumption.
Reading happens on the device when material is in front of you; it doesn't
happen when material is scattered across browser tabs and newsletters.

## Status

**Early / personal use.** v1. Single user. No automated quality gate — every
output is checked manually in Calibre before syncing to a device. Built to be
hacked on, not packaged.

## How to use

1. **Author an area.** Copy `areas/ai-future.yaml` as a template and fill in
   `goal`, `current_level`, `focus_areas`, `seed_sources`, and constraints.
   The more concrete you are, the better the reading.
2. **Run the skill.** In Claude Code: `/growth-week <area>` (e.g.
   `/growth-week ai-future`). The skill probes your current knowledge of the
   week's focus, sources reading from your trusted domains, and drafts a
   markdown file under `weeks/`.
3. **Pack it.** The skill auto-renders to `weeks/<week>-<area>.kepub.epub`
   via `epub-pack`. Open in Calibre's viewer to spot-check.
4. **Sync to device.** Drag the `.kepub.epub` to your Kobo (or any e-reader
   that handles EPUB).

## Layout

```
areas/<area>.yaml            human-authored brief (goal, level, sources)
state/<area>.yaml            v1.5+: progress + calibration log
weeks/YYYY-Www-<area>.md     drafted reading (markdown source of truth)
weeks/YYYY-Www-<area>.kepub.epub  Kobo-optimized output
.claude/skills/growth-week/  the weekly drafting skill
.claude/skills/epub-pack/    markdown → EPUB → KEPUB packager
```

## Requirements

- Claude Code
- `uv` (Python script runner; `pack.py` declares deps inline via PEP 723)
- `kepubify` (`brew install kepubify`)
- Calibre (for spot-checking and device sync)

## Planned

- **EOW review skill** — append-only writes to `state/<area>.yaml` capturing
  what was read, skipped, confused by, and wanted next week
- Multi-area support across one repo
- Annotation export from KOReader feeding back into curriculum
- Optional scheduling / cron for hands-off Sunday drafts
