"""The tool catalog an LLM client actually sees."""

import json

import pytest

from noorlib_mcp.server import (
    _budget,
    _cap,
    hadith_sources,
    mcp,
    noorlib_search,
    quran_surah_text,
)


def test_list_sizes_stay_inside_a_context_window():
    assert _cap(500, 10, 20) == 20
    assert _cap(0, 10, 20) == 10
    assert _budget(0, 12000) == 0
    assert _budget(999_999, 12000) == 30_000


def _hint(annotations: dict, snake: str, camel: str):
    """mcp 1.x model_dump() emits camelCase, mcp 2.x emits snake_case."""
    return annotations.get(snake, annotations.get(camel))


@pytest.mark.asyncio
async def test_catalog_is_ready_for_an_llm():
    tools = await mcp.list_tools()
    names = [tool.name for tool in tools]
    assert len(names) == 29
    assert len(names) == len(set(names))
    for tool in tools:
        data = tool.model_dump()
        annotations = data["annotations"]
        assert _hint(annotations, "read_only_hint", "readOnlyHint") is True
        assert _hint(annotations, "idempotent_hint", "idempotentHint") is True
        assert _hint(annotations, "open_world_hint", "openWorldHint") is True
        assert _hint(annotations, "destructive_hint", "destructiveHint") is False
        assert not data.get("output_schema")
        description = data["description"]
        assert description
        assert not description.startswith((" ", "\n"))
        assert "\n    Args:" not in description
    # mcp 1.x stores it as _mcp_server, mcp 2.x as _lowlevel_server
    lowlevel = getattr(mcp, "_lowlevel_server", None) or mcp._mcp_server
    instructions = lowlevel.instructions
    assert "noorlib_search" in instructions
    assert "hadith_by_id" in instructions
    assert "quran_surah_text" in instructions


@pytest.mark.asyncio
async def test_empty_query_does_not_hit_the_network():
    data = json.loads(await noorlib_search("  "))
    assert "خالی" in data["error"]


@pytest.mark.asyncio
async def test_protocol_call_returns_the_json_text():
    result = await mcp.call_tool("noorlib_search", {"query": ""})
    if isinstance(result, list):  # mcp 1.x: bare list of content blocks
        text = result[0].text
    else:  # mcp 2.x: CallToolResult wrapper
        assert result.is_error is False
        text = result.content[0].text
    assert "خالی" in text


@pytest.mark.asyncio
async def test_noorlib_search_accepts_nested_and_flat_books(monkeypatch):
    from noorlib_mcp import server as srv

    shapes = [
        {
            "resultList": [
                {
                    "type": "book",
                    "itemList": [
                        {
                            "bookId": 11,
                            "title": "کتاب تو در تو",
                            "snippetList": [{"pageNumber": 1, "sectionNumber": 2, "text": "نمونه"}],
                        }
                    ],
                },
                {"type": "author", "title": "پدیدآور"},
            ]
        },
        {
            "resultList": [
                {
                    "bookId": 22,
                    "title": "کتاب تخت",
                    "snippetList": [{"pageNumber": 4, "sectionNumber": 1, "text": "متن"}],
                }
            ]
        },
    ]

    class FakeNoorlib:
        def __init__(self, payload):
            self.payload = payload

        async def search(self, *args, **kwargs):
            return self.payload

    seen = []
    for payload in shapes:
        monkeypatch.setattr(srv, "_cl", lambda payload=payload: FakeNoorlib(payload))
        data = json.loads(await noorlib_search("فصوص"))
        seen.append(data["books"])

    assert [b["bookId"] for b in seen[0]] == [11]
    assert seen[0][0]["title"] == "کتاب تو در تو"
    assert [b["bookId"] for b in seen[1]] == [22]
    assert seen[1][0]["title"] == "کتاب تخت"


@pytest.mark.asyncio
async def test_search_sample_skips_an_image_only_snippet(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeNoorlib:
        async def search(self, *args, **kwargs):
            return {
                "resultList": [
                    {
                        "type": "book",
                        "bookId": 7,
                        "title": "کتاب",
                        "snippetList": [
                            {
                                "pageNumber": 1,
                                "sectionNumber": 1,
                                "volumeNumber": 1,
                                "imageUrl": "scan.jpg",
                            },
                            {
                                "pageNumber": 2,
                                "sectionNumber": 1,
                                "volumeNumber": 1,
                                "text": "متن واقعی",
                            },
                        ],
                    }
                ]
            }

    monkeypatch.setattr(srv, "_cl", lambda: FakeNoorlib())
    data = json.loads(await noorlib_search("نور"))
    assert "متن واقعی" in data["books"][0]["sample"]
    assert "scan.jpg" not in data["books"][0]["sample"]


@pytest.mark.asyncio
async def test_surah_juz_is_not_the_revelation_order(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeQuran:
        async def surahs(self):
            return [{"Id": 1, "Title": "حمد", "AyahCount": 7, "JuzNumber": 1, "FallPriority": 5}]

    monkeypatch.setattr(srv, "_qcl", lambda: FakeQuran())
    data = json.loads(await srv.quran_surahs())
    assert data["surahs"][0]["juz"] == 1


@pytest.mark.asyncio
async def test_qamus_dictionaries_keep_the_title(monkeypatch):
    from noorlib_mcp import server as srv

    class FakeQamus:
        async def dictionaries(self, **kwargs):
            return {
                "resultListTotalCount": 1,
                "resultList": [
                    {
                        "bookId": 2086,
                        "title": "قاموس قرآن",
                        "link": "http://noorlib.ir/book/info/2086",
                        "creatorList": [{"name": "قرشی"}],
                        "languageList": [{"name": "فارسی"}],
                        "hasTextContent": True,
                    }
                ],
            }

    monkeypatch.setattr(srv, "_mcl", lambda: FakeQamus())
    data = json.loads(await srv.qamus_dictionaries(query="قرشی"))
    assert data["dictionaries"][0]["title"] == "قاموس قرآن"


@pytest.mark.asyncio
async def test_invalid_surah_is_rejected_before_the_network():
    data = json.loads(await quran_surah_text(0))
    assert "surah_id" in data["error"]
    data = json.loads(await quran_surah_text(2, ayah_from=10, ayah_to=3))
    assert "ayah_to" in data["error"]


@pytest.mark.asyncio
async def test_hadith_sources_page_zero_is_the_first_page(monkeypatch):
    from noorlib_mcp import server as srv

    rows = [{"id": i, "title": f"کتاب{i}"} for i in range(10)]

    class FakeHadith:
        async def sources(self, page_size=900):
            return rows

    monkeypatch.setattr(srv, "_hcl", lambda: FakeHadith())
    data = json.loads(await hadith_sources(page_size=3, page_number=0))
    assert data["returned"] == 3
    assert data["sources"][0]["title"] == "کتاب0"


@pytest.mark.asyncio
async def test_unexpected_failure_reaches_the_model(monkeypatch):
    from noorlib_mcp import server as srv

    def boom():
        raise RuntimeError("boom-marker")

    monkeypatch.setattr(srv, "_cl", boom)
    data = json.loads(await noorlib_search("نور"))
    assert "boom-marker" in data["error"]
