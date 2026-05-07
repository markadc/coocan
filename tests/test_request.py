"""测试 Request 类"""

import asyncio
import time

import pytest
import httpx

from coocan.url.request import Request, close_client, get_client


class TestRequestInit:
    def test_basic(self):
        req = Request("https://taobao.com")
        assert req.url == "https://taobao.com"
        assert req.callback is None
        assert req.cb_kwargs == {}
        assert req.headers == {}

    def test_with_callback(self):
        def my_callback(response):
            pass

        req = Request("https://taobao.com", callback=my_callback)
        assert req.callback is my_callback

    def test_with_headers(self):
        req = Request("https://taobao.com", headers={"User-Agent": "test"})
        assert req.headers == {"User-Agent": "test"}

    def test_with_cookies(self):
        req = Request("https://taobao.com", cookies={"session": "abc"})
        assert req.cookies == {"session": "abc"}

    def test_with_params(self):
        req = Request("https://taobao.com", params={"page": 1})
        assert req.params == {"page": 1}

    def test_with_proxy(self):
        req = Request("https://taobao.com", proxy="http://127.0.0.1:8080")
        assert req.proxy == "http://127.0.0.1:8080"

    def test_timeout_default(self):
        req = Request("https://taobao.com")
        assert req.timeout == 6

    def test_timeout_custom(self):
        req = Request("https://taobao.com", timeout=30)
        assert req.timeout == 30

    def test_priority_default(self):
        before = time.time()
        req = Request("https://taobao.com")
        after = time.time()
        assert before <= req.priority <= after

    def test_priority_custom(self):
        req = Request("https://taobao.com", priority=100.0)
        assert req.priority == 100.0


class TestRequestMethod:
    def test_default_get(self):
        req = Request("https://taobao.com")
        assert req._get_method() == "GET"

    def test_data_implies_post(self):
        req = Request("https://taobao.com", data={"key": "value"})
        assert req._get_method() == "POST"

    def test_json_implies_post(self):
        req = Request("https://taobao.com", json={"key": "value"})
        assert req._get_method() == "POST"

    def test_explicit_override(self):
        req = Request("https://taobao.com", data={"key": "value"}, method="PUT")
        assert req._get_method() == "PUT"

    def test_case_insensitive(self):
        req = Request("https://taobao.com", method="delete")
        assert req._get_method() == "DELETE"


class TestRequestPriorityQueue:
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
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

        assert first.url == "https://high.com"
        assert second.url == "https://mid.com"
        assert third.url == "https://low.com"

    @pytest.mark.asyncio
    async def test_same_priority_tie_breaker(self):
        """相同 priority 时，先创建的 Request 先出队"""
        queue = asyncio.PriorityQueue()
        req_a = Request("https://a.com", priority=1.0)
        req_b = Request("https://b.com", priority=1.0)

        await queue.put(req_a)
        await queue.put(req_b)

        first = await queue.get()
        second = await queue.get()

        assert first.url == "https://a.com"
        assert second.url == "https://b.com"


class TestRequestSend:
    @pytest.mark.asyncio
    async def test_get(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="ok", request=request)))
        req = Request("https://example.com/get", timeout=10)
        resp = await req.send(client)
        await client.aclose()
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_post_data(self):
        seen = {}

        def handler(request):
            seen["body"] = request.content
            return httpx.Response(200, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        req = Request("https://example.com/post", data={"key": "value"}, timeout=10)
        resp = await req.send(client)
        await client.aclose()
        assert resp.status_code == 200
        assert seen["body"] == b"key=value"

    @pytest.mark.asyncio
    async def test_post_json(self):
        seen = {}

        def handler(request):
            seen["body"] = request.content
            return httpx.Response(200, json={"json": {"key": "value"}}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        req = Request("https://example.com/post", json={"key": "value"}, timeout=10)
        resp = await req.send(client)
        await client.aclose()
        assert resp.status_code == 200
        data = resp.json()
        assert data["json"] == {"key": "value"}
        assert seen["body"] == b'{"key":"value"}'

    @pytest.mark.asyncio
    async def test_with_headers(self):
        seen = {}

        def handler(request):
            seen["header"] = request.headers["X-Custom-Header"]
            return httpx.Response(200, json={"headers": {"X-Custom-Header": seen["header"]}}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        req = Request(
            "https://example.com/headers",
            headers={"X-Custom-Header": "test-value"},
            timeout=10,
        )
        resp = await req.send(client)
        await client.aclose()
        data = resp.json()
        assert data["headers"]["X-Custom-Header"] == "test-value"

    @pytest.mark.asyncio
    async def test_with_params(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            return httpx.Response(200, json={"args": {"foo": request.url.params["foo"]}}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        req = Request("https://example.com/get", params={"foo": "bar"}, timeout=10)
        resp = await req.send(client)
        await client.aclose()
        data = resp.json()
        assert data["args"]["foo"] == "bar"
        assert seen["url"] == "https://example.com/get?foo=bar"

    @pytest.fixture(autouse=True)
    async def cleanup_client(self):
        yield
        await close_client()


class TestClientManagement:
    @pytest.mark.asyncio
    async def test_singleton(self):
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_recreate_after_close(self):
        await close_client()
        new_client = get_client()
        assert new_client is not None
        await close_client()

    @pytest.mark.asyncio
    async def test_limits_get_separate_clients(self):
        await close_client()
        client1 = get_client(httpx.Limits(max_connections=1))
        client2 = get_client(httpx.Limits(max_connections=2))
        assert client1 is not client2
        await close_client()
