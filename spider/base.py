import asyncio
import hashlib
import random
import signal
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
from loguru import logger

from coocan.gen import gen_random_ua
from coocan.url import Request, Response, close_client, get_client


class IgnoreRequest(Exception):
    """忽略这个请求，不再重试"""

    pass


class IgnoreResponse(Exception):
    """忽略这个响应，不进回调"""

    pass


@dataclass
class Stats:
    """爬取统计信息"""

    start_time: float = field(default_factory=time.time)
    request_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    retry_count: int = 0
    item_count: int = 0

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def __str__(self):
        return (
            f"请求: {self.request_count} | "
            f"成功: {self.success_count} | "
            f"失败: {self.failed_count} | "
            f"重试: {self.retry_count} | "
            f"数据: {self.item_count} | "
            f"耗时: {self.elapsed:.2f}s"
        )


class MiniSpider:
    start_urls = []
    max_requests = 5
    max_retry_times = 3
    enable_random_ua = True
    headers_extra_field = None
    delay: int | tuple[float, float] = 0  # 支持固定延迟或随机延迟范围
    item_speed = 100
    enable_duplicate_filter = False  # 是否启用 URL 去重
    worker_count = None  # 请求处理协程数，None 则自动计算为 max_requests * 2
    client_limits = None  # httpx.Limits，控制连接池

    def __init__(self):
        self.stats = Stats()
        self._seen_urls: set[str] = set()
        self._stop_event: asyncio.Event | None = None
        self._clients: dict[str | None, httpx.AsyncClient] = {}

    def _get_url_fingerprint(self, request: Request) -> str:
        """生成 URL 指纹用于去重"""
        return hashlib.md5(request.url.encode()).hexdigest()

    def _is_duplicate(self, request: Request) -> bool:
        """检查请求是否重复"""
        if not self.enable_duplicate_filter:
            return False
        fp = self._get_url_fingerprint(request)
        if fp in self._seen_urls:
            return True
        self._seen_urls.add(fp)
        return False

    def _get_delay(self) -> float:
        """获取延迟时间"""
        if isinstance(self.delay, tuple):
            return random.uniform(self.delay[0], self.delay[1])
        return self.delay

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

    def _get_client_for_request(self, request: Request) -> httpx.AsyncClient:
        """根据请求的 proxy 获取或创建对应的 httpx 客户端"""
        proxy = request.proxy
        if proxy not in self._clients:
            client_kwargs = {"timeout": 10.0}
            if self.client_limits is not None:
                client_kwargs["limits"] = self.client_limits
            if proxy is None:
                self._clients[proxy] = get_client(limits=self.client_limits)
            else:
                client_kwargs["proxy"] = proxy
                self._clients[proxy] = httpx.AsyncClient(**client_kwargs)
        return self._clients[proxy]

    def validator(self, response: Response):
        """校验响应"""
        pass

    def parse(self, response: Response):
        """默认回调函数"""
        raise NotImplementedError("没有定义回调函数 {}.parse ".format(self.__class__.__name__))

    def handle_request_exception(self, e: Exception, request: Request):
        """处理请求时的异常"""
        logger.error("{} {}".format(type(e).__name__, request.url))

    def handle_callback_exception(self, e: Exception, request: Request, response: Response):
        logger.error("{} `回调`时出现异常 | {} | {} | {}".format(response.status_code, e, request.callback.__name__, request.url))

    def spider_opened(self):
        """爬虫启动时调用"""
        pass

    def spider_closed(self):
        """爬虫结束时调用"""
        pass

    async def request_task(self, q1: asyncio.PriorityQueue, q2: asyncio.Queue, semaphore: asyncio.Semaphore):
        """工作协程，从队列中获取请求并处理"""
        while True:
            try:
                req: Request = await asyncio.wait_for(q1.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if self._stop_event.is_set():
                    break
                continue

            # 结束信号
            if req.url == "":
                break

            # URL 去重
            if self._is_duplicate(req):
                logger.debug(f"跳过重复请求: {req.url}")
                q1.task_done()
                continue

            self.stats.request_count += 1

            # 控制并发
            async with semaphore:
                for i in range(self.max_retry_times + 1):
                    if self._stop_event.is_set():
                        break

                    # 进入了重试
                    if i > 0:
                        self.stats.retry_count += 1
                        logger.debug("正在重试第{}次... {}".format(i, req.url))

                    # 开始请求...
                    try:
                        self.middleware(req)
                        delay = self._get_delay()
                        if delay > 0:
                            await asyncio.sleep(delay)
                        client = self._get_client_for_request(req)
                        resp = await req.send(client)

                    # 请求失败
                    except Exception as e:
                        try:
                            result = self.handle_request_exception(e, req)
                            if isinstance(result, Request):
                                await q1.put(result)
                                break
                        except IgnoreRequest as e:
                            logger.debug("{} 忽略请求 {}".format(e, req.url))
                            break
                        except Exception as e:
                            logger.error("`处理异常函数`异常了 | {} | {}".format(e, req.url))

                        # 最后一次重试也失败了
                        if i == self.max_retry_times:
                            self.stats.failed_count += 1

                    # 请求成功
                    else:
                        self.stats.success_count += 1

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
                                        logger.warning(f"Please yield `Request` or `dict` Not {repr(c)}")
                        except Exception as e:
                            self.handle_callback_exception(e, req, resp)
                        finally:
                            break

            q1.task_done()

    async def item_task(self, q2: asyncio.Queue):
        while True:
            try:
                item = await asyncio.wait_for(q2.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if self._stop_event.is_set():
                    break
                continue

            if item is None:
                break
            self.stats.item_count += 1
            if asyncio.iscoroutinefunction(self.process_item):
                await self.process_item(item)
            else:
                self.process_item(item)
            q2.task_done()

    def process_item(self, item: dict):
        logger.success(item)

    async def run(self):
        """爬取入口"""
        self._stop_event = asyncio.Event()
        self.spider_opened()
        logger.info(f"爬虫 {self.__class__.__name__} 启动")

        request_queue = asyncio.PriorityQueue()
        item_queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(self.max_requests)

        # 请求处理协程数与并发数解耦
        worker_count = self.worker_count or self.max_requests * 2

        # 处理请求...
        request_tasks = [asyncio.create_task(self.request_task(request_queue, item_queue, semaphore)) for _ in range(worker_count)]

        # 处理数据...
        item_tasks = [asyncio.create_task(self.item_task(item_queue)) for _ in range(self.item_speed)]

        # 发送最开始的请求
        for req in self.start_requests():
            await request_queue.put(req)

        try:
            # 等待所有请求处理完成
            await request_queue.join()
            logger.debug("处理请求已结束")

            # 等待所有数据处理完成
            await item_queue.join()
            logger.debug("处理数据已结束")
        except asyncio.CancelledError:
            logger.warning("爬虫被取消")

        # 退出请求任务
        for _ in range(worker_count):
            await request_queue.put(Request(url=""))

        # 退出数据任务
        for _ in range(self.item_speed):
            await item_queue.put(None)

        # 等待所有工作协程完成
        await asyncio.gather(*request_tasks)
        await asyncio.gather(*item_tasks)

        # 关闭所有 HTTP 客户端
        await self._close_all_clients()

        self.spider_closed()
        logger.info(f"爬虫 {self.__class__.__name__} 结束 | {self.stats}")

    async def _close_all_clients(self):
        """关闭所有缓存的 HTTP 客户端"""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
        await close_client()

    def _handle_sigint(self, signum, frame):
        """处理 Ctrl+C 信号"""
        logger.warning("收到中断信号，正在优雅退出...")
        self._stop_event.set()

    def go(self):
        # 注册信号处理器
        original_handler = signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.warning("爬虫被强制中断")
        finally:
            # 恢复原始信号处理器
            signal.signal(signal.SIGINT, original_handler)
