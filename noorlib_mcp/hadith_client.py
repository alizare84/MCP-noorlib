"""Async HTTP client for the (unofficial) hadith.inoor.ir JSON API.

Reverse-engineered from https://hadith.inoor.ir/main.*.js and live traffic
(xr_settings.serviceUrl = https://hadith.inoor.ir/service):

    POST /api/elastic/v2/ElasticHadithList  — main search (text + filters)
    POST /api/elastic/ElasticHadithById     — full hadith text by id list
    POST /api/elastic/SourceList            — all hadith sources (350+)
    GET  /api/hadith/TocListBySource        — TOC of one source
    POST /api/elastic/RelatedHadith         — similar hadiths
    POST /api/hadith/HadithSimilarList      — similar list
    POST /api/elastic/SameTocHadith         — hadiths under same TOC node

Proxy policy mirrors noorlib_mcp.client: ambient http_proxy is IGNORED by
default (NOORLIB_MCP_USE_PROXY=1 opts in) and errors carry full detail.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("HADITH_MCP_BASE_URL", "https://hadith.inoor.ir")
SERVICE = BASE_URL + "/service"
TIMEOUT = float(os.environ.get("HADITH_MCP_TIMEOUT", "30"))
THROTTLE = float(os.environ.get("HADITH_MCP_THROTTLE", "1.2"))
RETRIES = int(os.environ.get("HADITH_MCP_RETRIES", "3"))

_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"


class HadithError(RuntimeError):
    pass


class HadithClient:
    def __init__(self, auth_token: str | None = None) -> None:
        self._auth = auth_token or os.environ.get("HADITH_MCP_AUTH", "")
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
        last_body = ""

        for attempt in range(1, RETRIES + 1):
            await self._throttle()
            try:
                if method == "POST":
                    resp = await self._client.post(path, json=payload)
                else:
                    resp = await self._client.get(path, params=params)
            except httpx.HTTPError as exc:
                raise HadithError(
                    f"network error calling {method} {path} "
                    f"(attempt {attempt}/{RETRIES}): {type(exc).__name__}: {exc} "
                    f"— hint: this client ignores http_proxy unless "
                    f"NOORLIB_MCP_USE_PROXY=1"
                ) from exc

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_body = resp.text[:300]
                last_exc = HadithError(
                    f"server busy (HTTP {resp.status_code}) attempt {attempt}/{RETRIES}"
                )
                await asyncio.sleep(min(2.0 * attempt, 6.0))
                continue
            if resp.status_code != 200:
                raise HadithError(
                    f"HTTP {resp.status_code} from {path}: {resp.text[:300]}"
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise HadithError(
                    f"non-JSON response from {path}: {resp.text[:300]}"
                ) from exc
            # API signals failures with status<0 and an exception message
            if data.get("status") is not None and data.get("status") < 0:
                raise HadithError(
                    f"API error from {path}: {data.get('message') or data.get('exception') or data}"
                )
            return data

        raise HadithError(
            f"request failed after {RETRIES} attempts: {last_exc} last body: {last_body}"
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------ endpoints
    async def sources(self, page_size: int = 900, page_number: int = 1) -> list[dict]:
        """All hadith sources (books): id, title, author, publisher..."""
        data = await self._request(
            "POST",
            "/service/api/elastic/SourceList",
            payload={
                "language": "fa",
                "pageNumber": page_number,
                "pageSize": page_size,
            },
        )
        return (data.get("data") or {}).get("resultList") or []

    async def search(
        self,
        text: str,
        page_number: int = 1,
        page_size: int = 10,
        source_ids: list[int] | None = None,
        search_in: str = "hadith",
        search_type: str = "and",
        is_erab: bool = True,
        translate: bool = False,
        explanation: bool = False,
    ) -> dict:
        """Search hadiths. search_in: hadith | translate | explanation | all."""
        payload: dict[str, Any] = {
            "searchInText": False,
            "pageNumber": page_number,
            "pageSize": page_size,
            "isErab": is_erab,
            "translate": translate,
            "explanation": explanation,
            "sortColumn": "default",
            "sortDirection": "asc",
            "text": text,
            "searchType": search_type,
            "inFeild": "all",
            "searchIn": search_in,
            # NOTE: the live site posts an empty bookListModel but the API
            # actually filters on the plain "bookList" array of source ids.
            "bookList": list(source_ids) if source_ids else None,
            "isGroup": False,
            "isFullText": False,
        }
        data = await self._request(
            "POST", "/service/api/elastic/v2/ElasticHadithList", payload=payload
        )
        return data.get("data") or {}

    async def hadith_by_id(
        self,
        hadith_ids: list[int],
        search_in: str = "arabic",
        search_phrase: str = "",
    ) -> list[dict]:
        """Full hadith records: complete text, sanad, tocInfo, translations."""
        data = await self._request(
            "POST",
            "/service/api/elastic/ElasticHadithById",
            payload={
                "hadithId": hadith_ids,
                "searchPhrase": search_phrase,
                "searchIn": search_in,
            },
        )
        return data.get("data") or []

    async def toc(self, source_id: int) -> list[dict]:
        """TOC nodes of a source (GET)."""
        data = await self._request(
            "GET",
            "/service/api/hadith/TocListBySource",
            params={"language": "fa", "sourceId": source_id},
        )
        return data.get("data") or []

    async def related(self, hadith_id: int, source_id: int) -> list[dict]:
        """Hadiths similar to one hadith (RelatedHadith)."""
        data = await self._request(
            "POST",
            "/service/api/elastic/RelatedHadith",
            payload={
                "language": "fa",
                "hadithId": hadith_id,
                "sourceId": source_id,
            },
        )
        d = data.get("data")
        if isinstance(d, dict):
            return d.get("resultList") or d.get("results") or []
        return d or []
