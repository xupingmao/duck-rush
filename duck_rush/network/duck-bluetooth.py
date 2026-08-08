# encoding=utf-8
# @since 2026/08/08

"""蓝牙带宽与已连接设备通信速度查看工具

子命令:
  list   列出当前已连接的蓝牙设备 (名称 / MAC / 状态 / 类型 / 理论通信速度上限)
  radio  显示本机蓝牙适配器信息与各蓝牙版本带宽上限对照表

重要说明 (关于 "通信速度"):
  Windows / macOS / Linux 桌面环境通常都 *不* 向应用层暴露单个蓝牙链路的
  实时吞吐率 (即真实的 "带宽 / 通信速度")。因此本工具展示的 "通信速度" 是
  基于蓝牙版本与设备类型 (A2DP / HID / SPP / PAN ...) 推算的 *理论峰值*,
  并非实时实测值。

  若确实需要实时实测:
    - 支持串口 (SPP) 的设备: 可在两端互发数据并计时测得真实速率;
    - 蓝牙网络 (PAN) 连接: 可读取对应网卡的 LinkSpeed。
  这两类实时测量本工具暂未内置, 如需可继续扩展。
"""

import sys
import json
import re
import subprocess
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import duck_utils.os_util as os_util


# ---------------------------------------------------------------------------
# 蓝牙服务 UUID -> 友好名称 (截取 SIG 定义中常用的一部分)
# ---------------------------------------------------------------------------
SERVICE_UUID_MAP: Dict[str, str] = {
    "00001101": "串口(SPP)",
    "00001102": "网络(PAN)",
    "00001103": "拨号网络(DUN)",
    "00001105": "对象推送(OPP)",
    "00001106": "文件传输(FTP)",
    "0000110A": "A2DP音频源",
    "0000110B": "A2DP音频汇",
    "0000110C": "音视频遥控(AVRCP)",
    "0000110D": "A2DP",
    "0000110E": "音视频遥控目标(AVRCP)",
    "00001112": "耳机(HSP)",
    "0000111E": "免提(HFP)",
    "0000111F": "音频/视频网关",
    "00001120": "电话簿(PBAP)",
    "00001124": "人机接口(HID)",
    "0000112F": "免提音频(HFP)",
    "00001133": "消息访问(MAP)",
}

# 仅用于推断设备大类的 "类型关键字 -> 中文设备类型"
_TYPE_BY_SERVICE: List[Tuple[str, str]] = [
    ("A2DP", "音频设备(耳机/音箱)"),
    ("AVRCP", "音频设备(耳机/音箱)"),
    ("HSP", "音频设备(耳机/音箱)"),
    ("HFP", "音频设备(耳机/音箱)"),
    ("HID", "输入设备(键鼠)"),
    ("SPP", "串口设备"),
    ("PAN", "网络设备(PAN)"),
    ("FTP", "文件传输设备"),
    ("OPP", "对象推送设备"),
]

# 各蓝牙版本的理论带宽上限 (链路层峰值, 非可用吞吐)
BT_VERSION_BANDWIDTH: List[Tuple[str, str]] = [
    ("Bluetooth 1.1 / 1.2", "1 Mbps (基础速率 BR)"),
    ("Bluetooth 2.0 + EDR", "3 Mbps (EDR 增强数据率)"),
    ("Bluetooth 3.0 + HS", "24 Mbps (借助 802.11 高速承载)"),
    ("Bluetooth 4.0 LE", "1 Mbps (低功耗)"),
    ("Bluetooth 4.2 LE", "1 Mbps (含 IPv6 / 隐私增强)"),
    ("Bluetooth 5.0", "经典 3 Mbps / 低功耗 2 Mbps (LE 2M)"),
    ("Bluetooth 5.1", "经典 3 Mbps / 低功耗 2 Mbps"),
    ("Bluetooth 5.2", "经典 3 Mbps / 低功耗 2 Mbps (含 LE Audio)"),
    ("Bluetooth 5.3 / 5.4", "经典 3 Mbps / 低功耗 2 Mbps (健壮性增强)"),
]

# 匹配 InstanceId 中正好 12 位十六进制 (蓝牙 MAC 地址, 不含更长/更短的十六进制串)
_MAC12_RE = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")
# 蓝牙 SIG 基础 UUID 的尾部 (00000000-0000-1000-8000-00805F9B34FB), 不是 MAC 地址
_SIG_BASE_TAIL = "00805F9B34FB"
_DEV_MAC_RE = re.compile(r"DEV_([0-9A-Fa-f]{12})", re.IGNORECASE)
# 匹配服务 UUID: {0000110C-0000-1000-8000-00805F9B34FB}
_UUID_RE = re.compile(r"\{([0-9A-Fa-f]{8})-0000-1000-8000-00805F9B34FB\}", re.IGNORECASE)

# 本地蓝牙基础设施条目 (非远端设备), 用于过滤
_INFRA_NAMES = (
    "microsoft 蓝牙",
    "microsoft bluetooth",
    "rfcomm protocol tdi",
    "bluetooth device (rfcomm",
)


@dataclass
class BluetoothDevice:
    mac: str
    name: str = ""
    status: str = ""
    connected: bool = False
    services: List[str] = field(default_factory=list)
    device_type: str = "其他设备"
    speed: str = ""


def _format_mac(raw: str) -> str:
    """将 12 位十六进制串格式化为 XX:XX:XX:XX:XX:XX。"""
    raw = raw.upper()
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def _extract_mac(instance_id: str) -> Optional[str]:
    """从 PnP InstanceId 中提取远端设备 MAC 地址。

    优先取 DEV_ 前缀的真实地址; 其余 12 位十六进制中需排除蓝牙 SIG 基础
    UUID 尾部 (00805F9B34FB), 否则会被误判为 MAC。
    """
    dev_match = _DEV_MAC_RE.search(instance_id)
    if dev_match:
        return _format_mac(dev_match.group(1))
    for m in _MAC12_RE.finditer(instance_id):
        val = m.group(0).upper()
        if val == _SIG_BASE_TAIL:
            continue
        return _format_mac(val)
    return None


def _is_infra(friendly_name: str) -> bool:
    low = (friendly_name or "").lower()
    return any(k in low for k in _INFRA_NAMES)


def _service_name(uuid: str) -> str:
    return SERVICE_UUID_MAP.get(uuid.upper(), "未知服务(%s)" % uuid)


def _infer_device_type(services: List[str]) -> str:
    blob = " ".join(services)
    for key, label in _TYPE_BY_SERVICE:
        if key in blob:
            return label
    return "其他设备"


def _theoretical_speed(device_type: str, services: List[str]) -> str:
    blob = " ".join(services)
    if "A2DP" in blob or "AVRCP" in blob or "HSP" in blob or "HFP" in blob:
        return "音频链路 ~0.3-1 Mbps (取决于 SBC/aptX/LDAC 等编解码器)"
    if "HID" in blob:
        return "< 1 Mbps (低速率输入设备)"
    if "SPP" in blob:
        return "最高 ~2.1 Mbps (EDR 串口)"
    if "PAN" in blob:
        return "经典 ~2-3 Mbps; 部分实现借 Wi-Fi 可达数十 Mbps"
    if device_type == "文件传输设备" or "FTP" in blob or "OPP" in blob:
        return "最高 ~2.1 Mbps (EDR 文件传输)"
    return "取决于本机蓝牙适配器版本 (见 radio 命令带宽对照表)"


def _dedupe_services(services: List[str]) -> List[str]:
    seen: List[str] = []
    for s in services:
        if s not in seen:
            seen.append(s)
    return seen


# ---------------------------------------------------------------------------
# Windows 实现 (通过 PowerShell 读取 PnP 蓝牙设备)
# ---------------------------------------------------------------------------
def _ps_run(script: str, timeout: int = 20) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.stdout.decode("utf-8", errors="replace")


def _enumerate_windows() -> List[BluetoothDevice]:
    script = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue"
        " | Select-Object FriendlyName,Status,InstanceId"
        " | ConvertTo-Json -Compress"
    )
    out = _ps_run(script).strip()
    if not out:
        return []
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        items: List[dict] = [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        return []

    # 按 MAC 聚合同一设备的多个服务条目
    by_mac: Dict[str, BluetoothDevice] = {}
    adapters: List[BluetoothDevice] = []

    for item in items:
        friendly = item.get("FriendlyName") or ""
        status = item.get("Status") or ""
        instance_id = item.get("InstanceId") or ""

        mac = _extract_mac(instance_id)
        if mac is None:
            # 没有远端 MAC: 可能是本机适配器 (如 "MediaTek Bluetooth Adapter")
            if _is_infra(friendly):
                continue
            if "adapter" in friendly.lower() or "controller" in friendly.lower():
                adapters.append(BluetoothDevice(
                    mac="(本机)", name=friendly, status=status,
                    device_type="蓝牙适配器", speed="",
                ))
            continue

        if _is_infra(friendly) and "DEV_" not in instance_id:
            continue

        uuids = _UUID_RE.findall(instance_id)
        svc_names = [_service_name(u) for u in uuids]

        dev = by_mac.get(mac)
        if dev is None:
            dev = BluetoothDevice(mac=mac, name=friendly, status=status)
            by_mac[mac] = dev
        else:
            # 优先使用非服务类条目的名称 (DEV_ 基础条目)
            if friendly and ("DEV_" in instance_id or not dev.name):
                dev.name = friendly
            if status == "OK":
                dev.status = status
        if svc_names:
            dev.services.extend(svc_names)
        if status == "OK":
            dev.connected = True

    result: List[BluetoothDevice] = []
    result.extend(adapters)
    for dev in by_mac.values():
        dev.services = _dedupe_services(dev.services)
        dev.device_type = _infer_device_type(dev.services)
        dev.speed = _theoretical_speed(dev.device_type, dev.services)
        result.append(dev)
    return result


# ---------------------------------------------------------------------------
# Linux 实现 (best-effort, 借助 bluetoothctl / hciconfig)
# ---------------------------------------------------------------------------
def _run(cmd: List[str], timeout: int = 20) -> str:
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return proc.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _enumerate_linux() -> List[BluetoothDevice]:
    raw = _run(["bluetoothctl", "devices"])
    if not raw:
        return []
    devices: List[BluetoothDevice] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("Device"):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        mac = parts[1]
        name = parts[2].strip() if len(parts) >= 3 else ""
        info = _run(["bluetoothctl", "info", mac])
        connected = "Connected: yes" in info
        services: List[str] = []
        for svc_line in info.splitlines():
            m = re.search(r"UUID:.*?([0-9A-Fa-f]{8})", svc_line)
            if m:
                services.append(_service_name(m.group(1)))
        services = _dedupe_services(services)
        dtype = _infer_device_type(services)
        devices.append(BluetoothDevice(
            mac=mac, name=name, status="已连接" if connected else "已配对",
            connected=connected, services=services, device_type=dtype,
            speed=_theoretical_speed(dtype, services),
        ))
    return devices


# ---------------------------------------------------------------------------
# macOS 实现 (best-effort, 借助 system_profiler)
# ---------------------------------------------------------------------------
def _enumerate_mac() -> List[BluetoothDevice]:
    raw = _run(["system_profiler", "SPBluetoothDataType"])
    if not raw:
        return []
    devices: List[BluetoothDevice] = []
    # system_profiler 文本较自由, 这里做最基础的解析:
    # 形如 "ACCENTUM:" 后跟 "  Connected: Yes" / "  Address: xx:xx:..."
    current_name: Optional[str] = None
    current_mac: Optional[str] = None
    current_connected = False
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z0-9_\- ]+):\s*$", line)
        if m and not line.startswith(" "):
            # 新设备块开始
            if current_name and current_mac:
                devices.append(BluetoothDevice(
                    mac=current_mac, name=current_name,
                    status="已连接" if current_connected else "已配对",
                    connected=current_connected, device_type="其他设备",
                    speed="取决于本机蓝牙适配器版本 (见 radio 命令)",
                ))
            current_name = m.group(1).strip()
            current_mac = None
            current_connected = False
            continue
        if current_name is not None:
            am = re.search(r"Address:\s*([0-9A-Fa-f:]{17})", line)
            if am:
                current_mac = am.group(1)
            if "Connected: Yes" in line:
                current_connected = True
    if current_name and current_mac:
        devices.append(BluetoothDevice(
            mac=current_mac, name=current_name,
            status="已连接" if current_connected else "已配对",
            connected=current_connected, device_type="其他设备",
            speed="取决于本机蓝牙适配器版本 (见 radio 命令)",
        ))
    return devices


def _enumerate() -> List[BluetoothDevice]:
    if os_util.is_windows():
        return _enumerate_windows()
    if os_util.is_linux():
        return _enumerate_linux()
    if os_util.is_mac():
        return _enumerate_mac()
    return []


# ---------------------------------------------------------------------------
# 展示
# ---------------------------------------------------------------------------
def _print_devices(devices: List[BluetoothDevice]) -> None:
    if not devices:
        print("未发现蓝牙设备。请确认蓝牙已开启, 且存在已配对/已连接的设备。")
        return

    adapters = [d for d in devices if d.device_type == "蓝牙适配器"]
    remotes = [d for d in devices if d.device_type != "蓝牙适配器"]

    if adapters:
        print("本机蓝牙适配器:")
        for a in adapters:
            print("  - %s  [%s]" % (a.name, a.status))
        print()

    print("已连接 / 已配对设备:")
    if not remotes:
        print("  (无)")
        return
    for d in remotes:
        state = "已连接" if d.connected else "已配对"
        print("  %s  (%s)" % (d.name or "(未知名称)", d.mac))
        print("    状态   : %s (%s)" % (state, d.status))
        print("    类型   : %s" % d.device_type)
        if d.services:
            print("    服务   : %s" % ", ".join(d.services))
        print("    通信速度: %s" % d.speed)
        print()


def _print_radio() -> None:
    print("蓝牙带宽对照表 (链路层理论峰值, 非可用吞吐):")
    print("  %-22s %s" % ("蓝牙版本", "理论带宽上限"))
    print("  " + "-" * 56)
    for ver, bw in BT_VERSION_BANDWIDTH:
        print("  %-22s %s" % (ver, bw))
    print()
    print("说明:")
    print("  - 实际可用吞吐通常只有理论峰值的 1/2 ~ 2/3 (协议开销、重传、调度)。")
    print("  - 本机适配器决定链路上限: 链路速率取本机与对端中较低的一方。")
    print("  - Windows 不向应用层暴露单链路实时吞吐率, 本工具仅给出理论峰值。")
    print("  - 如需实时实测: SPP 设备可互发数据计时; PAN 连接可读网卡 LinkSpeed。")


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
def cmd_list(args: argparse.Namespace) -> None:
    devices = _enumerate()
    _print_devices(devices)


def cmd_radio(args: argparse.Namespace) -> None:
    _print_radio()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duck-bluetooth",
        description="查看蓝牙带宽与已连接蓝牙设备的通信速度(理论峰值)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="列出已连接的蓝牙设备及其理论通信速度 (默认)")
    sub.add_parser("radio", help="显示本机蓝牙适配器与各版本带宽对照表")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "list"
    if command == "radio":
        cmd_radio(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    # 最开头处理 -h/--help, 不产生任何副作用, 直接退出 0
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()
