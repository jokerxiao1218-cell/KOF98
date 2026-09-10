"""art/terry_attacks.py — 特瑞姿势表·普通技姿势族(batch F 家族拆分)。

站立/蹲/空中拳脚:三段式(起手→挥出→收招),**判定帧 = 最狠姿势**
(设计文档 §11.2B:判定窗第 i 拍显示第 i 张挥出帧),新帧数与判定窗联动,
收招帧做"惯性回收"。
覆盖姿势:st_A st_B st_C st_D cr_A cr_B cr_C cr_D j_A j_B j_C j_D。骨架助手与部件字符画
约定见 terry_base;本文件只管摆放表,新帧直接加进 POSE_TABLE。
"""
from .terry_base import _f, _stand, _crouch, _air

# ---- 家族私有部件(新臂/腿变体等):名字 → 字符画,
# 格式同 terry_base.PARTS(字符→色见其模块 docstring)----
PARTS_EXTRA = {}

POSE_TABLE = {}

# ---- 普通技(startup→active→recovery)----

POSE_TABLE["st_A"] = (
    _stand("wind", 31, 22),
    _stand("punch", 34, 24, legs="run1", lg_dx=14, torso_dx=1, head_dx=2),
)

POSE_TABLE["st_B"] = (
    _stand("stance_f", 33, 15, legs="knee", lg_dx=16),
    _f(("arm_kick_bal", 25, 26), ("leg_sidekick", 12, 54),
        ("torso", 18, 26), ("head", 16, 10), ("arm_air", 29, 30)),
)

POSE_TABLE["st_C"] = (
    _stand("wind", 31, 22),
    _stand("punch_hi", 33, 14, legs="run1", lg_dx=13, torso_dx=1, head_dx=2),
    _stand("stance_f", 33, 15),
)

POSE_TABLE["st_D"] = (
    _stand("stance_f", 33, 15, legs="knee", lg_dx=16),
    _f(("arm_kick_bal", 24, 26), ("leg_sidekick", 11, 54),
        ("torso", 17, 26), ("head", 14, 10), ("arm_air", 28, 30)),
    _stand("stance_f", 33, 15, legs="knee", lg_dx=17),
)

POSE_TABLE["cr_A"] = (
    _crouch("low", 31, 58),
    _crouch("low", 35, 56),
)

POSE_TABLE["cr_B"] = (
    _crouch("low", 31, 58),
    _crouch("low", 33, 60, legs="crouch_kick", lg_dx=15),
)

POSE_TABLE["cr_C"] = (
    _crouch("low", 31, 58),
    _crouch("upper", 33, 40),
)

POSE_TABLE["cr_D"] = (
    _crouch("wind", 31, 56),
    _f(("arm_stance_b", 21, 54), ("leg_sweep", 9, 82),
        ("torso", 24, 58), ("head", 23, 46), ("arm_low", 31, 60)),
    _crouch("low", 33, 58, legs="crouch_kick", lg_dx=15),
)

POSE_TABLE["j_A"] = (
    _air("air", 33, 30),
    _air("punch_hi", 33, 28, head_dx=1),
)

POSE_TABLE["j_B"] = (
    _air("air", 33, 32),
    _air("air", 33, 32, legs="jumpkick", lg_dx=12),
)

POSE_TABLE["j_C"] = (
    _air("air", 33, 30),
    _air("air", 33, 32, legs="jumpkick", lg_dx=10),
    _air("punch_hi", 33, 28, legs="jumpkick", lg_dx=13),
)

POSE_TABLE["j_D"] = (
    _air("air", 33, 32),
    _air("punch_hi", 34, 26, legs="jumpkick", lg_dx=9),
    _air("punch_hi", 33, 28, legs="jumpkick", lg_dx=12, head_dx=1),
)

