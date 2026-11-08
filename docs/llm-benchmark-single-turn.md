# duck-llm-benchmark 汇总报告

> 数据源: `C:\Users\xupingmao\.duck-rush\data\duck-llm-benchmark`, 由 `duck-llm-benchmark report` 从各模型目录的落盘结果汇总; 模型 9 个 / 后端 5 个, 生成时间 2026-11-08 13:33:44。
> 「未安装」表示该后端当时不可用, 不是 0 分; lm-eval 为 gsm8k 20 题小样本, 推理型模型得 0.000 多因答案格式不匹配。
> 补跑的 thinking 模型使用 `--think-off` / `reasoning_effort=none` 保证正文可用, 与历史批次口径略有差异。
> 归档副本: `docs/llm-benchmark-single-turn.md` / `.json`（项目仓库, 由补跑流水线自动同步）。

| 模型 | ollama-speed | qa-basic | tool-call | lm-eval | opencompass |
| --- | --- | --- | --- | --- | --- |
| qwen3.8:27b | 2.0 tokens/s | 11/12 = 91.7% | 格式100% 调用100% | gsm8k=0.300 | localqa/accuracy=95.000 |
| qwen3.5:9b | 47.8 tokens/s | 10/12 = 83.3% | 格式100% 调用100% | gsm8k=0.000 | localqa/accuracy=90.000 |
| mimo-v2.6:latest | 51.8 tokens/s | 10/12 = 83.3% | 格式100% 调用100% | gsm8k=0.400 | localqa/accuracy=95.000 |
| gemma4:12b | 33.9 tokens/s | 10/12 = 83.3% | 格式88% 调用88% | gsm8k=0.000 | localqa/accuracy=95.000 |
| qwen2.5-coder:14b | 32.5 tokens/s | 11/12 = 91.7% | 格式100% 调用100% | gsm8k=0.560 | localqa/accuracy=95.000 |
| qwen2.5-coder:7b | 58.5 tokens/s | 9/12 = 75.0% | 格式100% 调用100% | gsm8k=0.667 | localqa/accuracy=95.000 |
| gemma4:e4b | 61.4 tokens/s | 11/12 = 91.7% | 格式88% 调用88% | gsm8k=0.000 | localqa/accuracy=75.000 |
| deepseek-r1:14b | 32.2 tokens/s | 10/12 = 83.3% | 格式100% 调用100% | gsm8k=0.050 | localqa/accuracy=100.000 |
| deepseek-r1:8b | 52.4 tokens/s | 10/12 = 83.3% | 格式62% 调用62% | gsm8k=0.000 | localqa/accuracy=95.000 |

## 资源监控 (运行期间 均值/峰值)

| 模型 | CPU% | 内存% | GPU% | 显存峰值(MB) |
| --- | --- | --- | --- | --- |
| qwen3.8:27b | 94.4/100.0 | 67.1/68 | 20.7/100.0 | 11182.0 |
| qwen3.5:9b | 37.4/43.7 | 33.1/34 | 51.1/85.0 | 7129.0 |
| mimo-v2.6:latest | 41.3/51.8 | 33.4/34 | 63.2/91.0 | 7129.0 |
| gemma4:12b | 35.4/77.5 | 34.9/38 | 6.4/99.0 | 9470.0 |
| qwen2.5-coder:14b | 36.3/77.4 | 34.1/36 | 9.4/83.0 | 9952.0 |
| qwen2.5-coder:7b | 30.4/45.7 | 31.6/32 | 4.0/31.0 | 5276.0 |
| gemma4:e4b | 39.8/97.5 | 34.1/36 | 2.4/44.0 | 5111.0 |
| deepseek-r1:14b | 42.0/91.2 | 35.5/37 | 60.6/96.0 | 9943.0 |
| deepseek-r1:8b | 49.8/100.0 | 34.7/37 | 27.9/100.0 | 6237.0 |

## 评测环境（硬件基线）

> 采集时间 2026-11-08 13:33:44；由报告生成程序自动读取本机信息，换机器重算时会自动更新。

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| CPU | Intel(R) Core(TM) i5-6500 CPU @ 3.20GHz (4 核 / 4 线程) |
| 内存 | 47.9 GB |
| GPU | NVIDIA GeForce RTX 3060 ｜ 显存 12288 MiB ｜ 驱动 610.88 ｜ CUDA 13.3 |
| 主板 / 机型 | System manufacturer / System Product Name |
| 数据盘 | C: 总 931 GB / 可用 593 GB |
| ollama | 0.40.15 |
| Python | 3.10.10 (CPython) |

> 注意：显存小于模型体积时会触发 CPU offload，吞吐与时延不可与全 GPU 载入的模型直接对比；单轮「资源监控」与多轮「效率与上下文开销」需结合本节显存容量一起解读。
