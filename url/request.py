import itertools
import time
from collections.abc import Callable
from typing import Any

_counter = itertools.count()

import httpx
from loguru import logger

# 全局共享的 HTTP 客户端（无代理时使用）
_client: httpx.AsyncClient | None = None
_client_limits: httpx.Limits | None = None


def get_client(limits: httpx.Limits | None = None) -> httpx.AsyncClient:
    """获取全局共享的 HTTP 客户端。

    Args:
        limits: httpx.Limits 连接池限制，仅首次调用时生效。

    Returns:
        全局单例 httpx.AsyncClient。
    """
    global _client, _client_limits
    if _client is None:
        if limits is not None:
            _client = httpx.AsyncClient(timeout=10.0, limits=limits)
        else:
            _client = httpx.AsyncClient(timeout=10.0)
        _client_limits = limits
    elif limits is not None and limits != _client_limits:
        logger.warning("get_client() 传入的 limits 与已有客户端不同，将继续使用现有客户端")
    return _client


def create_client(
    limits: httpx.Limits | None = None,
    proxy: str | None = None,
) -> httpx.AsyncClient:
    """创建一个新的 HTTP 客户端，每次调用返回独立实例。

    Args:
        limits: httpx.Limits 连接池限制。
        proxy: 代理地址，如 ``"http://127.0.0.1:8080"``。

    Returns:
        新建的 httpx.AsyncClient。
    """
    kwargs: dict[str, Any] = {"timeout": 10.0}
    if limits is not None:
        kwargs["limits"] = limits
    if proxy is not None:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


async def close_client():
    """关闭全局 HTTP 客户端。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class Request:
    """HTTP 请求的封装，是爬虫框架的调度单元。

    每个 Request 对象描述一次 HTTP 请求：URL、方法、头、体、回调等。
    支持优先级调度（priority 越小越先执行），配合 asyncio.PriorityQueue 使用。

    Examples:
        最简 GET 请求::

            req = Request("https://example.com", callback=self.parse)

        POST JSON，带 headers::

            req = Request(
                "https://api.example.com",
                json={"page": 1},
                headers={"Authorization": "Bearer xxx"},
                callback=self.parse_api,
                cb_kwargs={"source": "api"},
            )

        使用代理，提升优先级::

            req = Request(
                "https://example.com",
                callback=self.parse,
                proxy="http://127.0.0.1:8080",
                priority=1,
            )

        在回调中 yield 下一个请求，实现链式爬取::

            def parse(self, response):
                for item in response.get_all("//a/@href"):
                    yield Request(item, callback=self.parse_detail)
    """

    def __init__(
        self,
        url: str,
        callback: Callable[..., Any] | None = None,
        cb_kwargs: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        proxy: str | None = None,
        timeout: int = 6,
        priority: float | None = None,
        method: str | None = None,
    ):
        """初始化请求对象。

        Args:
            url: 请求 URL（必填）。
            callback: 响应回调函数，签名为 ``callback(response, **cb_kwargs)``。
            cb_kwargs: 传给 callback 的额外关键字参数。
            params: URL 查询参数。
            headers: 请求头。
            cookies: 请求 cookies。
            data: 表单数据，POST/PUT/PATCH 时发送。
            json: JSON 数据，POST/PUT/PATCH 时发送。
            proxy: 代理地址，如 ``"http://127.0.0.1:8080"``。
            timeout: 请求超时秒数，默认 6。
            priority: 优先级，越小越先执行，默认当前时间戳。
            method: HTTP 方法，不传则自动推断（有 data/json 为 POST，否则 GET）。
        """
        self.url = url
        self.callback = callback
        self.cb_kwargs = cb_kwargs or {}
        self.params = params
        self.headers = headers or {}
        self.cookies = cookies
        self.data = data
        self.json = json
        self.proxy = proxy
        self.timeout = timeout
        self.priority = time.time() if priority is None else priority
        self._order = next(_counter)
        self.method = method

    def _get_method(self) -> str:
        """推断 HTTP 方法：显式指定 > 有 body 则 POST > 默认 GET。"""
        if self.method:
            return self.method.upper()
        if self.data is not None or self.json is not None:
            return "POST"
        return "GET"

    async def send(self, client: httpx.AsyncClient | None = None) -> httpx.Response:
        """发送 HTTP 请求并返回原始 httpx.Response。

        Args:
            client: 可复用的 httpx 客户端，不传则自动获取或创建。

        Returns:
            原始 httpx.Response 对象。
        """
        method = self._get_method()
        kwargs = {
            "url": self.url,
            "params": self.params,
            "headers": self.headers,
            "cookies": self.cookies,
            "timeout": self.timeout,
        }

        # POST/PUT/PATCH 请求添加 body
        if method in ("POST", "PUT", "PATCH"):
            kwargs["data"] = self.data
            kwargs["json"] = self.json

        if client is None:
            if self.proxy is not None:
                client = create_client(proxy=self.proxy)
                try:
                    response = await client.request(method, **kwargs)
                finally:
                    await client.aclose()
                return response
            client = get_client()
        response = await client.request(method, **kwargs)
        return response

    def __lt__(self, other: "Request") -> bool:
        """按 priority 比较，供 PriorityQueue 排序。"""
        return (self.priority, self._order) < (other.priority, other._order)

    def __repr__(self) -> str:
        return f"<Request [{self._get_method()}] {self.url} priority={self.priority}>"
