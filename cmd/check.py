"""check 命令：检查爬虫文件配置。"""

from pathlib import Path

import click

from .cli import (
    CoocanClickException,
    ensure_static_spider_classes,
    find_spider_classes,
    load_module_from_file,
    print_validation_result,
)


@click.command(help="检查爬虫文件配置，不运行。")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path):
    """检查爬虫文件配置。"""
    static_names = ensure_static_spider_classes(file)
    module = load_module_from_file(file)
    spiders = find_spider_classes(module)
    runtime_names = {c.__name__ for c in spiders}
    unexpected = runtime_names - set(static_names)
    if unexpected:
        click.secho(f"警告: 运行时发现静态分析未检测到的类: {', '.join(sorted(unexpected))}", fg="yellow")
    if not spiders:
        raise CoocanClickException(f"未在 {file} 中找到 MiniSpider 子类")

    total_errors = 0
    for cls in spiders:
        errors, _ = print_validation_result(cls)
        total_errors += len(errors)

    if total_errors:
        raise CoocanClickException(f"检查未通过，共 {total_errors} 个错误")
