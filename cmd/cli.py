import re
from pathlib import Path

import click

TEMPLATE_DIR = Path(__file__).parent / "templates"

help_info = """
 ██████╗ ██████╗  ██████╗  ██████╗ █████╗ ███╗   ██╗
██╔════╝██╔═══██╗██╔═══██╗██╔════╝██╔══██╗████╗  ██║
██║     ██║   ██║██║   ██║██║     ███████║██╔██╗ ██║
██║     ██║   ██║██║   ██║██║     ██╔══██║██║╚██╗██║
╚██████╗╚██████╔╝╚██████╔╝╚██████╗██║  ██║██║ ╚████║
 ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""


def show_help_info():
    print(help_info)


def snake_to_pascal(snake_str: str):
    """小蛇变成大驼峰"""
    words = snake_str.split('_')
    pascal_str = ''.join(word.capitalize() for word in words)
    return pascal_str


@click.group(invoke_without_command=True)  # 允许无子命令调用
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        show_help_info()
        click.echo("cc new -s <spider_file_name>")


@main.command()
@click.option('-s', '--spider', required=True, help='爬虫文件名字')
def new(spider):
    """新建"""
    if not re.search("^[a-zA-Z0-9_]*$", spider):
        click.echo("只支持字母、数字、下划线")
        return

    pascal = snake_to_pascal(spider)
    if not pascal.endswith("Spider"):
        pascal += "Spider"

    try:
        template_path = TEMPLATE_DIR / "spider.txt"
        with open(template_path, 'r') as f:
            text = f.read()
            spider_py_text = text.replace("{SpiderClassName}", pascal)

        with open("{}.py".format(spider), 'w') as f:
            f.write(spider_py_text)

        click.echo("Success")

    except Exception as e:
        click.echo(str(e))
        raise click.ClickException("Failed")


if __name__ == '__main__':
    main()
