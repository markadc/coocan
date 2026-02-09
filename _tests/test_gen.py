"""测试 UA 生成器 - 直接运行即可测试"""

import re

from coocan.gen import gen_random_browser, gen_random_os, gen_random_ua


def test_gen_random_os():
    print("测试 gen_random_os...")
    result = gen_random_os()
    assert isinstance(result, str), "应返回字符串"

    valid_os = ["Windows", "Macintosh", "Linux", "X11"]
    assert any(os in result for os in valid_os), f"应包含有效的操作系统: {result}"

    # 测试随机性
    results = {gen_random_os() for _ in range(50)}
    assert len(results) > 1, "多次调用应产生不同结果"
    print(f"  ✓ 生成了 {len(results)} 种不同的 OS")


def test_gen_random_browser():
    print("测试 gen_random_browser...")
    result = gen_random_browser()
    assert isinstance(result, str), "应返回字符串"
    assert re.match(r"^(Chrome|Firefox|Edge|Safari)/\d+\.0$", result), f"格式错误: {result}"

    results = {gen_random_browser() for _ in range(50)}
    assert len(results) > 1, "多次调用应产生不同结果"
    print(f"  ✓ 生成了 {len(results)} 种不同的浏览器")


def test_gen_random_ua():
    print("测试 gen_random_ua...")
    result = gen_random_ua()
    assert isinstance(result, str), "应返回字符串"
    assert result.startswith("Mozilla/5.0"), f"应以 Mozilla/5.0 开头: {result}"
    assert "AppleWebKit/537.36" in result, f"应包含 AppleWebKit: {result}"

    results = {gen_random_ua() for _ in range(50)}
    assert len(results) > 1, "多次调用应产生不同结果"
    print(f"  ✓ 生成了 {len(results)} 种不同的 UA")
    print(f"  示例: {result}")


if __name__ == "__main__":
    print("=" * 50)
    print("测试 UA 生成器")
    print("=" * 50)

    test_gen_random_os()
    test_gen_random_browser()
    test_gen_random_ua()

    print("=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)
