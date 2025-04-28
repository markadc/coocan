import os
import re
from pathlib import Path

import click

TEMPLATE_DIR = Path(__file__).parent.parent / 'templates'

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
    words = snake_str.split('_')
    pascal_str = ''.join(word.capitalize() for word in words)
    return pascal_str


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        print(help_info)
        click.echo("coocan new -s <spider_file_name>")


@main.command()
@click.option('-s', '--spider', required=True, help='爬虫文件名字')
def new(spider: str):
    """新建"""
    if not re.search("^[a-zA-Z0-9_]*$", spider):
        click.echo("只支持字母、数字、下划线")
        return

    spider_class_name = snake_to_pascal(spider)
    if not spider_class_name.lower().endswith("spider"):
        spider_class_name += "Spider"

    try:
        template_path = TEMPLATE_DIR / "spider.txt"
        with open(template_path, 'r') as f:
            text = f.read()
            spider_py_text = text.replace("{SpiderClassName}", spider_class_name)

        py_file = "{}.py".format(spider)
        if os.path.exists(py_file):
            click.echo("Failed because file {} already exists".format(py_file))
            return

        with open(py_file, 'w') as f:
            f.write(spider_py_text)

        click.echo("Success create {}".format(py_file))

    except Exception as e:
        click.echo(str(e))
        raise click.ClickException("Failed")


if __name__ == '__main__':
    main()
