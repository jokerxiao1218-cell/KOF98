"""art/terry_specials.py — 特瑞姿势表·必杀/超杀姿势族(batch F 家族拆分)。

搓招必杀与超杀:蓄力→爆发的姿势演化(蹲→升→顶),帧多用于**力量感
的蓄放对比**(起手沉、爆发张);proj_wave/fx_geyser 特效键不在本表。
覆盖姿势:power_wave burn_knuckle crack_shoot rising_tackle power_dunk power_geyser。骨架助手与部件字符画
约定见 terry_base;本文件只管摆放表,新帧直接加进 POSE_TABLE。
"""
from .terry_base import _f, _stand, _crouch, _air

# ---- 家族私有部件(新臂/腿变体等):名字 → 字符画,
# 格式同 terry_base.PARTS(字符→色见其模块 docstring)----
PARTS_EXTRA = {
    # 空中抡踢·前抡相位(crack_shoot 中割):踢腿向前下扫出,支撑腿收在身下
    "leg_kick_fwd": [
        "....pppppppppp...............",
        "....pppppppppp...............",
        "....pppppppppp...............",
        "...Ppppppppppp...............",
        "...Ppppppppppp...............",
        "...Ppppppppppp...............",
        "...Ppp.......ppp.............",
        "...Ppp.......ppp.............",
        "...Ppp.........ppp...........",
        "...Ppp.........ppp...........",
        "...Ppp...........ppp.........",
        "...Ppp...........ppp.........",
        "...Ppp.............ppp.......",
        "...Ppp.............ppp.......",
        "...rrr...............rrrr....",
        "..rrwr...............rrwrr...",
        "..rrwr................rrwrr..",
        "..rrrr................rrrr...",
        ".WWWWW................WWWWW..",
        ".WWWWW................WWWW...",
    ],
    # 空中抡踢·前上相位(crack_shoot 峰值):踢腿指向前上(脚尖高举过髋),
    # 髋块沉到部件下部接腰,支撑腿拖在身下
    "leg_kick_fup": [
        ".......................WWWWWW.....",
        ".......................WWWWWW.....",
        ".......................rrwrrr.....",
        ".......................rrwrrr.....",
        ".......................rrrrrr.....",
        ".......................rrrrrr.....",
        "........................ppp.......",
        "........................ppp.......",
        "......................ppp.........",
        "......................ppp.........",
        "....................ppp...........",
        "....................ppp...........",
        "..................ppp.............",
        "..................ppp.............",
        "................ppp...............",
        "................ppp...............",
        "..............ppp.................",
        "..............ppp.................",
        "....pppppppppp....................",
        "....pppppppppp....................",
        "....pppppppppp....................",
        "...Ppppppppppp....................",
        "...Ppppppppppp....................",
        "...Ppppppppppp....................",
        "...ppp............................",
        "...ppp............................",
        "..ppp.............................",
        "..ppp.............................",
        ".ppp..............................",
        ".ppp..............................",
        ".rrr..............................",
        "rrwr..............................",
        "rrwr..............................",
        "rrrr..............................",
        "WWWWW.............................",
        "WWWW..............................",
    ],
    # 落地双拳压地(power_dunk 收帧):双臂从肩并拢直插到地,拳套垫在最下
    "arm_plunge": [
        "sss........sss",
        ".sss......sss.",
        ".sss......sss.",
        "..sss....sss..",
        "..sss....sss..",
        "...sss..sss...",
        "...ssssssss...",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "....ssssss....",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "......ssssss..",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........ssssss",
        "........gggggg",
        "........gggggg",
        "........GGGGGG",
    ],
}

POSE_TABLE = {}

# ---- 必杀/超杀 ----

POSE_TABLE["power_wave"] = (    # 3 帧:后蓄→双掌前推→收
    _stand("wind", 31, 22, arm_b="wind", ab_dx=17, ab_dy=26),
    _f(("arm_punch", 19, 26), ("leg_run1", 13, 54),
        ("torso", 21, 24), ("head", 21, 8), ("arm_punch", 33, 24)),
    _stand("stance_f", 33, 15),
)

POSE_TABLE["burn_knuckle"] = (  # 4 帧:蹲蓄→前冲拳→全伸→收
    _crouch("wind", 31, 56),
    _stand("punch", 34, 24, legs="run1", lg_dx=13, torso_dx=2, head_dx=3),
    _stand("punch_hi", 34, 14, legs="run1", lg_dx=14, torso_dx=2, head_dx=3),
    _stand("stance_f", 33, 15),
)

POSE_TABLE["crack_shoot"] = (   # 4 帧:空中抡踢弧线(后摆蓄力→向前抡出→抡到前上→收)
    _air("air", 33, 30, legs="jumpkick", lg_dx=16),   # 后摆蓄力:踢腿收到身后下方
    _air("air", 33, 32, legs="kick_fwd", lg_dx=18),   # 向前抡出:腿扫过身前向斜下
    _air("air", 34, 32, legs="kick_fup", lg_dx=19, lg_dy=58,   # 抡到前上:脚尖指向前上,
         arm_b="kick_bal", ab_dx=15, ab_dy=40),                #  后臂扬起平衡
    _air("air", 33, 32),                              # 收腿团身
)

POSE_TABLE["rising_tackle"] = (  # 4 帧:上升螺旋(拳臂交替旋转 + 整体 dy 逐帧升空)
    _air("upper", 31, 26),      # 起手离地(脚仍贴画布底)
    _air("punch_hi", 34, 16, lg_dx=15, lg_dy=68, ab_dy=38,       # 升空 +8
         head_dx=-3, head_dy=-8, torso_dx=1, torso_dy=-8),
    _air("upper", 29, 8, lg_dx=14, lg_dy=58, ab_dy=28,           # 升空 +18
         head_dx=3, head_dy=-18, torso_dx=-1, torso_dy=-18),
    _air("air", 33, 2, lg_dx=15, lg_dy=48, ab_dy=18,             # 升空 +28(最高点)
         head_dx=-2, head_dy=-28, torso_dy=-28),
)

POSE_TABLE["power_dunk"] = (    # 5 帧:蹲蓄→升→空中举拳→下砸→落地双拳压地
    _crouch("wind", 31, 56),
    _air("upper", 31, 26),
    _air("punch_hi", 33, 24),
    _air("slam", 26, 32),
    _crouch("plunge", 25, 58, legs="crouch_kick", lg_dx=15),  # 拳套压到 y96-98 贴地
)

POSE_TABLE["power_geyser"] = (  # 5 帧:蹲蓄→跪砸地→爆发挺举→保持→收
    _crouch("wind", 31, 56, arm_b="wind", ab_dx=17, ab_dy=58),
    _f(("leg_kneel", 16, 68), ("torso", 20, 48), ("head", 21, 32),
        ("arm_slam", 22, 62)),
    _f(("arm_raise", 15, 0), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 19, 7), ("arm_raise", 31, 2)),
    _f(("arm_raise", 14, 1), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 20, 6), ("arm_raise", 32, 2)),
    _stand("stance_f", 33, 15),
)
