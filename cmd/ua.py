"""ua 命令：生成随机 User-Agent。"""

import click

from coocan.gen import gen_random_ua


@click.command(help="生成随机 User-Agent 字符串。")
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
