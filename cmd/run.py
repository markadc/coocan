"""run 命令：运行爬虫文件。"""

from pathlib import Path

import click

from .utils import (
    CoocanClickException,
    load_spider_classes,
    print_validation_result,
    select_spider_class,
)


@click.command(help="加载并运行指定的爬虫文件。")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-n", "--name", help="指定要运行的爬虫类名（文件中存在多个爬虫类时使用）")
def run(file: Path, name: str | None):
    """运行爬虫文件。"""
    click.secho(f"加载爬虫文件: {file}", fg="cyan")
    spiders = load_spider_classes(file, name)
    spider_cls = select_spider_class(spiders, name)

    # 前置检查
    errors, _ = print_validation_result(spider_cls, heading_color="cyan")
    if errors:
        raise CoocanClickException("前置检查未通过")

    instance = spider_cls()

    click.secho(f"运行 {spider_cls.__name__}...", fg="green")
    instance.go()
