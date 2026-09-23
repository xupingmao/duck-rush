# -*- coding: utf-8 -*-
'''
duck-video-resize - 视频分辨率转换 (调用 ffmpeg, 把高分辨率视频压成低分辨率)

ffmpeg 路径通过 duck-config 配置 (推荐全局配置一次即可):
    duck-config set ffmpeg_path "C:/tools/ffmpeg/bin/ffmpeg.exe" --global
    duck-config set ffprobe_path "C:/tools/ffmpeg/bin/ffprobe.exe" --global   # 可选
    duck-video-resize --set-ffmpeg "C:/tools/ffmpeg/bin/ffmpeg.exe"           # 等价的快捷方式

用法:
    duck-video-resize <路径...> [选项]

示例:
    duck-video-resize a.mp4 --height 720                 # 按高度缩放到 720p
    duck-video-resize a.mp4 -p 480p                      # 用预设 (2160p/1440p/1080p/720p/480p/360p)
    duck-video-resize a.mp4 -s 1280x720                  # 同时指定宽高
    duck-video-resize a.mp4 --width 1280                 # 只指定宽度, 高度按比例
    duck-video-resize ~/Videos -r -p 720p -o ./out       # 递归处理目录下的所有视频
    duck-video-resize a.mp4 -p 720p --dry-run            # 只打印 ffmpeg 命令, 不执行
    duck-video-resize a.mp4 -p 720p --encoder libx265    # 用 H.265 编码

说明:
    - ffmpeg 路径优先级: --ffmpeg > 配置 ffmpeg_path > PATH 中的 ffmpeg
    - 输出默认写在源文件同目录, 文件名加后缀 (默认 _{目标高度}p, 如 a_720p.mp4)
    - 源分辨率已低于目标时默认跳过 (避免放大变模糊), 需要放大加 --allow-upscale
    - 只指定宽或高时另一边按比例自动计算, 并向下取偶数 (H.264/H.265 要求偶数值)
    - 音频默认直接拷贝不重编码, 需要重编码用 --audio 指定编码器 (如 aac)
'''
import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

try:
    from duck_utils import config_util, os_util
except ImportError:
    sys.stderr.write("无法导入 duck_utils 模块, 请先执行 `python install.py` 安装后重试。\n")
    sys.exit(1)

from termcolor import colored

FFMPEG_KEY = "ffmpeg_path"
FFPROBE_KEY = "ffprobe_path"

# 预设名 -> 目标高度
PRESETS: Dict[str, int] = {
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}

VIDEO_EXTS: Set[str] = {
    ".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".webm", ".m4v",
    ".mpg", ".mpeg", ".ts", ".3gp", ".rmvb", ".vob",
}

# 支持 -movflags +faststart 的容器 (其它容器加该参数会报错)
FASTSTART_EXTS: Set[str] = {".mp4", ".m4v", ".mov"}


@dataclass
class ResizeOptions:
    """一次转换所需的全部参数"""
    ffmpeg: str
    ffprobe: Optional[str]
    width: Optional[int]
    height: Optional[int]
    encoder: str
    crf: str
    speed: str
    audio: str
    out_dir: Optional[str]
    suffix: Optional[str]
    ext: Optional[str]
    overwrite: bool
    dry_run: bool
    quiet: bool
    allow_upscale: bool


def resolve_ffmpeg(cli_path: Optional[str] = None) -> str:
    """确定 ffmpeg 可执行文件路径

    优先级: --ffmpeg 参数 > 配置 ffmpeg_path > PATH 中的 ffmpeg。
    找不到时打印配置指引并以退出码 1 结束。
    """
    candidates: List[str] = []
    if cli_path:
        candidates.append(cli_path)
    conf_value = config_util.get_value(FFMPEG_KEY)
    if isinstance(conf_value, str) and conf_value.strip():
        candidates.append(conf_value.strip())

    for path in candidates:
        if os.path.isfile(path):
            return path
        sys.stderr.write("ffmpeg 路径无效(文件不存在): %s\n" % path)

    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path

    sys.stderr.write("未找到 ffmpeg, 请先配置路径, 任选一种方式:\n")
    sys.stderr.write('  duck-config set ffmpeg_path "C:/tools/ffmpeg/bin/ffmpeg.exe" --global\n')
    sys.stderr.write('  duck-video-resize --set-ffmpeg "C:/tools/ffmpeg/bin/ffmpeg.exe"\n')
    sys.stderr.write("  或在运行本命令时加 --ffmpeg <路径>\n")
    sys.exit(1)


def resolve_ffprobe(ffmpeg_path: str) -> Optional[str]:
    """确定 ffprobe 路径: 配置 ffprobe_path > ffmpeg 同目录 > PATH; 都没有则返回 None"""
    conf_value = config_util.get_value(FFPROBE_KEY)
    if isinstance(conf_value, str) and conf_value.strip() and os.path.isfile(conf_value.strip()):
        return conf_value.strip()

    exe_name = "ffprobe.exe" if os_util.is_windows() else "ffprobe"
    sibling = os.path.join(os.path.dirname(ffmpeg_path), exe_name)
    if os.path.isfile(sibling):
        return sibling

    return shutil.which("ffprobe")


def decode_text(data: bytes) -> str:
    """解码子进程输出: 优先 UTF-8, Windows 下回退到本地 ANSI 编码 (避免中文报错乱码)"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        if os_util.is_windows():
            return data.decode("mbcs", errors="replace")
        return data.decode("utf-8", errors="replace")


def parse_size(text: str) -> Tuple[Optional[int], Optional[int]]:
    """解析分辨率文本, 支持 `1280x720` / `1280X720` / `1280*720` / 单边 `720`"""
    lower = text.strip().lower().replace("*", "x")
    if "x" not in lower:
        value = int(lower)
        return None, value
    w_text, h_text = lower.split("x", 1)
    return int(w_text), int(h_text)


def build_scale_filter(width: Optional[int], height: Optional[int]) -> str:
    """生成 scale 滤镜表达式, 未指定的一边按比例自动取偶数"""
    if width and height:
        return "scale=%d:%d" % (width, height)
    if width:
        return "scale=%d:-2" % width
    assert height is not None, "宽高不能同时为空"
    return "scale=-2:%d" % height


def probe_size(ffprobe: Optional[str], path: str) -> Optional[Tuple[int, int]]:
    """用 ffprobe 读取视频宽高; 没有 ffprobe 或解析失败时返回 None"""
    if not ffprobe:
        return None
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", path,
    ]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    text = decode_text(proc.stdout).strip().splitlines()
    if not text:
        return None
    parts = text[0].split(",")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def need_skip(opts: ResizeOptions, src: str) -> bool:
    """源分辨率已不高于目标时返回 True (避免放大), 探测不到源分辨率时不跳过"""
    if opts.allow_upscale:
        return False
    size = probe_size(opts.ffprobe, src)
    if size is None:
        return False
    src_w, src_h = size
    if opts.height and src_h <= opts.height:
        return True
    if opts.width and src_w <= opts.width:
        return True
    return False


def build_output_path(src: str, opts: ResizeOptions) -> str:
    """计算输出文件路径"""
    base, old_ext = os.path.splitext(src)
    ext = opts.ext if opts.ext else old_ext
    if ext and not ext.startswith("."):
        ext = "." + ext

    if opts.suffix is not None:
        suffix = opts.suffix
    elif opts.height:
        suffix = "_%dp" % opts.height
    else:
        suffix = "_resized"

    name = os.path.basename(base) + suffix + ext
    out_dir = opts.out_dir if opts.out_dir else os.path.dirname(src)
    return os.path.join(out_dir, name)


def build_ffmpeg_cmd(src: str, dest: str, opts: ResizeOptions) -> List[str]:
    """拼接 ffmpeg 命令行"""
    cmd = [opts.ffmpeg]
    cmd.append("-y" if opts.overwrite else "-n")
    if not opts.quiet:
        cmd.append("-hide_banner")
    cmd += ["-i", src]
    cmd += ["-vf", build_scale_filter(opts.width, opts.height)]
    cmd += ["-c:v", opts.encoder, "-crf", opts.crf, "-preset", opts.speed]
    cmd += ["-c:a", opts.audio]
    if os.path.splitext(dest)[1].lower() in FASTSTART_EXTS:
        cmd += ["-movflags", "+faststart"]
    cmd.append(dest)
    return cmd


def resize_one(src: str, opts: ResizeOptions) -> str:
    """转换单个文件, 返回状态: ok / skip / fail / dry-run"""
    dest = build_output_path(src, opts)
    if os.path.abspath(dest) == os.path.abspath(src):
        sys.stderr.write("输出路径与源文件相同, 请换一个后缀或输出目录: %s\n" % src)
        return "fail"

    size_text = ""
    size = probe_size(opts.ffprobe, src)
    if size is not None:
        size_text = " (%dx%d)" % (size[0], size[1])

    if need_skip(opts, src):
        print("%s %s%s 源分辨率不高于目标, 跳过 (需放大加 --allow-upscale)"
              % (colored("[skip]", "yellow"), src, size_text))
        return "skip"

    cmd = build_ffmpeg_cmd(src, dest, opts)
    if opts.dry_run:
        print(colored("[dry-run]", "cyan"), " ".join(shlex.quote(c) for c in cmd))
        return "dry-run"

    out_dir = os.path.dirname(dest)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        if opts.quiet:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            stderr_text = decode_text(proc.stderr)
        else:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL)
            stderr_text = ""
    except OSError as ex:
        sys.stderr.write("执行 ffmpeg 失败: %s\n" % ex)
        return "fail"

    if proc.returncode != 0:
        sys.stderr.write("%s %s -> %s\n" % (colored("[fail]", "red"), src, dest))
        if stderr_text:
            sys.stderr.write(stderr_text.strip()[-2000:] + "\n")
        return "fail"

    if not os.path.isfile(dest):
        sys.stderr.write("%s %s ffmpeg 返回成功但没有生成输出文件: %s\n"
                         % (colored("[fail]", "red"), src, dest))
        return "fail"

    src_size = os.path.getsize(src)
    dest_size = os.path.getsize(dest) if os.path.exists(dest) else 0
    ratio = (dest_size * 100.0 / src_size) if src_size else 0.0
    print("%s %s%s -> %s (%s -> %s, %.0f%%)"
          % (colored("[ok]", "green"), src, size_text, dest,
             format_size(src_size), format_size(dest_size), ratio))
    return "ok"


def format_size(num: int) -> str:
    """把字节数格式化成易读文本"""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "%.1f%s" % (value, unit) if unit != "B" else "%d%s" % (int(value), unit)
        value /= 1024.0
    return "%.1fGB" % value


def collect_inputs(paths: List[str], recursive: bool) -> List[str]:
    """把命令行路径展开成视频文件列表 (目录会扫描其中的视频文件)"""
    result: List[str] = []
    for path in paths:
        if os.path.isfile(path):
            result.append(path)
            continue
        if not os.path.isdir(path):
            sys.stderr.write("路径不存在: %s\n" % path)
            continue
        if recursive:
            for root, _dirs, files in os.walk(path):
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                        result.append(os.path.join(root, name))
        else:
            for name in sorted(os.listdir(path)):
                child = os.path.join(path, name)
                if os.path.isfile(child) and os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                    result.append(child)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duck-video-resize",
        description="视频分辨率转换: 调用 ffmpeg 把高分辨率视频压成低分辨率",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="视频文件或目录 (目录会扫描其中的视频文件)")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-p", "--preset", choices=sorted(PRESETS.keys(), key=lambda k: -PRESETS[k]),
                       help="分辨率预设: %(choices)s (按高度缩放)")
    group.add_argument("-s", "--size", metavar="WxH",
                       help="目标分辨率, 如 1280x720; 只写一个数字视为高度")
    group.add_argument("--height", type=int, metavar="H", help="目标高度, 宽度按比例")
    group.add_argument("--width", type=int, metavar="W", help="目标宽度, 高度按比例")

    parser.add_argument("-o", "--out-dir", help="输出目录, 默认与源文件同目录")
    parser.add_argument("--suffix", help="输出文件名后缀, 默认 _{目标高度}p")
    parser.add_argument("--ext", help="输出扩展名, 默认沿用源文件扩展名")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归扫描目录下的视频")
    parser.add_argument("--encoder", default="libx264", help="视频编码器, 默认 %(default)s")
    parser.add_argument("--crf", default="23", help="画质因子 (越小越清晰), 默认 %(default)s")
    parser.add_argument("--speed", default="medium",
                        help="ffmpeg preset 编码速度: ultrafast..veryslow, 默认 %(default)s")
    parser.add_argument("--audio", default="copy", help="音频处理方式, 默认 %(default)s (不重编码)")
    parser.add_argument("-y", "--overwrite", action="store_true", help="输出文件已存在时覆盖")
    parser.add_argument("--allow-upscale", action="store_true", help="允许放大 (默认跳过低分辨率源)")
    parser.add_argument("--dry-run", action="store_true", help="只打印 ffmpeg 命令, 不执行")
    parser.add_argument("-q", "--quiet", action="store_true", help="不打印 ffmpeg 的实时输出")
    parser.add_argument("--ffmpeg", help="临时指定 ffmpeg 路径, 覆盖配置值")
    parser.add_argument("--set-ffmpeg", metavar="PATH",
                        help="把 ffmpeg 路径写入全局配置 (等价 duck-config set ffmpeg_path --global)")
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.set_ffmpeg:
        path = args.set_ffmpeg
        if not os.path.isfile(path):
            sys.stderr.write("ffmpeg 路径无效(文件不存在): %s\n" % path)
            sys.exit(1)
        config_util.set_value(FFMPEG_KEY, path, config_util.SCOPE_GLOBAL)
        print("已写入全局配置 %s = %s (%s)" % (
            FFMPEG_KEY, path, config_util.get_global_path()))
        return

    if not args.paths:
        parser.print_help()
        return

    width: Optional[int] = None
    height: Optional[int] = None
    if args.preset:
        height = PRESETS[args.preset]
    elif args.size:
        width, height = parse_size(args.size)
    elif args.height:
        height = args.height
    elif args.width:
        width = args.width
    else:
        sys.stderr.write("请指定目标分辨率: -p 720p / -s 1280x720 / --height 720 / --width 1280\n")
        sys.exit(1)

    if width is not None and width <= 0:
        sys.stderr.write("宽度必须为正整数: %s\n" % width)
        sys.exit(1)
    if height is not None and height <= 0:
        sys.stderr.write("高度必须为正整数: %s\n" % height)
        sys.exit(1)

    ffmpeg_path = resolve_ffmpeg(args.ffmpeg)
    opts = ResizeOptions(
        ffmpeg=ffmpeg_path,
        ffprobe=resolve_ffprobe(ffmpeg_path),
        width=width,
        height=height,
        encoder=args.encoder,
        crf=args.crf,
        speed=args.speed,
        audio=args.audio,
        out_dir=args.out_dir,
        suffix=args.suffix,
        ext=args.ext,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        quiet=args.quiet,
        allow_upscale=args.allow_upscale,
    )

    inputs = collect_inputs(args.paths, args.recursive)
    if not inputs:
        sys.stderr.write("没有找到可处理的视频文件\n")
        sys.exit(1)

    counter: Dict[str, int] = {"ok": 0, "skip": 0, "fail": 0, "dry-run": 0}
    for src in inputs:
        counter[resize_one(src, opts)] += 1

    print("完成: 共 %d 个, 成功 %s, 跳过 %s, 失败 %s%s" % (
        len(inputs), colored(str(counter["ok"]), "green"),
        colored(str(counter["skip"]), "yellow"),
        colored(str(counter["fail"]), "red"),
        ", 待执行 %d" % counter["dry-run"] if counter["dry-run"] else ""))

    if counter["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    # -h/--help 不得产生副作用, 直接打印用法后退出
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    main()
