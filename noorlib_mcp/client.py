"""Async HTTP client for the (unofficial) noorlib.ir JSON API.

Endpoints (reverse-engineered from https://noorlib.ir/_nuxt/*.js):

    POST /api/book/getGeneralBookInfo        {origin, language, bookId, type}
    GET  /api/book/getBookTOC                ?origin&language&bookId&offset&limit&parentNodeId
    POST /api/book/getBookPageContent        {origin, language, bookId, volumeNumber,
                                              sectionNumber, viewType, pageNumber}
    POST /api/search/generalSearchPhrase     {origin, language, query, sp.*, page_*}
    POST /api/search/bookSearchPhrasePageList {origin, language, query, sp.book_id, ...}
    POST /api/search/pageSearchPhrase        {origin, language, query, sp.book_id, sp.page, ...}

Design notes for the three field-reported issues:

* Proxy — many Iranian networks run a local proxy (http_proxy=127.0.0.1:10808)
  that MITMs and breaks TLS to noorlib.ir.  By default the client IGNORES the
  ambient proxy environment (trust_env=False) and connects directly, because
  noorlib.ir is reachable directly and its certificate is valid.  Set
  ``NOORLIB_MCP_USE_PROXY=1`` to honour http_proxy/https_proxy/no_proxy again.
* Error text — every network failure now embeds the underlying exception text
  (previously messages looked like ``transport error:`` with no detail).
* Paywall — page reads consume credit for non-free ranges.  The response's
  ``validation`` block is surfaced verbatim, and an optional bearer token
  (``NOORLIB_MCP_AUTH``) is sent on every call so authenticated users with
  credit can read full pages.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("NOORLIB_MCP_BASE_URL", "https://noorlib.ir")
TIMEOUT = float(os.environ.get("NOORLIB_MCP_TIMEOUT", "30"))
THROTTLE = float(os.environ.get("NOORLIB_MCP_THROTTLE", "1.2"))
RETRIES = int(os.environ.get("NOORLIB_MCP_RETRIES", "3"))

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
)


class NoorlibError(RuntimeError):
    """Any failure while talking to noorlib.ir."""


class NoorlibClient:
    def __init__(self, auth_token: str | None = None) -> None:
        self._auth = auth_token or os.environ.get("NOORLIB_MCP_AUTH", "")
        use_proxy = os.environ.get("NOORLIB_MCP_USE_PROXY", "").strip() in (
            "1", "true", "TRUE", "yes",
        )
        headers = {
            "User-Agent": _UA,
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/",
            "Accept": "application/json, text/plain, */*",
        }
        if self._auth:
            token = self._auth.strip()
            if not token.lower().startswith("bearer"):
                token = "Bearer " + token
            headers["Authorization"] = token
        # trust_env=False -> ignore http_proxy/https_proxy/ALL_PROXY unless
        # explicitly opted-in via NOORLIB_MCP_USE_PROXY (fixes the local
        # MITM proxy breaking TLS while still allowing opt-in).
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=headers,
            timeout=TIMEOUT,
            trust_env=use_proxy,
            verify=True,
            follow_redirects=True,
        )
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------- plumbing
    async def _throttle(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = THROTTLE - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _request(self, method: str, path: str, **kw: Any) -> dict:
        payload = kw.pop("payload", None)
        params = kw.pop("params", None)
        last_exc: Exception | None = None
        last_body: str = ""

        for attempt in range(1, RETRIES + 1):
            await self._throttle()
            try:
                if method == "POST":
                    resp = await self._client.post(path, json=payload)
                else:
                    resp = await self._client.get(path, params=params)
            except httpx.HTTPError as exc:
                # include the real cause (SSL/EOF/connect) — the previous
                # build dropped this text and printed an empty detail.
                raise NoorlibError(
                    f"network error calling {method} {path} "
                    f"(attempt {attempt}/{RETRIES}): {type(exc).__name__}: {exc} "
                    f"— hint: noorlib.ir is reachable directly; if a local proxy "
                    f"(http_proxy) breaks TLS, this client already ignores it "
                    f"unless NOORLIB_MCP_USE_PROXY=1 is set"
                ) from exc

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_body = resp.text[:300]
                last_exc = NoorlibError(
                    f"server busy (HTTP {resp.status_code}) on attempt "
                    f"{attempt}/{RETRIES}"
                )
                await asyncio.sleep(min(2.0 * attempt, 6.0))
                continue
            if resp.status_code != 200:
                raise NoorlibError(
                    f"HTTP {resp.status_code} from {path}: {resp.text[:300]}"
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise NoorlibError(
                    f"non-JSON response from {path}: {resp.text[:300]}"
                ) from exc
            if data.get("isSuccess") is False and data.get("statusCode") not in (200, None):
                raise NoorlibError(
                    f"API error from {path}: {data.get('message') or data}"
                )
            return data

        raise NoorlibError(
            f"request failed after {RETRIES} attempts: {last_exc} "
            f"last body: {last_body}"
        )

    @staticmethod
    def _svc() -> dict:
        return {"origin": "noorlib.web.app", "language": "fa"}

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------- endpoints
    async def book_info(self, book_id: int) -> dict:
        """Book metadata: title, creators, free-study flags, volume count."""
        data = await self._request(
            "POST",
            "/api/book/getGeneralBookInfo",
            payload={**self._svc(), "bookId": book_id, "type": "metadata"},
        )
        return data.get("data") or {}

    async def book_toc(
        self,
        book_id: int,
        parent_node_id: int | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> dict:
        """Table of contents (GET). Returns nodes + totalCount."""
        params: dict[str, Any] = {
            **self._svc(),
            "bookId": book_id,
            "offset": offset,
            "limit": limit,
        }
        if parent_node_id is not None:
            params["parentNodeId"] = parent_node_id
        data = await self._request(
            "GET", "/api/book/getBookTOC", params=params
        )
        return {
            "nodes": data.get("data") or [],
            "totalCount": data.get("totalCount", 0),
        }

    async def book_page(
        self,
        book_id: int,
        page_number: int,
        volume_number: int = 1,
        section_number: int = 1,
        view_type: str = "html",
    ) -> dict:
        """One page of a book (encrypted html + validation block)."""
        data = await self._request(
            "POST",
            "/api/book/getBookPageContent",
            payload={
                **self._svc(),
                "bookId": book_id,
                "volumeNumber": volume_number,
                "sectionNumber": section_number,
                "viewType": view_type,
                "pageNumber": page_number,
            },
        )
        pages = data.get("data") or []
        return pages[0] if pages else {}

    async def search(
        self,
        query: str,
        page_number: int = 1,
        page_size: int = 10,
        book_id: int | None = None,
        creator_id: int | None = None,
        subject_id: int | None = None,
        sort: str = "rank-desc",
    ) -> dict:
        """Global search. Optional sp.* filters narrow it to a book/author/subject."""
        payload: dict[str, Any] = {
            **self._svc(),
            "query": query,
            "sp.display_type": "details",
            "sp.grouping": "book",
            "page_size": page_size,
            "page_number": page_number,
            "sort": sort,
        }
        if book_id is not None:
            payload["sp.book_id"] = book_id
        if creator_id is not None:
            payload["sp.creator_id"] = creator_id
        if subject_id is not None:
            payload["sp.subject_ids"] = subject_id
        data = await self._request(
            "POST", "/api/search/generalSearchPhrase", payload=payload
        )
        return data.get("data") or {}

    async def search_in_book(
        self,
        book_id: int,
        query: str,
        page_number: int = 1,
        page_size: int = 10,
        volume_number: int | None = None,
        sort: str = "rank-desc",
    ) -> dict:
        """Search inside one book: pages + highlighted snippets + TOC path."""
        payload: dict[str, Any] = {
            **self._svc(),
            "query": query,
            "sp.book_id": book_id,
            "sp.display_type": "details",
            "page_size": page_size,
            "page_number": page_number,
            "sort": sort,
        }
        if volume_number is not None:
            payload["sp.volume_number"] = volume_number
        data = await self._request(
            "POST", "/api/search/bookSearchPhrasePageList", payload=payload
        )
        return data.get("data") or {}

    async def find_pages(
        self, book_id: int, query: str, volume_number: int = 1
    ) -> list[dict]:
        """Cheap word-index lookup: pages containing the query words."""
        payload = {
            **self._svc(),
            "query": query,
            "sp.book_id": book_id,
            "sp.volume": volume_number,
            "page_size": 25,
            "page_number": 1,
        }
        data = await self._request(
            "POST", "/api/search/pageSearchPhrase", payload=payload
        )
        return (data.get("data") or {}).get("resultList") or []
