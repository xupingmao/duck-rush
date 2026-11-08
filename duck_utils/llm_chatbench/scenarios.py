# -*- coding: utf-8 -*-
"""剧本加载与静态校验。剧本是与代码分离的 JSON 数据, 便于直接改题。"""

import glob
import json
import os
from typing import Any, Dict, List, Optional

from .checks import supported_kinds
from .model import CheckSpec, Scenario, TurnSpec

SCENARIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenarios')


def _check_spec(data: Dict[str, Any]) -> CheckSpec:
    return CheckSpec(
        kind=str(data.get('kind', '')),
        args=dict(data.get('args', {})),
        dimension=str(data.get('dimension', 'task')),
        weight=float(data.get('weight', 1.0)),
        label=str(data.get('label', '')),
    )


def _turn_spec(data: Dict[str, Any]) -> TurnSpec:
    return TurnSpec(
        user=str(data.get('user', '')),
        checks=[_check_spec(c) for c in data.get('checks', [])],
        env=data.get('env'),
        note=str(data.get('note', '')),
    )


def load_scenario(path: str) -> Scenario:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Scenario(
        id=str(data.get('id', '')),
        name=str(data.get('name', '')),
        category=str(data.get('category', '')),
        description=str(data.get('description', '')),
        system=str(data.get('system', '')),
        turns=[_turn_spec(t) for t in data.get('turns', [])],
        setup=dict(data.get('setup', {})),
    )


def load_all(directory: str = SCENARIO_DIR) -> List[Scenario]:
    paths = sorted(glob.glob(os.path.join(directory, '*.json')))
    return [load_scenario(p) for p in paths]


def find_scenarios(ids: Optional[List[str]] = None,
                   directory: str = SCENARIO_DIR) -> List[Scenario]:
    all_items = load_all(directory)
    if not ids:
        return all_items
    wanted = set(ids)
    return [s for s in all_items if s.id in wanted or s.category in wanted]


def validate(scenario: Scenario) -> List[str]:
    """静态校验剧本, 返回问题列表 (dry-run 用, 不调用模型)。"""
    problems: List[str] = []
    if not scenario.id:
        problems.append('缺少 id')
    if not scenario.system:
        problems.append('缺少 system')
    if not scenario.turns:
        problems.append('没有轮次')
    kinds = set(supported_kinds())
    for i, turn in enumerate(scenario.turns):
        if not turn.user:
            problems.append('第 %d 轮缺少 user' % (i + 1))
        for c in turn.checks:
            if c.kind not in kinds:
                problems.append('第 %d 轮未知检查类型 %s' % (i + 1, c.kind))
            if c.kind == 'code_test' and not c.args.get('test'):
                problems.append('第 %d 轮 code_test 缺少 test' % (i + 1))
            if c.kind in ('contains', 'not_contains') and not (
                    c.args.get('any') or c.args.get('all') or c.args.get('value')):
                problems.append('第 %d 轮 %s 缺少关键词' % (i + 1, c.kind))
        env = turn.env or {}
        if env.get('type') == 'apply_ops' and 'files' not in scenario.setup:
            problems.append('第 %d 轮 apply_ops 需要 setup.files' % (i + 1))
        if env.get('type') == 'tool_step' and not scenario.setup.get('tool_responses'):
            problems.append('第 %d 轮 tool_step 需要 setup.tool_responses' % (i + 1))
    return problems
