# -*- coding: utf-8 -*-
"""
duck-shell 的 headless 冒烟测试（基于 Textual 的 run_test，无需真实终端）。

直接运行： python duck_rush/shell/test_duck_shell.py
"""
import asyncio
import importlib.util
import os
import sys

from textual.widgets import Input, RichLog, DirectoryTree


# 通过文件路径加载带连字符的模块（duck-shell.py 无法用普通 import）
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "duck_shell_mod", os.path.join(_HERE, "duck-shell.py"))
duck_shell_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["duck_shell_mod"] = duck_shell_mod
_SPEC.loader.exec_module(duck_shell_mod)
DuckShellApp = duck_shell_mod.DuckShellApp


async def _submit(app, pilot, cmd):
    inp = app.query_one("#cmdline", Input)
    inp.post_message(Input.Submitted(inp, cmd))
    # 等待命令被分发并处理：shell 命令会进入 busy，cd 之类不会
    for i in range(300):
        await asyncio.sleep(0.02)
        await pilot.pause()
        if not app.busy and i >= 3:
            break


async def _wait_cwd(app, pilot, expected):
    target = os.path.normcase(expected)
    for _ in range(100):
        await asyncio.sleep(0.02)
        await pilot.pause()
        if os.path.normcase(app.cwd) == target:
            return True
    return False


async def test_startup_and_echo():
    app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
    captured = []
    orig = app._write

    def cap(text):
        captured.append(text)
        orig(text)

    app._write = cap
    async with app.run_test() as pilot:
        assert app.query_one("#terminal", RichLog) is not None
        assert app.query_one("#tree") is not None
        await _submit(app, pilot, "echo hello")
        assert "hello" in "".join(captured)
        assert not app.busy


async def test_cd_changes_cwd_and_tree():
    start = os.getcwd()
    parent = os.path.dirname(start)
    app = DuckShellApp(start_path=start, max_lines=500)
    async with app.run_test() as pilot:
        await _submit(app, pilot, "cd ..")
        assert await _wait_cwd(app, pilot, parent)
        # 目录树已重新根定到新工作目录
        assert os.path.normcase(str(app.query_one("#tree", DirectoryTree).path)) == os.path.normcase(parent)


async def test_up_via_tree():
    # 点击目录树首行的虚拟「返回上级目录」节点 = 返回上级目录
    # 通过 select_node 走真实的选择事件路径（Tree.NodeSelected -> DirectoryTree 处理）
    start = os.getcwd()
    parent = os.path.dirname(start)
    app = DuckShellApp(start_path=start, max_lines=500)
    async with app.run_test() as pilot:
        tree = app.query_one("#tree", duck_shell_mod.DuckDirTree)
        # 等待虚拟「返回上级目录」节点出现在首行
        up_node = None
        for _ in range(100):
            await pilot.pause()
            for child in tree.root.children:
                if isinstance(child.data, duck_shell_mod._UpEntry):
                    up_node = child
                    break
            if up_node is not None:
                break
        assert up_node is not None, "目录树未注入[返回上级目录]虚拟节点"
        # 首行即该虚拟节点
        assert tree.root.children[0] is up_node, "虚拟节点不在首行"
        # 模拟点击：移动到该节点并触发 NodeSelected 事件
        tree.select_node(up_node)
        await pilot.pause()
        assert await _wait_cwd(app, pilot, parent)


async def test_context_limit():
    # max_lines 较小，输出大量行，验证 RichLog 行数被裁剪（上下文上限生效）
    app = DuckShellApp(start_path=os.getcwd(), max_lines=50)
    async with app.run_test() as pilot:
        await _submit(app, pilot, 'python -c "for i in range(200): print(i)"')
        lines = app.query_one("#terminal", RichLog).lines
        assert len(lines) <= 50, "终端历史未被裁剪: %d" % len(lines)


async def test_terminal_scrollable():
    # 输出足够多行后应可滚动（修复：右侧输出无法滚动）
    app = DuckShellApp(start_path=os.getcwd(), max_lines=1000)
    async with app.run_test(size=(80, 40)) as pilot:
        await _submit(app, pilot, 'python -c "for i in range(120): print(i)"')
        term = app.query_one("#terminal", RichLog)
        assert term.max_scroll_y > 0, "终端不可滚动: max_scroll_y=%r" % term.max_scroll_y
        term.scroll_to(y=10, animate=False)
        await pilot.pause()
        assert term.scroll_y > 0, "滚动位置未被改变"


async def test_is_attach():
    # 交互式命令判定（交接屏幕控制权）
    app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
    assert app._is_attach("python") is True
    assert app._is_attach("vim file.txt") is True
    assert app._is_attach("!dir") is True
    assert app._is_attach("echo hi") is False
    assert app._is_attach("ls") is False


async def test_nonzero_exit():
    app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
    captured = []
    orig = app._write

    def cap(text):
        captured.append(text)
        orig(text)

    app._write = cap
    async with app.run_test() as pilot:
        await _submit(app, pilot, "exit 3")
        assert "[退出码 3]" in "".join(captured)


FAILED = 0


def _run(coro):
    global FAILED
    try:
        asyncio.run(coro())
        print("PASS:", coro.__name__)
    except Exception as e:  # noqa
        FAILED += 1
        print("FAIL:", coro.__name__, "->", repr(e))
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    _run(test_startup_and_echo)
    _run(test_cd_changes_cwd_and_tree)
    _run(test_up_via_tree)
    _run(test_context_limit)
    _run(test_terminal_scrollable)
    _run(test_is_attach)
    _run(test_nonzero_exit)
    sys.exit(1 if FAILED else 0)
