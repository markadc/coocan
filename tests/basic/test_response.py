"""测试 Response 类 — 真实 HTTP 请求"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import asyncio

import httpx

from coocan.url.errs import ResponseCodeError, ResponseTextError
from coocan.url.request import Request, close_client
from coocan.url.response import SelectorResponse

TAOBAO = "https://www.taobao.com"


async def _fetch(url):
    req = Request(url, timeout=10)
    client = httpx.AsyncClient(timeout=10.0, trust_env=False)
    try:
        resp = await req.send(client)
    finally:
        await client.aclose()
    await close_client()
    return SelectorResponse(resp)


def test_real_fetch():
    print("测试真实请求...")
    resp = asyncio.run(_fetch(TAOBAO))
    assert resp.status_code in (200, 302)
    assert len(resp.text) > 0
    print(f"  ✓ status={resp.status_code}, text_len={len(resp.text)}")


def test_selector():
    print("测试选择器...")
    resp = asyncio.run(_fetch(TAOBAO))
    # 淘宝首页应该有 title 标签
    titles = resp.xpath("//title/text()").getall()
    assert len(titles) >= 1
    print(f"  ✓ xpath titles={titles}")

    titles_css = resp.css("title::text").getall()
    assert titles_css == titles
    print("  ✓ css 与 xpath 一致")

    title = resp.get_one("//title/text()")
    assert title == titles[0]
    print(f"  ✓ get_one: {title}")

    default_val = resp.get_one("//nonexistent_xpath/text()", default="默认值")
    assert default_val == "默认值"
    print("  ✓ get_one 默认值")

    all_items = resp.get_all("//title/text()")
    assert all_items == titles
    print("  ✓ get_all")

    empty = resp.get_all("//nonexistent_xpath/text()")
    assert empty == []
    print("  ✓ get_all 空结果")


def test_css_method():
    print("测试 get_one/get_all method=css...")
    resp = asyncio.run(_fetch(TAOBAO))
    title = resp.get_one("title::text", method="css")
    xpath_title = resp.get_one("//title/text()")
    assert title == xpath_title
    print(f"  ✓ CSS: {title}")

    titles = resp.get_all("title::text", method="css")
    xpath_titles = resp.get_all("//title/text()")
    assert titles == xpath_titles
    print(f"  ✓ CSS get_all: {titles}")


def test_selector_cached():
    print("测试 Selector 缓存...")
    resp = asyncio.run(_fetch(TAOBAO))
    sel1 = resp.selector
    sel2 = resp.selector
    assert sel1 is sel2
    print("  ✓ Selector 被缓存")


def test_str():
    print("测试字符串表示...")
    resp = asyncio.run(_fetch(TAOBAO))
    s = str(resp)
    assert s.startswith("<Response ")
    print(f"  ✓ {s}")


def test_text_and_content():
    print("测试属性代理...")
    resp = asyncio.run(_fetch(TAOBAO))
    assert isinstance(resp.text, str)
    assert isinstance(resp.content, bytes)
    assert resp.url is not None
    assert isinstance(resp.headers, dict) or hasattr(resp.headers, "items")
    print("  ✓ text/content/url/headers")


def test_json():
    print("测试 json()...")
    resp = asyncio.run(_fetch("https://httpbin.org/get"))
    data = resp.json()
    assert "headers" in data
    print("  ✓ json 解析成功")


def test_validation():
    print("测试响应验证...")
    resp = asyncio.run(_fetch(TAOBAO))

    resp.raise_for_status(codes=[200, 302])
    print("  ✓ raise_for_status 成功")

    try:
        resp.raise_for_status(codes=[404])
        assert False
    except ResponseCodeError:
        pass
    print("  ✓ raise_for_status 失败")

    resp.raise_for_text(lambda t: "</html>" in t.lower() or "</HTML>" in t)
    print("  ✓ raise_for_text 成功")

    try:
        resp.raise_for_text(lambda t: "IMPOSSIBLE_STRING_XYZ" in t)
        assert False
    except ResponseTextError:
        pass
    print("  ✓ raise_for_text 失败")

    resp.raise_has_text("验证码")  # 页面不含此文本则通过
    print("  ✓ raise_has_text")

    resp.raise_no_text("淘宝")  # 页面含此文本则通过
    print("  ✓ raise_no_text")


if __name__ == "__main__":
    print("=" * 50)
    print("测试 Response 类（真实 HTTP）")
    print("=" * 50)

    test_real_fetch()
    test_selector()
    test_css_method()
    test_selector_cached()
    test_str()
    test_text_and_content()
    test_json()
    test_validation()

    print("=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)
