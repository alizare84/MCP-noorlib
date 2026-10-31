"""Client for the (unofficial) qamus-api.inoor.ir API — لغت‌نامه قاموس نور.

Reverse-engineered from https://qamus.inoor.ir/_nuxt/*.js
(apiEndpointHost = https://qamus-api.inoor.ir):

    POST /vocabulary | /term | /name   — search (body: text, language{...},
                                          facets, pageIndex, pageLimit, isNew)
    GET  /headWord?headWordId=         — word detail (X-Api-Version: 2)
    GET  /AutoComplete?lang=&word=     — search suggestions
    GET  /GetBookList?...              — the dictionaries (X-Api-Version: 2)
    GET  /Statistics?lang=             — statistics

Live-tested: ~369k Persian words, 163 dictionaries.
"""

from __future__ import annotations

import os

from .httpcore import SiteClient, SiteError

BASE_URL = os.environ.get("QAMUS_MCP_BASE_URL", "https://qamus-api.inoor.ir")

_CATEGORIES = ("vocabulary", "term", "name")


class QamusClient(SiteClient):
    name = "qamus"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("QAMUS_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("QAMUS_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("QAMUS_MCP_RETRIES", "3")),
            headers={
                "Origin": "https://qamus.inoor.ir",
                "Referer": "https://qamus.inoor.ir/",
            },
        )
        self._v2 = {"X-Api-Version": "2"}

    # -------------------------------------------------------------- search
    async def search(
        self,
        text: str,
        *,
        category: str = "vocabulary",
        page_index: int = 1,
        page_limit: int = 10,
        search_in: str = "fa",
        target: str = "both",
        conformity: int = 1,
    ) -> dict:
        if category not in _CATEGORIES:
            category = "vocabulary"
        data = await self.post(
            f"/{category}",
            payload={
                "text": text,
                "language": {
                    "searchIn": search_in,
                    "target": target,
                    "conformity": conformity,
                },
                "facets": [],
                "pageIndex": page_index,
                "pageLimit": page_limit,
                "isNew": True,
            },
        )
        d = data.get("data")
        return d if isinstance(d, dict) else {}

    # ---------------------------------------------------------------- word
    async def word(self, head_word_id: str) -> dict:
        data = await self.get(
            "/headWord",
            params={"headWordId": head_word_id},
            headers=self._v2,
        )
        d = data.get("data")
        return d if isinstance(d, dict) else {}

    # ------------------------------------------------------------- suggest
    async def autocomplete(self, word: str, lang: str = "fa") -> list[dict]:
        data = await self.get(
            "/AutoComplete", params={"lang": lang, "word": word}
        )
        rows = data.get("data") or []
        return rows if isinstance(rows, list) else []

    # ------------------------------------------------------------- books
    async def dictionaries(
        self, page_number: int = 1, page_size: int = 20, query: str = ""
    ) -> dict:
        data = await self.get(
            "/GetBookList",
            params={
                "pageSize": page_size,
                "pageNumber": page_number,
                "language": "fa",
                "query": query,
                "sortKey": "title",
                "sortOrder": "asc",
            },
            headers=self._v2,
        )
        d = (data.get("data") or {}).get("data")
        return d if isinstance(d, dict) else {}

    # -------------------------------------------------------------- stats
    async def statistics(self) -> dict:
        data = await self.get("/Statistics", params={"lang": "fa"})
        d = data.get("data")
        return d if isinstance(d, dict) else {}


__all__ = ["QamusClient", "SiteError"]
