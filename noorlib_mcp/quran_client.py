"""Client for the (unofficial) apiquran.inoor.ir JSON API — پایگاه جامع قرآنی.

Reverse-engineered from https://quran.inoor.ir/_nuxt/*.js
(API_BASE_URL = https://apiquran.inoor.ir):

    GET /api/Search/AutoComplete            — search quran text / translations
    GET /api/Surah/ListSurahLight           — the 114 surahs
    GET /api/Surah/GetSurah/{id}            — surah info
    GET /api/Ayah/AyahListBySurah           — full verse text of a surah
    GET /api/Ayah/ListTranslate             — translations of one ayah
    GET /api/Ayah/ListCommentary            — tafsir texts for one ayah
    GET /api/Ayah/ListHadithWithGrouping    — hadiths narrated about one ayah
    GET /api/Home/GetDataStatistics/        — database statistics

Notes discovered by live testing:
* /api/Search responses are DOUBLE JSON-encoded (a JSON string holding
  JSON) — unwrapped here.
* /api/Ayah/ListCommentary and ListHadithWithGrouping require the FULL
  parameter set (even empty strings) or the route 404s (ASP.NET model
  binding).
* ResultSet1 holds the items; ResultSet2 holds facets.
"""

from __future__ import annotations

import os

from .httpcore import SiteClient, SiteError

BASE_URL = os.environ.get("QURAN_MCP_BASE_URL", "https://apiquran.inoor.ir")


class QuranClient(SiteClient):
    name = "quran"

    def __init__(self) -> None:
        super().__init__(
            BASE_URL,
            timeout=float(os.environ.get("QURAN_MCP_TIMEOUT", "30")),
            throttle=float(os.environ.get("QURAN_MCP_THROTTLE", "1.2")),
            retries=int(os.environ.get("QURAN_MCP_RETRIES", "3")),
            headers={"Origin": "https://quran.inoor.ir",
                     "Referer": "https://quran.inoor.ir/"},
        )

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _unwrap(data) -> dict:
        """apiquran sometimes returns a JSON string containing JSON."""
        if isinstance(data, str):
            import json

            try:
                data = json.loads(data)
            except ValueError:
                return {}
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------- search
    async def search(
        self,
        text: str,
        *,
        source: str = "quran",
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        """Search. source: 'quran' (Arabic text) or 'translation'."""
        data = await self.get(
            "/api/Search/AutoComplete",
            params={
                "searchText": text,
                "pageNumber": page_number,
                "pageSize": page_size,
                "source": source,
                "root": "true",
                "stem": "true",
                "synonym": "true",
                "searchType": "all",
                "type": "search",
                "exec": "true",
                "sort": "rank_desc",
            },
        )
        d = self._unwrap(data).get("data") or {}
        return d if isinstance(d, dict) else {}

    # -------------------------------------------------------------- surah
    async def surahs(self) -> list[dict]:
        data = await self.get(
            "/api/Surah/ListSurahLight", params={"language": "fa"}
        )
        rows = data.get("Data") or []
        return rows if isinstance(rows, list) else []

    async def surah_text(self, surah_id: int, orthography_id: int = 4) -> list[dict]:
        """Full verse list of a surah. orthography 4=عثمان طه, 2=ساده..."""
        data = await self.get(
            "/api/Ayah/AyahListBySurah",
            params={"surahId": surah_id, "orthographyId": orthography_id},
        )
        rows = data.get("Data") or []
        return rows if isinstance(rows, list) else []

    # -------------------------------------------------------------- ayah
    async def ayah_translations(
        self,
        surah_id: int,
        ayah_number: int,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        data = await self.get(
            "/api/Ayah/ListTranslate",
            params={
                "surahId": surah_id,
                "ayahNumber": ayah_number,
                "language": "fa",
                "pageNumber": page_number,
                "pageSize": page_size,
                "order": 0,
                "bookIds": "",
                "languageIds": "",
                "religionIds": "",
            },
        )
        d = data.get("Data") or {}
        return d if isinstance(d, dict) else {}

    async def ayah_commentary(
        self,
        surah_id: int,
        ayah_number: int,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        data = await self.get(
            "/api/Ayah/ListCommentary",
            params=self._full_params(surah_id, ayah_number,
                                      page_number, page_size),
        )
        d = data.get("Data") or {}
        return d if isinstance(d, dict) else {}

    async def ayah_hadiths(
        self,
        surah_id: int,
        ayah_number: int,
        *,
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        data = await self.get(
            "/api/Ayah/ListHadithWithGrouping",
            params=self._full_params(surah_id, ayah_number,
                                      page_number, page_size),
        )
        d = data.get("Data") or {}
        return d if isinstance(d, dict) else {}

    @staticmethod
    def _full_params(surah_id, ayah_number, page_number, page_size) -> dict:
        # ASP.NET model binding: every route param must be present, even
        # when empty, otherwise the route does not match.
        return {
            "authorIds": "",
            "ayahNumber": ayah_number,
            "bookIds": "",
            "centuryIds": "",
            "commentaryTypeIds": "",
            "language": "fa",
            "languageIds": "",
            "order": 0,
            "pageNumber": page_number,
            "pageSize": page_size,
            "religionIds": "",
            "surahId": surah_id,
        }

    # -------------------------------------------------------------- stats
    async def statistics(self) -> dict:
        data = await self.get(
            "/api/Home/GetDataStatistics/", params={"language": "fa"}
        )
        return data.get("Data") or {}


__all__ = ["QuranClient", "SiteError"]
