import asyncio
from collections.abc import Iterator

from loguru import logger

from coocan.url import Request, Response


class IgnoreRequest(Exception):
    pass


class MiniSpider:
    start_urls = []
    max_requests = 5
    max_retry_times = 3

    def start_requests(self):
        """初始请求"""
        assert self.start_urls, "没有起始 URL 列表"
        for url in self.start_urls:
            yield Request(url, self.parse)

    def middleware(self, request: Request):
        request.headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0")

    async def get_response(self, request: Request):
        """发送请求，获取响应"""
        self.middleware(request)
        response = await request.send()
        return response

    def parse(self, response: Response):
        raise NotImplementedError("没有定义回调函数 {}.parse ".format(self.__class__.__name__))

    def when_request_error(self, e: Exception, request: Request):
        logger.error("{} {}".format(type(e).__name__, request.url))

    async def worker(self, queue, semaphore):
        """工作协程，从队列中获取请求并处理"""
        while True:
            request = await queue.get()

            # 结束信号
            if request is None:
                break

            # 控制并发
            async with semaphore:
                for i in range(self.max_retry_times + 1):
                    if i > 0:
                        logger.debug("正在重试第{}次...{}".format(i, request.url))
                    try:
                        response = await self.get_response(request)
                        cached = request.callback(Response(response), **request.cb_kwargs)
                        if isinstance(cached, Iterator):
                            for next_request in cached:
                                await queue.put(next_request)  # 将后续请求加入队列
                    except Exception as e:
                        try:
                            result = self.when_request_error(e, request)
                            if isinstance(result, Request):
                                await queue.put(result)
                                logger.debug("新的请求 {}".format(result.url))
                        except IgnoreRequest as e:
                            logger.debug("{} 忽略请求 {}".format(e, request.url))
                            break
                    else:
                        break
            queue.task_done()

    async def run(self):
        """爬取入口"""
        queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(self.max_requests)

        # 工作协程启动...
        workers = [
            asyncio.create_task(self.worker(queue, semaphore))
            for _ in range(self.max_requests)
        ]

        # 将初始请求加入队列
        for req in self.start_requests():
            await queue.put(req)

        # 等待队列中的所有任务完成
        await queue.join()

        # ...停止工作协程
        for _ in range(self.max_requests):
            await queue.put(None)

        # 等待所有工作协程完成
        await asyncio.gather(*workers)

    def go(self):
        asyncio.run(self.run())
