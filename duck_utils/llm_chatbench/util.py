# -*- coding: utf-8 -*-
"""文本处理小工具: 代码块/JSON 提取、thinking 标签剥离、文本归一化。"""

import json
import re
from typing import Any, Dict, List, Optional

_THINK_RE = re.compile(r'<(?:think|thinking|reasoning)>.*?</(?:think|thinking|reasoning)>',
                       re.S | re.I)
_OPEN_THINK_RE = re.compile(r'^<(?:think|thinking|reasoning)>.*$', re.S | re.I)
_FENCE_RE = re.compile(r'```([a-zA-Z0-9_+-]*)\s*\n(.*?)```', re.S)


def strip_thinking(text: str) -> str:
    """剥离推理模型的 <think>...</think> 内容, 只保留给用户的可见回复。

    部分模型在内容被 num_predict 截断时只给出未闭合的 <think> 段,
    此时返回空串, 由调用方记为无有效回复。
    """
    if not text:
        return ''
    cleaned = _THINK_RE.sub('', text)
    if _OPEN_THINK_RE.match(cleaned.strip()):
        return ''
    # 未闭合标签: 取最后一个 </think> 之后的内容
    if '</think>' in cleaned.lower():
        lower = cleaned.lower()
        cleaned = cleaned[lower.rfind('</think>') + len('</think>'):]
    return cleaned.strip()


def normalize(text: str) -> str:
    """归一化用于关键词匹配: 小写、去空白与常见全半角标点。"""
    if not text:
        return ''
    s = text.lower()
    for ch in (' ', '\t', '\r', '\n', '，', '。', '、', '；', '：', '！',
               '？', '（', '）', '(', ')', '[', ']', '【', '】', '"', "'",
               '`', '*', '～', '~', ',', '.', ':', ';', '!', '?'):
        s = s.replace(ch, '')
    return s


def extract_code_blocks(text: str, lang: str = 'python') -> List[str]:
    """提取 markdown 代码块。lang 为空时提取所有带围栏的代码块。"""
    blocks = []
    for m in _FENCE_RE.finditer(text or ''):
        tag = (m.group(1) or '').strip().lower()
        if lang and tag and tag != lang.lower():
            continue
        blocks.append(m.group(2).strip())
    return blocks


def extract_json(text: str) -> Optional[Any]:
    """从回复里抽取第一个完整 JSON 对象/数组, 兼容 markdown 围栏。"""
    if not text:
        return None
    candidates: List[str] = []
    for block in extract_code_blocks(text, lang='json'):
        candidates.append(block)
    for block in extract_code_blocks(text, lang=''):
        candidates.append(block)
    candidates.append(text)
    for raw in candidates:
        s = raw.strip()
        if s.lower().startswith('json') and len(s) > 4 and s[4].isspace():
            s = s[4:].strip()
        # 依次尝试对象与数组
        for left, right in (('{', '}'), ('[', ']')):
            start = s.find(left)
            end = s.rfind(right)
            if start == -1 or end <= start:
                continue
            try:
                return json.loads(s[start:end + 1])
            except Exception:
                continue
    return None


def json_get(obj: Any, path: str) -> Any:
    """按点号路径取 JSON 值, 取不到返回 None。"""
    cur = obj
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}
