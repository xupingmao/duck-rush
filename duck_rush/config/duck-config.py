# -*- coding: utf-8 -*-
'''
duck-config - 分层配置管理 (项目级 {cwd}/.duck-rush.json + 全局 ~/.duck-rush/config.json)

配置分两层, 读取时合并, 项目级同名键覆盖全局级:

* 项目级 (project): 当前目录下的 .duck-rush.json, 默认写入层 (只认当前目录, 不向上查找)
* 全局级 (global):  ~/.duck-rush/config.json, 加 --global 指定

用法:
    duck-config get <KEY> [--scope 层级] [--json]
    duck-config set <KEY> <VALUE> [--global] [--type 类型]
    duck-config unset <KEY> [--global]
    duck-config list [--scope 层级] [--json] [--source]
    duck-config where [--global]
    duck-config edit [--global]
    duck-config import <FILE> [--global] [--keep]
    duck-config export [FILE] [--scope 层级]

示例:
    duck-config set name duck                 # 项目级写入 name = "duck"
    duck-config set port 8080                 # 数字 8080 (JSON 自动解析)
    duck-config set debug true                # 布尔 true
    duck-config set ver 1.0 --type str        # 强制存为字符串 "1.0"
    duck-config get port                      # 读生效值 (项目级优先)
    duck-config list --source                 # 列出全部并标注来源层
    duck-config set editor code --global      # 写入全局配置
    duck-config unset port                    # 只删项目级, 全局残留会提示
    duck-config where                         # 查看两层配置文件路径
    duck-config edit                          # 用编辑器打开项目级配置
    duck-config export backup.json            # 导出合并后的配置
    duck-config import backup.json            # 合并导入 (同名键覆盖)
    cat backup.json | duck-config import -    # 从标准输入导入

说明:
    - 各子命令加 -h 可查看详细参数, 如: duck-config set -h
    - -h/--help 仅打印帮助并以 0 退出, 不读写配置、不创建文件
    - get/list/export 默认看合并后的生效值; set/unset/import/edit 默认操作项目级
    - 值默认按 JSON 自动解析 (123/true/[1,2]/null), 想原样存字符串用 --type str
    - unset 只删一层, 若另一层仍有同名键会给出提示
'''
import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

try:
    from duck_utils import config_util, os_util
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)

from termcolor import colored


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duck-config",
        description="分层配置管理: 项目级 .duck-rush.json + 全局 ~/.duck-rush/config.json")
    sub = parser.add_subparsers(dest="command")

    def new_parser(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(
            name, help=help_text,
            formatter_class=argparse.RawDescriptionHelpFormatter)

    def add_scope_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--scope", default=config_util.SCOPE_MERGED,
                       choices=[config_util.SCOPE_MERGED,
                                config_util.SCOPE_PROJECT,
                                config_util.SCOPE_GLOBAL],
                       help="读取的层级, 默认 %(default)s (合并后的生效值)")

    p_get = new_parser("get", "读取配置值")
    p_get.add_argument("key", help="配置键")
    add_scope_arg(p_get)
    p_get.add_argument("--json", action="store_true", help="按 JSON 输出原始值")
    p_get.set_defaults(func=cmd_get)

    p_set = new_parser("set", "写入配置值 (默认项目级)")
    p_set.add_argument("key", help="配置键")
    p_set.add_argument("value", help="配置值")
    p_set.add_argument("-g", "--global", action="store_true", dest="global_",
                       help="写入全局配置 (~/.duck-rush/config.json)")
    p_set.add_argument("--type", default="auto",
                       choices=["auto", "str", "int", "float", "bool", "json"],
                       help="值的类型, 默认 %(default)s (按 JSON 自动解析)")
    p_set.set_defaults(func=cmd_set)

    p_unset = new_parser("unset", "删除配置项 (默认项目级)")
    p_unset.add_argument("key", help="配置键")
    p_unset.add_argument("-g", "--global", action="store_true", dest="global_",
                         help="删除全局配置中的键")
    p_unset.set_defaults(func=cmd_unset)

    p_list = new_parser("list", "列出配置")
    add_scope_arg(p_list)
    p_list.add_argument("--json", action="store_true", help="按 JSON 输出")
    p_list.add_argument("--source", action="store_true",
                        help="标注每个键来自哪一层 (始终展示合并结果)")
    p_list.set_defaults(func=cmd_list)

    p_where = new_parser("where", "打印配置文件路径")
    p_where.add_argument("-g", "--global", action="store_true", dest="global_",
                         help="只打印全局配置路径")
    p_where.set_defaults(func=cmd_where)

    p_edit = new_parser("edit", "用编辑器打开配置文件 (默认项目级)")
    p_edit.add_argument("-g", "--global", action="store_true", dest="global_",
                        help="编辑全局配置")
    p_edit.set_defaults(func=cmd_edit)

    p_import = new_parser("import", "导入配置 (默认合并到项目级)")
    p_import.add_argument("file", help="JSON 文件路径, `-` 表示从标准输入读取")
    p_import.add_argument("-g", "--global", action="store_true", dest="global_",
                          help="导入到全局配置")
    p_import.add_argument("-k", "--keep", action="store_true",
                          help="保留已存在的键 (默认同名键覆盖)")
    p_import.set_defaults(func=cmd_import)

    p_export = new_parser("export", "导出配置 (默认合并后的生效值)")
    p_export.add_argument("file", nargs="?", default=None,
                          help="输出文件, 省略则打印到标准输出")
    add_scope_arg(p_export)
    p_export.set_defaults(func=cmd_export)

    return parser


def scope_of(args: argparse.Namespace) -> str:
    """按 --global 判定写入/操作层级"""
    if getattr(args, "global_", False):
        return config_util.SCOPE_GLOBAL
    return config_util.SCOPE_PROJECT


def load_by_scope(scope: str) -> Dict[str, Any]:
    if scope == config_util.SCOPE_MERGED:
        return config_util.load_merged()
    return config_util.load_scope(scope)


def colored_key(key: str) -> str:
    return colored(key, "cyan")


def colored_value(value: Any) -> str:
    return colored(config_util.format_value(value), "green")


def cmd_get(args: argparse.Namespace) -> None:
    data = load_by_scope(args.scope)
    if args.key not in data:
        sys.stderr.write("配置键不存在: %s (可用 `duck-config list` 查看)\n" % args.key)
        sys.exit(1)
    value = data[args.key]
    if args.json:
        print(json.dumps(value, ensure_ascii=False))
    else:
        print(config_util.format_value(value))


def cmd_set(args: argparse.Namespace) -> None:
    try:
        value = config_util.convert_value(args.value, args.type)
    except ValueError as ex:
        sys.stderr.write("配置值转换失败: %s\n" % ex)
        sys.exit(1)

    scope = scope_of(args)
    path = config_util.resolve_path(scope)
    existed = os.path.exists(path)
    config_util.set_value(args.key, value, scope)

    if not existed and scope == config_util.SCOPE_PROJECT:
        print("已在当前目录创建 %s" % config_util.CONFIG_FILE_NAME)
    print("已设置 %s = %s (%s)" % (
        colored_key(args.key), colored_value(value), scope))


def cmd_unset(args: argparse.Namespace) -> None:
    scope = scope_of(args)
    if not config_util.unset_value(args.key, scope):
        sys.stderr.write("配置键不存在: %s (可用 `duck-config list` 查看)\n" % args.key)
        sys.exit(1)

    print("已删除 %s (%s)" % (colored_key(args.key), scope))

    other = (config_util.SCOPE_GLOBAL if scope == config_util.SCOPE_PROJECT
             else config_util.SCOPE_PROJECT)
    if args.key in config_util.load_scope(other):
        print(colored("注意: %s 配置中仍存在 %s, 它现在是生效值" % (other, args.key), "yellow"))


def cmd_list(args: argparse.Namespace) -> None:
    if args.json:
        print(json.dumps(load_by_scope(args.scope), ensure_ascii=False,
                         indent=2, sort_keys=True))
        return

    if args.source:
        entries = [(key, item["value"], item["scope"])
                   for key, item in config_util.load_merged_with_source().items()]
    else:
        entries = [(key, value, None)
                   for key, value in load_by_scope(args.scope).items()]

    if not entries:
        print("(无配置)")
        return

    entries.sort(key=lambda item: item[0])
    width = max(len(key) for key, _, _ in entries)
    for key, value, scope in entries:
        line = "%s = %s" % (colored(key.ljust(width), "cyan"),
                            colored_value(value))
        if scope is not None:
            line += colored("  [%s]" % scope, "yellow")
        print(line)


def cmd_where(args: argparse.Namespace) -> None:
    if getattr(args, "global_", False):
        print(config_util.get_global_path())
        return
    for scope, path in ((config_util.SCOPE_PROJECT, config_util.get_project_path()),
                        (config_util.SCOPE_GLOBAL, config_util.get_global_path())):
        state = "存在" if os.path.exists(path) else "不存在"
        print("%s: %s (%s)" % (colored(scope, "cyan"), path, state))


def cmd_edit(args: argparse.Namespace) -> None:
    scope = scope_of(args)
    path = config_util.resolve_path(scope)
    if not os.path.exists(path):
        config_util.ConfigFile(path).save({})
        print("已创建配置文件: %s" % path)

    cmd = build_editor_cmd(path)
    if subprocess.call(cmd) != 0:
        sys.stderr.write("编辑器启动失败: %s\n" % " ".join(cmd))
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as fp:
            json.load(fp)
    except ValueError as ex:
        sys.stderr.write("配置文件不是合法的 JSON, 已保留原文件: %s\n" % ex)
        sys.exit(1)
    print("已保存: %s" % path)


def build_editor_cmd(path: str) -> List[str]:
    """按平台选择打开配置文件的编辑器命令

    优先级: $VISUAL > $EDITOR > 平台默认 (Windows: code/notepad,
    macOS: open -t, Linux: xdg-open/vi)
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return editor.split() + [path]
    if os_util.is_windows():
        if shutil.which("code"):
            return ["code", path]
        return ["notepad", path]
    if os_util.is_mac():
        return ["open", "-t", path]
    if shutil.which("xdg-open"):
        return ["xdg-open", path]
    return ["vi", path]


def cmd_import(args: argparse.Namespace) -> None:
    if args.file == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(args.file, "r", encoding="utf-8") as fp:
                text = fp.read()
        except OSError as ex:
            sys.stderr.write("读取文件失败: %s\n" % ex)
            sys.exit(1)

    try:
        data = json.loads(text)
    except ValueError as ex:
        sys.stderr.write("导入失败, 不是合法的 JSON: %s\n" % ex)
        sys.exit(1)
    if not isinstance(data, dict):
        sys.stderr.write("导入失败: JSON 顶层必须是对象 (键值映射)\n")
        sys.exit(1)

    scope = scope_of(args)
    count = config_util.import_values(data, scope, overwrite=not args.keep)
    print("已导入 %s 项配置 -> %s" % (count, config_util.resolve_path(scope)))


def cmd_export(args: argparse.Namespace) -> None:
    data = load_by_scope(args.scope)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    if not args.file:
        print(text)
        return
    with open(args.file, "w", encoding="utf-8") as fp:
        fp.write(text + "\n")
    print("已导出 %s 项配置 -> %s" % (len(data), args.file))


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    # -h/--help 不得产生副作用(不创建配置文件), 直接打印用法后退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    main()
