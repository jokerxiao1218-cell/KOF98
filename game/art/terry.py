"""art/terry.py — 特瑞·伯格纸娃娃:部件字符画 + 姿势装配表(设计文档 §4.7)。

纸娃娃 = 部件字符画(头+红帽/金发/马甲躯干/手臂×姿势库/腿×姿势库/拳套/鞋)
+ 每姿势一张摆放表(部件名 → 画布坐标 dx,dy)。姿势库不逐张画满 46 键的
细节:臂/腿姿势复用 + 偏移演化,能看出"出拳/踢腿/蹲/倒地"即可(设计文档)。

约定:
  * 画布 56×100(人形姿势统一画布,脚底 = 画布底,身体轴 x≈28);
  * 所有部件按"面朝右"绘制,面朝左由 assets.sprite 整幅镜像(像素级对称);
  * 装配顺序 = 摆放表顺序(先画后臂/腿,再躯干/头,最后前臂在上层);
  * 字符 → 色:'c'红帽 'C'帽暗 'h'金发 'H'发暗 's'皮肤 'S'肤暗
    'v'马甲 'V'马甲暗 'w'白(帽字/滚边/腕带) 'g'拳套 'G'拳套暗
    'p'牛仔裤 'P'裤暗 'r'鞋红 'W'鞋白 'b'腰带 'm'金属扣 'k'黑(眼);
  * 换色:P1 红马甲 / P2 蓝马甲 只换 palette,部件形状零改动。
"""
import pygame

from . import paint, shift

CANVAS_W, CANVAS_H = 56, 100

# ---------------------------------------------------------------- 部件字符画

PARTS = {}

PARTS["head"] = [        # 头:红帽(帽檐朝后)+ 金长发后披 + 侧脸朝右
    "......ccccc.......",
    ".....ccccccc......",
    "....ccccccccc.....",
    "....ccccccccw.....",
    "...Cccccccccw.....",
    "..CCccccccccw.....",
    ".hhh.......ssss...",
    ".hhhh.....ssssss..",
    ".hhhh.....ssksss..",
    ".hhhh.....ssssss..",
    ".hhhh.....sssssss.",
    ".Hhhh......Ssss...",
    ".Hhhh.......Ss....",
    "..Hhh.......ss....",
    "..Hhh.............",
    "..Hhh.............",
    "..Hhhh............",
    "...Hhh............",
    "...Hhh............",
    "....Hh............",
]

PARTS["torso"] = [       # 无袖红马甲躯干:裸肩 + 白滚边 + 胸口白徽 + 腰带
    "........ss........",
    ".ss....ss......s..",
    ".sswvvvvvvvvw.ss..",
    "...wvvvvsssvw.....",
    "...wvvvvssvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvwvvvw.....",
    "...wvvvvwvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wvvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...wVvvvvvvvw.....",
    "...bbbbbbbbbb.....",
    "...bbbbmmbbbb.....",
]

# ---- 手臂部件(面朝右;"前臂"在画面右侧伸向对手,后臂在左侧)----
# 臂部件自带拳套(g/G),肩端画在部件底部/侧缘,由摆放表贴到躯干肩位。

PARTS["arm_stance_f"] = [  # 前臂格斗架势:肘前下折,拳套举在下巴高
    "........ggg..",
    "........ggg..",
    ".......sGG...",
    "......sss....",
    ".....sss.....",
    "....sss......",
    "...sss.......",
    "..sss........",
    ".ssss........",
    ".sss.........",
    ".sss.........",
    ".ss..........",
    ".ss..........",
    ".ss..........",
]

PARTS["arm_stance_b"] = [  # 后臂护肋:上臂贴身,前臂横折护肋
    ".ss.........",
    ".sss........",
    "..sss.......",
    "..sss.......",
    "...ss.......",
    "...sssggg...",
    "...sssGG....",
    "....sss.....",
    "....ss......",
    "....ss......",
    "...ss.......",
    "...ss.......",
    "..ss........",
    "..ss........",
]

PARTS["arm_punch"] = [    # 直拳水平全伸(拳套+白腕带在右端)
    ".ss..................",
    ".ssssssssssssssss....",
    ".sssssssssssssssswggg",
    ".sssssssssssssssswggg",
    ".ssssssssssssssss....",
    ".ss..................",
]

PARTS["arm_punch_hi"] = [  # 上位拳:臂斜上举,拳套在头侧高位
    "...............ggg",
    "...............ggg",
    "..............GG..",
    "............ssw...",
    "..........sss.....",
    "........sss.......",
    "......sss.........",
    "....sss...........",
    "..sss.............",
    ".sss..............",
    ".ss...............",
    ".ss...............",
]

PARTS["arm_wind"] = [      # 收拳预备:拳套收在胸前
    ".ss.........",
    ".sss........",
    "..sss.......",
    "..sss..gg...",
    "..sss..gg...",
    "..ssss......",
    "...sss......",
    "...sss......",
    "...ss.......",
    "...ss.......",
    "..ss........",
    "..ss........",
    ".ss.........",
    ".ss.........",
    ".ss.........",
    ".ss.........",
]

PARTS["arm_guard"] = [     # 防御:竖臂上抬护脸
    "....gg..",
    "....gg..",
    "...GG...",
    "...ss...",
    "...ss...",
    "..sss...",
    "..sss...",
    "..ss....",
    "..ss....",
    ".sss....",
    ".sss....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
]

PARTS["arm_raise"] = [     # 举臂过头(胜利/蓄力)
    "....ggg..",
    "....ggg..",
    "....GG...",
    "...ssw...",
    "...ss....",
    "...ss....",
    "...ss....",
    "...ss....",
    "...ss....",
    "...ss....",
    "..sss....",
    "..sss....",
    "..ss.....",
    "..ss.....",
    "..ss.....",
    ".sss.....",
    ".sss.....",
    ".ss......",
    ".ss......",
    ".ss......",
    ".ss......",
    ".ss......",
    ".ss......",
    ".ss......",
]

PARTS["arm_upper"] = [     # 上勾拳:拳套顶在部件上端
    "...ggg..",
    "...ggg..",
    "...GG...",
    "...ss...",
    "...ss...",
    "...ss...",
    "...ss...",
    "...ss...",
    "..sss...",
    "..sss...",
    "..ss....",
    "..ss....",
    ".sss....",
    ".sss....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
    ".ss.....",
]

PARTS["arm_kick_bal"] = [  # 踢腿时的后上平衡臂(拳套在后上)
    "..ggg..........",
    "..ggg..........",
    "...GG..........",
    "...ssw.........",
    "....ss.........",
    "....sss........",
    ".....sss.......",
    "......sss......",
    "......ss.......",
    ".......ss......",
    ".......ss......",
    "........ss.....",
    ".........ss....",
    ".........ss....",
]

PARTS["arm_air"] = [       # 空中展开臂(斜下)
    ".ss.............",
    ".sss............",
    "..sss...........",
    "...sss..........",
    "....sss.........",
    ".....sss........",
    "......sss.......",
    ".......sssggg...",
    "..........GGG...",
]

PARTS["arm_grab"] = [      # 前抓臂(投技伸出)
    ".ss.............",
    ".sss....ggggg...",
    ".ssssssssssggg..",
    ".ssssssssssggg..",
    ".sss....ggggg...",
    ".ss.............",
]

PARTS["arm_slam"] = [      # 砸地双臂(双拳向下合砸)
    ".ss..............ss.",
    ".ssss..........sss..",
    "..sss........ssss...",
    "...ssss.....ssss....",
    "....ssss...ssss.....",
    ".....ssssssss.......",
    "......ssssss........",
    "......ssssss........",
    ".......ssss.........",
    "........ggg.........",
    "........ggg.........",
    "........GGG.........",
]

PARTS["arm_low"] = [       # 蹲姿前下伸臂(低位的拳)
    ".ss.........",
    ".sss........",
    "..sss.......",
    "...sss......",
    "....sss.....",
    ".....sssgg..",
    ".......ggg..",
    ".......ggg..",
    ".......GGG..",
]

PARTS["arm_down"] = [      # 垂臂(败者)
    ".ss.......",
    ".sss......",
    ".sss......",
    "..sss.....",
    "..sss.....",
    "..ss......",
    "..ss......",
    "..ss......",
    "..ss......",
    "..ss......",
    "..ss......",
    "..ss......",
    "..gg......",
    "..gg......",
    "..GG......",
]

# ---- 腿部件(含红白运动鞋;腰接部件顶,脚底 = 部件底,全长 46 高)----
# 站姿族腿部件统一 46 高(腰 y0 → 脚底 y45),姿势差异画在部件内部;
# 蹲/空中族(蹲 24 高、蜷 24 高等)由摆放表把躯干相应下移压低身高。

PARTS["leg_stand"] = [     # 站立微分开(后腿略后)
    ".....ppppppppp......",
    ".....ppppppppp......",
    ".....ppppppppp......",
    ".....Ppppppppp......",
    ".....Ppppppppp......",
    ".....Ppppppppp......",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....PPP.....PPP....",
    ".....PPP.....PPP....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....Ppp.....ppp....",
    ".....rrr.....rrr....",
    "....rrrr....rrrr....",
    "....rrwr....rrwr....",
    "....rrrr....rrrr....",
    "....rrrr....rrrr....",
    "...WWWW....WWWWW....",
    "...WWWW....WWWWW....",
]

PARTS["leg_closed"] = [    # 并腿(蓄跳/被投)
    "....pppppp....",
    "....pppppp....",
    "....pppppp....",
    "....Ppppp.....",
    "....Ppppp.....",
    "....Ppppp.....",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....PPP.......",
    "....PPP.......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....Pppp......",
    "....rrr.......",
    "...rrrr.......",
    "...rrwr.......",
    "...rrrr.......",
    "...rrrr.......",
    "..WWWWW.......",
    "..WWWWW.......",
]

PARTS["leg_walk1"] = [     # 迈步:后蹬前迈
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    "......Ppppppppp.....",
    ".....Ppp......ppp...",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......PPP......PPP..",
    "......PPP......PPP..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......Ppp......ppp..",
    "......rrr......rrr..",
    ".....rrrr.....rrrr..",
    ".....rrwr.....rrwr..",
    ".....rrrr.....rrrr..",
    ".....rrrr.....rrrr..",
    "....WWWW.....WWWWW..",
    "....WWWW.....WWWWW..",
]

PARTS["leg_run1"] = [      # 跑步大跨步:前后腿都斜,大幅张开
    "........ppppppppp...........",
    "........ppppppppp...........",
    "........ppppppppp...........",
    "........Ppppppppp...........",
    "........Ppppppppp...........",
    "........Ppppppppp...........",
    ".......Ppp.......ppp........",
    "......Ppp........ppp........",
    "......Ppp........ppp........",
    ".....Ppp..........ppp.......",
    ".....Ppp..........ppp.......",
    ".....Ppp..........ppp.......",
    "....Ppp............ppp......",
    "....Ppp............ppp......",
    "....Ppp............ppp......",
    "....Ppp.............ppp.....",
    "....Ppp.............ppp.....",
    "....Ppp.............ppp.....",
    "...Ppp...............ppp....",
    "...Ppp...............ppp....",
    "...Ppp.............ppp......",
    "...Ppp.............ppp......",
    "...Ppp..............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp..............ppp......",
    "..Ppp..............ppp......",
    "..Ppp..............ppp......",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..Ppp...............ppp.....",
    "..rrr................rrr....",
    ".rrrr................rrrr...",
    ".rrwr................rrwr...",
    ".rrrr................rrrr...",
    ".rrrr................rrrr...",
    "WWWW.................WWWWW..",
    "WWWW.................WWWWW..",
]

PARTS["leg_run2"] = [      # 跑步腾空帧:前膝抬、后腿拖
    ".....ppppppppp.......",
    ".....ppppppppp.......",
    ".....ppppppppp.......",
    ".....Ppppppppp.......",
    ".....Ppppppppp.......",
    ".....Ppppppppp.......",
    ".....Ppp...ppppppp...",
    ".....Ppp...ppppppp...",
    ".....Ppp...ppppppp...",
    ".....Ppp...pppppp....",
    ".....Ppp...pppppp....",
    ".....Ppp...pppppp....",
    ".....Ppp....ppp......",
    ".....Ppp....ppp......",
    ".....Ppp....ppp......",
    ".....Ppp....ppp......",
    ".....Ppp....ppp......",
    ".....Ppp....ppp......",
    "....Pppp....ppp......",
    "....Pppp....ppp......",
    "....Pppp....ppp......",
    "....Pppp....ppp......",
    "....Pppp....ppp......",
    "....Pppp....ppp......",
    "....Ppp.....ppp......",
    "....Ppp.....ppp......",
    "....Ppp.....ppp......",
    "....Ppp.....ppp......",
    "....Ppp.....ppp......",
    "...Pppp.....ppp......",
    "...Pppp.....ppp......",
    "...Pppp.....ppp......",
    "...Pppp.....ppp......",
    "...Ppp......ppp......",
    "...Ppp......ppp......",
    "...Ppp......ppp......",
    "...Ppp......ppp......",
    "...Ppp......ppp......",
    "...rrr.....rrr.......",
    "..rrrr.....rrrr......",
    "..rrwr.....rrwr......",
    "..rrrr.....rrrr......",
    "..rrrr.....rrrr......",
    ".WWWW......WWWW......",
    ".WWWW......WWWW......",
]

PARTS["leg_crouch"] = [    # 蹲:大腿水平前伸,小腿竖直
    ".....ppppppppp........",
    ".....ppppppppp........",
    ".....ppppppppp........",
    "....Pppppppppp........",
    "....Pppppppppp........",
    "....Pppppppppp........",
    "....Ppppppppppppppp...",
    "....Ppppppppppppppp...",
    "....Ppppppppppppppp...",
    "....Ppppppppppppppp...",
    "....Ppppppppppppppp...",
    "....Ppppppppppppppp...",
    "...............ppp....",
    "...............ppp....",
    "...............ppp....",
    "...............ppp....",
    "...............ppp....",
    "..............rrrr....",
    "..............rrwr....",
    ".............rrrrr....",
    ".............WWWWW....",
    ".............WWWWW....",
]

PARTS["leg_crouch_kick"] = [  # 蹲姿踢小腿:低位水平前伸(扫前的小踢)
    ".....ppppppppp........",
    ".....ppppppppp........",
    ".....ppppppppp........",
    "....Pppppppppp........",
    "....Pppppppppp........",
    "....Pppppppppp........",
    "....Pppppppppppppp....",
    "....Pppppppppppppp....",
    "....Pppppppppppppp....",
    "....Pppppppppppppp....",
    "....Pppppppppppppp....",
    "....Pppppppppppppp....",
    "...........ppppppp....",
    "...........ppppppp....",
    "...........ppppppp....",
    "...........ppppppp....",
    "......................",
    "...............rrrrr..",
    "...............rrwrr..",
    "...............rrwrr..",
    "...............WWWWWW.",
    "...............WWWWWW.",
]

PARTS["leg_sweep"] = [     # 扫堂腿:一腿全伸贴地横扫,一腿折叠跪撑
    ".....pppppppp...................",
    ".....pppppppp...................",
    ".....pppppppp...................",
    "....Pppppppp....................",
    "....Pppppppp....................",
    "....Pppppppp....................",
    "....Ppppppppppppppppppppppp.....",
    "....Ppppppppppppppppppppppp.....",
    "....Ppppppppppppppppppppppp.....",
    "....Ppppppppppppppppppppppp.....",
    "....Ppppppppppppppppppppppp.....",
    "....Ppppppppppppppppppppppp.....",
    ".....pppp..................rrrr.",
    ".....pppp..................rrwrr",
    ".....pppp..................rrwrr",
    ".....rrr...................WWWWW",
    ".....rrr...................WWWWW",
    "....WWWW...................WWWW.",
]

PARTS["leg_kneel"] = [     # 半跪:后腿跪地,前腿撑地(起身/砸地用)
    ".....ppppppppp..........",
    ".....ppppppppp..........",
    ".....ppppppppp..........",
    "....Ppppppppp...........",
    "....Ppppppppp...........",
    "....Ppppppppp...........",
    "....Pppp................",
    "....Pppp................",
    "....Pppp................",
    "....Pppp................",
    "....Pppp...pppp.........",
    "....Pppp...pppp.........",
    "....Pppp...pppp.........",
    "....Pppp...pppp.........",
    "...........ppp..........",
    "...........ppp..........",
    "...........ppp..........",
    "...........ppp..........",
    "...........ppp..........",
    "...........ppp..........",
    "...........ppp..........",
    "..........ppp...........",
    "..........ppp...........",
    "..........ppp...........",
    "..........ppp...........",
    "..........rrr...........",
    "..........rrr...........",
    ".........rrrr...........",
    ".........rrwr...........",
    ".........rrrr...........",
    ".........WWWW...........",
    ".........WWWW...........",
]

PARTS["leg_tuck"] = [      # 空中蜷腿(跳起团身)
    "......pppppppppp.......",
    "......pppppppppp.......",
    "......pppppppppp.......",
    ".....Ppppppppppp.......",
    ".....Ppppppppppp.......",
    ".....Ppppppppppp.......",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    "......pppppppp.........",
    ".....ppppppppp.........",
    ".....ppppppppp.........",
    ".....rrrr...rrrr.......",
    ".....rrrr...rrrr.......",
    ".....rrwr...rrwr.......",
    ".....rrrr...rrrr.......",
    "....WWWWW...WWWWW......",
    "....WWWWW...WWWWW......",
]

PARTS["leg_jumpkick"] = [  # 空中踢:一腿斜下全伸(带鞋),一腿蜷
    "........pppppppppp..........",
    "........pppppppppp..........",
    "........pppppppppp..........",
    ".......Ppppppppppp..........",
    ".......Ppppppppppp..........",
    ".......Ppppppppppp..........",
    "......Ppp....ppp............",
    "......Ppp....ppp............",
    "......Ppp.....ppp...........",
    ".....Ppp.....ppp............",
    ".....Ppp......ppp...........",
    ".....Ppp......ppp...........",
    "....Ppp.......ppp...........",
    "....Ppp.......ppp...........",
    "....rrr.......ppp...........",
    "....rrwr......ppp...........",
    "....rrwr......rrrr..........",
    "....rrrr......rrwrr.........",
    "...WWWW......rrwrr..........",
    "...WWWW......WWWWW..........",
    ".............WWWWW..........",
    ".............WWWWW..........",
]

PARTS["leg_sidekick"] = [   # 站姿横踢:前腿水平全伸,支撑腿直立
    "........pppppppppp..............",
    "........pppppppppp..............",
    "........pppppppppp..............",
    ".......Ppppppppppp..............",
    ".......Ppppppppppp..............",
    ".......Ppppppppppp..............",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "......Ppppppppppppppppppppp.....",
    "..........................rrrr..",
    "..........................rrwrr.",
    "..........................rrwrr.",
    "..........................rrrrr.",
    "..........................WWWWW.",
    "..........................WWWWW.",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......Ppp.......................",
    "......rrr.......................",
    "......rrr.......................",
    ".....rrrr.......................",
    ".....rrwr.......................",
    ".....rrwr.......................",
    ".....rrrr.......................",
    "....WWWWW.......................",
    "....WWWWW.......................",
    "....WWWWW.......................",
    "....WWWWW.......................",
    "....WWWWW.......................",
    "....WWWWW.......................",
]
PARTS["leg_knee"] = [      # 提膝:前膝抬起,支撑腿全长
    "....pppppppppp......",
    "....pppppppppp......",
    "....pppppppppp......",
    "....Pppppppppp......",
    "....Pppppppppp......",
    "....Pppppppppp......",
    "....Ppp...pppppp....",
    "....Ppp...pppppp....",
    "....Ppp...pppppp....",
    "....Ppp...pppppp....",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....ppp......",
    "....Ppp....rrr......",
    "....Ppp....rrr......",
    "....Ppp....rrr......",
    "....Ppp....rrr......",
    "....Ppp...rrrr......",
    "....Ppp...rrwr......",
    "....Ppp...rrrr......",
    "....Ppp...rrrr......",
    "....Ppp....ww.......",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....Ppp.............",
    "....rrr.............",
    "...rrrr.............",
    "...rrwr.............",
    "...rrrr.............",
    "..WWWWW.............",
    "..WWWWW.............",
]

PARTS["leg_fall"] = [      # 下落:双腿微张下探
    ".....pppppppp......",
    ".....pppppppp......",
    ".....pppppppp......",
    "....Ppppppppp......",
    "....Ppppppppp......",
    "....Ppppppppp......",
    "....Ppp....ppp.....",
    "....Ppp....ppp.....",
    "....Ppp....ppp.....",
    "....Ppp....ppp.....",
    "...Ppp.....ppp.....",
    "...Ppp.....ppp.....",
    "...Ppp.....ppp.....",
    "...Ppp.....ppp.....",
    "..Ppp......ppp.....",
    "..Ppp......ppp.....",
    "..Ppp......ppp.....",
    "..Ppp......ppp.....",
    "..rrr......rrr.....",
    "..rrr......rrr.....",
    "..rrr......rrr.....",
    "..rrr......rrr.....",
    ".rrrr......rrrr....",
    ".rrwr......rrwr....",
    ".rrrr......rrrr....",
    ".rrrr......rrrr....",
    "WWWW.......WWWW....",
    "WWWW.......WWWW....",
]

# ---- 整体部件(大幅变形的姿势:倒地/被投/翻滚,单独整画)----

PARTS["body_lie"] = [      # 倒地蜷缩:红帽金发在左,马甲/蜷腿/红白鞋向右
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
    "....hh...bbbbppppppppppppppppppp..............",
    "....hh...bbppppppppppppppppppppp..............",
    "....hh...bpppppppppppppppppppppp..............",
    "....hh..bppppppppppppppppppppppp..............",
    "....hh..bpppp..pppppppppppppppp...............",
    "....hh.bpppp....ppppppppppppppp...............",
    "....hh.bppp......ppppppppppppppp..............",
    "....hh.bppp......ppppppppppp.rrrr.............",
    "....hh.bppp.....ppppppppppprrwrr..............",
    "....hh.bppp.....ppppppppp.rrwrr...............",
    "....hh.bppp....ppppppppppWWWWWW...............",
    "....hh.bppp...pppppppp..WWWWWW................",
    "....hh.bppp..ppppppp..........................",
    "....hh.bppp.pppppp............................",
    "....hh.bppppppppp.............................",
    "....hh.bppppppp...............................",
]

PARTS["body_fall1"] = [    # 空中翻滚下坠(相位一):后仰蜷缩
    ".............ccccc.......................",
    "............ccccccc......................",
    "...........ccccccccc.....................",
    "...h.......Ccccccccccw...................",
    "...hh......hhssssssss....................",
    "...hhh....hhhsssssssss...................",
    "...hhhh..hhhh..sssss.....................",
    "...hhhhhhhhhh................wvvvvvvvvw..",
    "....hhhhhhhhh...............wvvvvvvvvw...",
    ".....hhhhhhh................wvvvvvvvvw...",
    "......hhh...................wvvvvvvvvw...",
    ".......ss....................bbbbbbbpp...",
    ".......sss.................bppppppppppp..",
    "........sss..............bppppppppppppp..",
    ".........ss............ppppppppppppppp...",
    "..........ss...........pppp....ppppppp...",
    "...........s..........pppp......ppppp....",
    "......................pppp.......pprrr...",
    "......................ppp........pprrwr..",
    ".....................pppp........pprrr...",
    "....................pppp.........pWWWWW..",
    "...................pppp..........p.......",
    "..................pppp...........pp......",
    ".................pppp............pp......",
    "................pppp.............rrr.....",
    "..............pppp..............WWWW.....",
    "............ppppp..............WWWW......",
    "...........ppppp.........................",
    "..........ppppp..........................",
    ".........ppppp...........................",
]

PARTS["body_fall2"] = [    # 空中翻滚下坠(相位二):腿相位变化
    ".............ccccc.......................",
    "............ccccccc......................",
    "...........ccccccccc.....................",
    "...h.......Ccccccccccw...................",
    "...hh......hhssssssss....................",
    "...hhh....hhhsssssssss...................",
    "...hhhh..hhhh..sssss.....................",
    "...hhhhhhhhhh................wvvvvvvvvw..",
    "....hhhhhhhhh...............wvvvvvvvvw...",
    ".....hhhhhhh................wvvvvvvvvw...",
    "......hhh...................wvvvvvvvvw...",
    ".......ss....................bbbbbbbpp...",
    ".......sss.................bppppppppppp..",
    "........sss..............bppppppppppppp..",
    ".........ss............ppppppppppppppp...",
    "..........ss...........pppp..ppppppppp...",
    "...........s..........pppp....pppppppp...",
    "......................pppp.....pppprrr...",
    "......................ppp......pppprrwr..",
    ".....................pppp......pppprrr...",
    "....................pppp.......ppWWWWW...",
    "...................pppp..........p.......",
    "..................pppp...........pp......",
    ".................pppp............pp......",
    "................pppp.............pp......",
    "..............pppp..............rrrr.....",
    "............ppppp..............WWWW......",
    "...........ppppp..............WWWW.......",
    "..........ppppp..........................",
    ".........ppppp...........................",
]

PARTS["body_thrown"] = [   # 被投飞出:身体前扑蜷缩(头朝右下)
    "...........................hhhh.......",
    ".........................hhhssssss....",
    "...................cccccchhhssssss....",
    ".................ccccccchhsssssss.....",
    "................cccccccchhsssssssss...",
    "...............Ccccccccccwsssssssss...",
    "..............Ccccccccccw.sssssssss...",
    ".............wvvvvvvvvvw..sssssss.....",
    "............wvvvvvvvvvw...sssss.......",
    "...........wvvvvvvvvvw....sss.........",
    "..........wvvvvvvvvvw.................",
    "..........wvvvvvvvvvw.................",
    "..........wvvvvvvvvvw.................",
    "...........bbbbbbbb...................",
    "........bppppppppppb..................",
    "......bppppppppppppppp................",
    "....bppppppppppppppppppp..............",
    "...ppppppppp..ppppppppppp.............",
    "..ppppppppp....pppppppppppp...........",
    ".ppppppppp......ppppppppppppp.........",
    "ppppppppp........pppp..ppppppp........",
    "ppppppp..........pppp....pppppp.......",
    "ppppp............pppp.....ppppp.......",
    "pppp............pppp.......ppp.rrr....",
    "ppp............pppp........ppp.rrwr...",
    "pp............pppp.........ppp.rrrr...",
    "p............pppp..........pppWWWWW...",
    "............pppp...........pppp.......",
    "...........pppp............pppp.......",
    "..........ppppp............ppppp......",
]

# ---------------------------------------------------------------- 调色板
# 传入角色 palette(PALETTES.P1/P2 的 8 个基础键),补出部件字符用的全部色。

_REQUIRED = ("cap", "hair", "vest", "skin", "glove", "pants", "shoe", "shoe_white")


def normalize_palette(pal):
    """8 个基础键缺一不可;补出单字符部件色 + 固定色(黑白/腰带/金属)。"""
    missing = [k for k in _REQUIRED if k not in pal]
    if missing:
        raise ValueError(f"调色板缺基础色 {missing},应有 {list(_REQUIRED)}")
    out = dict(pal)
    for k in _REQUIRED:
        v = pal[k]
        if not isinstance(v, (tuple, list)) or len(v) != 3 or \
                not all(isinstance(c, int) and not isinstance(c, bool) for c in v):
            raise ValueError(f"调色板 {k} 应为 (R,G,B) 整数三元组,得到 {v!r}")
    out.update({
        "c": tuple(pal["cap"]),      "C": shift(pal["cap"], 0.62),
        "h": tuple(pal["hair"]),     "H": shift(pal["hair"], 0.66),
        "s": tuple(pal["skin"]),     "S": shift(pal["skin"], 0.74),
        "v": tuple(pal["vest"]),     "V": shift(pal["vest"], 0.62),
        "g": tuple(pal["glove"]),    "G": shift(pal["glove"], 0.62),
        "p": tuple(pal["pants"]),    "P": shift(pal["pants"], 0.62),
        "r": tuple(pal["shoe"]),     "W": tuple(pal["shoe_white"]),
        "w": (240, 240, 240),        "b": (58, 42, 30),
        "m": (176, 176, 186),        "k": (22, 18, 20),
    })
    return out


def palette_id(pal):
    """调色板的缓存标识(排序后固化,同色同 id)。"""
    return tuple(sorted((k, tuple(v)) for k, v in pal.items()))


# ---------------------------------------------------------------- 姿势装配表
# 一帧 = 部件摆放序列(名字, dx, dy);顺序即绘制顺序(后画的盖前画的)。
# 基准坐标(画布 56×100,面朝右):torso (20,24) / head (19,8) / leg (18,54),
# 脚底 = 画布底;攻击键帧序按 startup→active→recovery 演化。

def _f(*parts):
    return tuple(parts)


def _stand(arm_f, af_dx, af_dy, arm_b="stance_b", ab_dx=17, ab_dy=24,
           legs="stand", lg_dx=18, lg_dy=54,
           head_dx=0, head_dy=0, torso_dx=0, torso_dy=0):
    """站姿骨架:后臂→腿→躯干→头→前臂。"""
    return _f(
        ("arm_" + arm_b, ab_dx, ab_dy),
        ("leg_" + legs, lg_dx, lg_dy),
        ("torso", 20 + torso_dx, 24 + torso_dy),
        ("head", 19 + head_dx, 8 + head_dy),
        ("arm_" + arm_f, af_dx, af_dy),
    )


def _crouch(arm_f, af_dx, af_dy, arm_b="stance_b", ab_dx=17, ab_dy=52,
            legs="crouch", lg_dx=16, lg_dy=76,
            head_dx=0, head_dy=0, torso_dx=0, torso_dy=0):
    """蹲姿骨架:腿 24 高贴地,躯干压到 56 起,头 44 起(总高约 56)。"""
    return _f(
        ("arm_" + arm_b, ab_dx, ab_dy),
        ("leg_" + legs, lg_dx, lg_dy),
        ("torso", 20 + torso_dx, 56 + torso_dy),
        ("head", 19 + head_dx, 44 + head_dy),
        ("arm_" + arm_f, af_dx, af_dy),
    )


def _air(arm_f, af_dx, af_dy, legs="tuck", lg_dx=16, lg_dy=76,
         arm_b="stance_b", ab_dx=17, ab_dy=46,
         head_dx=0, head_dy=0, torso_dx=0, torso_dy=0):
    """空中骨架:躯干下移接 24 高的蜷腿(团身)。"""
    return _f(
        ("arm_" + arm_b, ab_dx, ab_dy),
        ("leg_" + legs, lg_dx, lg_dy),
        ("torso", 20 + torso_dx, 46 + torso_dy),
        ("head", 19 + head_dx, 30 + head_dy),
        ("arm_" + arm_f, af_dx, af_dy),
    )


POSES = {}

# ---- 基础状态 ----

POSES["idle"] = (          # 4 帧:呼吸起伏(躯干/头沉 1px)+ 拳套微动
    _stand("stance_f", 33, 15),
    _stand("stance_f", 33, 16, torso_dy=1, head_dy=1),
    _stand("stance_f", 34, 15),
    _stand("stance_f", 33, 17, torso_dy=1, head_dy=1),
)

POSES["walk"] = (          # 4 帧:迈步/过渡交替
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=17),
    _stand("stance_f", 33, 16, torso_dy=1, head_dy=1),
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=16),
    _stand("stance_f", 34, 16, torso_dy=1, head_dy=1, lg_dx=19),
)

POSES["run"] = (           # 6 帧:大跨→腾空→过渡 ×2(前倾,摆臂)
    _stand("stance_f", 33, 15, legs="run1", lg_dx=13, head_dx=3, torso_dx=2),
    _stand("punch", 34, 26, legs="run2", lg_dx=15, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 16, legs="walk1", lg_dx=14, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 15, legs="run1", lg_dx=13, head_dx=3, torso_dx=2),
    _stand("stance_f", 33, 16, legs="run2", lg_dx=15, head_dx=3, torso_dx=2, ab_dx=14),
    _stand("stance_f", 33, 15, legs="walk1", lg_dx=15, head_dx=3, torso_dx=2),
)

POSES["crouch"] = (
    _crouch("low", 31, 58),
)

POSES["stand_block"] = (
    _stand("guard", 32, 16, torso_dy=2, head_dy=2),
)

POSES["crouch_block"] = (
    _crouch("guard", 31, 46),
)

POSES["prejump"] = (
    _f(("arm_kick_bal", 29, 26), ("leg_closed", 18, 54),
        ("torso", 20, 26), ("head", 19, 10)),
)

POSES["jump"] = (          # 2 帧:团身上升
    _air("air", 33, 30),
    _air("air", 33, 32, head_dy=-1),
)

POSES["jump_fall"] = (     # 2 帧:双腿下探
    _air("air", 33, 32, legs="fall", lg_dx=18, lg_dy=72),
    _air("air", 33, 34, legs="fall", lg_dx=18, lg_dy=72, head_dy=-1),
)

POSES["land"] = (
    _f(("arm_kick_bal", 29, 28), ("leg_crouch", 16, 76),
        ("torso", 20, 56), ("head", 19, 44)),
)

POSES["air_hit"] = (
    _air("air", 31, 28, lg_dx=12, torso_dx=-1, head_dx=-6),
)

POSES["fall"] = (
    _f(("body_fall1", 10, 70)),
    _f(("body_fall2", 10, 70)),
)

POSES["knockdown"] = (
    _f(("body_lie", 5, 73)),
)

POSES["wakeup"] = (
    _f(("arm_stance_b", 19, 48), ("leg_kneel", 16, 68),
        ("torso", 20, 48), ("head", 19, 34), ("arm_stance_f", 31, 38)),
)

POSES["hit_high"] = (      # 2 帧:逐帧后仰
    _f(("arm_air", 29, 26), ("leg_stand", 18, 54),
        ("torso", 18, 24), ("head", 15, 10)),
    _f(("arm_air", 27, 28), ("leg_walk1", 16, 54),
        ("torso", 16, 26), ("head", 12, 12)),
)

POSES["hit_low"] = (
    _f(("arm_low", 27, 40), ("leg_stand", 18, 54),
        ("torso", 22, 26), ("head", 24, 18)),
)

POSES["dash_back"] = (
    _air("kick_bal", 25, 26, lg_dx=12, torso_dx=-3, head_dx=-5),
    _air("kick_bal", 24, 27, lg_dx=12, torso_dx=-4, head_dx=-6),
)

POSES["throw_whiff"] = (
    _stand("grab", 31, 24),
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
)

POSES["throw_grab"] = (
    _stand("grab", 34, 26, torso_dx=1, head_dx=1),
    _f(("arm_stance_b", 17, 24), ("leg_run1", 14, 54),
        ("torso", 21, 24), ("head", 21, 8), ("arm_grab", 35, 24)),
)

POSES["thrown"] = (
    _f(("body_thrown", 10, 70)),
)

POSES["win"] = (
    _f(("arm_stance_b", 17, 24), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 19, 7), ("arm_raise", 31, 2)),
)

POSES["lose"] = (
    _f(("arm_down", 15, 28), ("leg_stand", 18, 54),
        ("torso", 20, 26), ("head", 18, 12), ("arm_down", 32, 28)),
)

POSES["intro"] = (         # 2 帧:双拳合握互撞(拍拳套开场)
    _f(("arm_wind", 17, 26), ("leg_stand", 18, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_wind", 31, 24)),
    _f(("arm_wind", 18, 27), ("leg_stand", 18, 54),
        ("torso", 20, 24), ("head", 19, 8), ("arm_wind", 32, 25)),
)

# ---- 普通技(startup→active→recovery)----

POSES["st_A"] = (
    _stand("wind", 31, 22),
    _stand("punch", 34, 24, legs="run1", lg_dx=14, torso_dx=1, head_dx=2),
)

POSES["st_B"] = (
    _stand("stance_f", 33, 15, legs="knee", lg_dx=16),
    _f(("arm_kick_bal", 25, 26), ("leg_sidekick", 12, 54),
        ("torso", 18, 26), ("head", 16, 10), ("arm_air", 29, 30)),
)

POSES["st_C"] = (
    _stand("wind", 31, 22),
    _stand("punch_hi", 33, 14, legs="run1", lg_dx=13, torso_dx=1, head_dx=2),
    _stand("stance_f", 33, 15),
)

POSES["st_D"] = (
    _stand("stance_f", 33, 15, legs="knee", lg_dx=16),
    _f(("arm_kick_bal", 24, 26), ("leg_sidekick", 11, 54),
        ("torso", 17, 26), ("head", 14, 10), ("arm_air", 28, 30)),
    _stand("stance_f", 33, 15, legs="knee", lg_dx=17),
)

POSES["cr_A"] = (
    _crouch("low", 31, 58),
    _crouch("low", 35, 56),
)

POSES["cr_B"] = (
    _crouch("low", 31, 58),
    _crouch("low", 33, 60, legs="crouch_kick", lg_dx=15),
)

POSES["cr_C"] = (
    _crouch("low", 31, 58),
    _crouch("upper", 33, 40),
)

POSES["cr_D"] = (
    _crouch("wind", 31, 56),
    _f(("arm_stance_b", 21, 54), ("leg_sweep", 9, 82),
        ("torso", 24, 58), ("head", 23, 46), ("arm_low", 31, 60)),
    _crouch("low", 33, 58, legs="crouch_kick", lg_dx=15),
)

POSES["j_A"] = (
    _air("air", 33, 30),
    _air("punch_hi", 33, 28, head_dx=1),
)

POSES["j_B"] = (
    _air("air", 33, 32),
    _air("air", 33, 32, legs="jumpkick", lg_dx=12),
)

POSES["j_C"] = (
    _air("air", 33, 30),
    _air("air", 33, 32, legs="jumpkick", lg_dx=10),
    _air("punch_hi", 33, 28, legs="jumpkick", lg_dx=13),
)

POSES["j_D"] = (
    _air("air", 33, 32),
    _air("punch_hi", 34, 26, legs="jumpkick", lg_dx=9),
    _air("punch_hi", 33, 28, legs="jumpkick", lg_dx=12, head_dx=1),
)

# ---- 必杀/超杀 ----

POSES["power_wave"] = (    # 3 帧:后蓄→双掌前推→收
    _stand("wind", 31, 22, arm_b="wind", ab_dx=17, ab_dy=26),
    _f(("arm_punch", 19, 26), ("leg_run1", 13, 54),
        ("torso", 21, 24), ("head", 21, 8), ("arm_punch", 33, 24)),
    _stand("stance_f", 33, 15),
)

POSES["burn_knuckle"] = (  # 4 帧:蹲蓄→前冲拳→全伸→收
    _crouch("wind", 31, 56),
    _stand("punch", 34, 24, legs="run1", lg_dx=13, torso_dx=2, head_dx=3),
    _stand("punch_hi", 34, 14, legs="run1", lg_dx=14, torso_dx=2, head_dx=3),
    _stand("stance_f", 33, 15),
)

POSES["crack_shoot"] = (   # 4 帧:空中弧线踢(团身→横踢→换相位→收)
    _air("air", 33, 30),
    _air("air", 33, 32, legs="jumpkick", lg_dx=12),
    _air("punch_hi", 33, 28, legs="jumpkick", lg_dx=9, head_dx=1),
    _air("air", 33, 32, legs="jumpkick", lg_dx=14),
)

POSES["rising_tackle"] = (  # 4 帧:上升螺旋(头/拳交替模拟旋转)
    _air("upper", 31, 26),
    _air("punch_hi", 34, 24, lg_dx=15, head_dx=-3, torso_dx=1),
    _air("upper", 29, 26, lg_dx=14, head_dx=3, torso_dx=-1),
    _air("air", 33, 30, lg_dx=15, head_dx=-2),
)

POSES["power_dunk"] = (    # 5 帧:蹲蓄→升→空中举拳→下砸→落地
    _crouch("wind", 31, 56),
    _air("upper", 31, 26),
    _air("punch_hi", 33, 24),
    _air("slam", 26, 32),
    _crouch("slam", 26, 56, legs="crouch_kick", lg_dx=15),
)

POSES["power_geyser"] = (  # 5 帧:蹲蓄→跪砸地→爆发挺举→保持→收
    _crouch("wind", 31, 56, arm_b="wind", ab_dx=17, ab_dy=58),
    _f(("arm_slam", 22, 62), ("leg_kneel", 16, 68),
        ("torso", 20, 48), ("head", 21, 32)),
    _f(("arm_raise", 15, 0), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 19, 7), ("arm_raise", 31, 2)),
    _f(("arm_raise", 14, 1), ("leg_stand", 18, 54),
        ("torso", 20, 23), ("head", 20, 6), ("arm_raise", 32, 2)),
    _stand("stance_f", 33, 15),
)


# ---------------------------------------------------------------- 装配

_part_cache = {}


def _part(name, pal_id, pal):
    """部件 Surface 缓存(同部件同配色只画一次)。"""
    key = (name, pal_id)
    if key not in _part_cache:
        _part_cache[key] = paint(name, PARTS[name], pal)
    return _part_cache[key]


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
