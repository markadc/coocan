"""run 命令：运行爬虫文件。"""

from pathlib import Path

import click

from .cli import (
    CoocanClickException,
    ensure_static_spider_classes,
    find_spider_classes,
    load_module_from_file,
    print_validation_result,
    select_spider_class,
)


@click.command(help="加载并运行指定的爬虫文件。")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-n", "--name", help="指定要运行的爬虫类名（文件中存在多个爬虫类时使用）")
def run(file: Path, name: str | None):
    """运行爬虫文件。"""
    click.secho(f"加载爬虫文件: {file}", fg="cyan")
    static_names = ensure_static_spider_classes(file, name)
    module = load_module_from_file(file)
    spiders = find_spider_classes(module)
    runtime_names = {c.__name__ for c in spiders}
    unexpected = runtime_names - set(static_names)
    if unexpected:
        click.secho(f"警告: 运行时发现静态分析未检测到的类: {', '.join(sorted(unexpected))}", fg="yellow")
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
