# -*- coding:utf-8 -*-
"""duck-disk-health 的单元测试(仅依赖标准库)。

运行: python duck_rush/os/test_duck_disk_health.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "duck-disk-health.py")


def load_mod():
    """以 importlib 加载带连字符的脚本模块。"""
    spec = importlib.util.spec_from_file_location("duck_disk_health_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = load_mod()


SAMPLE_SMART = """
smartctl 7.4 2023-08-01 r5530 [x86_64-linux] (local build)
=== START OF INFORMATION SECTION ===
Model Family:     Samsung SSD 870 EVO
Device Model:     Samsung SSD 870 EVO 1TB
=== START OF READ SMART DATA SECTION ===
SMART overall-health self-assessment test result: PASSED

ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE
  5 Reallocated_Sector_Ct   0x0033   100   100   010    Pre-fail  Always       -       0
  9 Power_On_Hours          0x0032   099   099   000    Old_age   Always       -       12345
190 Airflow_Temperature_Cel 0x0022   070   060   045    Old_age   Always       -       30
194 Temperature_Celsius     0x0022   070   060   000    Old_age   Always       -       30
197 Current_Pending_Sector  0x0012   100   100   000    Old_age   Always       -       0
198 Offline_Uncorrectable   0x0010   100   100   000    Old_age   Always       -       0
173 Wear_Leveling_Count     0x0033   098   098   010    Old_age   Always       -       1234
241 Total_LBAs_Written      0x0032   099   099   000    Old_age   Always       -       100000000
242 Total_LBAs_Read         0x0032   099   099   000    Old_age   Always       -       50000000
"""

SAMPLE_NVME = """
smartctl 7.4 2023-08-01 r5530 [x86_64-linux] (local build)
=== START OF INFORMATION SECTION ===
Model Number:                       Samsung SSD 980 PRO 1TB
Firmware Version:                  5B2QGXA7
=== START OF SMART DATA SECTION ===
SMART/Health Information (NVMe Log 0x02)
Critical Warning:                   0x00
Temperature:                        36 Celsius
Available Spare:                    100%
Available Spare Threshold:          10%
Percentage Used:                    3%
Data Units Read:                    12,345,678 [6.32 TB]
Data Units Written:                 23,456,789 [12.0 TB]
Host Read Commands:                 123,456,789
Host Write Commands:                234,567,890
Controller Busy Time:               1,234
Power Cycles:                      123
Power On Hours:                    12,345
Unsafe Shutdowns:                  45
Media and Data Integrity Errors:   0
Error Information Log Entries:     0
"""


class TestClassifyUsage(unittest.TestCase):

    def test_healthy(self):
        self.assertEqual(mod.classify_usage(0, 80, 90), mod.STATUS_HEALTHY)
        self.assertEqual(mod.classify_usage(79.9, 80, 90), mod.STATUS_HEALTHY)

    def test_warning(self):
        self.assertEqual(mod.classify_usage(80, 80, 90), mod.STATUS_WARNING)
        self.assertEqual(mod.classify_usage(89.9, 80, 90), mod.STATUS_WARNING)

    def test_critical(self):
        self.assertEqual(mod.classify_usage(90, 80, 90), mod.STATUS_CRITICAL)
        self.assertEqual(mod.classify_usage(100, 80, 90), mod.STATUS_CRITICAL)

    def test_custom_thresholds(self):
        self.assertEqual(mod.classify_usage(70, 70, 85), mod.STATUS_WARNING)
        self.assertEqual(mod.classify_usage(85, 70, 85), mod.STATUS_CRITICAL)


class TestFormatBytes(unittest.TestCase):

    def test_units(self):
        self.assertEqual(mod.format_bytes(0), "0 B")
        self.assertEqual(mod.format_bytes(512), "512 B")
        self.assertEqual(mod.format_bytes(1024), "1.00 KiB")
        self.assertEqual(mod.format_bytes(1024 * 1024 * 1024), "1.00 GiB")

    def test_large(self):
        text = mod.format_bytes(1024 * 1024 * 1024 * 1024)
        self.assertTrue(text.startswith("1.00 TiB"))


class TestParseSmart(unittest.TestCase):

    def test_passed(self):
        health, metrics = mod.parse_smart_output(SAMPLE_SMART)
        self.assertEqual(health, mod.STATUS_HEALTHY)
        self.assertEqual(metrics.get("temperature"), 30)
        self.assertEqual(metrics.get("power_on_hours"), 12345)
        self.assertEqual(metrics.get("reallocated_sectors"), 0)
        self.assertEqual(metrics.get("pending_sectors"), 0)
        self.assertEqual(metrics.get("uncorrectable_sectors"), 0)
        self.assertEqual(metrics.get("total_lbas_written"), 100000000)
        self.assertEqual(metrics.get("total_lbas_read"), 50000000)
        self.assertEqual(metrics.get("wear_leveling_count"), 1234)

    def test_failed(self):
        text = SAMPLE_SMART.replace("PASSED", "FAILED")
        health, _ = mod.parse_smart_output(text)
        self.assertEqual(health, mod.STATUS_CRITICAL)


class TestParseNvme(unittest.TestCase):

    def test_passed(self):
        health, metrics = mod.parse_smart_output(SAMPLE_NVME)
        self.assertEqual(health, mod.STATUS_HEALTHY)
        # 寿命已用 3%
        self.assertEqual(metrics.get("percentage_used"), 3)
        # Data Units: 1 单元 = 1000 * 512 字节
        self.assertEqual(metrics.get("total_lbas_written"), 23456789)
        self.assertEqual(metrics.get("total_bytes_written"), 23456789 * 512 * 1000)
        self.assertEqual(metrics.get("total_lbas_read"), 12345678)
        self.assertEqual(metrics.get("total_bytes_read"), 12345678 * 512 * 1000)
        self.assertEqual(metrics.get("temperature"), 36)
        self.assertEqual(metrics.get("power_on_hours"), 12345)

    def test_critical_warning(self):
        text = SAMPLE_NVME.replace("Critical Warning:                   0x00",
                                   "Critical Warning:                   0x04")
        health, _ = mod.parse_smart_output(text)
        self.assertEqual(health, mod.STATUS_CRITICAL)


class TestApplyFilter(unittest.TestCase):

    def test_no_filter(self):
        parts = [mod.Partition("a", "/a", None, 1, 1, 0, 0.0)]
        self.assertEqual(mod.apply_filter(parts, None), parts)

    def test_by_device(self):
        parts = [
            mod.Partition("/dev/sda1", "/", None, 1, 1, 0, 0.0),
            mod.Partition("/dev/sdb1", "/data", None, 1, 1, 0, 0.0),
        ]
        out = mod.apply_filter(parts, "sdb")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].device, "/dev/sdb1")


if __name__ == "__main__":
    unittest.main()
