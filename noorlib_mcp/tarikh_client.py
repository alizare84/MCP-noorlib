"""Client for the (unofficial) tarikh.inoor.ir API — پایگاه جامع تاریخ.

Reverse-engineered from https://cdntarikh.inoor.ir/js/**.js (AngularJS
app; the event.service.js lists every endpoint):

    GET /api/event/List    — search historical events (SearchPhrase)
    GET /api/event/Page    — full event detail by id
    GET /api/event/Today   — today's events (hejri-qamari)

Live-tested: 65k+ political events, 58k military, 37k وفات ...
StartDate is YYMMDD (6 digits, hejri-qamari) — 360520 = 36/05/20 ق.
"""

from __future__ import annotations

import os

from .httpcore import SiteClient, SiteError

BASE_URL = os.environ.get("TARIKH_MCP_BASE_URL", "https://tarikh.inoor.ir")


def decode_tarikh_date(code) -> str:
    """360520 -> '36/05/20 قمری' ; 8570520 -> '857/05/20 قمری'.

    Format is YY..YYMMDD (year of varying length, then month, then day).
    """
    try:
        code = int(code or 0)
    except (TypeError, ValueError):
        return ""
    if code <= 0:
        return ""
    s = str(code)
    if len(s) >= 5:
        day, month, year = s[-2:], s[-4:-2], s[:-4]
        return f"{year}/{month}/{day} قمری"
    return s


class TarikhClient(SiteClient):
    name = "tarikh"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("TARIKH_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("TARIKH_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("TARIKH_MCP_RETRIES", "3")),
        )

    # -------------------------------------------------------------- search
    async def search(
        self,
        text: str,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        data = await self.get(
            "/api/event/List",
            params={
                "SearchPhrase": text,
                "PageNumber": page_number,
                "PageSize": page_size,
                "DateType": "all",
                "SortItem": "rank",
                "SortType": "desc",
                "StartDate": 0,
                "EndDate": 0,
                "StartDateMMDD": 0,
                "EndDateMMDD": 0,
                "Priority": 0,
                "HasPicture": "false",
                "SearchIn": "title,comment,text",
                "EventTypeId": 0,
                "SourceId": 0,
                "UserLanguage": "fa",
                "IsAdvance": "false",
            },
        )
        return data if isinstance(data, dict) else {}

    # --------------------------------------------------------------- event
    async def event(self, event_id: str) -> dict:
        data = await self.get(
            "/api/event/Page",
            params={"id": event_id, "rowNumber": 1},
        )
        return data if isinstance(data, dict) else {}

    async def today(self) -> list[dict]:
        data = await self.get("/api/event/Today")
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------- facets
    async def main_page(self) -> dict:
        """EventTypes + sources overview."""
        data = await self.get("/api/home/MainPage")
        return data if isinstance(data, dict) else {}


__all__ = ["TarikhClient", "SiteError", "decode_tarikh_date"]
