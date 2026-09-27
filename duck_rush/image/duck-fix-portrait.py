"""duck-fix-portrait — 人像区域提亮 / 色彩平衡修正（支持多人）

针对"人像太暗、衣服一片死黑"的场景，仅对人像区域做：
  1) gamma 提暗部（保高光不过曝，把死黑衣物从 p25≈6 抬到 ~35）
  2) 轻微白平衡校正（原图偏暖，R↓ / B↑）
  3) 饱和度增强，让花色衣物/绿植更鲜活
背景区域保持不动（蒙版羽化过渡，避免硬边痕迹）。

人像定位（三种方式，自动优先）:
  * 默认：用 OpenCV 人脸检测自动框出所有人，为每人生成"头部椭圆 + 躯干梯形"
    蒙版并合并 —— 不限制人数，换图也能用
  * --regions "x1,y1,...;x2,y2,..."：手动用归一化多边形圈定每个人（分号分隔多人）
  * 无 cv2 且无 --regions 时：回退到内置的一对默认多边形（仅适配示例图）

默认行为：按多个 gamma 值各生成一张（不同亮度水平），并拼一张对比图，
方便直接挑最好的一张，无需手动调参。

EXIF：会自动按 Orientation 标签转正（避免像原图那样被旋转 90°）。

用法:
  duck-fix-portrait [input]                              # 自动多人 + 多亮度 + 对比拼图
  duck-fix-portrait [input] -o OUT.jpg --gamma 0.60      # 单张
  duck-fix-portrait [input] --regions "0.3,0.27,0.4,0.3,...;..."  # 手动多人
  duck-fix-portrait [input] --gammas 0.55,0.65,0.75
"""
import argparse
import os
import sys
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# 内置默认多边形（归一化坐标）仅用于"无 cv2 且未指定 --regions"的回退，
# 适配示例图（左男士、右女士）。一般场景请用自动检测或 --regions。
DEFAULT_POLYS = [
    [  # 男士
        (0.285, 0.29), (0.285, 0.33), (0.295, 0.42), (0.30, 0.55),
        (0.31, 0.62), (0.39, 0.62), (0.395, 0.55), (0.39, 0.42),
        (0.40, 0.31), (0.38, 0.25), (0.30, 0.27),
    ],
    [  # 女士
        (0.49, 0.29), (0.485, 0.33), (0.49, 0.45), (0.495, 0.55),
        (0.51, 0.63), (0.605, 0.63), (0.61, 0.58), (0.605, 0.45),
        (0.60, 0.32), (0.575, 0.265), (0.50, 0.27),
    ],
]

# 调色参数
DEFAULT_GAMMA = 0.65   # <1 提亮暗部、基本不动高光（单张模式用）
WB_R = 0.97            # 原图偏暖，R 略降
WB_B = 1.03            # B 略升
SAT_BOOST = 1.12       # 饱和度增强系数
FEATHER = 22           # 蒙版羽化半径(px)
DEFAULT_GAMMAS = [0.55, 0.65, 0.75]  # 多亮度版本默认扫描


def detect_faces(img: Image.Image) -> list:
    """OpenCV 正面人脸检测，返回 [(x, y, w, h), ...] 像素坐标（适配任意人数）。

    用 frontalface_alt2 + 较严的 minNeighbors 抑制误检，再按相对尺寸/长宽比过滤
    异常框。无 cv2 时返回 []（调用方回退到默认多边形或要求 --regions）。
    """
    try:
        import cv2  # type: ignore
    except ImportError:
        return []
    arr = np.asarray(img)[:, :, ::-1]  # RGB -> BGR
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    cascade = cv2.CascadeClassifier(  # type: ignore[attr-defined]
        cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"  # type: ignore[attr-defined]
    )
    found = cascade.detectMultiScale(
        gray, 1.1, 5, minSize=(int(h * 0.02), int(h * 0.02))
    )
    if found is None:
        return []
    faces = []
    for (x, y, bw, bh) in found:
        relh = bh / h
        # 尺寸合理性过滤：相对身高 1.5%~35%，长宽比 0.5~1.8，剔除绝大多数误检
        if relh < 0.015 or relh > 0.35:
            continue
        if bw / bh < 0.5 or bw / bh > 1.8:
            continue
        faces.append((int(x), int(y), int(bw), int(bh)))
    return faces


def parse_regions(s: str) -> list:
    """解析 --regions：分号分隔多人，每人逗号分隔的归一化坐标 x1,y1,x2,y2,..."""
    polys = []
    for poly_s in s.split(";"):
        nums = [float(v) for v in poly_s.split(",") if v.strip() != ""]
        if len(nums) < 6 or len(nums) % 2 != 0:
            raise ValueError(f"无效的多边形: {poly_s}")
        polys.append([(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)])
    return polys


def polygon_mask(w: int, h: int, polys: list, feather: int = FEATHER) -> np.ndarray:
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for poly in polys:
        pts = [(int(x * w), int(y * h)) for (x, y) in poly]
        d.polygon(pts, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(mask, dtype=np.float32) / 255.0


def faces_mask(w: int, h: int, faces: list, feather: int = FEATHER) -> np.ndarray:
    """为每个人生成 头部椭圆 + 躯干梯形 的蒙版并合并，适配任意人数。"""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for (x, y, fw, fh) in faces:
        cx = x + fw / 2
        # 头部椭圆（略大于检测框）
        d.ellipse([x - fw * 0.15, y - fh * 0.2, x + fw * 1.15, y + fh * 1.1], fill=255)
        # 躯干梯形：从脸下缘延伸到约 3.6 倍脸高，自上而下收窄近似身形
        topw, botw = fw * 1.5, fw * 0.9
        ty, by = y + fh * 0.7, y + fh * 3.6
        d.polygon(
            [(cx - topw / 2, ty), (cx + topw / 2, ty),
             (cx + botw / 2, by), (cx - botw / 2, by)],
            fill=255,
        )
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(mask, dtype=np.float32) / 255.0


def build_mask(w: int, h: int, polys: Optional[list] = None,
                faces: Optional[list] = None) -> np.ndarray:
    if polys:
        return polygon_mask(w, h, polys)
    if faces:
        return faces_mask(w, h, faces)
    return polygon_mask(w, h, DEFAULT_POLYS)


def adjust_region(rgb: np.ndarray, gamma: float) -> np.ndarray:
    """对人像区域(浮点 0-255)做 gamma + 白平衡 + 饱和增强。"""
    # 1) 白平衡
    wb = rgb.copy()
    wb[:, :, 0] *= WB_R
    wb[:, :, 2] *= WB_B
    wb = np.clip(wb, 0.0, 255.0)

    # 2) 每通道 gamma 提暗部
    norm = np.clip(wb / 255.0, 0.0, 1.0)
    g = np.power(norm, gamma)

    # 3) 饱和度增强
    lum = 0.2126 * g[:, :, 0] + 0.7152 * g[:, :, 1] + 0.0722 * g[:, :, 2]
    sat = g + (g - lum[..., None]) * (SAT_BOOST - 1.0)
    sat = np.clip(sat, 0.0, 1.0)
    return sat * 255.0


def lum_stats(arr: np.ndarray, mask: np.ndarray) -> str:
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    inside = lum[mask > 0.3]
    if inside.size == 0:
        return "蒙版内: (空)"
    return (f"蒙版内 lum mean={inside.mean():.1f} p25={np.percentile(inside,25):.1f} "
            f"p95={np.percentile(inside,95):.1f}")


def mask_bbox(mask: np.ndarray, pad_frac: float = 0.02) -> tuple:
    """从蒙版反推所有人像的外接框（归一化 pad），用于对比拼图裁剪。"""
    h, w = mask.shape
    ys, xs = np.where(mask > 0.3)
    if xs.size == 0:
        return (0, 0, w, h)
    x0 = max(0, int(xs.min() - w * pad_frac))
    x1 = min(w, int(xs.max() + w * pad_frac))
    y0 = max(0, int(ys.min() - h * pad_frac))
    y1 = min(h, int(ys.max() + h * pad_frac))
    return (x0, y0, x1, y1)


def fix_one(rgb: np.ndarray, mask: np.ndarray, gamma: float,
            strength: float) -> np.ndarray:
    adjusted = adjust_region(rgb, gamma)
    blended = rgb * (1 - strength * mask[..., None]) + adjusted * (strength * mask[..., None])
    return np.clip(blended, 0, 255).astype(np.uint8)


def make_contact_sheet(images: list, labels: list, box: tuple,
                        thumb_h: int = 600) -> Image.Image:
    crops = []
    for im in images:
        crop = im.crop(box)
        scale = thumb_h / crop.height
        crop = crop.resize((max(1, int(crop.width * scale)), thumb_h))
        crops.append(crop)
    gap = 12
    label_h = 36
    total_w = sum(c.width for c in crops) + gap * (len(crops) + 1)
    sheet = Image.new("RGB", (total_w, thumb_h + label_h), (30, 30, 30))
    x = gap
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for crop, label in zip(crops, labels):
        sheet.paste(crop, (x, label_h))
        d.text((x + 4, 8), label, fill=(235, 235, 235), font=font)
        x += crop.width + gap
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="duck-fix-portrait",
        description="人像区域提亮 + 色彩平衡修正（自动多人/手动 --regions；背景不动）",
    )
    parser.add_argument("input", nargs="?", default="data/input.jpg",
                        help="输入图片路径（默认 data/input.jpg）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出单张图片路径；不指定则进入多亮度版本模式")
    parser.add_argument("--gamma", type=float, default=DEFAULT_GAMMA,
                        help="单张模式下的 gamma（默认 %(default)s）")
    parser.add_argument("--gammas", default=",".join(str(g) for g in DEFAULT_GAMMAS),
                        help="多亮度版本扫描的 gamma 列表，逗号分隔（默认 %(default)s）")
    parser.add_argument("--strength", type=float, default=1.0,
                        help="调整强度 0~1（默认 1.0，0.5 更保守）")
    parser.add_argument("--regions", default=None,
                        help="手动多边形覆盖，归一化坐标；分号分隔多人，"
                             "如 '0.3,0.27,0.4,0.31,...;0.5,0.29,0.6,0.33,...'")
    parser.add_argument("--no-contact", action="store_true",
                        help="多亮度模式下不生成对比拼图")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[fix-portrait] 错误: 输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    # 读取并按 EXIF 转正（修复被旋转的问题）
    raw = Image.open(args.input)
    transposed = ImageOps.exif_transpose(raw)
    src: Image.Image = transposed if transposed is not None else raw
    src = src.convert("RGB")
    w, h = src.size
    rgb = np.asarray(src, dtype=np.float32)

    # 选择人像定位方式
    polys, faces = None, None
    if args.regions:
        polys = parse_regions(args.regions)
        print(f"[fix-portrait] 手动多边形: {len(polys)} 人")
    else:
        faces = detect_faces(src)
        if faces:
            print(f"[fix-portrait] 自动人脸检测: {len(faces)} 人")
        else:
            print("[fix-portrait] 未检测到人脸/无 cv2，回退到内置默认双人多边形")

    mask = build_mask(w, h, polys=polys, faces=faces)
    print(f"[fix-portrait] 输入: {args.input} ({w}x{h}, 已按 EXIF 转正)")

    if args.output:  # 单张模式
        out = fix_one(rgb, mask, args.gamma, args.strength)
        Image.fromarray(out, "RGB").save(args.output, quality=95)
        print(f"[fix-portrait] 输出: {args.output} (gamma={args.gamma})")
        print(f"[fix-portrait] 校验(原图): {lum_stats(rgb, mask)}")
        print(f"[fix-portrait] 校验(结果): {lum_stats(out, mask)}")
        return

    # 多亮度版本模式
    gammas = [float(x) for x in args.gammas.split(",") if x.strip()]
    base = os.path.splitext(args.input)[0]
    out_paths, out_images = [], []
    for g in gammas:
        out = fix_one(rgb, mask, g, args.strength)
        im = Image.fromarray(out, "RGB")
        path = f"{base}_adjusted_g{g:.2f}.jpg"
        im.save(path, quality=95)
        out_paths.append(path)
        out_images.append(im)
        print(f"[fix-portrait] 生成: {path}  {lum_stats(out, mask)}")
    print(f"[fix-portrait] 校验(原图): {lum_stats(rgb, mask)}")

    if not args.no_contact:
        box = mask_bbox(mask)
        sheet = make_contact_sheet(out_images, [f"g={g:.2f}" for g in gammas], box)
        sheet_path = f"{base}_adjusted_contact.jpg"
        sheet.save(sheet_path, quality=92)
        print(f"[fix-portrait] 对比拼图: {sheet_path}")


if __name__ == "__main__":
    main()
