# -*- coding:utf-8 -*-
# @filename duck_utils/find_assign/__init__.py
# @description 赋值搜索子模块的公共 API 导出。
#
# 设计: 命名变体(name) / 语言插件(lang) / 搜索引擎(engine) 三层高内聚低耦合,
# 引擎只依赖 LanguagePlugin 接口与 NameVariants, 不内含任何语言规则。

from duck_utils.find_assign.name import NameVariants, split_words
from duck_utils.find_assign.lang import (
    GENERIC_PLUGIN,
    KNOWN_EXTENSIONS,
    LanguagePlugin,
    get_plugin_by_ext,
    get_plugin_by_name,
    list_lang_names,
)
from duck_utils.find_assign.engine import AssignmentFinder, DEFAULT_MAX_SIZE

__all__ = [
    "NameVariants",
    "split_words",
    "GENERIC_PLUGIN",
    "KNOWN_EXTENSIONS",
    "LanguagePlugin",
    "get_plugin_by_ext",
    "get_plugin_by_name",
    "list_lang_names",
    "AssignmentFinder",
    "DEFAULT_MAX_SIZE",
]
