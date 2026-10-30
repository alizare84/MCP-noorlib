"""MCP server exposing noorlib.ir tools (stdio transport).

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
from .textutil import extract_images, html_to_text, strip_em

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
mcp = _Server("noorlib", instructions=(
    "Tools for noorlib.ir (کتابخانه دیجیتال نور). Typical flow: "
    "noorlib_search to find books -> noorlib_book_info for metadata -> "
    "noorlib_book_toc to navigate -> noorlib_book_page to read a page. "
    "For finding text inside one book use noorlib_search_in_book (returns "
    "snippets) instead of fetching pages one by one."
))

_client: NoorlibClient | None = None


def _cl() -> NoorlibClient:
    global _client
    if _client is None:
        _client = NoorlibClient()
    return _client


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
