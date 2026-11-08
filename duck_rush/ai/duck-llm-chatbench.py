# -*- coding: utf-8 -*-
# @filename duck-llm-chatbench.py
# @description 本地 ollama 模型的多轮真实场景对话评测
"""duck-llm-chatbench -- 本地大模型多轮对话场景评测

与 duck-llm-benchmark 的单轮指标互补: 用固定剧本跑完整多轮会话,
对每一轮做规则/状态断言, 代码与文件类场景还会在沙箱里真实执行并回灌结果。

用法:
  duck-llm-chatbench scenarios              列出全部剧本
  duck-llm-chatbench models                列出本地 ollama 模型
  duck-llm-chatbench dry-run               静态校验剧本 + mock 跑通链路 (不调用模型)
  duck-llm-chatbench run [选项]            运行评测
  duck-llm-chatbench report                汇总已保存的结果

示例:
  duck-llm-chatbench run --models qwen2.5-coder:7b --scenarios code-dev bugfix
  duck-llm-chatbench run --all --scenarios customer-service --force
  duck-llm-chatbench run --all --limit 2 --verbose
"""

import sys
import os
import json
import glob
import shutil
import argparse
import subprocess
from typing import Any, Dict, List, Optional, Tuple

try:
    from termcolor import colored as _colored
except Exception:
    def _fallback_colored(text: Any, color: Any = None,
                          on_color: Any = None, attrs: Any = None,
                          **kwargs: Any) -> str:
        return str(text)
    _colored = _fallback_colored


def bright(text: Any, color: str) -> str:
    """终端统一用明亮配色。"""
    return _colored(str(text), color)


def _ensure_repo_on_path() -> None:
    """优先使用仓库内的 duck_utils 源码。

    已安装到 venv 的 duck_utils 可能是旧副本, 不含 llm_chatbench 子包;
    直接在 import 之前把仓库根放到 sys.path 最前可避免被旧副本截胡。
    仓库不存在时 (仅安装了包) 则退回 site-packages 里的版本。
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if os.path.isfile(os.path.join(root, 'duck_utils', '__init__.py')):
        if root not in sys.path:
            sys.path.insert(0, root)


_ensure_repo_on_path()

from duck_utils.llm_chatbench import (  # noqa: E402
    OllamaChatClient, RunOptions, ScenarioResult, find_scenarios,
    load_all, run_scenario, validate, write_report,
)
from duck_utils.llm_chatbench.model import ChatReply, Scenario  # noqa: E402


def get_data_dir() -> str:
    try:
        from duck_utils.os_util import get_command_data_dir
        return get_command_data_dir('duck-llm-chatbench')
    except Exception:
        d = os.path.join(os.path.expanduser('~'), '.duck-rush', 'data',
                         'duck-llm-chatbench')
        os.makedirs(d, exist_ok=True)
        return d


def _safe(name: str) -> str:
    return name.replace('/', '_').replace(':', '_').replace(' ', '_')


def scenario_dir(model: str, scenario_id: str) -> str:
    return os.path.join(get_data_dir(), _safe(model), scenario_id)


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_result(result: ScenarioResult) -> None:
    d = scenario_dir(result.model, result.scenario_id)
    _write_json(os.path.join(d, 'result.json'), result.to_dict())
    _write_json(os.path.join(d, 'transcript.json'), {
        'model': result.model, 'scenario_id': result.scenario_id,
        'scenario_name': result.scenario_name, 'score': result.score,
        'turns': [t.to_dict() for t in result.turns],
    })


def load_saved_results() -> Dict[Tuple[str, str], ScenarioResult]:
    found: Dict[Tuple[str, str], ScenarioResult] = {}
    pattern = os.path.join(get_data_dir(), '*', '*', 'result.json')
    for path in glob.glob(pattern):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                r = ScenarioResult.from_dict(json.load(f))
            found[(r.model, r.scenario_id)] = r
        except Exception:
            continue
    return found


def stop_other_models(except_name: Optional[str] = None) -> None:
    """切换模型前卸载其它实例, 避免多个模型同时占显存。"""
    if shutil.which('ollama') is None:
        return
    try:
        proc = subprocess.run(['ollama', 'ps'], capture_output=True,
                              text=True, timeout=30)
    except Exception:
        return
    for line in (proc.stdout or '').splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        if except_name and name == except_name:
            continue
        try:
            subprocess.run(['ollama', 'stop', name], capture_output=True,
                           text=True, timeout=60)
        except Exception:
            pass


def _mock_chat(model: str, messages: List[Dict[str, str]],
               opts: RunOptions) -> ChatReply:
    """dry-run 用的假回复, 只验证链路不调用模型。"""
    return ChatReply(content='[OK] 这是 dry-run 的模拟回复。',
                     prompt_tokens=1, eval_tokens=1, elapsed_ms=0)


def cmd_scenarios(args: argparse.Namespace) -> int:
    items = load_all()
    print(bright('多轮对话剧本 (共 %d 个):' % len(items), 'cyan'))
    print('  %-22s %-16s %6s %6s  %s' % ('ID', '分类', '轮数', '检查点', '说明'))
    for s in items:
        print('  %-22s %-16s %6d %6d  %s' % (
            s.id, s.category, len(s.turns), s.check_count(), s.name))
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    models = OllamaChatClient().list_models()
    if not models:
        print(bright('未检测到模型 (ollama 服务是否在运行?).', 'yellow'))
        return 1
    print(bright('本地 ollama 模型 (共 %d 个):' % len(models), 'cyan'))
    for m in models:
        print('  ' + m)
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    items = find_scenarios(args.scenarios)
    if not items:
        print(bright('没有匹配的剧本.', 'red'))
        return 1
    ok = True
    for s in items:
        problems = validate(s)
        opts = RunOptions(model='dry-run', allow_exec=False)
        result = run_scenario(s, _mock_chat, opts, allow_exec=False)
        status = bright('OK', 'green') if not problems and not result.error \
            else bright('FAIL', 'red')
        print('  %-22s %s  轮数=%d 检查点=%d' % (
            s.id, status, len(s.turns), s.check_count()))
        for p in problems:
            print('    ' + bright('配置问题: ' + p, 'red'))
        if result.error:
            print('    ' + bright('执行异常: ' + result.error, 'red'))
        if problems or result.error:
            ok = False
    print(bright('dry-run %s (未调用任何模型)' % ('通过' if ok else '发现问题'),
                 'green' if ok else 'red'))
    return 0 if ok else 1


def _resolve_models(args: argparse.Namespace) -> List[str]:
    client = OllamaChatClient()
    all_models = client.list_models()
    if args.models:
        return list(args.models)
    if args.all:
        return all_models
    print(bright('请指定 --models 或 --all.', 'yellow'))
    return []


def cmd_run(args: argparse.Namespace) -> int:
    scenarios = find_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    if not scenarios:
        print(bright('没有匹配的剧本, 可用 id 见 scenarios 子命令.', 'red'))
        return 1
    models = _resolve_models(args)
    if not models:
        return 1
    think: Optional[bool] = None
    if args.think == 'on':
        think = True
    elif args.think == 'off':
        think = False
    python_exe = sys.executable
    try:
        from duck_utils.duck_meta import InstallMeta
        meta = InstallMeta.load()
        python_exe = str(meta.python or python_exe)
    except Exception:
        pass

    known = load_saved_results()
    print(bright('评测开始: %d 个模型 × %d 个场景' % (len(models), len(scenarios)),
                 'cyan'))
    print(bright('数据目录: ' + get_data_dir(), 'cyan'))
    interrupted = False
    try:
        for model in models:
            print('')
            print(bright('=== 模型: %s ===' % model, 'cyan'))
            stop_other_models(model)
            for s in scenarios:
                key = (model, s.id)
                d = scenario_dir(model, s.id)
                done = os.path.exists(os.path.join(d, 'result.json'))
                if done and not args.force:
                    print('  %-22s %s' % (
                        s.id, bright('SKIP (已有结果, --force 可重跑)', 'yellow')))
                    continue
                try:
                    opts = RunOptions(
                        model=model, temperature=args.temperature,
                        seed=args.seed, num_ctx=args.num_ctx,
                        max_tokens=args.max_tokens, timeout=args.timeout,
                        think=think, allow_exec=not args.no_exec,
                        python_exe=python_exe,
                    )
                    client = OllamaChatClient(timeout=args.timeout)
                    result = run_scenario(s, client.chat, opts,
                                          python_exe=python_exe,
                                          allow_exec=not args.no_exec)
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except Exception as e:
                    result = ScenarioResult(
                        scenario_id=s.id, scenario_name=s.name,
                        category=s.category, model=model,
                        error='%s: %s' % (type(e).__name__, e))
                save_result(result)
                known[key] = result
                failed = sum(1 for t in result.turns for c in t.checks
                             if not c.passed)
                total = sum(len(t.checks) for t in result.turns)
                line = '  %-22s %s  失败检查点 %d/%d' % (
                    s.id, bright('%.0f%%' % (result.score * 100),
                                 'green' if result.score >= 0.6 else 'yellow'),
                    failed, total)
                if result.error:
                    line += '  ' + bright(result.error[:60], 'red')
                print(line)
                if args.verbose:
                    for t in result.turns:
                        for c in t.checks:
                            if not c.passed:
                                print('    轮%d [%s] %s: %s' % (
                                    t.index, c.dimension, c.label,
                                    c.detail[:100]))
                write_report(list(known.values()), get_data_dir())
            if interrupted:
                break
    except KeyboardInterrupt:
        interrupted = True
    finally:
        write_report(list(known.values()), get_data_dir())
        stop_other_models()
    print('')
    if interrupted:
        print(bright('已中断; 已完成的结果均已保存 (可不带 --force 续跑).',
                     'yellow'))
    print(bright('报告: %s' % os.path.join(get_data_dir(), 'report.md'),
                 'cyan'))
    return 0 if not interrupted else 130


def cmd_report(args: argparse.Namespace) -> int:
    known = load_saved_results()
    if not known:
        print(bright('没有已保存的结果, 请先运行 run.', 'yellow'))
        return 0
    paths = write_report(list(known.values()), get_data_dir())
    for p in paths:
        print(bright('报告已写: ' + p, 'cyan'))
    # 终端上给一份极简矩阵
    models = sorted(set(r.model for r in known.values()))
    ids = sorted(set(r.scenario_id for r in known.values()))
    print('')
    print('  %-26s %s' % ('模型', ' '.join('%8s' % i[:8] for i in ids)))
    for m in models:
        cells = []
        for sid in ids:
            r = known.get((m, sid))
            cells.append('%7.0f%%' % (r.score * 100) if r else '    N/A')
        print('  %-26s %s' % (m, ' '.join(cells)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='duck-llm-chatbench',
        description='本地 ollama 模型多轮对话场景评测')
    sub = p.add_subparsers(dest='cmd')
    sub.add_parser('scenarios', help='列出全部剧本')
    sub.add_parser('models', help='列出本地 ollama 模型')
    pd = sub.add_parser('dry-run', help='校验剧本并用 mock 跑通链路')
    pd.add_argument('scenarios', nargs='*', help='只校验指定剧本 id')
    pr = sub.add_parser('run', help='运行评测')
    pr.add_argument('--models', nargs='+', default=[], help='模型名(可多个)')
    pr.add_argument('--all', action='store_true', help='跑全部本地模型')
    pr.add_argument('--scenarios', nargs='+', default=[], help='剧本 id(可多个)')
    pr.add_argument('--limit', type=int, default=None, help='只跑前 N 个剧本')
    pr.add_argument('--force', action='store_true', help='覆盖已有结果')
    pr.add_argument('--verbose', '-v', action='store_true', help='打印失败检查点')
    pr.add_argument('--no-exec', action='store_true', help='禁用代码沙箱执行')
    pr.add_argument('--timeout', type=int, default=300, help='单次调用超时(秒)')
    pr.add_argument('--max-tokens', type=int, default=3072, help='单轮最大生成 token')
    pr.add_argument('--num-ctx', type=int, default=12288, help='上下文窗口')
    pr.add_argument('--temperature', type=float, default=0.0, help='采样温度')
    pr.add_argument('--seed', type=int, default=42, help='随机种子')
    pr.add_argument('--think', choices=['auto', 'on', 'off'], default='auto',
                    help='推理模型思考开关 (auto: 对 r1/qwq 关闭)')
    sub.add_parser('report', help='汇总已保存的结果')
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == 'scenarios':
        return cmd_scenarios(args)
    if args.cmd == 'models':
        return cmd_models(args)
    if args.cmd == 'dry-run':
        return cmd_dry_run(args)
    if args.cmd == 'run':
        return cmd_run(args)
    if args.cmd == 'report':
        return cmd_report(args)
    parser.print_help()
    return 0


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    sys.exit(main())
