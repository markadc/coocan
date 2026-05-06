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
        with open(_pyproject, "r") as f:
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


def snake_to_pascal(snake_str: str):
    """小蛇变成大驼峰"""
    words = [w for w in snake_str.split("_") if w]
    return "".join(word.capitalize() for word in words)


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
        click.echo("只支持字母、数字、下划线，且不能以数字开头")
        return

    spider_class_name = snake_to_pascal(spider)
    if not spider_class_name.lower().endswith("spider"):
        spider_class_name += "Spider"

    try:
        template_path = TEMPLATE_DIR / "spider.txt"
        with open(template_path, "r", encoding="utf-8") as f:
            text = f.read()
            spider_py_text = text.replace("{SpiderClassName}", spider_class_name)

        py_file = Path("{}.py".format(spider))
        if py_file.exists():
            click.echo("❌ Failed because file {} already exists".format(py_file))
            return

        with open(py_file, "w", encoding="utf-8") as f:
            f.write(spider_py_text)

        click.echo("✅ Success create {}".format(py_file))

    except Exception as e:
        click.echo(str(e))
        raise click.ClickException("Failed")


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-n", "--name", help="指定要运行的爬虫类名（文件中存在多个爬虫类时使用）")
def run(file: Path, name: str | None):
    """运行爬虫文件。"""
    click.secho(f"加载爬虫文件: {file}", fg="cyan")
    module_name = file.stem
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise click.ClickException(click.style(f"无法加载文件: {file}", fg="red"))

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    spiders = [
        obj for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, MiniSpider) and obj is not MiniSpider
    ]

    if not spiders:
        raise click.ClickException(click.style(f"未在 {file} 中找到 MiniSpider 子类", fg="red"))

    click.secho(f"发现 {len(spiders)} 个爬虫类", fg="green")

    spider_cls = None
    if name:
        click.secho(f"指定运行类: {name}", fg="cyan")
        for cls in spiders:
            if cls.__name__ == name:
                spider_cls = cls
                break
        if spider_cls is None:
            available = ", ".join(c.__name__ for c in spiders)
            raise click.ClickException(click.style(f"未找到类 '{name}'，可用类: {available}", fg="red"))
    elif len(spiders) == 1:
        spider_cls = spiders[0]
    else:
        click.secho(f"发现 {len(spiders)} 个爬虫类，请用 -n 指定:", fg="yellow")
        for i, cls in enumerate(spiders, 1):
            click.secho(f"  {i}. {cls.__name__}", fg="cyan")
        raise click.ClickException(click.style("需要指定爬虫类名", fg="red"))

    # 前置检查
    click.secho(f"检查 {spider_cls.__name__}...", fg="cyan")
    instance = spider_cls()
    if not instance.start_urls:
        raise click.ClickException(click.style("start_urls 为空", fg="red"))
    click.secho(f"  start_urls: {len(instance.start_urls)} 个 URL", fg="green")

    if spider_cls.parse is MiniSpider.parse:
        raise click.ClickException(click.style("parse 方法未实现", fg="red"))
    click.secho("  parse: 已实现", fg="green")

    click.secho(f"运行 {spider_cls.__name__}...", fg="green")
    instance.go()


@main.command()
@click.option("-n", "--count", default=1, type=int, help="生成数量（默认 1，最大 100）")
def ua(count: int):
    """生成随机 User-Agent。"""
    count = max(1, min(count, 100))
    for _ in range(count):
        click.echo(gen_random_ua())


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path):
    """检查爬虫文件配置。"""
    module_name = file.stem
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"无法加载文件: {file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    spiders = [
        obj for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, MiniSpider) and obj is not MiniSpider
    ]

    if not spiders:
        click.secho(f"错误: 未在 {file} 中找到 MiniSpider 子类", fg="red")
        return

    for cls in spiders:
        click.echo(f"\n检查 {cls.__name__}...")
        errors = 0
        warnings = 0

        # start_urls
        if not cls.start_urls:
            click.secho("  错误: start_urls 为空列表", fg="red")
            errors += 1
        else:
            click.echo(f"  start_urls: {len(cls.start_urls)} 个 URL")

        # parse
        if cls.parse is MiniSpider.parse:
            click.secho("  错误: parse 方法未实现", fg="red")
            errors += 1
        else:
            click.echo("  parse: 已实现")

        # max_concurrency
        if not isinstance(cls.max_concurrency, int) or cls.max_concurrency < 1:
            click.secho(f"  警告: max_concurrency={cls.max_concurrency} 应为正整数", fg="yellow")
            warnings += 1
        else:
            click.echo(f"  max_concurrency: {cls.max_concurrency}")

        # delay
        if isinstance(cls.delay, tuple):
            if len(cls.delay) != 2 or cls.delay[0] < 0 or cls.delay[1] < cls.delay[0]:
                click.secho(f"  警告: delay={cls.delay} 格式不合法", fg="yellow")
                warnings += 1
            else:
                click.echo(f"  delay: 随机 {cls.delay[0]}~{cls.delay[1]}s")
        elif isinstance(cls.delay, (int, float)):
            click.echo(f"  delay: {cls.delay}s")
        else:
            click.secho(f"  警告: delay 类型不合法", fg="yellow")
            warnings += 1

        # item_speed
        if not isinstance(cls.item_speed, int) or cls.item_speed < 1:
            click.secho(f"  警告: item_speed={cls.item_speed} 应为正整数", fg="yellow")
            warnings += 1
        else:
            click.echo(f"  item_speed: {cls.item_speed}")

        if errors == 0 and warnings == 0:
            click.secho("  全部通过", fg="green")
        elif errors == 0:
            click.secho(f"  通过，{warnings} 个警告", fg="yellow")
        else:
            click.secho(f"  {errors} 个错误，{warnings} 个警告", fg="red")


if __name__ == "__main__":
    main()
