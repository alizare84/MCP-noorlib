"""Client for the wikinoor.ir MediaWiki API — دانشنامه ویکی‌نور.

wikinoor is a plain MediaWiki 1.39 install (~33k articles on Persian
bibliography/biography of Islamic texts). We speak the standard
action API at https://fa.wikinoor.ir/w/api.php:

    action=query&list=search   — full-text search
    action=parse&prop=wikitext — article source (redirects followed)
    action=query&meta=siteinfo — statistics
"""

from __future__ import annotations

import os
from typing import Any

from .siteclient import SiteClient, SiteError

BASE_URL = os.environ.get("WIKINOOR_MCP_BASE_URL", "https://fa.wikinoor.ir")


class WikinoorClient(SiteClient):
    name = "wikinoor"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("WIKINOOR_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("WIKINOOR_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("WIKINOOR_MCP_RETRIES", "3")),
            headers={"Referer": BASE_URL + "/"},
        )
        self._api = "/w/api.php"

    def _after_json(self, data: Any, path: str) -> Any:
        # MediaWiki answers HTTP 200 with an "error" body for failures
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            raise SiteError(f"[wikinoor] MediaWiki error {err.get('code')}: {err.get('info')}")
        return data

    async def _api_get(self, **params) -> dict:
        params["format"] = "json"
        data = await self.get(self._api, params=params)
        return data if isinstance(data, dict) else {}

    # -------------------------------------------------------------- search
    async def search(self, query: str, limit: int = 10, offset: int = 0) -> dict:
        return await self._api_get(
            action="query",
            list="search",
            srsearch=query,
            srlimit=limit,
            sroffset=offset,
        )

    # ---------------------------------------------------------------- page
    async def page(self, title: str) -> dict:
        """Article wikitext with redirects followed."""
        return await self._api_get(
            action="parse",
            page=title,
            prop="wikitext",
            redirects=1,
        )

    # --------------------------------------------------------------- stats
    async def statistics(self) -> dict:
        data = await self._api_get(action="query", meta="siteinfo", siprop="statistics")
        return (data.get("query") or {}).get("statistics") or {}


__all__ = ["WikinoorClient", "SiteError"]
