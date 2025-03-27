from typing import Callable

import httpx

cli = httpx.AsyncClient()


class Request:
    def __init__(self, url, callback: Callable = None, params=None, headers=None, data=None, json=None, timeout=None, cb_kwargs=None):
        self.url = url
        self.callback = callback
        self.params = params
        self.headers = headers or {}
        self.data = data
        self.json = json
        self.timeout = timeout
        self.cb_kwargs = cb_kwargs or {}

    async def send(self):
        response = await cli.get(self.url, params=self.params, headers=self.headers, timeout=self.timeout)
        return response
