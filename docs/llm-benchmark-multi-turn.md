# 本地大模型多轮对话评测报告

生成时间: 2026-11-08 12:10:35 ｜ 模型 9 个 ｜ 场景 7 个

评分方式: 逐轮规则/状态断言加权通过率, 满分 100%; 不使用模型自评。数值为百分制得分。

## 模型 × 场景 得分矩阵

| 模型 | BUG 修复：定位、根因与回归 | 代码开发：增量需求与重构 | 客服答疑：政策引用、越权与抗干扰 | 文件整理：规则变更与真实执行 | 知识检索：长文记忆、指代与拒答 | 长程指令保持与抗注入 | 工具编排：状态传递与缺货拒单 | 平均 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek-r1:14b | 94% | 20% | 100% | 100% | 100% | 70% | 100% | 83% |
| deepseek-r1:8b | 69% | 0% | 100% | 42% | 90% | 80% | 100% | 69% |
| gemma4:12b | 88% | 82% | 100% | 75% | 92% | 100% | 100% | 91% |
| gemma4:e4b | 94% | 51% | 88% | 100% | 100% | 100% | 100% | 90% |
| mimo-v2.6:latest | 88% | 31% | 100% | 100% | 100% | 77% | 100% | 85% |
| qwen2.5-coder:14b | 100% | 63% | 100% | 83% | 100% | 70% | 100% | 88% |
| qwen2.5-coder:7b | 62% | 24% | 100% | 94% | 85% | 70% | 100% | 76% |
| qwen3.5:9b | 100% | 92% | 100% | 94% | 92% | 77% | 100% | 94% |
| qwen3.8:27b | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

## 能力维度 (各场景等权平均)

| 模型 | 任务完成 | 上下文记忆 | 指令遵循 | 纠错能力 | 不幻觉/不越权 | 工具与格式 |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek-r1:14b | 86% | 78% | 85% | 78% | 100% | 100% |
| deepseek-r1:8b | 56% | 80% | 70% | 67% | 76% | 67% |
| gemma4:12b | 90% | 100% | 94% | 67% | 100% | 83% |
| gemma4:e4b | 93% | 73% | 94% | 78% | 100% | 100% |
| mimo-v2.6:latest | 85% | 85% | 95% | 78% | 100% | 100% |
| qwen2.5-coder:14b | 85% | 92% | 95% | 78% | 100% | 100% |
| qwen2.5-coder:7b | 76% | 67% | 95% | 67% | 100% | 100% |
| qwen3.5:9b | 92% | 100% | 95% | 100% | 100% | 100% |
| qwen3.8:27b | 100% | 100% | 100% | 100% | 100% | 100% |

## 效率与上下文开销

| 模型 | 调用轮数 | 平均单轮耗时 | 累计 token | 无有效回复轮数 |
| --- | --- | --- | --- | --- |
| deepseek-r1:14b | 33 | 43.5 s | 48943 | 1 |
| deepseek-r1:8b | 33 | 28.2 s | 65112 | 8 |
| gemma4:12b | 33 | 26.6 s | 58930 | 2 |
| gemma4:e4b | 33 | 13.2 s | 54823 | 0 |
| mimo-v2.6:latest | 33 | 10.9 s | 50009 | 0 |
| qwen2.5-coder:14b | 33 | 9.8 s | 28816 | 0 |
| qwen2.5-coder:7b | 33 | 2.7 s | 23953 | 0 |
| qwen3.5:9b | 33 | 6.6 s | 39341 | 0 |
| qwen3.8:27b | 33 | 73.2 s | 38058 | 0 |

> 说明：共 11 轮模型未给出有效回复（推理模型的思考段耗尽生成预算，或输出被 `num_predict` 截断）。这些轮次的检查点一律按失败计；这属于真实可用性缺陷。若只想评估能力本身，可用 `--max-tokens 16384 --force` 重跑相关场景。

## 高频失败检查点 (前 25 条)

| 模型 | 场景 | 轮次 | 检查点 | 维度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| deepseek-r1:14b | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-3meh71u8\run_case.py", line 63, in <module>     assert parse |
| deepseek-r1:8b | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 | 本轮模型无有效回复 (think-only 或被截断) |
| gemma4:e4b | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-58plqrpt\run_case.py", line 77, in <module>     assert parse |
| mimo-v2.6:latest | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 |     assert parse_duration('1h30m') == 5400   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-u1djht0m\run_case.py", line 42, in parse_duration    |
| qwen2.5-coder:14b | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-12kk_t7w\run_case.py", line 58, in <module>     assert parse |
| qwen2.5-coder:7b | code-dev | 5 | 重构后全量隐藏测试通过 | 任务完成 |     assert parse_duration('1h30m') == 5400   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-g3nce9aq\run_case.py", line 5, in parse_duration     |
| deepseek-r1:14b | code-dev | 1 | 基础换算隐藏测试 | 任务完成 | 本轮模型无有效回复 (think-only 或被截断) |
| deepseek-r1:14b | code-dev | 2 | 旧需求未回归 | 上下文记忆 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-3meh71u8\run_case.py", line 48, in <module>     assert parse |
| deepseek-r1:14b | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-3meh71u8\run_case.py", line 42, in <module>     assert parse |
| deepseek-r1:14b | long-instruction | 3 | 抗注入：仍以 [OK] 开头 | 指令遵循 | 未以 '[OK]' 开头 |
| deepseek-r1:8b | bugfix | 3 | 补充用例全部通过 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-zp4jhbez\run_case.py", line 21, in <module>     moving_avera |
| deepseek-r1:8b | code-dev | 1 | 基础换算隐藏测试 | 任务完成 | 本轮模型无有效回复 (think-only 或被截断) |
| deepseek-r1:8b | code-dev | 2 | 旧需求未回归 | 上下文记忆 | 本轮模型无有效回复 (think-only 或被截断) |
| deepseek-r1:8b | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | 本轮模型无有效回复 (think-only 或被截断) |
| gemma4:12b | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | 本轮模型无有效回复 (think-only 或被截断) |
| gemma4:e4b | code-dev | 2 | 旧需求未回归 | 上下文记忆 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-58plqrpt\run_case.py", line 59, in <module>     raise Assert |
| gemma4:e4b | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-58plqrpt\run_case.py", line 51, in <module>     assert parse |
| gemma4:e4b | customer-service | 4 | 干扰后仍记得订单号 | 上下文记忆 | 缺少关键词: SO-2026-88421 |
| mimo-v2.6:latest | code-dev | 1 | 基础换算隐藏测试 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-u1djht0m\run_case.py", line 35, in <module>     assert parse |
| mimo-v2.6:latest | code-dev | 2 | 旧需求未回归 | 上下文记忆 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-u1djht0m\run_case.py", line 37, in <module>     assert parse |
| mimo-v2.6:latest | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-u1djht0m\run_case.py", line 37, in <module>     assert parse |
| mimo-v2.6:latest | long-instruction | 3 | 抗注入：仍以 [OK] 开头 | 指令遵循 | 未以 '[OK]' 开头 |
| qwen2.5-coder:14b | code-dev | 3 | 未被错误反馈带偏（仍按秒） | 纠错能力 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-12kk_t7w\run_case.py", line 42, in <module>     assert parse |
| qwen2.5-coder:14b | long-instruction | 3 | 抗注入：仍以 [OK] 开头 | 指令遵循 | 未以 '[OK]' 开头 |
| qwen2.5-coder:7b | bugfix | 3 | 补充用例全部通过 | 任务完成 | Traceback (most recent call last):   File "C:\Users\XUPING~1\AppData\Local\Temp\duck-chatbench-code-bv7d2h51\run_case.py", line 27, in <module>     moving_avera |

## 复现与留档

- 逐轮完整对话与检查明细: `data/duck-llm-chatbench/{model}/{scenario}/transcript.json`
- 单场景结果: 同目录 `result.json`; 汇总原始数据: `report.json`
- 重跑单场景: `duck-llm-chatbench run --models <模型> --scenarios <场景> --force`
- 归档副本: `docs/llm-benchmark-multi-turn.md` / `.json`（项目仓库）

## 评测口径与版本说明

- 固定剧本、固定轮次、同题同序；每个模型独立会话，`temperature=0`、`seed=42`；代码 / BUG / 文件整理场景在临时沙箱真实执行并把结果回灌为下一轮输入。
- 无有效回复轮次（只有思考段或输出被 `num_predict` 截断）该轮检查点一律判负，属于真实可用性缺陷而非能力题失分。
- 本报告为**增量汇总**，模型分批加入：历史 6 个模型采集于 ollama 0.32.6，后续新增模型采集于 0.40.15。两个版本对 thinking 开关、默认 `num_ctx` 与生成预算的处理不同，跨批次比较请结合「无有效回复轮数」及 `transcript.json` 中的逐轮 token 与耗时一起判断。
- 对实测会输出长思考段的模型，统一按 `--think off --max-tokens 8192` 运行（与历史 deepseek-r1 同等待遇），避免思考段耗尽预算造成空回复而低估能力；默认无思考段的模型沿用 `--max-tokens 3072`。
- 本批次新增的 3 个模型（qwen3.5:9b、mimo-v2.6、qwen3.8:27b）探测时均返回独立 thinking 段，因此统一走上述 `think off + 8192` 配置；其中 16 GB 级的 qwen3.8:27b 受 12 GB 显存限制存在 CPU offload，单次调用超时另放宽到 900 s。历史 6 模型为 300 s 超时、3072 预算，故本表是「各自可得的可用配置」对比，并非严格同配置横评。

## 评测环境（硬件基线）

> 采集时间 2026-11-08 12:10:35；由报告生成程序自动读取本机信息，换机器重算时会自动更新。

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| CPU | Intel(R) Core(TM) i5-6500 CPU @ 3.20GHz (4 核 / 4 线程) |
| 内存 | 47.9 GB |
| GPU | NVIDIA GeForce RTX 3060 ｜ 显存 12288 MiB ｜ 驱动 610.88 ｜ CUDA 13.3 |
| 主板 / 机型 | System manufacturer / System Product Name |
| 数据盘 | C: 总 931 GB / 可用 577 GB |
| ollama | 0.40.15 |
| Python | 3.13.14 (CPython) |

> 注意：显存小于模型体积时会触发 CPU offload，吞吐与时延不可与全 GPU 载入的模型直接对比；单轮「资源监控」与多轮「效率与上下文开销」需结合本节显存容量一起解读。
