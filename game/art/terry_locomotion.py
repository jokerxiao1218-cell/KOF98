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

# ---- walk 步态六相位腿件(与 base 的 leg_walk1 同骨架 45×20)----
# 左右腿交替的关键:特瑞面朝右,远侧(左)腿全程用裤暗色 P、近侧(右)腿纯 p——
# A/B 两半环各用三个相位件且前后腿角色互换(B = A 的换腿镜像),播放时
# 暗色腿可见地"后蹬→提膝→前迈"绕环一周。远侧摆动腿过位时比近侧靠内 1 列
# (透视上从支撑腿后方提起)。压实相位后鞋=踮尖楔形:鞋跟抬高 3 行、
# 脚尖 W 像素伸到部件 43-44 行触地(真踮尖蹬伸,不是整脚离地)。
PARTS_EXTRA["leg_loco_ca"] = [   # A触地:远(暗P)腿前槽 14-16 落脚,近(p)腿后槽 6-8 平贴
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    ".....ppp.....PPP....",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......PPP.....PPP...",
    "......PPP.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......ppp.....PPP...",
    "......rrr.....rrr...",
    ".....rrrr.....rrrr..",
    ".....rrwr.....rrwr..",
    ".....rrrr.....rrrr..",
    ".....rrrr.....rrrr..",
    "....WWWW.....WWWWW..",
    "....WWWW.....WWWWW..",
]

PARTS_EXTRA["leg_loco_ra"] = [   # A压实:远腿竖直承重 11-13,近腿拖后踮尖蹬伸(跟抬尖触地)
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    ".....ppp..PPP.......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    ".....ppp...PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "....ppp....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    "...ppp.....PPP......",
    ".rrrr......PPP......",
    ".rrwr......PPP......",
    ".rrrr......rrr......",
    ".rrrrr.....rrrr.....",
    ".rrwrr.....rrwr.....",
    "..rrwrr....rrrr.....",
    "...rrwrr...rrrr.....",
    "...WWWWW..WWWWW.....",
    "...WWWWW..WWWWW.....",
]

PARTS_EXTRA["leg_loco_pa"] = [   # A过腿:近腿从髋后/左提膝过位(膝 5-7),远腿续撑 8-10
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "....pppPPP..........",
    "....ppp.PPP.........",
    "....ppp.PPP.........",
    "....ppp.PPP.........",
    ".....pppPPP.........",
    ".....pppPPP.........",
    ".....pppPPP.........",
    ".....pppPPP.........",
    ".....PPPPPP.........",
    ".....PPPPPP.........",
    "....ppppPPP.........",
    "....ppp.PPP.........",
    "....ppp.PPP.........",
    "....ppp.PPP.........",
    "....ppp.PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...ppp..PPP.........",
    "...rrr..PPP.........",
    "...rrrr.PPP.........",
    "..rrwrr.PPP.........",
    "..rrrrr.PPP.........",
    "..rrwrr.PPP.........",
    "..WWWWW.PPP.........",
    "..WWWWW.PPP.........",
    "........PPP.........",
    "........PPP.........",
    "........PPP.........",
    "........rrr.........",
    "........rrrr........",
    "........rrwr........",
    "........rrrr........",
    "........rrrr........",
    ".......WWWWW........",
    ".......WWWWW........",
]

PARTS_EXTRA["leg_loco_cb"] = [   # B触地:近(p)腿前槽落脚,远(暗P)腿后槽——与 ca 前后腿互换
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    ".....PPP.....ppp....",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....PPP...",
    "......PPP.....PPP...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......PPP.....ppp...",
    "......rrr.....rrr...",
    ".....rrrr.....rrrr..",
    ".....rrwr.....rrwr..",
    ".....rrrr.....rrrr..",
    ".....rrrr.....rrrr..",
    "....WWWW.....WWWWW..",
    "....WWWW.....WWWWW..",
]

PARTS_EXTRA["leg_loco_rb"] = [   # B压实:近腿承重,远腿拖后踮尖蹬伸——与 ra 互换
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    ".....PPP..ppp.......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    ".....PPP...ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....PPP......",
    "....PPP....PPP......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "....PPP....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    "...PPP.....ppp......",
    ".rrrr......ppp......",
    ".rrwr......ppp......",
    ".rrrr......rrr......",
    ".rrrrr.....rrrr.....",
    ".rrwrr.....rrwr.....",
    "..rrwrr....rrrr.....",
    "...rrwrr...rrrr.....",
    "...WWWWW..WWWWW.....",
    "...WWWWW..WWWWW.....",
]

PARTS_EXTRA["leg_loco_pb"] = [   # B过腿:远(暗P)腿从髋后提膝(靠内1列),近腿续撑——与 pa 互换
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "...PPP.ppp..........",
    "...PPP..ppp.........",
    "...PPP..ppp.........",
    "...PPP..ppp.........",
    "....PPP.ppp.........",
    "....PPP.ppp.........",
    "....PPP.ppp.........",
    "....PPP.ppp.........",
    "....PPP.ppp.........",
    "....PPP.ppp.........",
    "...PPPP.ppp.........",
    "...PPP..ppp.........",
    "...PPP..ppp.........",
    "...PPP..PPP.........",
    "...PPP..PPP.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..PPP...ppp.........",
    "..rrr...ppp.........",
    "..rrrr..ppp.........",
    ".rrwrr..ppp.........",
    ".rrrrr..ppp.........",
    ".rrwrr..ppp.........",
    ".WWWWW..ppp.........",
    ".WWWWW..ppp.........",
    "........ppp.........",
    "........ppp.........",
    "........ppp.........",
    "........rrr.........",
    "........rrrr........",
    "........rrwr........",
    "........rrrr........",
    "........rrrr........",
    ".......WWWWW........",
    ".......WWWWW........",
]

POSE_TABLE = {}


# ---- 基础状态 ----

POSE_TABLE["idle"] = (          # 4 帧:呼吸起伏(躯干/头沉 1px)+ 拳套微动
    _stand("stance_f", 33, 15),
    _stand("stance_f", 33, 16, torso_dy=1, head_dy=1),
    _stand("stance_f", 34, 15),
    _stand("stance_f", 33, 17, torso_dy=1, head_dy=1),
)

POSE_TABLE["walk"] = (          # 6 帧:左右腿交替完整步态环(暗P=远侧左腿,绕环可追)
    _stand("stance_f", 33, 15, legs="loco_ca", lg_dx=17),         # A触地:远(左)腿前伸落脚,双足平贴
    _stand("stance_f", 33, 16, legs="loco_ra", lg_dx=17,
           torso_dy=1, head_dy=1),                              # A压实:远腿竖直承重,近腿踮尖蹬伸
    _stand("stance_f", 34, 14, legs="loco_pa", lg_dx=18),          # A过腿:近腿从髋后提膝过位,远腿续撑
    _stand("stance_f", 32, 15, legs="loco_cb", lg_dx=16,
           torso_dx=-1, head_dx=-1, ab_dx=15),                     # B触地:近(右)腿前伸落脚,前后腿角色互换
    _stand("stance_f", 32, 16, legs="loco_rb", lg_dx=16,
           torso_dx=-1, head_dx=-1, torso_dy=1, head_dy=1,
           ab_dx=15),                                              # B压实:近腿承重,远腿踮尖蹬伸
    _stand("stance_f", 33, 14, legs="loco_pb", lg_dx=17,
           torso_dx=-1, head_dx=-1, ab_dx=15),                      # B过腿:远腿提膝,迈出接回A触地成环
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

POSE_TABLE["jump"] = (          # 3 帧:起跳收腿 → 团身最紧 → 顶点微展
    _air("air", 33, 30),                       # 离地收腿:臂前下张,目视前方
    _air("air", 32, 31, head_dy=1, lg_dx=17, lg_dy=74),   # 团身最紧:腿上提贴胸,收下颌,拳套收回
    _air("air", 34, 28, torso_dy=1, lg_dy=77),  # 顶点微展:躯干松落,腿下放,臂上浮
)

POSE_TABLE["jump_fall"] = (     # 3 帧:下落展腿 → 下沉前倾 → 触地前预备
    _air("air", 33, 32, legs="fall", lg_dx=18, lg_dy=72),        # 下落展腿(现有)
    _air("air", 34, 34, legs="fall", lg_dx=19, lg_dy=72,
         torso_dx=1, head_dx=2, head_dy=1),                      # 下沉前倾:躯干前送,低头看落点
    _air("air", 35, 35, legs="jumpkick", lg_dx=17, lg_dy=78,
         torso_dx=2, torso_dy=3, head_dx=3, head_dy=2,
         ab_dx=18, ab_dy=49),  # 触地前预备:屈膝探地,躯干下沉,双臂前撑
)

POSE_TABLE["land"] = (
    _f(("arm_kick_bal", 29, 28), ("leg_crouch", 16, 78),
        ("torso", 20, 56), ("head", 19, 44)),
)

POSE_TABLE["dash_back"] = (     # 3 帧:蹬地后撤 → 腾空后仰 → 收步落地
    _air("kick_bal", 24, 40, legs="run1", lg_dx=13, lg_dy=54,
         torso_dx=-2, torso_dy=5, head_dx=-4, head_dy=7,
         ab_dx=15, ab_dy=51),     # 蹬地后撤:大开步后撑(髋块藏马甲后),平衡臂接肩上举
    _air("raise", 30, 29, lg_dx=12, torso_dx=-3, head_dx=-5),
    _air("air", 32, 34, legs="fall", lg_dx=17, lg_dy=72,
         torso_dx=-1, head_dx=-1, head_dy=1, ab_dx=16, ab_dy=48),
)                  # 腾空后仰(臂过头后甩)→ 收步落地(展腿回正)

POSE_TABLE["intro"] = (         # 3 帧:抱拳 → 直立 → 摆开战姿(开场三拍演出)
    _f(("arm_wind", 17, 26), ("leg_stand", 18, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_wind", 31, 24)),  # 抱拳:双拳收握互撞(现有)
    _f(("arm_down", 20, 29), ("leg_closed", 17, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_down", 32, 29)),  # 直立:并腿立正,双臂贴滚边垂落
    _f(("arm_stance_b", 17, 24), ("leg_stand", 18, 54),
        ("torso", 21, 25), ("head", 21, 9),
        ("arm_stance_f", 33, 15)),  # 摆开战姿:沉腰开架,双拳抬起护卫
)

