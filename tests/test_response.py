"""测试 Response 类"""

import httpx
import pytest

from coocan.url.errs import ResponseCodeError, ResponseTextError
from coocan.url.request import Request, close_client
from coocan.url.response import SelectorResponse

TAOBAO = "https://www.taobao.com"


async def _fetch(url: str) -> SelectorResponse:
    req = Request(url, timeout=10)
    client = httpx.AsyncClient(timeout=10.0, trust_env=False)
    try:
        resp = await req.send(client)
    finally:
        await client.aclose()
    await close_client()
    return SelectorResponse(resp)


@pytest.mark.online
class TestRealFetch:
    @pytest.mark.asyncio
    async def test_status_and_text(self):
        resp = await _fetch(TAOBAO)
        assert resp.status_code in (200, 302)
        assert len(resp.text) > 0


@pytest.mark.online
class TestSelector:
    @pytest.mark.asyncio
    async def test_xpath(self):
        resp = await _fetch(TAOBAO)
        titles = resp.xpath("//title/text()").getall()
        assert len(titles) >= 1

    @pytest.mark.asyncio
    async def test_css_matches_xpath(self):
        resp = await _fetch(TAOBAO)
        titles_xpath = resp.xpath("//title/text()").getall()
        titles_css = resp.css("title::text").getall()
        assert titles_css == titles_xpath

    @pytest.mark.asyncio
    async def test_get_one(self):
        resp = await _fetch(TAOBAO)
        titles = resp.xpath("//title/text()").getall()
        title = resp.get_one("//title/text()")
        assert title == titles[0]

    @pytest.mark.asyncio
    async def test_get_one_default(self):
        resp = await _fetch(TAOBAO)
        default_val = resp.get_one("//nonexistent_xpath/text()", default="默认值")
        assert default_val == "默认值"

    @pytest.mark.asyncio
    async def test_get_all(self):
        resp = await _fetch(TAOBAO)
        titles = resp.xpath("//title/text()").getall()
        all_items = resp.get_all("//title/text()")
        assert all_items == titles

    @pytest.mark.asyncio
    async def test_get_all_empty(self):
        resp = await _fetch(TAOBAO)
        empty = resp.get_all("//nonexistent_xpath/text()")
        assert empty == []


@pytest.mark.online
class TestCssMethod:
    @pytest.mark.asyncio
    async def test_get_one_css(self):
        resp = await _fetch(TAOBAO)
        title = resp.get_one("title::text", method="css")
        xpath_title = resp.get_one("//title/text()")
        assert title == xpath_title

    @pytest.mark.asyncio
    async def test_get_all_css(self):
        resp = await _fetch(TAOBAO)
        titles = resp.get_all("title::text", method="css")
        xpath_titles = resp.get_all("//title/text()")
        assert titles == xpath_titles


@pytest.mark.online
class TestSelectorCached:
    @pytest.mark.asyncio
    async def test_cached(self):
        resp = await _fetch(TAOBAO)
        sel1 = resp.selector
        sel2 = resp.selector
        assert sel1 is sel2


@pytest.mark.online
class TestStrRepresentation:
    @pytest.mark.asyncio
    async def test_str(self):
        resp = await _fetch(TAOBAO)
        s = str(resp)
        assert s.startswith("<Response ")


@pytest.mark.online
class TestTextAndContent:
    @pytest.mark.asyncio
    async def test_types(self):
        resp = await _fetch(TAOBAO)
        assert isinstance(resp.text, str)
        assert isinstance(resp.content, bytes)
        assert resp.url is not None
        assert hasattr(resp.headers, "items")


@pytest.mark.online
class TestJson:
    @pytest.mark.asyncio
    async def test_json_parsing(self):
        resp = await _fetch("https://httpbin.org/get")
        data = resp.json()
        assert "headers" in data


@pytest.mark.online
class TestValidation:
    @pytest.mark.asyncio
    async def test_raise_for_status_success(self):
        resp = await _fetch(TAOBAO)
        resp.raise_for_status(codes=[200, 302])

    @pytest.mark.asyncio
    async def test_raise_for_status_failure(self):
        resp = await _fetch(TAOBAO)
        with pytest.raises(ResponseCodeError):
            resp.raise_for_status(codes=[404])

    @pytest.mark.asyncio
    async def test_raise_for_text_success(self):
        resp = await _fetch(TAOBAO)
        resp.raise_for_text(lambda t: "</html>" in t.lower() or "</HTML>" in t)

    @pytest.mark.asyncio
    async def test_raise_for_text_failure(self):
        resp = await _fetch(TAOBAO)
        with pytest.raises(ResponseTextError):
            resp.raise_for_text(lambda t: "IMPOSSIBLE_STRING_XYZ" in t)

    @pytest.mark.asyncio
    async def test_raise_has_text(self):
        resp = await _fetch(TAOBAO)
        resp.raise_has_text("验证码")  # 页面不含此文本则通过

    @pytest.mark.asyncio
    async def test_raise_no_text(self):
        resp = await _fetch(TAOBAO)
        resp.raise_no_text("淘宝")  # 页面含此文本则通过
