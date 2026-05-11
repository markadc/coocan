import click

from . import __version__

help_info = """
 ██████╗ ██████╗  ██████╗  ██████╗ █████╗ ███╗   ██╗
██╔════╝██╔═══██╗██╔═══██╗██╔════╝██╔══██╗████╗  ██║
██║     ██║   ██║██║   ██║██║     ███████║██╔██╗ ██║
██║     ██║   ██║██║   ██║██║     ██╔══██║██║╚██╗██║
╚██████╗╚██████╔╝╚██████╔╝╚██████╗██║  ██║██║ ╚████║
 ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""


@click.version_option(version=__version__, prog_name="coocan")
@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        print(help_info)
        click.echo("coocan new -s <spider_file_name>")
        click.echo(f"Coocan Version {__version__}")


# 注册子命令
from .check import check  # noqa: E402
from .new import new  # noqa: E402
from .run import run  # noqa: E402
from .ua import ua  # noqa: E402


main.add_command(new)
main.add_command(run)
main.add_command(ua)
main.add_command(check)

if __name__ == "__main__":
    main()
