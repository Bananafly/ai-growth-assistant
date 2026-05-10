---
name: epub-pack
description: |
  Pack a markdown file into EPUB + Kobo-optimized KEPUB. Use when the user has
  drafted reading material as markdown and wants it on a Kobo. Invoked by the
  growth-week skill, but works standalone for any markdown.
allowed-tools:
  - Bash
  - Read
---

# epub-pack

Single script: `pack.py`. Self-contained via PEP 723 inline metadata, run with
`uv run`. No project venv needed.

## Invoke

```bash
uv run .claude/skills/epub-pack/pack.py <path/to/source.md>
```

Writes `<source>.epub` and `<source>.kepub.epub` next to the markdown.

Flags:
- `--out <path>`  output `.epub` path (KEPUB derived from this).
- `--no-kepub`    skip the `.kepub.epub` (useful if you only want the EPUB for
                  Calibre).

## Markdown convention

```markdown
---
title: Optional override
author: Optional override
subtitle: Shown on the auto-generated cover
lang: en
---

# Book title (used if frontmatter doesn't set one)

Intro content goes here. Becomes the "Introduction" chapter.

## First chapter title

Body of chapter 1...

## Second chapter title

Body of chapter 2...
```

- First H1 → book title (frontmatter wins if both are present).
- Each H2 → new chapter; the H2 text is the chapter title.
- Anything before the first H2 → Introduction chapter.
- Frontmatter is optional. Cover is auto-generated as a text-only JPEG.

## Verify

After running, **open the `.kepub.epub` in Calibre's viewer** before sending
to a device. Check: title page, chapter list, navigation, body rendering,
no broken markdown that leaked through as raw text. The EPUB output is the
contract — if it looks wrong in Calibre, it'll look wrong on the Kobo.

## Dependencies

Listed inline in `pack.py` via PEP 723:
- `ebooklib` — EPUB generation
- `markdown` — markdown → HTML (extras + sane_lists extensions)
- `pillow` — auto-generated text cover
- `pyyaml` — frontmatter parsing

External binary: `kepubify` (install with `brew install kepubify`). If absent,
the script emits a warning and skips the `.kepub.epub` (you still get the
plain `.epub`).
