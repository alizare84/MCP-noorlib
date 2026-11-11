"""Client for the public Ganjoor API — گنجور (ganjoor.net).

The site itself calls https://api.ganjoor.net. Read routes used here are
anonymous. Ganjoor says the shape can change without notice; only the
stable reading calls are wrapped:

    GET /api/ganjoor/poets
    GET /api/ganjoor/poet/{id}
    GET /api/ganjoor/cat/{id}
    GET /api/ganjoor/poems/search
    GET /api/ganjoor/poem/{id}
    GET /api/ganjoor/hafez/faal
    GET /api/ganjoor/poem/random
"""

from __future__ import annotations

import os
from typing import Any

from .siteclient import SiteClient, SiteError

BASE_URL = os.environ.get("GANJOOR_MCP_BASE_URL", "https://api.ganjoor.net")

# Skip recitations, images, songs and comments. The poem text is in verses.
_POEM_PARAMS = {
    "catInfo": True,
    "catPoems": False,
    "rhymes": False,
    "recitations": False,
    "images": False,
    "songs": False,
    "comments": False,
    "verseDetails": False,
    "navigation": True,
}


class GanjoorClient(SiteClient):
    name = "ganjoor"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("GANJOOR_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("GANJOOR_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("GANJOOR_MCP_RETRIES", "3")),
        )

    def _body(self, data: Any, path: str) -> Any:
        if isinstance(data, str) and data.strip():
            raise SiteError(f"[ganjoor] {data.strip()}")
        return data

    async def poets(self) -> list[dict]:
        data = self._body(await self.get("/api/ganjoor/poets"), "/api/ganjoor/poets")
        return data if isinstance(data, list) else []

    async def poet(self, poet_id: int) -> dict:
        path = f"/api/ganjoor/poet/{poet_id}"
        data = self._body(await self.get(path, params={"catPoems": False}), path)
        return data if isinstance(data, dict) else {}

    async def category(self, cat_id: int, *, poems: bool = True) -> dict:
        path = f"/api/ganjoor/cat/{cat_id}"
        data = self._body(await self.get(path, params={"poems": poems, "mainSections": False}), path)
        return data if isinstance(data, dict) else {}

    async def search(
        self,
        term: str,
        *,
        page_number: int = 1,
        page_size: int = 5,
        poet_id: int = 0,
        cat_id: int = 0,
    ) -> list[dict]:
        data = self._body(
            await self.get(
                "/api/ganjoor/poems/search",
                params={
                    "term": term,
                    "PageNumber": page_number,
                    "PageSize": page_size,
                    "poetId": poet_id,
                    "catId": cat_id,
                },
            ),
            "/api/ganjoor/poems/search",
        )
        return data if isinstance(data, list) else []

    async def poem(self, poem_id: int) -> dict:
        path = f"/api/ganjoor/poem/{poem_id}"
        data = self._body(await self.get(path, params=_POEM_PARAMS), path)
        return data if isinstance(data, dict) else {}

    async def hafez_faal(self) -> dict:
        data = self._body(await self.get("/api/ganjoor/hafez/faal"), "/api/ganjoor/hafez/faal")
        return data if isinstance(data, dict) else {}

    async def random_poem(self, poet_id: int = 0) -> dict:
        data = self._body(
            await self.get("/api/ganjoor/poem/random", params={"poetId": poet_id}),
            "/api/ganjoor/poem/random",
        )
        return data if isinstance(data, dict) else {}


__all__ = ["GanjoorClient", "SiteError"]
