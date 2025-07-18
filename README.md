# 项目说明

- 一个非常轻量的异步爬虫框架

## 安装

`pip install -U coocan`

# 新建一个爬虫

## 命令

`coocan new -s <spider_file_name>`

![alt text](cmd.png)

# 更新记录

### 2025-5-15

- 请求支持代理，使用`proxy`参数
- 请求的默认超时为 6 秒

### 2025-4-28

- 新增 `process_item` 方法，用来处理数据
  - 示例位于 coocan/\_examples/recv_item

### 2025-4-25

- 实现 `coocan` 命令行工具
  - 在当前目录下新建一个爬虫
    - coocan new -s <spider_file_name>

### 2025-4-23

- 可以设置请求延迟（如果你想放慢爬虫速度的话）
  - delay
- 默认启动随机 Ua
  - enable_random_ua

### 2025-4-22

- 请求可以指定优先级（priority）

### 2025-4-21

- 请求异常时触发 `handle_request_excetpion`
  - 若抛出 `IgnoreRequest` 异常，表示抛弃这个请求（不再重试）
  - 若返回了新的 `Request` 则表示旧请求丢弃，新请求进入请求队列
- 加入校验器 `validator`（用来提前检查响应内容，可以选择不进入回调函数）
  - 若抛出 `IgnoreResponse` 异常，则不进入回调函数
- `callback` 异常时触发 `handle_callback_excetpion`

### 2025-4-18

- 响应对象自带`Xpath`、`CSS`解析
- 加入请求重试机制、请求异常时可以使用回调函数 `handle_request_excetpion`

# 简单演示

- 效果
  <br>
  ![效果](demo.gif)

- 代码

```python
import json

from loguru import logger

import coocan
from coocan import Request, MiniSpider


class CSDNDetailSpider(MiniSpider):
    start_urls = ["http://www.csdn.net"]
    max_requests = 10

    def middleware(self, request: Request):
        request.headers["Referer"] = "http://www.csdn.net/"

    def parse(self, response):
        api = "https://blog.csdn.net/community/home-api/v1/get-business-list"
        params = {
            "page": "1",
            "size": "20",
            "businessType": "lately",
            "noMore": "false",
            "username": "markadc"
        }
        yield Request(api, self.parse_page, params=params, cb_kwargs={"api": api, "params": params})

    def parse_page(self, response, api, params):
        current_page = params["page"]
        data = json.loads(response.text)
        some = data["data"]["list"]

        if not some:
            logger.warning("没有第 {} 页".format(current_page))
            return

        for one in some:
            date = one["formatTime"]
            name = one["title"]
            detail_url = one["url"]
            logger.info(
                """
                {}
                {}
                {}
                """.format(date, name, detail_url)
            )
            yield coocan.Request(detail_url, self.parse_detail, cb_kwargs={"title": name})

        logger.info("第 {} 页抓取成功".format(params["page"]))

        # 抓取下一页
        next_page = int(current_page) + 1
        params["page"] = str(next_page)
        yield Request(api, self.parse_page, params=params, cb_kwargs={"api": api, "params": params})

    def parse_detail(self, response, title):
        logger.success("{}  已访问 {}".format(response.status_code, title))


if __name__ == '__main__':
    s = CSDNDetailSpider()
    s.go()
```
