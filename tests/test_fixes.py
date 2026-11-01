"""Regression tests for the v3.1.0 fixes.

Each test maps to a reported bug:

* unicode fold in hadith_sources filtering (ك↔ک, ي↔ی)
* noordoc_search crash when data is null
* wikinoor infobox lost with nested templates
* <ref> bodies / File:/Category: links / tables / magic words leaking
* html_to_text glued cells + destroyed paragraphs + dropped Persian digits
* extract_images: single quotes, protocol-relative, relative URLs
* clean_hadith_text: tags with attributes
* no network retry for transient errors / pointless final sleep
* qamus silently converting an invalid category
* https-only base_url
"""

import json

import httpx
import pytest

from noorlib_mcp.qamus_client import QamusClient
from noorlib_mcp.siteclient import SiteClient, SiteError
from noorlib_mcp.textutil import (
    clean_hadith_text,
    extract_images,
    fold_arabic,
    html_to_text,
    wikitext_to_text,
)


# ---------------------------------------------------------------- fold
def test_fold_arabic_persian_equivalence():
    assert fold_arabic("كافي") == fold_arabic("کافی")
    assert fold_arabic("الکَتَابُ") == "الکتاب"  # tashkeel gone
    assert fold_arabic("أحمد") == "احمد"
    assert fold_arabic("") == ""


def test_fold_handles_presentation_forms():
    # U+FEFB ARABIC LIGATURE LAM WITH ALEF (presentation form)
    assert fold_arabic("\ufefb") == "لا"


# ------------------------------------------------------- wikitext infobox
def test_wikinoor_infobox_with_nested_template():
    wt = (
        "{{جعبه اطلاعات کتاب\n"
        "|عنوان=فصوص الحکم\n"
        "|سال نشر={{سال|1229}}\n"
        "|پدیدآور=ابن عربی\n"
        "}}\n"
        "__NOTOC__ [[رده:کتاب‌های عرفانی]] متن مقاله "
        "<ref>منبع: کتاب فلان</ref> ادامه "
        "[[پرونده:x.jpg|thumb|250px|عنوان تصویر]]پایان"
    )
    text, infobox = wikitext_to_text(wt)
    assert infobox.get("عنوان") == "فصوص الحکم"
    assert infobox.get("سال نشر") == "1229"
    assert infobox.get("پدیدآور") == "ابن عربی"
    assert "منبع: کتاب فلان" not in text  # <ref> body gone
    assert "رده:" not in text  # category link gone
    assert "thumb" not in text  # file link gone
    assert "__NOTOC__" not in text  # magic words gone
    assert "متن مقاله" in text


def test_infobox_flattens_two_template_levels():
    text, infobox = wikitext_to_text(
        "{{جعبه اطلاعات کتاب\n|سال نشر={{قالب|{{سال|1229}}}}\n}}\nمتن مقاله"
    )
    assert infobox.get("سال نشر") == "1229"
    assert "متن مقاله" in text


def test_wikitext_tables_dropped():
    text, _ = wikitext_to_text("{|\n|الف||ب\n|}\nمتن اصلی")
    assert "الف" not in text and "ب" not in text
    assert "{|" not in text
    assert "متن اصلی" in text


# ------------------------------------------------------------- html_to_text
def test_paragraph_breaks_preserved():
    out = html_to_text("<p>پاراگراف اول.</p><p>پاراگراف دوم.</p>")
    assert "\n\n" in out


def test_cells_and_headings_not_glued():
    out = html_to_text("<td>الف</td><td>ب</td><h2>عنوان</h2>")
    assert "الف" in out and "ب" in out and "عنوان" in out
    assert "الفب" not in out and "بعنوان" not in out


def test_nested_noise_element_fully_removed():
    # regression: the inner </div> used to end the match early and leak text
    html = '<div class="Footer"><div>x</div>LEFTOVER</div><p>متن اصلی</p>'
    out = html_to_text(html)
    assert "LEFTOVER" not in out
    assert "x" not in out
    assert "متن اصلی" in out


def test_unbalanced_noise_tag_keeps_text():
    out = html_to_text('<span class="PageNo">12<p>ادامه متن</p>')
    assert "ادامه متن" in out


def test_noise_class_removed_but_numbers_kept():
    html = '<span class="Header">سرصفحه</span><p>۹۹</p>'
    out = html_to_text(html)
    assert "سرصفحه" not in out
    assert "۹۹" in out  # Persian digits are content, never dropped


def test_single_quoted_noise_class_and_footnote():
    out = html_to_text(
        "<span class='Header'>سرصفحه</span><div class='footnote'>یادداشت</div><p>متن</p>"
    )
    assert "سرصفحه" not in out
    assert "[پاورقی]" in out
    assert "یادداشت" in out
    assert "متن" in out


# ----------------------------------------------------------- extract_images
def test_extract_images_urljoin_and_quotes():
    html = (
        "<img src='//cdn.example.ir/a.png'>"
        '<img src="images/b.png">'
        '<img src="/abs/c.png">'
        '<img src="data:image/png;base64,AAA">'
    )
    imgs = extract_images(html, base_url="https://noorlib.ir")
    urls = [i["url"] for i in imgs]
    assert urls == [
        "https://cdn.example.ir/a.png",
        "https://noorlib.ir/images/b.png",
        "https://noorlib.ir/abs/c.png",
    ]


# ---------------------------------------------------------------- hadith
def test_clean_hadith_text_with_attributes():
    t = 'عَنْ <Narrator id="1"> اَلْحَسَنِ</Narrator> قَالَ'
    plain, structure = clean_hadith_text(t)
    assert structure["Narrator"] == ["اَلْحَسَنِ"]
    assert "<" not in plain


# ------------------------------------------------------------------ HTTP
def _mock_transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def make_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make_client)


@pytest.mark.asyncio
async def test_transient_network_errors_are_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"ok": True})

    _mock_transport(monkeypatch, handler)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("noorlib_mcp.siteclient.asyncio.sleep", no_sleep)
    client = SiteClient("https://example.test", throttle=0, retries=2)
    try:
        result = await client.get("/resource")
    finally:
        await client.close()
    assert len(calls) == 2
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_no_sleep_after_final_5xx(monkeypatch):
    sleeps = []

    def handler(request):
        return httpx.Response(503, text="busy")

    _mock_transport(monkeypatch, handler)

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("noorlib_mcp.siteclient.asyncio.sleep", fake_sleep)
    client = SiteClient("https://example.test", throttle=0, retries=3)
    try:
        with pytest.raises(SiteError):
            await client.get("/resource")
    finally:
        await client.close()
    # backoff happens only BETWEEN attempts (2 sleeps for 3 attempts),
    # never after the last one
    assert len(sleeps) == 2


def test_https_only_base_url():
    with pytest.raises(ValueError):
        SiteClient("http://example.test")


# ------------------------------------------------------------------ qamus
@pytest.mark.asyncio
async def test_qamus_invalid_category_raises():
    client = QamusClient()
    try:
        with pytest.raises(ValueError):
            await client.search("نور", category="bogus")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qamus_search_tool_returns_error_json():
    from noorlib_mcp import server as srv

    srv._qamus_client = None
    out = await srv.qamus_search("نور", category="bogus")
    data = json.loads(out)
    assert "category" in data["error"]
    client = srv._qamus_client
    if client is not None:
        await client.close()
        srv._OPEN_CLIENTS[:] = [c for c in srv._OPEN_CLIENTS if c is not client]
    srv._qamus_client = None


# ------------------------------------------------- server tool: noordoc null
@pytest.mark.asyncio
async def test_noordoc_search_survives_null_data(monkeypatch):
    from noorlib_mcp import server as srv

    def handler(request):
        return httpx.Response(200, json={"totalCount": 0, "data": None})

    _mock_transport(monkeypatch, handler)
    out = await srv.noordoc_search(text="عرفان")
    d = json.loads(out)
    assert "error" not in d
    assert d["theses"] == []


# ------------------------------------------------------------- quran / tarikh
@pytest.mark.asyncio
async def test_surah_text_clips_verse_longer_than_budget(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeQuran:
        async def surah_text(self, surah_id, orthography_id=4):
            return [
                {"AyahNum": 1, "Text": "الف" * 40, "JuzNumber": 1, "PageNumber": 1},
                {"AyahNum": 2, "Text": "ب" * 10, "JuzNumber": 1, "PageNumber": 1},
            ]

    monkeypatch.setattr(srv, "_qcl", lambda: FakeQuran())
    data = json.loads(await srv.quran_surah_text(1, max_chars=10))
    assert "error" not in data
    verse = data["verses"][0]["text"]
    assert data["truncated"] is True
    assert data["returnedAyahs"] == 1
    assert verse.endswith("…")
    assert len(verse) == 12  # 10 chars kept, then " …"
    assert ("الف" * 40).startswith(verse[:-2])


@pytest.mark.asyncio
async def test_surah_text_keeps_earlier_verses_when_later_one_overflows(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeQuran:
        async def surah_text(self, surah_id, orthography_id=4):
            return [
                {"AyahNum": 1, "Text": "کوتاه", "JuzNumber": 1, "PageNumber": 1},
                {"AyahNum": 2, "Text": "ب" * 30, "JuzNumber": 1, "PageNumber": 1},
            ]

    monkeypatch.setattr(srv, "_qcl", lambda: FakeQuran())
    data = json.loads(await srv.quran_surah_text(1, max_chars=10))
    assert data["returnedAyahs"] == 1
    assert data["verses"][0]["text"] == "کوتاه"
    assert data["truncated"] is True


@pytest.mark.asyncio
async def test_tarikh_today_prefers_type_title(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeTarikh:
        async def today(self):
            return [
                {
                    "EventId": "A1",
                    "EventTitle": "رویداد",
                    "EventTypeTitle": "سیاسی",
                    "EventTypeId": 4,
                    "StartDate": 360520,
                }
            ]

    monkeypatch.setattr(srv, "_tcl", lambda: FakeTarikh())
    data = json.loads(await srv.tarikh_today())
    assert data["events"][0]["type"] == "سیاسی"


def test_event_type_falls_back_to_id():
    from noorlib_mcp.server import _event_type

    assert _event_type({"EventTypeId": 4}) == 4
    assert _event_type({"EventTypeTitle": "وفات", "EventTypeId": 2}) == "وفات"
