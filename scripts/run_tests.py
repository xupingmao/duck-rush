#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Duck Rush 统一测试入口。

自动发现并执行全量测试:

- Python: pytest(默认带 coverage 覆盖率统计), 发现 test_*.py / *_test.py
- JavaScript: node, 发现 *.test.js

用法:
    python scripts/run_tests.py                 # 全量测试(含覆盖率)
    python scripts/run_tests.py tests/python    # 只跑指定目录/文件
    python scripts/run_tests.py -k dir_util     # 按名字过滤用例
    python scripts/run_tests.py --no-js --html  # 只跑 Python, 并生成 HTML 覆盖率报告

退出码: 全部通过为 0, 否则为 1。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 测试文件命名规则
PY_NAME_PREFIX = "test_"
PY_NAME_SUFFIX = "_test.py"
JS_NAME_SUFFIX = ".test.js"

# 遍历时跳过的目录(依赖/构建产物/文档等)
DEFAULT_EXCLUDE_DIRS = frozenset({
    ".git", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", "__pycache__",
    "node_modules", "site-packages", "venv", ".venv", "build", "dist",
    "local", "data", "docs", "lib",
    # GUI 手工测试(需人工交互/显示器), 默认不纳入自动化
    "gui-tools",
})

# 默认统计覆盖率的源码目录(仅统计仓库自身代码)
DEFAULT_COV_SOURCES = ("duck_rush", "duck_utils")

DEFAULT_REPORT = "test-report.json"
HTML_COV_DIR = "htmlcov"
PYTHON_TIMEOUT = 900      # 秒
JS_TIMEOUT = 300          # 秒

Result = Dict[str, Any]


def relpath(path: str) -> str:
    """相对仓库根的路径, 统一用 '/' 分隔, 便于展示"""
    return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")


def walk_files(root: str, exclude_dirs: Sequence[str]) -> List[str]:
    """递归列出文件(相对仓库根的路径), 跳过 exclude_dirs 中的目录"""
    exclude = set(DEFAULT_EXCLUDE_DIRS) | set(exclude_dirs)
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fn in filenames:
            found.append(os.path.join(dirpath, fn))
    return found


def is_python_test(path: str) -> bool:
    name = os.path.basename(path)
    return name.startswith(PY_NAME_PREFIX) and path.endswith(".py")


def is_js_test(path: str) -> bool:
    return path.endswith(JS_NAME_SUFFIX)


def discover_tests(kind: str, extra_excludes: Sequence[str]) -> List[str]:
    """发现测试文件: kind 取 'python' 或 'js', 返回排序后的绝对路径"""
    matcher = is_python_test if kind == "python" else is_js_test
    files = [p for p in walk_files(PROJECT_ROOT, extra_excludes) if matcher(p)]
    return sorted(files)


def resolve_paths(paths: Sequence[str]) -> List[str]:
    """把命令行传入的文件/目录展开成测试文件列表(目录递归查找)"""
    result: List[str] = []
    for raw in paths:
        target = raw if os.path.isabs(raw) else os.path.join(PROJECT_ROOT, raw)
        if os.path.isdir(target):
            result.extend(p for p in walk_files(target, ()) if is_python_test(p) or is_js_test(p))
        else:
            result.append(target)
    return sorted(set(result))


def module_available(name: str) -> bool:
    """判断 Python 模块是否已安装(不导入, 避免副作用)"""
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def decode(data: Optional[bytes]) -> str:
    return data.decode("utf-8", errors="replace") if data else ""


def build_pytest_cmd(files: Sequence[str], args: argparse.Namespace,
                     coverage: bool) -> List[str]:
    """构造 pytest 命令行; coverage 为 True 时追加 coverage 参数"""
    cmd = [sys.executable, "-m", "pytest", *files, "-q", "--color=no",
           "-p", "no:cacheprovider"]
    if args.keyword:
        cmd += ["-k", args.keyword]
    if args.verbose:
        cmd += ["-v"]
    if args.fail_fast:
        cmd += ["-x"]

    if coverage:
        for source in DEFAULT_COV_SOURCES:
            cmd += ["--cov", source]
        # skip-covered: 不展示已全覆盖的文件, 避免输出过长
        cmd += ["--cov-report", "term-missing:skip-covered"]
        if args.html:
            cmd += ["--cov-report", "html:%s" % HTML_COV_DIR]
    return cmd


def run_python_suite(files: Sequence[str], args: argparse.Namespace) -> Result:
    """执行 Python 测试(pytest + coverage), 返回单个结果记录"""
    result: Result = {
        "test": "pytest (%d files)" % len(files),
        "lang": "Python",
        "status": "PASS",
        "detail": "",
        "files": [relpath(f) for f in files],
        "time": 0,
    }
    if not files:
        result["status"] = "SKIP"
        result["detail"] = "no test files found"
        return result

    coverage = bool(args.coverage) and module_available("pytest_cov")
    if args.coverage and not coverage:
        # 没有 pytest-cov 时降级: 只跑 pytest, 不统计覆盖率
        sys.stderr.write("run_tests: 未安装 pytest-cov, 本次不统计覆盖率\n")
    result["coverage_enabled"] = coverage

    cmd = build_pytest_cmd(files, args, coverage)
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True,
                              timeout=PYTHON_TIMEOUT)
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        result["detail"] = "timeout >%ds" % PYTHON_TIMEOUT
        result["time"] = PYTHON_TIMEOUT
        return result

    output = decode(proc.stdout) + decode(proc.stderr)
    result["time"] = round(time.time() - start, 2)
    if proc.returncode != 0:
        result["status"] = "FAIL"
        result["output"] = output.strip()[-4000:]
    elif args.verbose:
        result["output"] = output.strip()[-4000:]
    if coverage:
        result["coverage"] = parse_coverage_percent(output)
    return result


def parse_coverage_percent(output: str) -> Optional[float]:
    """从 coverage 报告的 TOTAL 行里解析总覆盖率(百分比)"""
    # Windows 下输出可能带 \r, 故行尾允许空白字符
    m = re.search(r"^TOTAL\s+.*?(\d+(?:\.\d+)?)%[ \t\r]*$", output, re.MULTILINE)
    if m:
        return float(m.group(1))
    return None


def run_js_file(fpath: str) -> Result:
    """用 node 执行单个 JS 测试文件"""
    result: Result = {
        "test": relpath(fpath), "lang": "JavaScript", "status": "PASS",
        "detail": "", "time": 0,
    }
    start = time.time()
    try:
        proc = subprocess.run(["node", fpath], cwd=PROJECT_ROOT,
                              capture_output=True, timeout=JS_TIMEOUT)
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        result["detail"] = "timeout >%ds" % JS_TIMEOUT
        result["time"] = JS_TIMEOUT
        return result
    except FileNotFoundError:
        result["status"] = "ERROR"
        result["detail"] = "node not found"
        return result

    output = decode(proc.stdout) + decode(proc.stderr)
    result["time"] = round(time.time() - start, 2)
    if proc.returncode != 0:
        result["status"] = "FAIL"
        result["output"] = output.strip()[-4000:]
    return result


def run_js_suite(files: Sequence[str]) -> List[Result]:
    if not files:
        return []
    if shutil.which("node") is None:
        sys.stderr.write("run_tests: 未找到 node, 跳过 JavaScript 测试\n")
        return [{"test": "node", "lang": "JavaScript", "status": "SKIP",
                 "detail": "node not found", "time": 0}]
    return [run_js_file(f) for f in files]


def print_result(r: Result) -> None:
    icon = "PASS" if r["status"] == "PASS" else r["status"]
    line = "  [%s] %-10s %s" % (icon, r["lang"], r["test"])
    if r["time"]:
        line += "  (%.2fs)" % r["time"]
    print(line)
    if r.get("coverage") is not None:
        print("         coverage: %s%%" % r["coverage"])
    if r.get("output"):
        print(r["output"])


def write_report(results: Sequence[Result], coverage: Optional[float]) -> str:
    """写出 JSON 报告, 返回报告路径"""
    passed = sum(1 for r in results if r["status"] == "PASS")
    report = {
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "coverage": coverage,
        },
        "results": list(results),
    }
    path = os.path.join(PROJECT_ROOT, DEFAULT_REPORT)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2, ensure_ascii=False)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Duck Rush 测试入口: 自动发现并运行 Python(pytest + coverage) "
                    "与 JavaScript(node) 测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/run_tests.py                 # 全量测试(含覆盖率)\n"
            "  python scripts/run_tests.py tests/python    # 只跑指定目录/文件\n"
            "  python scripts/run_tests.py -k dir_util     # 按用例名过滤\n"
            "  python scripts/run_tests.py --no-js --html  # 只跑 Python 并生成 HTML 报告\n"
            "  python scripts/run_tests.py --no-coverage -v  # 关覆盖率, 显示详细输出\n\n"
            "默认统计覆盖率的源码目录: " + ", ".join(DEFAULT_COV_SOURCES) + "\n"
            "覆盖率报告: 终端输出 + " + DEFAULT_REPORT + " (--html 时额外生成 "
            + HTML_COV_DIR + "/)"
        ),
    )
    parser.add_argument("paths", nargs="*",
                        help="只运行指定的测试文件或目录(默认自动发现全量测试)")
    parser.add_argument("-k", "--keyword", default=None, metavar="EXPR",
                        help="按 pytest -k 表达式过滤用例")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示 pytest 详细输出(单条用例级别)")
    parser.add_argument("-x", "--fail-fast", action="store_true",
                        help="首次失败即停止")
    parser.add_argument("--no-coverage", action="store_true",
                        help="不统计覆盖率(可略微加速)")
    parser.add_argument("--no-js", action="store_true", help="跳过 JavaScript 测试")
    parser.add_argument("--no-python", action="store_true", help="跳过 Python 测试")
    parser.add_argument("--html", action="store_true",
                        help="额外生成 HTML 覆盖率报告(htmlcov/)")
    parser.add_argument("--exclude", action="append", default=None, metavar="DIR",
                        help="额外排除的目录(可重复或用逗号分隔, 如 --exclude docs,lib)")
    return parser


def split_dirs(values: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    for value in values or []:
        result += [p.strip() for p in value.split(",") if p.strip()]
    return result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    args.coverage = not args.no_coverage
    excludes = split_dirs(args.exclude)

    if args.paths:
        all_files = resolve_paths(args.paths)
        py_files = [f for f in all_files if is_python_test(f)]
        js_files = [f for f in all_files if is_js_test(f)]
    else:
        py_files = discover_tests("python", excludes)
        js_files = discover_tests("js", excludes)

    print("=" * 60)
    print("  Duck Rush - Test Runner")
    print("=" * 60)
    print("  Python: %d files   JavaScript: %d files   coverage: %s"
          % (len(py_files), len(js_files), "on" if args.coverage else "off"))

    results: List[Result] = []
    if not args.no_python:
        print("\n--- Python (pytest) ---")
        results.append(run_python_suite(py_files, args))
    if not args.no_js:
        print("\n--- JavaScript (node) ---")
        results.extend(run_js_suite(js_files))

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for r in results:
        print_result(r)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = len(results) - passed
    coverage: Optional[float] = None
    for r in results:
        if r.get("coverage") is not None:
            coverage = r["coverage"]
    print("\n  Total: %d  |  Pass: %d  |  Fail: %d  |  Coverage: %s"
          % (len(results), passed, failed,
             "%.2f%%" % coverage if coverage is not None else "n/a"))

    report_path = write_report(results, coverage)
    print("  Report: %s" % report_path)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
