import asyncio
from collections.abc import Iterator

from loguru import logger

from coocan.url import Request, Response


class IgnoreRequest(Exception):
    """忽略这个请求，不再重试"""
    pass


class IgnoreResponse(Exception):
    """忽略这个响应，不进回调"""
    pass


class MiniSpider:
    start_urls = []
    max_requests = 5
    max_retry_times = 3
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"

    def start_requests(self):
        """初始请求"""
        assert self.start_urls, "没有起始 URL 列表"
        for url in self.start_urls:
            yield Request(url, self.parse)

    def middleware(self, request: Request):
        """默认只设置Ua"""
        request.headers.setdefault("User-Agent", self.default_ua)

    def validator(self, response: Response):
        """校验响应"""
        pass

    def parse(self, response: Response):
        """默认回调函数"""
        raise NotImplementedError("没有定义回调函数 {}.parse ".format(self.__class__.__name__))

    def handle_request_excetpion(self, e: Exception, request: Request):
        """处理请求时的异常"""
        logger.error("{} {}".format(type(e).__name__, request.url))

    def handle_callback_excetpion(self, e: Exception, request: Request, response: Response):
        logger.error("{} `回调`时出现异常 | {} | {} | {}".format(response.status_code, e, request.callback.__name__, request.url))

    async def worker(self, queue, semaphore):
        """工作协程，从队列中获取请求并处理"""
        while True:
            request: Request = await queue.get()

            # 结束信号
            if request is None:
                break

            # 控制并发
            async with semaphore:
                for i in range(self.max_retry_times + 1):
                    # 进入了重试
                    if i > 0:
                        logger.debug("正在重试第{}次... {}".format(i, request.url))

                    # 开始请求...
                    try:
                        self.middleware(request)
                        response = await request.send()

                    # 请求失败
                    except Exception as e:
                        try:
                            result = self.handle_request_excetpion(e, request)
                            if isinstance(result, Request):
                                await queue.put(result)
                                break
                        except IgnoreRequest as e:
                            logger.debug("{} 忽略请求 {}".format(e, request.url))
                            break
                        except Exception as e:
                            logger.error("`处理异常函数`异常了 | {} | {}".format(e, request.url))

                    # 请求成功
                    else:
                        # 校验响应
                        try:
                            self.validator(response)
                        except IgnoreResponse as e:
                            logger.debug("{} 忽略响应 {}".format(e, request.url))
                            break
                        except Exception as e:
                            logger.error("`校验器`函数异常了 | {} | {}".format(e, request.url))

                        # 进入回调
                        try:
                            cached = request.callback(Response(response), **request.cb_kwargs)
                            if isinstance(cached, Iterator):
                                for next_request in cached:
                                    await queue.put(next_request)  # 把后续请求加入队列
                        except Exception as e:
                            self.handle_callback_excetpion(e, request, response)
                        finally:
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
