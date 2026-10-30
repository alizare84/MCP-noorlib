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
    all tags and collapses whitespace.
    """
    if not html:
        return ""

    # mark block boundaries before stripping tags
    text = re.sub(r"(?i)</p\s*>", "\n\n", html)
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
