# -*- coding: utf-8 -*-
"""
duck-shell 的 headless 冒烟测试（基于 Textual 的 run_test，无需真实终端）。

直接运行： python duck_rush/shell/test_duck_shell.py
"""
import asyncio
import importlib.util
import os
import sys

import tempfile

from rich.style import Style
from textual.widgets import Input, RichLog, DirectoryTree, Button


# 通过文件路径加载带连字符的模块（duck-shell.py 无法用普通 import）
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "duck_shell_mod", os.path.join(_HERE, "duck-shell.py"))
assert _SPEC is not None
assert _SPEC.loader is not None
duck_shell_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["duck_shell_mod"] = duck_shell_mod
_SPEC.loader.exec_module(duck_shell_mod)
DuckShellApp = duck_shell_mod.DuckShellApp
# duck-shell 已导入 duck_utils，直接复用其 JsonlStore
JsonlStore = duck_shell_mod.JsonlStore


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


async def _wait_for(pilot, predicate, times=100):
    """轮询等待 predicate() 为真（容错异步消息分发的时序不确定性）。"""
    for _ in range(times):
        await asyncio.sleep(0.02)
        await pilot.pause()
        if predicate():
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


async def test_up_via_button():
    # 点击按钮组中的「返回上级目录」= 返回上级目录
    start = os.getcwd()
    parent = os.path.dirname(start)
    app = DuckShellApp(start_path=start, max_lines=500)
    async with app.run_test() as pilot:
        btn = app.query_one("#up_entry", Button)
        btn.post_message(Button.Pressed(btn))
        assert await _wait_cwd(app, pilot, parent)


async def test_bookmark_dao():
    # 收藏夹 DAO：JSONL 持久化 + toggle + 路径规范化
    with tempfile.TemporaryDirectory() as tmp:
        dao = duck_shell_mod.BookmarkDao(root=tmp)
        p1 = os.path.join(tmp, "a")
        p2 = os.path.join(tmp, "b")
        os.makedirs(p1)
        os.makedirs(p2)
        assert dao.all() == []
        assert dao.has(p1) is False
        dao.add(p1)
        assert dao.has(p1) is True
        # 重复 add 不重复
        dao.add(p1)
        assert len(dao.all()) == 1
        # 路径规范化后重复（尾部斜杠）不重复
        dao.add(p1 + os.sep)
        assert len(dao.all()) == 1
        # toggle 关闭
        assert dao.toggle(p1) is False
        assert dao.has(p1) is False
        # toggle 开启
        assert dao.toggle(p2) is True
        assert dao.has(p2) is True
        # JSONL 格式：每行一个 JSON 对象
        with open(os.path.join(tmp, "bookmarks.jsonl"), "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        assert len(lines) == 1, "JSONL 行数不符: %r" % lines
        import json as _json
        obj = _json.loads(lines[0])
        assert obj["path"] == p2


async def test_fav_toggle_button():
    # 点击「收藏/取消收藏」按钮：文案切换 + 持久化
    with tempfile.TemporaryDirectory() as tmp:
        app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
        app.dao = duck_shell_mod.BookmarkDao(root=tmp)
        async with app.run_test() as pilot:
            btn = app.query_one("#fav_toggle", Button)
            assert btn.label == "收藏"
            assert app.dao.has(app.cwd) is False
            btn.post_message(Button.Pressed(btn))
            assert await _wait_for(pilot, lambda: btn.label == "取消收藏")
            assert app.dao.has(app.cwd) is True
            # 再点一次取消
            btn.post_message(Button.Pressed(btn))
            assert await _wait_for(pilot, lambda: btn.label == "收藏")
            assert app.dao.has(app.cwd) is False


async def test_bookmark_pick():
    # 打开收藏夹弹窗，点击某项可跳转到该目录
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "go")
        os.makedirs(target)
        app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
        app.dao = duck_shell_mod.BookmarkDao(root=tmp)
        app.dao.add(target)
        async with app.run_test() as pilot:
            app.push_screen(duck_shell_mod.BookmarkScreen(app.dao), app._on_bookmark_picked)
            await pilot.pause()
            # 找到跳转按钮并点击
            screen = app.screen
            goto = None
            for b in screen.query(Button):
                if getattr(b, "bm_path", None) == target and b.id == "bm_goto":
                    goto = b
                    break
            assert goto is not None, "收藏夹未列出目标目录"
            goto.post_message(Button.Pressed(goto))
            assert await _wait_for(pilot, lambda: os.path.normcase(app.cwd) == os.path.normcase(target))


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


async def test_no_extra_blank_lines():
    # 每条输出应占独立一行，不应因多余换行产生空行（去掉行间距）
    app = DuckShellApp(start_path=os.getcwd(), max_lines=1000)
    async with app.run_test(size=(100, 40)) as pilot:
        term = app.query_one("#terminal", RichLog)
        await pilot.pause()
        for i in range(100):
            app._write("line-%d" % i)
        await pilot.pause()
        # 不含任何纯空行（行间距）
        blanks = sum(1 for ln in term.lines if ln.text == "")
        assert blanks == 0, "存在多余空行（行间距）: %d" % blanks


async def test_scroll_binding():
    # PageUp/PageDown 绑定可在输入框聚焦时滚动右侧终端
    app = DuckShellApp(start_path=os.getcwd(), max_lines=1000)
    async with app.run_test(size=(100, 40)) as pilot:
        term = app.query_one("#terminal", RichLog)
        await pilot.pause()
        for i in range(120):
            app._write("line-%d" % i)
        await pilot.pause()
        assert term.max_scroll_y > 0
        # 先 PageUp 离开底部，再 PageDown 应能向下滚动
        await pilot.press("pageup")
        await pilot.pause()
        after_up = term.scroll_y
        assert after_up < term.max_scroll_y, "PageUp 未改变滚动位置"
        await pilot.press("pagedown")
        await pilot.pause()
        assert term.scroll_y > after_up, "PageDown 未向下滚动"


async def test_ansi_color():
    # 命令输出的 ANSI 颜色转义应被解析为富文本样式，而非以原始控制字符显示
    app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
    async with app.run_test() as pilot:
        term = app.query_one("#terminal", RichLog)
        await pilot.pause()
        app._write("\x1b[31mhello\x1b[0m")
        await pilot.pause()
        last = term.lines[-1]
        assert last.text == "hello", "ANSI 转义未被解析，仍残留控制字符: %r" % last.text


async def test_subprocess_stdin_isolated():
    # 子进程必须断开 stdin，否则会继承本应用终端输入、与 Textual 抢夺，
    # 导致界面两侧滚动条卡死。这里用「读取 stdin」的命令验证其能立即得到 EOF 并完成。
    app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
    async with app.run_test() as pilot:
        # 该命令若继承了终端 stdin 会一直阻塞等待输入（界面卡死）；
        # 使用 DEVNULL 时应立即读到 EOF 并退出。
        await _submit(app, pilot, "python -c \"import sys; print('stdin_bytes=%d' % len(sys.stdin.read()))\"")
        assert not app.busy, "命令疑似因 stdin 继承而卡死"
        captured = "".join(l.text for l in app.query_one("#terminal", RichLog).lines)
        assert "stdin_bytes=0" in captured, "子进程未正确隔离 stdin: %s" % captured


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


async def test_tab_completion():
    # 输入命令前缀时给出补全建议，Tab 接受
    with tempfile.TemporaryDirectory() as tmp:
        app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
        app._history_store = JsonlStore(os.path.join(tmp, "h.jsonl"))
        async with app.run_test() as pilot:
            inp = app.query_one("#cmdline")
            inp.focus()
            await pilot.pause()
            inp.value = "cl"
            # 补全建议由 worker 异步计算，轮询等待
            ok = await _wait_for(pilot, lambda: inp._suggestion == "clear", times=50)
            assert ok, "未产生补全建议: %r" % inp._suggestion
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "clear", "Tab 补全失败: %r" % inp.value


async def test_history_navigation():
    # 上下方向键在已执行命令间切换
    with tempfile.TemporaryDirectory() as tmp:
        app = DuckShellApp(start_path=os.getcwd(), max_lines=500)
        app._history_store = JsonlStore(os.path.join(tmp, "h.jsonl"))
        async with app.run_test() as pilot:
            await _submit(app, pilot, "echo first")
            await _submit(app, pilot, "echo second")
            await _submit(app, pilot, "echo third")
            inp = app.query_one("#cmdline")
            inp.focus()
            await pilot.pause()
            assert app.history[-3:] == ["echo first", "echo second", "echo third"], app.history
            await pilot.press("up")
            await pilot.pause()
            assert inp.value == "echo third", inp.value
            await pilot.press("up")
            await pilot.pause()
            assert inp.value == "echo second", inp.value
            await pilot.press("up")
            await pilot.pause()
            assert inp.value == "echo first", inp.value
            # 顶部继续上翻应被夹住
            await pilot.press("up")
            await pilot.pause()
            assert inp.value == "echo first", inp.value
            await pilot.press("down")
            await pilot.pause()
            assert inp.value == "echo second", inp.value
            # 下翻越过末尾应回到空草稿
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert inp.value == "", inp.value


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


async def test_dir_child_file_count():
    # 左侧目录树：目录节点在名称后附加「直接子项数量」（文件+文件夹，灰色），不递归统计
    with tempfile.TemporaryDirectory() as tmp:
        # 顶层放一个目录 sub（含 3 个文件 + 1 个子目录）与一个普通文件
        sub = os.path.join(tmp, "sub")
        os.makedirs(os.path.join(sub, "nested"))
        for i in range(3):
            open(os.path.join(sub, "f%d.txt" % i), "w").close()
        open(os.path.join(tmp, "top.txt"), "w").close()

        app = DuckShellApp(start_path=tmp, max_lines=500)
        async with app.run_test(size=(40, 20)) as pilot:
            tree = app.query_one("#tree", DirectoryTree)
            # 等待子节点异步加载完成
            for _ in range(60):
                await pilot.pause()
                if tree.root.children:
                    break
            assert tree.root.children, "目录树未加载子节点"

            sub_node = None
            file_node = None
            for child in tree.root.children:
                name = os.path.basename(str(child.data.path))
                if name == "sub" and child._allow_expand:
                    sub_node = child
                elif name == "top.txt" and not child._allow_expand:
                    file_node = child
            assert sub_node is not None, "未找到 sub 目录节点"
            assert file_node is not None, "未找到 top.txt 文件节点"

            rendered = tree.render_label(sub_node, Style(), Style())
            # 统计直接子项（3 个文件 + 1 个子目录 = 4），不递归
            assert "  (4)" in rendered.plain, "目录子项数量不正确: %r" % rendered.plain
            # 数量部分使用灰色样式（有效灰色 #808080），与文件名区分
            assert any("808080" in str(s.style) for s in rendered.spans), \
                "数量未使用灰色样式: %r" % rendered.spans
            # 普通文件节点不应附加数量
            file_rendered = tree.render_label(file_node, Style(), Style())
            assert "  (" not in file_rendered.plain, \
                "文件节点不应附加数量: %r" % file_rendered.plain


async def test_filename_completion():
    # 命令输入框支持文件名/目录名补全（任意参数位置），Tab 接受
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "subdir"))
        open(os.path.join(tmp, "hello_world.txt"), "w").close()
        open(os.path.join(tmp, "subdir", "inner.txt"), "w").close()
        app = DuckShellApp(start_path=tmp, max_lines=500)
        async with app.run_test() as pilot:
            inp = app.query_one("#cmdline")
            inp.focus()
            await pilot.pause()

            # 1) 参数位置的文件名补全
            inp.value = "cat he"
            inp.cursor_position = len(inp.value)
            ok = await _wait_for(
                pilot,
                lambda: inp._suggestion == "cat hello_world.txt",
                times=50,
            )
            assert ok, "未产生文件名补全: %r" % inp._suggestion
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "cat hello_world.txt", inp.value

            # 2) 目录补全：末尾补平台分隔符，便于继续下钻
            inp.value = "cat sub"
            inp.cursor_position = len(inp.value)
            ok = await _wait_for(
                pilot,
                lambda: inp._suggestion == "cat subdir" + os.sep,
                times=50,
            )
            assert ok, "未产生目录补全: %r" % inp._suggestion
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "cat subdir" + os.sep, inp.value

            # 3) 已进入子目录后继续补全内部文件
            inp.value = "cat " + "subdir" + os.sep + "in"
            inp.cursor_position = len(inp.value)
            ok = await _wait_for(
                pilot,
                lambda: inp._suggestion == "cat subdir" + os.sep + "inner.txt",
                times=50,
            )
            assert ok, "子目录内文件名补全失败: %r" % inp._suggestion
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "cat subdir" + os.sep + "inner.txt", inp.value


if __name__ == "__main__":
    _run(test_startup_and_echo)
    _run(test_cd_changes_cwd_and_tree)
    _run(test_up_via_button)
    _run(test_bookmark_dao)
    _run(test_fav_toggle_button)
    _run(test_bookmark_pick)
    _run(test_context_limit)
    _run(test_terminal_scrollable)
    _run(test_is_attach)
    _run(test_dir_child_file_count)
    _run(test_no_extra_blank_lines)
    _run(test_scroll_binding)
    _run(test_ansi_color)
    _run(test_subprocess_stdin_isolated)
    _run(test_nonzero_exit)
    _run(test_tab_completion)
    _run(test_filename_completion)
    _run(test_history_navigation)
    sys.exit(1 if FAILED else 0)
