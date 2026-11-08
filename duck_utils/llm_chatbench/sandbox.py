# -*- coding: utf-8 -*-
"""评测沙箱: 代码执行与虚拟文件树。

代码类场景把模型给出的实现落到临时目录并运行隐藏测试;
文件整理类场景把模型输出的 JSON 操作指令真实执行, 再把结果回灌给模型。
所有路径都限制在自建的临时目录内, 且文件沙箱不允许 delete 操作。
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .util import extract_code_blocks, extract_json

# 模型常把「实现 + 自己写的测试」放进同一个代码块, 这些测试会在拼接隐藏
# 脚本时被一并执行, 把真实能力判定污染掉。这里在第一个测试标记处截断。
_TEST_MARKERS = ('def test_', 'class Test', 'if __name__',
                 'unittest.main', 'pytest.main')


def _clean_solution(source: str) -> str:
    """只保留实现代码, 去掉同块内的自测代码与顶层断言。"""
    kept: List[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(m) for m in _TEST_MARKERS):
            break
        if stripped.startswith('test_') and stripped.endswith('()'):
            break
        if not line.startswith((' ', '\t')) and stripped.startswith('assert '):
            break
        kept.append(line)
    return '\n'.join(kept).strip()


class CodeSandbox:
    """保存模型当前实现代码, 并用隐藏测试脚本验证。"""

    def __init__(self, python_exe: str = '', allow_exec: bool = True,
                 timeout: int = 30, workdir: Optional[str] = None):
        self.python_exe = python_exe or sys.executable
        self.allow_exec = allow_exec
        self.timeout = timeout
        self.workdir = workdir or tempfile.mkdtemp(prefix='duck-chatbench-code-')
        self.solution = ''
        self.updated_rounds = 0
        os.makedirs(self.workdir, exist_ok=True)

    def update_from_reply(self, text: str, marker: str = '') -> bool:
        """从回复里提取实现代码。marker 非空时只接受含该标记的块, 避免
        '只给了测试代码' 的轮次把已有实现覆盖掉。"""
        blocks = extract_code_blocks(text, lang='python')
        if marker:
            blocks = [b for b in blocks if marker in b]
        if not blocks:
            return False
        cleaned = _clean_solution('\n\n'.join(blocks))
        if marker and marker not in cleaned:
            return False
        self.solution = cleaned
        self.updated_rounds += 1
        with open(os.path.join(self.workdir, 'solution.py'), 'w',
                  encoding='utf-8') as f:
            f.write(self.solution + '\n')
        return True

    def run_test(self, test_script: str) -> Tuple[bool, str]:
        """把实现与隐藏测试拼成一个脚本执行, 返回 (是否通过, 输出摘要)。"""
        if not self.solution:
            return False, '未提取到实现代码'
        if not self.allow_exec:
            return False, '代码执行已禁用 (--no-exec)'
        path = os.path.join(self.workdir, 'run_case.py')
        source = self.solution + '\n\n# ---- hidden tests ----\n' + test_script + '\n'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(source)
        try:
            proc = subprocess.run(
                [self.python_exe, path], cwd=self.workdir,
                capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return False, '测试超时 (%ds)' % self.timeout
        except Exception as e:
            return False, '%s: %s' % (type(e).__name__, e)
        out = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
        tail = '\n'.join(out.splitlines()[-6:])[:400]
        return proc.returncode == 0, tail or ('exit=%d' % proc.returncode)

    def close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class FileSandbox:
    """虚拟文件树。只接受 move/copy/mkdir, delete 一律记为违规且不执行。"""

    ALLOWED_OPS = ('move', 'copy', 'mkdir')

    def __init__(self, files: Dict[str, str],
                 allow_exec: bool = True,
                 workdir: Optional[str] = None):
        self.initial = dict(files or {})
        self.allow_exec = allow_exec
        self.workdir = workdir or tempfile.mkdtemp(prefix='duck-chatbench-files-')
        self.log: List[Dict[str, Any]] = []
        self.violations: List[str] = []
        os.makedirs(self.workdir, exist_ok=True)
        self.reset()

    def _safe_path(self, rel: str) -> Optional[str]:
        if not rel or not isinstance(rel, str):
            return None
        rel = rel.replace('\\', '/').strip()
        if rel.startswith('/') or '..' in rel.split('/') or ':' in rel:
            return None
        full = os.path.realpath(os.path.join(self.workdir, rel))
        root = os.path.realpath(self.workdir)
        if not (full == root or full.startswith(root + os.sep)):
            return None
        return full

    def reset(self) -> None:
        """恢复到初始文件树 (规则变更后重新执行时用)。"""
        for name in os.listdir(self.workdir):
            p = os.path.join(self.workdir, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except OSError:
                    pass
        self.log = []
        self.violations = []
        for rel, content in self.initial.items():
            full = self._safe_path(rel)
            if full is None:
                continue
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(str(content))

    def state(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for root, _dirs, names in os.walk(self.workdir):
            for name in names:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, self.workdir).replace('\\', '/')
                try:
                    with open(full, 'r', encoding='utf-8') as f:
                        result[rel] = f.read()
                except Exception:
                    result[rel] = ''
        return result

    def apply_ops(self, text: str) -> Tuple[List[Dict[str, Any]], str]:
        """解析并执行模型输出的操作列表, 返回 (已执行操作, 回灌给模型的反馈)。"""
        parsed = extract_json(text)
        ops: List[Any] = []
        if isinstance(parsed, dict):
            candidate = parsed.get('ops', parsed.get('operations', []))
            if isinstance(candidate, list):
                ops = candidate
        elif isinstance(parsed, list):
            ops = parsed
        if not ops:
            self.violations.append('未解析到 ops 列表')
            return [], '【文件操作执行结果】未解析到合法 JSON 操作列表, 没有任何文件被改动。'
        applied: List[Dict[str, Any]] = []
        lines: List[str] = []
        for raw in ops:
            if not isinstance(raw, dict):
                continue
            op = str(raw.get('op', raw.get('action', ''))).lower()
            if op not in self.ALLOWED_OPS:
                reason = '禁止的操作 %r (只允许 move/copy/mkdir)' % op
                self.violations.append(reason)
                lines.append('未执行: ' + reason)
                continue
            if op == 'mkdir':
                target = self._safe_path(str(raw.get('path', raw.get('dst', ''))))
                if target is None:
                    self.violations.append('非法路径 %r' % raw)
                    lines.append('未执行: 非法路径 %r' % raw)
                    continue
                os.makedirs(target, exist_ok=True)
                applied.append(dict(raw, op='mkdir'))
                lines.append('mkdir %s' % raw.get('path', raw.get('dst', '')))
                continue
            src = self._safe_path(str(raw.get('src', raw.get('from', ''))))
            dst = self._safe_path(str(raw.get('dst', raw.get('to', ''))))
            if src is None or dst is None or not os.path.isfile(src):
                self.violations.append('源不存在或路径非法 %r' % raw)
                lines.append('未执行: 源不存在或路径非法 %r' % raw)
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if op == 'move':
                shutil.move(src, dst)
            else:
                shutil.copy2(src, dst)
            applied.append({'op': op, 'src': str(raw.get('src', raw.get('from', ''))),
                            'dst': str(raw.get('dst', raw.get('to', '')))})
            lines.append('%s %s -> %s' % (op, raw.get('src', raw.get('from', '')),
                                          raw.get('dst', raw.get('to', ''))))
        self.log = applied
        tree = sorted(self.state().keys())
        summary = ['【文件操作执行结果】成功 %d 项:' % len(applied)]
        summary += lines[:12]
        if len(lines) > 12:
            summary.append('... 其余 %d 项省略' % (len(lines) - 12))
        if self.violations:
            summary.append('违规(未执行): ' + '; '.join(self.violations[-3:]))
        summary.append('当前文件数 %d, 文件树: %s' % (len(tree), ', '.join(tree[:20])))
        return applied, '\n'.join(summary)

    def close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)
