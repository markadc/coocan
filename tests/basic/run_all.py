"""运行所有测试 - 直接运行即可"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def run_test(test_file: str):
    """运行单个测试文件"""
    print(f"\n{'#' * 60}")
    print(f"# 运行: {test_file}")
    print(f"{'#' * 60}\n")

    result = subprocess.run(
        [sys.executable, test_file],
        cwd=Path(__file__).parent.parent.parent,
    )
    return result.returncode == 0


def main():
    test_dir = Path(__file__).parent
    test_files = [
        test_dir / "test_gen.py",
        test_dir / "test_request.py",
        test_dir / "test_response.py",
        test_dir / "test_spider.py",
    ]

    print("=" * 60)
    print("Coocan 测试套件")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_file in test_files:
        if test_file.exists():
            if run_test(str(test_file)):
                passed += 1
            else:
                failed += 1
        else:
            print(f"警告: 测试文件不存在 {test_file}")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
