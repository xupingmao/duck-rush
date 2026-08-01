# encoding=utf-8
"""duck-rush 安装元数据 (~/.duck-rush/duck.json) 的读写与结构定义。

把 duck.json 的相关操作集中到 duck_utils, 便于 duck-rush 内其它命令复用,
不再各自用 dict 裸操作。结构由 InstallMeta 类描述, 加载/保存/外部目录管理
等方法都挂在该类上。
"""
import os
import json
from dataclasses import dataclass, field
from typing import List

from duck_utils.os_util import get_duck_rush_home


@dataclass
class InstallMeta:
    """~/.duck-rush/duck.json 的安装元数据。

    version:            元数据格式版本
    install_dir:        用户级安装根目录 (~/.duck-rush)
    bin_dir:            命令包装脚本目录 (~/.duck-rush/bin)
    data_dir:           命令运行时数据根目录 (~/.duck-rush/data)
    python:             虚拟环境 Python 解释器的绝对路径
    src_dir:            duck-rush 源码目录 (仓库内 duck_rush/)
    external_src_dirs:  已登记的外部工具源码目录列表
    """

    version: str = "1.0"
    install_dir: str = ""
    bin_dir: str = ""
    data_dir: str = ""
    python: str = ""
    src_dir: str = ""
    external_src_dirs: List[str] = field(default_factory=list)

    @classmethod
    def meta_path(cls) -> str:
        """返回 duck.json 的绝对路径。"""
        return os.path.join(get_duck_rush_home(), "duck.json")

    @classmethod
    def load(cls) -> "InstallMeta":
        """读取 duck.json; 文件不存在或损坏时返回默认值实例。"""
        path = cls.meta_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls(
            version=str(data.get("version", "1.0")),
            install_dir=str(data.get("install_dir", "")),
            bin_dir=str(data.get("bin_dir", "")),
            data_dir=str(data.get("data_dir", "")),
            python=str(data.get("python", "")),
            src_dir=str(data.get("src_dir", "")),
            external_src_dirs=[str(d) for d in (data.get("external_src_dirs") or [])],
        )

    def to_dict(self) -> dict:
        """序列化为可写盘的 dict。"""
        return {
            "version": self.version,
            "install_dir": self.install_dir,
            "bin_dir": self.bin_dir,
            "data_dir": self.data_dir,
            "python": self.python,
            "src_dir": self.src_dir,
            "external_src_dirs": list(self.external_src_dirs),
        }

    def save(self) -> None:
        """写回 duck.json (父目录不存在则自动创建)。"""
        path = self.meta_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def add_external_src_dir(self, d: str) -> bool:
        """追加外部工具源码目录 (按绝对路径去重)。

        返回是否发生了新增; 已存在则返回 False。调用方应自行校验目录存在性。
        """
        d = os.path.abspath(os.path.expanduser(d))
        if d in self.external_src_dirs:
            return False
        self.external_src_dirs.append(d)
        return True

    def get_external_src_dirs(self) -> List[str]:
        """返回已登记且仍然存在的外部工具源码目录。"""
        return [d for d in self.external_src_dirs if os.path.isdir(d)]
