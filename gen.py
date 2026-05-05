import random


def gen_random_os() -> str:
    """生成一个随机的操作系统"""
    os_choices = [
        "Windows NT 10.0; Win64; x64",
        "Windows NT 11.0; Win64; x64",
        "Macintosh; Intel Mac OS X 10_15_7",
        "Macintosh; Intel Mac OS X 14_0",
        "X11; Linux x86_64",
        "X11; Ubuntu; Linux x86_64",
    ]
    return random.choice(os_choices)


def gen_random_browser() -> str:
    """生成一个随机的浏览器类型和版本"""
    browser_choices = [
        ("Chrome", (125, 138)),
        ("Firefox", (120, 132)),
        ("Edge", (125, 138)),
        ("Safari", (16, 18)),
    ]
    browser, (lo, hi) = random.choice(browser_choices)
    version = random.randint(lo, hi)
    return f"{browser}/{version}.0"


def gen_random_ua() -> str:
    """生成一个随机的UA"""
    os_str, browser = gen_random_os(), gen_random_browser()
    browser_name, _ = browser.split("/", 1)
    if browser_name == "Safari":
        version = browser.split("/")[1]
        # Safari 使用独立的 UA 格式
        ua = f"Mozilla/5.0 ({os_str}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{version} Safari/605.1.15"
    else:
        ua = f"Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) {browser} Safari/537.36"
    return ua
