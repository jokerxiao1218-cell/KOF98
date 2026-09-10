"""art/terry_reactions.py — 特瑞姿势表·受击/被控/胜负反应族(batch F 家族拆分)。

被打/倒地/起身/投技双方/胜负演出:反应姿势的中割关键是**受力方向**
(头后仰→躯干跟倒)与**时长铺陈**(knockdown 躺 2 帧、wakeup 撑地 2 帧)。
覆盖姿势:air_hit fall knockdown wakeup hit_high hit_low throw_whiff throw_grab thrown win lose。骨架助手与部件字符画
约定见 terry_base;本文件只管摆放表,新帧直接加进 POSE_TABLE。
"""
from .terry_base import _f, _stand, _crouch, _air

# ---- 家族私有部件(新臂/腿变体等):名字 → 字符画,
# 格式同 terry_base.PARTS(字符→色见其模块 docstring)----

# 挣扎躺姿:body_lie 的头块上提 3 行(手肘压地撑起),躯干下缘收成
# 楔形,垂发移到 1-2 列,手臂(ss)从肩斜下压过腰前、手套(g/G)按地,
# 腿块原样(受力最后才传到腿)。
PARTS_EXTRA = {
    "rxn_lie_struggle": [
        "....ccccc.....................................",
        "...ccccccc....................................",
        "..cccccccccw..................................",
        ".Ccccccccccw..................................",
        ".Ccccccccccw..................................",
        ".hhsssssssswvvvvvvvvvw........................",
        ".hhsssssssswvvvvvvvvvw........................",
        ".hhsssssssswvvvvvvvvvw........................",
        ".hhsssssss.wvvvvvvvvvw........................",
        ".hhssssss..wvvvvvvvvvw........................",
        ".hh.........wvvvvvvvvvw.......................",
        ".hh........sswVvvvvvvV........................",
        ".hh.......ss..wVvvvvvw........................",
        ".hh......ss....wVvvw..........................",
        ".hh.....ssbbbppppppppppppppppppp..............",
        ".hh.....ssbppppppppppppppppppppp..............",
        ".hh....ssbpppppppppppppppppppppp..............",
        ".hh....ssppppppppppppppppppppppp..............",
        ".hh....sspppp..pppppppppppppppp...............",
        ".hh...sspppp....ppppppppppppppp...............",
        ".hh...ssppp......ppppppppppppppp..............",
        ".hh...ssppp......ppppppppppp.rrrr.............",
        ".hh...ssppp.....ppppppppppprrwrr..............",
        ".hh...ssppp.....ppppppppp.rrwrr...............",
        ".hh..ssbppp....ppppppppppWWWWWW...............",
        ".hh..ssbppp...pppppppp..WWWWWW................",
        ".hh..ssbppp..ppppppp..........................",
        ".hhggg.bppp.pppppp............................",
        ".hhggg.bppppppppp.............................",
        ".hhGGG.bppppppp...............................",
    ],
}

POSE_TABLE = {}

POSE_TABLE["air_hit"] = (
    # 帧0 上身骤然后仰:前臂 arm_air 落到躯干顶右肩(躯干 (19,46)+11,+2,
    # 同 hit_high/j_A 的肩锚惯例),受击瞬间双臂从肩斜下甩开——原摆
    # (31,28) 悬在头上方与身体脱开 6px,读作断臂,已修。
    _air("air", 30, 48, lg_dx=12, torso_dx=-1, head_dx=-6),
    # 帧1 躯干跟倒:躯干 (-4,+4) 跟着后倒,头甩到 (-10,+4),前臂随躯干
    # 左移落到肩头 (27,48)——肩端 ss 压住躯干 (16,50) 顶右肩,间隙 0px;
    # 蜷腿滞后不动(受力顺序:头→躯干→臂→腿)。
    _air("air", 27, 48, lg_dx=12, ab_dx=14, ab_dy=49,
         torso_dx=-4, torso_dy=4, head_dx=-10, head_dy=4),
)

POSE_TABLE["fall"] = (
    _f(("body_fall1", 10, 70)),
    _f(("body_fall2", 10, 70)),
    # 帧2 贴地躺平:翻滚后砸地,与 knockdown 帧0 同位(躺定姿势),
    # fall→knockdown 状态衔接零跳变。
    _f(("body_lie", 5, 73)),
)

POSE_TABLE["knockdown"] = (
    _f(("body_lie", 5, 73)),
    # 帧1 挣扎微动:肘撑地、头肩抬起(rxn_lie_struggle,30 行 @ dy70
    # = 头块上提 3px、腿块原位贴地)。
    _f(("rxn_lie_struggle", 5, 70)),
)

POSE_TABLE["wakeup"] = (
    _f(("arm_stance_b", 19, 48), ("leg_kneel", 16, 68),
        ("torso", 20, 48), ("head", 19, 34), ("arm_stance_f", 31, 38)),
    # 帧1 半起身:后膝仍点地(腿最后动),躯干/头/双臂整体上抬,
    # 头相对躯干前倾 +2 —— 起身发力时重心向前压。
    _f(("arm_stance_b", 19, 44), ("leg_kneel", 16, 68),
        ("torso", 20, 45), ("head", 21, 30), ("arm_stance_f", 33, 35)),
)

POSE_TABLE["hit_high"] = (      # 3 帧:逐帧后仰
    _f(("arm_air", 29, 26), ("leg_stand", 18, 54),
        ("torso", 18, 24), ("head", 15, 10)),
    _f(("arm_air", 27, 28), ("leg_walk1", 16, 54),
        ("torso", 16, 26), ("head", 12, 12)),
    # 帧2 深后仰:头再后摆沉落 (-3,+2)、躯干跟倒 (-2,+2),
    # 前臂换成上位甩起(arm_punch_hi,受重击本能扬臂),腿保持后撤步。
    _f(("arm_punch_hi", 22, 25), ("leg_walk1", 16, 54),
        ("torso", 14, 28), ("head", 9, 14)),
)

POSE_TABLE["hit_low"] = (
    _f(("arm_low", 27, 40), ("leg_stand", 18, 54),
        ("torso", 22, 26), ("head", 24, 18)),
    # 帧1 更深弯:头再沉 (+3,+6) 逼近膝,躯干跟折 (+3,+4),
    # 手臂垂得更低 (+3,+6);腿仍站定(受力最后才传到腿)。
    _f(("arm_low", 30, 46), ("leg_stand", 18, 54),
        ("torso", 25, 30), ("head", 27, 24)),
)

POSE_TABLE["throw_whiff"] = (
    _stand("grab", 31, 24),
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
)

POSE_TABLE["throw_grab"] = (
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
    _f(("arm_stance_b", 17, 24), ("leg_run1", 14, 54),
        ("torso", 21, 24), ("head", 21, 8), ("arm_grab", 35, 24)),
    # 帧2 前倾发力:扣住后身体前倾(躯干 +2,+3、头随沉),
    # 前臂换成 arm_slam 双臂下压拽拽,步子扎稳发力(arm_slam
    # 摆法参照 power_geyser 跪砸帧)。
    _f(("arm_stance_b", 17, 26), ("leg_run1", 14, 54),
        ("torso", 23, 27), ("head", 23, 11), ("arm_slam", 25, 41)),
)

POSE_TABLE["thrown"] = (
    _f(("body_thrown", 10, 70)),
    # 帧1 空中翻转:被抛出后身体前翻(头从右上甩到左上),
    # 复用 body_fall1 翻滚相位,右上移 (+4,-7) 表现抛物线上升段。
    _f(("body_fall1", 14, 63)),
)

POSE_TABLE["win"] = (
    # leg_stand 上移 2px(54→52)封腰缝:躯干(20,23)腰带底行 y51 与腿顶
    # 行 y52 直接相接,原来 y52-53 两行全空(2px 透明缝)已消;代价是
    # 脚底从 y97 浮到 y95(脚底允许微浮,腰缝优先)。举臂庆祝,头微后仰。
    _f(("arm_stance_b", 17, 24), ("leg_stand", 18, 52),
        ("torso", 20, 23), ("head", 19, 7), ("arm_raise", 31, 2)),
)

POSE_TABLE["lose"] = (
    _f(("arm_down", 15, 28), ("leg_stand", 18, 54),
        ("torso", 20, 26), ("head", 18, 12), ("arm_down", 32, 28)),
)

