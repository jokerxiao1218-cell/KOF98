"""art/ — 纸娃娃像素装配的公共工具(设计文档 §4.7)。

纪律(照 mota50 的 assets._paint):
  * 字符画每行必须等长,行数/行长/字符非法都直接 raise,绝不静默画歪;
  * '.' 与 ' ' 是透明像素;
  * 零图片文件、运行时程序自绘,按 (部件名, 配色标识) 缓存部件 Surface。
本包不 import game.core(素材层独立,设计文档 §5.2 依赖方向);
也不 import game.assets(assets → art 单向,防环)。
"""
import pygame

TRANSPARENT = (".", " ")


def shift(color, factor):
    """颜色整体调亮(>1)或调暗(<1),做同部件的暗部/高光。"""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def paint(name, rows, palette):
    """字符画 → Surface。任何形状问题直接报错,不许静默画歪。"""
    height = len(rows)
    if height == 0:
        raise ValueError(f"部件 {name} 是空字符画")
    width = len(rows[0])
    if width == 0:
        raise ValueError(f"部件 {name} 字符画宽度为 0")
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"部件 {name} 第 {y} 行长度 {len(row)} != {width}:{row!r}")
        for x, ch in enumerate(row):
            if ch in TRANSPARENT:
                continue
            if ch not in palette:
                raise ValueError(f"部件 {name} 用了未定义颜色的字符 {ch!r}(可用:{sorted(palette)})")
            surface.set_at((x, y), palette[ch])
    return surface
