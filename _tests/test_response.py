"""测试 Response 类 - 直接运行即可测试"""

from coocan.url.errs import ResponseCodeError, ResponseTextError
from coocan.url.response import SelectorResponse


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>测试页面</title></head>
<body>
    <h1 class="title">标题</h1>
    <ul id="items">
        <li>项目1</li>
        <li>项目2</li>
        <li>项目3</li>
    </ul>
    <p class="content">这是内容</p>
</body>
</html>
"""


class MockResponse:
    """简单的模拟 Response 类"""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self._text = text
        self.content = text.encode() if text else b""
        self.headers = {}
        self.url = "https://example.com"
        self.encoding = "utf-8"

    @property
    def text(self):
        return self._text


def create_mock_response(status_code=200, text=""):
    """创建模拟的 httpx.Response"""
    return MockResponse(status_code, text)


def test_response_init():
    print("测试 Response 初始化...")

    mock = create_mock_response(200, "<html></html>")
    resp = SelectorResponse(mock)
    assert resp.status_code == 200
    print("  ✓ 基本初始化")

    assert str(resp) == "<Response 200>"
    print("  ✓ 字符串表示")

    assert resp._selector is None
    print("  ✓ Selector 延迟初始化")


def test_response_selector():
    print("测试选择器...")

    mock = create_mock_response(200, SAMPLE_HTML)
    resp = SelectorResponse(mock)

    # xpath
    titles = resp.xpath("//h1/text()").getall()
    assert titles == ["标题"]
    print("  ✓ xpath")

    # css
    titles = resp.css("h1.title::text").getall()
    assert titles == ["标题"]
    print("  ✓ css")

    # get_one
    title = resp.get_one("//title/text()")
    assert title == "测试页面"
    print("  ✓ get_one")

    # get_one with default
    result = resp.get_one("//nonexistent/text()", default="默认值")
    assert result == "默认值"
    print("  ✓ get_one 默认值")

    # get_all
    items = resp.get_all("//li/text()")
    assert items == ["项目1", "项目2", "项目3"]
    print("  ✓ get_all")

    # get_all empty
    items = resp.get_all("//nonexistent/text()")
    assert items == []
    print("  ✓ get_all 空结果")


def test_response_selector_cached():
    print("测试 Selector 缓存...")

    mock = create_mock_response(200, SAMPLE_HTML)
    resp = SelectorResponse(mock)

    sel1 = resp.selector
    sel2 = resp.selector
    assert sel1 is sel2
    print("  ✓ Selector 被缓存")


def test_response_validation():
    print("测试响应验证...")

    # raise_for_status 成功
    mock = create_mock_response(200)
    resp = SelectorResponse(mock)
    resp.raise_for_status()  # 不应抛出异常
    print("  ✓ raise_for_status 成功")

    # raise_for_status 带 codes
    mock = create_mock_response(201)
    resp = SelectorResponse(mock)
    resp.raise_for_status(codes=[200, 201, 204])
    print("  ✓ raise_for_status 带 codes")

    # raise_for_status 失败
    mock = create_mock_response(404)
    resp = SelectorResponse(mock)
    try:
        resp.raise_for_status()
        assert False, "应抛出异常"
    except ResponseCodeError:
        pass
    print("  ✓ raise_for_status 失败")

    # raise_for_text 成功
    mock = create_mock_response(200, "success")
    resp = SelectorResponse(mock)
    resp.raise_for_text(lambda t: "success" in t)
    print("  ✓ raise_for_text 成功")

    # raise_for_text 失败
    mock = create_mock_response(200, "error")
    resp = SelectorResponse(mock)
    try:
        resp.raise_for_text(lambda t: "success" in t)
        assert False, "应抛出异常"
    except ResponseTextError:
        pass
    print("  ✓ raise_for_text 失败")

    # raise_has_text 成功
    mock = create_mock_response(200, "正常内容")
    resp = SelectorResponse(mock)
    resp.raise_has_text("错误")  # 没有"错误"，不抛出
    print("  ✓ raise_has_text 成功")

    # raise_has_text 失败
    mock = create_mock_response(200, "发生错误")
    resp = SelectorResponse(mock)
    try:
        resp.raise_has_text("错误")
        assert False, "应抛出异常"
    except ResponseTextError:
        pass
    print("  ✓ raise_has_text 失败")

    # raise_no_text 成功
    mock = create_mock_response(200, "登录成功")
    resp = SelectorResponse(mock)
    resp.raise_no_text("成功")  # 包含"成功"，不抛出
    print("  ✓ raise_no_text 成功")

    # raise_no_text 失败
    mock = create_mock_response(200, "登录失败")
    resp = SelectorResponse(mock)
    try:
        resp.raise_no_text("成功")
        assert False, "应抛出异常"
    except ResponseTextError:
        pass
    print("  ✓ raise_no_text 失败")


if __name__ == "__main__":
    print("=" * 50)
    print("测试 Response 类")
    print("=" * 50)

    test_response_init()
    test_response_selector()
    test_response_selector_cached()
    test_response_validation()

    print("=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)
