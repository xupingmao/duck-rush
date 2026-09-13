# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2026-09-12
@LastEditors  : xupingmao
@LastEditTime : 2026-09-12
@FilePath     : duck_rush/os/duck-disk-health.py
@Description  : 跨平台磁盘健康检查: 分区空间占用(纯标准库) + 可选的 S.M.A.R.T 真实健康(尽力而为)。
"""

import os
import sys
import re
import json
import shutil
import subprocess
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from duck_utils.os_util import is_windows, is_linux, is_mac


# ---------------------------------------------------------------------------
# 颜色(明亮 ANSI, 符合"浅色明亮"规范, 不依赖第三方库)
# ---------------------------------------------------------------------------
COLOR_RESET = "\033[0m"
COLOR_HEALTHY = "\033[92m"    # bright green
COLOR_WARNING = "\033[93m"    # bright yellow
COLOR_CRITICAL = "\033[91m"   # bright red
COLOR_UNKNOWN = "\033[96m"    # bright cyan


def colorize(text: str, color: str) -> str:
    return "%s%s%s" % (color, text, COLOR_RESET)


# ---------------------------------------------------------------------------
# 健康状态枚举
# ---------------------------------------------------------------------------
STATUS_HEALTHY = "healthy"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"
STATUS_UNKNOWN = "unknown"

STATUS_LABEL = {
    STATUS_HEALTHY: "正常",
    STATUS_WARNING: "警告",
    STATUS_CRITICAL: "危险",
    STATUS_UNKNOWN: "未知",
}

STATUS_COLOR = {
    STATUS_HEALTHY: COLOR_HEALTHY,
    STATUS_WARNING: COLOR_WARNING,
    STATUS_CRITICAL: COLOR_CRITICAL,
    STATUS_UNKNOWN: COLOR_UNKNOWN,
}

# 取最差状态用于总体小结
_STATUS_RANK = {
    STATUS_HEALTHY: 0,
    STATUS_UNKNOWN: 1,
    STATUS_WARNING: 2,
    STATUS_CRITICAL: 3,
}


def worst_status(a: str, b: str) -> str:
    return a if _STATUS_RANK.get(a, 0) >= _STATUS_RANK.get(b, 0) else b


def classify_usage(percent: float, warn: int, crit: int) -> str:
    """根据使用率(0-100)与阈值返回健康状态英文键。

    percent < warn -> healthy; percent < crit -> warning; 否则 critical。
    """
    if percent < warn:
        return STATUS_HEALTHY
    if percent < crit:
        return STATUS_WARNING
    return STATUS_CRITICAL


def format_bytes(num: int) -> str:
    """把字节数格式化为人类可读字符串(二进制单位)。"""
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024.0 or unit == "PiB":
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.2f %s" % (value, unit)
        value /= 1024.0
    return "%.2f PiB" % value


# ---------------------------------------------------------------------------
# 分区数据结构
# ---------------------------------------------------------------------------
@dataclass
class Partition:
    device: str
    mountpoint: str
    fstype: Optional[str]
    total: int
    used: int
    free: int
    percent: float

    @property
    def status(self) -> str:
        # 占位: 真正分级在收集后统一计算(需要 warn/crit), 这里提供默认
        return STATUS_UNKNOWN


def _run(cmd: List[str], timeout: int = 8) -> Optional[str]:
    """运行命令返回 stdout 文本; 失败/超时返回 None。"""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 分区枚举
# ---------------------------------------------------------------------------
_PSEUDO_FSTYPES = set([
    "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup", "cgroup2", "debugfs",
    "tracefs", "mqueue", "hugetlbfs", "securityfs", "pstore", "bpf",
    "configfs", "fusectl", "binfmt_misc", "autofs", "ramfs", "rpc_pipefs",
    "overlay", "squashfs", "devpts", "nsfs", "efivarfs",
])

_PSEUDO_MOUNTPOINT_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/snap")


def _load_proc_mounts_fstype() -> Dict[str, str]:
    """Linux: 从 /proc/mounts 建立 device -> fstype 映射。"""
    result: Dict[str, str] = {}
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fp:
            for line in fp:
                parts = line.split()
                if len(parts) >= 3:
                    result[parts[0]] = parts[2]
    except Exception:
        pass
    return result


def list_partitions_windows() -> List[Partition]:
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32")
    buf = ctypes.create_unicode_buffer(256)
    n = kernel32.GetLogicalDriveStringsW(256, buf)
    if n <= 0:
        return []
    raw = ctypes.string_at(ctypes.addressof(buf), n * 2)
    drives = [p for p in raw.decode("utf-16-le").split("\x00") if p]
    partitions: List[Partition] = []
    for drive in drives:
        drive_type = kernel32.GetDriveTypeW(drive)
        # DRIVE_FIXED = 3; 也包含可移动磁盘(2)? 仅固定磁盘更贴近"磁盘健康"
        if drive_type != 3:
            continue
        try:
            usage = shutil.disk_usage(drive)
        except Exception:
            continue
        percent = usage.total and (usage.used / usage.total * 100) or 0.0
        partitions.append(Partition(
            device=drive,
            mountpoint=drive,
            fstype=None,
            total=usage.total,
            used=usage.used,
            free=usage.free,
            percent=round(percent, 1),
        ))
    return partitions


def list_partitions_posix() -> List[Partition]:
    fstype_map = _load_proc_mounts_fstype() if is_linux() else {}
    out = _run(["df", "-P", "-k"])
    if out is None:
        return []
    partitions: List[Partition] = []
    lines = out.splitlines()
    # 跳过表头
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        mountpoint = parts[-1]
        capacity = parts[-2]
        used_k = parts[-4]
        avail_k = parts[-3]
        blocks_k = parts[-5]
        device = " ".join(parts[:-5])
        fstype = fstype_map.get(device)
        # 过滤伪文件系统与特殊挂载点
        if fstype in _PSEUDO_FSTYPES:
            continue
        if mountpoint.startswith(_PSEUDO_MOUNTPOINT_PREFIXES):
            continue
        try:
            total = int(blocks_k) * 1024
            used = int(used_k) * 1024
            free = int(avail_k) * 1024
            percent = float(capacity.rstrip("%")) if capacity.endswith("%") else (
                (used / total * 100) if total else 0.0)
        except ValueError:
            continue
        partitions.append(Partition(
            device=device,
            mountpoint=mountpoint,
            fstype=fstype,
            total=total,
            used=used,
            free=free,
            percent=round(percent, 1),
        ))
    return partitions


def list_partitions() -> List[Partition]:
    if is_windows():
        return list_partitions_windows()
    return list_partitions_posix()


# ---------------------------------------------------------------------------
# S.M.A.R.T (best-effort)
# ---------------------------------------------------------------------------
@dataclass
class SmartInfo:
    device: str
    model: Optional[str] = None
    status: str = STATUS_UNKNOWN          # healthy/warning/critical/unknown(PASSED->healthy, FAILED->critical)
    temperature: Optional[int] = None      # 摄氏度
    power_on_hours: Optional[int] = None
    reallocated_sectors: Optional[int] = None
    pending_sectors: Optional[int] = None
    uncorrectable_sectors: Optional[int] = None
    total_lbas_written: Optional[int] = None   # 累计写入扇区/数据单元数(SATA:241 / NVMe:Data Units)
    total_lbas_read: Optional[int] = None      # 累计读取扇区/数据单元数(SATA:242 / NVMe:Data Units)
    total_bytes_written: Optional[int] = None  # 累计写入字节数(已按接口换算)
    total_bytes_read: Optional[int] = None     # 累计读取字节数(已按接口换算)
    percentage_used: Optional[int] = None      # NVMe 寿命已用百分比(Percentage Used)
    wear_leveling_count: Optional[int] = None   # 磨损均衡计数/寿命(173/177, SATA)
    reason: Optional[str] = None           # 采集失败原因


# smartctl -A 属性名 -> 字段 (SATA/SAS 通用属性 ID)
_ATTR_ID_MAP = {
    "5": "reallocated_sectors",
    "9": "power_on_hours",
    "173": "wear_leveling_count",
    "177": "wear_leveling_count",
    "190": "temperature",
    "194": "temperature",
    "197": "pending_sectors",
    "198": "uncorrectable_sectors",
    "241": "total_lbas_written",
    "242": "total_lbas_read",
}

# SATA/SAS: LBA 计数按 512 字节扇区换算; NVMe: 1 数据单元 = 1000 * 512 字节
_LBA_SECTOR_BYTES = 512
_NVME_DATA_UNIT_BYTES = 512 * 1000


def _first_int(text: str) -> Optional[int]:
    """从字符串中提取第一个整数(忽略千位逗号), 失败返回 None。"""
    m = re.search(r"-?[\d,]+", text)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_ata_output(text: str) -> Tuple[str, Dict[str, int]]:
    """解析 SATA/SAS 的 smartctl -H -A 属性表, 返回 (health_key, 指标dict)。"""
    health = STATUS_UNKNOWN
    metrics: Dict[str, int] = {}
    for line in text.splitlines():
        if "overall-health self-assessment" in line or "SMART Health Status" in line:
            if "PASS" in line or "OK" in line:
                health = STATUS_HEALTHY
            elif "FAIL" in line:
                health = STATUS_CRITICAL
            continue
        # 属性表: 以数字 ID 开头
        if line.strip() and line.strip()[0].isdigit():
            cells = line.split()
            if len(cells) < 10:
                continue
            field_name = _ATTR_ID_MAP.get(cells[0])
            if field_name is None:
                continue
            try:
                metrics[field_name] = int(cells[-1])
            except ValueError:
                pass
    # 由 LBA 计数换算字节数(统一渲染口径)
    if "total_lbas_written" in metrics:
        metrics["total_bytes_written"] = metrics["total_lbas_written"] * _LBA_SECTOR_BYTES
    if "total_lbas_read" in metrics:
        metrics["total_bytes_read"] = metrics["total_lbas_read"] * _LBA_SECTOR_BYTES
    return health, metrics


def parse_nvme_output(text: str) -> Tuple[str, Dict[str, int]]:
    """解析 NVMe 的 smartctl -A 输出(SMART/Health Information Log 0x02)。

    关键字段: Data Units Written/Read(1 单元=1000*512 字节)、
    Percentage Used(寿命已用%)、Temperature、Power On Hours、Critical Warning。
    """
    health = STATUS_HEALTHY
    metrics: Dict[str, int] = {}
    for line in text.splitlines():
        low = line.lower()
        if "critical warning" in low:
            # Critical Warning: 0x00 表示无告警, 非 0 视为异常
            val = line.split(":", 1)[1].strip() if ":" in line else ""
            if val not in ("0x00", "0", ""):
                health = STATUS_CRITICAL
        elif "temperature:" in low:
            m = re.search(r"(-?\d+)\s*Celsius", line)
            if m:
                metrics["temperature"] = int(m.group(1))
        elif "power on hours" in low:
            hours = _first_int(line.split(":", 1)[1]) if ":" in line else None
            if hours is not None:
                metrics["power_on_hours"] = hours
        elif "data units written" in low:
            units = _first_int(line.split(":", 1)[1]) if ":" in line else None
            if units is not None:
                metrics["total_lbas_written"] = units
                metrics["total_bytes_written"] = units * _NVME_DATA_UNIT_BYTES
        elif "data units read" in low:
            units = _first_int(line.split(":", 1)[1]) if ":" in line else None
            if units is not None:
                metrics["total_lbas_read"] = units
                metrics["total_bytes_read"] = units * _NVME_DATA_UNIT_BYTES
        elif "percentage used" in low:
            m = re.search(r"(\d+)\s*%", line)
            if m:
                metrics["percentage_used"] = int(m.group(1))
    return health, metrics


def parse_smart_output(text: str) -> Tuple[str, Dict[str, int]]:
    """解析 smartctl -H -A 输出, 自动区分 NVMe 与 SATA/SAS 格式。

    返回 (health_key, 指标dict)。health_key:
    STATUS_HEALTHY / STATUS_CRITICAL / STATUS_UNKNOWN。
    """
    if "NVMe" in text or "Data Units Written" in text:
        return parse_nvme_output(text)
    return parse_ata_output(text)


def list_physical_disks() -> List[Tuple[str, Optional[str]]]:
    """按平台列出物理磁盘 (device, model)。"""
    if is_windows():
        out = _run(["wmic", "diskdrive", "get", "DeviceID,Model", "/value"])
        disks: List[Tuple[str, Optional[str]]] = []
        if out:
            dev = model = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("DeviceID="):
                    dev = line[len("DeviceID="):].strip()
                elif line.startswith("Model="):
                    model = line[len("Model="):].strip()
                if dev and model is not None:
                    disks.append((dev, model or None))
                    dev = model = None
        return disks
    if is_mac():
        out = _run(["diskutil", "list", "physical"])
        disks = []
        if out:
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("/dev/disk"):
                    # 形如: "/dev/disk0 (internal, physical):"
                    dev = line.split()[0]
                    disks.append((dev, None))
        return disks
    # Linux: lsblk 优先
    out = _run(["lsblk", "-d", "-n", "-o", "NAME,MODEL,TYPE"])
    disks = []
    if out:
        for line in out.splitlines():
            cells = line.split()
            if len(cells) >= 1 and (len(cells) < 3 or cells[-1] == "disk"):
                name = cells[0]
                model = cells[1] if len(cells) >= 2 and cells[1] != "disk" else None
                disks.append(("/dev/%s" % name, model))
    if disks:
        return disks
    # 兜底: 扫描 /sys/block
    try:
        for name in os.listdir("/sys/block"):
            if name.startswith(("loop", "ram", "dm-", "sr", "fd")):
                continue
            disks.append(("/dev/%s" % name, None))
    except Exception:
        pass
    return disks


def _smartctl_available() -> bool:
    return _run(["smartctl", "--version"]) is not None


def collect_smart() -> List[SmartInfo]:
    """尽力采集各物理磁盘 SMART 信息; 不可用时给出 N/A 原因。"""
    disks = list_physical_disks()
    result: List[SmartInfo] = []
    have_smartctl = _smartctl_available()
    for dev, model in disks:
        info = SmartInfo(device=dev, model=model)
        if have_smartctl:
            out = _run(["smartctl", "-H", "-A", "-i", dev])
            if out is None:
                info.reason = "smartctl 执行失败或需要权限(建议管理员/root)"
            else:
                health, metrics = parse_smart_output(out)
                info.status = health
                info.temperature = metrics.get("temperature")
                info.power_on_hours = metrics.get("power_on_hours")
                info.reallocated_sectors = metrics.get("reallocated_sectors")
                info.pending_sectors = metrics.get("pending_sectors")
                info.uncorrectable_sectors = metrics.get("uncorrectable_sectors")
                info.total_lbas_written = metrics.get("total_lbas_written")
                info.total_lbas_read = metrics.get("total_lbas_read")
                info.total_bytes_written = metrics.get("total_bytes_written")
                info.total_bytes_read = metrics.get("total_bytes_read")
                info.percentage_used = metrics.get("percentage_used")
                info.wear_leveling_count = metrics.get("wear_leveling_count")
                if health == STATUS_UNKNOWN:
                    info.reason = "未解析到健康状态(smartctl 无输出?)"
                continue
        else:
            # 降级: Windows 用 wmic 取整体状态
            if is_windows():
                out = _run(["wmic", "diskdrive", "where",
                            "DeviceID='%s'" % dev, "get", "Status", "/value"])
                if out and "Status=" in out:
                    status = out.split("Status=")[-1].strip()
                    if status.upper().startswith("OK"):
                        info.status = STATUS_HEALTHY
                    else:
                        info.status = STATUS_CRITICAL
                    info.reason = "仅 wmic 整体状态(smartctl 不可用, 无温度/扇区详情)"
                else:
                    info.reason = "smartctl 与 wmic 均不可用"
            else:
                info.reason = "smartctl 不可用(安装 smartmontools 后可用 --smart 获取详情)"
        result.append(info)
    return result


# ---------------------------------------------------------------------------
# 渲染(表格)
# ---------------------------------------------------------------------------
def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        width += 2 if ord(ch) > 0x2E80 else 1
    return width


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _render_table(title: str, headers: List[str], rows: List[List[str]]) -> None:
    if title:
        print(title)
    cols = len(headers)
    widths = [_display_width(h) for h in headers]
    for row in rows:
        for i in range(cols):
            widths[i] = max(widths[i], _display_width(row[i]))
    sep = "+" + "+".join("-" * (widths[i] + 2) for i in range(cols)) + "+"
    print(sep)
    print("| " + " | ".join(_pad(headers[i], widths[i]) for i in range(cols)) + " |")
    print(sep)
    for row in rows:
        print("| " + " | ".join(_pad(row[i], widths[i]) for i in range(cols)) + " |")
    print(sep)


def render_usage_table(partitions: List[Partition], warn: int, crit: int) -> None:
    headers = ["设备", "挂载点", "文件系统", "总量", "已用", "可用", "使用率", "状态"]
    rows: List[List[str]] = []
    for p in partitions:
        status = classify_usage(p.percent, warn, crit)
        color = STATUS_COLOR[status]
        status_cell = colorize(STATUS_LABEL[status], color)
        rows.append([
            p.device,
            p.mountpoint,
            p.fstype or "-",
            format_bytes(p.total),
            format_bytes(p.used),
            format_bytes(p.free),
            "%.1f%%" % p.percent,
            status_cell,
        ])
    _render_table("磁盘分区空间占用", headers, rows)


def render_smart_table(smart_list: List[SmartInfo]) -> None:
    headers = ["设备", "型号", "健康", "温度", "通电(时)", "写入量", "读取量",
               "寿命已用", "重分配扇区", "待映射扇区", "不可纠正", "磨损计数", "说明"]
    rows: List[List[str]] = []
    for s in smart_list:
        color = STATUS_COLOR[s.status]
        health_cell = colorize(STATUS_LABEL.get(s.status, s.status), color)
        written = format_bytes(s.total_bytes_written) if s.total_bytes_written is not None else "-"
        read = format_bytes(s.total_bytes_read) if s.total_bytes_read is not None else "-"
        if s.percentage_used is not None:
            wear = "%d%%" % s.percentage_used
        elif s.wear_leveling_count is not None:
            wear = str(s.wear_leveling_count)
        else:
            wear = "-"
        rows.append([
            s.device,
            s.model or "-",
            health_cell,
            "%d℃" % s.temperature if s.temperature is not None else "-",
            str(s.power_on_hours) if s.power_on_hours is not None else "-",
            written,
            read,
            wear,
            str(s.reallocated_sectors) if s.reallocated_sectors is not None else "-",
            str(s.pending_sectors) if s.pending_sectors is not None else "-",
            str(s.uncorrectable_sectors) if s.uncorrectable_sectors is not None else "-",
            str(s.wear_leveling_count) if (s.wear_leveling_count is not None
                                          and s.percentage_used is None) else "-",
            s.reason or "-",
        ])
    _render_table("物理磁盘 S.M.A.R.T (--smart)", headers, rows)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
def build_json(partitions: List[Partition], smart_list: Optional[List[SmartInfo]],
               warn: int, crit: int) -> dict:
    part_objs = []
    overall = STATUS_HEALTHY
    for p in partitions:
        st = classify_usage(p.percent, warn, crit)
        overall = worst_status(overall, st)
        part_objs.append({
            "device": p.device,
            "mountpoint": p.mountpoint,
            "fstype": p.fstype,
            "total": p.total,
            "used": p.used,
            "free": p.free,
            "percent": p.percent,
            "status": st,
        })
    result: dict = {
        "partitions": part_objs,
        "summary": {
            "status": overall,
            "partition_count": len(part_objs),
        },
    }
    if smart_list is not None:
        smart_objs = []
        smart_overall = STATUS_HEALTHY
        for s in smart_list:
            smart_overall = worst_status(smart_overall, s.status)
            smart_objs.append({
                "device": s.device,
                "model": s.model,
                "status": s.status,
                "temperature": s.temperature,
                "power_on_hours": s.power_on_hours,
                "total_lbas_written": s.total_lbas_written,
                "total_lbas_read": s.total_lbas_read,
                "total_bytes_written": s.total_bytes_written,
                "total_bytes_read": s.total_bytes_read,
                "percentage_used": s.percentage_used,
                "reallocated_sectors": s.reallocated_sectors,
                "pending_sectors": s.pending_sectors,
                "uncorrectable_sectors": s.uncorrectable_sectors,
                "wear_leveling_count": s.wear_leveling_count,
                "reason": s.reason,
            })
        result["smart"] = smart_objs
        result["summary"]["smart_status"] = smart_overall
    return result


def apply_filter(partitions: List[Partition], pattern: Optional[str]) -> List[Partition]:
    if not pattern:
        return partitions
    return [p for p in partitions
            if pattern in p.device or pattern in p.mountpoint]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    """跨平台磁盘健康检查: 分区空间占用 + 可选 S.M.A.R.T。

    默认输出分区空间健康表; 加 --smart 尽力采集物理磁盘 SMART; --json 输出结构。
    """
    parser = argparse.ArgumentParser(
        usage="duck-disk-health [filter] [--smart] [--json] [--warn N] [--crit N]",
        description="跨平台磁盘健康检查: 分区空间占用(纯标准库) + 可选 S.M.A.R.T 真实健康(尽力而为)。")
    parser.add_argument("filter", nargs="?", default=None,
                        help="可选过滤: 只显示 device 或 mountpoint 包含该子串的分区")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 结构输出(可被脚本消费)")
    parser.add_argument("--smart", action="store_true",
                        help="开启 S.M.A.R.T 采集(默认关闭, 避免慢/需权限的调用)")
    parser.add_argument("--warn", type=int, default=80,
                        help="使用率警告阈值(%%)，默认 80")
    parser.add_argument("--crit", type=int, default=90,
                        help="使用率危险阈值(%%)，默认 90")
    args = parser.parse_args()

    partitions = apply_filter(list_partitions(), args.filter)
    smart_list: Optional[List[SmartInfo]] = None
    if args.smart:
        smart_list = collect_smart()

    if args.json:
        print(json.dumps(build_json(partitions, smart_list, args.warn, args.crit),
                         ensure_ascii=False, indent=2))
        return

    render_usage_table(partitions, args.warn, args.crit)
    if smart_list is not None:
        print()
        render_smart_table(smart_list)

    # 总体小结
    overall = STATUS_HEALTHY
    for p in partitions:
        overall = worst_status(overall, classify_usage(p.percent, args.warn, args.crit))
    if smart_list:
        for s in smart_list:
            overall = worst_status(overall, s.status)
    print()
    print("总体健康: " + colorize(STATUS_LABEL[overall], STATUS_COLOR[overall]))


if __name__ == "__main__":
    main()
