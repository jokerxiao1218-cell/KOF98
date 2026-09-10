"""scripts/sheet_ascii.py — 外部 sprite sheet 的 ASCII 过目工具(batch G)。

把任意 PNG sheet 按透明像素渲染成终端字符画(密度字符),AI 会话靠它
"看"图而不用 Read PNG(红线);人类也可以在终端直接看。
自动按整行空白切"带"(一排帧),每带打印粗粒度字符画 + 连通域清单。

用法(仓库根目录):
  env -u PYTHONPATH .venv/bin/python scripts/sheet_ascii.py game/sprites/terry/ff1_terry.png
  env -u PYTHONPATH .venv/bin/python scripts/sheet_ascii.py <png> --scale 2            # 放大细看
  env -u PYTHONPATH .venv/bin/python scripts/sheet_ascii.py <png> --region x,y,w,h    # 只看一块
  env -u PYTHONPATH .venv/bin/python scripts/sheet_ascii.py <png> --band 4             # 只看第 4 带
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

CHARS = " .:+#@@"   # 按不透明占比升级(≥70% 都用 @)


def load_alpha(path):
    img = pygame.image.load(path)
    if img.get_bitsize() == 32:      # PNG 带 alpha:直接用,别 convert_alpha(无头会炸)
        return img
    # 无 alpha:四角众数当底色抠掉
    w, h = img.get_size()
    corners = [img.get_at((x, y))[:3] for x, y in
               ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    bg = max(set(corners), key=corners.count)
    img.set_colorkey(bg)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(img, (0, 0))
    return out


def render(surf, x, y, w, h, scale):
    """区域 → 密度字符画(每 scale×scale 像素一格)。"""
    rows = []
    for cy in range(y, min(y + h, surf.get_height()), scale):
        line = []
        for cx in range(x, min(x + w, surf.get_width()), scale):
            n = 0
            tot = 0
            for yy in range(cy, min(cy + scale, surf.get_height())):
                for xx in range(cx, min(cx + scale, surf.get_width())):
                    tot += 1
                    if surf.get_at((xx, yy))[3] > 40:
                        n += 1
            frac = n / max(tot, 1)
            line.append(CHARS[min(int(frac * len(CHARS)), len(CHARS) - 1)])
        rows.append("".join(line))
    return rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("用法:sheet_ascii.py <png> [--scale n] [--region x,y,w,h] [--band n]")
    path = args[0]
    scale = 3
    region = None
    band_no = None
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--scale":
            scale = int(next(it))
        elif a == "--region":
            region = tuple(int(v) for v in next(it).split(","))
        elif a == "--band":
            band_no = int(next(it))

    pygame.init()
    surf = load_alpha(path)
    w, h = surf.get_size()
    print(f"{path} {w}x{h} scale={scale}")
    if region:
        for r in render(surf, *region, scale):
            print(r)
        return

    # 按整行空白切带
    rowfill = [any(surf.get_at((x, y))[3] > 40 for x in range(w))
               for y in range(h)]
    bands = []
    y = 0
    while y < h:
        if rowfill[y]:
            s = y
            while y < h and rowfill[y]:
                y += 1
            # 容忍 2 行以内的带内空隙
            while y < h and not rowfill[y] and sum(rowfill[y:y + 3]) > 0:
                y += 1
            bands.append((s, y))
        else:
            y += 1
    print(f"共 {len(bands)} 带(整行空白分隔):")
    for i, (s, e) in enumerate(bands):
        if band_no is not None and i != band_no:
            continue
        print(f"\n===== 带 {i}:y={s}..{e}(高 {e - s})=====")
        for r in render(surf, 0, s, w, e - s, scale):
            print(r)


if __name__ == "__main__":
    main()
