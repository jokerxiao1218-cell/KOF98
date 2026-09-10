"""art/terry_reactions.py — 特瑞姿势表·受击/被控/胜负反应族(batch F 家族拆分)。

被打/倒地/起身/投技双方/胜负演出:反应姿势的中割关键是**受力方向**
(头后仰→躯干跟倒)与**时长铺陈**(knockdown 躺 2 帧、wakeup 撑地 2 帧)。
覆盖姿势:air_hit fall knockdown wakeup hit_high hit_low throw_whiff throw_grab thrown win lose。骨架助手与部件字符画
约定见 terry_base;本文件只管摆放表,新帧直接加进 POSE_TABLE。
"""
from .terry_base import _f, _stand, _crouch, _air

# ---- 家族私有部件(新臂/腿变体等):名字 → 字符画,
# 格式同 terry_base.PARTS(字符→色见其模块 docstring)----
PARTS_EXTRA = {}

POSE_TABLE = {}

POSE_TABLE["air_hit"] = (
    _air("air", 31, 28, lg_dx=12, torso_dx=-1, head_dx=-6),
)

POSE_TABLE["fall"] = (
    _f(("body_fall1", 10, 70)),
    _f(("body_fall2", 10, 70)),
)

POSE_TABLE["knockdown"] = (
    _f(("body_lie", 5, 73)),
)

POSE_TABLE["wakeup"] = (
    _f(("arm_stance_b", 19, 48), ("leg_kneel", 16, 68),
        ("torso", 20, 48), ("head", 19, 34), ("arm_stance_f", 31, 38)),
)

POSE_TABLE["hit_high"] = (      # 2 帧:逐帧后仰
    _f(("arm_air", 29, 26), ("leg_stand", 18, 54),
        ("torso", 18, 24), ("head", 15, 10)),
    _f(("arm_air", 27, 28), ("leg_walk1", 16, 54),
        ("torso", 16, 26), ("head", 12, 12)),
)

POSE_TABLE["hit_low"] = (
    _f(("arm_low", 27, 40), ("leg_stand", 18, 54),
        ("torso", 22, 26), ("head", 24, 18)),
)

POSE_TABLE["throw_whiff"] = (
    _stand("grab", 31, 24),
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
)

POSE_TABLE["throw_grab"] = (
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
    _f(("arm_stance_b", 17, 24), ("leg_run1", 14, 54),
        ("torso", 21, 24), ("head", 21, 8), ("arm_grab", 35, 24)),
)

POSE_TABLE["thrown"] = (
    _f(("body_thrown", 10, 70)),
)

POSE_TABLE["win"] = (
    _f(("arm_stance_b", 17, 24), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 19, 7), ("arm_raise", 31, 2)),
)

POSE_TABLE["lose"] = (
    _f(("arm_down", 15, 28), ("leg_stand", 18, 54),
        ("torso", 20, 26), ("head", 18, 12), ("arm_down", 32, 28)),
)

