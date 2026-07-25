# -*- coding: utf-8 -*-
# JSONL(每行一个 JSON 对象)通用读写工具。
#
# 适用于各类「追加式 / 整体重写式」的持久化场景，例如：
#   - duck-shell 的收藏夹(bookmarks.jsonl)
#   - duck-shell 的命令历史(history.jsonl)
#   - duck-remind 的提醒数据(reminders.jsonl)
#
# 设计原则：JsonlStore 只负责「文件 <-> list[dict]」这一层，
# 不关心具体业务字段；字段映射(如 Bookmark / Reminder)留在各自的 DAO 中。
import json
import os


class JsonlStore:
    """管理一个 JSONL 文件：逐行存储 JSON 对象。

    特性：
    - 文件 / 父目录不存在时自动创建；
    - 读取时跳过空行与非法 JSON 行（容错，不因单行损坏而整体失败）；
    - write_all 可选 max_records 上限，超出时仅保留末尾若干条；
    - write_all 可选 atomic=True，先写临时文件再 os.replace，避免半写损坏。
    """

    def __init__(self, path, *, max_records=None):
        self.path = path
        self.max_records = max_records

    def _ensure_parent(self):
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def read_all(self):
        """读取全部记录，返回 dict 列表（已跳过空行 / 非法 JSON 行）。"""
        if not os.path.exists(self.path):
            return []
        records = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def append(self, record):
        """追加一条记录（dict）。"""
        self._ensure_parent()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_all(self, records, *, max_records=None, atomic=False):
        """整体重写全部记录。

        Args:
            records: 待写入的 dict 列表。
            max_records: 上限；超出时仅保留末尾若干条（默认取构造时的设定）。
            atomic: True 时先写临时文件再 os.replace，避免写入过程中文件损坏。
        """
        cap = self.max_records if max_records is None else max_records
        if cap is not None and len(records) > cap:
            records = records[-cap:]
        self._ensure_parent()
        if atomic:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        else:
            with open(self.path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
