from typing import Callable

from cocoman.spider.errors import ResponseCodeError, ResponseTextError
from httpx import Response
from parsel import Selector


class SelectorResponse(Response):
    """可以使用Xpath、CSS"""

    def __init__(self, response: Response):
        super().__init__(response.status_code)
        self.__dict__.update(response.__dict__)
        self.selector = Selector(text=response.text)

    def __str__(self):
        return "<Response {}>".format(self.status_code)

    def xpath(self, query: str):
        sel = self.selector.xpath(query)
        return sel

    def css(self, query: str):
        sel = self.selector.css(query)
        return sel

    def get_one(self, query: str, default=None, strip=True):
        v = self.selector.xpath(query).get(default=default)
        return v.strip() if strip and isinstance(v, str) else v

    def get_all(self, query: str, strip=True):
        vs = [v.strip() if strip else v for v in self.selector.xpath(query).getall()]
        return vs

    def raise_for_status(self, codes: list = None):
        codes = codes or [200]
        if self.status_code not in codes:
            raise ResponseCodeError("{} not in {}".format(self.status_code, codes))

    def raise_for_text(self, validate: Callable[[str], bool]):
        if validate(self.text) is False:
            raise ResponseTextError("not ideal text")

    def raise_has_text(self, text: str):
        """有此文本则抛出异常"""
        assert self.text.find(text) == -1, ResponseTextError("has text: {}".format(text))

    def raise_no_text(self, text: str):
        """无此文本则抛出异常"""
        assert self.text.find(text) != -1, ResponseTextError("no text: {}".format(text))
