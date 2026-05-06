"""测试 UA 生成器"""

import re

import pytest

from coocan.gen import gen_random_browser, gen_random_os, gen_random_ua


class TestGenRandomOS:
    def test_returns_string(self):
        result = gen_random_os()
        assert isinstance(result, str)

    def test_contains_valid_os(self):
        result = gen_random_os()
        valid_os = ["Windows", "Macintosh", "Linux", "X11"]
        assert any(os in result for os in valid_os), f"应包含有效的操作系统: {result}"

    def test_randomness(self):
        results = {gen_random_os() for _ in range(50)}
        assert len(results) > 1, "多次调用应产生不同结果"


class TestGenRandomBrowser:
    def test_returns_string(self):
        result = gen_random_browser()
        assert isinstance(result, str)

    def test_format(self):
        result = gen_random_browser()
        assert re.match(r"^(Chrome|Firefox|Edge|Safari)/\d+\.0$", result), f"格式错误: {result}"

    def test_randomness(self):
        results = {gen_random_browser() for _ in range(50)}
        assert len(results) > 1, "多次调用应产生不同结果"


class TestGenRandomUA:
    def test_returns_string(self):
        result = gen_random_ua()
        assert isinstance(result, str)

    def test_starts_with_mozilla(self):
        result = gen_random_ua()
        assert result.startswith("Mozilla/5.0"), f"应以 Mozilla/5.0 开头: {result}"

    @pytest.mark.parametrize(
        "expected_substring",
        [
            pytest.param(
                "AppleWebKit/537.36",
                id="webkit-chrome-firefox-edge",
            ),
        ],
    )
    def test_contains_webkit_for_non_safari(self, expected_substring):
        """非 Safari 浏览器应包含 AppleWebKit/537.36"""
        for _ in range(200):
            ua = gen_random_ua()
            if "Version/" not in ua:  # Safari 使用 Version/ 标记
                assert expected_substring in ua, f"应包含 {expected_substring}: {ua}"
                return
        pytest.skip("200 次生成中未命中非 Safari 浏览器")

    def test_safari_format(self):
        """Safari 应使用正确的 UA 格式"""
        for _ in range(200):
            ua = gen_random_ua()
            if "Version/" in ua:
                assert "AppleWebKit/605.1.15" in ua, f"Safari UA 错误: {ua}"
                assert "Safari/605.1.15" in ua, f"Safari UA 错误: {ua}"
                return
        pytest.skip("200 次生成中未命中 Safari")

    def test_randomness(self):
        results = {gen_random_ua() for _ in range(50)}
        assert len(results) > 1, "多次调用应产生不同结果"
