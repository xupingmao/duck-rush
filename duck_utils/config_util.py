# -*- coding: utf-8 -*-
"""分层配置管理 (项目级 {cwd}/.duck-rush.json + 全局 ~/.duck-rush/config.json)

配置分两层, 均为 JSON 格式:

* 项目级 (project): {cwd}/.duck-rush.json, 默认写入层, 只认当前工作目录不做向上查找
* 全局级 (global):  ~/.duck-rush/config.json, 需显式指定 (对应 CLI 的 --global)

读取时两层浅合并 (项目级同名键覆盖全局级), 即"生效值"。
键是扁平字符串, 不支持 `a.b` 形式的嵌套, 点号按字面处理。

边界约定:

* 文件不存在 / JSON 损坏 / 顶层不是对象时按空配置处理, 并且**不会**自动改写用户的文件
* `null` 是合法值, 只有 unset 才删键, 判断键是否存在一律用 `key in data`
* 写入采用原子写 (同目录临时文件 + os.replace), 多进程并发时后写者胜出
"""
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

from duck_utils.os_util import get_duck_rush_home

SCOPE_PROJECT = "project"
SCOPE_GLOBAL = "global"
SCOPE_MERGED = "merged"

CONFIG_FILE_NAME = ".duck-rush.json"
GLOBAL_CONFIG_NAME = "config.json"

# 布尔值文本 -> bool, 用于 `--type bool`
BOOL_TRUE_TEXT = ("1", "true", "yes", "y", "on")
BOOL_FALSE_TEXT = ("0", "false", "no", "n", "off")


class ConfigFile:
    """单个 JSON 配置文件的读写封装"""

    def __init__(self, path: str) -> None:
        self.path = path

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def load(self) -> Dict[str, Any]:
        """读取配置; 文件不存在/损坏/顶层不是对象时返回空 dict (并提示到 stderr)"""
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, ValueError) as ex:
            sys.stderr.write("配置文件无法解析, 按空配置处理: %s (%s)\n" % (self.path, ex))
            return {}
        if not isinstance(data, dict):
            sys.stderr.write("配置文件顶层不是对象, 按空配置处理: %s\n" % self.path)
            return {}
        return data

    def save(self, data: Dict[str, Any]) -> None:
        """原子写入: 先写同目录的临时文件再 os.replace, 避免写入过程中文件损坏"""
        dirname = os.path.dirname(self.path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dirname, prefix=".duck-rush.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2, sort_keys=True)
                fp.write("\n")
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


def get_project_path(cwd: Optional[str] = None) -> str:
    """返回项目级配置路径 {cwd}/.duck-rush.json"""
    return os.path.join(cwd or os.getcwd(), CONFIG_FILE_NAME)


def get_global_path() -> str:
    """返回全局级配置路径 ~/.duck-rush/config.json"""
    return os.path.join(get_duck_rush_home(), GLOBAL_CONFIG_NAME)


def resolve_path(scope: str, cwd: Optional[str] = None) -> str:
    """按 scope 返回配置文件路径; merged 视作 project"""
    if scope == SCOPE_GLOBAL:
        return get_global_path()
    return get_project_path(cwd)


def load_scope(scope: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """读取单层配置的全部键值"""
    return ConfigFile(resolve_path(scope, cwd)).load()


def load_merged(cwd: Optional[str] = None) -> Dict[str, Any]:
    """读取两层合并后的配置 (项目级同名键覆盖全局级)"""
    merged: Dict[str, Any] = dict(load_scope(SCOPE_GLOBAL, cwd))
    merged.update(load_scope(SCOPE_PROJECT, cwd))
    return merged


def load_merged_with_source(cwd: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """读取两层合并后的配置, 并标注每个键来自哪一层

    返回 {key: {"value": 值, "scope": 层级}}
    """
    result: Dict[str, Dict[str, Any]] = {}
    for key, value in load_scope(SCOPE_GLOBAL, cwd).items():
        result[key] = {"value": value, "scope": SCOPE_GLOBAL}
    for key, value in load_scope(SCOPE_PROJECT, cwd).items():
        result[key] = {"value": value, "scope": SCOPE_PROJECT}
    return result


def parse_value(text: str) -> Any:
    """把文本解析成配置值: 能按 JSON 解析则取其值, 否则原样作为字符串

    `123` -> 123, `true` -> True, `[1,2]` -> [1,2], `null` -> None, `abc` -> "abc"
    """
    try:
        return json.loads(text)
    except ValueError:
        return text


def convert_value(text: str, type_name: str = "auto") -> Any:
    """按指定类型把命令行文本转换成配置值

    auto  : 先按 JSON 解析, 失败则按字符串 (见 parse_value)
    str   : 原样作为字符串
    int/float/bool/json : 强制转换, 失败时抛 ValueError
    """
    if type_name == "auto":
        return parse_value(text)
    if type_name == "str":
        return text
    if type_name == "json":
        return json.loads(text)
    if type_name == "int":
        return int(text)
    if type_name == "float":
        return float(text)
    if type_name == "bool":
        return _parse_bool(text)
    raise ValueError("未知的值类型: %s" % type_name)


def _parse_bool(text: str) -> bool:
    lower = text.strip().lower()
    if lower in BOOL_TRUE_TEXT:
        return True
    if lower in BOOL_FALSE_TEXT:
        return False
    raise ValueError("无法解析为布尔值: %s (可用 1/true/yes/on/0/false/no/off)" % text)


def format_value(value: Any) -> str:
    """把配置值格式化成一行文本: 字符串原样输出, 其余按 JSON 输出"""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def get_value(key: str, default: Any = None, cwd: Optional[str] = None) -> Any:
    """读取合并后的生效值; 键不存在时返回 default"""
    data = load_merged(cwd)
    if key in data:
        return data[key]
    return default


def set_value(
        key: str,
        value: Any,
        scope: str = SCOPE_PROJECT,
        cwd: Optional[str] = None,
) -> None:
    """写入单个键值到指定层 (默认项目级)"""
    conf = ConfigFile(resolve_path(scope, cwd))
    data = conf.load()
    data[key] = value
    conf.save(data)


def unset_value(
        key: str,
        scope: str = SCOPE_PROJECT,
        cwd: Optional[str] = None,
) -> bool:
    """删除指定层的键; 返回是否真的删除了 (键不存在时返回 False)"""
    conf = ConfigFile(resolve_path(scope, cwd))
    data = conf.load()
    if key not in data:
        return False
    del data[key]
    conf.save(data)
    return True


def import_values(
        data: Dict[str, Any],
        scope: str = SCOPE_PROJECT,
        cwd: Optional[str] = None,
        overwrite: bool = True,
) -> int:
    """把一组键值合并写入指定层, 返回实际写入的键数量

    overwrite=False 时保留该层已存在的键 (不覆盖)。
    """
    if not data:
        return 0
    conf = ConfigFile(resolve_path(scope, cwd))
    target = conf.load()
    count = 0
    for key, value in data.items():
        if not overwrite and key in target:
            continue
        target[key] = value
        count += 1
    if count:
        conf.save(target)
    return count


def list_keys(cwd: Optional[str] = None) -> List[str]:
    """返回合并后配置的全部键 (按字典序)"""
    return sorted(load_merged(cwd).keys())
