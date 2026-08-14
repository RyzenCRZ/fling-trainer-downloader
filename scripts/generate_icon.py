"""生成现代风格的应用图标 — 亚克力/玻璃拟态风格

设计：
- 圆角方形背景，蓝色渐变 #007AFF → #5856D6
- 中心白色闪电图标（代表"修改器"速度主题）
- 多尺寸 ICO 输出
"""
import math
from PIL import Image, ImageDraw, ImageFont


def draw_rounded_gradient_rect(size, radius, color1, color2):
    """绘制圆角渐变方形"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 逐行绘制渐变
    for y in range(size):
        ratio = y / size
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # 创建圆角蒙版
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)

    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def draw_lightning(draw, cx, cy, size, color):
    """绘制闪电图标"""
    # 闪电的顶点坐标（相对于中心点）
    w = size * 0.4  # 宽度
    h = size * 0.7  # 高度
    points = [
        (cx + w * 0.1, cy - h * 0.5),   # 顶部右
        (cx - w * 0.3, cy - h * 0.5),   # 顶部左
        (cx - w * 0.05, cy - h * 0.05),  # 中上左
        (cx - w * 0.25, cy - h * 0.05),  # 中上左外
        (cx + w * 0.15, cy + h * 0.5),   # 底部
        (cx + w * 0.05, cy + h * 0.05),  # 中下右
        (cx + w * 0.25, cy + h * 0.05),  # 中下右外
    ]
    draw.polygon(points, fill=color)


def draw_gamepad(draw, cx, cy, size, color):
    """绘制游戏手柄图标（简化版）"""
    w = size * 0.5
    h = size * 0.3
    # 手柄主体
    draw.rounded_rectangle(
        [cx - w, cy - h, cx + w, cy + h],
        radius=int(h * 0.4),
        outline=color,
        width=max(2, size // 64)
    )
    # 左摇杆
    draw.ellipse([cx - w * 0.5, cy - h * 0.3, cx - w * 0.2, cy + h * 0.3], outline=color, width=max(2, size // 64))
    # 右摇杆
    draw.ellipse([cx + w * 0.2, cy - h * 0.3, cx + w * 0.5, cy + h * 0.3], outline=color, width=max(2, size // 64))


def create_icon(size=256):
    """生成图标"""
    # 1. 圆角渐变背景
    radius = int(size * 0.22)  # iOS 风格圆角
    bg = draw_rounded_gradient_rect(size, radius, (0, 122, 255), (88, 86, 214))

    # 2. 添加内发光效果（半透明白色边框）
    glow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        [size * 0.03, size * 0.03, size * 0.97, size * 0.97],
        radius=radius,
        outline=(255, 255, 255, 40),
        width=max(2, size // 64)
    )
    bg = Image.alpha_composite(bg, glow)

    # 3. 绘制白色闪电
    draw = ImageDraw.Draw(bg)
    draw_lightning(draw, size // 2, size // 2, size, (255, 255, 255, 255))

    # 4. 添加底部高光
    highlight = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(highlight)
    hl_draw.rounded_rectangle(
        [size * 0.05, size * 0.05, size * 0.95, size * 0.4],
        radius=radius,
        fill=(255, 255, 255, 15)
    )
    # 创建圆角蒙版用于高光
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    highlight_masked = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    highlight_masked.paste(highlight, (0, 0), mask)
    bg = Image.alpha_composite(bg, highlight_masked)

    return bg


def main():
    output_path = "assets/app_icon.ico"

    # 生成多尺寸
    sizes = [256, 128, 64, 48, 32, 16]
    images = [create_icon(s) for s in sizes]

    # 保存为 ICO
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes]
    )
    print(f"图标已保存: {output_path}")

    # 同时保存 PNG 预览
    png_path = "assets/app_icon_256.png"
    images[0].save(png_path)
    print(f"PNG 预览: {png_path}")


if __name__ == '__main__':
    main()
