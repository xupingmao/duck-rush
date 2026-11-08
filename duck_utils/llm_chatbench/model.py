# -*- coding: utf-8 -*-
"""多轮对话评测的数据结构定义。

剧本 (Scenario) 是纯数据, 由 scenarios/*.json 加载; 运行产物
(TurnRecord / ScenarioResult) 可序列化为 JSON, 用于断点续跑和报告。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# 评分维度: 任务完成 / 上下文记忆 / 指令遵循 / 纠错 / 不幻觉 / 工具与格式
DIMENSIONS = ('task', 'memory', 'instruction', 'correction', 'hallucination', 'tool')

DIMENSION_NAMES = {
    'task': '任务完成',
    'memory': '上下文记忆',
    'instruction': '指令遵循',
    'correction': '纠错能力',
    'hallucination': '不幻觉/不越权',
    'tool': '工具与格式',
}


@dataclass
class CheckSpec:
    """一个检查点。kind 决定用哪种检查器, args 为检查器参数。"""
    kind: str
    args: Dict[str, Any] = field(default_factory=dict)
    dimension: str = 'task'
    weight: float = 1.0
    label: str = ''


@dataclass
class TurnSpec:
    """一轮用户话术及其检查点。env 描述本轮回复后要做的环境动作。"""
    user: str
    checks: List[CheckSpec] = field(default_factory=list)
    env: Optional[Dict[str, Any]] = None
    note: str = ''


@dataclass
class Scenario:
    """一个完整的多轮对话剧本。"""
    id: str
    name: str
    category: str
    description: str
    system: str
    turns: List[TurnSpec]
    setup: Dict[str, Any] = field(default_factory=dict)

    def check_count(self) -> int:
        return sum(len(t.checks) for t in self.turns)


@dataclass
class CheckResult:
    label: str
    kind: str
    dimension: str
    weight: float
    passed: bool
    detail: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label, 'kind': self.kind, 'dimension': self.dimension,
            'weight': self.weight, 'passed': self.passed, 'detail': self.detail,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'CheckResult':
        return CheckResult(
            label=d.get('label', ''), kind=d.get('kind', ''),
            dimension=d.get('dimension', 'task'),
            weight=float(d.get('weight', 1.0)),
            passed=bool(d.get('passed', False)), detail=d.get('detail', ''),
        )


@dataclass
class ChatReply:
    """一次模型调用的回复 (content 已剥离 thinking 标签)。"""
    content: str
    prompt_tokens: int = 0
    eval_tokens: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None


@dataclass
class RunOptions:
    """运行参数。全部通过关键字构造, 避免长位置参数列表。"""
    model: str = ''
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 12288
    max_tokens: int = 3072
    timeout: int = 300
    think: Optional[bool] = None
    allow_exec: bool = True
    python_exe: str = ''


# 会话函数: (model, messages, options) -> ChatReply; 测试时可注入 mock。
ChatFn = Callable[[str, List[Dict[str, str]], RunOptions], ChatReply]


@dataclass
class TurnRecord:
    """一轮的完整留档, 供人工复核。"""
    index: int
    user: str
    reply: str
    feedback: Optional[str]
    checks: List[CheckResult] = field(default_factory=list)
    elapsed_ms: int = 0
    prompt_tokens: int = 0
    eval_tokens: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index, 'user': self.user, 'reply': self.reply,
            'feedback': self.feedback,
            'checks': [c.to_dict() for c in self.checks],
            'elapsed_ms': self.elapsed_ms,
            'prompt_tokens': self.prompt_tokens,
            'eval_tokens': self.eval_tokens, 'error': self.error,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'TurnRecord':
        return TurnRecord(
            index=int(d.get('index', 0)), user=d.get('user', ''),
            reply=d.get('reply', ''), feedback=d.get('feedback'),
            checks=[CheckResult.from_dict(c) for c in d.get('checks', [])],
            elapsed_ms=int(d.get('elapsed_ms', 0)),
            prompt_tokens=int(d.get('prompt_tokens', 0)),
            eval_tokens=int(d.get('eval_tokens', 0)), error=d.get('error'),
        )


@dataclass
class ScenarioResult:
    """一个模型在一个剧本上的结果。"""
    scenario_id: str
    scenario_name: str
    category: str
    model: str
    turns: List[TurnRecord] = field(default_factory=list)
    score: float = 0.0
    dimensions: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario_id': self.scenario_id,
            'scenario_name': self.scenario_name,
            'category': self.category, 'model': self.model,
            'turns': [t.to_dict() for t in self.turns],
            'score': self.score, 'dimensions': self.dimensions,
            'error': self.error,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'ScenarioResult':
        return ScenarioResult(
            scenario_id=d.get('scenario_id', ''),
            scenario_name=d.get('scenario_name', ''),
            category=d.get('category', ''), model=d.get('model', ''),
            turns=[TurnRecord.from_dict(t) for t in d.get('turns', [])],
            score=float(d.get('score', 0.0)),
            dimensions=dict(d.get('dimensions', {})),
            error=d.get('error'),
        )
