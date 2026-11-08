# -*- coding: utf-8 -*-
# @filename duck-llm-benchmark.py
# @description 本地 ollama 小模型 benchmark 工具
"""duck-llm-benchmark -- 本地 ollama 小模型 benchmark 工具

用法:
  duck-llm-benchmark list                       列出已下载的 ollama 模型
  duck-llm-benchmark tools                      列出各 benchmark 后端及可用性
  duck-llm-benchmark run [MODEL...] [选项]      对模型跑 benchmark (默认跑全部已注册后端)
  duck-llm-benchmark report [MODEL...]          汇总已保存的评测结果

子命令可用 'duck-llm-benchmark <子命令> -h' 查看详细选项。
评测后端包括内置的 推理速度/基础问答/函数调用, 以及外部框架
lm-evaluation-harness (已接入, 通过 ollama 的 OpenAI 兼容接口评测) 与
OpenCompass (已接入, 通过 OpenAISDK 后端指向本地 ollama, 用自定义 QA 数据集评测)。
"""

import sys
import os
import json
import glob
import shutil
import argparse
import subprocess
import threading
import time
import platform
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable

try:
    from termcolor import colored as _colored
except Exception:
    def _fallback_colored(text, color=None, on_color=None, attrs=None, **kwargs):
        return str(text)
    _colored = _fallback_colored


def bright(text, color):
    """用浅亮色输出 (termcolor 默认色在深色背景下已足够明亮)。"""
    return _colored(str(text), color)


def get_data_dir():
    """命令数据目录, 优先用 duck_utils, 否则回退到 ~/.duck-rush/data/duck-llm-benchmark。"""
    try:
        from duck_utils.os_util import get_command_data_dir
        return get_command_data_dir('duck-llm-benchmark')
    except Exception:
        d = os.path.join(os.path.expanduser('~'), '.duck-rush', 'data', 'duck-llm-benchmark')
        os.makedirs(d, exist_ok=True)
        return d


def _safe(name):
    """把模型名转成安全的目录名。"""
    return name.replace('/', '_').replace(':', '_').replace(' ', '_')


def model_dir(model):
    d = os.path.join(get_data_dir(), _safe(model))
    os.makedirs(d, exist_ok=True)
    return d


@dataclass
class BenchResult:
    tool: str
    model: str
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    summary: str = ''
    raw_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            'tool': self.tool,
            'model': self.model,
            'ok': self.ok,
            'metrics': self.metrics,
            'summary': self.summary,
            'raw_path': self.raw_path,
            'error': self.error,
        }


@dataclass
class BenchTool:
    name: str
    desc: str
    builtin: bool
    available_fn: Callable
    run_fn: Callable
    install_hint: str = ''

    def available(self):
        try:
            return bool(self.available_fn())
        except Exception:
            return False

    def run(self, model, opts):
        try:
            return self.run_fn(model, opts)
        except subprocess.TimeoutExpired:
            return BenchResult(self.name, model, False, error='timeout')
        except Exception as e:
            return BenchResult(self.name, model, False, error=str(e))


@dataclass
class RunOpts:
    limit: Optional[int] = None
    tasks: str = 'gsm8k'
    keepalive: str = '5m'
    timeout: int = 1800
    think_off: bool = False


def ollama_run(model, prompt, keepalive, timeout, think_off=False):
    """调用 ollama run, 返回 (回答文本, 含 --verbose 计时信息的合并输出)。

    thinking 模型默认会把完整思考过程写进 stdout, 关键词/JSON 断言会被污染,
    因此补跑新模型时可用 --think-off 关闭 (对不支持思考的旧模型无副作用)。
    """
    cmd = ['ollama', 'run', model, prompt, '--verbose', '--nowordwrap',
           '--keepalive', keepalive]
    if think_off:
        cmd.append('--think=false')
    # 后台任务里 stdin 常是「已打开但无数据」的管道, ollama CLI 会把它当成交互式
    # 会话而一直等待输入, 直到单题超时; 显式给 DEVNULL 让它输出完立即退出。
    # encoding/errors 显式指定, 避免 Windows 默认 GBK 解码 spinner/特殊字符时报错。
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          stdin=subprocess.DEVNULL,
                          encoding='utf-8', errors='replace')
    out = (proc.stdout or '') + '\n' + (proc.stderr or '')
    return proc.stdout or '', out


def _int(s):
    if not s:
        return None
    num = s.strip().split()[0] if s.strip() else ''
    try:
        return int(num)
    except Exception:
        return None


def _parse_duration_ms(s):
    if not s:
        return None
    num = ''
    unit = ''
    for ch in s.strip():
        if ch.isdigit() or ch == '.':
            num += ch
        else:
            unit += ch
    unit = unit.strip().lower()
    try:
        val = float(num)
    except Exception:
        return None
    if unit.startswith('ns'):
        return val / 1e6
    if unit.startswith('us') or unit.startswith('µs'):
        return val / 1e3
    if unit.startswith('ms'):
        return val
    if unit.startswith('s'):
        return val * 1000
    if unit.startswith('m'):
        return val * 60000
    return None


def ollama_installed():
    return shutil.which('ollama') is not None


# ---------------------------------------------------------------------------
# 模型实例管控与系统资源监控
# ---------------------------------------------------------------------------
def stop_other_models(except_name=None):
    """关闭除 except_name 之外正在运行的 ollama 模型, 避免同时驻留多个模型占用资源。"""
    if not ollama_installed():
        return
    try:
        proc = subprocess.run(['ollama', 'ps'], capture_output=True, text=True, timeout=30)
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
            subprocess.run(['ollama', 'stop', name], capture_output=True, text=True, timeout=60)
        except Exception:
            pass


_IS_WIN = platform.system() == 'Windows'
_cpu_prev = None  # 跨采样保留的 CPU 时间快照 (idle, total)


def _win_cpu_times():
    try:
        import ctypes
        idle = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        return idle.value, kernel.value + user.value
    except Exception:
        return None


def _linux_cpu_times():
    try:
        with open('/proc/stat') as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3]
        total = sum(parts)
        return idle, total
    except Exception:
        return None


def sample_cpu():
    """返回 CPU 使用率(百分比), 无可用数据时返回 None。"""
    global _cpu_prev
    times = _win_cpu_times() if _IS_WIN else _linux_cpu_times()
    if times is None:
        return None
    idle, total = times
    if _cpu_prev is None:
        _cpu_prev = times
        return None
    d_idle = idle - _cpu_prev[0]
    d_total = total - _cpu_prev[1]
    _cpu_prev = times
    if d_total <= 0:
        return None
    return round((1 - d_idle / d_total) * 100, 1)


def _win_mem():
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
            ]
        s = MEMORYSTATUSEX()
        s.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
        used = (s.ullTotalPhys - s.ullAvailPhys) / 1e9
        total = s.ullTotalPhys / 1e9
        return s.dwMemoryLoad, used, total
    except Exception:
        return None, None, None


def _linux_mem():
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                parts = line.split()
                if parts[0] == 'MemTotal:':
                    info['total'] = int(parts[1]) * 1024
                elif parts[0] == 'MemAvailable:':
                    info['avail'] = int(parts[1]) * 1024
        total = info.get('total')
        if total is None:
            return None, None, None
        avail = info.get('avail')
        used = (total - avail) if avail is not None else None
        percent = round(used / total * 100, 1) if used is not None else None
        return percent, (used / 1e9) if used is not None else None, total / 1e9
    except Exception:
        return None, None, None


def sample_mem():
    """返回 (内存使用率%, 已用GB, 总GB), 无可用数据时返回 (None, None, None)。"""
    return _win_mem() if _IS_WIN else _linux_mem()


def sample_gpu():
    """返回 GPU 显存/利用率(通过 nvidia-smi), 无 GPU 或命令缺失时返回 None。"""
    try:
        proc = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10)
        line = (proc.stdout or '').strip().splitlines()
        if line:
            p = [x.strip() for x in line[0].split(',')]
            return {'gpu_util': float(p[0]),
                    'gpu_mem_used_mb': float(p[1]),
                    'gpu_mem_total_mb': float(p[2])}
    except Exception:
        return None
    return None


class SystemMonitor:
    """后台采样 CPU/内存/GPU 使用率, 用于评测期间资源监控。"""

    def __init__(self, interval=1.0):
        self.interval = interval
        self.records = []
        self._stop = False
        self._thread = None

    def _loop(self):
        while not self._stop:
            rec = {}
            cpu = sample_cpu()
            mem = sample_mem()
            gpu = sample_gpu()
            if cpu is not None:
                rec['cpu'] = cpu
            if mem[0] is not None:
                rec['mem_percent'] = mem[0]
            if mem[1] is not None:
                rec['mem_used_gb'] = mem[1]
            if mem[2] is not None:
                rec['mem_total_gb'] = mem[2]
            if gpu is not None:
                rec['gpu'] = gpu
            self.records.append(rec)
            time.sleep(self.interval)

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=3)

    def summary(self):
        if not self.records:
            return None

        def agg(key):
            vals = [r[key] for r in self.records if key in r]
            if not vals:
                return None
            return round(sum(vals) / len(vals), 1), round(max(vals), 1)

        s: Dict[str, Any] = {}
        cpu = agg('cpu')
        if cpu:
            s['cpu_avg'] = cpu[0]
            s['cpu_max'] = cpu[1]
        mem = agg('mem_percent')
        if mem:
            s['mem_avg_percent'] = mem[0]
            s['mem_max_percent'] = mem[1]
        mu = agg('mem_used_gb')
        if mu:
            s['mem_peak_used_gb'] = mu[1]
        mt = agg('mem_total_gb')
        if mt:
            s['mem_total_gb'] = mt[0]
        gpu_utils = [r['gpu']['gpu_util'] for r in self.records if 'gpu' in r]
        gpu_mems = [r['gpu']['gpu_mem_used_mb'] for r in self.records if 'gpu' in r]
        if gpu_utils:
            s['gpu_util_avg'] = round(sum(gpu_utils) / len(gpu_utils), 1)
            s['gpu_util_max'] = round(max(gpu_utils), 1)
        if gpu_mems:
            s['gpu_mem_peak_mb'] = round(max(gpu_mems), 0)
        return s


def save_system_metrics(model, summary):
    path = os.path.join(model_dir(model), 'system.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def load_system_metrics(model):
    path = os.path.join(model_dir(model), 'system.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def format_resource(summary):
    if not summary:
        return 'N/A'
    parts = []
    if 'cpu_avg' in summary:
        parts.append('CPU %s%%/%s%%' % (summary['cpu_avg'], summary['cpu_max']))
    if 'mem_avg_percent' in summary:
        parts.append('MEM %s%%/%s%%' % (summary['mem_avg_percent'], summary['mem_max_percent']))
    if 'gpu_util_avg' in summary:
        parts.append('GPU %s%%/%s%%' % (summary['gpu_util_avg'], summary['gpu_util_max']))
    return ' '.join(parts) if parts else 'N/A'


SPEED_PROMPT = '请描写春天, 至少写 300 字, 不要停。'


def run_speed(model, opts):
    """用 ollama run --verbose 测生成吞吐与首 token 延迟。"""
    _, verbose = ollama_run(model, SPEED_PROMPT, opts.keepalive, opts.timeout,
                            opts.think_off)
    metrics = {}
    for line in verbose.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith('eval rate:'):
            v = s.split(':', 1)[1].strip()
            num = v.split()[0] if v else ''
            if num.replace('.', '', 1).isdigit():
                metrics['tokens_per_sec'] = float(num)
        elif low.startswith('eval count:'):
            metrics['eval_count'] = _int(s.split(':', 1)[1])
        elif low.startswith('total duration:'):
            metrics['total_duration_ms'] = _parse_duration_ms(s.split(':', 1)[1])
        elif low.startswith('prompt eval count:'):
            metrics['prompt_eval_count'] = _int(s.split(':', 1)[1])
        elif low.startswith('prompt eval duration:'):
            pec = metrics.get('prompt_eval_count') or 0
            dms = _parse_duration_ms(s.split(':', 1)[1]) or 0
            if pec:
                metrics['first_token_ms'] = round(dms / pec, 2)
    ok = 'tokens_per_sec' in metrics
    if ok:
        summary = '%.1f tokens/s' % metrics['tokens_per_sec']
    else:
        summary = 'parse-failed'
    return BenchResult('ollama-speed', model, ok, metrics, summary)


QA_QUESTIONS = [
    {'q': '中国的首都是哪里?', 'keywords': ['北京']},
    {'q': '1 + 1 等于多少?', 'keywords': ['2']},
    {'q': '世界上最高的山峰是哪座?', 'keywords': ['珠穆朗玛', '珠峰']},
    {'q': '水的化学式是什么?', 'keywords': ['h2o', 'H2O']},
    {'q': '一年有多少个月?', 'keywords': ['12', '十二']},
    {'q': '红楼梦的作者是谁?', 'keywords': ['曹雪芹']},
    {'q': '太阳系中最大的行星是哪个?', 'keywords': ['木星']},
    {'q': '圆周率 pi 约等于几 (取前两位)?', 'keywords': ['3.14', '3.1416', '三点一四']},
    {'q': '英语中 苹果 怎么说?', 'keywords': ['apple', 'Apple']},
    {'q': '地球自转一圈大约需要多少小时?', 'keywords': ['24', '二十四']},
    {'q': '计算机的 CPU 中文全称是什么?', 'keywords': ['中央处理器']},
    {'q': '光在真空中的速度约是多少?', 'keywords': ['30万', '3亿', 'km/s', '千米每秒', '公里每秒']},
]


def run_qa(model, opts):
    items = QA_QUESTIONS
    if opts.limit:
        items = items[: opts.limit]
    correct = 0
    total = len(items)
    for it in items:
        # 大模型 CPU offload / 首次加载可能超过 120s, 放宽到 300s 避免整批误判超时
        ans, _ = ollama_run(model, it['q'], opts.keepalive, 300, opts.think_off)
        ans_l = ans.lower()
        hit = any(k.lower() in ans_l for k in it['keywords'])
        if hit:
            correct += 1
    acc = correct / total if total else 0
    metrics = {'correct': correct, 'total': total, 'accuracy': round(acc, 4)}
    summary = '%d/%d = %.1f%%' % (correct, total, acc * 100)
    return BenchResult('qa-basic', model, total > 0, metrics, summary)


TOOL_CALLS = [
    {'instruction': '查询北京今天的天气', 'functions': [
        {'name': 'get_weather', 'description': '查询城市天气', 'parameters': ['city']}], 'expected': 'get_weather', 'required': ['city']},
    {'instruction': '把 100 元人民币换成美元', 'functions': [
        {'name': 'exchange', 'description': '货币兑换', 'parameters': ['amount', 'currency']}], 'expected': 'exchange', 'required': ['amount']},
    {'instruction': '设置一个 30 分钟后提醒我开会', 'functions': [
        {'name': 'set_reminder', 'description': '设置提醒', 'parameters': ['minutes', 'text']}], 'expected': 'set_reminder', 'required': ['minutes']},
    {'instruction': '计算 23 乘以 47', 'functions': [
        {'name': 'calculator', 'description': '计算器', 'parameters': ['expression']}], 'expected': 'calculator', 'required': ['expression']},
    {'instruction': '播放周杰伦的歌', 'functions': [
        {'name': 'play_music', 'description': '播放音乐', 'parameters': ['artist', 'song']}], 'expected': 'play_music', 'required': ['artist']},
    {'instruction': '发邮件给张三说你好', 'functions': [
        {'name': 'send_email', 'description': '发送邮件', 'parameters': ['to', 'body']}], 'expected': 'send_email', 'required': ['to']},
    {'instruction': '搜索附近的咖啡店', 'functions': [
        {'name': 'search_places', 'description': '搜索地点', 'parameters': ['keyword', 'location']}], 'expected': 'search_places', 'required': ['keyword']},
    {'instruction': '把 你好 翻译成英文', 'functions': [
        {'name': 'translate', 'description': '翻译文本', 'parameters': ['text', 'target_lang']}], 'expected': 'translate', 'required': ['text']},
]


def build_tool_prompt(it):
    lines = []
    lines.append('你是一个函数调用助手。根据用户指令, 从下面的函数中选择最合适的一个, 并只输出严格 JSON:')
    lines.append('{"name": "<函数名>", "arguments": {<参数键值对>}}')
    lines.append('不要输出任何解释或多余文字。')
    lines.append('')
    lines.append('可用函数:')
    for fn in it['functions']:
        params = ', '.join(fn['parameters'])
        lines.append('- %s(%s): %s' % (fn['name'], params, fn['description']))
    lines.append('')
    lines.append('用户指令: %s' % it['instruction'])
    return '\n'.join(lines)


def extract_json(text):
    fence = chr(96) * 3
    text = text.strip()
    if fence in text:
        parts = text.split(fence)
        if len(parts) >= 3:
            text = parts[1]
            if text.lower().startswith('json'):
                text = text[4:]
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end < start:
        return None
    sub = text[start:end + 1]
    try:
        obj = json.loads(sub)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def run_toolcall(model, opts):
    items = TOOL_CALLS
    if opts.limit:
        items = items[: opts.limit]
    fmt_ok = 0
    call_ok = 0
    total = len(items)
    for it in items:
        prompt = build_tool_prompt(it)
        ans, _ = ollama_run(model, prompt, opts.keepalive, 300, opts.think_off)
        parsed = extract_json(ans)
        if parsed is None:
            continue
        fmt_ok += 1
        name = parsed.get('name')
        args = parsed.get('arguments', {}) or {}
        if name == it['expected'] and all(r in args for r in it.get('required', [])):
            call_ok += 1
    fmt_rate = fmt_ok / total if total else 0
    call_rate = call_ok / total if total else 0
    metrics = {'format_ok': fmt_ok, 'call_ok': call_ok, 'total': total,
               'format_rate': round(fmt_rate, 4), 'call_rate': round(call_rate, 4)}
    summary = '格式%.0f%% 调用%.0f%%' % (fmt_rate * 100, call_rate * 100)
    return BenchResult('tool-call', model, total > 0, metrics, summary)


def lmeval_installed():
    """lm-evaluation-harness 是否已安装 (py 模块可被导入即可)。"""
    try:
        import importlib.util
        return importlib.util.find_spec('lm_eval') is not None
    except Exception:
        return False


def _parse_lmeval(out_dir):
    metrics = {}
    # 优先读顶层 results.json, 否则递归查找含 results 的文件
    candidates = [os.path.join(out_dir, 'results.json')]
    candidates += sorted(glob.glob(os.path.join(out_dir, '**', '*.json'), recursive=True))
    for f in candidates:
        if not os.path.exists(f):
            continue
        try:
            with open(f, encoding='utf-8') as fp:
                data = json.load(fp)
        except Exception:
            continue
        results = data.get('results') if isinstance(data, dict) else None
        if results:
            for task, vals in results.items():
                if isinstance(vals, dict):
                    for k, v in vals.items():
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            metrics['%s/%s' % (task, k)] = round(float(v), 4)
            break
    return metrics


def run_lmeval(model, opts):
    """调用 lm-evaluation-harness 评测 ollama 模型。

    ollama 提供 OpenAI 兼容接口 (默认 http://localhost:11434/v1/completions),
    用 lm-eval 的 local-completions 后端接入。生成类任务 (如 gsm8k) 以纯文本
    prompt 发送并取回续写文本 (tokenized_requests=False, 规避 ollama 不接收
    token 数组 prompt 的限制); loglikelihood 类任务 (hellaswag/arc 等需要模型
    返回 token logprobs, ollama 的 OpenAI 接口不返回) 在此后端下不可用。
    无需额外 API key。
    """
    out_dir = os.path.join(model_dir(model), 'lm-eval-out')
    # lm-eval 每次运行会写出带时间戳的新 results 文件而不覆盖旧的,
    # 先清空目录, 保证只解析本次结果, 避免读到历史(旧 limit)的脏数据
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    cmd = [sys.executable, '-m', 'lm_eval', 'run',
           '--model', 'local-completions',
           '--model_args',
           'model=%s,base_url=http://localhost:11434/v1/completions,'
           'tokenizer_backend=huggingface,tokenizer=bert-base-uncased,'
           'tokenized_requests=False' % model,
           '--tasks', opts.tasks, '--output_path', out_dir]
    if opts.limit:
        cmd += ['--limit', str(opts.limit)]
    # 数据集多来自 HuggingFace, 国内走镜像加速下载
    env = dict(os.environ)
    env.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=opts.timeout, env=env,
                              stdin=subprocess.DEVNULL,
                              encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        return BenchResult('lm-eval', model, False,
                           error='timeout (%ds)' % opts.timeout, raw_path=out_dir)
    if proc.returncode != 0:
        combined = (proc.stderr or '') + '\n' + (proc.stdout or '')
        tail = [l for l in combined.splitlines() if l.strip()][-5:]
        err = ' '.join(tail[-2:]) if tail else '未知错误'
        return BenchResult('lm-eval', model, False,
                           error='lm_eval 失败: ' + err, raw_path=out_dir)
    metrics = _parse_lmeval(out_dir)
    ok = bool(metrics)
    summary = _lmeval_summary(metrics)
    return BenchResult('lm-eval', model, ok, metrics, summary, raw_path=out_dir)


def _lmeval_summary(metrics):
    """把 lm-eval 指标压缩成每个任务一个代表性分数, 便于表格展示。"""
    by_task = {}
    for k, v in metrics.items():
        if '/' not in k:
            continue
        task, name = k.split('/', 1)
        by_task.setdefault(task, []).append((name, v))
    parts = []
    for task in sorted(by_task):
        items = by_task[task]
        pick = None
        for pref in ('flexible-extract', 'exact_match', 'acc', 'em'):
            for name, v in items:
                if pref in name:
                    pick = v
                    break
            if pick is not None:
                break
        if pick is None and items:
            pick = items[0][1]
        if pick is not None:
            parts.append('%s=%.3f' % (task, pick))
    return ', '.join(parts) if parts else '(no metric)'


def opencompass_installed():
    """OpenCompass 是否已安装 (py 模块可被导入即可)。"""
    try:
        import importlib.util
        return importlib.util.find_spec('opencompass') is not None
    except Exception:
        return False


# OpenCompass 评测所需资源 (评测器模块 + 自定义 QA 数据集), 放在数据目录下,
# 由 run_opencompass 自动生成/引用; oc_eval 需在子进程中可被导入 (通过 PYTHONPATH)。
_OC_DIR = os.path.join(get_data_dir(), 'opencompass')
_OC_EVAL = os.path.join(_OC_DIR, 'oc_eval.py')
_OC_DATA = os.path.join(_OC_DIR, 'localqa.jsonl')

_OC_EVAL_SRC = '''# -*- coding: utf-8 -*-
"""OpenCompass 自定义评测器: 宽松的包含匹配 (大小写不敏感)。

OpenCompass 内置 AccEvaluator 用的是 HuggingFace accuracy (严格精确匹配),
对本地小模型的自由文本回答过于严苛。这里用 参考答案是否作为子串出现在
模型回答中 (归一化后) 来判断正确性, 适合本地 ollama 模型的事实类问答。
"""

from opencompass.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator
from opencompass.registry import ICL_EVALUATORS


def _norm(s):
    if s is None:
        return ''
    s = str(s).strip().lower()
    for ch in ' 。.，,、；;：:！!？?（）()[]【】"\\\\' \\\\t\\\\n':
        s = s.replace(ch, '')
    return s


@ICL_EVALUATORS.register_module()
class ContainsEvaluator(BaseEvaluator):
    """预测文本中包含参考答案 (归一化后) 即判对。"""

    def score(self, predictions, references, test_set=None):
        total = len(predictions)
        correct = 0
        for pred, ref in zip(predictions, references):
            if _norm(ref) and _norm(ref) in _norm(pred):
                correct += 1
        acc = (correct / total * 100.0) if total else 0.0
        return {'accuracy': round(acc, 4), 'correct': correct, 'total': total}
'''

_OC_DATA_ROWS = [
    ("中国的首都是哪里？", "北京"),
    ("1加1等于多少？", "2"),
    ("世界上最高的山峰是哪座？", "珠穆朗玛峰"),
    ("水的化学式是什么？", "H2O"),
    ("一年有多少个月？", "12"),
    ("《红楼梦》的作者是谁？", "曹雪芹"),
    ("太阳系中体积最大的行星是哪一颗？", "木星"),
    ("圆周率 pi 的前三位有效数字是多少？", "3.14"),
    ("英语中 苹果 怎么说？", "apple"),
    ("地球自转一圈大约需要多少小时？", "24"),
    ("计算机的 CPU 中文全称是什么？", "中央处理器"),
    ("光在真空中的速度约是多少千米每秒？", "300000"),
    ("七大洲中面积最大的是哪一个？", "亚洲"),
    ("人体最大的器官是什么？", "皮肤"),
    ("第一次世界大战爆发于哪一年？", "1914"),
    ("一个正方形有几条对称轴？", "4"),
    ("化学元素铁的符号是什么？", "Fe"),
    ("一年中有几个月有31天？", "7"),
    ("二进制中 101 对应的十进制数是多少？", "5"),
    ("中国的国宝动物是什么？", "熊猫"),
]


def _ensure_oc_assets():
    """确保 OpenCompass 评测所需的评测器模块与数据集存在。"""
    os.makedirs(_OC_DIR, exist_ok=True)
    if not os.path.exists(_OC_EVAL):
        with open(_OC_EVAL, 'w', encoding='utf-8') as f:
            f.write(_OC_EVAL_SRC)
    if not os.path.exists(_OC_DATA):
        with open(_OC_DATA, 'w', encoding='utf-8') as f:
            for q, a in _OC_DATA_ROWS:
                f.write(json.dumps({'question': q, 'answer': a},
                                   ensure_ascii=False) + '\n')


def _write_oc_config(model, config_path):
    """为指定 ollama 模型生成 OpenCompass 配置文件 (OpenAISDK 指向本地 ollama)。"""
    safe = _safe(model)
    cfg = []
    cfg.append('from opencompass.models import OpenAISDK')
    cfg.append('from opencompass.datasets import CustomDataset')
    cfg.append('from opencompass.openicl.icl_prompt_template import PromptTemplate')
    cfg.append('from opencompass.openicl.icl_retriever import ZeroRetriever')
    cfg.append('from opencompass.openicl.icl_inferencer import GenInferencer')
    cfg.append('from oc_eval import ContainsEvaluator')
    cfg.append('')
    cfg.append('api_meta_template = dict(round=[')
    cfg.append("    dict(role='HUMAN', api_role='HUMAN'),")
    cfg.append("    dict(role='BOT', api_role='BOT', generate=True),")
    cfg.append('])')
    cfg.append('')
    cfg.append('models = [')
    cfg.append("    dict(abbr='%s', type=OpenAISDK," % safe)
    cfg.append("         path='%s', openai_api_base='http://localhost:11434/v1'," % model)
    cfg.append("         key='sk-no-key-required', meta_template=api_meta_template,")
    cfg.append("         query_per_second=2, max_out_len=1024, max_seq_len=4096, batch_size=8,")
    # /v1/chat/completions 会把 thinking 单独放进 reasoning 字段, 思考耗尽预算时
    # content 为空; reasoning_effort=none 对 thinking 模型关闭思考, 旧模型会忽略。
    cfg.append("         extra_body=dict(reasoning_effort='none')),")
    cfg.append(']')
    cfg.append('')
    cfg.append("DATA_PATH = r'%s'" % _OC_DATA)
    cfg.append("reader_cfg = dict(input_columns=['question'], output_column='answer')")
    cfg.append('infer_cfg = dict(')
    cfg.append('    prompt_template=dict(')
    cfg.append('        type=PromptTemplate,')
    cfg.append('        template=dict(round=[dict(role=\'HUMAN\',')
    cfg.append('                              prompt=\'请回答以下问题，只输出答案本身，不要任何解释：\\n{question}\')])),')
    cfg.append('    retriever=dict(type=ZeroRetriever),')
    cfg.append('    inferencer=dict(type=GenInferencer),')
    cfg.append(')')
    cfg.append("eval_cfg = dict(evaluator=dict(type=ContainsEvaluator), pred_role='BOT')")
    cfg.append('')
    cfg.append('datasets = [dict(abbr=\'localqa\', type=CustomDataset, path=DATA_PATH,')
    cfg.append('                 reader_cfg=reader_cfg, infer_cfg=infer_cfg, eval_cfg=eval_cfg)]')
    cfg.append('')
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cfg) + '\n')


def _parse_opencompass(out_dir):
    """从 OpenCompass 输出目录解析 accuracy 等指标。

    OpenCompass 把汇总写入 <work_dir>/<时间戳>/summary/summary_<时间戳>.csv,
    其中 metric 列为 'accuracy' 的行给出该模型的得分。
    """
    metrics = {}
    cands = sorted(glob.glob(os.path.join(out_dir, '**', 'summary_*.csv'),
                            recursive=True))
    if not cands:
        return metrics
    csv_path = cands[-1]
    try:
        with open(csv_path, encoding='utf-8') as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
    except Exception:
        return metrics
    if len(lines) < 2:
        return metrics
    header = [h.strip() for h in lines[0].split(',')]
    # 找到 accuracy 行, 取模型名列 (最后一列) 的值
    try:
        metric_idx = header.index('metric')
        val_idx = len(header) - 1
    except Exception:
        return metrics
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) <= val_idx:
            continue
        if parts[metric_idx] == 'accuracy':
            try:
                metrics['localqa/accuracy'] = round(float(parts[val_idx]), 4)
            except Exception:
                pass
    return metrics


def run_opencompass(model, opts):
    """调用 OpenCompass 评测 ollama 模型。

    通过 OpenCompass 的 OpenAISDK 后端 (OpenAI 兼容接口) 指向本地 ollama
    的 http://localhost:11434/v1, 用自定义 QA 数据集 (localqa) 评测事实类
    问答能力; 评测器为宽松的包含匹配 (ContainsEvaluator), 避免内置精确匹配
    对自由文本过于严苛。无需额外 API key。
    """
    _ensure_oc_assets()
    out_dir = os.path.join(model_dir(model), 'opencompass-out')
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    config_path = os.path.join(_OC_DIR, '%s_config.py' % _safe(model))
    _write_oc_config(model, config_path)
    env = dict(os.environ)
    # 让 OpenCompass 的任务子进程也能 import 自定义评测器 oc_eval
    env['PYTHONPATH'] = _OC_DIR + os.pathsep + env.get('PYTHONPATH', '')
    # opencompass 以控制台脚本形式安装, 没有 __main__ 模块, 需直接调用其可执行文件
    oc_bin = shutil.which('opencompass') or (sys.executable + ' -m opencompass')
    cmd = [oc_bin, config_path, '--debug', '--work-dir', out_dir]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=opts.timeout, env=env,
                              stdin=subprocess.DEVNULL,
                              encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        return BenchResult('opencompass', model, False,
                           error='timeout (%ds)' % opts.timeout, raw_path=out_dir)
    if proc.returncode != 0:
        combined = (proc.stderr or '') + '\n' + (proc.stdout or '')
        tail = [l for l in combined.splitlines() if l.strip()][-5:]
        err = ' '.join(tail[-2:]) if tail else '未知错误'
        return BenchResult('opencompass', model, False,
                           error='opencompass 失败: ' + err, raw_path=out_dir)
    metrics = _parse_opencompass(out_dir)
    ok = bool(metrics)
    summary = ', '.join('%s=%.3f' % (k, v)
                        for k, v in metrics.items()) or '(no metric)'
    return BenchResult('opencompass', model, ok, metrics, summary, raw_path=out_dir)


def build_tools():
    return [
        BenchTool('ollama-speed', '推理速度(tokens/s、首token延迟)', True,
                  ollama_installed, run_speed),
        BenchTool('qa-basic', '基础问答正确率(内置12题)', True,
                  ollama_installed, run_qa),
        BenchTool('tool-call', '函数调用正确率(BFCL风格)', True,
                  ollama_installed, run_toolcall),
        BenchTool('lm-eval', 'lm-evaluation-harness', False,
                  lmeval_installed, run_lmeval, install_hint='pip install "lm-eval[api]"'),
        BenchTool('opencompass', 'OpenCompass', False,
                  opencompass_installed, run_opencompass, install_hint='pip install opencompass'),
    ]


def list_models():
    if not ollama_installed():
        return []
    try:
        proc = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    lines = (proc.stdout or '').splitlines()
    models = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        mid = parts[1]
        # 末 3 个 token 为 MODIFIED(如 "34 minutes ago"), 中间为 SIZE(如 "8.0 GB")
        modified = ' '.join(parts[-3:])
        size = ' '.join(parts[2:-3]) if len(parts) > 5 else (parts[2] if len(parts) > 2 else '')
        models.append({'name': name, 'id': mid, 'size': size, 'modified': modified})
    return models


def save_models(models):
    path = os.path.join(get_data_dir(), 'models.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(models, f, ensure_ascii=False, indent=2)


def load_models():
    path = os.path.join(get_data_dir(), 'models.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def save_result(model, tool, res):
    path = os.path.join(model_dir(model), tool + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(res.to_dict(), f, ensure_ascii=False, indent=2)


def load_result(model, tool):
    path = os.path.join(model_dir(model), tool + '.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return BenchResult(**json.load(f))
    except Exception:
        return None


def cmd_list(args):
    models = list_models()
    save_models(models)
    if not models:
        print(bright('未检测到 ollama 模型 (请先 ollama pull 下载).', 'yellow'))
        return 0
    print(bright('已下载的 ollama 模型:', 'cyan'))
    print('  %-28s %-16s %-10s %s' % ('NAME', 'ID', 'SIZE', 'MODIFIED'))
    for m in models:
        print('  %-28s %-16s %-10s %s' % (m['name'], m['id'], m['size'], m['modified']))
    print(bright('共 %d 个模型 (已缓存到数据目录).' % len(models), 'green'))
    return 0


def cmd_tools(args):
    tools = build_tools()
    print(bright('Benchmark 后端:', 'cyan'))
    for t in tools:
        ok = t.available()
        status = bright('可用', 'green') if ok else bright('未安装', 'yellow')
        print('  %-14s %s  %s' % (t.name, status, t.desc))
        if not ok and t.install_hint:
            print(bright('     安装: ' + t.install_hint, 'yellow'))
    return 0


def _cell(text, limit=90):
    """把任意结果文本压成单行、可安全放进 Markdown 表格单元格的短标签。"""
    text = ' '.join(str(text or '').split()).replace('|', '/')
    if len(text) > limit:
        text = text[:limit - 1] + '…'
    return text or 'N/A'


# 子进程可能吐出整段异常栈; 表格里只保留可辨识的异常类型, 完整信息留在 report.json
_EXCEPTION_KEYS = ('ProxyError', 'MaxRetryError', 'ConnectionError', 'TimeoutError',
                   'TimeoutExpired', 'FileNotFoundError', 'ModuleNotFoundError',
                   'JSONDecodeError', 'HTTPError', 'SSLError', 'OSError')


def _fail_cell(err):
    text = ' '.join(str(err or 'fail').split())
    if not text:
        return 'fail'
    kind = next((k for k in _EXCEPTION_KEYS if k in text), None)
    if kind:
        return '执行失败: %s (详见 report.json)' % kind
    return _cell(text)


def print_summary_table(models, tools, results):
    by_model = {m: {} for m in models}
    for r in results:
        by_model.setdefault(r.model, {})[r.tool] = r
    print(bright('汇总:', 'cyan'))
    header = ['模型'] + [t.name for t in tools]
    print('  '.join(header))
    for m in models:
        row = [m]
        for t in tools:
            r = by_model.get(m, {}).get(t.name)
            if r is None:
                row.append(bright('N/A', 'yellow'))
            elif r.ok:
                row.append(bright(_cell(r.summary or 'ok'), 'green'))
            else:
                row.append(bright(_fail_cell(r.error), 'red'))
        print('  '.join(str(x) for x in row))


def _hardware_module():
    """按文件路径加载共享硬件模块, 绕开 site-packages 里可能存在的旧 duck_utils。"""
    import importlib.util
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(repo, 'duck_utils', 'llm_chatbench', 'hardware.py')
    spec = importlib.util.spec_from_file_location('_duck_llm_hardware', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load hardware module: ' + path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hardware_section():
    """返回 (硬件 dict, Markdown 段落); 采集失败时返回空值, 不阻断报告生成。"""
    try:
        mod = _hardware_module()
        hw = mod.collect_hardware(get_data_dir())
        return hw, mod.hardware_markdown(hw=hw)
    except Exception:
        return {}, ''


def write_report(models, tools, results, fmt, system_metrics=None):
    by_model = {m: {} for m in models}
    for r in results:
        by_model.setdefault(r.model, {})[r.tool] = r
    data_dir = get_data_dir()
    hw, hw_md = hardware_section()
    if fmt == 'json':
        out = {'models': models, 'tools': [t.name for t in tools],
               'results': [r.to_dict() for r in results],
               'system_metrics': system_metrics or {}}
        if hw:
            out['hardware'] = hw
        path = os.path.join(data_dir, 'report.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(bright('报告已写: ' + path, 'cyan'))
        return
    lines = ['# duck-llm-benchmark 汇总报告', '']
    lines.append('> 数据源: `%s`, 由 `duck-llm-benchmark report` 从各模型目录的落盘结果汇总; '
                 '模型 %d 个 / 后端 %d 个, 生成时间 %s。'
                 % (data_dir, len(models), len(tools),
                    time.strftime('%Y-%m-%d %H:%M:%S')))
    lines.append('> 「未安装」表示该后端当时不可用, 不是 0 分; lm-eval 为 gsm8k 20 题小样本, '
                 '推理型模型得 0.000 多因答案格式不匹配。')
    lines.append('> 补跑的 thinking 模型使用 `--think-off` / `reasoning_effort=none` '
                 '保证正文可用, 与历史批次口径略有差异。')
    lines.append('> 归档副本: `docs/llm-benchmark-single-turn.md` / `.json`'
                 '（项目仓库, 由补跑流水线自动同步）。')
    lines.append('')
    head = '| 模型 | ' + ' | '.join(t.name for t in tools) + ' |'
    sep = '| --- | ' + ' | '.join('---' for _ in tools) + ' |'
    lines.append(head)
    lines.append(sep)
    for m in models:
        cells = [m]
        for t in tools:
            r = by_model.get(m, {}).get(t.name)
            if r is None:
                cells.append('N/A')
            elif r.ok:
                cells.append(_cell(r.summary or 'ok'))
            else:
                cells.append(_fail_cell(r.error))
        lines.append('| ' + ' | '.join(cells) + ' |')
    # 资源监控表 (运行期间均值/峰值)
    lines.append('')
    lines.append('## 资源监控 (运行期间 均值/峰值)')
    lines.append('')
    lines.append('| 模型 | CPU% | 内存% | GPU% | 显存峰值(MB) |')
    lines.append('| --- | --- | --- | --- | --- |')
    for m in models:
        sm = (system_metrics or {}).get(m)
        if not sm:
            lines.append('| %s | N/A | N/A | N/A | N/A |' % m)
            continue
        cpu = '%s/%s' % (sm.get('cpu_avg'), sm.get('cpu_max')) if 'cpu_avg' in sm else 'N/A'
        mem = '%s/%s' % (sm.get('mem_avg_percent'), sm.get('mem_max_percent')) if 'mem_avg_percent' in sm else 'N/A'
        gpu = '%s/%s' % (sm.get('gpu_util_avg'), sm.get('gpu_util_max')) if 'gpu_util_avg' in sm else 'N/A'
        vram = sm.get('gpu_mem_peak_mb', 'N/A')
        lines.append('| %s | %s | %s | %s | %s |' % (m, cpu, mem, gpu, vram))
    lines.append('')
    if hw_md:
        lines.append(hw_md.rstrip('\n'))
        lines.append('')
    path = os.path.join(data_dir, 'report.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(bright('报告已写: ' + path, 'cyan'))


def cmd_run(args):
    opts = RunOpts(limit=args.limit, tasks=args.tasks,
                   keepalive=args.keepalive, timeout=args.timeout,
                   think_off=args.think_off)
    tools = build_tools()
    if args.tool:
        want = set(t.strip() for t in args.tool.split(',') if t.strip())
        tools = [t for t in tools if t.name in want]
        if not tools:
            print(bright('未知后端, 可用: ' + ', '.join(t.name for t in build_tools()), 'red'))
            return 1
    models = list(args.models)
    if not models:
        if args.all:
            cached = load_models() or list_models()
            models = [m['name'] for m in cached]
        else:
            print(bright('请指定模型名, 或加 --all 跑全部模型.', 'yellow'))
            return 1
    if not models:
        print(bright('没有可用模型, 请先 duck-llm-benchmark list 确认.', 'yellow'))
        return 1
    all_results = []
    system_metrics: Dict[str, Any] = {}
    for model in models:
        print(bright('=== 模型: ' + model + ' ===', 'cyan'))
        # 先关闭其它已加载的模型实例, 避免同时驻留多个模型占用资源
        stop_other_models(model)
        monitor = SystemMonitor(interval=1.0)
        monitor.start()
        for tool in tools:
            if tool.available():
                print('  运行 %s ...' % tool.name)
                res = tool.run(model, opts)
            else:
                res = BenchResult(tool.name, model, False,
                                 error='未安装', summary=tool.install_hint or 'N/A')
            save_result(model, tool.name, res)
            all_results.append(res)
            if res.ok:
                print('    %s: %s' % (tool.name, bright(res.summary or 'ok', 'green')))
            else:
                print('    %s: %s' % (tool.name, bright(res.error or 'fail', 'red')))
        monitor.stop()
        summary = monitor.summary()
        system_metrics[model] = summary
        if summary:
            save_system_metrics(model, summary)
            print('    ' + bright('资源监控: ', 'cyan') + format_resource(summary))
    print('')
    print_summary_table(models, tools, all_results)
    if args.report != 'none':
        write_report(models, tools, all_results, args.report, system_metrics)
    # 收尾: 停止所有已加载模型, 释放资源
    stop_other_models()
    return 0


def cmd_report(args):
    tools = build_tools()
    models = list(args.models)
    if not models:
        cached = load_models()
        models = [m['name'] for m in cached] if cached else []
    if not models:
        print(bright('没有已保存的结果, 请先运行 run.', 'yellow'))
        return 0
    results = []
    for m in models:
        for t in tools:
            r = load_result(m, t.name)
            if r is not None:
                results.append(r)
    if not results:
        print(bright('没有已保存的结果, 请先运行 run.', 'yellow'))
        return 0
    print_summary_table(models, tools, results)
    # 资源监控表
    system_metrics = {m: load_system_metrics(m) for m in models}
    if any(system_metrics.values()):
        print('')
        print(bright('资源监控 (运行期间 均值/峰值):', 'cyan'))
        print('  %-22s %-22s %-22s %-16s' % ('模型', 'CPU', '内存', 'GPU'))
        for m in models:
            sm = system_metrics.get(m)
            if not sm:
                print('  %-22s %s' % (m, 'N/A'))
                continue
            cpu = '%s/%s' % (sm.get('cpu_avg'), sm.get('cpu_max')) if 'cpu_avg' in sm else 'N/A'
            mem = '%s/%s' % (sm.get('mem_avg_percent'), sm.get('mem_max_percent')) if 'mem_avg_percent' in sm else 'N/A'
            gpu = '%s/%s' % (sm.get('gpu_util_avg'), sm.get('gpu_util_max')) if 'gpu_util_avg' in sm else 'N/A'
            print('  %-22s %-22s %-22s %-16s' % (m, cpu, mem, gpu))
    write_report(models, tools, results, args.format, system_metrics)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog='duck-llm-benchmark',
                               description='本地 ollama 小模型 benchmark 工具')
    sub = p.add_subparsers(dest='cmd')
    sub.add_parser('list', help='列出已下载的 ollama 模型')
    sub.add_parser('tools', help='列出各 benchmark 后端及可用性')
    pr = sub.add_parser('run', help='对模型跑 benchmark')
    pr.add_argument('models', nargs='*', help='模型名(可多个); 省略需加 --all')
    pr.add_argument('--all', action='store_true', help='跑 ollama list 的全部模型')
    pr.add_argument('--tool', help='只跑指定后端, 逗号分隔, 如 ollama-speed,qa-basic')
    pr.add_argument('--tasks', default='gsm8k',
                    help='透传给 lm-eval 的任务(默认 gsm8k; 仅支持生成类任务, '
                         'loglikelihood 类如 hellaswag 需模型返回 token logprobs, '
                         'ollama 的 OpenAI 接口不支持)')
    pr.add_argument('--limit', type=int, default=None, help='内置评测题量上限(快速试跑)')
    pr.add_argument('--keepalive', default='5m', help='ollama 模型保活时长')
    pr.add_argument('--timeout', type=int, default=600, help='单后端超时(秒)')
    pr.add_argument('--report', default='md', choices=['md', 'json', 'none'],
                    help='运行后生成汇总报告')
    pr.add_argument('--think-off', action='store_true',
                    help='给 ollama run 传 --think=false, 关闭 thinking 模型的思考输出')
    pp = sub.add_parser('report', help='汇总已保存的结果')
    pp.add_argument('models', nargs='*', help='模型名; 省略则全部')
    pp.add_argument('--format', default='md', choices=['md', 'json'], help='报告格式')
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == 'list':
        return cmd_list(args)
    if args.cmd == 'tools':
        return cmd_tools(args)
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
