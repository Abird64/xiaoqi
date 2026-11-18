"""生成小栖步数的启动图标（无第三方设计工具，Pillow 直接绘制）。

用法：
  python tools/generate_icons.py

输出到 app/src/main/res/mipmap-*/ic_launcher(.round).png。
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app" / "src" / "main" / "res"

SIZE = 512
BG_TOP = (27, 37, 48)
BG_BOTTOM = (14, 19, 25)
TRACK = (39, 49, 61)
GREEN = (139, 217, 123)
GREEN_DEEP = (95, 168, 90)
TEXT = (241, 245, 247)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def circle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    return mask


def draw_icon(round_icon: bool) -> Image.Image:
    # 背景渐变
    bg = Image.new("RGB", (SIZE, SIZE))
    draw_bg = ImageDraw.Draw(bg)
    for y in range(SIZE):
        draw_bg.line([(0, y), (SIZE, y)], fill=lerp(BG_TOP, BG_BOTTOM, y / (SIZE - 1)))
    mask = circle_mask(SIZE) if round_icon else rounded_mask(SIZE, 112)
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    image.paste(bg, (0, 0), mask)

    draw = ImageDraw.Draw(image, "RGBA")
    center = SIZE / 2
    radius = 170
    width = 34
    bbox = (center - radius, center - radius, center + radius, center + radius)

    # 外圈刻度
    for i in range(60):
        angle = math.radians(135 + 270 * i / 59)
        inner = radius + 27
        outer = radius + 36
        x1 = center + math.cos(angle) * inner
        y1 = center + math.sin(angle) * inner
        x2 = center + math.cos(angle) * outer
        y2 = center + math.sin(angle) * outer
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 30), width=4)

    # 轨道与 270° 进度
    draw.arc(bbox, 135, 405, fill=TRACK, width=width)
    draw.arc(bbox, 135, 405, fill=GREEN, width=width)
    # 圆头端点
    for deg in (135, 405):
        a = math.radians(deg)
        x = center + math.cos(a) * radius
        y = center + math.sin(a) * radius
        draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=GREEN)

    # 末端高亮点 + 光晕
    a = math.radians(405)
    x = center + math.cos(a) * radius
    y = center + math.sin(a) * radius
    draw.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(139, 217, 123, 55))
    draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=TEXT)

    # 中心“步”字
    font_path = r"C:\Windows\Fonts\msyhbd.ttc"
    font = ImageFont.truetype(font_path, 188) if os.path.exists(font_path) else ImageFont.load_default()
    text = "步"
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text((center - tw / 2 - box[0], center - th / 2 - box[1] - 6), text, font=font, fill=TEXT)

    # 轻描边，避免浅色桌面上糊成一片
    if not round_icon:
        draw.rounded_rectangle((2, 2, SIZE - 3, SIZE - 3), radius=110,
                               outline=(255, 255, 255, 18), width=2)
    return image


def main() -> None:
    densities = {
        "mdpi": 48,
        "hdpi": 72,
        "xhdpi": 96,
        "xxhdpi": 144,
        "xxxhdpi": 192,
    }
    square = draw_icon(False)
    round_icon = draw_icon(True)
    for density, px in densities.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        square.resize((px, px), Image.LANCZOS).save(folder / "ic_launcher.png")
        round_icon.resize((px, px), Image.LANCZOS).save(folder / "ic_launcher_round.png")
    square.resize((512, 512), Image.LANCZOS).save(ROOT / "docs" / "app-icon.png")
    print("icons written to", RES)


if __name__ == "__main__":
    main()
