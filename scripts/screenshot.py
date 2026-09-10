"""scripts/screenshot.py — 无头渲染验收截图(A5 素材过目/batch C 无头验收用)。

跑法:cd ~/kof98 && env -u PYTHONPATH .venv/bin/python scripts/screenshot.py
输出:scripts/out/poses_sheet.png(姿势全家福)+ scripts/out/scene.png(带背景的一帧)
红线:生成的 PNG 一律不 Read 进会话——人来打开看,程序用像素统计验收。
"""
import os
import sys
from pathlib import Path

# 必须在 import pygame 之前设好 dummy 驱动(先例项目实测结论)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from game import assets
from game.art import stage

OUT = Path(__file__).resolve().parent / "out"
SCALE = 3
CANVAS_W, CANVAS_H = 56, 100  # assets.sprite 人形统一画布(脚底=画布底)

# 过目清单:A5 汇报里"拿不准"的 + 各状态族代表
POSES = [
    ("idle", 0), ("walk", 1), ("run", 2), ("crouch", 0),
    ("st_C", 1), ("cr_D", 1), ("jump", 1), ("burn_knuckle", 2),
    ("rising_tackle", 1), ("power_geyser", 2), ("knockdown", 0), ("win", 0),
    ("dash_back", 1), ("throw_grab", 1),
]
PER_ROW = 7


def main() -> int:
    pygame.init()
    OUT.mkdir(exist_ok=True)

    # ---- 1) 姿势全家福:P1 一排 + P2 换色一排 ----
    rows = [(assets.load_palette("P1"), POSES[:PER_ROW]),
            (assets.load_palette("P1"), POSES[PER_ROW:]),
            (assets.load_palette("P2"), POSES[:PER_ROW])]
    cell_w, cell_h = CANVAS_W * SCALE, CANVAS_H * SCALE
    sheet = pygame.Surface((cell_w * PER_ROW, cell_h * len(rows)))
    for r, (pal, poses) in enumerate(rows):
        for c, (key, frame) in enumerate(poses):
            sp = assets.sprite(key, frame, 1, pal)
            big = pygame.transform.scale(sp, (sp.get_width() * SCALE, sp.get_height() * SCALE))
            sheet.blit(big, (c * cell_w, r * cell_h))
    pygame.image.save(sheet, OUT / "poses_sheet.png")

    # ---- 2) 一帧场景:黄昏街头 + 双人对峙 + 能量波 + 喷泉 ----
    scene = pygame.Surface((320, 224))
    stage.draw(scene, cam_x=0)
    p1, p2 = assets.load_palette("P1"), assets.load_palette("P2")
    ground_y = 190  # 渲染层屏幕地面(世界 y 向上为正,此处换算)
    cam_x = 0

    def put(key, frame, facing, x, pal, y_off=0):
        sp = assets.sprite(key, frame, facing, pal)
        scene.blit(sp, (int(x - cam_x - CANVAS_W / 2), ground_y - CANVAS_H - y_off))

    put("idle", 0, 1, 96, p1)
    put("idle", 0, -1, 224, p2)
    scene.blit(assets.sprite("proj_wave", 1, 1, p1), (150, ground_y - 28))
    scene.blit(assets.sprite("fx_geyser", 2, 1, p1), (200, ground_y - 92))
    pygame.image.save(pygame.transform.scale(scene, (320 * SCALE, 224 * SCALE)), OUT / "scene.png")

    # 像素统计兜底(证明不是全黑/全空)
    for name in ("poses_sheet.png", "scene.png"):
        surf = pygame.image.load(OUT / name)
        w, h = surf.get_size()
        dark = sum(
            1 for x in range(0, w, 7) for y in range(0, h, 7)
            if sum(surf.get_at((x, y))[:3]) < 45
        )
        total = (w // 7 + 1) * (h // 7 + 1)
        print(f"{name}: {w}x{h}, 非暗像素占比 {100 * (1 - dark / total):.1f}%")
    print(f"输出目录:{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
