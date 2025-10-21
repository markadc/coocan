<div align="center">

# Coocan

**🚀 轻量级异步爬虫框架**

[![PyPI version](https://badge.fury.io/py/coocan.svg)](https://badge.fury.io/py/coocan)
[![Python Version](https://img.shields.io/pypi/pyversions/coocan.svg)](https://pypi.org/project/coocan/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[安装](#安装) •
[快速开始](#快速开始) •
[功能特性](#功能特性) •
[示例](#示例) •
[文档](#文档)

![Demo](demo.gif)

</div>

---

## 📖 简介

Coocan 是一个简洁、高效的 Python 异步爬虫框架，专为快速开发而设计。它基于 `httpx` 和 `asyncio`，提供了简单易用的 API，让你能够快速构建高性能的网络爬虫。

### ✨ 为什么选择 Coocan？

- **🪶 轻量级** - 核心代码简洁，依赖少，易于理解和扩展
- **⚡ 异步高效** - 基于 asyncio，充分利用异步 I/O 提升爬取效率
- **🎯 简单易用** - 类 Scrapy 的 API 设计，上手即用
- **🔧 功能完善** - 内置请求重试、优先级队列、代理支持、数据处理等功能
- **🎨 开箱即用** - 自带 XPath/CSS 选择器，随机 User-Agent，命令行工具等

---

## 📦 安装

### 使用 pip 安装

```bash
pip install -U coocan
```

### 要求

- Python >= 3.10

---

## 🚀 快速开始

### 1. 创建爬虫

使用命令行工具快速生成爬虫模板：

```bash
coocan new -s my_spider
```

![命令行工具](cmd.png)

### 2. 编写爬虫代码

```python
from coocan import MiniSpider, Request
from loguru import logger


class MySpider(MiniSpider):
    # 起始 URL 列表
    start_urls = ["https://example.com"]

    # 最大并发请求数
    max_requests = 10

    def parse(self, response):
        """解析响应"""
        # 使用 CSS 选择器提取数据
        titles = response.css('h1::text').getall()

        # 使用 XPath 提取数据
        links = response.xpath('//a/@href').getall()

        for title, link in zip(titles, links):
            logger.info(f"Title: {title}, Link: {link}")

            # 发起新请求
            yield Request(link, callback=self.parse_detail)

    def parse_detail(self, response):
        """解析详情页"""
        content = response.css('.content::text').get()
        logger.success(f"Content: {content}")


if __name__ == '__main__':
    spider = MySpider()
    spider.go()
```

### 3. 运行爬虫

```bash
python my_spider.py
```

---

## 🎯 功能特性

### 核心功能

| 功能           | 说明                            |
| -------------- | ------------------------------- |
| **异步请求**   | 基于 httpx 的异步 HTTP 客户端   |
| **智能重试**   | 自动重试失败的请求              |
| **优先级队列** | 支持请求优先级控制              |
| **代理支持**   | 轻松配置 HTTP/HTTPS 代理        |
| **请求延迟**   | 可配置请求间隔，避免被封        |
| **随机 UA**    | 自动随机 User-Agent             |
| **中间件**     | 支持请求预处理                  |
| **数据管道**   | `process_item` 方法处理爬取数据 |
| **异常处理**   | 完善的异常处理机制              |
| **选择器**     | 内置 XPath 和 CSS 选择器        |

### 类属性配置

```python
class MySpider(MiniSpider):
    start_urls = ["https://example.com"]  # 起始 URL
    max_requests = 20                      # 最大并发数
    max_retry_times = 3                    # 最大重试次数
    delay = 0                              # 请求延迟（秒）
    enable_random_ua = True                # 启用随机 User-Agent
    timeout = 6                            # 请求超时时间（秒）
```

---

## 📚 示例

### 示例 1：基础爬虫

```python
from coocan import MiniSpider
from loguru import logger


class BasicSpider(MiniSpider):
    start_urls = ["https://httpbin.org/get"]

    def parse(self, response):
        data = response.json()
        logger.info(f"Your IP: {data.get('origin')}")


if __name__ == '__main__':
    BasicSpider().go()
```

### 示例 2：使用代理

```python
from coocan import MiniSpider, Request


class ProxySpider(MiniSpider):
    def start_requests(self):
        yield Request(
            url="https://httpbin.org/ip",
            callback=self.parse,
            proxy="http://proxy.example.com:8080"
        )

    def parse(self, response):
        print(response.text)
```

更多示例请查看 [`_examples/`](_examples/) 目录：

- `crawl_csdn_list.py` - 爬取 CSDN 文章列表
- `crawl_csdn_detail.py` - 爬取 CSDN 文章详情
- `recv_item.py` - 数据处理示例
- `use_proxy.py` - 代理使用示例
- `view_local_ip.py` - 查看本机 IP

### 示例 3：完整的 CSDN 爬虫

```python
import json
from loguru import logger
from coocan import Request, MiniSpider


class CSDNSpider(MiniSpider):
    start_urls = ["http://www.csdn.net"]
    max_requests = 10

    def middleware(self, request: Request):
        """请求中间件"""
        request.headers["Referer"] = "http://www.csdn.net/"

    def parse(self, response):
        """解析首页"""
        api = "https://blog.csdn.net/community/home-api/v1/get-business-list"
        params = {
            "page": "1",
            "size": "20",
            "businessType": "lately",
            "noMore": "false",
            "username": "markadc"
        }
        yield Request(
            api,
            self.parse_page,
            params=params,
            cb_kwargs={"api": api, "params": params}
        )

    def parse_page(self, response, api, params):
        """解析列表页"""
        current_page = params["page"]
        data = json.loads(response.text)
        articles = data["data"]["list"]

        if not articles:
            logger.warning(f"没有第 {current_page} 页")
            return

        for article in articles:
            date = article["formatTime"]
            title = article["title"]
            url = article["url"]

            logger.info(f"{date} - {title}\n{url}")

            # 爬取详情页
            yield Request(url, self.parse_detail, cb_kwargs={"title": title})

        logger.info(f"第 {current_page} 页抓取成功")

        # 抓取下一页
        next_page = int(current_page) + 1
        params["page"] = str(next_page)
        yield Request(api, self.parse_page, params=params, cb_kwargs={"api": api, "params": params})

    def parse_detail(self, response, title):
        """解析详情页"""
        logger.success(f"{response.status_code} - 已访问 {title}")

    def process_item(self, item):
        """处理数据"""
        # 可以在这里保存到数据库或文件
        logger.debug(f"Processing: {item}")


if __name__ == '__main__':
    spider = CSDNSpider()
    spider.go()
```

---

## 📖 文档

### Request 对象

```python
Request(
    url: str,                    # 请求 URL
    callback=None,               # 回调函数
    method: str = "GET",         # 请求方法
    params: dict = None,         # URL 参数
    data: dict = None,           # POST 数据
    json: dict = None,           # JSON 数据
    headers: dict = None,        # 请求头
    cookies: dict = None,        # Cookies
    proxy: str = None,           # 代理地址
    timeout: int = 6,            # 超时时间
    priority: int = 0,           # 优先级（数字越大优先级越高）
    cb_kwargs: dict = None,      # 传递给回调函数的额外参数
    validator=None,              # 响应验证器
)
```

### Response 对象

```python
response.text           # 响应文本
response.content        # 响应字节
response.json()         # 解析 JSON
response.status_code    # 状态码
response.headers        # 响应头
response.url            # 请求 URL

# 选择器方法
response.xpath(query)   # XPath 选择器
response.css(query)     # CSS 选择器
```

### MiniSpider 主要方法

| 方法                                      | 说明                                      |
| ----------------------------------------- | ----------------------------------------- |
| `start_requests()`                        | 生成初始请求（可选，默认使用 start_urls） |
| `parse(response)`                         | 默认回调函数，解析响应                    |
| `middleware(request)`                     | 请求中间件，可修改请求                    |
| `process_item(item)`                      | 处理爬取的数据项                          |
| `handle_request_exception(request, exc)`  | 处理请求异常                              |
| `handle_callback_exception(request, exc)` | 处理回调函数异常                          |
| `go()`                                    | 启动爬虫                                  |

### 异常处理

```python
from coocan import MiniSpider, Request
from coocan.url.errs import IgnoreRequest, IgnoreResponse


class MySpider(MiniSpider):
    def handle_request_exception(self, request: Request, exc: Exception):
        """处理请求异常"""
        # 抛出 IgnoreRequest 表示放弃该请求
        raise IgnoreRequest("放弃请求")

        # 或返回新请求替代
        # return Request(new_url, callback=self.parse)

    def validator(self, response):
        """验证响应"""
        if response.status_code != 200:
            # 抛出 IgnoreResponse 跳过回调
            raise IgnoreResponse("状态码异常")

    def handle_callback_exception(self, request: Request, exc: Exception):
        """处理回调异常"""
        logger.error(f"回调异常: {exc}")
```

---

## 🛠️ 命令行工具

Coocan 提供了便捷的命令行工具：

```bash
# 创建新爬虫
coocan new -s spider_name

# 查看帮助
coocan --help
```

---

## 📝 更新日志

### v0.6.1 (2025-5-15)

- ✨ 请求支持代理，使用 `proxy` 参数
- ⚡ 请求的默认超时设置为 6 秒

### v0.5.0 (2025-4-28)

- ✨ 新增 `process_item` 方法，用于处理数据
  - 示例代码位于 `_examples/recv_item.py`

### v0.4.0 (2025-4-25)

- 🎉 实现 `coocan` 命令行工具
  - 支持 `coocan new -s <spider_file_name>` 创建爬虫

### v0.3.2 (2025-4-23)

- ✨ 可以设置请求延迟 (`delay` 属性)
- ✨ 默认启用随机 User-Agent (`enable_random_ua` 属性)

### v0.3.1 (2025-4-22)

- ✨ 请求支持优先级参数 (`priority`)

### v0.3.0 (2025-4-21)

- ✨ 请求异常时触发 `handle_request_exception`
  - 可抛出 `IgnoreRequest` 异常放弃请求
  - 可返回新的 `Request` 对象替代原请求
- ✨ 加入响应验证器 `validator`
  - 可抛出 `IgnoreResponse` 异常跳过回调
- ✨ 回调异常时触发 `handle_callback_exception`

### v0.2.0 (2025-4-18)

- ✨ 响应对象支持 `XPath` 和 `CSS` 选择器
- ✨ 加入请求重试机制
- ✨ 请求异常处理回调函数

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

---

## 📄 许可证

本项目采用 [MIT](https://opensource.org/licenses/MIT) 许可证。

---

## 👨‍💻 作者

**wauo** - [markadc@126.com](mailto:markadc@126.com)

项目主页: [https://github.com/markadc/coocan](https://github.com/markadc/coocan)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！**

</div>
