"""«عرش الرحمان» — one MCP server for the Noor family of sites (stdio).

Currently serves:

* noorlib.ir  — کتابخانه دیجیتال نور (search / TOC / encrypted page decoding)
* hadith.inoor.ir — پایگاه جامع‌الاحادیث (350+ shi'a hadith sources)
* quran.inoor.ir — پایگاه جامع قرآنی (متن، ترجمه، تفسیر)
* wikinoor.ir — دانشنامه ویکی‌نور (کتاب‌شناسی/زندگی‌نامه)
* qamus.inoor.ir — لغت‌نامه قاموس نور
* noordoc.ir — پایگاه پایان‌نامه‌های علوم اسلامی و انسانی
* tarikh.inoor.ir — پایگاه جامع تاریخ

Compatible with the official ``mcp`` SDK 1.x AND 2.x:

* mcp 1.x: ``from mcp.server.fastmcp import FastMCP``
* mcp 2.x: ``from mcp.server.mcpserver import MCPServer`` (FastMCP renamed)

Both expose the same decorator/run API used here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from .client import NoorlibClient, NoorlibError
from .decoder import DecodeError, decode_page_html
from .hadith_client import HadithClient, HadithError
from .httpcore import SiteError
from .noordoc_client import NoordocClient
from .qamus_client import QamusClient
from .quran_client import QuranClient
from .tarikh_client import TarikhClient, decode_tarikh_date
from .textutil import (
    clean_hadith_text,
    extract_images,
    html_to_text,
    strip_em,
    wikitext_to_text,
)
from .wikinoor_client import WikinoorClient

logger = logging.getLogger("noorlib_mcp")


def _get_server_cls():
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore  # mcp 1.x
        return FastMCP
    except ImportError:
        pass
    try:
        from mcp.server.mcpserver import MCPServer  # type: ignore  # mcp 2.x
        return MCPServer
    except ImportError:
        pass
    print(
        "The 'mcp' package is required (pip install mcp). "
        "Neither mcp.server.fastmcp (v1) nor mcp.server.mcpserver (v2) "
        "could be imported.",
        file=sys.stderr,
    )
    raise SystemExit(2)


_Server = _get_server_cls()
mcp = _Server("arsh-alrahman", instructions=(
    "عرش الرحمان — unified tools for the Noor family of sites: "
    "noorlib.ir (کتابخانه دیجیتال نور), hadith.inoor.ir "
    "(جامع‌الاحادیث), quran.inoor.ir (قرآن), wikinoor.ir (دانشنامه), "
    "qamus.inoor.ir (لغت‌نامه), noordoc.ir (پایان‌نامه‌ها), "
    "tarikh.inoor.ir (تاریخ). "
    "noorlib: noorlib_search -> noorlib_book_info -> noorlib_book_toc -> "
    "noorlib_book_page, or noorlib_search_in_book for snippets. "
    "hadith: hadith_search -> hadith_by_id; hadith_sources lists books. "
    "quran: quran_search -> quran_surah_text / quran_ayah_translations / "
    "quran_ayah_commentary / quran_ayah_hadiths. "
    "wikinoor: wikinoor_search -> wikinoor_page. "
    "qamus: qamus_search -> qamus_word. noordoc: noordoc_search -> "
    "noordoc_thesis. tarikh: tarikh_search / tarikh_event / tarikh_today."
))

_client: NoorlibClient | None = None
_hadith_client: HadithClient | None = None
_quran_client: QuranClient | None = None
_wikinoor_client: WikinoorClient | None = None
_qamus_client: QamusClient | None = None
_noordoc_client: NoordocClient | None = None
_tarikh_client: TarikhClient | None = None


def _cl() -> NoorlibClient:
    global _client
    if _client is None:
        _client = NoorlibClient()
    return _client


def _hcl() -> HadithClient:
    global _hadith_client
    if _hadith_client is None:
        _hadith_client = HadithClient()
    return _hadith_client


def _qcl() -> QuranClient:
    global _quran_client
    if _quran_client is None:
        _quran_client = QuranClient()
    return _quran_client


def _wcl() -> WikinoorClient:
    global _wikinoor_client
    if _wikinoor_client is None:
        _wikinoor_client = WikinoorClient()
    return _wikinoor_client


def _mcl() -> QamusClient:
    global _qamus_client
    if _qamus_client is None:
        _qamus_client = QamusClient()
    return _qamus_client


def _dcl() -> NoordocClient:
    global _noordoc_client
    if _noordoc_client is None:
        _noordoc_client = NoordocClient()
    return _noordoc_client


def _tcl() -> TarikhClient:
    global _tarikh_client
    if _tarikh_client is None:
        _tarikh_client = TarikhClient()
    return _tarikh_client


def _err(exc: Exception) -> str:
    return json.dumps(
        {"error": str(exc)}, ensure_ascii=False, indent=1
    )


# --------------------------------------------------------------------- tools
@mcp.tool()
async def noorlib_search(
    query: str,
    page_number: int = 1,
    page_size: int = 10,
    book_id: int | None = None,
    creator_id: int | None = None,
    subject_id: int | None = None,
) -> str:
    """جستجوی کلی در کتابخانه نور (noorlib.ir).

    Returns matching books with authors, match counts and a sample snippet
    (page/section/volume + text) for each. Use query in Arabic/Persian.

    Args:
        query: عبارت جستجو (فارسی/عربی)، مثل «فصوص الحکم» یا «توحید ذاتی»
        page_number: شماره صفحه نتایج (1-based)
        page_size: تعداد نتیجه در هر صفحه (5-20)
        book_id: محدود کردن جستجو به یک کتاب (اختیاری)
        creator_id: محدود کردن به یک پدیدآور (اختیاری)
        subject_id: محدود کردن به یک موضوع (اختیاری)
    """
    try:
        data = await _cl().search(
            query, page_number, page_size, book_id, creator_id, subject_id
        )
    except NoorlibError as exc:
        return _err(exc)

    books = []
    for grp in data.get("resultList", []):
        if grp.get("type") != "book":
            continue
        items = grp.get("itemList") or ([grp] if grp.get("bookId") else [])
        for it in items:
            snippet = ""
            snips = it.get("snippetList") or []
            if snips:
                s0 = snips[0]
                snippet = "p{} s{} v{}: {}".format(
                    s0.get("pageNumber"), s0.get("sectionNumber"),
                    s0.get("volumeNumber"), strip_em(s0.get("text") or ""),
                )
            books.append({
                "bookId": it.get("bookId"),
                "title": strip_em(it.get("title") or ""),
                "creators": [c.get("name") for c in (it.get("creatorList") or [])][:4],
                "matches": it.get("matchListTotalCount"),
                "isFreeStudy": it.get("isFreeStudy"),
                "link": "https://noorlib.ir" + (it.get("link") or ""),
                "sample": snippet,
            })
    return json.dumps({
        "query": query,
        "resultCount": len(books),
        "pageNumber": data.get("pageNumber", page_number),
        "resultListTotalCount": data.get("resultListTotalCount"),
        "books": books,
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def noorlib_book_info(book_id: int) -> str:
    """متادیتای کتاب: عنوان، پدیدآورندگان، تعداد جلد، رایگان بودن، لینک.

    Args:
        book_id: شناسه کتاب در noorlib.ir (مثلا 55202)
    """
    try:
        info = await _cl().book_info(book_id)
    except NoorlibError as exc:
        return _err(exc)
    if not info:
        return _err(NoorlibError(f"book {book_id} not found"))
    creators = [
        {
            "name": c.get("creatorFullName"),
            "role": c.get("roleTitle"),
        }
        for c in (info.get("creators") or [])
    ]
    return json.dumps({
        "bookId": info.get("bookId"),
        "title": info.get("bookTitle"),
        "otherTitles": info.get("bookOtherTitles"),
        "creators": creators,
        "isMultiVolume": info.get("isMultiVolume"),
        "totalVolumes": info.get("totalVolumes"),
        "hasTextContent": info.get("hasTextContent"),
        "hasImageContent": info.get("hasImageContent"),
        "isFreeStudy": info.get("isFreeStudy"),
        "hasTocContent": info.get("hasTocContent"),
        "shortLink": info.get("shortLink"),
        "url": f"https://noorlib.ir/book/{book_id}",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def noorlib_book_toc(
    book_id: int,
    parent_node_id: int | None = None,
    offset: int = 0,
    limit: int = 25,
) -> str:
    """فهرست مطالب کتاب (درخت TOC).

    Each node has: nodeId, title, pageNumber, volumeNumber, section,
    hasChildren, levelNumber, pageCount and `zone` (the page range of the
    node per section). Use parent_node_id=nodeId of a node with
    hasChildren=true to go deeper.

    Args:
        book_id: شناسه کتاب
        parent_node_id: شناسه گره پدر برای پیمایش عمیق‌تر (اختیاری)
        offset: از کدام نتیجه (صفحه‌بندی TOC)
        limit: چند گره (پیش‌فرض 25)
    """
    try:
        data = await _cl().book_toc(book_id, parent_node_id, offset, limit)
    except NoorlibError as exc:
        return _err(exc)
    nodes = []
    for n in data.get("nodes", []):
        nodes.append({
            "nodeId": n.get("nodeId"),
            "title": n.get("nodeTitle"),
            "pageNumber": n.get("pageNumber"),
            "volumeNumber": n.get("volumeNumber"),
            "section": n.get("section"),
            "sectionNumber": (n.get("zone") or [{}])[0].get("sectionNumber"),
            "level": n.get("levelNumber"),
            "hasChildren": n.get("hasChildren"),
            "pageCount": n.get("pageCount"),
            "zone": n.get("zone"),
        })
    return json.dumps({
        "bookId": book_id,
        "totalCount": data.get("totalCount"),
        "returned": len(nodes),
        "hint": "برای خواندن صفحه از noorlib_book_page، sectionNumber را از zone بگیرید",
        "nodes": nodes,
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def noorlib_book_page(
    book_id: int,
    page_number: int,
    volume_number: int = 1,
    section_number: int = 1,
) -> str:
    """خواندن متن یک صفحه کتاب (رمزگشایی شده و به متن ساده تبدیل می‌شود).

    IMPORTANT: pageNumber is counted WITHIN the section (sectionNumber), not
    within the whole book. Get the right section from noorlib_book_toc
    (node.zone[].sectionNumber). If the response carries a validation error
    (paywall/credit), the Persian server message is returned — in that case
    set NOORLIB_MCP_AUTH with your logged-in Bearer token or use
    noorlib_search_in_book snippets instead.

    Args:
        book_id: شناسه کتاب
        page_number: شماره صفحه داخل بخش (section)
        volume_number: شماره جلد (پیش‌فرض 1)
        section_number: شماره بخش/سلکت (پیش‌فرض 1؛ از TOC بگیرید)
    """
    try:
        pg = await _cl().book_page(book_id, page_number, volume_number, section_number)
        # The backend fleet flip-flops between "credit required" and
        # "successful" for anonymous users; one silent retry often recovers
        # the payload when validation says successful but html is missing.
        if not (pg.get("html") or ""):
            await asyncio.sleep(1.5)
            pg2 = await _cl().book_page(
                book_id, page_number, volume_number, section_number
            )
            if (pg2.get("html") or ""):
                pg = pg2
    except NoorlibError as exc:
        return _err(exc)

    validation = pg.get("validation") or {}
    html_enc = pg.get("html") or ""
    text = ""
    images: list[dict] = []
    decode_error = ""
    if html_enc:
        try:
            page_html = decode_page_html(html_enc, page_number)
            text = html_to_text(page_html)
            images = extract_images(page_html)
        except DecodeError as exc:
            decode_error = str(exc)

    result: dict = {
        "bookId": book_id,
        "pageNumber": pg.get("pageNumber", page_number),
        "volumeNumber": volume_number,
        "sectionNumber": pg.get("sectionNumber", section_number),
        "isEmpty": pg.get("isEmpty"),
        "isFreeStudy": pg.get("isFreeStudy"),
        "validation": validation,
        "text": text,
    }
    if images:
        result["images"] = images
        result["imageHint"] = (
            "این صفحه تصویر اسکن دارد؛ URL عمومی است و مستقیم قابل بازکردن "
            "است (متن OCR ندارد)."
        )
    if decode_error:
        result["decodeError"] = decode_error
    if not html_enc:
        if validation.get("type") != "successful":
            result["hint"] = (
                "سرور متن کامل این صفحه را به دلیل اعتبار/شارژ برنگرداند "
                f"(پیام سرور: {validation.get('message')}). راهکارها: "
                "1) لاگین در noorlib.ir و ست کردن NOORLIB_MCP_AUTH، "
                "2) استفاده از noorlib_search_in_book برای دریافت اسنیپت‌ها."
            )
        else:
            result["hint"] = (
                "سرور متن این صفحه را (موقتاً؟) برنگرداند؛ یک تلاش مجدد خودکار "
                "انجام شد ولی محتوا هنوز خالی است. می‌توانید دوباره صدا بزنید، "
                "با NOORLIB_MCP_AUTH لاگین کنید، یا از noorlib_search_in_book "
                "اسنیپت بگیرید. اگر صفحه فقط تصویری است hasImageContent=true است."
            )
    elif not text and not images:
        result["hint"] = (
            "این صفحه متن قابل استخراج ندارد (صفحه خالی یا فقط سرصفحه). "
            "از TOC صفحه بعدی را بخوانید."
        )
    return json.dumps(result, ensure_ascii=False, indent=1)


@mcp.tool()
async def noorlib_search_in_book(
    book_id: int,
    query: str,
    page_number: int = 1,
    page_size: int = 10,
    volume_number: int | None = None,
) -> str:
    """جستجوی متن داخل یک کتاب: صفحه + مسیر TOC + اسنیپت هایلایت‌شده.

    This works even for paywalled books (snippets are free) and is the
    recommended way to locate content.

    Args:
        book_id: شناسه کتاب
        query: عبارت جستجو
        page_number: صفحه نتایج
        page_size: تعداد نتیجه
        volume_number: محدود به جلد (اختیاری)
    """
    try:
        data = await _cl().search_in_book(
            book_id, query, page_number, page_size, volume_number
        )
    except NoorlibError as exc:
        return _err(exc)
    hits = []
    for r in data.get("resultList", []):
        sn = r.get("snippet") or {}
        hits.append({
            "pageNumber": sn.get("pageNumber"),
            "sectionNumber": sn.get("sectionNumber"),
            "volumeNumber": sn.get("volumeNumber"),
            "sectionTitle": sn.get("sectionTitle"),
            "tocPath": sn.get("hierarchyToc"),
            "text": strip_em(sn.get("text") or ""),
        })
    return json.dumps({
        "bookId": book_id,
        "query": query,
        "hits": len(hits),
        "results": hits,
        "hint": "برای متن کامل صفحه از noorlib_book_page با sectionNumber همین نتیجه استفاده کنید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def noorlib_find_pages(
    book_id: int, query: str, volume_number: int = 1
) -> str:
    """پیدا کردن شماره صفحه‌هایی که کلمات را دارند (ایندکس ارزان و سریع).

    Returns page/section numbers per matched word — useful before reading
    pages one by one.

    Args:
        book_id: شناسه کتاب
        query: کلمه/کلمات
        volume_number: شماره جلد
    """
    try:
        rows = await _cl().find_pages(book_id, query, volume_number)
    except NoorlibError as exc:
        return _err(exc)
    return json.dumps({
        "bookId": book_id,
        "query": query,
        "results": [
            {
                "pageNumber": r.get("pageNumber"),
                "sectionNumber": r.get("sectionNumber"),
                "volumeNumber": r.get("volumeNumber"),
                "words": r.get("words"),
            }
            for r in rows
        ],
    }, ensure_ascii=False, indent=1)


# ------------------------------------------------------------- hadith tools
@mcp.tool()
async def hadith_search(
    text: str,
    page_number: int = 1,
    page_size: int = 10,
    source_ids: list[int] | None = None,
    search_in: str = "hadith",
    search_type: str = "and",
) -> str:
    """جستجوی متن حدیث در پایگاه جامع‌الاحادیث (hadith.inoor.ir).

    Searches 350+ shi'a hadith sources (کافی، بحار، وسائل، نهج‌البلاغه...).
    Returns highlighted snippets + hadithId + sourceId + volume/page +
    link to the same hadith in noorlib.

    Args:
        text: عبارت جستجو (عربی/فارسی)، مثل «العقل» یا «خیر الناس»
        page_number: صفحه نتایج
        page_size: تعداد نتیجه (5-20)
        source_ids: فهرست sourceId برای محدود کردن به منابع خاص (از hadith_sources)
        search_in: hadith | translate | explanation | all
        search_type: and | or | exact
    """
    try:
        data = await _hcl().search(
            text, page_number, page_size, source_ids, search_in, search_type
        )
    except HadithError as exc:
        return _err(exc)

    results = []
    for r in data.get("resultList", []):
        hl = r.get("highLight") or []
        snippet = strip_em(hl[0]) if hl else ""
        results.append({
            "hadithId": r.get("hadithId"),
            "sourceId": r.get("sourceId"),
            "book": r.get("bookTitleShort") or r.get("bookTitle"),
            "author": r.get("authorTitle"),
            "vol": r.get("vol"),
            "page": r.get("pageNum"),
            "snippet": snippet,
            "noorlibLink": r.get("noorLibLink"),
        })
    return json.dumps({
        "query": text,
        "hadithCount": data.get("hadithCount"),
        "groupCount": data.get("groupCount"),
        "returned": len(results),
        "results": results,
        "hint": "برای متن کامل حدیث و سند، hadithId را به hadith_by_id بدهید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def hadith_by_id(hadith_id: int, search_phrase: str = "") -> str:
    """متن کامل یک حدیث + سند + مسیر کتاب (hadith.inoor.ir).

    Returns the full text (with narrator chain preserved in `narrators`),
    TOC path (کتاب/باب), translations list and the same-hadith occurrences
    in other sources (groupTogetherList).

    Args:
        hadith_id: شناسه حدیث از hadith_search
        search_phrase: عبارت جستجو برای هایلایت (اختیاری)
    """
    try:
        rows = await _hcl().hadith_by_id([hadith_id], "arabic", search_phrase)
    except HadithError as exc:
        return _err(exc)
    if not rows:
        return _err(HadithError(f"hadith {hadith_id} not found"))
    r = rows[0]
    plain, structure = clean_hadith_text(r.get("text") or "")
    toc_path = [
        t.get("title") for t in (r.get("tocInfo") or []) if t.get("title")
    ]
    together = [
        {
            "hadithId": g.get("hadithId"),
            "sourceId": g.get("sourceId"),
            "source": g.get("sourceMainTitle"),
            "vol": g.get("vol"),
            "page": g.get("pageNum"),
        }
        for g in (r.get("groupTogetherList") or [])
    ]
    result: dict = {
        "hadithId": r.get("hadithId"),
        "sourceId": r.get("sourceId"),
        "book": r.get("bookTitleShort") or r.get("bookTitle"),
        "author": r.get("authorTitle"),
        "vol": r.get("vol"),
        "page": r.get("pageNum"),
        "tocPath": toc_path,
        "text": plain,
        "narrators": structure.get("Narrator", []),
        "infallible": structure.get("Innocent", []),
        "sourceBook": structure.get("Book", []),
        "sameHadithInOtherSources": together,
        "noorlibLink": r.get("noorLibLink"),
        "url": f"https://hadith.inoor.ir/fa/hadith/{hadith_id}",
    }
    translations = [
        {
            "language": t.get("languageTitle") or t.get("language"),
            "text": clean_hadith_text(t.get("text") or "")[0],
        }
        for t in (r.get("translateList") or [])
    ]
    if translations:
        result["translations"] = translations
    return json.dumps(result, ensure_ascii=False, indent=1)


@mcp.tool()
async def hadith_sources(
    query: str = "", page_size: int = 50, page_number: int = 1
) -> str:
    """فهرست منابع حدیثی hadith.inoor.ir (۳۵۰+ کتاب) با sourceId هرکدام.

    Args:
        query: فیلتر عنوان/نویسنده (مثل «کافی» یا «مجلسی»؛ خالی = همه)
        page_size: تعداد نتیجه (پیش‌فرض 50)
        page_number: صفحه نتایج
    """
    try:
        rows = await _hcl().sources(page_size=900)
    except HadithError as exc:
        return _err(exc)
    q = (query or "").strip()
    if q:
        rows = [
            s for s in rows
            if q in (s.get("title") or "")
            or q in (s.get("shortTitle") or "")
            or q in (s.get("author") or "")
        ]
    total = len(rows)
    start = (page_number - 1) * page_size
    rows = rows[start:start + page_size]
    return json.dumps({
        "total": total,
        "returned": len(rows),
        "sources": [
            {
                "sourceId": s.get("id"),
                "title": s.get("title"),
                "shortTitle": s.get("shortTitle"),
                "author": s.get("author"),
                "publisher": s.get("publisher"),
                "publishYear": s.get("publishYear"),
                "wikinoorUrl": s.get("wikinoorUrl"),
            }
            for s in rows
        ],
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def hadith_toc(source_id: int) -> str:
    """فهرست مطالب یک منبع حدیثی (کتاب‌ها و ابواب).

    Args:
        source_id: شناسه منبع از hadith_sources (مثلا 1348 = الکافی)
    """
    try:
        nodes = await _hcl().toc(source_id)
    except HadithError as exc:
        return _err(exc)
    return json.dumps({
        "sourceId": source_id,
        "count": len(nodes),
        "nodes": [
            {
                "id": n.get("id"),
                "parentId": n.get("parentId"),
                "title": n.get("title"),
                "level": n.get("levelNum"),
                "hadithCount": n.get("hadithCount"),
                "childCount": n.get("childCount"),
            }
            for n in nodes
        ],
    }, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- quran tools
@mcp.tool()
async def quran_search(
    text: str,
    source: str = "quran",
    page_number: int = 1,
    page_size: int = 10,
) -> str:
    """جستجو در قرآن (quran.inoor.ir): متن عربی آیات یا ترجمه‌های فارسی.

    source='quran' searches the Arabic text (use Arabic/Persian words;
    root/stem/synonym expansion is on). source='translation' searches
    150+ translations (Persian, Pashto, Urdu...). Returns surahId +
    ayahNumber + highlighted text for each hit.

    Args:
        text: عبارت جستجو (مثل «نور» یا «توحید»)
        source: quran | translation
        page_number: صفحه نتایج
        page_size: تعداد نتیجه (5-20)
    """
    try:
        data = await _qcl().search(
            text, source=source, page_number=page_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    results = []
    for r in data.get("resultList") or []:
        results.append({
            "surahId": r.get("surahId"),
            "surah": r.get("surahTitle"),
            "ayahNumber": r.get("ayahNumber"),
            "text": strip_em(r.get("text") or ""),
            "link": r.get("link"),
        })
    return json.dumps({
        "query": text,
        "source": source,
        "total": data.get("resultListTotalCount"),
        "returned": len(results),
        "results": results,
        "hint": "برای ترجمه/تفسیر/احادیث این آیه از quran_ayah_* با surahId+ayahNumber استفاده کنید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def quran_surahs() -> str:
    """فهرست ۱۱۴ سوره قرآن با شماره، نام، تعداد آیات (quran.inoor.ir)."""
    try:
        rows = await _qcl().surahs()
    except SiteError as exc:
        return _err(exc)
    return json.dumps({
        "count": len(rows),
        "surahs": [
            {
                "surahId": s.get("Id"),
                "title": s.get("Title"),
                "names": s.get("PopularNames"),
                "ayahCount": s.get("AyahCount"),
                "juz": s.get("FallPriority"),
            }
            for s in rows
        ],
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def quran_surah_text(surah_id: int, orthography_id: int = 4) -> str:
    """متن کامل یک سوره قرآن (آیه به آیه با شماره صفحه و جزء).

    Args:
        surah_id: شماره سوره 1-114 (از quran_surahs)
        orthography_id: نوع خط؛ 4=عثمان طه (پیش‌فرض)، 2=ساده، 5=املایی، 7=مصحف ایران
    """
    try:
        rows = await _qcl().surah_text(surah_id, orthography_id)
    except SiteError as exc:
        return _err(exc)
    if not rows:
        return _err(SiteError(f"no verses for surah {surah_id}"))
    return json.dumps({
        "surahId": surah_id,
        "orthographyId": orthography_id,
        "ayahCount": len(rows),
        "url": f"https://quran.inoor.ir/fa/surah/{surah_id}",
        "verses": [
            {
                "ayahNum": v.get("AyahNum"),
                "text": (v.get("Text") or "").strip(),
                "juz": v.get("JuzNumber"),
                "page": v.get("PageNumber"),
                "hasProstration": v.get("HasProstration"),
            }
            for v in rows
        ],
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def quran_ayah_translations(
    surah_id: int, ayah_number: int, page_size: int = 10
) -> str:
    """ترجمه‌های یک آیه قرآن از ده‌ها ترجمه (quran.inoor.ir).

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند ترجمه (پیش‌فرض 10)
    """
    try:
        data = await _qcl().ayah_translations(
            surah_id, ayah_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    return json.dumps({
        "surahId": surah_id,
        "ayahNumber": ayah_number,
        "total": rows[0].get("ResultCount") if rows else 0,
        "translations": [
            {
                "text": strip_em(r.get("Text") or ""),
                "book": r.get("BookTitle"),
                "author": r.get("AuthorFullName"),
                "noorlibId": r.get("NoorlibId"),
            }
            for r in rows
        ],
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def quran_ayah_commentary(
    surah_id: int, ayah_number: int, page_size: int = 5
) -> str:
    """تفاسیر یک آیه قرآن (المیزان، نور الثقلین، مجمع البیان...) — متن کامل تفسیر.

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند تفسیر (پیش‌فرض 5)
    """
    try:
        data = await _qcl().ayah_commentary(
            surah_id, ayah_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    return json.dumps({
        "surahId": surah_id,
        "ayahNumber": ayah_number,
        "commentaries": [
            {
                "bookId": r.get("BookId"),
                "text": strip_em(r.get("Text") or ""),
            }
            for r in rows
        ],
        "hint": "bookId را با quran_commentary_books یا مستقیم از سایت نام کتاب بگیرید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def quran_ayah_hadiths(
    surah_id: int, ayah_number: int, page_size: int = 5
) -> str:
    """احادیث مرتبط با یک آیه قرآن (روایت‌های تفسیری از منابع حدیثی).

    Each item is a group of narrations; hadithId inside the text links to
    hadith.inoor.ir (use hadith_by_id for the full hadith).

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند گروه حدیث (پیش‌فرض 5)
    """
    try:
        data = await _qcl().ayah_hadiths(
            surah_id, ayah_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    import re as _re
    out = []
    for r in rows:
        raw = r.get("Text") or ""
        ids = [m for m in _re.findall(r'hadithId="(\d+)"', raw)]
        plain = html_to_text(raw)
        out.append({"id": r.get("Id"), "text": plain, "hadithIds": ids})
    return json.dumps({
        "surahId": surah_id,
        "ayahNumber": ayah_number,
        "hadithGroups": out,
        "hint": "hadithIds را به hadith_by_id بدهید تا متن کامل و سند حدیث را بگیرید",
    }, ensure_ascii=False, indent=1)


# -------------------------------------------------------------- wikinoor tools
@mcp.tool()
async def wikinoor_search(query: str, limit: int = 10) -> str:
    """جستجو در دانشنامه ویکی‌نور (کتاب‌شناسی و زندگی‌نامه آثار حوزوی).

    33k+ articles about books, authors, publishers — the bibliographic
    backbone of the Noor libraries.

    Args:
        query: عبارت جستجو (مثل «فصوص الحکم» یا «طباطبایی»)
        limit: تعداد نتیجه (پیش‌فرض 10)
    """
    try:
        data = await _wcl().search(query, limit=limit)
    except SiteError as exc:
        return _err(exc)
    hits = (data.get("query") or {}).get("search") or []
    return json.dumps({
        "query": query,
        "total": ((data.get("query") or {}).get("searchinfo") or {}).get("total"),
        "returned": len(hits),
        "results": [
            {
                "title": h.get("title"),
                "snippet": strip_em(h.get("snippet") or ""),
                "wordcount": h.get("wordcount"),
                "url": "https://fa.wikinoor.ir/wiki/" + (h.get("title") or "").replace(" ", "_"),
            }
            for h in hits
        ],
        "hint": "عنوان (title) را به wikinoor_page بدهید تا متن کامل مقاله را بگیرید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def wikinoor_page(title: str, max_length: int = 12000) -> str:
    """متن کامل مقاله ویکی‌نور + جعبه اطلاعات کتاب/شخص.

    Returns the cleaned article text plus structured infobox fields
    (پدیدآورندگان، ناشر، سال نشر، کد کتابخانه دیجیتال نور ...).
    Redirects are followed automatically.

    Args:
        title: عنوان مقاله از wikinoor_search
        max_length: حداکثر طول متن (پیش‌فرض 12000 کاراکتر)
    """
    try:
        data = await _wcl().page(title)
    except SiteError as exc:
        return _err(exc)
    p = data.get("parse") or {}
    wt = (p.get("wikitext") or {}).get("*") or ""
    if not wt:
        return _err(SiteError(f"wikinoor article '{title}' not found"))
    text, infobox = wikitext_to_text(wt)
    if len(text) > max_length:
        text = text[:max_length] + "\n… (بریده شد؛ max_length را بیشتر کنید)"
    return json.dumps({
        "title": p.get("title"),
        "infobox": infobox,
        "text": text,
        "url": "https://fa.wikinoor.ir/wiki/" + (p.get("title") or title).replace(" ", "_"),
    }, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- qamus tools
@mcp.tool()
async def qamus_search(
    text: str,
    category: str = "vocabulary",
    page_index: int = 1,
    page_limit: int = 10,
) -> str:
    """جستجوی واژه در لغت‌نامه قاموس نور (۳۶۹ هزار واژه، ۱۶۳ فرهنگ).

    Returns headwords with meanings from classical Persian/Arabic
    dictionaries (معین، دهخوار، قرشی...).

    Args:
        text: واژه (مثل «نور» یا «توحید»)
        category: vocabulary (واژه) | term (اصطلاح) | name (نام)
        page_index: شماره صفحه نتایج
        page_limit: تعداد نتیجه
    """
    try:
        data = await _mcl().search(
            text, category=category, page_index=page_index, page_limit=page_limit
        )
    except SiteError as exc:
        return _err(exc)
    hws = data.get("headWords") or []
    qty = data.get("quantity") or {}
    out = []
    for h in hws:
        words = []
        for w in h.get("words") or []:
            descs = []
            for d in (w.get("descriptions") or [])[:3]:
                parts = [dd.get("text") for dd in (d.get("descriptionDetails") or [])[:3]]
                descs.append(" | ".join(x for x in parts if x))
            words.append({"word": w.get("text"), "meanings": descs[:3]})
        out.append({
            "headWordId": h.get("id"),
            "headWord": strip_em(h.get("text") or ""),
            "conformity": h.get("conformity"),
            "words": words,
        })
    return json.dumps({
        "query": text,
        "category": category,
        "counts": qty,
        "returned": len(out),
        "headWords": out,
        "hint": "برای معانی کامل‌تر headWordId را به qamus_word بدهید",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def qamus_word(head_word_id: str) -> str:
    """معانی کامل یک واژه از قاموس نور (ریشه، جمع، مثال‌ها، فرهنگ‌ها).

    Args:
        head_word_id: شناسه واژه از qamus_search (مثل 4J781M)
    """
    try:
        d = await _mcl().word(head_word_id)
    except SiteError as exc:
        return _err(exc)
    meanings = []
    for m in d.get("meaning") or []:
        descs = []
        for dd in (m.get("descriptions") or [])[:4]:
            parts = [x.get("text") for x in (dd.get("descriptionDetails") or [])[:4]]
            descs.append(" | ".join(x for x in parts if x))
        meanings.append({"word": m.get("text"), "meanings": descs})
    return json.dumps({
        "headWordId": d.get("id"),
        "headWord": (d.get("headWord") or "").strip(),
        "phonetic": d.get("phoneticTitle"),
        "plural": d.get("pluralWord"),
        "root": d.get("root"),
        "meanings": meanings,
        "url": f"https://qamus.inoor.ir/fa/word/{head_word_id}",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def qamus_dictionaries(page_number: int = 1, page_size: int = 20) -> str:
    """فهرست فرهنگ‌های موجود در قاموس نور (۱۶۳ فرهنگ عمومی و تخصصی).

    Args:
        page_number: شماره صفحه
        page_size: تعداد نتیجه
    """
    try:
        data = await _mcl().dictionaries(
            page_number=page_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("resultList") or []
    return json.dumps({
        "total": data.get("resultListTotalCount"),
        "returned": len(rows),
        "dictionaries": [
            {
                "bookId": b.get("bookId"),
                "link": b.get("link"),
                "creators": [c.get("name") for c in (b.get("creatorList") or [])],
                "language": [l.get("name") for l in (b.get("languageList") or [])],
                "hasText": b.get("hasTextContent"),
            }
            for b in rows
        ],
    }, ensure_ascii=False, indent=1)


# --------------------------------------------------------------- noordoc tools
@mcp.tool()
async def noordoc_search(
    text: str,
    page_number: int = 1,
    page_size: int = 10,
    from_title: bool = True,
) -> str:
    """جستجوی پایان‌نامه‌های علوم اسلامی و انسانی (noordoc.ir — ۱۴۹ هزار پایان‌نامه).

    Returns thesis titles with university, education level, year, advisor.

    Args:
        text: عبارت جستجو (در عنوان پایان‌نامه)
        page_number: شماره صفحه نتایج
        page_size: تعداد نتیجه
        from_title: جستجو در عنوان (true) به‌جای متن کامل
    """
    try:
        data = await _dcl().search(
            text, page_number=page_number, page_size=page_size,
            from_title=from_title,
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("data", {}).get("resultList") or []
    out = []
    for r in rows:
        t = (r.get("titles") or [{}])[0]
        out.append({
            "thesisId": r.get("id"),
            "title": t.get("title"),
            "organization": (r.get("organization") or {}).get("title"),
            "educationLevel": (r.get("educationLevel") or {}).get("title"),
            "year": (r.get("defianceDate") or {}).get("original"),
            "pageCount": r.get("pageCount"),
            "hasPdf": r.get("hasPdf"),
            "students": [s.get("fullName") for s in (r.get("students") or [])][:3],
            "teachers": [s.get("fullName") for s in (r.get("teachers") or [])][:3],
        })
    return json.dumps({
        "query": text,
        "total": data.get("totalCount"),
        "returned": len(out),
        "theses": out,
        "hint": "thesisId را به noordoc_thesis بدهید برای چکیده و جزئیات کامل",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def noordoc_thesis(thesis_id: int) -> str:
    """جزئیات کامل یک پایان‌نامه: چکیده، دانشجو، استاد راهنما، کلیدواژه‌ها.

    Args:
        thesis_id: شناسه پایان‌نامه از noordoc_search
    """
    try:
        d = await _dcl().thesis(thesis_id)
    except SiteError as exc:
        return _err(exc)
    if not d:
        return _err(SiteError(f"thesis {thesis_id} not found"))
    abstracts = [
        {"lang": a.get("language"), "text": a.get("text")}
        for a in (d.get("abstracts") or []) if a.get("text")
    ]
    return json.dumps({
        "thesisId": d.get("id"),
        "title": ((d.get("titles") or [{}])[0]).get("title"),
        "organization": (d.get("organization") or {}).get("title"),
        "college": (d.get("college") or {}).get("title"),
        "field": (d.get("field") or {}).get("title"),
        "educationLevel": (d.get("educationLevel") or {}).get("title"),
        "year": (d.get("defianceDate") or {}).get("original"),
        "pageCount": d.get("pageCount"),
        "hasPdf": d.get("hasPdf"),
        "hasPage": d.get("hasPage"),
        "keywords": [k.get("title") for k in (d.get("keywords") or [])],
        "students": [s.get("fullName") for s in (d.get("students") or [])],
        "teachers": [s.get("fullName") for s in (d.get("teachers") or [])],
        "abstracts": abstracts,
        "url": f"https://noordoc.ir/fa/thesis/view/{thesis_id}",
    }, ensure_ascii=False, indent=1)


# --------------------------------------------------------------- tarikh tools
@mcp.tool()
async def tarikh_search(text: str, page_number: int = 1, page_size: int = 10) -> str:
    """جستجوی رویدادهای تاریخی (tarikh.inoor.ir — صدها هزار رویداد).

    Returns matching historical events (births, deaths, battles, treaties)
    with their hejri-qamari dates.

    Args:
        text: عبارت جستجو (مثل «جنگ جمل» یا «فتح بغداد»)
        page_number: شماره صفحه نتایج
        page_size: تعداد نتیجه
    """
    try:
        data = await _tcl().search(
            text, page_number=page_number, page_size=page_size
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultList") or []
    out = []
    for r in rows:
        ev = r.get("SelectedEvent") or r
        out.append({
            "eventId": ev.get("EventId"),
            "title": strip_em(ev.get("EventTitle") or ""),
            "type": ev.get("EventTypeTitle"),
            "date": decode_tarikh_date(ev.get("StartDate")),
            "comment": strip_em(ev.get("Comment") or "")[:200],
        })
    return json.dumps({
        "query": text,
        "total": data.get("Count"),
        "returned": len(out),
        "events": out,
        "hint": "eventId را به tarikh_event بدهید برای شرح کامل رویداد",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def tarikh_event(event_id: str) -> str:
    """شرح کامل یک رویداد تاریخی (توضیح، شخصیت‌ها، منابع گزارش با لینک noorlib).

    Args:
        event_id: شناسه رویداد از tarikh_search (مثل FF5FD)
    """
    try:
        d = await _tcl().event(event_id)
    except SiteError as exc:
        return _err(exc)
    if not d:
        return _err(SiteError(f"event {event_id} not found"))
    reports = []
    for r in (d.get("EventDetailReports") or [])[:10]:
        reports.append({
            "source": r.get("BookTitle"),
            "summary": strip_em(r.get("Comment") or ""),
            "quote": html_to_text(r.get("SelectedText") or ""),
            "page": r.get("StartPageNumber"),
            "noorlibLink": r.get("NoorLibLink"),
        })
    persons = [
        {"name": p.get("PersonTitle") or p.get("Title"),
         "role": p.get("PersonRoleTitle")}
        for p in (d.get("EventDetailPersons") or [])
        if isinstance(p, dict)
    ]
    return json.dumps({
        "eventId": d.get("EventId"),
        "title": strip_em(d.get("EventTitle") or ""),
        "type": d.get("EventTypeTitle"),
        "date": decode_tarikh_date(d.get("StartDate")),
        "weekDay": d.get("WeekDayPhrase"),
        "description": html_to_text(d.get("Description") or ""),
        "persons": persons,
        "keywords": [
            k.get("Title") or k.get("KeywordTitle")
            for k in (d.get("EventDetailKeywords") or []) if isinstance(k, dict)
        ],
        "reports": reports,
        "url": f"https://tarikh.inoor.ir/fa/event/page/{event_id}",
    }, ensure_ascii=False, indent=1)


@mcp.tool()
async def tarikh_today() -> str:
    """رویدادهای امروز (تقویم هجری قمری) از پایگاه جامع تاریخ."""
    try:
        rows = await _tcl().today()
    except SiteError as exc:
        return _err(exc)
    return json.dumps({
        "count": len(rows),
        "events": [
            {
                "eventId": e.get("EventId"),
                "title": strip_em(e.get("EventTitle") or ""),
                "type": e.get("EventTypeId"),
                "date": decode_tarikh_date(e.get("StartDate")),
                "comment": strip_em(e.get("Comment") or "")[:150],
            }
            for e in rows
        ],
    }, ensure_ascii=False, indent=1)


def main() -> None:
    level = os.environ.get("NOORLIB_MCP_LOG", "INFO").upper()
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s noorlib-mcp %(levelname)s %(message)s",
    )
    if level == "DEBUG":
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.DEBUG)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
