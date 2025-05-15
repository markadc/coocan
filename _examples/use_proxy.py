from coocan import Request, Response, MiniSpider


class UseProxySpider(MiniSpider):
    start_urls = ["https://httpbin.org/ip"]
    max_requests = 5
    delay = 5

    def start_requests(self):
        proxy = "http://127.0.0.1:1082"
        yield Request(self.start_urls[0], callback=self.parse, proxy=proxy)

    def middleware(self, request: Request):
        request.headers["Referer"] = "https://httpbin.org"

    def parse(self, response: Response):
        print(response.status_code, response.json())


if __name__ == '__main__':
    s = UseProxySpider()
    s.go()
