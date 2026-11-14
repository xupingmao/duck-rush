# -*- coding: utf-8 -*-
"""评测环境硬件基线采集。

只用标准库 + 系统自带命令 (powershell / nvidia-smi / ollama), 任何一项失败
都降级为 N/A, 绝不阻断报告生成。供单轮与多轮 benchmark 报告共用, 使报告
在换机器重算时能自动带上当时的真实硬件信息。
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_NA = 'N/A'


def _wmi_gpu() -> str:
    """取显卡型号, 供没有 nvidia-smi 的机器 (AMD/Intel 核显) 兜底。

    Win32_VideoController 的 AdapterRAM 只报 32 位以内的值, 对 4GB 以上
    显存/共享内存会严重低估, 故这里只取型号, 不声称容量。
    """
    script = ("Get-CimInstance Win32_VideoController | "
              "ForEach-Object { Write-Output ('GPUNAME=' + $_.Name) }")
    raw = _run(['powershell', '-NoProfile', '-NonInteractive',
                '-Command', script], 30)
    names = [ln.partition('=')[2].strip() for ln in raw.splitlines()
             if ln.upper().startswith('GPUNAME=')]
    # 过滤虚拟显示器/基础渲染设备, 优先真实 GPU 厂商
    junk = ('basic render', 'virtual', 'remote', 'parsec', 'idd', 'mirror')
    names = [n for n in names if n and not any(j in n.lower() for j in junk)]
    vendors = ('radeon', 'geforce', 'nvidia', 'intel', 'arc', 'iris', 'uhd')
    real = [n for n in names if any(v in n.lower() for v in vendors)]
    if real:
        return real[0]
    return names[0] if names else ''


def _run(cmd: List[str], timeout: int = 20) -> str:
    """执行只读系统命令, 超时/缺失/解码异常一律返回空串。"""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, encoding='utf-8', errors='replace')
        return (proc.stdout or '').strip()
    except Exception:
        return ''


def _windows_info() -> Dict[str, str]:
    """用 PowerShell 一次取回 CPU / 核数 / 物理内存 / 机型。"""
    script = (
        "$c = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "$s = Get-CimInstance Win32_ComputerSystem; "
        "$o = Get-CimInstance Win32_OperatingSystem; "
        # 只取纯 ASCII 的 Version, 避免中文 Caption 经 PowerShell 管道出现编码乱码
        "Write-Output ('OSVER=' + $o.Version); "
        "Write-Output ('CPU=' + $c.Name); "
        "Write-Output ('CORES=' + $c.NumberOfCores); "
        "Write-Output ('LOGICAL=' + $c.NumberOfLogicalProcessors); "
        "Write-Output ('MEMBYTES=' + $s.TotalPhysicalMemory); "
        "Write-Output ('BOARD=' + $s.Manufacturer + ' / ' + $s.Model)"
    )
    raw = _run(['powershell', '-NoProfile', '-NonInteractive',
                '-Command', script], 30)
    out: Dict[str, str] = {}
    for line in raw.splitlines():
        if '=' not in line:
            continue
        key, _, val = line.partition('=')
        out[key.strip().upper()] = val.strip()
    return out


def _linux_info() -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        with open('/proc/cpuinfo', encoding='utf-8') as f:
            for line in f:
                if line.lower().startswith('model name'):
                    out['CPU'] = line.partition(':')[2].strip()
                    break
        with open('/proc/meminfo', encoding='utf-8') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    out['MEMBYTES'] = str(int(line.split()[1]) * 1024)
                    break
    except Exception:
        pass
    return out


def collect_hardware(path: Optional[str] = None) -> Dict[str, Any]:
    """采集当前机器硬件/软件环境, 返回可直接写入 JSON 的字典。"""
    info = (_windows_info() if platform.system() == 'Windows'
            else _linux_info())

    cpu = info.get('CPU') or platform.processor() or _NA
    cores = info.get('CORES')
    logical = info.get('LOGICAL') or str(os.cpu_count() or '?')
    if cores:
        cpu = '%s (%s 核 / %s 线程)' % (cpu, cores, logical)
    elif logical:
        cpu = '%s (%s 逻辑线程)' % (cpu, logical)

    memory = _NA
    try:
        memory = '%.1f GB' % (int(info['MEMBYTES']) / (1024 ** 3))
    except Exception:
        pass

    gpu = _NA
    q = _run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
              '--format=csv,noheader'])
    if q:
        parts = [p.strip() for p in q.splitlines()[0].split(',')]
        if len(parts) >= 3:
            gpu = '%s ｜ 显存 %s ｜ 驱动 %s' % (parts[0], parts[1], parts[2])
            match = re.search(r'CUDA(?: UMD)? Version:\s*([\d.]+)',
                              _run(['nvidia-smi']))
            if match:
                gpu += ' ｜ CUDA %s' % match.group(1)
    if gpu == _NA and platform.system() == 'Windows':
        name = _wmi_gpu()
        if name:
            gpu = '%s（核显/共享内存，无 nvidia-smi，显存与内存共享）' % name

    ollama_version = _NA
    match = re.search(r'(\d+\.\d+\.\d+)', _run(['ollama', '--version']))
    if match:
        ollama_version = match.group(1)

    disk = _NA
    try:
        target = path or os.getcwd()
        drive = os.path.splitdrive(os.path.abspath(target))[0]
        usage = shutil.disk_usage(target)
        disk = '%s总 %.0f GB / 可用 %.0f GB' % (
            (drive + ' ') if drive else '',
            usage.total / (1024 ** 3), usage.free / (1024 ** 3))
    except Exception:
        pass

    return {
        'captured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        # Windows 上 Python 3.10/3.13 的 platform.platform() 会报不同的 build 号
        # (manifest 差异), 统一用 WMI 的真实 Version 更准确且无编码问题。
        'os': ('Windows %s' % info['OSVER']) if info.get('OSVER')
              else platform.platform(),
        'cpu': cpu,
        'memory': memory,
        'gpu': gpu,
        'disk': disk,
        'board': info.get('BOARD') or _NA,
        'ollama': ollama_version,
        'python': '%s (%s)' % (platform.python_version(),
                               platform.python_implementation()),
        'python_exe': sys.executable,
    }


_ROWS = [
    ('操作系统', 'os'),
    ('CPU', 'cpu'),
    ('内存', 'memory'),
    ('GPU', 'gpu'),
    ('主板 / 机型', 'board'),
    ('数据盘', 'disk'),
    ('ollama', 'ollama'),
    ('Python', 'python'),
]


def hardware_markdown(path: Optional[str] = None,
                      hw: Optional[Dict[str, Any]] = None) -> str:
    """把硬件基线渲染为可直接追加到报告末尾的 Markdown 段落。

    传入 hw 可复用同一次采集结果, 保证 JSON 与 Markdown 的采集时间一致。
    """
    hw = hw if hw is not None else collect_hardware(path)
    lines = ['## 评测环境（硬件基线）', '']
    lines.append('> 采集时间 %s；由报告生成程序自动读取本机信息，'
                 '换机器重算时会自动更新。' % hw['captured_at'])
    lines.append('')
    lines.append('| 项目 | 值 |')
    lines.append('| --- | --- |')
    for label, key in _ROWS:
        value = str(hw.get(key) or _NA).replace('|', '/')
        lines.append('| %s | %s |' % (label, value))
    lines.append('')
    lines.append('> 注意：显存小于模型体积时会触发 CPU offload，吞吐与时延不可与'
                 '全 GPU 载入的模型直接对比；单轮「资源监控」与多轮「效率与'
                 '上下文开销」需结合本节显存容量一起解读。')
    return '\n'.join(lines) + '\n'
