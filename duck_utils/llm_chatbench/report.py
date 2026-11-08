# -*- coding: utf-8 -*-
"""汇总报告: 模型 × 场景得分矩阵、维度分、典型失败检查点。"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from .hardware import collect_hardware, hardware_markdown
from .model import DIMENSIONS, DIMENSION_NAMES, ScenarioResult


def _pct(value: float) -> str:
    return '%.0f%%' % (value * 100)


def _collect(results: List[ScenarioResult]) -> Dict[str, Any]:
    models = sorted(set(r.model for r in results))
    scenarios = sorted(set((r.scenario_id, r.scenario_name) for r in results))
    matrix: Dict[str, Dict[str, float]] = {m: {} for m in models}
    dims: Dict[str, Dict[str, List[float]]] = {m: {} for m in models}
    failures: List[Dict[str, Any]] = []
    latency: Dict[str, List[int]] = {m: [] for m in models}
    tokens: Dict[str, int] = {m: 0 for m in models}
    empty_turns: Dict[str, int] = {m: 0 for m in models}
    for r in results:
        matrix.setdefault(r.model, {})[r.scenario_id] = r.score
        for d, v in r.dimensions.items():
            dims.setdefault(r.model, {}).setdefault(d, []).append(v)
        for t in r.turns:
            if not t.reply.strip():
                empty_turns[r.model] = empty_turns.get(r.model, 0) + 1
            latency.setdefault(r.model, []).append(t.elapsed_ms)
            tokens[r.model] = tokens.get(r.model, 0) + t.prompt_tokens + t.eval_tokens
            for c in t.checks:
                if c.passed:
                    continue
                failures.append({
                    'model': r.model, 'scenario': r.scenario_id, 'turn': t.index,
                    'label': c.label, 'kind': c.kind, 'dimension': c.dimension,
                    'weight': c.weight, 'detail': c.detail[:160],
                })
    return {
        'models': models, 'scenarios': [s[0] for s in scenarios],
        'scenario_names': {s[0]: s[1] for s in scenarios},
        'matrix': matrix, 'dims': dims, 'failures': failures,
        'latency': latency, 'tokens': tokens, 'empty_turns': empty_turns,
    }


def build_json(results: List[ScenarioResult],
               hardware: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = _collect(results)
    data['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    data['hardware'] = (hardware if hardware is not None
                        else collect_hardware())
    data['results'] = [r.to_dict() for r in results]
    return data


def build_markdown(results: List[ScenarioResult],
                   hardware: Optional[Dict[str, Any]] = None) -> str:
    data = _collect(results)
    models: List[str] = data['models']
    scenario_ids: List[str] = data['scenarios']
    names: Dict[str, str] = data['scenario_names']
    lines = ['# 本地大模型多轮对话评测报告', '']
    lines.append('生成时间: %s ｜ 模型 %d 个 ｜ 场景 %d 个' % (
        time.strftime('%Y-%m-%d %H:%M:%S'), len(models), len(scenario_ids)))
    lines.append('')
    lines.append('评分方式: 逐轮规则/状态断言加权通过率, 满分 100%; '
                 '不使用模型自评。数值为百分制得分。')
    lines.append('')
    lines.append('## 模型 × 场景 得分矩阵')
    lines.append('')
    lines.append('| 模型 | ' + ' | '.join(names.get(s, s) for s in scenario_ids) + ' | 平均 |')
    lines.append('| --- | ' + ' | '.join('---' for _ in scenario_ids) + ' | --- |')
    for m in models:
        cells = []
        for s in scenario_ids:
            v = data['matrix'].get(m, {}).get(s)
            cells.append(_pct(v) if v is not None else 'N/A')
        vals = [v for v in data['matrix'].get(m, {}).values() if v is not None]
        avg = sum(vals) / len(vals) if vals else 0.0
        lines.append('| %s | %s | %s |' % (m, ' | '.join(cells), _pct(avg)))
    lines.append('')
    lines.append('## 能力维度 (各场景等权平均)')
    lines.append('')
    lines.append('| 模型 | ' + ' | '.join(DIMENSION_NAMES[d] for d in DIMENSIONS) + ' |')
    lines.append('| --- | ' + ' | '.join('---' for _ in DIMENSIONS) + ' |')
    for m in models:
        cells = []
        for d in DIMENSIONS:
            vals = data['dims'].get(m, {}).get(d, [])
            cells.append(_pct(sum(vals) / len(vals)) if vals else 'N/A')
        lines.append('| %s | %s |' % (m, ' | '.join(cells)))
    lines.append('')
    lines.append('## 效率与上下文开销')
    lines.append('')
    lines.append('| 模型 | 调用轮数 | 平均单轮耗时 | 累计 token | 无有效回复轮数 |')
    lines.append('| --- | --- | --- | --- | --- |')
    for m in models:
        lat = data['latency'].get(m, [])
        avg_ms = sum(lat) / len(lat) if lat else 0
        lines.append('| %s | %d | %.1f s | %d | %d |' % (
            m, len(lat), avg_ms / 1000.0, data['tokens'].get(m, 0),
            data['empty_turns'].get(m, 0)))
    lines.append('')
    total_empty = sum(data['empty_turns'].values())
    if total_empty:
        lines.append('> 说明：共 %d 轮模型未给出有效回复（推理模型的思考段耗尽生成预算，'
                     '或输出被 `num_predict` 截断）。这些轮次的检查点一律按失败计；'
                     '这属于真实可用性缺陷。若只想评估能力本身，可用 '
                     '`--max-tokens 16384 --force` 重跑相关场景。' % total_empty)
        lines.append('')
    lines.append('## 高频失败检查点 (前 25 条)')
    lines.append('')
    lines.append('| 模型 | 场景 | 轮次 | 检查点 | 维度 | 说明 |')
    lines.append('| --- | --- | --- | --- | --- | --- |')
    failures = sorted(data['failures'], key=lambda x: -x['weight'])[:25]
    for f in failures:
        detail = f['detail'].replace('|', '/').replace('\n', ' ')
        lines.append('| %s | %s | %s | %s | %s | %s |' % (
            f['model'], f['scenario'], f['turn'], f['label'],
            DIMENSION_NAMES.get(f['dimension'], f['dimension']), detail))
    if not failures:
        lines.append('| - | - | - | - | - | 无失败项 |')
    lines.append('')
    lines.append('## 复现与留档')
    lines.append('')
    lines.append('- 逐轮完整对话与检查明细: `data/duck-llm-chatbench/{model}/{scenario}/transcript.json`')
    lines.append('- 单场景结果: 同目录 `result.json`; 汇总原始数据: `report.json`')
    lines.append('- 重跑单场景: `duck-llm-chatbench run --models <模型> --scenarios <场景> --force`')
    lines.append('- 归档副本: `docs/llm-benchmark-multi-turn.md` / `.json`（项目仓库）')
    lines.append('')
    lines.append('## 评测口径与版本说明')
    lines.append('')
    lines.append('- 固定剧本、固定轮次、同题同序；每个模型独立会话，'
                 '`temperature=0`、`seed=42`；代码 / BUG / 文件整理场景在临时沙箱'
                 '真实执行并把结果回灌为下一轮输入。')
    lines.append('- 无有效回复轮次（只有思考段或输出被 `num_predict` 截断）'
                 '该轮检查点一律判负，属于真实可用性缺陷而非能力题失分。')
    lines.append('- 本报告为**增量汇总**，模型分批加入：历史 6 个模型采集于 '
                 'ollama 0.32.6，后续新增模型采集于 0.40.15。两个版本对 '
                 'thinking 开关、默认 `num_ctx` 与生成预算的处理不同，'
                 '跨批次比较请结合「无有效回复轮数」及 `transcript.json` '
                 '中的逐轮 token 与耗时一起判断。')
    lines.append('- 对实测会输出长思考段的模型，统一按 `--think off '
                 '--max-tokens 8192` 运行（与历史 deepseek-r1 同等待遇），'
                 '避免思考段耗尽预算造成空回复而低估能力；'
                 '默认无思考段的模型沿用 `--max-tokens 3072`。')
    lines.append('- 本批次新增的 3 个模型（qwen3.5:9b、mimo-v2.6、qwen3.8:27b）'
                 '探测时均返回独立 thinking 段，因此统一走上述 `think off + 8192` 配置；'
                 '其中 16 GB 级的 qwen3.8:27b 受 12 GB 显存限制存在 CPU offload，'
                 '单次调用超时另放宽到 900 s。历史 6 模型为 300 s 超时、3072 预算，'
                 '故本表是「各自可得的可用配置」对比，并非严格同配置横评。')
    lines.append('')
    lines.append(hardware_markdown(
        hw=hardware if hardware is not None else collect_hardware()).rstrip('\n'))
    return '\n'.join(lines) + '\n'


def write_report(results: List[ScenarioResult], out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    # 同一次采集供 JSON 与 Markdown 共用, 保证两份留档的硬件基线完全一致。
    hardware = collect_hardware(out_dir)
    json_path = os.path.join(out_dir, 'report.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(build_json(results, hardware), f, ensure_ascii=False, indent=2)
    paths.append(json_path)
    md_path = os.path.join(out_dir, 'report.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(build_markdown(results, hardware))
    paths.append(md_path)
    return paths
