# -*- coding: utf-8 -*-
"""duck-cli 的命令别名支持。

- 内置默认别名(DEFAULT_ALIASES)开箱可用, 如 `ll` = `duck-ls -lh --color`
- 用户用 `alias name="cmd"` / `unalias name` 增删, 持久化到
  ~/.duck-rush/data/duck-cli/aliases.jsonl
- 删除内置别名时写入墓碑记录(cmd 为 null), 使删除在重启后依然生效
- 展开只作用于命令行的首个 token, 采用 bash 语义: 同一个别名名不会被重复展开,
  因此 `alias ls="ls -l"` 这类自引用不会无限递归

本模块以 `_util.py` 结尾, 不会被 install.py 注册成独立命令。
"""
import os
from typing import Dict, List, Optional, Set, Tuple

from duck_utils.jsonl_util import JsonlStore
from duck_utils.os_util import is_windows

# 展开的最大轮数, 防御异常情况下的死循环(正常情况下 seen 集合已足够)
MAX_EXPAND_DEPTH = 10


def build_default_aliases() -> Dict[str, str]:
    """内置默认别名。

    Windows 上没有原生 ls, 所以额外把 ls 指向 duck-ls;
    unix 平台保留功能更完整的系统 ls 不做覆盖。
    """
    aliases = {
        "ll": "duck-ls -lh --color",
    }
    if is_windows():
        aliases["ls"] = "duck-ls --color"
    return aliases


DEFAULT_ALIASES = build_default_aliases()


def parse_assign(text: str) -> Optional[Tuple[str, str]]:
    """解析 `name=cmd` 形式的赋值, 返回 (name, cmd); 不是赋值则返回 None。

    cmd 外围的成对单/双引号会被剥掉。

    >>> parse_assign('ll="duck-ls -lh"')
    ('ll', 'duck-ls -lh')
    >>> parse_assign("gs='git status'")
    ('gs', 'git status')
    >>> parse_assign("k=duck-ls")
    ('k', 'duck-ls')
    >>> parse_assign("ll") is None
    True
    >>> parse_assign("=x") is None
    True
    """
    if "=" not in text:
        return None
    name, _, value = text.partition("=")
    name = name.strip()
    if not name:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return name, value


def format_alias(name: str, cmd: str) -> str:
    """按 bash 风格格式化一条别名, 便于直接复制使用。

    >>> format_alias("ll", "duck-ls -lh --color")
    "alias ll='duck-ls -lh --color'"
    """
    return "alias %s='%s'" % (name, cmd)


class AliasError(Exception):
    """别名操作失败(名称非法、保存失败等)。"""


class AliasStore:
    """别名的读写与展开。

    生效别名 = 内置默认别名 叠加 用户自定义, 再剔除被墓碑标记删除的名字。
    """

    def __init__(self, path: str, defaults: Optional[Dict[str, str]] = None) -> None:
        self.path = path
        self._defaults = dict(DEFAULT_ALIASES if defaults is None else defaults)
        self._store = JsonlStore(path)
        # 用户自定义: name -> cmd; cmd 为 None 表示墓碑(删除内置别名)
        self._user: Dict[str, Optional[str]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """读取磁盘记录; 文件损坏/缺失时退化为「只有内置别名」, 不影响 shell 启动。"""
        self._user = {}
        try:
            records = self._store.read_all()
        except OSError:
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            name = record.get("name")
            if not isinstance(name, str) or not name:
                continue
            cmd = record.get("cmd")
            self._user[name] = cmd if isinstance(cmd, str) else None

    def _save(self) -> None:
        records = []
        for name in sorted(self._user):
            records.append({"name": name, "cmd": self._user[name]})
        try:
            self._store.write_all(records, atomic=True)
        except OSError as e:
            raise AliasError("保存别名失败: %s" % e)

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def all(self) -> Dict[str, str]:
        """返回当前生效的全部别名。"""
        result = dict(self._defaults)
        for name, cmd in self._user.items():
            if cmd is None:
                # 墓碑: 内置别名被用户删除
                result.pop(name, None)
            else:
                result[name] = cmd
        return result

    def get(self, name: str) -> Optional[str]:
        return self.all().get(name)

    def names(self) -> List[str]:
        return sorted(self.all())

    # ------------------------------------------------------------------ #
    # 修改
    # ------------------------------------------------------------------ #
    def set(self, name: str, cmd: str) -> None:
        """新增/覆盖一个别名并持久化。"""
        if not name or "=" in name or any(c.isspace() for c in name):
            raise AliasError("别名名称非法: %s" % name)
        if not cmd.strip():
            raise AliasError("别名内容不能为空")
        self._user[name] = cmd
        self._save()

    def remove(self, name: str) -> bool:
        """删除别名; 返回是否真的删掉了什么。

        删除内置别名时保留墓碑记录, 否则重启后它又会冒出来。
        """
        if name not in self.all():
            return False
        if name in self._defaults:
            self._user[name] = None  # 墓碑
        else:
            self._user.pop(name, None)
        self._save()
        return True

    # ------------------------------------------------------------------ #
    # 展开
    # ------------------------------------------------------------------ #
    def expand(self, cmd: str) -> str:
        """展开命令行首个 token 的别名, 其余部分原样保留。

        采用 bash 语义: 已展开过的别名名不再二次展开, 因此 `alias ls="ls -l"`
        只会展开一次, 不会死循环。
        """
        aliases = self.all()
        seen: Set[str] = set()
        result = cmd
        for _ in range(MAX_EXPAND_DEPTH):
            stripped = result.lstrip()
            if not stripped:
                return result
            name, sep, rest = stripped.partition(" ")
            if name in seen or name not in aliases:
                return result
            seen.add(name)
            replacement = aliases[name]
            result = replacement + sep + rest if sep else replacement
        return result


def get_default_store_path(data_dir: str) -> str:
    """别名文件路径: {data_dir}/aliases.jsonl。"""
    return os.path.join(data_dir, "aliases.jsonl")
