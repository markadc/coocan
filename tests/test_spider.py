"""测试 MiniSpider 类"""

import time

import pytest

from coocan import MiniSpider, Request, Response
from coocan.spider.base import IgnoreRequest, IgnoreResponse, Stats


class TestStats:
    def test_initial_values(self):
        stats = Stats()
        assert stats.request_count == 0
        assert stats.success_count == 0
        assert stats.failed_count == 0

    def test_elapsed(self):
        stats = Stats()
        time.sleep(0.1)
        assert stats.elapsed >= 0.1

    def test_str_representation(self):
        stats = Stats()
        stats.request_count = 10
        stats.success_count = 8
        stats.failed_count = 2
        s = str(stats)
        assert "请求: 10" in s
        assert "成功: 8" in s
        assert "失败: 2" in s


class TestSpiderInit:
    def test_defaults(self):
        spider = MiniSpider()
        assert spider.start_urls == []
        assert spider.max_concurrency == 5
        assert spider.max_retry_times == 3
        assert spider.enable_random_ua is True
        assert spider.delay == 0
        assert spider.item_speed == 10
        assert spider.enable_duplicate_filter is False

    def test_stats_initialized(self):
        spider = MiniSpider()
        assert isinstance(spider.stats, Stats)

    def test_seen_urls_initialized(self):
        spider = MiniSpider()
        assert spider._seen_urls == set()


class TestDuplicateFilter:
    def test_fingerprint_format(self):
        spider = MiniSpider()
        req = Request("https://taobao.com")
        fp = spider._get_url_fingerprint(req)
        assert isinstance(fp, str)
        assert len(fp) == 32  # MD5

    def test_same_url_same_fingerprint(self):
        spider = MiniSpider()
        req1 = Request("https://taobao.com")
        req2 = Request("https://taobao.com")
        assert spider._get_url_fingerprint(req1) == spider._get_url_fingerprint(req2)

    def test_different_url_different_fingerprint(self):
        spider = MiniSpider()
        req1 = Request("https://taobao.com/1")
        req2 = Request("https://taobao.com/2")
        assert spider._get_url_fingerprint(req1) != spider._get_url_fingerprint(req2)

    def test_dict_order_independence(self):
        """相同内容不同顺序的 dict 应产生相同指纹"""
        spider = MiniSpider()
        req1 = Request("https://taobao.com", params={"b": 1, "a": 2})
        req2 = Request("https://taobao.com", params={"a": 2, "b": 1})
        assert spider._get_url_fingerprint(req1) == spider._get_url_fingerprint(req2)

    def test_disabled(self):
        spider = MiniSpider()
        spider.enable_duplicate_filter = False
        req = Request("https://taobao.com")
        assert spider._is_duplicate(req) is False
        assert spider._is_duplicate(req) is False

    def test_enabled(self):
        spider = MiniSpider()
        spider.enable_duplicate_filter = True
        req = Request("https://taobao.com/test")
        assert spider._is_duplicate(req) is False  # 第一次
        assert spider._is_duplicate(req) is True  # 第二次


class TestDelay:
    def test_fixed_delay(self):
        spider = MiniSpider()
        spider.delay = 1.5
        assert spider._get_delay() == 1.5

    def test_random_delay(self):
        spider = MiniSpider()
        spider.delay = (1.0, 3.0)
        for _ in range(100):
            delay = spider._get_delay()
            assert 1.0 <= delay <= 3.0


class TestStartRequests:
    def test_from_start_urls(self):
        class TestSpider(MiniSpider):
            start_urls = ["https://taobao.com/1", "https://taobao.com/2"]

            def parse(self, response):
                pass

        spider = TestSpider()
        requests = list(spider.start_requests())
        assert len(requests) == 2
        assert all(isinstance(r, Request) for r in requests)
        assert requests[0].url == "https://taobao.com/1"

    def test_empty_start_urls_raises(self):
        spider = MiniSpider()
        with pytest.raises(AssertionError):
            list(spider.start_requests())


class TestMiddleware:
    def test_random_ua(self):
        spider = MiniSpider()
        spider.enable_random_ua = True
        req = Request("https://taobao.com")
        spider.middleware(req)
        assert "User-Agent" in req.headers
        assert req.headers["User-Agent"].startswith("Mozilla/5.0")

    def test_disabled_random_ua(self):
        spider = MiniSpider()
        spider.enable_random_ua = False
        req = Request("https://taobao.com")
        spider.middleware(req)
        assert "User-Agent" not in req.headers

    def test_extra_headers(self):
        spider = MiniSpider()
        spider.headers_extra_field = {"X-Custom": "value"}
        req = Request("https://taobao.com")
        spider.middleware(req)
        assert req.headers["X-Custom"] == "value"


class TestParse:
    def test_not_implemented(self):
        spider = MiniSpider()
        with pytest.raises(NotImplementedError):
            spider.parse(None)


class TestExceptions:
    def test_ignore_request(self):
        exc = IgnoreRequest("测试忽略请求")
        assert str(exc) == "测试忽略请求"

    def test_ignore_response(self):
        exc = IgnoreResponse("测试忽略响应")
        assert str(exc) == "测试忽略响应"


@pytest.mark.online
class TestIntegrationSimple:
    def test_crawl(self):
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


@pytest.mark.online
class TestIntegrationDuplicate:
    def test_duplicate_filter(self):
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


@pytest.mark.online
class TestIntegrationLifecycle:
    def test_hooks_called(self):
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


@pytest.mark.online
class TestIntegrationChain:
    def test_callback_chain(self):
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
