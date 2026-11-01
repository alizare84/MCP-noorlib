"""Async HTTP client for the (unofficial) hadith.inoor.ir JSON API.

Reverse-engineered from https://hadith.inoor.ir/main.*.js and live traffic
(xr_settings.serviceUrl = https://hadith.inoor.ir/service):

    POST /service/api/elastic/v2/ElasticHadithList  — main search (text + filters)
    POST /service/api/elastic/ElasticHadithById     — full hadith text by id list
    POST /service/api/elastic/SourceList            — all hadith sources (350+)
    GET  /service/api/hadith/TocListBySource        — TOC of one source
    POST /service/api/elastic/RelatedHadith         — similar hadiths

Proxy policy mirrors noorlib_mcp.client: ambient http_proxy is IGNORED by
default (NOORLIB_MCP_USE_PROXY=1 or NOOR_MCP_USE_PROXY=1 opts in).
"""

from __future__ import annotations

import os
from typing import Any

from .siteclient import SiteClient, SiteError

BASE_URL = os.environ.get("HADITH_MCP_BASE_URL", "https://hadith.inoor.ir")
TIMEOUT = float(os.environ.get("HADITH_MCP_TIMEOUT", "30"))
THROTTLE = float(os.environ.get("HADITH_MCP_THROTTLE", "1.2"))
RETRIES = int(os.environ.get("HADITH_MCP_RETRIES", "3"))


class HadithError(SiteError):
    """Any failure while talking to hadith.inoor.ir."""


class HadithClient(SiteClient):
    name = "hadith"
    error = HadithError

    def __init__(self, auth_token: str | None = None) -> None:
        self._auth = auth_token or os.environ.get("HADITH_MCP_AUTH", "")
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

    def _after_json(self, data: Any, path: str) -> Any:
        if isinstance(data, dict):
            status = data.get("status")
            if isinstance(status, (int, float)) and status < 0:
                raise self.error(
                    f"API error from {path}: {data.get('message') or data.get('exception') or data}"
                )
            if data.get("isSuccess") is False:
                raise self.error(f"API error from {path}: {data.get('message') or data}")
        return data

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
        if not isinstance(data, dict):
            return []
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
        if not isinstance(data, dict):
            return {}
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
        if not isinstance(data, list):
            return []
        return data

    async def toc(self, source_id: int) -> list[dict]:
        """TOC nodes of a source (GET). Empty list when the source has no TOC."""
        data = await self._request(
            "GET",
            "/service/api/hadith/TocListBySource",
            params={"language": "fa", "sourceId": source_id},
        )
        if not isinstance(data, dict):
            return []
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
        d = data.get("data") if isinstance(data, dict) else None
        if isinstance(d, dict):
            return d.get("resultList") or d.get("results") or []
        if isinstance(d, list):
            return d
        return []


__all__ = ["HadithClient", "HadithError"]
