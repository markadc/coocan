"""测试 Response 类"""

import httpx
import pytest

from coocan.req.errs import ResponseCodeError, ResponseTextError
from coocan.req.response import SelectorResponse

HTML = """
<html>
  <head><title>淘宝测试页</title></head>
  <body>
    <a href="/a">A</a>
    <div class="content"> 内容 </div>
  </body>
</html>
"""


async def _fetch(url: str) -> SelectorResponse:
    request = httpx.Request("GET", url)
    if url.endswith("/json"):
        resp = httpx.Response(200, json={"headers": {"User-Agent": "test"}}, request=request)
    else:
        resp = httpx.Response(200, text=HTML, request=request)
    return SelectorResponse(resp)


class TestRealFetch:
    @pytest.mark.asyncio
    async def test_status_and_text(self):
        resp = await _fetch("https://example.com")
        assert resp.status_code == 200
        assert len(resp.text) > 0


class TestSelector:
    @pytest.mark.asyncio
    async def test_xpath(self):
        resp = await _fetch("https://example.com")
        titles = resp.xpath("//title/text()").getall()
        assert len(titles) >= 1

    @pytest.mark.asyncio
    async def test_css_matches_xpath(self):
        resp = await _fetch("https://example.com")
        titles_xpath = resp.xpath("//title/text()").getall()
        titles_css = resp.css("title::text").getall()
        assert titles_css == titles_xpath

    @pytest.mark.asyncio
    async def test_get_one(self):
        resp = await _fetch("https://example.com")
        titles = resp.xpath("//title/text()").getall()
        title = resp.get_one("//title/text()")
        assert title == titles[0]

    @pytest.mark.asyncio
    async def test_get_one_default(self):
        resp = await _fetch("https://example.com")
        default_val = resp.get_one("//nonexistent_xpath/text()", default="默认值")
        assert default_val == "默认值"

    @pytest.mark.asyncio
    async def test_get_all(self):
        resp = await _fetch("https://example.com")
        titles = resp.xpath("//title/text()").getall()
        all_items = resp.get_all("//title/text()")
        assert all_items == titles

    @pytest.mark.asyncio
    async def test_get_all_empty(self):
        resp = await _fetch("https://example.com")
        empty = resp.get_all("//nonexistent_xpath/text()")
        assert empty == []


class TestCssMethod:
    @pytest.mark.asyncio
    async def test_get_one_css(self):
        resp = await _fetch("https://example.com")
        title = resp.get_one("title::text", method="css")
        xpath_title = resp.get_one("//title/text()")
        assert title == xpath_title

    @pytest.mark.asyncio
    async def test_get_all_css(self):
        resp = await _fetch("https://example.com")
        titles = resp.get_all("title::text", method="css")
        xpath_titles = resp.get_all("//title/text()")
        assert titles == xpath_titles


class TestSelectorCached:
    @pytest.mark.asyncio
    async def test_cached(self):
        resp = await _fetch("https://example.com")
        sel1 = resp.selector
        sel2 = resp.selector
        assert sel1 is sel2


class TestStrRepresentation:
    @pytest.mark.asyncio
    async def test_str(self):
        resp = await _fetch("https://example.com")
        s = str(resp)
        assert s.startswith("<Response ")


class TestTextAndContent:
    @pytest.mark.asyncio
    async def test_types(self):
        resp = await _fetch("https://example.com")
        assert isinstance(resp.text, str)
        assert isinstance(resp.content, bytes)
        assert resp.url is not None
        assert hasattr(resp.headers, "items")


class TestJson:
    @pytest.mark.asyncio
    async def test_json_parsing(self):
        resp = await _fetch("https://example.com/json")
        data = resp.json()
        assert "headers" in data


class TestValidation:
    @pytest.mark.asyncio
    async def test_raise_for_status_success(self):
        resp = await _fetch("https://example.com")
        resp.raise_for_status(codes=[200, 302])

    @pytest.mark.asyncio
    async def test_raise_for_status_failure(self):
        resp = await _fetch("https://example.com")
        with pytest.raises(ResponseCodeError):
            resp.raise_for_status(codes=[404])

    @pytest.mark.asyncio
    async def test_raise_for_text_success(self):
        resp = await _fetch("https://example.com")
        resp.raise_for_text(lambda t: "</html>" in t.lower() or "</HTML>" in t)

    @pytest.mark.asyncio
    async def test_raise_for_text_failure(self):
        resp = await _fetch("https://example.com")
        with pytest.raises(ResponseTextError):
            resp.raise_for_text(lambda t: "IMPOSSIBLE_STRING_XYZ" in t)

    @pytest.mark.asyncio
    async def test_raise_has_text(self):
        resp = await _fetch("https://example.com")
        resp.raise_has_text("验证码")  # 页面不含此文本则通过

    @pytest.mark.asyncio
    async def test_raise_no_text(self):
        resp = await _fetch("https://example.com")
        resp.raise_no_text("淘宝")  # 页面含此文本则通过
