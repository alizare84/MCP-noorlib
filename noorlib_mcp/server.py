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
import functools
import inspect
import json
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from urllib.parse import quote

from .client import NoorlibClient, NoorlibError
from .decoder import DecodeError, decode_page_html
from .hadith_client import HadithClient, HadithError
from .noordoc_client import NoordocClient
from .qamus_client import QamusClient
from .quran_client import QuranClient
from .siteclient import SiteError
from .tarikh_client import TarikhClient, decode_tarikh_date
from .textutil import (
    clean_hadith_text,
    extract_images,
    fold_arabic,
    html_to_text,
    strip_em,
    wikitext_to_text,
)
from .wikinoor_client import WikinoorClient

try:  # ToolAnnotations exists in mcp 1.x and 2.x; degrade gracefully
    from mcp.types import ToolAnnotations

    _ann_kwargs = dict(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
    _ann_fields = getattr(ToolAnnotations, "model_fields", {})
    if "destructiveHint" in _ann_fields or "destructive_hint" in _ann_fields:
        _ann_kwargs["destructiveHint"] = False
    _READ_ONLY: "ToolAnnotations | None" = ToolAnnotations(**_ann_kwargs)
except Exception:  # pragma: no cover - very old SDKs
    _READ_ONLY = None

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

_OPEN_CLIENTS: list = []


def _reg(client):
    """Track live clients so the lifespan hook can close them."""
    _OPEN_CLIENTS.append(client)
    return client


@asynccontextmanager
async def _lifespan(_server):
    """Close all httpx clients when the MCP server shuts down."""
    yield
    for c in _OPEN_CLIENTS:
        try:
            await c.close()
        except Exception:  # pragma: no cover - best effort on shutdown
            pass


def _build_server():
    kw = dict(
        instructions=(
            "عرش الرحمان — unified tools for the Noor family of sites: "
            "noorlib.ir (کتابخانه دیجیتال نور), hadith.inoor.ir "
            "(جامع‌الاحادیث), quran.inoor.ir (قرآن), wikinoor.ir (دانشنامه), "
            "qamus.inoor.ir (لغت‌نامه), noordoc.ir (پایان‌نامه‌ها), "
            "tarikh.inoor.ir (تاریخ). "
            "noorlib: noorlib_search -> noorlib_book_info -> noorlib_book_toc -> "
            "noorlib_book_page, or noorlib_search_in_book for snippets. "
            "hadith: hadith_search -> hadith_by_id; hadith_sources lists books; "
            "hadith_related for similar narrations. "
            "quran: quran_search (exact=True برای تطبیق لفظی) -> "
            "quran_surah_text / quran_ayah_translations / "
            "quran_ayah_commentary / quran_ayah_hadiths. "
            "wikinoor: wikinoor_search -> wikinoor_page. "
            "qamus: qamus_search / qamus_autocomplete -> qamus_word. "
            "noordoc: noordoc_search -> noordoc_thesis / noordoc_thesis_pages. "
            "tarikh: tarikh_search / tarikh_event / tarikh_today."
        ),
        lifespan=_lifespan,
    )
    try:
        return _Server("arsh-alrahman", **kw)
    except TypeError:  # SDK without lifespan support
        kw.pop("lifespan", None)
        return _Server("arsh-alrahman", **kw)


mcp = _build_server()


def _tool(**tool_kw):
    """Register a read-only tool the way an LLM client should see it.

    mcp 2.x would otherwise publish a ``str`` return as structured output
    ``{"result": "<json string>"}``. The payload is already JSON text, so
    clients should receive that text directly. Unexpected exceptions are
    turned into the same ``{"error": ...}`` envelope as site failures,
    because mcp 2 hides the message of an uncaught exception.
    """
    tool_kw.setdefault("annotations", _READ_ONLY)
    if "structured_output" in inspect.signature(mcp.tool).parameters:
        tool_kw.setdefault("structured_output", False)
    register = mcp.tool(**tool_kw)

    def decorate(fn):
        if fn.__doc__:
            fn.__doc__ = inspect.cleandoc(fn.__doc__)

        @functools.wraps(fn)
        async def safe(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                logger.exception("tool %s failed", fn.__name__)
                return _err(exc)

        return register(safe)

    return decorate


def _clip(value: str, limit: int) -> tuple[str, bool]:
    """Truncate long text to `limit` chars; returns (text, truncated)."""
    if limit and len(value) > limit:
        return value[:limit] + " …", True
    return value, False


def _pos(value: int, default: int = 1) -> int:
    """Page numbers and ids are 1-based. Invalid values fall back to `default`."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 1 else default


def _nonneg(value: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number >= 0 else 0


def _cap(value: int, default: int, high: int) -> int:
    """Keep list sizes inside a range an LLM context can hold."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < 1:
        return default
    return min(number, high)


def _budget(value: int, default: int, high: int = 30000) -> int:
    """0 keeps the documented unlimited sentinel; positive values are bounded."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return 0
    return min(number, high)


def _required_text(value: str, label: str) -> str | None:
    if not str(value or "").strip():
        return _err(ValueError(f"{label} خالی است"))
    return None


def _positive_id(value: int, label: str) -> str | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return _err(ValueError(f"{label} نامعتبر است"))
    if number < 1:
        return _err(ValueError(f"{label} باید بزرگ‌تر از صفر باشد"))
    return None


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
        _client = _reg(NoorlibClient())
    return _client


def _hcl() -> HadithClient:
    global _hadith_client
    if _hadith_client is None:
        _hadith_client = _reg(HadithClient())
    return _hadith_client


def _qcl() -> QuranClient:
    global _quran_client
    if _quran_client is None:
        _quran_client = _reg(QuranClient())
    return _quran_client


def _wcl() -> WikinoorClient:
    global _wikinoor_client
    if _wikinoor_client is None:
        _wikinoor_client = _reg(WikinoorClient())
    return _wikinoor_client


def _mcl() -> QamusClient:
    global _qamus_client
    if _qamus_client is None:
        _qamus_client = _reg(QamusClient())
    return _qamus_client


def _dcl() -> NoordocClient:
    global _noordoc_client
    if _noordoc_client is None:
        _noordoc_client = _reg(NoordocClient())
    return _noordoc_client


def _tcl() -> TarikhClient:
    global _tarikh_client
    if _tarikh_client is None:
        _tarikh_client = _reg(TarikhClient())
    return _tarikh_client


def _err(exc: Exception) -> str:
    return json.dumps({"error": str(exc)}, ensure_ascii=False, indent=1)


# --------------------------------------------------------------------- tools
@_tool()
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
    if err := _required_text(query, "query"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _cl().search(query, page_number, page_size, book_id, creator_id, subject_id)
    except NoorlibError as exc:
        return _err(exc)

    books = []
    for grp in data.get("resultList", []):
        if not isinstance(grp, dict):
            continue
        # The search fleet alternates between two shapes:
        # nested groups tagged type=book, and flat book objects with no type.
        kind = grp.get("type")
        if kind not in (None, "", "book"):
            continue
        nested = grp.get("itemList")
        if isinstance(nested, list) and nested:
            items = nested
        elif grp.get("bookId"):
            items = [grp]
        else:
            continue
        for it in items:
            snippet = ""
            snips = [s for s in (it.get("snippetList") or []) if isinstance(s, dict)]
            if snips:
                s0 = next((s for s in snips if (s.get("text") or "").strip()), snips[0])
                body = strip_em(s0.get("text") or "")
                if not body and s0.get("imageUrl"):
                    body = s0.get("imageUrl")
                snippet = "p{} s{} v{}: {}".format(
                    s0.get("pageNumber"),
                    s0.get("sectionNumber"),
                    s0.get("volumeNumber"),
                    body,
                )
            books.append(
                {
                    "bookId": it.get("bookId"),
                    "title": strip_em(it.get("title") or ""),
                    "creators": [c.get("name") for c in (it.get("creatorList") or [])][:4],
                    "matches": it.get("matchListTotalCount"),
                    "isFreeStudy": it.get("isFreeStudy"),
                    "link": "https://noorlib.ir" + (it.get("link") or ""),
                    "sample": snippet,
                }
            )
    return json.dumps(
        {
            "query": query,
            "resultCount": len(books),
            "pageNumber": data.get("pageNumber", page_number),
            "resultListTotalCount": data.get("resultListTotalCount"),
            "books": books,
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def noorlib_book_info(book_id: int) -> str:
    """متادیتای کتاب: عنوان، پدیدآورندگان، تعداد جلد، رایگان بودن، لینک.

    Args:
        book_id: شناسه کتاب در noorlib.ir (مثلا 55202)
    """
    if err := _positive_id(book_id, "book_id"):
        return err
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
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
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
    if err := _positive_id(book_id, "book_id"):
        return err
    offset = _nonneg(offset)
    limit = _cap(limit, 25, 50)
    try:
        data = await _cl().book_toc(book_id, parent_node_id, offset, limit)
    except NoorlibError as exc:
        return _err(exc)
    nodes = []
    for n in data.get("nodes", []):
        nodes.append(
            {
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
            }
        )
    return json.dumps(
        {
            "bookId": book_id,
            "totalCount": data.get("totalCount"),
            "returned": len(nodes),
            "hint": "برای خواندن صفحه از noorlib_book_page، sectionNumber را از zone بگیرید",
            "nodes": nodes,
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def noorlib_book_page(
    book_id: int,
    page_number: int,
    volume_number: int = 1,
    section_number: int = 1,
    max_chars: int = 12000,
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
        max_chars: سقف طول متن خروجی (پیش‌فرض 12000؛ 0 = بی‌سقف)
    """
    if err := _positive_id(book_id, "book_id"):
        return err
    page_number = _pos(page_number)
    volume_number = _pos(volume_number)
    section_number = _pos(section_number)
    max_chars = _budget(max_chars, 12000)
    try:
        pg = await _cl().book_page(book_id, page_number, volume_number, section_number)
        # The backend fleet flip-flops between "credit required" and
        # "successful" for anonymous users; one silent retry often recovers
        # the payload when validation says successful but html is missing.
        if not (pg.get("html") or ""):
            await asyncio.sleep(1.5)
            pg2 = await _cl().book_page(book_id, page_number, volume_number, section_number)
            if pg2.get("html") or "":
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

    text, truncated = _clip(text, max_chars)
    result: dict = {
        "bookId": book_id,
        "pageNumber": pg.get("pageNumber", page_number),
        "volumeNumber": volume_number,
        "sectionNumber": pg.get("sectionNumber", section_number),
        "isEmpty": pg.get("isEmpty"),
        "isFreeStudy": pg.get("isFreeStudy"),
        "validation": validation,
        "text": text,
        "url": (
            f"https://noorlib.ir/book/view/{book_id}"
            f"?volumeNumber={volume_number}&sectionNumber={section_number}"
            f"&pageNumber={page_number}&viewType=html"
        ),
    }
    if truncated:
        result["truncated"] = True
    if images:
        result["images"] = images
        result["imageHint"] = (
            "این صفحه تصویر اسکن دارد؛ URL عمومی است و مستقیم قابل بازکردن است (متن OCR ندارد)."
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


@_tool()
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
    if err := _positive_id(book_id, "book_id"):
        return err
    if err := _required_text(query, "query"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _cl().search_in_book(book_id, query, page_number, page_size, volume_number)
    except NoorlibError as exc:
        return _err(exc)
    hits = []
    for r in data.get("resultList", []):
        sn = r.get("snippet") or {}
        hits.append(
            {
                "pageNumber": sn.get("pageNumber"),
                "sectionNumber": sn.get("sectionNumber"),
                "volumeNumber": sn.get("volumeNumber"),
                "sectionTitle": sn.get("sectionTitle"),
                "tocPath": sn.get("hierarchyToc"),
                "text": strip_em(sn.get("text") or ""),
            }
        )
    return json.dumps(
        {
            "bookId": book_id,
            "query": query,
            "hits": len(hits),
            "results": hits,
            "hint": "برای متن کامل صفحه از noorlib_book_page با sectionNumber همین نتیجه استفاده کنید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def noorlib_find_pages(
    book_id: int,
    query: str,
    volume_number: int = 1,
    page_size: int = 25,
    page_number: int = 1,
) -> str:
    """پیدا کردن شماره صفحه‌هایی که کلمات را دارند (ایندکس ارزان و سریع).

    Returns page/section numbers per matched word — useful before reading
    pages one by one. NOTE: the index API returns at most `page_size`
    rows per call; paginate with page_number.

    Args:
        book_id: شناسه کتاب
        query: کلمه/کلمات
        volume_number: شماره جلد
        page_size: تعداد نتیجه در هر فراخوانی (پیش‌فرض و سقف 25)
        page_number: شماره صفحه نتایج
    """
    if err := _positive_id(book_id, "book_id"):
        return err
    if err := _required_text(query, "query"):
        return err
    volume_number = _pos(volume_number)
    page_number = _pos(page_number)
    page_size = _cap(page_size, 25, 25)
    try:
        rows = await _cl().find_pages(
            book_id,
            query,
            volume_number,
            page_size=page_size,
            page_number=page_number,
        )
    except NoorlibError as exc:
        return _err(exc)
    return json.dumps(
        {
            "bookId": book_id,
            "query": query,
            "page": page_number,
            "returned": len(rows),
            "results": [
                {
                    "pageNumber": r.get("pageNumber"),
                    "sectionNumber": r.get("sectionNumber"),
                    "volumeNumber": r.get("volumeNumber"),
                    "words": r.get("words"),
                }
                for r in rows
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


# ------------------------------------------------------------- hadith tools
@_tool()
async def hadith_search(
    text: str,
    page_number: int = 1,
    page_size: int = 10,
    source_ids: list[int] | None = None,
    search_in: str = "hadith",
    search_type: str = "and",
    is_erab: bool = True,
    translate: bool = False,
    explanation: bool = False,
) -> str:
    """جستجوی متن حدیث در پایگاه جامع‌الاحادیث (hadith.inoor.ir).

    Searches 350+ shi'a hadith sources (کافی، بحار، وسائل، نهج‌البلاغه...).
    Returns highlighted snippets + hadithId + sourceId + volume/page +
    link to the same hadith in noorlib.

    NOTE: this tool does NOT validate sanad/rejal grading — treat results
    as raw source text, not as verified hadith.

    Args:
        text: عبارت جستجو (عربی/فارسی)، مثل «العقل» یا «خیر الناس»
        page_number: صفحه نتایج
        page_size: تعداد نتیجه (5-20)
        source_ids: فهرست sourceId برای محدود کردن به منابع خاص (از hadith_sources)
        search_in: hadith | translate | explanation | all
        search_type: and | or | exact
        is_erab: جستجو با اعراب
        translate: جستجو در ترجمه‌ها
        explanation: جستجو در شرح‌ها
    """
    if err := _required_text(text, "text"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _hcl().search(
            text,
            page_number,
            page_size,
            source_ids,
            search_in,
            search_type,
            is_erab=is_erab,
            translate=translate,
            explanation=explanation,
        )
    except HadithError as exc:
        return _err(exc)

    results = []
    for r in data.get("resultList", []):
        hl = r.get("highLight") or []
        snippet = strip_em(hl[0]) if hl else ""
        results.append(
            {
                "hadithId": r.get("hadithId"),
                "sourceId": r.get("sourceId"),
                "book": r.get("bookTitleShort") or r.get("bookTitle"),
                "author": r.get("authorTitle"),
                "vol": r.get("vol"),
                "page": r.get("pageNum"),
                "snippet": snippet,
                "noorlibLink": r.get("noorLibLink"),
            }
        )
    return json.dumps(
        {
            "query": text,
            "hadithCount": data.get("hadithCount"),
            "groupCount": data.get("groupCount"),
            "returned": len(results),
            "results": results,
            "hint": "برای متن کامل حدیث و سند، hadithId را به hadith_by_id بدهید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def hadith_by_id(hadith_id: int, search_phrase: str = "", max_chars: int = 12000) -> str:
    """متن کامل یک حدیث + سند + مسیر کتاب (hadith.inoor.ir).

    Returns the full text (with narrator chain preserved in `narrators`),
    TOC path (کتاب/باب), translations list and the same-hadith occurrences
    in other sources (groupTogetherList).

    NOTE: sanad/rejal grading is NOT validated here.

    Args:
        hadith_id: شناسه حدیث از hadith_search
        search_phrase: عبارت جستجو برای هایلایت (اختیاری)
        max_chars: سقف طول متن حدیث (پیش‌فرض 12000؛ 0 = بی‌سقف)
    """
    if err := _positive_id(hadith_id, "hadith_id"):
        return err
    max_chars = _budget(max_chars, 12000)
    try:
        rows = await _hcl().hadith_by_id([hadith_id], "arabic", search_phrase)
    except HadithError as exc:
        return _err(exc)
    if not rows:
        return _err(HadithError(f"hadith {hadith_id} not found"))
    r = rows[0]
    plain, structure = clean_hadith_text(r.get("text") or "")
    toc_path = [t.get("title") for t in (r.get("tocInfo") or []) if t.get("title")]
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
    plain, truncated = _clip(plain, max_chars)
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
    if truncated:
        result["truncated"] = True
    return json.dumps(result, ensure_ascii=False, indent=1)


@_tool()
async def hadith_sources(query: str = "", page_size: int = 50, page_number: int = 1) -> str:
    """فهرست منابع حدیثی hadith.inoor.ir (۳۵۰+ کتاب) با sourceId هرکدام.

    Filtering is Unicode-folded (ك↔ک, ي↔ی, alef/heh forms, tashkeel) so
    both Arabic and Persian letter forms match.

    NOTE: sourceId comes back as a STRING — pass it through as-is.

    Args:
        query: فیلتر عنوان/نویسنده (مثل «کافی» یا «مجلسی»؛ خالی = همه)
        page_size: تعداد نتیجه (پیش‌فرض 50)
        page_number: صفحه نتایج
    """
    page_number = _pos(page_number)
    page_size = _cap(page_size, 50, 100)
    try:
        rows = await _hcl().sources(page_size=900)
    except HadithError as exc:
        return _err(exc)
    q = fold_arabic(query)
    if q:
        rows = [
            s
            for s in rows
            if q
            in fold_arabic(
                " ".join(
                    x
                    for x in (
                        s.get("title"),
                        s.get("shortTitle"),
                        s.get("author"),
                    )
                    if x
                )
            )
        ]
    total = len(rows)
    start = (page_number - 1) * page_size
    rows = rows[start : start + page_size]
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def hadith_toc(source_id: int) -> str:
    """فهرست مطالب یک منبع حدیثی (کتاب‌ها و ابواب).

    Args:
        source_id: شناسه منبع از hadith_sources (رشته؛ مثلا '2643' = الروضة من الكافي). منابع بدون TOC، فهرست خالی می‌دهند.
    """
    if err := _positive_id(source_id, "source_id"):
        return err
    try:
        nodes = await _hcl().toc(source_id)
    except HadithError as exc:
        return _err(exc)
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
        indent=1,
    )


# ---------------------------------------------------------------- quran tools
@_tool()
async def quran_search(
    text: str,
    source: str = "quran",
    page_number: int = 1,
    page_size: int = 10,
    exact: bool = False,
) -> str:
    """جستجو در قرآن (quran.inoor.ir): متن عربی آیات یا ترجمه‌های فارسی.

    source='quran' searches the Arabic text; source='translation' searches
    150+ translations. By default root/stem/synonym expansion is ON —
    results may NOT contain the literal word. Set exact=True when the
    model must claim "the word X appears in verse Y".

    Args:
        text: عبارت جستجو (مثل «نور» یا «توحید»)
        source: quran | translation
        page_number: صفحه نتایج
        page_size: تعداد نتیجه (5-20)
        exact: true = فقط تطبیق لفظی خود کلمه (بدون ریشه/مشتق/مترادف)
    """
    if err := _required_text(text, "text"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _qcl().search(
            text,
            source=source,
            page_number=page_number,
            page_size=page_size,
            exact=exact,
        )
    except SiteError as exc:
        return _err(exc)
    results = []
    for r in data.get("resultList") or []:
        results.append(
            {
                "surahId": r.get("surahId"),
                "surah": r.get("surahTitle"),
                "ayahNumber": r.get("ayahNumber"),
                "text": strip_em(r.get("text") or ""),
                "link": r.get("link"),
            }
        )
    return json.dumps(
        {
            "query": text,
            "source": source,
            "exact": exact,
            "total": data.get("resultListTotalCount"),
            "returned": len(results),
            "results": results,
            "hint": "برای ترجمه/تفسیر/احادیث این آیه از quran_ayah_* با surahId+ayahNumber استفاده کنید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def quran_surahs() -> str:
    """فهرست ۱۱۴ سوره قرآن با شماره، نام و تعداد آیات.

    شمارهٔ سوره (`surahId`) را به quran_surah_text، و برای یک آیه به
    quran_ayah_translations / quran_ayah_commentary / quran_ayah_hadiths بدهید.
    """
    try:
        rows = await _qcl().surahs()
    except SiteError as exc:
        return _err(exc)
    return json.dumps(
        {
            "count": len(rows),
            "surahs": [
                {
                    "surahId": s.get("Id"),
                    "title": s.get("Title"),
                    "names": s.get("PopularNames"),
                    "ayahCount": s.get("AyahCount"),
                    "juz": s.get("JuzNumber"),
                }
                for s in rows
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def quran_surah_text(
    surah_id: int,
    orthography_id: int = 4,
    ayah_from: int = 1,
    ayah_to: int | None = None,
    max_chars: int = 20000,
) -> str:
    """متن آیات یک سوره قرآن با بازه‌ی دلخواه و سقف خروجی.

    متن آیات verbatim است؛ مدل نباید آن را بازنویسی کند. برای سوره‌های
    بزرگ (بقره، آل‌عمران...) بازه ayah_from/ayah_to بدهید.

    Args:
        surah_id: شماره سوره 1-114 (از quran_surahs)
        orthography_id: نوع خط؛ 4=عثمان طه (پیش‌فرض)، 2=ساده، 5=املایی، 7=مصحف ایران
        ayah_from: اولین آیه (1-based)
        ayah_to: آخرین آیه (None = تا آخر سوره)
        max_chars: سقف مجموع طول متن آیات (پیش‌فرض 20000)
    """
    if not 1 <= _pos(surah_id, 0) <= 114:
        return _err(ValueError("surah_id باید بین ۱ و ۱۱۴ باشد"))
    ayah_from = _pos(ayah_from)
    if ayah_to is not None and int(ayah_to) < ayah_from:
        return _err(ValueError("ayah_to باید بزرگ‌تر یا مساوی ayah_from باشد"))
    max_chars = _budget(max_chars, 20000)
    try:
        rows = await _qcl().surah_text(surah_id, orthography_id)
    except SiteError as exc:
        return _err(exc)
    if not rows:
        return _err(SiteError(f"no verses for surah {surah_id}"))
    upper = ayah_to if ayah_to is not None else 10**9
    verses, total_len, truncated = [], 0, False
    for v in rows:
        num = v.get("AyahNum")
        try:
            num_i: int | None = int(num)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            num_i = None  # unparseable: keep the row, cannot judge range
        if num_i is not None and (num_i < ayah_from or num_i > upper):
            continue
        t = (v.get("Text") or "").strip()
        over = bool(max_chars and total_len + len(t) > max_chars)
        if over and verses:
            truncated = True
            break
        if over:
            # The first verse is longer than the whole budget: return it
            # clipped instead of reporting an empty range.
            t, truncated = _clip(t, max_chars)
        total_len += len(t)
        verses.append(
            {
                "ayahNum": num,
                "text": t,
                "juz": v.get("JuzNumber"),
                "page": v.get("PageNumber"),
                "hasProstration": v.get("HasProstration"),
            }
        )
        if over:
            break
    if not verses:
        return _err(
            SiteError(
                f"no verses in range {ayah_from}-{ayah_to if ayah_to else '?'} for surah {surah_id}"
            )
        )
    ref = f"{surah_id}:{verses[0]['ayahNum']}"
    if len(verses) > 1:
        ref += f"-{verses[-1]['ayahNum']}"
    return json.dumps(
        {
            "surahId": surah_id,
            "orthographyId": orthography_id,
            "ref": ref,
            "returnedAyahs": len(verses),
            "truncated": truncated,
            "url": f"https://quran.inoor.ir/fa/surah/{surah_id}",
            "verses": verses,
            "hint": (
                "متن آیات عیناً از پایگاه برگردانده شده؛ ارجاع استاندارد فیلد ref است"
                if not truncated
                else "خروجی به سقف max_chars رسید؛ برای بقیه‌ی آیات از ayah_from/ayah_to استفاده کنید"
            ),
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def quran_ayah_translations(
    surah_id: int,
    ayah_number: int,
    page_size: int = 10,
    page_number: int = 1,
    book_ids: str = "",
    language_ids: str = "",
) -> str:
    """ترجمه‌های یک آیه قرآن از ده‌ها ترجمه (quran.inoor.ir).

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند ترجمه (پیش‌فرض 10)
        page_number: صفحه نتایج (برای دیدن ترجمه‌های بیشتر)
        book_ids: شناسه کتاب(های) ترجمه جدا شده با کاما برای انتخاب ترجمه خاص
        language_ids: شناسه زبان(ها) برای ترجمه‌های غیر فارسی
    """
    if err := _positive_id(surah_id, "surah_id"):
        return err
    if err := _positive_id(ayah_number, "ayah_number"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _qcl().ayah_translations(
            surah_id,
            ayah_number,
            page_size=page_size,
            page_number=page_number,
            book_ids=book_ids,
            language_ids=language_ids,
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    return json.dumps(
        {
            "surahId": surah_id,
            "ayahNumber": ayah_number,
            "ref": f"{surah_id}:{ayah_number}",
            "total": rows[0].get("ResultCount") if rows else 0,
            "page": page_number,
            "translations": [
                {
                    "text": strip_em(r.get("Text") or ""),
                    "book": r.get("BookTitle"),
                    "author": r.get("AuthorFullName"),
                    "noorlibId": r.get("NoorlibId"),
                }
                for r in rows
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def quran_ayah_commentary(
    surah_id: int,
    ayah_number: int,
    page_size: int = 5,
    page_number: int = 1,
    book_ids: str = "",
    author_ids: str = "",
    max_chars: int = 6000,
) -> str:
    """تفاسیر یک آیه قرآن (المیزان، نور الثقلین، مجمع البیان...) — با فیلتر.

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند تفسیر (پیش‌فرض 5)
        page_number: صفحه نتایج
        book_ids: شناسه کتاب(های) تفسیر جدا شده با کاما برای انتخاب تفسیر خاص
        author_ids: شناسه مؤلف(ها) جدا شده با کاما
        max_chars: سقف طول هر متن تفسیر (پیش‌فرض 6000)
    """
    if err := _positive_id(surah_id, "surah_id"):
        return err
    if err := _positive_id(ayah_number, "ayah_number"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 5, 10)
    max_chars = _budget(max_chars, 6000)
    try:
        data = await _qcl().ayah_commentary(
            surah_id,
            ayah_number,
            page_size=page_size,
            page_number=page_number,
            book_ids=book_ids,
            author_ids=author_ids,
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    commentaries = []
    for r in rows:
        t, tclip = _clip(strip_em(r.get("Text") or ""), max_chars)
        item: dict = {
            "bookId": r.get("BookId"),
            "book": r.get("BookTitle") or r.get("BookName"),
            "text": t,
        }
        if tclip:
            item["truncated"] = True
        commentaries.append(item)
    return json.dumps(
        {
            "surahId": surah_id,
            "ayahNumber": ayah_number,
            "ref": f"{surah_id}:{ayah_number}",
            "commentaries": commentaries,
            "hint": "برای انتخاب یک تفسیر خاص book_ids همان کتاب را بفرستید؛ شناسه‌ها را می‌توانید از ویکی‌نور (wikinoor_page، فیلد کد کتابخانه) بگیرید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def quran_ayah_hadiths(
    surah_id: int,
    ayah_number: int,
    page_size: int = 5,
    page_number: int = 1,
    book_ids: str = "",
    max_chars: int = 6000,
) -> str:
    """احادیث مرتبط با یک آیه قرآن (روایت‌های تفسیری از منابع حدیثی).

    Each item is a group of narrations; hadithId inside the text links to
    hadith.inoor.ir (use hadith_by_id for the full hadith).

    Args:
        surah_id: شماره سوره (1-114)
        ayah_number: شماره آیه داخل سوره
        page_size: چند گروه حدیث (پیش‌فرض 5)
        page_number: صفحه نتایج
        book_ids: شناسه منبع(های) حدیثی جدا شده با کاما
        max_chars: سقف طول هر گروه متن (پیش‌فرض 6000)
    """
    if err := _positive_id(surah_id, "surah_id"):
        return err
    if err := _positive_id(ayah_number, "ayah_number"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 5, 10)
    max_chars = _budget(max_chars, 6000)
    try:
        data = await _qcl().ayah_hadiths(
            surah_id,
            ayah_number,
            page_size=page_size,
            page_number=page_number,
            book_ids=book_ids,
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultSet1") or []
    out = []
    for r in rows:
        raw = r.get("Text") or ""
        ids = re.findall(r'hadithId="(\d+)"', raw)
        plain = html_to_text(raw)
        plain, tclip = _clip(plain, max_chars)
        item: dict = {"id": r.get("Id"), "text": plain, "hadithIds": ids}
        if tclip:
            item["truncated"] = True
        out.append(item)
    return json.dumps(
        {
            "surahId": surah_id,
            "ayahNumber": ayah_number,
            "ref": f"{surah_id}:{ayah_number}",
            "hadithGroups": out,
            "hint": "hadithIds را به hadith_by_id بدهید تا متن کامل و سند حدیث را بگیرید",
        },
        ensure_ascii=False,
        indent=1,
    )


# -------------------------------------------------------------- wikinoor tools
@_tool()
async def wikinoor_search(query: str, limit: int = 10) -> str:
    """جستجو در دانشنامه ویکی‌نور (کتاب‌شناسی و زندگی‌نامه آثار حوزوی).

    33k+ articles about books, authors, publishers — the bibliographic
    backbone of the Noor libraries.

    Args:
        query: عبارت جستجو (مثل «فصوص الحکم» یا «طباطبایی»)
        limit: تعداد نتیجه (پیش‌فرض 10)
    """
    if err := _required_text(query, "query"):
        return err
    limit = _cap(limit, 10, 20)
    try:
        data = await _wcl().search(query, limit=limit)
    except SiteError as exc:
        return _err(exc)
    hits = (data.get("query") or {}).get("search") or []
    return json.dumps(
        {
            "query": query,
            "total": ((data.get("query") or {}).get("searchinfo") or {}).get("total"),
            "returned": len(hits),
            "results": [
                {
                    "title": h.get("title"),
                    "snippet": strip_em(h.get("snippet") or ""),
                    "wordcount": h.get("wordcount"),
                    "url": "https://fa.wikinoor.ir/wiki/"
                    + quote((h.get("title") or "").replace(" ", "_")),
                }
                for h in hits
            ],
            "hint": "عنوان (title) را به wikinoor_page بدهید تا متن کامل مقاله را بگیرید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def wikinoor_page(title: str, max_length: int = 12000) -> str:
    """متن کامل مقاله ویکی‌نور + جعبه اطلاعات کتاب/شخص.

    Returns the cleaned article text plus structured infobox fields
    (پدیدآورندگان، ناشر، سال نشر، کد کتابخانه دیجیتال نور ...).
    Redirects are followed automatically.

    Args:
        title: عنوان مقاله از wikinoor_search
        max_length: حداکثر طول متن (پیش‌فرض 12000 کاراکتر)
    """
    if err := _required_text(title, "title"):
        return err
    max_length = _budget(max_length, 12000)
    try:
        data = await _wcl().page(title)
    except SiteError as exc:
        return _err(exc)
    p = data.get("parse") or {}
    wt = (p.get("wikitext") or {}).get("*") or ""
    if not wt:
        return _err(SiteError(f"wikinoor article '{title}' not found"))
    text, infobox = wikitext_to_text(wt)
    text, truncated = _clip(text, max_length)
    return json.dumps(
        {
            "title": p.get("title"),
            "infobox": infobox,
            "text": text,
            "truncated": truncated,
            "url": "https://fa.wikinoor.ir/wiki/"
            + quote((p.get("title") or title).replace(" ", "_")),
        },
        ensure_ascii=False,
        indent=1,
    )


# ---------------------------------------------------------------- qamus tools
@_tool()
async def qamus_search(
    text: str,
    category: str = "vocabulary",
    page_index: int = 1,
    page_limit: int = 10,
    search_in: str = "fa",
) -> str:
    """جستجوی واژه در لغت‌نامه قاموس نور (۳۶۹ هزار واژه، ۱۶۳ فرهنگ).

    Returns headwords with meanings from classical Persian/Arabic
    dictionaries (معین، دهخوار، قرشی...).

    Args:
        text: واژه (مثل «نور» یا «توحید»)
        category: vocabulary (واژه) | term (اصطلاح) | name (نام) — مقدار نامعتبر خطا می‌دهد
        page_index: شماره صفحه نتایج
        page_limit: تعداد نتیجه
        search_in: زبان ورودی: fa (پیش‌فرض) | ar (واژه عربی)
    """
    if err := _required_text(text, "text"):
        return err
    page_index = _pos(page_index)
    page_limit = _cap(page_limit, 10, 20)
    try:
        data = await _mcl().search(
            text,
            category=category,
            page_index=page_index,
            page_limit=page_limit,
            search_in=search_in,
        )
    except (SiteError, ValueError) as exc:
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
        out.append(
            {
                "headWordId": h.get("id"),
                "headWord": strip_em(h.get("text") or ""),
                "conformity": h.get("conformity"),
                "words": words,
            }
        )
    return json.dumps(
        {
            "query": text,
            "category": category,
            "counts": qty,
            "returned": len(out),
            "headWords": out,
            "hint": "برای معانی کامل‌تر headWordId را به qamus_word بدهید",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def qamus_word(head_word_id: str) -> str:
    """معانی کامل یک واژه از قاموس نور (ریشه، جمع، مثال‌ها، فرهنگ‌ها).

    Args:
        head_word_id: شناسه واژه از qamus_search (مثل 4J781M)
    """
    if err := _required_text(head_word_id, "head_word_id"):
        return err
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
    return json.dumps(
        {
            "headWordId": d.get("id"),
            "headWord": (d.get("headWord") or "").strip(),
            "phonetic": d.get("phoneticTitle"),
            "plural": d.get("pluralWord"),
            "root": d.get("root"),
            "meanings": meanings,
            "url": f"https://qamus.inoor.ir/fa/word/{head_word_id}",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def qamus_dictionaries(page_number: int = 1, page_size: int = 20, query: str = "") -> str:
    """فهرست فرهنگ‌های موجود در قاموس نور (۱۶۳ فرهنگ عمومی و تخصصی).

    Args:
        page_number: شماره صفحه
        page_size: تعداد نتیجه
        query: فیلتر عنوان فرهنگ (مثل «قرشی»)
    """
    page_number = _pos(page_number)
    page_size = _cap(page_size, 20, 50)
    try:
        data = await _mcl().dictionaries(page_number=page_number, page_size=page_size, query=query)
    except SiteError as exc:
        return _err(exc)
    rows = data.get("resultList") or []
    return json.dumps(
        {
            "total": data.get("resultListTotalCount"),
            "returned": len(rows),
            "dictionaries": [
                {
                    "bookId": b.get("bookId"),
                    "title": strip_em(b.get("title") or ""),
                    "link": b.get("link"),
                    "creators": [c.get("name") for c in (b.get("creatorList") or [])],
                    "language": [lang.get("name") for lang in (b.get("languageList") or [])],
                    "hasText": b.get("hasTextContent"),
                }
                for b in rows
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


# --------------------------------------------------------------- noordoc tools
@_tool()
async def noordoc_search(
    text: str,
    page_number: int = 1,
    page_size: int = 10,
    from_title: bool = True,
    organization: str | None = None,
    education_level: str | None = None,
    has_pdf: int = 0,
) -> str:
    """جستجوی پایان‌نامه‌های علوم اسلامی و انسانی (noordoc.ir — ۱۴۹ هزار پایان‌نامه).

    Returns thesis titles with university, education level, year, advisor.

    Args:
        text: عبارت جستجو (در عنوان پایان‌نامه)
        page_number: شماره صفحه نتایج
        page_size: تعداد نتیجه
        from_title: جستجو در عنوان (true) به‌جای متن کامل
        organization: فیلتر دانشگاه/سازمان (مثل «دانشگاه تهران»)
        education_level: فیلتر مقطع (کارشناسی ارشد | دکتری)
        has_pdf: 1 = فقط پایان‌نامه‌های دارای PDF
    """
    if err := _required_text(text, "text"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _dcl().search(
            text,
            page_number=page_number,
            page_size=page_size,
            from_title=from_title,
            organization=organization,
            education_level=education_level,
            has_pdf=has_pdf,
        )
    except SiteError as exc:
        return _err(exc)
    rows = (data.get("data") or {}).get("resultList") or []
    out = []
    for r in rows:
        t = (r.get("titles") or [{}])[0]
        out.append(
            {
                "thesisId": r.get("id"),
                "title": t.get("title"),
                "organization": (r.get("organization") or {}).get("title"),
                "educationLevel": (r.get("educationLevel") or {}).get("title"),
                "year": (r.get("defianceDate") or {}).get("original"),
                "pageCount": r.get("pageCount"),
                "hasPdf": r.get("hasPdf"),
                "students": [s.get("fullName") for s in (r.get("students") or [])][:3],
                "teachers": [s.get("fullName") for s in (r.get("teachers") or [])][:3],
            }
        )
    return json.dumps(
        {
            "query": text,
            "total": data.get("totalCount"),
            "returned": len(out),
            "theses": out,
            "hint": "thesisId را به noordoc_thesis بدهید برای چکیده و جزئیات کامل",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def noordoc_thesis(thesis_id: int) -> str:
    """جزئیات کامل یک پایان‌نامه: چکیده، دانشجو، استاد راهنما، کلیدواژه‌ها.

    Args:
        thesis_id: شناسه پایان‌نامه از noordoc_search
    """
    if err := _positive_id(thesis_id, "thesis_id"):
        return err
    try:
        d = await _dcl().thesis(thesis_id)
    except SiteError as exc:
        return _err(exc)
    if not d:
        return _err(SiteError(f"thesis {thesis_id} not found"))
    abstracts = [
        {"lang": a.get("language"), "text": a.get("text")}
        for a in (d.get("abstracts") or [])
        if a.get("text")
    ]
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
        indent=1,
    )


def _event_type(row: dict):
    """Prefer the human-readable event type; fall back to the numeric id."""
    title = row.get("EventTypeTitle")
    if title:
        return title
    return row.get("EventTypeId")


# --------------------------------------------------------------- tarikh tools
@_tool()
async def tarikh_search(
    text: str,
    page_number: int = 1,
    page_size: int = 10,
    event_type_id: int = 0,
    source_id: int = 0,
    start_date: int = 0,
    end_date: int = 0,
) -> str:
    """جستجوی رویدادهای تاریخی (tarikh.inoor.ir — صدها هزار رویداد).

    Returns matching historical events (births, deaths, battles, treaties)
    with their dates. Dates are hejri-qamari per the upstream API.

    Args:
        text: عبارت جستجو (مثل «جنگ جمل» یا «فتح بغداد»)
        page_number: شماره صفحه نتایج
        page_size: تعداد نتیجه
        event_type_id: شناسه نوع رویداد (0 = همه)
        source_id: شناسه منبع (0 = همه)
        start_date: آغاز بازه تاریخ، قالب YYMMDD قمری مثل 610801 = 61/08/01 (0 = بدون فیلتر)
        end_date: پایان بازه تاریخ، همان قالب (0 = بدون فیلتر)
    """
    if err := _required_text(text, "text"):
        return err
    page_number = _pos(page_number)
    page_size = _cap(page_size, 10, 20)
    try:
        data = await _tcl().search(
            text,
            page_number=page_number,
            page_size=page_size,
            event_type_id=event_type_id,
            source_id=source_id,
            start_date=start_date,
            end_date=end_date,
        )
    except SiteError as exc:
        return _err(exc)
    rows = data.get("ResultList") or []
    out = []
    for r in rows:
        ev = r.get("SelectedEvent") or r
        out.append(
            {
                "eventId": ev.get("EventId"),
                "title": strip_em(ev.get("EventTitle") or ""),
                "type": _event_type(ev),
                "date": decode_tarikh_date(ev.get("StartDate")),
                "comment": strip_em(ev.get("Comment") or "")[:200],
            }
        )
    return json.dumps(
        {
            "query": text,
            "total": data.get("Count"),
            "returned": len(out),
            "events": out,
            "hint": "eventId را به tarikh_event بدهید برای شرح کامل رویداد",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def tarikh_event(event_id: str) -> str:
    """شرح کامل یک رویداد تاریخی (توضیح، شخصیت‌ها، منابع گزارش با لینک noorlib).

    Args:
        event_id: شناسه رویداد از tarikh_search (مثل FF5FD)
    """
    if err := _required_text(event_id, "event_id"):
        return err
    try:
        d = await _tcl().event(event_id)
    except SiteError as exc:
        return _err(exc)
    if not d:
        return _err(SiteError(f"event {event_id} not found"))
    reports = []
    for r in (d.get("EventDetailReports") or [])[:10]:
        reports.append(
            {
                "source": r.get("BookTitle"),
                "summary": strip_em(r.get("Comment") or ""),
                "quote": html_to_text(r.get("SelectedText") or ""),
                "page": r.get("StartPageNumber"),
                "noorlibLink": r.get("NoorLibLink"),
            }
        )
    persons = [
        {"name": p.get("PersonTitle") or p.get("Title"), "role": p.get("PersonRoleTitle")}
        for p in (d.get("EventDetailPersons") or [])
        if isinstance(p, dict)
    ]
    return json.dumps(
        {
            "eventId": d.get("EventId"),
            "title": strip_em(d.get("EventTitle") or ""),
            "type": _event_type(d),
            "date": decode_tarikh_date(d.get("StartDate")),
            "weekDay": d.get("WeekDayPhrase"),
            "description": html_to_text(d.get("Description") or ""),
            "persons": persons,
            "keywords": [
                k.get("Title") or k.get("KeywordTitle")
                for k in (d.get("EventDetailKeywords") or [])
                if isinstance(k, dict)
            ],
            "reports": reports,
            "url": f"https://tarikh.inoor.ir/fa/event/page/{event_id}",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def tarikh_today() -> str:
    """رویدادهای امروز در تقویم هجری قمری.

    هر ردیف `eventId` دارد؛ برای شرح کامل آن را به tarikh_event بدهید.
    فیلد `type` عنوان نوع رویداد است و اگر عنوان نباشد شناسهٔ عددی است.
    """
    try:
        rows = await _tcl().today()
    except SiteError as exc:
        return _err(exc)
    return json.dumps(
        {
            "count": len(rows),
            "events": [
                {
                    "eventId": e.get("EventId"),
                    "title": strip_em(e.get("EventTitle") or ""),
                    "type": _event_type(e),
                    "date": decode_tarikh_date(e.get("StartDate")),
                    "comment": strip_em(e.get("Comment") or "")[:150],
                }
                for e in rows
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


# --------------------------------------------------------------- extra tools
@_tool()
async def hadith_related(hadith_id: int, source_id: int) -> str:
    """حدیث‌های مشابه یک حدیث (RelatedHadith در hadith.inoor.ir).

    Args:
        hadith_id: شناسه حدیث از hadith_search
        source_id: شناسه منبع همان حدیث
    """
    if err := _positive_id(hadith_id, "hadith_id"):
        return err
    if err := _positive_id(source_id, "source_id"):
        return err
    try:
        rows = await _hcl().related(hadith_id, source_id)
    except HadithError as exc:
        return _err(exc)
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        out.append(
            {
                "hadithId": r.get("hadithId"),
                "sourceId": r.get("sourceId"),
                "book": r.get("bookTitleShort") or r.get("bookTitle"),
                "vol": r.get("vol"),
                "page": r.get("pageNum"),
                "snippet": strip_em(r.get("text") or "")[:300],
            }
        )
    return json.dumps(
        {
            "hadithId": hadith_id,
            "returned": len(out),
            "related": out,
            "hint": "hadithId را به hadith_by_id بدهید برای متن کامل",
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def qamus_autocomplete(word: str, lang: str = "fa") -> str:
    """پیشنهاد واژه‌ها برای املای نادرست/ناقص (قاموس نور).

    Args:
        word: پیشوند یا قسمتی از واژه
        lang: fa | ar
    """
    if err := _required_text(word, "word"):
        return err
    try:
        rows = await _mcl().autocomplete(word, lang=lang)
    except SiteError as exc:
        return _err(exc)
    return json.dumps(
        {
            "word": word,
            "suggestions": rows[:20] if isinstance(rows, list) else [],
        },
        ensure_ascii=False,
        indent=1,
    )


@_tool()
async def noordoc_thesis_pages(thesis_id: int, limit: int = 20) -> str:
    """فهرست صفحات موجود (اینونتاری) یک پایان‌نامه در noordoc.ir.

    Args:
        thesis_id: شناسه پایان‌نامه از noordoc_search
        limit: حداکثر تعداد ردیف
    """
    if err := _positive_id(thesis_id, "thesis_id"):
        return err
    limit = _cap(limit, 20, 50)
    try:
        items = await _dcl().thesis_pages(thesis_id, limit=limit)
    except SiteError as exc:
        return _err(exc)
    return json.dumps(
        {
            "thesisId": thesis_id,
            "returned": len(items),
            "pages": items,
            "url": f"https://noordoc.ir/fa/thesis/view/{thesis_id}",
        },
        ensure_ascii=False,
        indent=1,
    )


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
