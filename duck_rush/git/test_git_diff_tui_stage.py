# -*- coding: utf-8 -*-
"""Headless smoke test: stage a file, verify it stays in the list with updated status."""
import asyncio
import os
import tempfile
import shutil
import subprocess
import sys
from textual.widgets import Label

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402

def _load_mod():
    path = os.path.join(HERE, "duck-git-diff-tui.py")
    spec = importlib.util.spec_from_file_location("duck_git_diff_tui_mod", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod

_mod = _load_mod()
GitDiffTUI = _mod.GitDiffTUI
build_context = _mod.build_context
parse_args = _mod.parse_args
emoji_supported = _mod.emoji_supported


def git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=cwd, check=True,
                   encoding="utf-8", errors="replace",
                   capture_output=True)


def setup_repo():
    d = tempfile.mkdtemp(prefix="gdt-test-")
    git(d, "init")
    git(d, "config", "user.email", "t@t.com")
    git(d, "config", "user.name", "t")
    with open(os.path.join(d, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    git(d, "add", "a.txt")
    git(d, "commit", "-m", "init")
    # unstaged modification
    with open(os.path.join(d, "a.txt"), "a", encoding="utf-8") as fh:
        fh.write("world\n")
    return d


async def run():
    d = setup_repo()
    os.chdir(d)
    try:
        ctx = build_context(parse_args([]))
        app = GitDiffTUI(ctx)
        async with app.run_test() as pilot:
            await pilot.pause()
            # before staging: 1 file, unstaged, status 'M'
            assert len(app.files) == 1, "expected 1 file, got %d" % len(app.files)
            f0 = app.files[0]
            assert f0.path == "a.txt", f0.path
            assert f0.status == "M", f0.status
            assert f0.staged is False, "should not be staged yet"
            mark = "✔" if emoji_supported() else "*"
            label_before = app._item_text(f0).plain
            assert mark not in label_before and "staged" not in label_before, \
                "unstaged label should have no marker: %r" % label_before
            print("[ok] before stage: %s status=%s staged=%s label=%r"
                  % (f0.path, f0.status, f0.staged, label_before))

            # stage it
            await pilot.press("s")
            await pilot.pause()

            # file must remain in the list
            assert len(app.files) == 1, "file disappeared after stage! got %d" % len(app.files)
            f1 = app.files[0]
            assert f1.path == "a.txt"
            assert f1.staged is True, "staged flag not updated in place"
            assert f1.status == "M", f1.status
            # the list label must now show the staged marker (visible change)
            label_txt = app._item_text(f1).plain
            assert mark in label_txt and "staged" in label_txt, \
                "label did not reflect staged state: %r" % label_txt
            print("[ok] after stage: %s status=%s staged=%s (kept in list, label=%r)"
                  % (f1.path, f1.status, f1.staged, label_txt))

            # verify git state agrees
            out = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=d,
                                 encoding="utf-8", errors="replace",
                                 capture_output=True).stdout.strip()
            assert "a.txt" in out, "git says not staged: %r" % out
            print("[ok] git confirms a.txt is staged")

            # unstage again -> stays in list, staged=False
            await pilot.press("u")
            await pilot.pause()
            assert len(app.files) == 1, "file disappeared after unstage! got %d" % len(app.files)
            f2 = app.files[0]
            assert f2.staged is False, "unstage did not clear staged flag"
            print("[ok] after unstage: staged=%s (kept in list)" % f2.staged)
        print("\nSCENARIO 1 PASSED")
    finally:
        os.chdir(HERE)
        shutil.rmtree(d, ignore_errors=True)


async def run_reopen():
    """Bug regression: a file staged BEFORE launching must still appear
    in the default (unstaged) view, not vanish from the list."""
    d = setup_repo()
    os.chdir(d)
    try:
        # stage a.txt up-front, then close & reopen the tool
        git(d, "add", "a.txt")
        ctx = build_context(parse_args([]))
        app = GitDiffTUI(ctx)
        async with app.run_test() as pilot:
            await pilot.pause()
            paths = [f.path for f in app.files]
            assert "a.txt" in paths, "staged file missing on reopen: %r" % paths
            f = next(x for x in app.files if x.path == "a.txt")
            assert f.staged is True, "staged file should be flagged staged on reopen"
            print("[ok] reopen: a.txt present, staged=%s (did not disappear)" % f.staged)
        print("\nSCENARIO 2 PASSED")
    finally:
        os.chdir(HERE)
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run())
    asyncio.run(run_reopen())



if __name__ == "__main__":
    asyncio.run(run())
