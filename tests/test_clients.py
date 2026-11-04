import json

import httpx
import pytest

from noorlib_mcp.client import NoorlibClient
from noorlib_mcp.hadith_client import HadithClient
from noorlib_mcp.noordoc_client import NoordocClient
from noorlib_mcp.qamus_client import QamusClient
from noorlib_mcp.quran_client import QuranClient
from noorlib_mcp.siteclient import SiteClient
from noorlib_mcp.tarikh_client import TarikhClient, decode_tarikh_date
from noorlib_mcp.wikinoor_client import WikinoorClient


def _mock_transport(monkeypatch, handler):
    real_async_client = httpx.AsyncClient
    requests = []

    def dispatch(request):
        requests.append(request)
        return handler(request)

    def make_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(dispatch)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make_client)
    return requests


@pytest.mark.asyncio
async def test_noorlib_page_request_and_bearer_auth(monkeypatch):
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"data": [{"pageNumber": 7, "html": "encoded"}]},
        ),
    )
    client = NoorlibClient(auth_token="test-token")
    try:
        page = await client.book_page(1327, 7, volume_number=2, section_number=3)
    finally:
        await client.close()

    request = requests[0]
    assert request.url.path == "/api/book/getBookPageContent"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert json.loads(request.content) == {
        "origin": "noorlib.web.app",
        "language": "fa",
        "bookId": 1327,
        "volumeNumber": 2,
        "sectionNumber": 3,
        "viewType": "html",
        "pageNumber": 7,
    }
    assert page["html"] == "encoded"


@pytest.mark.asyncio
async def test_hadith_search_posts_source_filter(monkeypatch):
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"data": {"resultList": [{"hadithId": 91}]}},
        ),
    )
    client = HadithClient()
    try:
        result = await client.search("العقل", page_number=2, page_size=5, source_ids=[1348])
    finally:
        await client.close()

    request = requests[0]
    assert request.url.path == "/service/api/elastic/v2/ElasticHadithList"
    payload = json.loads(request.content)
    assert payload["text"] == "العقل"
    assert payload["pageNumber"] == 2
    assert payload["pageSize"] == 5
    assert payload["bookList"] == [1348]
    assert result["resultList"] == [{"hadithId": 91}]


@pytest.mark.asyncio
async def test_quran_search_unwraps_double_encoded_response(monkeypatch):
    body = json.dumps({"data": {"resultList": [{"surahId": 24}]}})
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json=body),
    )
    client = QuranClient()
    try:
        result = await client.search("نور", source="translation", page_number=3, page_size=8)
    finally:
        await client.close()

    request = requests[0]
    assert request.url.path == "/api/Search/AutoComplete"
    assert request.url.params["searchText"] == "نور"
    assert request.url.params["source"] == "translation"
    assert request.url.params["pageNumber"] == "3"
    assert request.url.params["pageSize"] == "8"
    assert result["resultList"] == [{"surahId": 24}]


@pytest.mark.asyncio
async def test_quran_commentary_sends_required_empty_filters(monkeypatch):
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"Data": {"ResultSet1": [{"Text": "tafsir"}]}}),
    )
    client = QuranClient()
    try:
        result = await client.ayah_commentary(2, 255, page_number=2, page_size=4)
    finally:
        await client.close()

    params = requests[0].url.params
    assert params["surahId"] == "2"
    assert params["ayahNumber"] == "255"
    assert params["pageNumber"] == "2"
    assert params["pageSize"] == "4"
    assert params["bookIds"] == ""
    assert params["authorIds"] == ""
    assert params["languageIds"] == ""
    assert params["religionIds"] == ""
    assert result["ResultSet1"] == [{"Text": "tafsir"}]


@pytest.mark.asyncio
async def test_wikinoor_search_and_page_use_mediawiki_api(monkeypatch):
    def respond(request):
        if request.url.params["action"] == "query":
            return httpx.Response(200, json={"query": {"search": [{"title": "فصوص الحکم"}]}})
        return httpx.Response(
            200,
            json={
                "parse": {
                    "title": "فصوص الحکم",
                    "wikitext": {"*": "{{جعبه اطلاعات کتاب\n|عنوان=فصوص الحکم\n}}\nمتن مقاله"},
                }
            },
        )

    requests = _mock_transport(monkeypatch, respond)
    client = WikinoorClient()
    client.throttle = 0
    try:
        search = await client.search("فصوص الحکم", limit=7, offset=2)
        page = await client.page("فصوص الحکم")
    finally:
        await client.close()

    search_params = requests[0].url.params
    assert requests[0].url.path == "/w/api.php"
    assert search_params["action"] == "query"
    assert search_params["list"] == "search"
    assert search_params["srsearch"] == "فصوص الحکم"
    assert search_params["srlimit"] == "7"
    assert search_params["sroffset"] == "2"
    page_params = requests[1].url.params
    assert page_params["action"] == "parse"
    assert page_params["prop"] == "wikitext"
    assert page_params["redirects"] == "1"
    assert search["query"]["search"][0]["title"] == "فصوص الحکم"
    assert page["parse"]["title"] == "فصوص الحکم"


@pytest.mark.asyncio
async def test_qamus_search_body_and_word_version_header(monkeypatch):
    def respond(request):
        if request.url.path == "/term":
            return httpx.Response(200, json={"data": {"headWords": []}})
        return httpx.Response(200, json={"data": {"headWord": "نور"}})

    requests = _mock_transport(monkeypatch, respond)
    client = QamusClient()
    client.throttle = 0
    try:
        search = await client.search("نور", category="term", page_index=2, page_limit=6)
        word = await client.word("4J781M")
    finally:
        await client.close()

    payload = json.loads(requests[0].content)
    assert requests[0].url.path == "/term"
    assert payload["text"] == "نور"
    assert payload["language"] == {
        "searchIn": "fa",
        "target": "both",
        "conformity": 1,
    }
    assert payload["pageIndex"] == 2
    assert payload["pageLimit"] == 6
    assert requests[1].url.path == "/headWord"
    assert requests[1].url.params["headWordId"] == "4J781M"
    assert requests[1].headers["X-Api-Version"] == "2"
    assert search["headWords"] == []
    assert word["headWord"] == "نور"


@pytest.mark.asyncio
async def test_noordoc_search_filters_and_thesis_detail(monkeypatch):
    def respond(request):
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"totalCount": 1, "data": {"resultList": [{"id": 17}]}},
            )
        return httpx.Response(200, json={"data": {"id": 17, "abstracts": []}})

    requests = _mock_transport(monkeypatch, respond)
    client = NoordocClient()
    client.throttle = 0
    try:
        search = await client.search("عرفان", organization="university", education_level="phd")
        thesis = await client.thesis(17)
    finally:
        await client.close()

    search_request = requests[0]
    assert search_request.url.path == "/_search/api/v1.0/SearchThesis"
    payload = json.loads(search_request.content)
    assert payload["text"] == "عرفان"
    assert payload["organization"] == "university"
    assert payload["educationLevel"] == "phd"
    assert payload["fromTitle"] is True
    assert requests[1].url.path == "/_content/api/v1/thesis/17"
    assert search["totalCount"] == 1
    assert thesis["id"] == 17


@pytest.mark.asyncio
async def test_tarikh_search_parameters_and_hijri_date(monkeypatch):
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"Count": 1, "ResultList": [{"EventId": "FF5FD"}]}
        ),
    )
    client = TarikhClient()
    try:
        result = await client.search("فتح قسطنطنیه", page_number=2, page_size=4)
    finally:
        await client.close()

    params = requests[0].url.params
    assert requests[0].url.path == "/api/event/List"
    assert params["SearchPhrase"] == "فتح قسطنطنیه"
    assert params["PageNumber"] == "2"
    assert params["PageSize"] == "4"
    assert params["UserLanguage"] == "fa"
    assert result["Count"] == 1
    assert decode_tarikh_date(360520) == "36/05/20 قمری"


@pytest.mark.asyncio
async def test_shared_http_core_retries_server_errors(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"ok": True})

    _mock_transport(monkeypatch, respond)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("noorlib_mcp.siteclient.asyncio.sleep", no_sleep)
    client = SiteClient("https://example.test", throttle=0, retries=2)
    try:
        result = await client.get("/resource")
    finally:
        await client.close()

    assert len(calls) == 2
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_hadith_by_id_unwraps_envelope(monkeypatch):
    """ElasticHadithById returns {data: [...], status, isSuccess}, not a bare list."""
    requests = _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "data": [{"hadithId": 236718, "text": "<Hadith>متن حدیث</Hadith>"}],
                "status": 1,
                "isSuccess": True,
            },
        ),
    )
    client = HadithClient()
    try:
        rows = await client.hadith_by_id([236718])
    finally:
        await client.close()

    request = requests[0]
    assert request.url.path == "/service/api/elastic/ElasticHadithById"
    assert json.loads(request.content)["hadithId"] == [236718]
    assert rows and rows[0]["hadithId"] == 236718


@pytest.mark.asyncio
async def test_hadith_by_id_accepts_bare_list(monkeypatch):
    _mock_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json=[{"hadithId": 5, "text": "..."}]),
    )
    client = HadithClient()
    try:
        rows = await client.hadith_by_id([5])
    finally:
        await client.close()
    assert rows and rows[0]["hadithId"] == 5


@pytest.mark.asyncio
async def test_noorlib_retries_microservice_503_inside_http_200(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={"isSuccess": False, "statusCode": 503, "message": "service down"},
            )
        return httpx.Response(200, json={"isSuccess": True, "data": {"resultList": []}})

    _mock_transport(monkeypatch, respond)

    async def no_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("noorlib_mcp.siteclient.asyncio.sleep", no_sleep)
    client = NoorlibClient()
    client.throttle = 0
    try:
        result = await client.search("فصوص")
    finally:
        await client.close()

    assert len(calls) == 2
    assert result == {"resultList": []}
