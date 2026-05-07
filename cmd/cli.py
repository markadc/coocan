import ast
import hashlib
import importlib.util
import inspect
import re
import sys
from pathlib import Path

import click

try:
    from importlib.metadata import version as get_version
except ImportError:
    from importlib_metadata import version as get_version

try:
    __version__ = get_version("coocan")
except Exception:
    # 开发环境未安装时，从 pyproject.toml 读取
    _pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    if _pyproject.exists():
        with open(_pyproject, "r", encoding="utf-8") as f:
            _text = f.read()
        _m = re.search(r'^version = "([^"]+)"', _text, re.M)
        __version__ = _m.group(1) if _m else "unknown"
    else:
        __version__ = "unknown"

from coocan.gen import gen_random_ua
from coocan.spider.base import MiniSpider

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

help_info = """
 ██████╗ ██████╗  ██████╗  ██████╗ █████╗ ███╗   ██╗
██╔════╝██╔═══██╗██╔═══██╗██╔════╝██╔══██╗████╗  ██║
██║     ██║   ██║██║   ██║██║     ███████║██╔██╗ ██║
██║     ██║   ██║██║   ██║██║     ██╔══██║██║╚██╗██║
╚██████╗╚██████╔╝╚██████╔╝╚██████╗██║  ██║██║ ╚████║
 ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""


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
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except SyntaxError as e:
        if had_old_module:
            sys.modules[module_name] = old_module
        else:
            sys.modules.pop(module_name, None)
        detail = f"{e.filename}:{e.lineno}" if e.filename and e.lineno else str(file)
        raise CoocanClickException(f"语法错误: {detail} {e.msg}")
    except ImportError as e:
        if had_old_module:
            sys.modules[module_name] = old_module
        else:
            sys.modules.pop(module_name, None)
        raise CoocanClickException(f"导入失败: {e}")
    except Exception as e:
        if had_old_module:
            sys.modules[module_name] = old_module
        else:
            sys.modules.pop(module_name, None)
        raise CoocanClickException(f"加载爬虫文件失败: {type(e).__name__}: {e}")

    return module


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
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

    minispider_names = {"MiniSpider"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"coocan", "coocan.spider.base"}:
            for alias in node.names:
                if alias.name == "MiniSpider":
                    minispider_names.add(alias.asname or alias.name)

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

    if isinstance(cls.max_concurrency, bool) or not isinstance(cls.max_concurrency, int) or cls.max_concurrency < 1:
        warnings.append(f"max_concurrency={cls.max_concurrency} 应为正整数")
    else:
        infos.append(("max_concurrency", str(cls.max_concurrency)))

    if isinstance(cls.delay, tuple):
        if (
            len(cls.delay) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in cls.delay)
            or cls.delay[0] < 0
            or cls.delay[1] < cls.delay[0]
        ):
            warnings.append(f"delay={cls.delay} 格式不合法")
        else:
            infos.append(("delay", f"随机 {cls.delay[0]}~{cls.delay[1]}s"))
    elif isinstance(cls.delay, bool):
        warnings.append(f"delay 类型不合法: {cls.delay}")
    elif isinstance(cls.delay, (int, float)):
        if cls.delay < 0:
            warnings.append(f"delay={cls.delay} 应为非负数")
        else:
            infos.append(("delay", f"{cls.delay}s"))
    else:
        warnings.append(f"delay 类型不合法: {cls.delay}")

    if isinstance(cls.item_speed, bool) or not isinstance(cls.item_speed, int) or cls.item_speed < 1:
        warnings.append(f"item_speed={cls.item_speed} 应为正整数")
    else:
        infos.append(("item_speed", str(cls.item_speed)))

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


def print_spider_validation(cls):
    return print_validation_result(cls)


@click.version_option(version=__version__, prog_name="coocan")
@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        print(help_info)
        click.echo("coocan new -s <spider_file_name>")
        click.echo(f"coocan version {__version__}")


@main.command()
@click.option("-s", "--spider", required=True, help="爬虫文件名字")
def new(spider: str):
    """新建"""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", spider):
        raise CoocanClickException("只支持字母、数字、下划线，且不能以数字开头")

    spider_class_name = snake_to_pascal(spider)
    if not spider_class_name.lower().endswith("spider"):
        spider_class_name += "Spider"

    py_file = Path(f"{spider}.py")
    if py_file.exists():
        raise CoocanClickException(f"Failed because file {py_file} already exists")

    try:
        template_path = TEMPLATE_DIR / "spider.txt"
        with open(template_path, "r", encoding="utf-8") as f:
            text = f.read()
            spider_py_text = text.replace("{SpiderClassName}", spider_class_name)

        with open(py_file, "w", encoding="utf-8") as f:
            f.write(spider_py_text)

    except Exception as e:
        raise CoocanClickException(f"Failed: {e}")

    click.secho(f"✅ Success create {py_file}", fg="green")


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-n", "--name", help="指定要运行的爬虫类名（文件中存在多个爬虫类时使用）")
def run(file: Path, name: str | None):
    """运行爬虫文件。"""
    click.secho(f"加载爬虫文件: {file}", fg="cyan")
    ensure_static_spider_classes(file, name)
    module = load_module_from_file(file)
    spiders = find_spider_classes(module)
    if not spiders:
        raise CoocanClickException(f"未在 {file} 中找到 MiniSpider 子类")

    spider_cls = select_spider_class(spiders, name)

    # 前置检查
    errors, _ = print_validation_result(spider_cls, heading_color="cyan")
    if errors:
        raise CoocanClickException("前置检查未通过")

    instance = spider_cls()

    click.secho(f"运行 {spider_cls.__name__}...", fg="green")
    instance.go()


@main.command()
@click.option(
    "-n",
    "--count",
    default=1,
    type=click.IntRange(1, 100),
    help="生成数量（默认 1，最大 100）",
)
def ua(count: int):
    """生成随机 User-Agent。"""
    for _ in range(count):
        click.echo(gen_random_ua())


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path):
    """检查爬虫文件配置。"""
    ensure_static_spider_classes(file)
    module = load_module_from_file(file)
    spiders = find_spider_classes(module)

    if not spiders:
        raise CoocanClickException(f"未在 {file} 中找到 MiniSpider 子类")

    total_errors = 0
    for cls in spiders:
        errors, _ = print_spider_validation(cls)
        total_errors += len(errors)

    if total_errors:
        raise CoocanClickException(f"检查未通过，共 {total_errors} 个错误")


if __name__ == "__main__":
    main()
