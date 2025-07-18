import random
import time

from loguru import logger

from coocan import MiniSpider, Request, Response


class RecvItemSpider(MiniSpider):
    start_urls = ["https://cn.bing.com/search?q=1"]
    max_requests = 10

    def parse(self, response: Response):
        logger.warning(
            f"{response.status_code} {response.request.url} {response.get_one('//title/text()')}"
        )
        for _ in range(10):
            item = {
                "timestamp": int(time.time() * 1000),
                "mark": random.randint(1, 10000),
            }
            yield item  # 这里是模拟爬取的数据

        head, tail = str(response.request.url).split("=")
        next_url = "{}={}".format(head, int(tail) + 1)
        if next_url.endswith("11"):
            yield "xxx"  # 出现警告日志（只能 yield request对象 或者 dict对象）
            return
        yield Request(next_url, callback=self.parse)

    def process_item(self, item: dict):
        logger.success("Get => {}".format(item))


if __name__ == "__main__":
    s = RecvItemSpider()
    s.go()
