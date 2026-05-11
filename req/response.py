from collections.abc import Callable
from typing import Any

from httpx import Headers, Response
from parsel import Selector, SelectorList

from coocan.req.errs import ResponseCodeError, ResponseTextError


class SelectorResponse:
    """包装 httpx.Response，提供 XPath / CSS 选择器能力。

    延迟初始化 parsel.Selector —— 只有调用 xpath/css/get_one/get_all 时才会解析 HTML，
    避免了不必要的解析开销。

    Attributes:
        status_code: HTTP 状态码（int）。
        text: 响应文本（str）。
        content: 响应原始字节（bytes）。
        url: 最终 URL，含重定向后的（str）。
        headers: 响应头（dict）。
        request: 原始请求对象。

    Examples:
        提取数据::

            # XPath（默认）
            response.get_one("//title/text()")           # 提取第一个
            response.get_all("//a/@href")               # 提取全部
            response.xpath("//div[@class='content']")    # 返回 parsel 对象

            # CSS 选择器
            response.get_one("title::text", method="css")
            response.css("div.content")

        响应校验::

            response.raise_for_status()                  # 非 200 抛异常
            response.raise_for_status(codes=[200, 302])  # 自定义合法状态码
            response.raise_for_text(lambda t: "success" in t)  # 文本不含 success 抛异常
            response.raise_has_text("错误")               # 含"错误"抛异常
            response.raise_no_text("登录")                # 不含"登录"抛异常
    """

    def __init__(self, response: Response):
        """初始化。

        Args:
            response: httpx.Response 对象。
        """
        self._response = response
        self._selector: Selector | None = None
        # 代理常用属性，避免 __dict__.update 拷贝所有内部状态
        self.status_code: int = response.status_code
        self.headers: Headers = response.headers
        self.url: str = str(response.url)
        self.request = getattr(response, "request", None)

    @property
    def text(self) -> str:
        """响应文本（str）。"""
        return self._response.text

    @property
    def content(self) -> bytes:
        """响应原始字节（bytes）。"""
        return self._response.content

    @property
    def encoding(self) -> str:
        """响应编码。"""
        return self._response.encoding

    def json(self) -> Any:
        """解析 JSON 响应体。

        Returns:
            解析后的 dict 或 list。
        """
        return self._response.json()

    @property
    def selector(self) -> Selector:
        """延迟初始化 parsel.Selector，首次访问时解析 HTML。"""
        if self._selector is None:
            self._selector = Selector(text=self.text)
        return self._selector

    def __str__(self) -> str:
        return "<Response {}>".format(self.status_code)

    def xpath(self, query: str) -> SelectorList:
        """执行 XPath 查询。

        Args:
            query: XPath 表达式。

        Returns:
            parsel SelectorList 对象。
        """
        return self.selector.xpath(query)

    def css(self, query: str) -> SelectorList:
        """执行 CSS 选择器查询。

        Args:
            query: CSS 选择器表达式。

        Returns:
            parsel SelectorList 对象。
        """
        return self.selector.css(query)

    def get_one(
        self,
        query: str,
        default: Any = None,
        strip: bool = True,
        method: str = "xpath",
    ) -> str | None:
        """提取第一个匹配的文本。

        Args:
            query: XPath 或 CSS 选择器。
            default: 无匹配时的默认值。
            strip: 是否去除首尾空白，默认 True。
            method: ``"xpath"``（默认）或 ``"css"``。

        Returns:
            匹配的文本，或 default。
        """
        sel = self.selector.xpath(query) if method == "xpath" else self.selector.css(query)
        v = sel.get(default=default)
        return v.strip() if strip and isinstance(v, str) else v

    def get_all(
        self,
        query: str,
        strip: bool = True,
        method: str = "xpath",
    ) -> list[str]:
        """提取所有匹配的文本列表。

        Args:
            query: XPath 或 CSS 选择器。
            strip: 是否去除首尾空白，默认 True。
            method: ``"xpath"``（默认）或 ``"css"``。

        Returns:
            匹配文本的列表，无匹配时为空列表。
        """
        sel = self.selector.xpath(query) if method == "xpath" else self.selector.css(query)
        vs = [v.strip() if strip else v for v in sel.getall()]
        return vs

    def raise_for_status(self, codes: list[int] | None = None):
        """状态码不在合法列表中则抛出 ResponseCodeError。

        Args:
            codes: 合法状态码列表，默认 ``[200]``。

        Raises:
            ResponseCodeError: 状态码不合法。
        """
        codes = codes or [200]
        if self.status_code not in codes:
            raise ResponseCodeError("{} not in {}".format(self.status_code, codes))

    def raise_for_text(self, validate: Callable[[str], bool]) -> None:
        """自定义文本校验。

        Args:
            validate: 校验函数，签名为 ``(text: str) -> bool``。

        Raises:
            ResponseTextError: validate 返回 False。
        """
        if validate(self.text) is False:
            raise ResponseTextError("响应文本未通过自定义校验")

    def raise_has_text(self, text: str) -> None:
        """响应中包含指定文本时抛出异常，用于检测错误页面。

        Args:
            text: 要检测的文本。

        Raises:
            ResponseTextError: 响应中包含该文本。
        """
        if text in self.text:
            raise ResponseTextError(f"响应中包含不应存在的文本: {text}")

    def raise_no_text(self, text: str) -> None:
        """响应中不含指定文本时抛出异常，用于检测登录失效等。

        Args:
            text: 要检测的文本。

        Raises:
            ResponseTextError: 响应中不含该文本。
        """
        if text not in self.text:
            raise ResponseTextError(f"响应中缺少必需的文本: {text}")
