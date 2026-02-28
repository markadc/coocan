import time
from typing import Any, Callable

import httpx

# 全局共享的 HTTP 客户端（无代理时使用）
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """获取全局共享的 HTTP 客户端"""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_client():
    """关闭全局 HTTP 客户端"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class Request:
    def __init__(
        self,
        url: str,
        callback: Callable = None,
        cb_kwargs: dict[str, Any] = None,
        params: dict[str, Any] = None,
        headers: dict[str, str] = None,
        cookies: dict[str, str] = None,
        data: dict[str, Any] = None,
        json: dict[str, Any] = None,
        proxy: str = None,
        timeout: int = 6,
        priority: float = None,
        method: str = None,
    ):
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
        self.method = method

    def _get_method(self) -> str:
        """推断 HTTP 方法"""
        if self.method:
            return self.method.upper()
        if self.data is not None or self.json is not None:
            return "POST"
        return "GET"

    async def send(self) -> httpx.Response:
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

        # 使用代理时创建临时客户端，用完即关闭
        if self.proxy:
            async with httpx.AsyncClient(proxy=self.proxy) as client:
                response = await client.request(method, **kwargs)
        else:
            client = get_client()
            response = await client.request(method, **kwargs)

        return response

    def __lt__(self, other):
        return self.priority < other.priority
