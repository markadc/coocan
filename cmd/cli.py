from pathlib import Path

import click

TEMPLATE_DIR = Path(__file__).parent / "templates"


@click.group()
def main():
    """
    \n
    可用命令：
      new -s 创建新的爬虫文件
    \n
    示例：
      cc new -s demo
    """


@main.command()
@click.option('-s', '--spider', required=True, help='爬虫文件')
def new(spider):
    """新建"""
    spider_file_name = "{}.py".format(spider)
    try:
        template_path = TEMPLATE_DIR / "spider.py"
        with open(template_path, 'r') as f:
            content = f.read()

        with open(spider_file_name, 'w') as f:
            f.write(content)

        click.echo("Success")

    except Exception as e:
        click.echo(str(e))
        raise click.ClickException("Failed")


if __name__ == '__main__':
    main()
