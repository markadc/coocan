"""测试 Request 类 - 直接运行即可测试"""

import asyncio
import time

from coocan.url.request import Request, close_client, get_client


def test_request_init():
    print("测试 Request 初始化...")

    # 基本初始化
    req = Request("https://example.com")
    assert req.url == "https://example.com"
    assert req.callback is None
    assert req.cb_kwargs == {}
    assert req.headers == {}
    print("  ✓ 基本初始化")

    # 带回调
    def my_callback(response):
        pass

    req = Request("https://example.com", callback=my_callback)
    assert req.callback == my_callback
    print("  ✓ 带回调")

    # 带 headers
    req = Request("https://example.com", headers={"User-Agent": "test"})
    assert req.headers == {"User-Agent": "test"}
    print("  ✓ 带 headers")

    # 带 cookies
    req = Request("https://example.com", cookies={"session": "abc"})
    assert req.cookies == {"session": "abc"}
    print("  ✓ 带 cookies")

    # 带 params
    req = Request("https://example.com", params={"page": 1})
    assert req.params == {"page": 1}
    print("  ✓ 带 params")

    # 带 proxy
    req = Request("https://example.com", proxy="http://127.0.0.1:8080")
    assert req.proxy == "http://127.0.0.1:8080"
    print("  ✓ 带 proxy")

    # 超时
    req = Request("https://example.com")
    assert req.timeout == 6
    req = Request("https://example.com", timeout=30)
    assert req.timeout == 30
    print("  ✓ 超时设置")

    # 优先级
    before = time.time()
    req = Request("https://example.com")
    after = time.time()
    assert before <= req.priority <= after
    req = Request("https://example.com", priority=100.0)
    assert req.priority == 100.0
    print("  ✓ 优先级")


def test_request_method():
    print("测试 HTTP 方法推断...")

    # 默认 GET
    req = Request("https://example.com")
    assert req._get_method() == "GET"
    print("  ✓ 默认 GET")

    # 带 data 是 POST
    req = Request("https://example.com", data={"key": "value"})
    assert req._get_method() == "POST"
    print("  ✓ 带 data 是 POST")

    # 带 json 是 POST
    req = Request("https://example.com", json={"key": "value"})
    assert req._get_method() == "POST"
    print("  ✓ 带 json 是 POST")

    # 显式指定 method
    req = Request("https://example.com", data={"key": "value"}, method="PUT")
    assert req._get_method() == "PUT"
    print("  ✓ 显式指定覆盖")

    # 大小写不敏感
    req = Request("https://example.com", method="delete")
    assert req._get_method() == "DELETE"
    print("  ✓ 大小写不敏感")


def test_request_priority_queue():
    print("测试优先级队列排序...")

    async def test():
        queue = asyncio.PriorityQueue()
        req_high = Request("https://high.com", priority=1.0)
        req_low = Request("https://low.com", priority=10.0)
        req_mid = Request("https://mid.com", priority=5.0)

        await queue.put(req_low)
        await queue.put(req_high)
        await queue.put(req_mid)

        first = await queue.get()
        second = await queue.get()
        third = await queue.get()

        assert first.url == "https://high.com", f"第一个应该是 high, 实际是 {first.url}"
        assert second.url == "https://mid.com", f"第二个应该是 mid, 实际是 {second.url}"
        assert third.url == "https://low.com", f"第三个应该是 low, 实际是 {third.url}"

    asyncio.run(test())
    print("  ✓ 优先级排序正确")


def test_request_send():
    print("测试 HTTP 请求...")

    async def test():
        # GET 请求
        req = Request("https://httpbin.org/get", timeout=10)
        resp = await req.send()
        assert resp.status_code == 200
        print("  ✓ GET 请求")

        # POST 请求
        req = Request("https://httpbin.org/post", data={"key": "value"}, timeout=10)
        resp = await req.send()
        assert resp.status_code == 200
        print("  ✓ POST 请求")

        # POST JSON
        req = Request("https://httpbin.org/post", json={"key": "value"}, timeout=10)
        resp = await req.send()
        assert resp.status_code == 200
        data = resp.json()
        assert data["json"] == {"key": "value"}
        print("  ✓ POST JSON")

        # 带 headers
        req = Request(
            "https://httpbin.org/headers",
            headers={"X-Custom-Header": "test-value"},
            timeout=10,
        )
        resp = await req.send()
        data = resp.json()
        assert data["headers"]["X-Custom-Header"] == "test-value"
        print("  ✓ 带 headers")

        # 带 params
        req = Request("https://httpbin.org/get", params={"foo": "bar"}, timeout=10)
        resp = await req.send()
        data = resp.json()
        assert data["args"]["foo"] == "bar"
        print("  ✓ 带 params")

        await close_client()

    asyncio.run(test())


def test_client_management():
    print("测试客户端管理...")

    async def test():
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2
        print("  ✓ 获取同一实例")

        await close_client()
        new_client = get_client()
        assert new_client is not None
        print("  ✓ 关闭后重新创建")

        await close_client()

    asyncio.run(test())


if __name__ == "__main__":
    print("=" * 50)
    print("测试 Request 类")
    print("=" * 50)

    test_request_init()
    test_request_method()
    test_request_priority_queue()
    test_request_send()
    test_client_management()

    print("=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)
