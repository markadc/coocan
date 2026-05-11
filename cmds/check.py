"""check 命令：检查爬虫文件配置。"""

from pathlib import Path

import click

from .utils import (
    CoocanClickException,
    load_spider_classes,
    print_validation_result,
)


@click.command(help="检查爬虫文件配置，不启动爬虫。")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path):
    """检查爬虫文件配置。"""
    spiders = load_spider_classes(file)
    total_errors = 0
    for cls in spiders:
        errors, _ = print_validation_result(cls)
        total_errors += len(errors)

    if total_errors:
        raise CoocanClickException(f"检查未通过，共 {total_errors} 个错误")
