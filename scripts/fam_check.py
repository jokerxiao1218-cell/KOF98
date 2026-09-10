"""scripts/fam_check.py — 家族级自检(batch F 四代理并行加帧的模块级验收)。

用法(仓库根目录):
  env -u PYTHONPATH SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
    .venv/bin/python scripts/fam_check.py locomotion|attacks|specials|reactions

为什么要有它:考卷 tests/test_art.py 的帧数一致性测试是全表单条循环,
四家族并行加帧时互相挡绿灯;本脚本只圈定该家族的姿势,逐项照考卷同款
断言(帧数 == poses.POSE_KEYS 目标、相邻帧 ≥12 像素差、非空、56×100
画布、bbox 分组高度带宽与 test_bbox_groups 完全一致)。全家族绿 = 该
家族可交付;四家族合流后的全量 pytest 由主会话统一跑(集成验收)。
退出码 0=全绿,1=有问题(逐条列出)。
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import assets, poses                     # noqa: E402
from game.art import terry                         # noqa: E402
from game.art import (terry_attacks, terry_locomotion,  # noqa: E402
                      terry_reactions, terry_specials)

FAM_MODULES = {"locomotion": terry_locomotion, "attacks": terry_attacks,
               "specials": terry_specials, "reactions": terry_reactions}

P1 = assets.load_palette("P1")

# bbox 分组带(与 tests/test_art.py 的 TALL/CROUCH/AIR/BENT/LIE 逐键一致)
TALL = ["idle", "walk", "run", "stand_block", "prejump", "hit_high",
        "throw_whiff", "throw_grab", "st_A", "st_B", "st_C", "st_D",
        "power_wave", "win", "lose", "intro"]
CROUCH = ["crouch", "crouch_block", "cr_A", "cr_B", "cr_C", "cr_D"]
AIR = ["jump", "jump_fall", "air_hit", "j_A", "j_B", "j_C", "j_D",
       "crack_shoot", "rising_tackle"]
BENT = ["hit_low", "land", "dash_back", "wakeup"]
LIE = ["fall", "knockdown", "thrown"]
CORE_WIDE = ["idle", "walk", "run", "st_A", "st_B", "st_C", "st_D",
             "throw_whiff", "throw_grab", "power_wave", "hit_high"]


def bbox(surf):
    rects = pygame.mask.from_surface(surf).get_bounding_rects()
    return (min(r.x for r in rects), min(r.y for r in rects),
            max(r.x + r.w for r in rects), max(r.y + r.h for r in rects))


def frame_diff(a, b):
    tobytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
    da, db = tobytes(a, "RGBA"), tobytes(b, "RGBA")
    return sum(1 for j in range(0, len(da), 4)
               if (da[j + 3] > 128 or db[j + 3] > 128)
               and da[j:j + 4] != db[j:j + 4])


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in FAM_MODULES:
        sys.exit(f"用法:{sys.argv[0]} locomotion|attacks|specials|reactions")
    fam_name = sys.argv[1]
    fam = FAM_MODULES[fam_name]
    errors = []
    total_frames = 0

    # 家族文件里混进未注册姿势键 → 直接红
    for key in fam.POSE_TABLE:
        if key not in poses.POSE_KEYS:
            errors.append(f"{key}:不在 poses.POSE_KEYS(键名冻结,不许加新键)")

    for key, frames in sorted(fam.POSE_TABLE.items()):
        label = f"[{fam_name}] {key}"
        n_target = poses.POSE_KEYS[key]
        n = len(frames)
        if n != n_target:
            errors.append(f"{label}:帧数 {n} != 目标 {n_target}")
        total_frames += n
        for f in range(min(n, n_target)):        # 越界帧号交给计数红门报
            s = assets.sprite(key, f, 1, P1)
            if pygame.mask.from_surface(s).count() == 0:
                errors.append(f"{label} 第{f}帧空白")
            if s.get_size() != (terry.CANVAS_W, terry.CANVAS_H):
                errors.append(f"{label} 第{f}帧画布 {s.get_size()}")
        for f in range(max(n - 1, 0)):
            d = frame_diff(assets.sprite(key, f, 1, P1),
                            assets.sprite(key, f + 1, 1, P1))
            if d < 12:
                errors.append(f"{label} 第{f}→{f + 1}帧只差 {d} 像素(凑数帧)")

        # bbox 分组带(与 test_bbox_groups 同款;蹲/空/弯/躺按考卷只查帧 0)
        if n:
            b0 = bbox(assets.sprite(key, 0, 1, P1))
            h0, w0 = b0[3] - b0[1], b0[2] - b0[0]
            if key in TALL:
                for f in range(n):
                    x1, y1, x2, y2 = bbox(assets.sprite(key, f, 1, P1))
                    h, w = y2 - y1, x2 - x1
                    if not 84 <= h <= 100:
                        errors.append(f"{label} 第{f}帧(站立族)高 {h} 应 84~100")
                    if not 18 <= w <= 48:
                        errors.append(f"{label} 第{f}帧宽 {w} 应 18~48")
            elif key in CROUCH and not 44 <= h0 <= 66:
                errors.append(f"{label}(蹲族)高 {h0} 应 44~66")
            elif key in AIR and not 60 <= h0 <= 80:
                errors.append(f"{label}(空中团身)高 {h0} 应 60~80")
            elif key in BENT and not 60 <= h0 <= 84:
                errors.append(f"{label}(弯身族)高 {h0} 应 60~84")
            elif key in LIE:
                if h0 > 45:
                    errors.append(f"{label}(躺/被抛)高 {h0} 应 <=45")
                if w0 < 30:
                    errors.append(f"{label}(横向蜷缩)宽 {w0} 应 >=30")
            if key in ("burn_knuckle", "power_geyser"):
                hs = [bbox(assets.sprite(key, f, 1, P1))[3]
                      - bbox(assets.sprite(key, f, 1, P1))[1]
                      for f in range(n)]
                if not all(50 <= h <= 100 for h in hs):
                    errors.append(f"{label} 各帧高 {hs} 应 50~100")
                if hs and max(hs) < 84:
                    errors.append(f"{label} 至少一帧应挺立(>=84),得到 {hs}")
            elif key == "power_dunk":
                for f in range(n):
                    b = bbox(assets.sprite(key, f, 1, P1))
                    if not 50 <= b[3] - b[1] <= 80:
                        errors.append(f"{label} 第{f}帧高 {b[3] - b[1]} 应 50~80")
            if key in CORE_WIDE:
                ws = [bbox(assets.sprite(key, f, 1, P1))[2]
                      - bbox(assets.sprite(key, f, 1, P1))[0]
                      for f in range(n)]
                if ws and not 24 <= max(ws) <= 44:
                    errors.append(f"{label} 最宽帧 {max(ws)} 应 24~44(各帧 {ws})")

    if errors:
        print(f"✗ {fam_name} 家族自检:发现 {len(errors)} 个问题")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"✓ {fam_name} 家族自检:{len(fam.POSE_TABLE)} 姿势 / "
          f"{total_frames} 帧全绿(帧数/帧差/非空/画布/bbox 带全过)")


if __name__ == "__main__":
    main()
