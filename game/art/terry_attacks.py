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

# 三段式:起手(拳收胸口蓄力,躯干后坐)→ 挥出(直拳全伸+跨步冲)→
# 收招(拳沿出拳线收回下巴,腿从弓步收回站桩,躯干回落)
POSE_TABLE["st_A"] = (
    _stand("wind", 28, 24, torso_dx=-1, head_dx=-1),
    _stand("punch", 34, 24, legs="run1", lg_dx=14, torso_dx=1, head_dx=2),
    _stand("wind", 33, 24),
)

# 三段式:起手(提膝蓄力,拳收胸口,躯干后坐)→ 挥出(横踢全伸+双臂平衡)
# → 收招(踢腿前落成走步位,臂收回护颌)
POSE_TABLE["st_B"] = (
    _stand("wind", 30, 22, legs="knee", lg_dx=16, torso_dx=-1, head_dx=-1),
    _f(("arm_kick_bal", 25, 26), ("leg_sidekick", 12, 54),
        ("torso", 18, 26), ("head", 16, 10), ("arm_air", 29, 30)),
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=15),
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

# 三段式:起手(拳收胸口蓄力,躯干后坐)→ 挥出(低刺拳前伸)→
# 收招(拳沿低位刺出线收回髋侧,重心回落下沉)
POSE_TABLE["cr_A"] = (
    _crouch("wind", 29, 56, torso_dx=-1, head_dx=-1),
    _crouch("low", 35, 56),
    _crouch("low", 29, 60, torso_dy=1, head_dy=1),
)

# 三段式:起手(拳高收肩侧深蓄,躯干后坐)→ 挥出(低位重拳+小腿弹踢前送,
# 重心前压)→ 收招(腿收回蹲桩,拳沿低位撤回,重心后撤回落)
POSE_TABLE["cr_B"] = (
    _crouch("wind", 26, 54, torso_dx=-1, head_dx=-1),
    _crouch("low", 33, 60, legs="crouch_kick", lg_dx=15),
    _crouch("low", 28, 62, torso_dx=-1, head_dx=-1),
)

# 三段式:起手(拳沉髋后蓄力,身体下压)→ 挥出(蹲姿升龙拳,拳套冲到头顶
# 前上方)→ 收招(拳沿弧线落回胸口,身体回正)
POSE_TABLE["cr_C"] = (
    _crouch("low", 26, 63, torso_dy=1, head_dx=-1, head_dy=1),
    _crouch("upper", 33, 40),
    _crouch("wind", 32, 53),
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

