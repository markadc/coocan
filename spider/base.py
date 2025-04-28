import asyncio
from collections.abc import Iterator

from loguru import logger

from coocan.gen import gen_random_ua
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
    enable_random_ua = True
    headers_extra_field = {}
    delay = 0
    item_speed = 100

    def start_requests(self):
        """初始请求"""
        assert self.start_urls, "没有起始 URL 列表"
        for url in self.start_urls:
            yield Request(url, self.parse)

    def middleware(self, request: Request):
        # 随机Ua
        if self.enable_random_ua is True:
            request.headers.setdefault("User-Agent", gen_random_ua())

        # 为 headers 补充额外字段
        if self.headers_extra_field:
            request.headers.update(self.headers_extra_field)

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

    async def request_task(self, q1: asyncio.PriorityQueue, q2: asyncio.Queue, semaphore: asyncio.Semaphore):
        """工作协程，从队列中获取请求并处理"""
        while True:
            req: Request = await q1.get()

            # 结束信号
            if req.url == "":
                break

            # 控制并发
            async with semaphore:
                for i in range(self.max_retry_times + 1):
                    # 进入了重试
                    if i > 0:
                        logger.debug("正在重试第{}次... {}".format(i, req.url))

                    # 开始请求...
                    try:
                        self.middleware(req)
                        await asyncio.sleep(self.delay)
                        resp = await req.send()

                    # 请求失败
                    except Exception as e:
                        try:
                            result = self.handle_request_excetpion(e, req)
                            if isinstance(result, Request):
                                await q1.put(result)
                                break
                        except IgnoreRequest as e:
                            logger.debug("{} 忽略请求 {}".format(e, req.url))
                            break
                        except Exception as e:
                            logger.error("`处理异常函数`异常了 | {} | {}".format(e, req.url))

                    # 请求成功
                    else:
                        # 校验响应
                        try:
                            self.validator(resp)
                        except IgnoreResponse as e:
                            logger.debug("{} 忽略响应 {}".format(e, req.url))
                            break
                        except Exception as e:
                            logger.error("`校验器`函数异常了 | {} | {}".format(e, req.url))

                        # 进入回调
                        try:
                            cached = req.callback(Response(resp), **req.cb_kwargs)
                            if isinstance(cached, Iterator):
                                for c in cached:
                                    if isinstance(c, Request):
                                        await q1.put(c)  # 把后续请求加入队列
                                    elif isinstance(c, dict):
                                        await q2.put(c)
                                    else:
                                        logger.warning("Please yield `Request` or `dict` Not {}".format(c))
                        except Exception as e:
                            self.handle_callback_excetpion(e, req, resp)
                        finally:
                            break

            q1.task_done()

    async def item_task(self, q2: asyncio.Queue):
        while True:
            item = await q2.get()
            if item is None:
                break
            self.process_item(item)
            q2.task_done()

    def process_item(self, item: dict):
        logger.success(item)

    async def run(self):
        """爬取入口"""
        request_queue = asyncio.PriorityQueue()
        item_queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(self.max_requests)

        # 处理请求...
        request_tasks = [
            asyncio.create_task(self.request_task(request_queue, item_queue, semaphore))
            for _ in range(self.max_requests)
        ]

        # 处理数据...
        item_tasks = [
            asyncio.create_task(self.item_task(item_queue))
            for _ in range(self.item_speed)
        ]

        # 发送最开始的请求
        for req in self.start_requests():
            await request_queue.put(req)

        # 等待所有请求处理完成
        await request_queue.join()
        logger.debug("处理请求已结束")

        # 等待所有数据处理完成
        await item_queue.join()
        logger.debug("处理数据已结束")

        # 退出请求任务
        for _ in range(self.max_requests):
            await request_queue.put(Request(url=""))

        # 退出数据任务
        for _ in range(self.item_speed):
            await item_queue.put(None)

        # 等待所有工作协程完成
        await asyncio.gather(*request_tasks)
        await asyncio.gather(*item_tasks)

    def go(self):
        asyncio.run(self.run())
