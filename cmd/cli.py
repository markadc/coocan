import re
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


if __name__ == "__main__":
    main()
