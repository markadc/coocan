import json

from loguru import logger

from coocan import Request, MiniSpider


class CSDNSpider(MiniSpider):
    start_urls = ['http://www.csdn.net']
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
            print(date, detail_url, name)
        print("第 {} 页抓取成功".format(params["page"]))

        # 抓取下一页
        next_page = int(current_page) + 1
        params["page"] = str(next_page)
        yield Request(api, self.parse_page, params=params, cb_kwargs={"api": api, "params": params})


if __name__ == '__main__':
    s = CSDNSpider()
    s.go()
