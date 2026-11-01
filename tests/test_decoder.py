import base64

import pytest

from noorlib_mcp.decoder import DecodeError, decode_page_html
from noorlib_mcp.textutil import clean_hadith_text, html_to_text, strip_em


def _encode(plain: str, page: int) -> str:
    """Inverse of decode: shift chars by +page, swap adjacent chars, utf-8, b64."""
    shifted = [chr(ord(c) + page) for c in plain]
    for i in range(0, len(shifted) - 1, 2):
        shifted[i], shifted[i + 1] = shifted[i + 1], shifted[i]
    raw = "".join(shifted).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode()


PLAIN_ASCII = '<div class="CODE"><p id="p1">hello world 123</p></div>'
PLAIN_FA = "<p>خواص وحدت ذاتیه</p><p>حينئذ لا يغاير الوجوب المطلق بالذات</p>"


@pytest.mark.parametrize("page", [1, 5, 59, 69, 120, 300])
def test_roundtrip_ascii(page):
    assert decode_page_html(_encode(PLAIN_ASCII, page), page) == PLAIN_ASCII


@pytest.mark.parametrize("page", [1, 69, 150])
def test_roundtrip_persian(page):
    """Multi-byte chars must be swapped as characters, not bytes."""
    assert decode_page_html(_encode(PLAIN_FA, page), page) == PLAIN_FA


def test_empty():
    assert decode_page_html("", 5) == ""


def test_invalid_b64():
    with pytest.raises(DecodeError):
        decode_page_html("!!not-base64!!", 3)


def test_html_to_text():
    html = '<p><span class="GPA0 bookPage PageNo5">5</span>چهل و يكم</p>'
    text = html_to_text(html)
    assert "چهل و يكم" in text
    # noise classes are removed structurally (the "5" page-number span)
    assert "PageNo" not in text
    # bare numeric lines are CONTENT (verse numbers, years, Persian digits)
    assert "70" in html_to_text("<p>70</p>")
    assert "۱۲۳" in html_to_text("<p>۱۲۳</p>")
    # only explicit page markers are noise
    assert "p. 12" not in html_to_text("<p>p. 12</p>")
    assert "70" in html_to_text("<p>صفحه 70 مهم است</p>")


def test_html_to_text_footnote():
    html = '<div class="footnote OriginalDigit" id="f1">(2) التبدل بمعنى التفاوت. رضا.</div>'
    text = html_to_text(html)
    assert "التبدل بمعنى التفاوت" in text


def test_strip_em():
    assert strip_em("نصوص <em>فصوص</em> الحكم") == "نصوص فصوص الحكم"


def test_clean_hadith_text_nested():
    t = (
        "<Hadith><Document> عَنْ <Narrator> اَلْحَسَنِ</Narrator> "
        "<Exporter><Innocent> أَبِي جَعْفَرٍ</Innocent></Exporter> قَالَ:</Document>"
        " لَمَّا خَلَقَ اَللَّهُ اَلْعَقْلَ </Hadith>"
    )
    plain, structure = clean_hadith_text(t)
    assert "لَمَّا خَلَقَ اَللَّهُ اَلْعَقْلَ" in plain
    assert structure["Narrator"] == ["اَلْحَسَنِ"]
    assert structure["Innocent"] == ["أَبِي جَعْفَرٍ"]
    assert "<" not in plain


def test_clean_hadith_text_empty():
    assert clean_hadith_text("") == ("", {})
    assert clean_hadith_text(None) == ("", {})


def test_clean_hadith_text_with_attributes():
    t = 'عَنْ <Narrator id="1"> اَلْحَسَنِ</Narrator> قَالَ <Exporter data-x="y">زَيْدٌ</Exporter>'
    plain, structure = clean_hadith_text(t)
    assert structure["Narrator"] == ["اَلْحَسَنِ"]
    assert structure["Exporter"] == ["زَيْدٌ"]
    assert "<" not in plain and "Narrator" not in plain
