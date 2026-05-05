"""测试 MiniSpider 类 - 直接运行即可测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from coocan import MiniSpider, Request, Response
from coocan.spider.base import IgnoreRequest, IgnoreResponse, Stats


def test_stats():
    print("测试统计类...")

    import time

    stats = Stats()
    assert stats.request_count == 0
    assert stats.success_count == 0
    assert stats.failed_count == 0
    print("  ✓ 初始值")

    time.sleep(0.1)
    assert stats.elapsed >= 0.1
    print("  ✓ 耗时计算")

    stats.request_count = 10
    stats.success_count = 8
    stats.failed_count = 2
    s = str(stats)
    assert "请求: 10" in s
    assert "成功: 8" in s
    assert "失败: 2" in s
    print("  ✓ 字符串表示")


def test_spider_init():
    print("测试 Spider 初始化...")

    spider = MiniSpider()
    assert spider.start_urls == []
    assert spider.max_concurrency == 5
    assert spider.max_retry_times == 3
    assert spider.enable_random_ua is True
    assert spider.delay == 0
    assert spider.item_speed == 10
    assert spider.enable_duplicate_filter is False
    print("  ✓ 默认值")

    assert isinstance(spider.stats, Stats)
    print("  ✓ stats 初始化")

    assert spider._seen_urls == set()
    print("  ✓ seen_urls 初始化")


def test_duplicate_filter():
    print("测试 URL 去重...")

    spider = MiniSpider()

    # 指纹生成
    req = Request("https://taobao.com")
    fp = spider._get_url_fingerprint(req)
    assert isinstance(fp, str)
    assert len(fp) == 32  # MD5
    print("  ✓ 指纹生成")

    # 相同 URL 相同指纹
    req1 = Request("https://taobao.com")
    req2 = Request("https://taobao.com")
    assert spider._get_url_fingerprint(req1) == spider._get_url_fingerprint(req2)
    print("  ✓ 相同 URL 相同指纹")

    # 不同 URL 不同指纹
    req1 = Request("https://taobao.com/1")
    req2 = Request("https://taobao.com/2")
    assert spider._get_url_fingerprint(req1) != spider._get_url_fingerprint(req2)
    print("  ✓ 不同 URL 不同指纹")

    # 禁用去重
    spider.enable_duplicate_filter = False
    req = Request("https://taobao.com")
    assert spider._is_duplicate(req) is False
    assert spider._is_duplicate(req) is False
    print("  ✓ 禁用去重")

    # 启用去重
    spider2 = MiniSpider()
    spider2.enable_duplicate_filter = True
    req = Request("https://taobao.com/test")
    assert spider2._is_duplicate(req) is False  # 第一次
    assert spider2._is_duplicate(req) is True  # 第二次
    print("  ✓ 启用去重")


def test_delay():
    print("测试延迟...")

    spider = MiniSpider()

    # 固定延迟
    spider.delay = 1.5
    assert spider._get_delay() == 1.5
    print("  ✓ 固定延迟")

    # 随机延迟
    spider.delay = (1.0, 3.0)
    for _ in range(100):
        delay = spider._get_delay()
        assert 1.0 <= delay <= 3.0
    print("  ✓ 随机延迟")


def test_start_requests():
    print("测试初始请求...")

    class TestSpider(MiniSpider):
        start_urls = ["https://taobao.com/1", "https://taobao.com/2"]

        def parse(self, response):
            pass

    spider = TestSpider()
    requests = list(spider.start_requests())
    assert len(requests) == 2
    assert all(isinstance(r, Request) for r in requests)
    assert requests[0].url == "https://taobao.com/1"
    print("  ✓ 从 start_urls 生成请求")

    # 空 start_urls
    spider2 = MiniSpider()
    try:
        list(spider2.start_requests())
        assert False, "应抛出异常"
    except AssertionError:
        pass
    print("  ✓ 空 start_urls 抛出异常")


def test_middleware():
    print("测试中间件...")

    spider = MiniSpider()
    spider.enable_random_ua = True
    req = Request("https://taobao.com")
    spider.middleware(req)
    assert "User-Agent" in req.headers
    assert req.headers["User-Agent"].startswith("Mozilla/5.0")
    print("  ✓ 随机 UA")

    spider2 = MiniSpider()
    spider2.enable_random_ua = False
    req = Request("https://taobao.com")
    spider2.middleware(req)
    assert "User-Agent" not in req.headers
    print("  ✓ 禁用随机 UA")

    spider3 = MiniSpider()
    spider3.headers_extra_field = {"X-Custom": "value"}
    req = Request("https://taobao.com")
    spider3.middleware(req)
    assert req.headers["X-Custom"] == "value"
    print("  ✓ 额外 headers")


def test_parse_not_implemented():
    print("测试默认 parse...")

    spider = MiniSpider()
    try:
        spider.parse(None)
        assert False, "应抛出异常"
    except NotImplementedError:
        pass
    print("  ✓ 默认 parse 抛出 NotImplementedError")


def test_exceptions():
    print("测试异常类...")

    exc = IgnoreRequest("测试忽略请求")
    assert str(exc) == "测试忽略请求"
    print("  ✓ IgnoreRequest")

    exc = IgnoreResponse("测试忽略响应")
    assert str(exc) == "测试忽略响应"
    print("  ✓ IgnoreResponse")


def test_integration_simple():
    print("测试简单爬取...")

    results = []

    class TestSpider(MiniSpider):
        start_urls = ["https://taobao.com"]
        max_concurrency = 1

        def parse(self, response: Response):
            title = response.get_one("//title/text()")
            yield {"title": title}

        def process_item(self, item):
            results.append(item)

    spider = TestSpider()
    spider.go()

    assert len(results) == 1
    assert results[0]["title"] is not None and len(results[0]["title"]) > 0
    assert spider.stats.request_count == 1
    assert spider.stats.success_count == 1
    assert spider.stats.item_count == 1
    print("  ✓ 爬取成功")
    print(f"  ✓ 统计: {spider.stats}")


def test_integration_duplicate():
    print("测试去重功能...")

    request_count = [0]

    class TestSpider(MiniSpider):
        enable_duplicate_filter = True
        max_concurrency = 2

        def start_requests(self):
            for _ in range(5):
                yield Request("https://taobao.com", callback=self.parse)

        def parse(self, response: Response):
            request_count[0] += 1

    spider = TestSpider()
    spider.go()

    assert request_count[0] == 1
    print("  ✓ 去重有效，只请求了 1 次")


def test_integration_lifecycle():
    print("测试生命周期钩子...")

    called = []

    class TestSpider(MiniSpider):
        start_urls = ["https://taobao.com"]
        max_concurrency = 1

        def spider_opened(self):
            called.append("opened")

        def spider_closed(self):
            called.append("closed")

        def parse(self, response):
            pass

    spider = TestSpider()
    spider.go()

    assert "opened" in called
    assert "closed" in called
    assert called.index("opened") < called.index("closed")
    print("  ✓ spider_opened 和 spider_closed 被调用")


def test_integration_chain():
    print("测试回调链...")

    results = []

    class TestSpider(MiniSpider):
        max_concurrency = 2

        def start_requests(self):
            yield Request("https://taobao.com", callback=self.parse_list)

        def parse_list(self, response: Response):
            results.append("list")
            yield Request("https://taobao.com", callback=self.parse_detail)

        def parse_detail(self, response: Response):
            results.append("detail")

    spider = TestSpider()
    spider.go()

    assert results == ["list", "detail"]
    print("  ✓ 回调链正常")


if __name__ == "__main__":
    print("=" * 50)
    print("测试 MiniSpider 类")
    print("=" * 50)

    test_stats()
    test_spider_init()
    test_duplicate_filter()
    test_delay()
    test_start_requests()
    test_middleware()
    test_parse_not_implemented()
    test_exceptions()

    print("\n" + "=" * 50)
    print("集成测试 (需要网络)")
    print("=" * 50)

    test_integration_simple()
    test_integration_duplicate()
    test_integration_lifecycle()
    test_integration_chain()

    print("=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)
