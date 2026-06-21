# -*- coding:utf-8 -*-
# @author xupingmao
# @since 2021/12/25 12:07:39
# @modified 2021/12/26 21:18:19
# @filename duck-init-project.py

import os
import sys
import argparse


PYTHON_GITIGNORE = """\
__pycache__/
*.pyc
*.pyo
.env
.venv
dist/
build/
*.egg-info/
"""

GO_GITIGNORE = """\
*.exe
*.out
*.test
vendor/
"""

PYTHON_SETUP_PY = """\
from setuptools import setup, find_packages

setup(
    name="%(name)s",
    version="0.1.0",
    packages=find_packages(),
)
"""

REQUIREMENTS_TXT = """\
# %(name)s dependencies
"""

PYTHON_MAIN = """\
def main():
    print("Hello from %(name)s!")


if __name__ == "__main__":
    main()
"""

PYTHON_TEST = """\
from %(name)s import main


def test_main():
    assert main is not None
"""

GO_MAIN = """\
package main

import (
    "fmt"
    "%(name)s/internal/app"
)

func main() {
    fmt.Println(app.Greeting())
}
"""

GO_APP = """\
package app

func Greeting() string {
    return "Hello from %(name)s!"
}
"""

GO_HELLO = """\
package hello

func Version() string {
    return "0.1.0"
}
"""

MAKEFILE = """\
.PHONY: run test clean

run:
	python -m %(name)s.main

test:
	python -m pytest tests/

clean:
	rm -rf __pycache__ .pytest_cache
"""

GO_MAKEFILE = """\
.PHONY: run test clean build

run:
	go run ./cmd/%(name)s/

test:
	go test ./...

build:
	go build -o bin/%(name)s ./cmd/%(name)s/

clean:
	rm -rf bin/
"""

README_TEMPLATE = """\
# %(name)s

## Usage

...

## License
"""


def create_file(filepath: str, content: str, context: dict) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content % context)
    print("  created %s" % filepath)


def init_python(project_dir: str, name: str) -> None:
    ctx = {"name": name}
    pkg_dir = os.path.join(project_dir, name)
    test_dir = os.path.join(project_dir, "tests")

    create_file(os.path.join(project_dir, "README.md"), README_TEMPLATE, ctx)
    create_file(os.path.join(project_dir, ".gitignore"),
                PYTHON_GITIGNORE, ctx)
    create_file(os.path.join(project_dir, "setup.py"),
                PYTHON_SETUP_PY, ctx)
    create_file(os.path.join(project_dir, "requirements.txt"),
                REQUIREMENTS_TXT, ctx)
    create_file(os.path.join(project_dir, "Makefile"), MAKEFILE, ctx)
    create_file(os.path.join(pkg_dir, "__init__.py"), "", ctx)
    create_file(os.path.join(pkg_dir, "main.py"), PYTHON_MAIN, ctx)
    create_file(os.path.join(test_dir, "__init__.py"), "", ctx)
    create_file(os.path.join(test_dir, "test_main.py"), PYTHON_TEST, ctx)


def init_go(project_dir: str, name: str) -> None:
    ctx = {"name": name}
    cmd_dir = os.path.join(project_dir, "cmd", name)

    create_file(os.path.join(project_dir, "README.md"), README_TEMPLATE, ctx)
    create_file(os.path.join(project_dir, ".gitignore"), GO_GITIGNORE, ctx)
    create_file(os.path.join(project_dir, "Makefile"), GO_MAKEFILE, ctx)
    create_file(os.path.join(cmd_dir, "main.go"), GO_MAIN, ctx)
    create_file(os.path.join(project_dir, "internal", "app", "app.go"),
                GO_APP, ctx)
    create_file(os.path.join(project_dir, "pkg", "hello", "hello.go"),
                GO_HELLO, ctx)

    go_mod_path = os.path.join(project_dir, "go.mod")
    if not os.path.exists(go_mod_path):
        os.system(
            "cd \"%s\" && go mod init %s" % (project_dir, name))


LANG_HANDLERS = {
    "python": init_python,
    "go": init_go,
}


def main():
    parser = argparse.ArgumentParser(description="初始化软件开发项目")
    parser.add_argument("name", type=str, help="项目名称")
    parser.add_argument("--lang", type=str, default="python",
                        choices=list(LANG_HANDLERS.keys()),
                        help="编程语言（默认 python）")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.name)
    if os.path.exists(project_dir):
        print("错误: 目录已存在: %s" % project_dir, file=sys.stderr)
        sys.exit(1)

    os.makedirs(project_dir)
    print("初始化 %s 项目: %s" % (args.lang, project_dir))
    LANG_HANDLERS[args.lang](project_dir, args.name)
    print("完成!")


if __name__ == '__main__':
    main()
