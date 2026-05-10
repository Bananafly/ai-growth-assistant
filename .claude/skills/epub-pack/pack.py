#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ebooklib>=0.18",
#   "markdown>=3.6",
#   "pillow>=10.0",
#   "pyyaml>=6.0",
#   "beautifulsoup4>=4.12",
#   "requests>=2.31",
# ]
# ///
"""
Pack a markdown file into EPUB + KEPUB for Kobo.

Markdown convention:
- Optional YAML frontmatter (--- ... ---) sets metadata: title, author, lang, subtitle.
- First H1 (# ...) becomes the book title if frontmatter doesn't set one.
- Each H2 (## ...) starts a new chapter; H2 text is the chapter title.
- Content before the first H2 (after the H1) becomes the Introduction chapter.

Output: <basename>.epub and <basename>.kepub.epub (the KEPUB only if `kepubify`
is on PATH).

Verify by opening the .kepub.epub in Calibre's viewer before claiming success.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import markdown as md_lib
import requests
import yaml
from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont


CSS = """
body { font-family: serif; line-height: 1.5; margin: 0 1em; }
h1 { font-size: 1.6em; margin-top: 1.5em; }
h2 { font-size: 1.3em; margin-top: 1.2em; }
h3 { font-size: 1.1em; }
p  { margin: 0.6em 0; }
blockquote { font-style: italic; border-left: 2px solid #999; padding-left: 0.8em; color: #444; }
hr { border: 0; border-top: 1px dashed #999; margin: 1.5em 0; }
code { font-family: monospace; font-size: 0.9em; }
pre  { background: #f4f4f4; padding: 0.6em; overflow-x: auto; font-size: 0.85em; }
.framing  { font-style: italic; color: #555; }
.questions { background: #f4f4f4; padding: 0.6em 1em; border-radius: 4px; margin-top: 1em; }
.questions h3 { margin-top: 0; }
.skipped  { color: #888; font-size: 0.85em; }
"""

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Georgia.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


_FENCE_RE = re.compile(r"^(?:```|~~~)")


def split_chapters(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Split markdown by H2 headings. Returns (intro_md, [(title, md_body), ...]).

    Fenced code blocks (``` or ~~~) are skipped when matching headings, so a
    `## comment` line inside a code block doesn't start a new chapter.
    """
    chapters: list[tuple[str, str]] = []
    intro: list[str] = []
    current_title: str | None = None
    current_body: list[str] = []
    in_fence = False
    for line in body.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            (current_body if current_title is not None else intro).append(line)
            continue
        m = None if in_fence else re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current_title is not None:
                chapters.append((current_title, "\n".join(current_body).strip()))
            current_title = m.group(1).strip()
            current_body = []
        else:
            (current_body if current_title is not None else intro).append(line)
    if current_title is not None:
        chapters.append((current_title, "\n".join(current_body).strip()))
    return "\n".join(intro).strip(), chapters


def extract_h1(intro_md: str) -> tuple[str | None, str]:
    """Pull the first H1 line out of the intro, return (title, remaining_intro).

    Skips lines inside fenced code blocks.
    """
    lines = intro_md.split("\n")
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            title = m.group(1).strip()
            remaining = "\n".join(lines[:i] + lines[i + 1 :]).strip()
            return title, remaining
    return None, intro_md


def make_text_cover(title: str, subtitle: str = "", size=(600, 800)) -> bytes:
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    title_font = _load_font(40)
    sub_font = _load_font(22)

    margin = 50
    max_width = size[0] - 2 * margin

    def wrap(text: str, font) -> list[str]:
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            tw = d.textbbox((0, 0), trial, font=font)[2]
            if tw <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    title_lines = wrap(title, title_font)
    line_h = 50
    block_h = len(title_lines) * line_h
    y = (size[1] - block_h) // 2 - 40
    for line in title_lines:
        tw = d.textbbox((0, 0), line, font=title_font)[2]
        d.text(((size[0] - tw) // 2, y), line, fill="black", font=title_font)
        y += line_h

    if subtitle:
        for line in wrap(subtitle, sub_font):
            tw = d.textbbox((0, 0), line, font=sub_font)[2]
            d.text(((size[0] - tw) // 2, y + 20), line, fill="#666", font=sub_font)
            y += 30

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _chapter_body(title: str, body_html: str) -> str:
    """Return body inner-HTML for ebooklib (it wraps in its own xhtml template)."""
    from html import escape

    return f"<h1>{escape(title)}</h1>\n{body_html}"


# Kobo Clara HD renders JPEG, PNG, GIF — but not WebP. Convert WebP to JPEG.
_KOBO_OK_FORMATS = {"JPEG", "PNG", "GIF"}
_IMG_TIMEOUT = 15
_IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
    )
}


def _fetch_and_convert_image(url: str) -> tuple[bytes, str, str] | None:
    """Download image, convert WebP/other → JPEG if needed.

    Returns (bytes, file_extension, media_type) or None on failure.
    """
    try:
        resp = requests.get(url, timeout=_IMG_TIMEOUT, headers=_IMG_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"warning: failed to fetch image {url}: {e}", file=sys.stderr)
        return None

    try:
        img = Image.open(io.BytesIO(resp.content))
        img.load()
    except Exception as e:
        print(f"warning: cannot decode image {url}: {e}", file=sys.stderr)
        return None

    fmt = (img.format or "").upper()
    if fmt in _KOBO_OK_FORMATS:
        ext = {"JPEG": "jpg", "PNG": "png", "GIF": "gif"}[fmt]
        media = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}[fmt]
        return resp.content, ext, media

    # Convert anything else (notably WebP) to JPEG.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "jpg", "image/jpeg"


def collect_images(book: epub.EpubBook, html: str) -> str:
    """Find <img> tags with remote URLs, download/convert, embed in book, rewrite src.

    Local image refs and relative paths are stripped (with a warning) — they
    can't be resolved without source-document context.
    """
    soup = BeautifulSoup(html, "html.parser")
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "")
        if not src:
            img_tag.decompose()
            continue
        if not src.startswith(("http://", "https://")):
            print(f"warning: dropping non-absolute image src: {src}", file=sys.stderr)
            img_tag.decompose()
            continue

        result = _fetch_and_convert_image(src)
        if result is None:
            img_tag.decompose()
            continue
        data, ext, media = result

        digest = hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]
        file_name = f"images/{digest}.{ext}"
        # Dedupe: only add the EpubItem if not already present.
        if not any(item.file_name == file_name for item in book.get_items()):
            item = epub.EpubItem(
                uid=f"img-{digest}",
                file_name=file_name,
                media_type=media,
                content=data,
            )
            book.add_item(item)
        img_tag["src"] = file_name
    return str(soup)


def build_epub(md_path: Path, out_path: Path) -> Path:
    raw = md_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    intro_md, chapters = split_chapters(body)
    h1_title, intro_md = extract_h1(intro_md)

    title = meta.get("title") or h1_title or md_path.stem
    author = meta.get("author") or "Personal Growth Assistant"
    lang = meta.get("lang") or "en"
    subtitle = meta.get("subtitle", "") or ""

    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid.uuid4()}")
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)
    book.set_cover("cover.jpg", make_text_cover(title, subtitle))

    css = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css", content=CSS
    )
    book.add_item(css)

    md_to_html = md_lib.Markdown(extensions=["extra", "sane_lists"])
    items: list[epub.EpubHtml] = []

    def add_chapter(file_name: str, ch_title: str, ch_md: str) -> None:
        html = md_to_html.convert(ch_md)
        md_to_html.reset()
        html = collect_images(book, html)
        ch = epub.EpubHtml(title=ch_title, file_name=file_name, lang=lang)
        ch.content = _chapter_body(ch_title, html)
        ch.add_item(css)
        book.add_item(ch)
        items.append(ch)

    if intro_md:
        add_chapter("intro.xhtml", "Introduction", intro_md)
    for i, (ch_title, ch_md) in enumerate(chapters, 1):
        add_chapter(f"ch{i:02d}.xhtml", ch_title, ch_md)

    if not items:
        raise SystemExit("error: no content found in markdown")

    book.toc = tuple(items)
    book.add_item(epub.EpubNcx())
    book.spine = list(items)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out_path), book)
    return out_path


def make_kepub(epub_path: Path) -> Path | None:
    if not shutil.which("kepubify"):
        print(
            "warning: kepubify not on PATH — skipping .kepub.epub. "
            "Install: brew install kepubify",
            file=sys.stderr,
        )
        return None
    out_path = epub_path.with_suffix(".kepub.epub")
    subprocess.run(
        ["kepubify", "-o", str(out_path), str(epub_path)],
        check=True,
        capture_output=True,
    )
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown", type=Path, help="Path to markdown source")
    ap.add_argument("--out", type=Path, help="Output .epub path (default: alongside source)")
    ap.add_argument("--no-kepub", action="store_true", help="Skip .kepub.epub generation")
    args = ap.parse_args()

    if not args.markdown.exists():
        sys.exit(f"error: {args.markdown} does not exist")

    out = args.out or args.markdown.with_suffix(".epub")
    epub_path = build_epub(args.markdown, out)
    print(f"wrote {epub_path}")

    if not args.no_kepub:
        kepub = make_kepub(epub_path)
        if kepub:
            print(f"wrote {kepub}")


if __name__ == "__main__":
    main()
