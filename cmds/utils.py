"""CLI 共享工具。"""

import ast
import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path

import click

from coocan.spider.base import MiniSpider


class CoocanClickException(click.ClickException):
    """使用中文错误前缀的 CLI 异常。"""

    def show(self, file=None):
        if file is None:
            file = click.get_text_stream("stderr")
        click.secho(f"错误: {self.format_message()}", fg="red", file=file)


def snake_to_pascal(snake_str: str):
    """小蛇变成大驼峰"""
    words = [w for w in snake_str.split("_") if w]
    return "".join(word[:1].upper() + word[1:] for word in words)


def load_module_from_file(file: Path):
    """从文件加载模块，使用唯一模块名避免同名文件冲突。"""
    file = file.resolve()
    digest = hashlib.sha1(str(file).encode("utf-8")).hexdigest()[:12]
    module_name = f"coocan_user_spider_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise CoocanClickException(f"无法加载文件: {file}")

    module = importlib.util.module_from_spec(spec)
    old_module = sys.modules.get(module_name)
    had_old_module = module_name in sys.modules
    module_dir = str(file.parent)
    sys.modules[module_name] = module
    sys.path.insert(0, module_dir)

    try:
        spec.loader.exec_module(module)
    except SyntaxError as e:
        detail = f"{e.filename}:{e.lineno}" if e.filename and e.lineno else str(file)
        raise CoocanClickException(f"语法错误: {detail} {e.msg}")
    except ImportError as e:
        raise CoocanClickException(f"导入失败: {e}")
    except Exception as e:
        raise CoocanClickException(f"加载爬虫文件失败: {type(e).__name__}: {e}")
    finally:
        try:
            sys.path.remove(module_dir)
        except ValueError:
            pass
        if had_old_module:
            sys.modules[module_name] = old_module
        else:
            sys.modules.pop(module_name, None)

    return module


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _base_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return None


def find_static_spider_class_names(file: Path):
    """导入前静态查找直接继承 MiniSpider 的类，避免误执行普通脚本。"""
    try:
        text = file.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file))
    except SyntaxError as e:
        detail = f"{e.filename}:{e.lineno}" if e.filename and e.lineno else str(file)
        raise CoocanClickException(f"语法错误: {detail} {e.msg}")
    except OSError as e:
        raise CoocanClickException(f"读取文件失败: {e}")

    minispider_names = set()
    coocan_module_names = set()
    import_from_modules = {"coocan", "coocan.spider", "coocan.spider.base"}
    import_modules = {"coocan", "coocan.spider", "coocan.spider.base"}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in import_modules:
                    coocan_module_names.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.module in import_from_modules:
            for alias in node.names:
                if alias.name == "MiniSpider":
                    minispider_names.add(alias.asname or alias.name)
                elif alias.name == "*":
                    minispider_names.add("MiniSpider")

    minispider_names.update(f"{name}.MiniSpider" for name in coocan_module_names)

    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    spider_names = set(minispider_names)
    found_names = []

    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in spider_names:
                continue
            if any(_base_name(base) in spider_names for base in node.bases):
                spider_names.add(node.name)
                found_names.append(node.name)
                changed = True

    return found_names


def ensure_static_spider_classes(file: Path, name: str | None = None):
    spider_names = find_static_spider_class_names(file)
    if not spider_names:
        raise CoocanClickException(f"未在 {file} 中找到 MiniSpider 子类")
    if name and name not in spider_names:
        available = ", ".join(spider_names)
        raise CoocanClickException(f"未找到类 '{name}'，可用类: {available}")
    return spider_names


def find_spider_classes(module):
    """只查找当前文件中定义的 MiniSpider 子类。"""
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if (
            issubclass(obj, MiniSpider)
            and obj is not MiniSpider
            and obj.__module__ == module.__name__
        )
    ]


def load_spider_classes(file: Path, name: str | None = None):
    """静态确认后加载爬虫文件并返回运行时爬虫类。"""
    static_names = ensure_static_spider_classes(file, name)
    module = load_module_from_file(file)
    spiders = find_spider_classes(module)
    runtime_names = {c.__name__ for c in spiders}
    unexpected = runtime_names - set(static_names)
    if unexpected:
        click.secho(f"警告: 运行时发现静态分析未检测到的类: {', '.join(sorted(unexpected))}", fg="yellow")
    if not spiders:
        raise CoocanClickException(f"未在 {file} 中找到 MiniSpider 子类")
    return spiders


def select_spider_class(spiders, name: str | None):
    if not spiders:
        raise CoocanClickException("未找到 MiniSpider 子类")

    click.secho(f"发现 {len(spiders)} 个爬虫类", fg="green")
    if name:
        click.secho(f"指定运行类: {name}", fg="cyan")
        for cls in spiders:
            if cls.__name__ == name:
                return cls
        available = ", ".join(c.__name__ for c in spiders)
        raise CoocanClickException(f"未找到类 '{name}'，可用类: {available}")

    if len(spiders) == 1:
        return spiders[0]

    click.secho(f"发现 {len(spiders)} 个爬虫类，请用 -n 指定:", fg="yellow")
    for i, cls in enumerate(spiders, 1):
        click.secho(f"  {i}. {cls.__name__}", fg="cyan")
    raise CoocanClickException("需要指定爬虫类名")


def _is_valid_positive_int(value):
    """拒绝 bool（它是 int 的子类），要求正整数。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) and value >= 1


def _is_valid_non_negative_int(value):
    if isinstance(value, bool):
        return False
    return isinstance(value, int) and value >= 0


def _is_valid_non_negative_number(value):
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float)) and value >= 0


def _validate_delay(delay):
    """检查 delay 字段，返回 (kind, message) 其中 kind 为 'warn' 或 'info'。"""
    if isinstance(delay, tuple):
        if (
            len(delay) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in delay)
            or delay[0] < 0
            or delay[1] < delay[0]
        ):
            return "warn", f"delay={delay} 格式不合法"
        return "info", ("delay", f"随机 {delay[0]}~{delay[1]}s")

    if isinstance(delay, bool):
        return "warn", f"delay 类型不合法: {delay}"

    if isinstance(delay, (int, float)):
        if delay < 0:
            return "warn", f"delay={delay} 应为非负数"
        return "info", ("delay", f"{delay}s")

    return "warn", f"delay 类型不合法: {delay}"


def validate_spider_class(cls):
    errors = []
    warnings = []
    infos = []

    start_urls = cls.start_urls
    has_start_urls = bool(start_urls)
    has_custom_start_requests = cls.start_requests is not MiniSpider.start_requests

    if has_start_urls and not isinstance(start_urls, (list, tuple)):
        errors.append("start_urls 必须是 list 或 tuple")
    elif has_start_urls and not all(isinstance(url, str) and url.strip() for url in start_urls):
        errors.append("start_urls 中每一项都必须是非空字符串")
    elif has_start_urls:
        infos.append(("start_urls", f"{len(start_urls)} 个 URL"))
    elif has_custom_start_requests:
        infos.append(("start_requests", "已覆写"))
    else:
        errors.append("start_urls 为空，且 start_requests 未覆写")

    if cls.parse is MiniSpider.parse:
        errors.append("parse 方法未实现")
    else:
        infos.append(("parse", "已实现"))

    if _is_valid_positive_int(cls.max_concurrency):
        infos.append(("max_concurrency", str(cls.max_concurrency)))
    else:
        errors.append(f"max_concurrency={cls.max_concurrency} 应为正整数")

    delay_result = _validate_delay(cls.delay)
    if delay_result[0] == "warn":
        warnings.append(delay_result[1])
    else:
        infos.append(delay_result[1])

    if _is_valid_positive_int(cls.item_speed):
        infos.append(("item_speed", str(cls.item_speed)))
    else:
        errors.append(f"item_speed={cls.item_speed} 应为正整数")

    if cls.worker_count is None:
        infos.append(("worker_count", "自动"))
    elif _is_valid_positive_int(cls.worker_count):
        infos.append(("worker_count", str(cls.worker_count)))
    else:
        errors.append(f"worker_count={cls.worker_count} 应为正整数或 None")

    if _is_valid_non_negative_int(cls.max_retry_times):
        infos.append(("max_retry_times", str(cls.max_retry_times)))
    else:
        errors.append(f"max_retry_times={cls.max_retry_times} 应为非负整数")

    if _is_valid_non_negative_number(cls.retry_backoff_base):
        infos.append(("retry_backoff_base", str(cls.retry_backoff_base)))
    else:
        errors.append(f"retry_backoff_base={cls.retry_backoff_base} 应为非负数")

    if _is_valid_non_negative_number(cls.retry_backoff_max):
        infos.append(("retry_backoff_max", str(cls.retry_backoff_max)))
    else:
        errors.append(f"retry_backoff_max={cls.retry_backoff_max} 应为非负数")

    if (
        _is_valid_non_negative_number(cls.retry_backoff_base)
        and _is_valid_non_negative_number(cls.retry_backoff_max)
        and cls.retry_backoff_max < cls.retry_backoff_base
    ):
        warnings.append("retry_backoff_max 小于 retry_backoff_base，重试退避会被上限截断")

    return errors, warnings, infos


def print_validation_result(cls, *, heading_color: str | None = None):
    if heading_color:
        click.secho(f"检查 {cls.__name__}...", fg=heading_color)
    else:
        click.echo(f"\n检查 {cls.__name__}...")

    errors, warnings, infos = validate_spider_class(cls)

    for name, value in infos:
        click.echo(f"  {name}: {value}")
    for warning in warnings:
        click.secho(f"  警告: {warning}", fg="yellow")
    for error in errors:
        click.secho(f"  错误: {error}", fg="red")

    if errors:
        click.secho(f"  {len(errors)} 个错误，{len(warnings)} 个警告", fg="red")
    elif warnings:
        click.secho(f"  通过，{len(warnings)} 个警告", fg="yellow")
    else:
        click.secho("  全部通过", fg="green")

    return errors, warnings
