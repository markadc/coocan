import asyncio
import hashlib
import inspect
import json
import random
import signal
import time
from collections.abc import AsyncIterator, Iterable, Iterator
from dataclasses import dataclass, field

import httpx
from loguru import logger

from coocan.gen import gen_random_ua
from coocan.url import Request, Response, close_client, get_client

_REQUEST_SENTINEL = Request(url="__sentinel__", priority=float("inf"))
_ITEM_SENTINEL = object()


class IgnoreRequest(Exception):
    """抛出此异常将忽略当前请求，不再重试。"""

    pass


class IgnoreResponse(Exception):
    """抛出此异常将忽略当前响应，不进入回调。"""

    pass


@dataclass
class Stats:
    """爬取统计信息，由 MiniSpider 自动维护。

    通过 ``spider.stats`` 访问。

    Attributes:
        start_time: 爬虫启动时间戳。
        request_count: 已发送的请求总数。
        success_count: 成功的请求数。
        failed_count: 最终失败的请求数。
        retry_count: 重试次数。
        replaced_count: 被 handle_request_exception 替换的请求数。
        item_count: 收到的数据条目数。
        elapsed: 爬虫已运行秒数（只读属性）。
    """

    start_time: float = field(default_factory=time.time)
    request_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    retry_count: int = 0
    replaced_count: int = 0
    item_count: int = 0

    @property
    def elapsed(self) -> float:
        """爬虫已运行时间（秒）。"""
        return time.time() - self.start_time

    def __str__(self):
        return f"请求: {self.request_count} | " f"成功: {self.success_count} | " f"失败: {self.failed_count} | " f"重试: {self.retry_count} | " f"数据: {self.item_count} | " f"耗时: {self.elapsed:.2f}s"


class MiniSpider:
    """轻量级异步爬虫基类，继承并实现回调即可使用。

    核心设计：

    - 基于 asyncio.PriorityQueue 的优先级调度（priority 越小越先执行）
    - 信号量控制并发数（max_concurrency）
    - 内置重试 + 指数退避
    - 可选的 URL 去重
    - 为每个 proxy 创建独立 httpx 客户端并缓存

    Attributes:
        start_urls: 初始 URL 列表。
        max_concurrency: 并发请求数（信号量大小），默认 5。
        max_retry_times: 最大重试次数，默认 3。
        retry_backoff_base: 重试退避基础秒数，0 禁用，默认 1.0。
        retry_backoff_max: 重试退避上限秒数，默认 30.0。
        delay: 请求间隔，固定值或 ``(min, max)`` 随机范围。
        enable_random_ua: 自动添加随机 User-Agent，默认 True。
        enable_duplicate_filter: 启用 URL 去重（MD5），默认 False。
        headers_extra_field: 额外请求头 dict。
        worker_count: 请求处理协程数，None 则自动计算为 max_concurrency * 2。
        item_speed: 数据处理协程数，默认 100。
        client_limits: httpx.Limits 控制连接池大小。

    可覆盖的钩子方法：

    - ``start_requests()`` — 初始请求生成器
    - ``middleware(request)`` — 请求发送前（添加 UA、headers 等）
    - ``validator(response)`` — 响应校验（抛 IgnoreResponse 跳过）
    - ``parse(response)`` — 默认回调（必须实现）
    - ``process_item(item)`` — 处理 yield 出来的 dict
    - ``handle_request_exception(e, request)`` — 请求异常处理（可返回新 Request 替换）
    - ``handle_callback_exception(e, request, response)`` — 回调异常处理
    - ``spider_opened()`` / ``spider_closed()`` — 生命周期钩子

    Examples:
        最小示例::

            from coocan import MiniSpider, Response

            class MySpider(MiniSpider):
                start_urls = ["https://example.com"]
                max_concurrency = 5

                def parse(self, response: Response):
                    title = response.get_one("//title/text()")
                    yield {"title": title}

            if __name__ == "__main__":
                MySpider().go()
    """

    start_urls = []
    max_concurrency = 5
    max_retry_times = 3
    retry_backoff_base: float = 1.0  # 重试退避基础秒数，0 禁用
    retry_backoff_max: float = 30.0
    enable_random_ua = True
    headers_extra_field = None
    delay: int | tuple[float, float] = 0  # 支持固定延迟或随机延迟范围
    item_speed = 10
    enable_duplicate_filter = False  # 是否启用 URL 去重
    worker_count = None  # 请求处理协程数，None 则自动计算为 max_concurrency * 2
    client_limits = None  # httpx.Limits，控制连接池

    def __init__(self):
        self.stats = Stats()
        self._seen_urls: set[str] = set()
        self._stop_event: asyncio.Event | None = None
        self._main_task: asyncio.Task | None = None
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._process_is_async: bool | None = None

    @staticmethod
    def _stable_repr(obj) -> str:
        """对常见请求参数进行稳定序列化，确保相同内容产生相同字符串。"""
        if obj is None:
            return ""
        try:
            return json.dumps(obj, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return repr(obj)

    def _get_url_fingerprint(self, request: Request) -> str:
        """生成请求指纹（MD5）用于去重，包含 method/url/params/body/cookies/proxy。"""
        canonical = "{}:{}:{}:{}:{}".format(
            request._get_method(),
            request.url,
            self._stable_repr(request.params),
            self._stable_repr(request.data),
            self._stable_repr(request.json),
        )
        if request.cookies:
            canonical += f":cookies:{self._stable_repr(request.cookies)}"
        if request.proxy:
            canonical += f":proxy:{request.proxy}"
        return hashlib.md5(canonical.encode()).hexdigest()

    def _is_duplicate(self, request: Request) -> bool:
        """检查请求是否重复。

        Returns:
            True 表示重复（应跳过）。
        """
        if not self.enable_duplicate_filter:
            return False
        fp = self._get_url_fingerprint(request)
        if fp in self._seen_urls:
            return True
        self._seen_urls.add(fp)
        return False

    def _get_delay(self) -> float:
        """获取延迟时间，支持固定值或随机范围。"""
        if isinstance(self.delay, tuple):
            return random.uniform(self.delay[0], self.delay[1])
        return self.delay

    def start_requests(self) -> Iterator[Request]:
        """生成初始请求，子类可覆盖以自定义初始逻辑。

        默认从 ``start_urls`` 生成，回调指向 ``self.parse``。

        Yields:
            Request 对象。
        """
        assert self.start_urls, "没有起始 URL 列表"
        for url in self.start_urls:
            yield Request(url, self.parse)

    def middleware(self, request: Request) -> None:
        """请求发送前的中间件，可在此修改请求（添加 UA、headers 等）。

        子类覆盖时注意调用 ``super().middleware(request)`` 或自行处理。

        Args:
            request: 即将发送的 Request 对象。
        """
        if self.enable_random_ua is True:
            request.headers.setdefault("User-Agent", gen_random_ua())

        if self.headers_extra_field:
            request.headers.update(self.headers_extra_field)

    def _get_client_for_request(self, request: Request) -> httpx.AsyncClient:
        """根据请求的 proxy 获取或创建对应的 httpx 客户端。

        无代理时复用全局客户端，有代理时为每个代理创建独立客户端并缓存。

        Args:
            request: 请求对象。

        Returns:
            适合该请求的 httpx.AsyncClient。
        """
        proxy = request.proxy
        if proxy is None:
            return get_client(limits=self.client_limits)
        if proxy not in self._clients:
            client_kwargs = {"timeout": 10.0}
            if self.client_limits is not None:
                client_kwargs["limits"] = self.client_limits
            client_kwargs["proxy"] = proxy
            self._clients[proxy] = httpx.AsyncClient(**client_kwargs)
        return self._clients[proxy]

    def validator(self, response: Response) -> None:
        """响应校验钩子。

        抛出 IgnoreResponse 跳过此响应不进入回调。

        Args:
            response: SelectorResponse 对象。
        """

    def parse(self, response: Response) -> Iterator[Request | dict] | None:
        """默认回调函数，子类必须实现。

        Args:
            response: SelectorResponse 对象。

        Raises:
            NotImplementedError: 子类未实现。
        """
        raise NotImplementedError("没有定义回调函数 {}.parse ".format(self.__class__.__name__))

    def handle_request_exception(self, e: Exception, request: Request) -> Request | None:
        """请求异常处理钩子。

        返回一个新的 Request 对象可替换当前请求继续执行；
        抛出 IgnoreRequest 则不再重试直接丢弃。

        Args:
            e: 捕获的异常。
            request: 发送失败的请求。

        Returns:
            （可选）一个新的 Request 对象用于替换。
        """
        logger.error("{} {}".format(type(e).__name__, request.url))

    def handle_callback_exception(self, e: Exception, request: Request, response: Response) -> None:
        """回调异常处理钩子，默认只记录日志。

        Args:
            e: 捕获的异常。
            request: 触发回调的请求。
            response: 响应对象。
        """
        callback_name = getattr(request.callback, "__name__", None) or self.parse.__name__
        logger.error("{} `回调`时出现异常 | {} | {} | {}".format(response.status_code, e, callback_name, request.url))

    def spider_opened(self) -> None:
        """爬虫启动时调用（在 run() 开头、发送初始请求之前）。"""

    def spider_closed(self) -> None:
        """爬虫结束时调用（在所有 worker 退出、客户端关闭之后）。"""

    async def _handle_callback_result(self, result, q1: asyncio.PriorityQueue, q2: asyncio.Queue) -> None:
        """处理 callback 返回值，支持普通返回、同步迭代器、异步函数和异步迭代器。"""
        if inspect.isawaitable(result):
            result = await result

        if result is None:
            return

        if isinstance(result, AsyncIterator) or hasattr(result, "__aiter__"):
            async for c in result:
                await self._enqueue_callback_value(c, q1, q2)
            return

        if isinstance(result, dict) or isinstance(result, Request):
            await self._enqueue_callback_value(result, q1, q2)
            return

        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, bytearray)):
            for c in result:
                await self._enqueue_callback_value(c, q1, q2)
            return

        logger.warning(f"请返回或 yield `Request` / `dict`，而非 {repr(result)}")

    async def _enqueue_callback_value(self, value, q1: asyncio.PriorityQueue, q2: asyncio.Queue) -> None:
        """将 callback 产物放回请求队列或 item 队列。"""
        if isinstance(value, Request):
            await q1.put(value)
        elif isinstance(value, dict):
            await q2.put(value)
        elif value is not None:
            logger.warning(f"请 yield `Request` 或 `dict`，而非 {repr(value)}")

    async def request_task(self, q1: asyncio.PriorityQueue, q2: asyncio.Queue, semaphore: asyncio.Semaphore):
        """工作协程：从请求队列取 Request → 发送 → 校验 → 回调 → yield 新 Request/item。"""
        while True:
            try:
                req: Request = await q1.get()
            except asyncio.CancelledError:
                break

            # 结束信号
            if req is _REQUEST_SENTINEL:
                q1.task_done()
                break

            # URL 去重
            if self._is_duplicate(req):
                logger.debug(f"跳过重复请求: {req.url}")
                q1.task_done()
                continue

            self.stats.request_count += 1

            # middleware 只执行一次（在重试循环外）
            self.middleware(req)
            delay = self._get_delay()

            for i in range(self.max_retry_times + 1):
                if self._stop_event.is_set():
                    break

                # 进入了重试
                if i > 0:
                    self.stats.retry_count += 1
                    logger.debug("正在重试第{}次... {}".format(i, req.url))
                    if self.retry_backoff_base > 0:
                        backoff = min(
                            self.retry_backoff_base * (2 ** (i - 1)),
                            self.retry_backoff_max,
                        )
                        await asyncio.sleep(backoff)
                else:
                    # delay 只在首次请求时生效，重试时已有 backoff
                    if delay > 0:
                        await asyncio.sleep(delay)

                # 开始请求...
                try:
                    client = self._get_client_for_request(req)
                    # 信号量只包裹实际 HTTP 请求
                    async with semaphore:
                        resp = await req.send(client)

                # 请求失败
                except Exception as e:
                    try:
                        result = self.handle_request_exception(e, req)
                        if isinstance(result, Request):
                            self.stats.replaced_count += 1
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
                    wrapped = Response(resp)

                    # 校验响应（传入 SelectorResponse）
                    try:
                        self.validator(wrapped)
                    except IgnoreResponse as e:
                        logger.debug("{} 忽略响应 {}".format(e, req.url))
                        break
                    except Exception as e:
                        logger.error("`校验器`函数异常了 | {} | {}".format(e, req.url))

                    # 进入回调
                    try:
                        if self._stop_event.is_set():
                            break
                        callback = req.callback or self.parse
                        cached = callback(wrapped, **req.cb_kwargs)
                        await self._handle_callback_result(cached, q1, q2)
                    except Exception as e:
                        self.handle_callback_exception(e, req, wrapped)
                    finally:
                        break

            q1.task_done()

    async def item_task(self, q2: asyncio.Queue):
        """工作协程：从数据队列取 item → process_item。"""
        while True:
            try:
                item = await q2.get()
            except asyncio.CancelledError:
                break

            if item is _ITEM_SENTINEL:
                q2.task_done()
                break
            self.stats.item_count += 1
            try:
                if self._process_is_async:
                    await self.process_item(item)
                else:
                    self.process_item(item)
            except Exception as e:
                logger.error(f"process_item 异常: {e}")
            q2.task_done()

    def process_item(self, item: dict) -> None:
        """处理 yield 出来的 dict 数据，子类覆盖实现存储逻辑。

        Args:
            item: callback 中 yield 的 dict。
        """
        logger.success(item)

    async def run(self):
        """启动爬虫主循环（async 入口）。通常通过 ``go()`` 调用。"""
        self._stop_event = asyncio.Event()
        self._main_task = asyncio.current_task()
        self._process_is_async = asyncio.iscoroutinefunction(self.process_item)

        request_queue = asyncio.PriorityQueue()
        item_queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        # 请求处理协程数与并发数解耦
        worker_count = self.worker_count or self.max_concurrency * 2

        request_tasks = []
        item_tasks = []

        try:
            self.spider_opened()
            logger.info(f"爬虫 {self.__class__.__name__} 启动")

            # 处理请求...
            request_tasks = [asyncio.create_task(self.request_task(request_queue, item_queue, semaphore)) for _ in range(worker_count)]

            # 处理数据...
            item_tasks = [asyncio.create_task(self.item_task(item_queue)) for _ in range(self.item_speed)]

            # 发送最开始的请求
            for req in self.start_requests():
                if req.callback is None:
                    req.callback = self.parse
                await request_queue.put(req)

            # 等待所有请求处理完成
            await request_queue.join()
            logger.debug("🎉 All requests processed")
            # 等待所有数据处理完成
            await item_queue.join()
            logger.debug("🎉 All items processed")
        except asyncio.CancelledError:
            logger.warning("⚠️ Spider cancelled")
            was_stopping = self._stop_event is not None and self._stop_event.is_set()
            if self._stop_event is not None:
                self._stop_event.set()
            if not was_stopping:
                raise
        except Exception:
            if self._stop_event is not None:
                self._stop_event.set()
            raise
        finally:
            if request_tasks or item_tasks:
                if self._stop_event is not None and self._stop_event.is_set():
                    for task in request_tasks + item_tasks:
                        task.cancel()
                else:
                    # 发送退出信号，唤醒阻塞在 get() 上的 worker。
                    logger.debug("Send exit signals")
                    for _ in range(worker_count):
                        await request_queue.put(_REQUEST_SENTINEL)
                    for _ in range(self.item_speed):
                        await item_queue.put(_ITEM_SENTINEL)

                all_tasks = request_tasks + item_tasks
                if all_tasks:
                    logger.debug("⌛️ Wait workers quit...")
                    await asyncio.gather(*all_tasks, return_exceptions=True)
                    logger.debug("🎉 Workers quited")

            logger.debug("⌛️ Close HTTP clients...")
            await self._close_all_clients()
            logger.debug("🎉 All HTTP clients closed")
            self._main_task = None

            self.spider_closed()
            logger.info(self.stats)
            logger.info(f"✅ {self.__class__.__name__} Finished")

    async def _close_all_clients(self):
        """关闭所有代理专属 HTTP 客户端和全局客户端。"""
        for key, client in list(self._clients.items()):
            try:
                await asyncio.wait_for(client.aclose(), timeout=3)
            except asyncio.TimeoutError:
                logger.warning(f"关闭代理客户端超时: {key}")
            except Exception as e:
                logger.warning(f"关闭代理客户端异常: {key} {e}")
        self._clients.clear()
        try:
            await asyncio.wait_for(close_client(), timeout=3)
        except asyncio.TimeoutError:
            logger.warning("关闭全局客户端超时")
        except Exception as e:
            logger.warning(f"关闭全局客户端异常: {e}")

    def _handle_sigint(self, signum, frame) -> None:
        """处理 Ctrl+C 信号，设置停止事件。"""
        logger.warning("收到中断信号，正在优雅退出...")
        if self._stop_event is not None:
            self._stop_event.set()
        if self._main_task is not None and not self._main_task.done():
            self._main_task.cancel()

    def go(self) -> None:
        """启动爬虫的同步入口。注册 SIGINT 处理器以支持 Ctrl+C 优雅退出。"""
        try:
            original_handler = signal.signal(signal.SIGINT, self._handle_sigint)
        except ValueError:
            logger.warning("当前不在主线程中，无法注册信号处理器，Ctrl+C 优雅退出不可用")
            original_handler = None
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.warning("爬虫被强制中断")
        finally:
            # 恢复原始信号处理器
            if original_handler is not None:
                signal.signal(signal.SIGINT, original_handler)
