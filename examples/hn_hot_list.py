import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rich import print as rprint
from coocan import MiniSpider, Request, Response


class HnHotListSpider(MiniSpider):
    """爬取 HackerNews 中文版 24小时热榜（多页）"""

    max_concurrency = 2
    delay = 1
    enable_random_ua = True

    def start_requests(self):
        yield Request(
            "https://hn.aimaker.dev/category/top?page=1",
            callback=self.parse,
            cb_kwargs={"page": 1},
        )

    def parse(self, response: Response, page: int):
        articles = response.xpath("//article")
        if not articles:
            return

        for article in articles:
            title = article.xpath('string(.//a[contains(@class, "flex-1")])').get("").strip()
            title = " ".join(title.split())
            url = article.xpath('.//a[contains(@class, "flex-1")]/@href').get("").strip()
            time_str = article.xpath('string(.//span[contains(text(), "小时前") or contains(text(), "分钟前")])').get("").strip()
            time_str = " ".join(time_str.split())

            if title and time_str:
                yield {"title": title, "url": url, "time": time_str, "page": page}

        # 下一页
        if page < 5:  # 最多爬取前5页
            rprint(f"[blue]第 {page} 页完成，正在请求第 {page + 1} 页[/blue]")
            time.sleep(1)  # 模拟人类浏览习惯，适当等待一下
            yield Request(
                f"https://hn.aimaker.dev/category/top?page={page + 1}",
                callback=self.parse,
                cb_kwargs={"page": page + 1},
            )

    def process_item(self, item: dict):
        rprint(f"[bold yellow]{item['title']}[/bold yellow]")
        rprint(f"[dim cyan]{item['url']}[/dim cyan]")
        rprint(f"[red]{item['time']}[/red]")
        rprint()


if __name__ == "__main__":
    spider = HnHotListSpider()
    spider.go()
