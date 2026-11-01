"""Small HTML/wikitext-to-text helpers for the Noor-family content.

Highlights of this module:

* ``html_to_text`` — decoded noorlib page HTML → readable plain text.
  Structural noise (PageNo/Header/Footer/hidden classes) is removed by
  CLASS, not by guessing numeric lines: verse numbers, years and table
  cells in Persian/Arabic digits survive.
* ``wikitext_to_text`` — wikinoor MediaWiki wikitext → (text, infobox).
  The infobox parser tolerates NESTED templates (balanced-brace scan);
  <ref> bodies, File:/Category: links, tables, magic words and HTML
  comments are dropped.
* ``clean_hadith_text`` — hadith pseudo-XML (also tags WITH attributes).
* ``fold_arabic`` — Arabic/Persian letter folding (ك↔ک, ي↔ی, alef forms,
  tashkeel, presentation forms) for search filters.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from urllib.parse import urljoin

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\u00a0]+")

# classes that mark marginal / structural noise in noorlib page html
_NOISE_CLASSES = ("PageNo", "pageNo", "Header", "Footer", "hidden")
# opening tag of a noise element (class-based, NOT number-guessing)
_NOISE_CLASS = "|".join(_NOISE_CLASSES)
_NOISE_OPEN_RE = re.compile(
    r"(?is)<(span|div|p|td|th)\b[^>]*\bclass="
    r"(?:\"[^\"]*(?:%s)[^\"]*\"|'[^']*(?:%s)[^']*')[^>]*>" % (_NOISE_CLASS, _NOISE_CLASS)
)


def _strip_noise_elements(text: str) -> str:
    """Remove noise elements including their (possibly nested) content.

    A plain ``<div ...>.*?</div>`` regex stops at the FIRST closing tag, so
    ``<div class="Footer"><div>x</div>LEFTOVER</div>`` leaked ``LEFTOVER``.
    Here every same-named open/close tag is counted to find the real end.
    An opening tag without a matching close is left untouched.
    """
    out: list[str] = []
    pos = 0
    while True:
        m = _NOISE_OPEN_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        name = m.group(1)
        tag_re = re.compile(r"(?i)<%s\b[^>]*?(?<!/)>|</%s\s*>" % (name, name))
        depth = 1
        end = -1
        for t in tag_re.finditer(text, m.end()):
            depth += -1 if t.group(0).startswith("</") else 1
            if depth == 0:
                end = t.end()
                break
        out.append(text[pos : m.start()])
        if end == -1:  # unbalanced: keep the text as it is
            out.append(m.group(0))
            pos = m.end()
        else:
            out.append(" ")
            pos = end
    return "".join(out)


_IMG_RE = re.compile(r"<img\s[^>]*?src=(?:\"([^\"]+)\"|'([^']+)')[^>]*>", re.I)


def extract_images(html: str, base_url: str = "https://noorlib.ir") -> list[dict]:
    """Extract scan images from a decoded page (image-only pages)."""
    out = []
    for m in _IMG_RE.finditer(html or ""):
        src = (m.group(1) or m.group(2) or "").strip()
        if not src or src.startswith("data:"):
            continue
        url = urljoin(base_url if base_url.endswith("/") else base_url + "/", src)
        imgtype = re.search(r'imgtype="([^"]*)"', m.group(0))
        out.append(
            {
                "url": url,
                "type": imgtype.group(1) if imgtype else "",
            }
        )
    return out


def html_to_text(html: str, max_length: int | None = None) -> str:
    """Convert a decoded page HTML fragment to readable plain text.

    Keeps paragraph breaks (``<p>`` → blank line), footnote blocks and
    line/table-cell/head boundaries; drops style/script and noise-class
    elements (page numbers etc.) structurally.  Bare numeric lines are
    NOT dropped — verse numbers, years and digits in Persian script are
    content, not noise.
    """
    if not html:
        return ""

    # 1) drop style/script blocks including their content
    text = re.sub(r"(?is)<(style|script)\b[^>]*>.*?</\1\s*>", " ", html)

    # 2) remove structural noise elements by class (PageNo, Header, ...)
    text = _strip_noise_elements(text)

    # 3) footnote divs: keep them, one per line
    text = re.sub(
        r"(?i)<div[^>]*class=(?:\"[^\"]*footnote[^\"]*\"|'[^']*footnote[^']*')[^>]*>",
        "\n[پاورقی] ",
        text,
    )

    # 4) block boundaries BEFORE stripping tags (cells/headings get spaces,
    #    paragraphs get blank lines — no more glued words)
    text = re.sub(r"(?i)</(p|div|table|tr|ul|ol|dl)\s*>", "\n\n", text)
    text = re.sub(r"(?i)</(td|th|li|h[1-6]|blockquote)\s*>", "\n", text)
    text = re.sub(r"(?i)<h[1-6]\b[^>]*>", "\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)

    # 5) strip remaining (inline) tags — no inserted spaces inside words
    text = _TAG_RE.sub("", text)
    text = unescape(text)

    # 6) line filtering: keep blank lines as paragraph markers
    lines: list[str] = []
    for line in text.split("\n"):
        s = _WS_RE.sub(" ", line).strip()
        if not s:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        # only explicit page-number markers ("p. 12" / "Page 12") are noise;
        # ASCII-only so Persian/Arabic digit lines are never dropped
        if re.fullmatch(r"\[?p(?:age)?\.?\s*\d+\]?", s, flags=re.I | re.A):
            continue
        lines.append(s)

    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if max_length and len(out) > max_length:
        out = out[:max_length] + " …"
    return out


def strip_em(text: str) -> str:
    """Remove <em> highlight tags from search snippets."""
    if not text:
        return ""
    return unescape(_TAG_RE.sub("", text))


# ------------------------------------------------------------------ MediaWiki
_LINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]")
_EXT_LINK_RE = re.compile(r"\[https?://[^\s\]]+(?:\s([^\]]+))?\]")
_BOLD_RE = re.compile(r"'''+([^']+?)''+")
_TABLE_RE = re.compile(r"(?s)\{\|.*?\|\}")
_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_REF_RE = re.compile(r"(?is)<ref\b[^>]*>.*?</ref\s*>")
_REF_SELF_RE = re.compile(r"(?is)<ref\b[^>]*/>")
_FILE_LINK_RE = re.compile(r"\[\[\s*(?:پرونده|تصویر|File|Image|file|image)\s*:[^\]]*\]\]")
_CAT_LINK_RE = re.compile(r"\[\[\s*(?:رده|Category|category)\s*:[^\]]*\]\]")
_MAGIC_WORD_RE = re.compile(r"__[A-Z]+__")
_NESTED_TPL_RE = re.compile(r"\{\{([^{}]*)\}\}")


def _balanced_template_end(text: str, start: int) -> int:
    """`start` points at '{{'; return index just after the matching '}}'
    (nesting-aware), or -1 when unbalanced."""
    depth = 0
    i = start
    n = len(text)
    while i < n - 1:
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def _remove_all_templates(text: str) -> str:
    """Remove every (possibly nested) {{...}} template via balanced scan."""
    out: list[str] = []
    i = 0
    while True:
        j = text.find("{{", i)
        if j == -1:
            out.append(text[i:])
            break
        e = _balanced_template_end(text, j)
        if e == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        i = e
    return "".join(out)


def _fold_value(val: str) -> str:
    """Clean an infobox value: links → label, nested templates → last arg.

    Templates are peeled from the inside out, so ``{{a|{{b|1229}}}}``
    becomes ``1229`` rather than stopping after the inner template.
    """
    val = _LINK_RE.sub(lambda m: (m.group(2) or m.group(1) or "").strip(), val)
    while True:
        nxt = _NESTED_TPL_RE.sub(lambda m: m.group(1).split("|")[-1], val)
        if nxt == val:
            return val.strip()
        val = nxt


def wikitext_to_text(wikitext: str) -> tuple[str, dict]:
    """Convert wikinoor (MediaWiki) wikitext to plain text.

    Returns (text, infobox) where infobox maps the Persian infobox
    fields (عنوان، پدیدآوران، ناشر، ...) to their cleaned values.
    Nested templates inside the infobox are tolerated.
    """
    if not wikitext:
        return "", {}

    infobox: dict[str, str] = {}
    text = wikitext

    # HTML comments and raw tables
    text = _COMMENT_RE.sub(" ", text)
    text = _TABLE_RE.sub(" ", text)

    # <ref> INCLUDING its body, then self-closing refs
    text = _REF_RE.sub(" ", text)
    text = _REF_SELF_RE.sub(" ", text)

    # infobox: balanced-brace extraction (tolerates nested templates)
    idx = text.find("{{جعبه اطلاعات")
    if idx != -1:
        end = _balanced_template_end(text, idx)
        if end != -1:
            body = text[idx:end]
            for line in body.split("\n"):
                line = line.strip()
                if not line.startswith("|") or "=" not in line:
                    continue
                key, _, val = line[1:].partition("=")
                key = key.strip()
                val = _fold_value(val)
                if key and val and "جعبه" not in key:
                    infobox[key] = val[:400]
            text = text[:idx] + text[end:]

    # remaining templates (nested tolerated)
    text = _remove_all_templates(text)

    # File/Image/Category links are dropped entirely (no more
    # "thumb|250px|..." or "رده:..." leftovers); general links keep label
    text = _FILE_LINK_RE.sub(" ", text)
    text = _CAT_LINK_RE.sub(" ", text)
    text = _LINK_RE.sub(lambda m: (m.group(2) or m.group(1) or "").strip(), text)
    text = _EXT_LINK_RE.sub(lambda m: m.group(1) or "", text)
    text = _MAGIC_WORD_RE.sub(" ", text)
    # bold/italics
    text = _BOLD_RE.sub(r"\1", text)
    # headings -> lines
    text = re.sub(r"^=+\s*([^=]+?)\s*=+\s*$", r"\n\n\1\n", text, flags=re.M)
    # list bullets
    text = re.sub(r"^\s*[*#:]+\s*", "• ", text, flags=re.M)
    # leftover tags
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    # collapse whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), infobox


# hadith.inoor.ir wraps narrators etc. in pseudo-XML tags
_HADITH_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9_]*(?:\s[^<>]*)?/?>")


def clean_hadith_text(text: str) -> tuple[str, dict]:
    """Clean a hadith pseudo-XML text.

    Returns (plain_text, structure) where structure maps tag names to the
    values found (Narrator, Innocent, Book, ...). Keeps the reading order.
    Tags WITH attributes (e.g. ``<Narrator id="1">``) are handled too.
    """
    if not text:
        return "", {}
    structure: dict[str, list[str]] = {}

    # repeatedly strip innermost tags until none remain, collecting contents
    work = text
    inner = re.compile(r"<([A-Za-z][A-Za-z0-9_]*)(?:\s[^<>]*)?>([^<>]*)</\1>")
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
    # drop leftover stray tags (open/close, with or without attributes)
    plain = _HADITH_TAG_RE.sub(" ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain, structure


# ------------------------------------------------------- Arabic/Persian folding
_FOLD_TABLE = str.maketrans(
    {
        "ك": "ک",
        "ي": "ی",
        "ى": "ی",  # kaf / yeh variants
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",  # alef variants
        "ۀ": "ه",
        "ة": "ه",  # heh variants
        "ؤ": "و",
        "ئ": "ی",
        "ء": "",  # hamza carriers
    }
)


def fold_arabic(s: str) -> str:
    """Fold Arabic/Persian letter variants for search filtering.

    Unifies ك↔ک, ي/ى↔ی, alef forms, heh forms, strips tashkeel
    (diacritics) and NFKC-normalizes presentation forms (U+FB50–FDFF,
    U+FE70–FEFF).  ``fold_arabic('كافي') == fold_arabic('کافی')``.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_FOLD_TABLE)
    return "".join(c for c in s if not unicodedata.combining(c))
