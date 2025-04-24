from pathlib import Path

import click

TEMPLATE_DIR = Path(__file__).parent / "templates"


@click.command()
@click.option('-s', '--spider', required=True, help='新建爬虫')
def main(spider):
    spider_file_name = "{}.py".format(spider)
    try:

        template_path = TEMPLATE_DIR / "spider.py"
        with open(template_path, 'r') as f:
            content = f.read()

        with open(spider_file_name, 'w') as f:
            f.write(content)

        click.echo("Success Create Spider {}".format(spider_file_name))

    except Exception as e:
        click.echo(str(e))
        raise click.ClickException("Failed Create Spider {}".format(spider_file_name))


if __name__ == '__main__':
    main()
