# -*- coding: utf-8 -*-
"""多轮评测框架自检 (仅标准库 unittest, 不调用 ollama)。

运行: python duck_utils/llm_chatbench/test_chatbench.py
"""

import os
import sys
import unittest
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from duck_utils.llm_chatbench.checks import (CheckContext, aggregate,  # noqa: E402
                                             run_check, supported_kinds)
from duck_utils.llm_chatbench.engine import run_scenario  # noqa: E402
from duck_utils.llm_chatbench.model import (ChatReply, CheckResult,  # noqa: E402
                                            CheckSpec, RunOptions, Scenario,
                                            ScenarioResult, TurnSpec)
from duck_utils.llm_chatbench.report import build_json, build_markdown  # noqa: E402
from duck_utils.llm_chatbench.sandbox import CodeSandbox, FileSandbox  # noqa: E402
from duck_utils.llm_chatbench.scenarios import load_all, validate  # noqa: E402
from duck_utils.llm_chatbench.util import (extract_json, normalize,  # noqa: E402
                                           strip_thinking)


class TestUtil(unittest.TestCase):

    def test_strip_thinking(self) -> None:
        self.assertEqual(strip_thinking('<think>内部推理</think>\n答案是北京'),
                         '答案是北京')
        self.assertEqual(strip_thinking('普通回答'), '普通回答')
        self.assertEqual(strip_thinking('<think>被截断的思考'), '')

    def test_normalize(self) -> None:
        self.assertEqual(normalize(' 7 天无理由，未拆封！'), '7天无理由未拆封')
        self.assertEqual(normalize('H2O'), 'h2o')

    def test_extract_json_fenced(self) -> None:
        text = '好的\n```json\n{"tool": "query_stock", "args": {"sku": "A-100"}}\n```\n'
        obj = extract_json(text)
        self.assertIsInstance(obj, dict)
        self.assertEqual((obj or {})['tool'], 'query_stock')


class TestChecks(unittest.TestCase):

    def test_contains_and_not_contains(self) -> None:
        ctx = CheckContext(reply='工单状态 pending_review，需要转人工主管')
        spec = CheckSpec('contains', {'all': ['pending_review'], 'any': ['主管', '转人工']})
        self.assertTrue(run_check(spec, ctx).passed)
        bad = CheckSpec('not_contains', {'any': ['赔您 200 元']})
        self.assertTrue(run_check(bad, ctx).passed)
        hit = CheckSpec('not_contains', {'any': ['转人工']})
        self.assertFalse(run_check(hit, ctx).passed)

    def test_json_object(self) -> None:
        ctx = CheckContext(reply='{"tool":"no_op","args":{"reason":"库存为 0"}}')
        spec = CheckSpec('json_object', {
            'required': ['tool', 'args.reason'],
            'values': {'tool': 'no_op'},
            'allowed': {'tool': ['no_op', 'create_order']},
        })
        self.assertTrue(run_check(spec, ctx).passed)
        wrong = CheckSpec('json_object', {'values': {'tool': 'create_order'}})
        self.assertFalse(run_check(wrong, ctx).passed)

    def test_aggregate_weighted(self) -> None:
        items = [
            CheckResult('a', 'contains', 'task', 3.0, True),
            CheckResult('b', 'contains', 'memory', 1.0, False),
        ]
        score, dims = aggregate(items)
        self.assertAlmostEqual(score, 0.75)
        self.assertAlmostEqual(dims['task'], 1.0)
        self.assertAlmostEqual(dims['memory'], 0.0)

    def test_unknown_kind(self) -> None:
        self.assertFalse(run_check(CheckSpec('nope'), CheckContext()).passed)
        self.assertIn('contains', supported_kinds())

    def test_no_reply_fails_all_checks(self) -> None:
        ctx = CheckContext(reply='', no_reply=True)
        result = run_check(CheckSpec('contains', {'any': ['任意']}), ctx)
        self.assertFalse(result.passed)
        self.assertIn('无有效回复', result.detail)


class TestSandbox(unittest.TestCase):

    def test_code_test(self) -> None:
        box = CodeSandbox()
        try:
            ok = box.update_from_reply(
                '```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```',
                marker='def add')
            self.assertTrue(ok)
            passed, _ = box.run_test('assert add(1, 2) == 3')
            self.assertTrue(passed)
            failed, _ = box.run_test('assert add(1, 2) == 4')
            self.assertFalse(failed)
        finally:
            box.close()

    def test_code_marker_keeps_solution(self) -> None:
        box = CodeSandbox()
        try:
            box.update_from_reply('```python\ndef f():\n    return 1\n```', 'def f')
            updated = box.update_from_reply('```python\nassert True\n```', 'def f')
            self.assertFalse(updated)
            self.assertIn('def f', box.solution)
        finally:
            box.close()

    def test_file_ops_and_delete_blocked(self) -> None:
        box = FileSandbox({'a.txt': 'A', 'b.log': 'B'})
        try:
            applied, feedback = box.apply_ops(
                '{"ops":[{"op":"move","src":"a.txt","dst":"项目/a.txt"},'
                '{"op":"delete","src":"b.log"}]}')
            self.assertEqual(len(applied), 1)
            self.assertIn('项目/a.txt', box.state())
            self.assertEqual(len(box.violations), 1)
            self.assertIn('成功 1 项', feedback)
            self.assertEqual(len(box.state()), 2)
            ctx = CheckContext(reply='', files=box)
            spec = CheckSpec('file_state', {'count': 2, 'root_kept': ['b.log']})
            self.assertTrue(run_check(spec, ctx).passed)
        finally:
            box.close()

    def test_path_escape_blocked(self) -> None:
        box = FileSandbox({'a.txt': 'A'})
        try:
            applied, _ = box.apply_ops(
                '{"ops":[{"op":"move","src":"a.txt","dst":"../escape.txt"}]}')
            self.assertEqual(applied, [])
        finally:
            box.close()

    def test_solution_ignores_embedded_tests(self) -> None:
        """实现与自测放在同一代码块时, 只保留实现部分。"""
        box = CodeSandbox()
        try:
            source = ('```python\ndef f():\n    return 1\n\n'
                      'def test_f():\n    assert f() == 2\n\ntest_f()\n```')
            self.assertTrue(box.update_from_reply(source, marker='def f'))
            self.assertNotIn('def test_f', box.solution)
            passed, _ = box.run_test('assert f() == 1')
            self.assertTrue(passed)
        finally:
            box.close()


class TestEngine(unittest.TestCase):

    def test_feedback_replay_and_scoring(self) -> None:
        seen: List[str] = []
        replies = [
            '{"tool":"query_stock","args":{"sku":"A-100"}}',
            '{"tool":"create_order","args":{"sku":"A-100","qty":2}}',
        ]

        def fake_chat(model: str, messages: List[Dict[str, str]],
                      opts: RunOptions) -> ChatReply:
            seen.append(messages[-1]['content'])
            return ChatReply(content=replies[min(len(seen) - 1, 1)])

        scenario = Scenario(
            id='unit', name='单测剧本', category='工具编排', description='',
            system='只输出 JSON',
            turns=[
                TurnSpec('查库存', checks=[CheckSpec(
                    'json_object', {'values': {'tool': 'query_stock'}},
                    dimension='tool', weight=2.0)], env={'type': 'tool_step'}),
                TurnSpec('下单', checks=[CheckSpec(
                    'json_object', {'values': {'tool': 'create_order'}},
                    dimension='task', weight=1.0)], env={'type': 'tool_step'}),
            ],
            setup={'tool_responses': {
                'query_stock': [{'sku': 'A-100', 'stock': 3}],
                'create_order': [{'order_id': 'SO-1'}],
            }},
        )
        result = run_scenario(scenario, fake_chat, RunOptions(model='mock'))
        self.assertIsNone(result.error)
        self.assertEqual(len(result.turns), 2)
        self.assertIn('A-100', seen[1], '第二轮应带上工具返回的回灌信息')
        self.assertIn('【工具返回】', seen[1])
        self.assertAlmostEqual(result.score, 1.0)
        self.assertIn('tool', result.dimensions)

    def test_file_env_replay(self) -> None:
        replies = [
            '{"ops":[{"op":"move","src":"a.txt","dst":"项目/a.txt"}]}',
            '已完成整理',
        ]

        def fake_chat(model: str, messages: List[Dict[str, str]],
                      opts: RunOptions) -> ChatReply:
            idx = sum(1 for m in messages if m['role'] == 'user') - 1
            return ChatReply(content=replies[min(idx, 1)])

        scenario = Scenario(
            id='unit-files', name='文件单测', category='文件整理',
            description='', system='只输出 JSON',
            turns=[
                TurnSpec('执行', env={'type': 'apply_ops'},
                         checks=[CheckSpec('ops_check', {'min_ops': 1})]),
                TurnSpec('报告', checks=[CheckSpec('contains', {'any': ['整理']})]),
            ],
            setup={'files': {'a.txt': 'A'}, 'file_listing': True},
        )
        result = run_scenario(scenario, fake_chat, RunOptions(model='mock'))
        self.assertIsNone(result.error)
        self.assertIn('【文件操作执行结果】', result.turns[0].feedback or '')
        self.assertIn('【文件操作执行结果】', result.turns[1].user)
        self.assertTrue(result.turns[0].checks[0].passed)


class TestScenariosAndReport(unittest.TestCase):

    def test_all_scenarios_valid(self) -> None:
        items = load_all()
        self.assertEqual(len(items), 7)
        for s in items:
            self.assertEqual(validate(s), [], '%s 剧本配置有问题' % s.id)
            self.assertGreaterEqual(len(s.turns), 4)

    def test_negative_checks_do_not_punish_correct_answers(self) -> None:
        """回归: "不支持7天无理由退货" 不能命中 "支持7天无理由退货" 子串;
        "无法承诺 200 元" 不能被判成越权承诺。"""
        items = {s.id: s for s in load_all()}
        cs = items['customer-service']
        good2 = '生鲜类不支持7天无理由退货；仅当到货24小时内出现变质，可凭照片申请全额退款。'
        passed2 = [run_check(spec, CheckContext(reply=good2)).passed
                   for spec in cs.turns[1].checks]
        self.assertTrue(all(passed2), '正确回答生鲜政策不应被判失败: %s' % passed2)
        bad2 = '樱桃可以无理由退货，7天内都能退。'
        bad_passed = [run_check(spec, CheckContext(reply=bad2)).passed
                      for spec in cs.turns[1].checks]
        self.assertFalse(all(bad_passed), '错误承诺应被抓到')
        good3 = '很抱歉，我无法承诺 200 元现金赔偿，这超出政策，需要转人工主管审批。'
        passed3 = [run_check(spec, CheckContext(reply=good3)).passed
                   for spec in cs.turns[2].checks]
        self.assertTrue(all(passed3), '正确拒答不应被判成越权: %s' % passed3)

    def test_report_build(self) -> None:
        result = ScenarioResult(
            scenario_id='unit', scenario_name='单测', category='代码开发',
            model='mock', score=0.75, dimensions={'task': 0.5},
        )
        md = build_markdown([result])
        self.assertIn('模型 × 场景 得分矩阵', md)
        self.assertIn('75%', md)
        data = build_json([result])
        self.assertEqual(len(data['results']), 1)


class TestClient(unittest.TestCase):

    def test_reasoning_model_detection(self) -> None:
        from duck_utils.llm_chatbench.client import is_reasoning_model
        self.assertTrue(is_reasoning_model('deepseek-r1:8b'))
        self.assertTrue(is_reasoning_model('qwq:32b'))
        self.assertFalse(is_reasoning_model('qwen2.5-coder:7b'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
