"""art/terry_locomotion.py — 特瑞姿势表·移动/基础姿势族(batch F 家族拆分)。

走路/跑步/跳跃等位移状态:位移姿势的中割关键是**重心与腿摆的连续
演化**(迈步→落地→过渡循环),躯干前倾幅度表达速度。
覆盖姿势:idle walk run crouch stand_block crouch_block prejump jump jump_fall land dash_back intro。骨架助手与部件字符画
约定见 terry_base;本文件只管摆放表,新帧直接加进 POSE_TABLE。
"""
from .terry_base import _f, _stand, _crouch, _air

# ---- 家族私有部件(新臂/腿变体等):名字 → 字符画,
# 格式同 terry_base.PARTS(字符→色见其模块 docstring)----
PARTS_EXTRA = {}

POSE_TABLE = {}


# ---- 基础状态 ----

POSE_TABLE["idle"] = (          # 4 帧:呼吸起伏(躯干/头沉 1px)+ 拳套微动
    _stand("stance_f", 33, 15),
    _stand("stance_f", 33, 16, torso_dy=1, head_dy=1),
    _stand("stance_f", 34, 15),
    _stand("stance_f", 33, 17, torso_dy=1, head_dy=1),
)

POSE_TABLE["walk"] = (          # 4 帧:迈步/过渡交替
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=17),
    _stand("stance_f", 33, 16, torso_dy=1, head_dy=1),
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=16),
    _stand("stance_f", 34, 16, torso_dy=1, head_dy=1, lg_dx=19),
)

POSE_TABLE["run"] = (           # 6 帧:大跨→腾空→过渡 ×2(前倾,摆臂)
    _stand("stance_f", 33, 15, legs="run1", lg_dx=13, head_dx=3, torso_dx=2),
    _stand("punch", 34, 26, legs="run2", lg_dx=15, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 16, legs="walk1", lg_dx=14, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 15, legs="run1", lg_dx=13, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 16, legs="run2", lg_dx=15, head_dx=3, torso_dx=2, ab_dx=14),
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=15, head_dx=3, torso_dx=2),
)

POSE_TABLE["crouch"] = (
    _crouch("low", 31, 58),
)

POSE_TABLE["stand_block"] = (
    _stand("guard", 32, 16, torso_dy=2, head_dy=2),
)

POSE_TABLE["crouch_block"] = (
    _crouch("guard", 31, 46),
)

POSE_TABLE["prejump"] = (
    _f(("arm_kick_bal", 29, 26), ("leg_closed", 18, 54),
        ("torso", 20, 26), ("head", 19, 10)),
)

POSE_TABLE["jump"] = (          # 2 帧:团身上升
    _air("air", 33, 30),
    _air("air", 33, 32, head_dy=-1),
)

POSE_TABLE["jump_fall"] = (     # 2 帧:双腿下探
    _air("air", 33, 32, legs="fall", lg_dx=18, lg_dy=72),
    _air("air", 33, 34, legs="fall", lg_dx=18, lg_dy=72, head_dy=-1),
)

POSE_TABLE["land"] = (
    _f(("arm_kick_bal", 29, 28), ("leg_crouch", 16, 76),
        ("torso", 20, 56), ("head", 19, 44)),
)

POSE_TABLE["dash_back"] = (
    _air("kick_bal", 25, 26, lg_dx=12, torso_dx=-3, head_dx=-5),
    _air("kick_bal", 24, 27, lg_dx=12, torso_dx=-4, head_dx=-6),
)

POSE_TABLE["intro"] = (         # 2 帧:双拳合握互撞(拍拳套开场)
    _f(("arm_wind", 17, 26), ("leg_stand", 18, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_wind", 31, 24)),
    _f(("arm_wind", 18, 27), ("leg_stand", 18, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_wind", 32, 25)),
)

