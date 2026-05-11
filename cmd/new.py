"""new 命令：创建爬虫文件。"""

import re
from pathlib import Path

import click

from .utils import CoocanClickException, snake_to_pascal

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


@click.command(help="从模板新建爬虫文件。")
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
        raise CoocanClickException(f"文件已存在: {py_file}")

    try:
        template_path = TEMPLATE_DIR / "spider.txt"
        with open(template_path, "r", encoding="utf-8") as f:
            text = f.read()
            spider_py_text = text.replace("{SpiderClassName}", spider_class_name)

        with open(py_file, "w", encoding="utf-8") as f:
            f.write(spider_py_text)

    except Exception as e:
        raise CoocanClickException(f"创建失败: {e}")

    click.secho(f"成功创建 {py_file}", fg="green")
