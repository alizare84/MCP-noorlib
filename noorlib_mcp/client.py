"""Async HTTP client for the (unofficial) noorlib.ir JSON API.

Endpoints (reverse-engineered from https://noorlib.ir/_nuxt/*.js):

    POST /api/book/getGeneralBookInfo        {origin, language, bookId, type}
    GET  /api/book/getBookTOC                ?origin&language&bookId&offset&limit&parentNodeId
    POST /api/book/getBookPageContent        {origin, language, bookId, volumeNumber,
                                              sectionNumber, viewType, pageNumber}
    POST /api/search/generalSearchPhrase     {origin, language, query, sp.*, page_*}
    POST /api/search/bookSearchPhrasePageList {origin, language, query, sp.book_id, ...}
    POST /api/search/pageSearchPhrase        {origin, language, query, sp.book_id, sp.page, ...}

Design notes:

* Proxy — many Iranian networks run a local proxy (http_proxy=127.0.0.1:10808)
  that MITMs and breaks TLS to noorlib.ir.  By default the client IGNORES the
  ambient proxy environment (trust_env=False) and connects directly.  Set
  ``NOORLIB_MCP_USE_PROXY=1`` (or ``NOOR_MCP_USE_PROXY=1``) to honour
  http_proxy/https_proxy/no_proxy again.
* Auth — an optional bearer token (``NOORLIB_MCP_AUTH``) is sent on every
  call so authenticated users with reading credit can fetch full pages.
* Errors — every failure raises NoorlibError with the real cause
  (type + message); site response bodies are labeled untrusted.
"""

from __future__ import annotations

import os
from typing import Any

from .siteclient import SiteClient, SiteError

BASE_URL = os.environ.get("NOORLIB_MCP_BASE_URL", "https://noorlib.ir")
TIMEOUT = float(os.environ.get("NOORLIB_MCP_TIMEOUT", "30"))
THROTTLE = float(os.environ.get("NOORLIB_MCP_THROTTLE", "1.2"))
RETRIES = int(os.environ.get("NOORLIB_MCP_RETRIES", "3"))


class NoorlibError(SiteError):
    """Any failure while talking to noorlib.ir."""


class NoorlibClient(SiteClient):
    name = "noorlib"
    error = NoorlibError

    def __init__(self, auth_token: str | None = None) -> None:
        self._auth = auth_token or os.environ.get("NOORLIB_MCP_AUTH", "")
        headers: dict[str, str] = {
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/",
        }
        if self._auth:
            token = self._auth.strip()
            if not token.lower().startswith("bearer"):
                token = "Bearer " + token
            headers["Authorization"] = token
        super().__init__(
            BASE_URL,
            timeout=TIMEOUT,
            throttle=THROTTLE,
            retries=RETRIES,
            headers=headers,
        )

    def _transient_payload(self, data: Any) -> str | None:
        if not isinstance(data, dict) or data.get("isSuccess") is not False:
            return None
        code = data.get("statusCode")
        try:
            code_i = int(code)
        except (TypeError, ValueError):
            code_i = 0
        if 500 <= code_i < 600:
            return str(data.get("message") or data)
        return None

    def _after_json(self, data: Any, path: str) -> Any:
        if isinstance(data, dict):
            if data.get("isSuccess") is False and data.get("statusCode") not in (200, None):
                raise self.error(f"API error from {path}: {data.get('message') or data}")
        return data

    # ------------------------------------------------------------- plumbing
    @staticmethod
    def _svc() -> dict:
        return {"origin": "noorlib.web.app", "language": "fa"}

    # ------------------------------------------------------------- endpoints
    async def book_info(self, book_id: int) -> dict:
        """Book metadata: title, creators, free-study flags, volume count."""
        data = await self._request(
            "POST",
            "/api/book/getGeneralBookInfo",
            payload={**self._svc(), "bookId": book_id, "type": "metadata"},
        )
        if not isinstance(data, dict):
            return {}
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
        data = await self._request("GET", "/api/book/getBookTOC", params=params)
        if not isinstance(data, dict):
            return {"nodes": [], "totalCount": 0}
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
        pages = data.get("data") if isinstance(data, dict) else None
        if isinstance(pages, dict):
            return pages
        if isinstance(pages, list) and pages:
            return pages[0]
        return {}

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
        data = await self._request("POST", "/api/search/generalSearchPhrase", payload=payload)
        if not isinstance(data, dict):
            return {}
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
        data = await self._request("POST", "/api/search/bookSearchPhrasePageList", payload=payload)
        if not isinstance(data, dict):
            return {}
        return data.get("data") or {}

    async def find_pages(
        self,
        book_id: int,
        query: str,
        volume_number: int = 1,
        page_size: int = 25,
        page_number: int = 1,
    ) -> list[dict]:
        """Cheap word-index lookup: pages containing the query words."""
        payload = {
            **self._svc(),
            "query": query,
            "sp.book_id": book_id,
            "sp.volume": volume_number,
            "page_size": page_size,
            "page_number": page_number,
        }
        data = await self._request("POST", "/api/search/pageSearchPhrase", payload=payload)
        if not isinstance(data, dict):
            return []
        return (data.get("data") or {}).get("resultList") or []


__all__ = ["NoorlibClient", "NoorlibError"]
