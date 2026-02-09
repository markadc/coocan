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
        ("Chrome", random.randint(110, 130)),
        ("Firefox", random.randint(110, 125)),
        ("Edge", random.randint(110, 130)),
        ("Safari", random.randint(15, 17)),
    ]
    browser, version = random.choice(browser_choices)
    return f"{browser}/{version}.0"


def gen_random_ua() -> str:
    """生成一个随机的UA"""
    os, browser = gen_random_os(), gen_random_browser()
    ua = f"Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) {browser} Safari/537.36"
    return ua
