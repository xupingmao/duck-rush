# -*- coding: utf-8 -*-
"""本地大模型多轮对话评测框架 (剧本 + 检查点 + 沙箱回灌)。"""

from .model import (ChatReply, RunOptions, Scenario, ScenarioResult,
                    TurnRecord)
from .client import OllamaChatClient
from .engine import run_scenario
from .report import build_json, build_markdown, write_report
from .scenarios import find_scenarios, load_all, load_scenario, validate

__all__ = [
    'ChatReply', 'RunOptions', 'Scenario', 'ScenarioResult', 'TurnRecord',
    'OllamaChatClient', 'run_scenario', 'build_json', 'build_markdown',
    'write_report', 'find_scenarios', 'load_all', 'load_scenario', 'validate',
]
