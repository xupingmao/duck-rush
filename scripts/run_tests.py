import subprocess, sys, os, json, time, re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_DEFS = [
    {"path": "tests/python/test_duck_server.py",        "runner": "pytest",  "lang": "Python"},
    {"path": "tests/python/import_test/main.py",         "runner": "python",  "lang": "Python"},
    {"path": "duck_rush/web-tools/pages/calculator/math-calculator.test.js", "runner": "node", "lang": "JavaScript"},
]

results = []
exit_code = 0

print("=" * 60)
print("  Duck Rush - Unified Test Runner")
print("=" * 60)

for t in TEST_DEFS:
    abspath = os.path.join(PROJECT_ROOT, t["path"])
    print(f"\n--- [{t['lang']}] {t['path']} ---")
    print(f"    File: {abspath}")
    
    if not os.path.exists(abspath):
        print(f"    SKIP: file not found")
        results.append({"test": t["path"], "lang": t["lang"], "status": "SKIP", "detail": "file not found", "time": 0})
        continue
    
    def _decode(data):
        return data.decode("utf-8", errors="replace") if data else ""

    start = time.time()
    try:
        if t["runner"] == "pytest":
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", abspath, "-v"],
                capture_output=True, timeout=120
            )
        elif t["runner"] == "python":
            proc = subprocess.run(
                [sys.executable, abspath],
                capture_output=True, timeout=120
            )
        elif t["runner"] == "node":
            proc = subprocess.run(
                ["node", abspath],
                capture_output=True, timeout=120
            )
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        elapsed = round(time.time() - start, 2)
        
        if proc.returncode == 0:
            print(f"    PASS ({elapsed}s)")
            results.append({"test": t["path"], "lang": t["lang"], "status": "PASS", "detail": "", "time": elapsed})
        else:
            print(f"    FAIL ({elapsed}s)")
            print(f"    stdout: {stdout.strip()[-2000:]}")
            print(f"    stderr: {stderr.strip()[-2000:]}")
            results.append({"test": t["path"], "lang": t["lang"], "status": "FAIL", "detail": stderr.strip()[:500], "time": elapsed})
            exit_code = 1
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT (>120s)")
        results.append({"test": t["path"], "lang": t["lang"], "status": "TIMEOUT", "detail": "", "time": 120})
        exit_code = 1
    except FileNotFoundError as e:
        print(f"    ERROR: {e}")
        results.append({"test": t["path"], "lang": t["lang"], "status": "ERROR", "detail": str(e), "time": 0})
        exit_code = 1

print("\n" + "=" * 60)
print("  Summary")
print("=" * 60)
total = len(results)
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] != "PASS")
print(f"  Total: {total}  |  Pass: {passed}  |  Fail: {failed}")
for r in results:
    icon = "PASS" if r["status"] == "PASS" else "FAIL"
    print(f"  [{icon}] {r['lang']:10s} {r['test']}  ({r['time']}s)")

report_path = os.path.join(PROJECT_ROOT, "test-report.json")
with open(report_path, "w") as f:
    json.dump({"results": results, "summary": {"total": total, "passed": passed, "failed": failed}}, f, indent=2)
print(f"\n  Report: {report_path}")

sys.exit(exit_code)
