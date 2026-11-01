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


@pytest.mark.asyncio
async def test_catalog_is_ready_for_an_llm():
    tools = await mcp.list_tools()
    names = [tool.name for tool in tools]
    assert len(names) == 29
    assert len(names) == len(set(names))
    for tool in tools:
        data = tool.model_dump()
        annotations = data["annotations"]
        assert annotations["read_only_hint"] is True
        assert annotations["idempotent_hint"] is True
        assert annotations["open_world_hint"] is True
        assert annotations["destructive_hint"] is False
        assert not data.get("output_schema")
        description = data["description"]
        assert description
        assert not description.startswith((" ", "\n"))
        assert "\n    Args:" not in description
    instructions = mcp._lowlevel_server.instructions
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
    assert result.is_error is False
    assert "خالی" in result.content[0].text


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
