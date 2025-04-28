from coocan import Request, Response, MiniSpider


class ViewLocalIPSpider(MiniSpider):
    start_urls = ["https://httpbin.org/ip"]
    max_requests = 5
    delay = 5

    def start_requests(self):
        for _ in range(10):
            yield Request(self.start_urls[0], callback=self.parse)

    def middleware(self, request: Request):
        request.headers["Referer"] = "https://httpbin.org"

    def parse(self, response: Response):
        print(response.status_code, response.json())


if __name__ == '__main__':
    s = ViewLocalIPSpider()
    s.go()
