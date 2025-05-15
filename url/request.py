import time
from typing import Callable

import httpx

cli = httpx.AsyncClient()


class Request:
    def __init__(
            self,
            url: str, callback: Callable = None, cb_kwargs=None,
            params=None, headers=None,
            data=None, json=None,
            proxy=None, timeout=6,
            priority=None
    ):
        self.url = url
        self.callback = callback
        self.cb_kwargs = cb_kwargs or {}
        self.params = params
        self.headers = headers or {}
        self.data = data
        self.json = json
        self.proxy = proxy
        self.timeout = timeout
        self.priority = priority or time.time()
        self.__client = None

    @property
    def client(self):
        if self.proxy is None:
            return cli
        return httpx.AsyncClient(proxy=self.proxy)

    async def send(self):
        if (self.data and self.json) is None:
            response = await self.client.get(self.url, params=self.params, headers=self.headers, timeout=self.timeout)
        elif self.data or self.json:
            response = await self.client.post(self.url, params=self.params, headers=self.headers, data=self.data, json=self.json, timeout=self.timeout)
        else:
            raise Exception("仅支持 GET 和 POST 请求")
        return response

    def __lt__(self, other):
        return self.priority < other.priority
