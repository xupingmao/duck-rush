# -*- coding: utf-8 -*-
"""剧本驱动的多轮会话引擎。

固定用户轮次 + 全量 messages 历史 + 环境反馈回灌。
每个模型、每个剧本都从干净会话与干净沙箱开始, 保证横比公平。
"""

import json
from typing import Any, Dict, List, Optional

from .checks import CheckContext, aggregate, run_check
from .model import (ChatFn, CheckResult, RunOptions, Scenario, ScenarioResult,
                    TurnRecord)
from .sandbox import CodeSandbox, FileSandbox
from .util import extract_json


def _build_system(scenario: Scenario, files: Optional[FileSandbox]) -> str:
    parts = [scenario.system]
    inject = scenario.setup.get('inject')
    if inject:
        parts.append(str(inject))
    if files is not None and scenario.setup.get('file_listing', False):
        lines = ['当前工作目录的文件清单 (相对路径):']
        for path in sorted(files.initial.keys()):
            lines.append('- %s : %s' % (path, files.initial[path]))
        parts.append('\n'.join(lines))
    return '\n\n'.join(p for p in parts if p)


def _tool_feedback(scenario: Scenario, reply: str,
                   call_counts: Dict[str, int]) -> str:
    """把模型输出的工具调用交给模拟工具, 生成下一轮的真实反馈。"""
    parsed = extract_json(reply)
    tool = ''
    args: Any = {}
    if isinstance(parsed, dict):
        tool = str(parsed.get('tool', parsed.get('name', '')))
        args = parsed.get('arguments', parsed.get('args', {}))
    if not tool:
        return '【工具返回】未解析到工具调用 JSON, 本轮没有任何操作被执行。'
    table = scenario.setup.get('tool_responses', {})
    responses = table.get(tool) if isinstance(table, dict) else None
    idx = call_counts.get(tool, 0)
    call_counts[tool] = idx + 1
    if not isinstance(responses, list) or idx >= len(responses):
        return '【工具返回】工具 %s 无可用返回 (调用次数 %d), 请检查调用是否正确。' % (tool, idx + 1)
    item = responses[idx]
    result = item.get('result', item) if isinstance(item, dict) and 'result' in item else item
    if isinstance(result, (dict, list)):
        result_text = json.dumps(result, ensure_ascii=False)
    else:
        result_text = str(result)
    return '【工具返回】%s(%s) -> %s' % (
        tool, json.dumps(args, ensure_ascii=False) if isinstance(args, (dict, list))
        else str(args), result_text)


def run_scenario(scenario: Scenario, chat_fn: ChatFn, opts: RunOptions,
                 python_exe: str = '', allow_exec: bool = True) -> ScenarioResult:
    """执行一个剧本, 返回逐轮留档与评分。"""
    result = ScenarioResult(
        scenario_id=scenario.id, scenario_name=scenario.name,
        category=scenario.category, model=opts.model,
    )
    code: Optional[CodeSandbox] = None
    files: Optional[FileSandbox] = None
    try:
        setup = scenario.setup or {}
        if setup.get('sandbox') == 'code':
            code = CodeSandbox(python_exe=python_exe, allow_exec=allow_exec)
        if 'files' in setup:
            files = FileSandbox(dict(setup.get('files', {})), allow_exec=allow_exec)
        system = _build_system(scenario, files)
        messages: List[Dict[str, str]] = [{'role': 'system', 'content': system}]
        pending_feedback: Optional[str] = None
        history: List[str] = []
        call_counts: Dict[str, int] = {}
        all_checks: List[CheckResult] = []

        for index, turn in enumerate(scenario.turns):
            user_text = turn.user
            if pending_feedback:
                user_text = pending_feedback + '\n\n' + turn.user
            messages.append({'role': 'user', 'content': user_text})
            reply = chat_fn(opts.model, list(messages), opts)
            content = reply.content or ''
            messages.append({'role': 'assistant',
                             'content': content or '(本轮无有效回复)'})

            # 代码沙箱: 每轮尝试更新实现 (marker 保证只被真实实现覆盖)
            if code is not None:
                code.update_from_reply(content, str(setup.get('code_marker', '')))

            feedback: Optional[str] = None
            env = turn.env or {}
            env_type = str(env.get('type', 'none'))
            if env_type == 'apply_ops' and files is not None:
                if env.get('reset'):
                    files.reset()
                _applied, feedback = files.apply_ops(content)
            elif env_type == 'tool_step':
                feedback = _tool_feedback(scenario, content, call_counts)
            elif env_type == 'inject':
                feedback = str(env.get('text', '')) or None

            ctx = CheckContext(
                reply=content, no_reply=not bool(content),
                history=list(history), code=code, files=files,
                feedback=feedback, turn_index=index, scenario=scenario,
            )
            checks = [run_check(spec, ctx) for spec in turn.checks]
            all_checks.extend(checks)
            history.append(content)
            result.turns.append(TurnRecord(
                index=index + 1, user=user_text, reply=content,
                feedback=feedback, checks=checks,
                elapsed_ms=reply.elapsed_ms,
                prompt_tokens=reply.prompt_tokens,
                eval_tokens=reply.eval_tokens, error=reply.error,
            ))
            pending_feedback = feedback

        result.score, result.dimensions = aggregate(all_checks)
    except Exception as e:
        result.error = '%s: %s' % (type(e).__name__, e)
    finally:
        if code is not None:
            code.close()
        if files is not None:
            files.close()
    return result
