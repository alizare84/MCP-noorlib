"""Small HTML-to-text helpers for decoded noorlib pages."""

from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\u00a0]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")

# classes that mark marginal / structural noise in noorlib page html
_NOISE_CLASSES = ("PageNo", "pageNo", "Header", "Footer", "hidden")

_IMG_RE = re.compile(r'<img\s[^>]*src="([^"]+)"[^>]*>', re.I)


def extract_images(html: str, base_url: str = "https://noorlib.ir") -> list[dict]:
    """Extract scan images from a decoded page (image-only pages)."""
    out = []
    for m in _IMG_RE.finditer(html or ""):
        src = m.group(1)
        if src.startswith("data:"):
            continue
        url = src if src.startswith("http") else base_url + src
        imgtype = re.search(r'imgtype="([^"]*)"', m.group(0))
        out.append({
            "url": url,
            "type": imgtype.group(1) if imgtype else "",
        })
    return out


def html_to_text(html: str, max_length: int | None = None) -> str:
    """Convert a decoded page HTML fragment to readable plain text.

    Keeps paragraph breaks (``<p>``) and footnote blocks (``footnote``), strips
    all tags and collapses whitespace. ``<style>``/``<script>`` blocks are
    dropped with their content.
    """
    if not html:
        return ""

    # drop style/script blocks including their content
    text = re.sub(r"(?is)<(style|script)\b[^>]*>.*?</\1\s*>", " ", html)

    # mark block boundaries before stripping tags
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    # footnote divs: keep them, one per line
    text = re.sub(r'(?i)<div[^>]*class="[^"]*footnote[^"]*"[^>]*>', "\n[پاورقی] ", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)

    text = _TAG_RE.sub("", text)
    text = unescape(text)

    # drop pure-noise lines (page numbers etc.)
    lines = []
    for line in text.split("\n"):
        line = _WS_RE.sub(" ", line).strip()
        if not line:
            continue
        if re.fullmatch(r"\[?p(?:age)?\.?\s*\d+\]?", line, flags=re.I):
            continue
        if re.fullmatch(r"\d{1,4}", line):
            continue
        lines.append(line)

    out = _MULTI_NL_RE.sub("\n\n", "\n".join(lines)).strip()
    if max_length and len(out) > max_length:
        out = out[:max_length] + " …"
    return out


def strip_em(text: str) -> str:
    """Remove <em> highlight tags from search snippets."""
    if not text:
        return ""
    return unescape(_TAG_RE.sub("", text))


# ------------------------------------------------------------------ MediaWiki
_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_NESTED_TEMPLATE_RE = re.compile(r"\{\{(?:[^{}]|\{\{[^{}]*\}\})*\}\}")
_LINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]")
_EXT_LINK_RE = re.compile(r"\[https?://[^\s\]]+(?:\s([^\]]+))?\]")
_BOLD_RE = re.compile(r"'''+([^']+?)''+")


def wikitext_to_text(wikitext: str) -> tuple[str, dict]:
    """Convert wikinoor (MediaWiki) wikitext to plain text.

    Returns (text, infobox) where infobox maps the Persian infobox
    fields (عنوان، پدیدآوران، ناشر، ...) to their cleaned values.
    """
    if not wikitext:
        return "", {}

    infobox: dict[str, str] = {}

    def _link_text(m: re.Match) -> str:
        return (m.group(2) or m.group(1) or "").strip()

    text = wikitext
    # extract infobox (nested templates tolerated) and drop other templates
    text = re.sub(
        r"\{\{جعبه اطلاعات[^{}]*\}\}",
        lambda m: _infobox_extract(m, infobox) or "",
        text,
    )
    text = _TEMPLATE_RE.sub("", text)
    text = _NESTED_TEMPLATE_RE.sub("", text)
    # links: [[a|b]] -> b ; [[a]] -> a
    text = _LINK_RE.sub(_link_text, text)
    text = _EXT_LINK_RE.sub(lambda m: (m.group(1) or ""), text)
    # bold/italics
    text = _BOLD_RE.sub(r"\1", text)
    # headings -> lines
    text = re.sub(r"^=+\s*([^=]+?)\s*=+\s*$", r"\n\n\1\n", text, flags=re.M)
    # list bullets
    text = re.sub(r"^\s*[*#:]+\s*", "• ", text, flags=re.M)
    # refs and leftover tags
    text = re.sub(r"<ref[^>]*/?>", "", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    # collapse whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), infobox


def _infobox_extract(m: re.Match, infobox: dict) -> str:
    def _link_text(mm: re.Match) -> str:
        return (mm.group(2) or mm.group(1) or "").strip()

    for line in m.group(0).split("\n"):
        if "|" in line and "=" in line:
            key, _, val = line.partition("|")[-1].partition("=")
            key = key.strip()
            val = val.strip()
            if key and val and "جعبه" not in key:
                infobox[key] = _LINK_RE.sub(_link_text, val)[:400]
    return ""


# hadith.inoor.ir wraps narrators etc. in pseudo-XML tags
_HADITH_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9_]*>")


def clean_hadith_text(text: str) -> tuple[str, dict]:
    """Clean a hadith pseudo-XML text.

    Returns (plain_text, structure) where structure maps tag names to the
    values found (Narrator, Innocent, Book, ...). Keeps the reading order.
    Nested tags (Exporter>Innocent) are handled by innermost-first matching.
    """
    if not text:
        return "", {}
    structure: dict[str, list[str]] = {}

    # repeatedly strip innermost tags until none remain, collecting contents
    work = text
    inner = re.compile(r"<([A-Za-z][A-Za-z0-9_]*)>([^<>]*)</\1>")
    while True:
        matches = list(inner.finditer(work))
        if not matches:
            break
        def _repl(m: re.Match) -> str:
            structure.setdefault(m.group(1), []).append(unescape(m.group(2)).strip())
            return m.group(2)
        work = inner.sub(_repl, work)

    plain = unescape(work)
    plain = re.sub(r"\s+", " ", plain).strip()
    # drop leftover stray tags if any
    plain = _HADITH_TAG_RE.sub(" ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain, structure
