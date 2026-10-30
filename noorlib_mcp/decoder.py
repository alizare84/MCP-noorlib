"""Decoder for noorlib.ir encrypted page HTML.

Algorithm (verified against live responses, 2026-10):

1. The ``html`` field of ``/api/book/getBookPageContent`` is URL-safe base64.
2. Base64-decoding yields UTF-8 text: a sequence of *characters* whose Unicode
   code points are each shifted by ``+pageNumber``.
3. Adjacent **characters** (not bytes!) are swapped pairwise.
4. Decoding: swap adjacent characters back, then subtract ``pageNumber`` from
   every code point.

NOTE the swap operates on Unicode characters AFTER UTF-8 decoding, not on the
raw bytes.  For small page numbers (< ~59) every shifted ASCII character stays
inside the 1-byte UTF-8 range, so a byte-level swap coincidentally works — but
for larger page numbers (or Persian/Arabic text, which is always multi-byte)
a byte-level swap corrupts the text.  Several earlier bugs came from this
distinction.
"""

from __future__ import annotations

import base64


class DecodeError(ValueError):
    """Raised when a page payload cannot be decoded."""


def decode_page_html(html: str, page_number: int) -> str:
    """Decode the encrypted ``html`` payload of a book page.

    Parameters
    ----------
    html:
        The base64 payload returned by the API (URL-safe alphabet).
    page_number:
        The page number the payload belongs to (the shift key).
    """
    if not html:
        return ""
    try:
        raw = base64.urlsafe_b64decode(html + "=" * (-len(html) % 4))
    except (ValueError, TypeError) as exc:
        raise DecodeError(f"base64 payload is invalid: {exc}") from exc
    try:
        shifted = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecodeError(f"payload is not valid UTF-8: {exc}") from exc

    chars = list(shifted)
    for i in range(0, len(chars) - 1, 2):
        chars[i], chars[i + 1] = chars[i + 1], chars[i]

    try:
        return "".join(chr(ord(c) - page_number) for c in chars)
    except ValueError as exc:  # pragma: no cover - chr() only fails on edge cases
        raise DecodeError(f"character shift failed: {exc}") from exc
