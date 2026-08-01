# -*- coding: utf-8 -*-
# @author xupingmao
# @since 2026/08/01
# @filename duck-translate.py
# @description 调用本地 Ollama 大模型, 从标准输入(或文件)读取文本并翻译后输出到标准输出

import argparse
import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

# 缺省模型: 仅当本地未安装任何模型时作为回退提示用; 实际运行时会优先选用已安装模型
_MODEL_DEFAULT = "gemma4:e4b"

# 用于粗略判断输入是否含中日韩汉字 / 拉丁字母
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _win_console_cp(kind: str) -> Optional[str]:
    """返回 Windows 控制台(输入/输出)代码页对应的 Python 编码名。

    直接读取控制台真实代码页, 避免硬编码 UTF-8 导致中文在 GBK 控制台变成 ? 或乱码。
    kind 为 "in" 取输入代码页, "out" 取输出代码页。无控制台时返回 None。
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        if kind == "out":
            cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        else:
            cp = ctypes.windll.kernel32.GetConsoleCP()
    except Exception:
        return None
    if not cp:
        return None
    if cp == 65001:
        return "utf-8"
    return "cp%d" % cp


def _can_encode(enc: Optional[str]) -> bool:
    """判断给定编码能否编码中文(用于决定是否覆盖默认编码)。"""
    if not enc:
        return False
    try:
        "中文测试".encode(enc)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def setup_io() -> None:
    """配置 stdin/stdout 编码, 保证中文正确显示与读取, 且不破坏已有终端。

    - 若 Python 当前默认编码已能正确处理中文(如 Git Bash 的 UTF-8、中文控制台的 cp936),
      则保持原样, 避免把 UTF-8 终端降级为 GBK 导致乱码。
    - 仅当默认编码无法表示中文(如 cp1252 控制台)时, 才按控制台真实代码页覆盖,
      输出用控制台输出代码页(如 cp936), 输入用控制台输入代码页(与管道来源一致)。
    - 统一 errors="replace", 避免个别无法编码的字符令程序崩溃。
    """
    cur = getattr(sys.stdout, "encoding", None)
    if _can_encode(cur):
        return

    if sys.platform == "win32":
        out_enc = _win_console_cp("out") or "utf-8"
        in_enc = _win_console_cp("in") or "utf-8"
    else:
        out_enc = in_enc = "utf-8"

    out_re = getattr(sys.stdout, "reconfigure", None)
    if callable(out_re):
        out_re(encoding=out_enc, errors="replace")
    in_re = getattr(sys.stdin, "reconfigure", None)
    if callable(in_re):
        in_re(encoding=in_enc, errors="replace")


def detect_source_lang(text: str) -> str:
    """粗略判断输入主体语言: 含中日韩汉字视为 Chinese, 仅拉丁字母视为 English, 否则 auto。"""
    has_cjk = bool(_CJK_RE.search(text))
    has_latin = bool(_LATIN_RE.search(text))
    if has_cjk and not has_latin:
        return "Chinese"
    if has_latin and not has_cjk:
        return "English"
    if has_cjk:  # 中英混合时, 默认按中文处理(翻译为英文)
        return "Chinese"
    return "auto"


def decide_langs(text: str, target_arg: Optional[str],
                 source_arg: str) -> Tuple[str, str]:
    """根据输入与目标参数决定 (源语言, 目标语言)。

    - 源语言: 用户显式指定(--from)则用指定值, 否则按输入自动检测
    - 目标语言: 用户显式指定(位置参数)则用指定值, 否则与源语言相反(中->英, 英->中)
    """
    detected = detect_source_lang(text)
    source = source_arg if source_arg != "auto" else detected
    if source == "auto":
        source = detected

    if target_arg is not None:
        target = target_arg
    elif source == "Chinese":
        target = "English"
    elif source == "English":
        target = "中文"
    else:
        target = "English"
    return source, target


def list_installed_models(ollama_url: str) -> Optional[List[str]]:
    """查询本地已安装模型。连接失败(服务未启动)返回 None, 否则返回模型名列表。"""
    url = ollama_url.rstrip("/") + "/api/tags"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        return [m.get("name", "") for m in models if isinstance(m, dict)]
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return None


def resolve_model(requested: str, installed: List[str]) -> Tuple[str, bool]:
    """在已安装模型中确定要使用的模型。返回 (模型名, 是否发生了回退)。"""
    if requested in installed:
        return requested, False

    # 前缀匹配: 用户写 qwen2.5, 本地已安装 qwen2.5:7b 时直接采用
    base = requested.split(":", 1)[0]
    for name in installed:
        if name == base or name.startswith(base + ":"):
            return name, requested != name

    # 未找到: 从已安装模型中挑选一个(优先非 coder/code 类模型)
    def _rank(name: str) -> Tuple[int, str]:
        lowered = name.lower()
        penalty = 1 if ("coder" in lowered or "code" in lowered) else 0
        return penalty, name

    preferred = sorted(installed, key=_rank)
    return preferred[0], True


def build_prompt(text: str, target: str, source: str, auto: bool = False) -> str:
    """构造翻译提示词, 要求模型只输出译文本身。

    auto=True 时(用户未指定目标语言且未指定源语言), 由模型自行判断输入是中文还是英文,
    并翻译到另一语言; 否则按显式指定的 source/target 方向翻译。
    """
    if auto:
        return (
            "You are a professional translator. "
            "First detect the source language of the text below. "
            "If it is Chinese, translate it into English; "
            "if it is English, translate it into Chinese. "
            "Output ONLY the translated text without any explanation, "
            "comment, or markdown code fence.\n\n"
            f"{text}"
        )
    src_desc = "auto-detect" if source == "auto" else source
    return (
        f"You are a professional translator. "
        f"Translate the following text from {src_desc} into {target}. "
        f"Output ONLY the translated text without any explanation, "
        f"comment, or markdown code fence.\n\n"
        f"{text}"
    )


def _post_generate(payload: bytes, url: str) -> "http.client.HTTPResponse":
    """向 Ollama /api/generate 发起 POST, 返回响应对象。"""
    req = urllib.request.Request(
        url.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req)


def _translate_stream(text: str, model: str, target: str, source: str,
                      ollama_url: str, think: bool, auto: bool) -> bool:
    """流式翻译: 逐 token 直接写到 stdout。成功返回 True, 失败返回 False。"""
    prompt = build_prompt(text, target, source, auto)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
        "think": think,
    }).encode("utf-8")
    try:
        with _post_generate(payload, ollama_url) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = obj.get("response", "")
                if isinstance(piece, str):
                    sys.stdout.write(piece)
                    sys.stdout.flush()
                if obj.get("done"):
                    break
        sys.stdout.write("\n")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.stderr.write(
                f"模型 {model} 未找到。请用 `ollama list` 查看可用模型"
                f"或 `ollama pull {model}` 拉取。\n")
        else:
            sys.stderr.write(f"Ollama HTTP 错误 {e.code}: {e.reason}\n")
    except urllib.error.URLError as e:
        sys.stderr.write(f"无法连接 Ollama ({ollama_url}): {e.reason}\n")
    return False


def _translate_once(text: str, model: str, target: str, source: str,
                    ollama_url: str, think: bool, auto: bool) -> Optional[str]:
    """非流式翻译: 返回完整译文; 出错时返回 None。"""
    prompt = build_prompt(text, target, source, auto)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": think,
    }).encode("utf-8")
    try:
        with _post_generate(payload, ollama_url) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = data.get("response", "")
        return result if isinstance(result, str) else ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.stderr.write(
                f"模型 {model} 未找到。请用 `ollama list` 查看可用模型"
                f"或 `ollama pull {model}` 拉取。\n")
        else:
            sys.stderr.write(f"Ollama HTTP 错误 {e.code}: {e.reason}\n")
    except urllib.error.URLError as e:
        sys.stderr.write(f"无法连接 Ollama ({ollama_url}): {e.reason}\n")
    return None


def _read_stdin_bytes() -> bytes:
    """以字节形式读取标准输入, 避免文本模式编码猜测出错。"""
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        return buf.read()
    return sys.stdin.read().encode("utf-8", errors="replace")


def _read_file_bytes(path: str) -> bytes:
    """以字节形式读取文件。"""
    try:
        with open(path, "rb") as fp:
            return fp.read()
    except OSError as e:
        sys.stderr.write(f"无法读取文件 {path}: {e}\n")
        sys.exit(1)


def _decode_bytes(raw: bytes) -> str:
    """把输入字节解码为文本。

    现代 PowerShell / 终端管道多使用 UTF-8, 传统 cmd 控制台使用 GBK(cp936)。
    优先按 UTF-8(严格)解码, 失败再按控制台输入代码页, 最后宽松回退,
    以保证 `echo 中文 | duck-translate` 这类管道输入能被正确读取。
    """
    if not raw:
        return ""
    candidates = ["utf-8"]
    if sys.platform == "win32":
        cp = _win_console_cp("in")
        if cp and cp != "utf-8":
            candidates.append(cp)
    for enc in candidates:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="调用本地 Ollama 大模型翻译文本。"
                    "文本可直接作为参数传入, 或用 --file 读文件, "
                    "或经标准输入管道传入; 译文输出到标准输出。"
                    "未指定目标语言时由模型自动判断中译英/英译中。"
                    "默认开启流式输出(可用 --no-stream 关闭)。")
    parser.add_argument("--target", type=str, default=None,
                        help="目标语言, 如 en / English / 中文。"
                             "缺省时由模型自动判断方向")
    parser.add_argument("text", type=str, nargs="?", default=None,
                        help="待翻译的文本(直接作为参数传入)")
    parser.add_argument("--file", type=str, default="",
                        help="输入文件路径; 与位置文本互斥, 缺省且无位置文本时读标准输入")
    parser.add_argument("-m", "--model", type=str, default=_MODEL_DEFAULT,
                        help=f"Ollama 模型名 (缺省 {_MODEL_DEFAULT}, "
                             f"本地未安装时自动选用已安装模型)")
    parser.add_argument("--from", dest="source", type=str, default="auto",
                        help="源语言, 缺省 auto 自动检测")
    parser.add_argument("-u", "--ollama-url", type=str,
                        default="http://localhost:11434",
                        help="Ollama 服务地址 (缺省 http://localhost:11434)")
    parser.add_argument("--no-stream", dest="stream", action="store_false",
                        help="关闭流式输出(默认开启, 逐 token 显示)")
    parser.add_argument("-t", "--think", action="store_true",
                        help="开启思考/think 模式(默认关闭, 部分模型支持)")
    parser.add_argument("--debug", action="store_true",
                        help="调试模式: 将调用 Ollama 的参数(URL/模型/提示词等)打印到 stderr")
    args: argparse.Namespace = parser.parse_args()

    # 按控制台真实代码页配置 stdin/stdout, 避免中文在 GBK 控制台乱码/变成 ?
    setup_io()

    if args.text is not None:
        text = args.text
    elif args.file:
        text = _decode_bytes(_read_file_bytes(args.file))
    else:
        text = _decode_bytes(_read_stdin_bytes())
    if text.strip() == "":
        return

    auto_mode = args.target is None and args.source == "auto"
    if auto_mode:
        source = target = ""
    else:
        source, target = decide_langs(text, args.target, args.source)

    installed = list_installed_models(args.ollama_url)
    if installed is None:
        sys.stderr.write(
            f"无法连接 Ollama 服务 ({args.ollama_url})。\n"
            f"请先启动 Ollama: 运行 `ollama serve` 或打开 Ollama 桌面应用,"
            f" 确认服务可访问后再重试。\n")
        sys.exit(1)
    if not installed:
        sys.stderr.write(
            "本地未安装任何 Ollama 模型。请先拉取模型, "
            "例如: ollama pull qwen2.5:7b\n")
        sys.exit(1)

    user_specified_model = args.model != _MODEL_DEFAULT
    model, fallback = resolve_model(args.model, installed)
    if fallback and user_specified_model:
        sys.stderr.write(
            f"模型 {args.model} 未安装, 已改用本地已安装模型: {model}\n")

    if args.debug:
        prompt = build_prompt(text, target, source, auto_mode)
        fb = f" (回退自 {args.model})" if fallback else ""
        sys.stderr.write(
            "[debug] Ollama URL : %s\n"
            "[debug] Model      : %s%s\n"
            "[debug] Stream     : %s\n"
            "[debug] Think      : %s\n"
            "[debug] Auto dir   : %s\n"
            "[debug] Source     : %s\n"
            "[debug] Target     : %s\n"
            "[debug] Prompt     :\n%s\n"
            % (args.ollama_url, model, fb, args.stream,
               args.think, auto_mode, source, target, prompt)
        )

    if args.stream:
        ok = _translate_stream(
            text, model, target, source, args.ollama_url, args.think, auto_mode)
        if not ok:
            sys.exit(1)
    else:
        result = _translate_once(
            text, model, target, source, args.ollama_url, args.think, auto_mode)
        if result is None:
            sys.exit(1)
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
