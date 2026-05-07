"""测试命令行工具"""

from pathlib import Path

from click.testing import CliRunner

from coocan.cmd.cli import main


def test_new_creates_spider_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["new", "-s", "my_spider"])

        assert result.exit_code == 0
        assert "Success create my_spider.py" in result.output


def test_new_preserves_existing_word_case_in_class_name():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["new", "-s", "URL_spider"])

        assert result.exit_code == 0
        with open("URL_spider.py", "r", encoding="utf-8") as f:
            assert "class URLSpider(MiniSpider):" in f.read()


def test_new_rejects_invalid_name():
    result = CliRunner().invoke(main, ["new", "-s", "123bad"])

    assert result.exit_code != 0
    assert "只支持字母、数字、下划线" in result.output


def test_new_rejects_existing_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["new", "-s", "my_spider"])
        result = runner.invoke(main, ["new", "-s", "my_spider"])

        assert result.exit_code != 0
        assert "already exists" in result.output


def test_run_allows_custom_start_requests_without_start_urls():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Request, Response\n"
                "class DemoSpider(MiniSpider):\n"
                "    def start_requests(self):\n"
                "        yield Request('https://example.com', callback=self.parse)\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
                "DemoSpider.go = lambda self: print('GO_CALLED')\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py"])

        assert result.exit_code == 0
        assert "start_requests: 已覆写" in result.output
        assert "GO_CALLED" in result.output


def test_run_rejects_string_start_urls():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Response\n"
                "class DemoSpider(MiniSpider):\n"
                "    start_urls = 'https://example.com'\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
                "DemoSpider.go = lambda self: print('GO_CALLED')\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py"])

        assert result.exit_code != 0
        assert "start_urls 必须是 list 或 tuple" in result.output
        assert "前置检查未通过" in result.output
        assert "GO_CALLED" not in result.output


def test_run_warns_negative_delay_but_continues():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Response\n"
                "class DemoSpider(MiniSpider):\n"
                "    start_urls = ['https://example.com']\n"
                "    delay = -1\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
                "DemoSpider.go = lambda self: print('GO_CALLED')\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py"])

        assert result.exit_code == 0
        assert "警告: delay=-1 应为非负数" in result.output
        assert "GO_CALLED" in result.output


def test_run_requires_name_for_multiple_spiders():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Response\n"
                "class FirstSpider(MiniSpider):\n"
                "    start_urls = ['https://example.com']\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
                "class SecondSpider(FirstSpider):\n"
                "    pass\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py"])

        assert result.exit_code != 0
        assert "需要指定爬虫类名" in result.output
        assert "FirstSpider" in result.output
        assert "SecondSpider" in result.output


def test_run_allows_named_indirect_spider_subclass():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Response\n"
                "class FirstSpider(MiniSpider):\n"
                "    start_urls = ['https://example.com']\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
                "class SecondSpider(FirstSpider):\n"
                "    pass\n"
                "SecondSpider.go = lambda self: print('SECOND_GO')\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py", "-n", "SecondSpider"])

        assert result.exit_code == 0
        assert "指定运行类: SecondSpider" in result.output
        assert "SECOND_GO" in result.output


def test_run_detects_coocan_module_base_class():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("demo_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "import coocan as cc\n"
                "class DemoSpider(cc.MiniSpider):\n"
                "    start_urls = ['https://example.com']\n"
                "    def parse(self, response):\n"
                "        return None\n"
                "DemoSpider.go = lambda self: print('GO_CALLED')\n"
            )

        result = runner.invoke(main, ["run", "demo_spider.py"])

        assert result.exit_code == 0
        assert "GO_CALLED" in result.output


def test_run_uses_chinese_error_prefix():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("empty.py", "w", encoding="utf-8") as f:
            f.write("VALUE = 1\n")

        result = runner.invoke(main, ["run", "empty.py"])

        assert result.exit_code != 0
        assert "错误: 未在 empty.py 中找到 MiniSpider 子类" in result.output
        assert "Error:" not in result.output


def test_run_does_not_execute_file_without_static_spider():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("p2.py", "w", encoding="utf-8") as f:
            f.write(
                "print('SHOULD_NOT_RUN')\n"
                "with open('side_effect.txt', 'w', encoding='utf-8') as fp:\n"
                "    fp.write('bad')\n"
            )

        result = runner.invoke(main, ["run", "p2.py"])

        assert result.exit_code != 0
        assert "错误: 未在 p2.py 中找到 MiniSpider 子类" in result.output
        assert "SHOULD_NOT_RUN" not in result.output
        assert not Path("side_effect.txt").exists()


def test_run_styles_chinese_error_prefix_red():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("empty.py", "w", encoding="utf-8") as f:
            f.write("VALUE = 1\n")

        result = runner.invoke(main, ["run", "empty.py"], color=True)

        assert "\x1b[31m错误:" in result.output


def test_ua_rejects_out_of_range_count():
    result = CliRunner().invoke(main, ["ua", "-n", "101"])

    assert result.exit_code != 0
    assert "101 is not in the range" in result.output


def test_check_rejects_file_without_spider():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("empty.py", "w", encoding="utf-8") as f:
            f.write("VALUE = 1\n")

        result = runner.invoke(main, ["check", "empty.py"])

        assert result.exit_code != 0
        assert "错误: 未在 empty.py 中找到 MiniSpider 子类" in result.output


def test_check_does_not_execute_file_without_static_spider():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("p2.py", "w", encoding="utf-8") as f:
            f.write(
                "print('SHOULD_NOT_RUN')\n"
                "with open('side_effect.txt', 'w', encoding='utf-8') as fp:\n"
                "    fp.write('bad')\n"
            )

        result = runner.invoke(main, ["check", "p2.py"])

        assert result.exit_code != 0
        assert "错误: 未在 p2.py 中找到 MiniSpider 子类" in result.output
        assert "SHOULD_NOT_RUN" not in result.output
        assert not Path("side_effect.txt").exists()


def test_check_rejects_invalid_spider_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("bad_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider\n"
                "class BadSpider(MiniSpider):\n"
                "    pass\n"
            )

        result = runner.invoke(main, ["check", "bad_spider.py"])

        assert result.exit_code != 0
        assert "start_urls 为空，且 start_requests 未覆写" in result.output
        assert "parse 方法未实现" in result.output
        assert "检查未通过，共 2 个错误" in result.output


def test_check_accepts_valid_spider_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("good_spider.py", "w", encoding="utf-8") as f:
            f.write(
                "from coocan import MiniSpider, Response\n"
                "class GoodSpider(MiniSpider):\n"
                "    start_urls = ['https://example.com']\n"
                "    def parse(self, response: Response):\n"
                "        return None\n"
            )

        result = runner.invoke(main, ["check", "good_spider.py"])

        assert result.exit_code == 0
        assert "全部通过" in result.output
