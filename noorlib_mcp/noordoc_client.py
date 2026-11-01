"""Client for the (unofficial) noordoc.ir API — پایگاه پایان‌نامه‌ها.

Reverse-engineered from https://noordoc.ir/_nuxt/*.js (Nuxt 2 app,
~149k theses, 249k persons):

    POST /_search/api/v1.0/SearchThesis  — thesis search (title/text)
    GET  /_search/api/v1.0/AutoCompelte  — suggestions (typo is theirs)
    GET  /_content/api/v1/thesis/{id}    — thesis detail (abstract, people)
    GET  /_content/api/v1/page?ThesisId= — page inventory of a thesis
    GET  /_content/api/v1/analyze/statistic — statistics

Page *content* (images/PDF) goes through _aggregator and needs a paid
account, so it is intentionally not exposed.
"""

from __future__ import annotations

import os

from .siteclient import SiteClient, SiteError

BASE_URL = os.environ.get("NOORDOC_MCP_BASE_URL", "https://noordoc.ir")


class NoordocClient(SiteClient):
    name = "noordoc"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("NOORDOC_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("NOORDOC_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("NOORDOC_MCP_RETRIES", "3")),
            headers={
                "Origin": "https://noordoc.ir",
                "Referer": "https://noordoc.ir/fa/search",
            },
        )

    # -------------------------------------------------------------- search
    async def search(
        self,
        text: str,
        *,
        page_number: int = 1,
        page_size: int = 10,
        from_title: bool = True,
        organization: str | None = None,
        education_level: str | None = None,
        has_pdf: int = 0,
        has_word: int = 0,
    ) -> dict:
        payload: dict = {
            "pageNumber": page_number,
            "pageSize": page_size,
            "searchType": "exact",
            "text": text,
            "fromTitle": from_title,
            "hasPdf": has_pdf,
            "hasWord": has_word,
        }
        if organization:
            payload["organization"] = organization
        if education_level:
            payload["educationLevel"] = education_level
        data = await self.post("/_search/api/v1.0/SearchThesis", payload=payload)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------- thesis
    async def thesis(self, thesis_id: int) -> dict:
        data = await self.get(f"/_content/api/v1/thesis/{thesis_id}")
        d = data.get("data")
        return d if isinstance(d, dict) else {}

    async def thesis_pages(self, thesis_id: int, limit: int = 20) -> list[dict]:
        data = await self.get("/_content/api/v1/page", params={"ThesisId": thesis_id})
        items = (data.get("data") or {}).get("items") or []
        return items[:limit] if isinstance(items, list) else []

    # ---------------------------------------------------------- statistics
    async def statistics(self) -> dict:
        data = await self.get("/_content/api/v1/analyze/statistic")
        d = data.get("data")
        return d if isinstance(d, dict) else {}


__all__ = ["NoordocClient", "SiteError"]
