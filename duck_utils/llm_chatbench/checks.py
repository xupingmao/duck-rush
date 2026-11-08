# -*- coding: utf-8 -*-
"""检查器: 对每一轮回复做可复现的规则判定。

刻意不使用"让另一个本地小模型当裁判"的做法 —— 小模型判分不稳定,
规则 + 状态断言才能横向对比, 且失败原因可以逐条追溯。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .model import CheckResult, CheckSpec, Scenario
from .sandbox import CodeSandbox, FileSandbox
from .util import extract_json, json_get, normalize


@dataclass
class CheckContext:
    """一次检查所需的全部上下文, 通过关键字构造。"""
    reply: str = ''
    no_reply: bool = False
    history: List[str] = field(default_factory=list)
    code: Optional[CodeSandbox] = None
    files: Optional[FileSandbox] = None
    feedback: Optional[str] = None
    turn_index: int = 0
    scenario: Optional[Scenario] = None


def _terms(spec: CheckSpec, key: str) -> List[str]:
    value = spec.args.get(key, [])
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v is not None]


def _check_contains(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    norm = normalize(ctx.reply)
    any_terms = _terms(spec, 'any')
    all_terms = _terms(spec, 'all')
    value = spec.args.get('value')
    if value is not None:
        all_terms = all_terms + [str(value)]
    if any_terms:
        hits = [t for t in any_terms if normalize(t) in norm]
        if not hits:
            return False, '未命中任一关键词: %s' % ', '.join(any_terms[:4])
    misses = [t for t in all_terms if normalize(t) not in norm]
    if misses:
        return False, '缺少关键词: %s' % ', '.join(misses[:4])
    if not any_terms and not all_terms:
        return False, '检查点未配置关键词'
    return True, '关键词命中'


def _check_not_contains(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    norm = normalize(ctx.reply)
    hits = [t for t in _terms(spec, 'any') if normalize(t) in norm]
    if hits:
        return False, '出现禁止内容: %s' % ', '.join(hits[:4])
    return True, '未出现禁止内容'


def _check_regex(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    pattern = str(spec.args.get('pattern', ''))
    if not pattern:
        return False, '缺少 pattern'
    try:
        found = re.search(pattern, ctx.reply, re.I | re.S) is not None
    except re.error as e:
        return False, '正则错误: %s' % e
    want = bool(spec.args.get('expect', True))
    return (found == want), ('匹配' if found else '未匹配') + ' %s' % pattern[:40]


def _check_json_object(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    obj = extract_json(ctx.reply)
    if obj is None:
        return False, '未解析到 JSON'
    if not isinstance(obj, dict):
        return False, 'JSON 顶层不是对象'
    for path in _terms(spec, 'required'):
        if json_get(obj, path) is None:
            return False, '缺少字段 %s' % path
    for path, expected in dict(spec.args.get('values', {})).items():
        actual = json_get(obj, str(path))
        if normalize(str(actual)) != normalize(str(expected)):
            return False, '%s=%r 期望 %r' % (path, actual, expected)
    for path, allowed in dict(spec.args.get('allowed', {})).items():
        actual = normalize(str(json_get(obj, str(path))))
        if actual not in [normalize(str(x)) for x in allowed]:
            return False, '%s=%r 不在允许值内' % (path, actual)
    forbid = [normalize(str(x)) for x in spec.args.get('forbid_ops', [])]
    if forbid:
        ops = obj.get('ops', [])
        if isinstance(ops, list):
            for op in ops:
                if isinstance(op, dict) and normalize(str(op.get('op', ''))) in forbid:
                    return False, '出现禁止操作 %r' % op.get('op')
    return True, 'JSON 结构合法'


def _check_code_test(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    if ctx.code is None:
        return False, '未启用代码沙箱'
    test_script = str(spec.args.get('test', ''))
    if not test_script:
        return False, '检查点未配置 test'
    ok, detail = ctx.code.run_test(test_script)
    return ok, detail


def _check_file_state(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    if ctx.files is None:
        return False, '未启用文件沙箱'
    state = ctx.files.state()
    paths = list(state.keys())
    for needle in _terms(spec, 'exists'):
        if not any(needle in p for p in paths):
            return False, '缺少路径(片段) %s' % needle
    for needle in _terms(spec, 'absent'):
        if any(needle in p for p in paths):
            return False, '出现不该有的路径(片段) %s' % needle
    for needle in _terms(spec, 'root_kept'):
        if needle not in paths:
            return False, '根目录文件 %s 被移动或删除' % needle
    count = spec.args.get('count')
    if count is not None and len(paths) != int(count):
        return False, '文件数 %d, 期望 %d' % (len(paths), int(count))
    if spec.args.get('no_nested'):
        nested = [p for p in paths if p.count('/') >= 2]
        if nested:
            return False, '存在二级以上目录: %s' % ', '.join(nested[:3])
    return True, '文件树 %d 个文件' % len(paths)


def _check_ops(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    if ctx.files is None:
        return False, '未启用文件沙箱'
    log = ctx.files.log
    min_ops = int(spec.args.get('min_ops', 0))
    if len(log) < min_ops:
        return False, '成功操作 %d 项, 少于 %d' % (len(log), min_ops)
    forbid_src = _terms(spec, 'forbid_src_contains')
    for entry in log:
        src = str(entry.get('src', ''))
        for needle in forbid_src:
            if needle in src:
                return False, '操作了不该动的文件 %s' % src
    forbid_dst = _terms(spec, 'forbid_dst_contains')
    for entry in log:
        dst = str(entry.get('dst', ''))
        for needle in forbid_dst:
            if needle in dst:
                return False, '目标路径含禁止片段 %s: %s' % (needle, dst)
    if spec.args.get('no_violations') and ctx.files.violations:
        return False, '存在违规操作: %s' % ctx.files.violations[-1]
    obj = extract_json(ctx.reply)
    ops = obj.get('ops', []) if isinstance(obj, dict) else []
    op_list = ops if isinstance(ops, list) else []
    for op in op_list:
        if isinstance(op, dict) and str(op.get('op', '')).lower() in ('delete', 'remove', 'rm'):
            return False, '输出了删除操作'
    return True, '%d 项操作合法' % len(log)


def _check_report_consistency(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    """报告里提到的文件, 必须确实出现在最近一次执行日志中 (防幻觉)。"""
    if ctx.files is None:
        return False, '未启用文件沙箱'
    mentioned = [name for name in _terms(spec, 'known') if name in ctx.reply]
    moved = set()
    for entry in ctx.files.log:
        moved.add(str(entry.get('src', '')).split('/')[-1])
        moved.add(str(entry.get('dst', '')).split('/')[-1])
    hits = [name for name in mentioned if name in moved]
    min_hits = int(spec.args.get('min_hits', 2))
    if len(hits) < min_hits:
        return False, '报告中仅 %d 个文件对应真实操作 (需 >=%d)' % (len(hits), min_hits)
    return True, '报告与操作日志一致 (%d 个文件)' % len(hits)


def _check_length(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    n = len(ctx.reply.strip())
    lo = int(spec.args.get('min', 0))
    hi = int(spec.args.get('max', 1000000))
    return lo <= n <= hi, '回复长度 %d (要求 %d~%d)' % (n, lo, hi)


def _check_prefix(spec: CheckSpec, ctx: CheckContext) -> Tuple[bool, str]:
    value = str(spec.args.get('value', ''))
    ok = ctx.reply.strip().startswith(value)
    return ok, ('以 %r 开头' % value) if ok else ('未以 %r 开头' % value)


_HANDLERS = {
    'contains': _check_contains,
    'not_contains': _check_not_contains,
    'regex': _check_regex,
    'json_object': _check_json_object,
    'code_test': _check_code_test,
    'file_state': _check_file_state,
    'ops_check': _check_ops,
    'report_consistency': _check_report_consistency,
    'length': _check_length,
    'prefix': _check_prefix,
}


def supported_kinds() -> List[str]:
    return sorted(_HANDLERS.keys())


def run_check(spec: CheckSpec, ctx: CheckContext) -> CheckResult:
    if ctx.no_reply:
        # 本轮只有 thinking 段或被截断: 即便沙箱里还留着上一轮的实现,
        # 也不能把"没回答"算成通过, 否则推理型模型会虚高。
        return CheckResult(
            label=spec.label or spec.kind, kind=spec.kind,
            dimension=spec.dimension, weight=spec.weight,
            passed=False, detail='本轮模型无有效回复 (think-only 或被截断)',
        )
    handler = _HANDLERS.get(spec.kind)
    if handler is None:
        passed, detail = False, '未知检查类型 %s' % spec.kind
    else:
        try:
            passed, detail = handler(spec, ctx)
        except Exception as e:
            passed, detail = False, '%s: %s' % (type(e).__name__, e)
    return CheckResult(
        label=spec.label or spec.kind, kind=spec.kind,
        dimension=spec.dimension, weight=spec.weight,
        passed=passed, detail=detail,
    )


def aggregate(results: List[CheckResult]) -> Tuple[float, Dict[str, float]]:
    """按 weight 汇总总分与各维度分 (0~1)。"""
    total_w = sum(r.weight for r in results)
    passed_w = sum(r.weight for r in results if r.passed)
    score = round(passed_w / total_w, 4) if total_w else 0.0
    dims: Dict[str, float] = {}
    for dim in set(r.dimension for r in results):
        items = [r for r in results if r.dimension == dim]
        w = sum(r.weight for r in items)
        p = sum(r.weight for r in items if r.passed)
        dims[dim] = round(p / w, 4) if w else 0.0
    return score, dims
