from typing import Callable

from httpx import Response
from parsel import Selector

from coocan.url.errs import ResponseCodeError, ResponseTextError


class SelectorResponse(Response):
    """可以使用 Xpath、CSS"""

    def __init__(self, response: Response):
        super().__init__(response.status_code)
        self.__dict__.update(response.__dict__)
        self._selector: Selector | None = None

    @property
    def selector(self) -> Selector:
        """延迟初始化 Selector，只有需要时才解析 HTML"""
        if self._selector is None:
            self._selector = Selector(text=self.text)
        return self._selector

    def __str__(self):
        return "<Response {}>".format(self.status_code)

    def xpath(self, query: str):
        return self.selector.xpath(query)

    def css(self, query: str):
        return self.selector.css(query)

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
        if self.text.find(text) != -1:
            raise ResponseTextError(f"has text: {text}")

    def raise_no_text(self, text: str):
        """无此文本则抛出异常"""
        if self.text.find(text) == -1:
            raise ResponseTextError(f"no text: {text}")
