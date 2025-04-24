from coocan import Request, Response, MiniSpider


class Spider(MiniSpider):
    start_urls = ['https://github.com/markadc/coocan']
    max_requests = 10

    def middleware(self, request: Request):
        request.headers["Referer"] = "https://github.com"

    def parse(self, response: Response):
        pass
