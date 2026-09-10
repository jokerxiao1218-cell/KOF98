"""art/terry.py — 特瑞·伯格纸娃娃门面(batch F 家族拆分)。

结构:terry_base(部件库/调色板/骨架助手/装配)← 四家族姿势表
(locomotion 移动 / attacks 普通技 / specials 必杀超杀 / reactions 受击反应)。
本文件合并各家族 POSE_TABLE → POSES,并保持 assets/测试的调用面不变:
assemble / normalize_palette / palette_id / CANVAS_W / CANVAS_H / PARTS。
合并纪律:姿势键或部件名跨家族重复 → import 期就 ValueError,不溜进运行期。
"""
import pygame

from . import (terry_attacks, terry_locomotion, terry_reactions,
               terry_specials)
from .terry_base import (CANVAS_W, CANVAS_H, PARTS, _air, _crouch, _f,
                         _part, _stand, normalize_palette, palette_id)

# ---------------------------------------------------------------- 家族合并

POSES = {}
for _mod in (terry_locomotion, terry_attacks, terry_specials, terry_reactions):
    for _key, _frames in _mod.POSE_TABLE.items():
        if _key in POSES:
            raise ValueError(f"姿势键 {_key!r} 在 {_mod.__name__} 与其他家族重复")
        POSES[_key] = _frames
    for _name, _rows in _mod.PARTS_EXTRA.items():
        if _name in PARTS:
            raise ValueError(f"部件 {_name!r} 在 {_mod.__name__} 与基础部件重复")
        PARTS[_name] = _rows



def assemble(pose_key, frame, palette):
    """POSE 键 + 帧号 + 调色板 → 整帧 Surface(56×100,脚底 = 画布底)。"""
    if pose_key not in POSES:
        raise KeyError(f"未注册的人形姿势 {pose_key!r}(可用:{sorted(POSES)})")
    frames = POSES[pose_key]
    plan = frames[frame % len(frames)]
    pal = normalize_palette(palette)
    pid = palette_id(pal)
    surface = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    for name, dx, dy in plan:
        if name not in PARTS:
            raise KeyError(f"姿势 {pose_key} 引用了未定义部件 {name!r}")
        surface.blit(_part(name, pid, pal), (dx, dy))
    return surface
