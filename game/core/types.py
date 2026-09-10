"""core/types.py — 全模块共享的冻结契约(设计文档 §5.1)。

并行纪律:
  * 组 A 各模块只许 import 本文件,禁止修改;契约要改必须回报主会话,
    统一改设计文档并同步受影响模块重新验收。
  * 本文件零 pygame 依赖(core 层纪律)。

全项目统一约定(所有模块必须遵守):
  * 帧号一律 0 起算,60 帧 = 1 秒(逻辑帧锁 60fps,system.json 的 fps 固定 60)。
  * Box 坐标:相对角色"脚底中心"、面朝右;x 向右为正、y 向上为正(0=脚底),
    要求 x2>x1、y2>y1 且 y1>=0(不许有伸到地底下的框);面朝左时用 Box.mirrored 镜像。
  * 速度:vx 右正左负;vy 上正下负(所以重力是负数,loader 强制校验 gravity<0)。
    system.json 里 walk.back / jump.back_vx / dash_back.vx 存"正数大小",
    语义是"向后退/向身后跳",方向由使用方乘朝向。
  * 指令记法:数字键盘方位(2=↓ 3=↘ 6=→ 4=← 1=↙ 8=↑),相对角色朝向,
    面朝左时由 motion.py 换算(镜像问题在输入层一次解决)。

input 字段约定(terry.json 的 MoveDef.input,键名冻结):
  {"type": "button",  "button": "A"}                          普通技(站姿随 MoveDef.stance)
  {"type": "motion",  "pattern": ["2","3","6"], "button": "A"}   指令技
  {"type": "charge",  "charge_dir": "2", "release_dir": "8", "button": "C"}  蓄力技
  {"type": "throw",   "dir": "fwd"|"back", "button": "C"}      投技(投距看 MoveDef.throw_range)

motion 字段约定(必杀技的移动参数,键名冻结):
  {"vx", "vy0", "frames", "from_frame", "until"}
  until ∈ {"land"(落地为止), "frames"(维持 frames 帧)};from_frame 缺省=0(出招即起效)。
  投技把受害者向前/向后抛 40px(相对攻方朝向,input.dir 决定),由 fighter 侧实现。

projectile 字段约定(发波招,键名冻结):{"speed", "box", "max_count"}
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Dir(Enum):
    """绝对方向(物理屏幕方向;角色"前后"由 motion.py 按 facing 换算)。"""

    L = "L"
    R = "R"
    U = "U"
    D = "D"


class Btn(Enum):
    """攻击四键(拳皇经典:A 轻拳 / B 轻脚 / C 重拳 / D 重脚)。"""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Side(Enum):
    P1 = "P1"
    P2 = "P2"


@dataclass(frozen=True)
class Tick:
    """一帧的完整输入(键盘和 AI 都产出这个,进同一管线)。"""

    dirs: frozenset  # frozenset[Dir]  本帧按住的方向
    pressed: frozenset  # frozenset[Btn]  本帧按下的按钮(边沿)
    released: frozenset  # frozenset[Btn]  本帧抬起的按钮(边沿)


EMPTY_TICK = Tick(frozenset(), frozenset(), frozenset())


@dataclass(frozen=True)
class FrameTriggers:
    """motion.py 每帧的识别输出(fighter 消费)。

    specials 保证 ≤1 条(长指令优先:双 QCF 压过单 QCF),fighter 取第一条即走。
    """

    specials: tuple  # tuple[str, ...]  本帧触发的必杀/超杀 move_id
    dash_fwd: bool  # 本帧触发前冲(双击前方向,窗口内)
    dash_back: bool  # 本帧触发后撤(双击后方向)


EMPTY_TRIGGERS = FrameTriggers((), False, False)


@dataclass(frozen=True)
class Box:
    """判定框(相对脚底中心、面朝右、y 向上为正)。"""

    x1: int
    y1: int
    x2: int
    y2: int

    def overlaps(self, other: "Box") -> bool:
        return (
            self.x1 < other.x2
            and other.x1 < self.x2
            and self.y1 < other.y2
            and other.y1 < self.y2
        )

    def mirrored(self) -> "Box":
        """面朝左时的 x 镜像(x1<x2 仍成立)。"""
        return Box(-self.x2, self.y1, -self.x1, self.y2)


@dataclass(frozen=True)
class AttackWindow:
    """一个判定窗:第 start..end 帧(含)攻击框生效(帧号相对招式第 0 帧)。

    knockdown 为本窗倒地类型的覆盖值(Power Dunk 第一段不倒、第二段重击倒地),
    None 表示沿用 MoveDef.knockdown。
    """

    start: int
    end: int  # 空中技可为 -1,表示"直到落地"
    hit: tuple  # tuple[Box, ...]  该窗攻击框
    knockdown: Optional[str] = None


@dataclass(frozen=True)
class MoveDef:
    """一招的完整定义(terry.json 每条 → 一个 MoveDef)。"""

    name: str  # move_id,全局唯一(st_C / power_wave_A / throw_fwd ...)
    label: str  # 中文显示名(重拳 / 能量波A ...)
    kind: str  # NORMAL / SPECIAL / SUPER / THROW
    stance: str  # stand / crouch / air(空中技只能空中出)
    pose_key: str  # 对应 poses.POSE_KEYS 键(渲染用)
    damage: int
    chip: int  # 防御削血(被防时扣)
    hitstun: int  # 命中硬直帧
    blockstun: int  # 防御硬直帧
    pushback_hit: float  # 命中推背 px/帧
    pushback_block: float
    guard: str  # mid / low / high / unblockable
    knockdown: str  # none / air_juggle / sweep / hard
    cancels: tuple  # tuple[str, ...] ⊆ ("special", "super")
    gauge_gain: int  # 命中后攻方涨气
    gauge_cost: int  # 发动耗气(只有 SUPER 允许 >0)
    total: int  # 总帧数(air 招 = 空中最长帧数上限)
    invuln: tuple  # tuple[tuple[int, int], ...] 无敌帧区间(闭区间)
    windows: tuple  # tuple[AttackWindow, ...] 判定窗(投技/发波招为空)
    hurt_boxes: Optional[tuple]  # 招期间受击框覆盖;None=用状态默认(system.json)
    projectile: Optional[dict]  # 发波参数 {"speed","box","max_count"};无则为 None
    motion: Optional[dict]  # 移动参数(见模块 docstring);无则为 None
    input: dict  # 触发条件(见模块 docstring)
    throw_range: Optional[int]  # 投技专属:可抓距离 px(THROW 必填,其余必须 None)

    @property
    def startup(self) -> int:
        """首判定窗起始帧(无窗招 = total,即全程无直接判定)。"""
        return self.windows[0].start if self.windows else self.total

    @property
    def recovery(self) -> int:
        """末判定窗结束后到回 idle 的帧数(空中招/无窗招无意义,返回 0)。"""
        if not self.windows or self.windows[-1].end < 0:
            return 0
        return self.total - self.windows[-1].end - 1


@dataclass(frozen=True)
class ActiveAttack:
    """combat 裁决用的攻击快照(世界坐标)。一次攻击每个窗只结算一次,
    该职责由 fighter 承担(命中后本窗不再挂出)。"""

    side: Side
    move: MoveDef
    window_index: int  # 第几个判定窗(0 起)
    frame: int  # 招式第几帧(0 起)
    world_hit: tuple  # tuple[Box, ...] 世界坐标攻击框(已含朝向镜像)


@dataclass(frozen=True)
class FighterView:
    """fighter 的只读视图,给 combat/AI 裁决用(不许摸 fighter 内部状态)。"""

    side: Side
    x: float  # 脚底中心世界 x
    y: float  # 脚底世界 y(在地面时 = system.stage.ground_y)
    facing: int  # +1 面右 / -1 面左
    state: str  # 状态名(fighter 状态表)
    move_id: Optional[str]  # 攻击状态时的招式名
    airborne: bool
    crouching: bool
    guarding: bool  # 处于防御姿态(按住后方向)
    guard_stance: str  # "stand" / "crouch"(决定能挡 mid/low 还是 mid/high)
    in_hitstun: bool  # 硬直中(不可被投)
    invulnerable: bool  # 当前帧无敌(起身无敌/招式无敌)
    hurt: tuple  # tuple[Box, ...] 世界坐标受击框


@dataclass(frozen=True)
class AiView:
    """AI 决策可见信息(AI 只看得到这些,不许偷看对手状态机内部)。"""

    dist: int  # 与对手水平像素距离
    own_health: int
    own_gauge: int  # 0..gauge.max
    facing: int  # 自己朝向(AI 产出物理方向时按它换算前后)
    opp_airborne: bool
    opp_attacking: bool  # 对手处于攻击状态(startup/active 期)
    opp_projectile: bool  # 场上有对手的飞行道具
    self_cornered: bool  # 自己贴角


@dataclass(frozen=True)
class HitResult:
    """combat 的结算结果(match 层应用到双方)。"""

    attacker: Side
    victim: Side
    kind: str  # hit / block / trade
    move: str  # move_id
    damage: int  # 已按连段缩放
    hitstop: int
    stun: int  # 命中→受击硬直;防御→防御硬直
    pushback: float
    knockdown: str
    gauge_attacker: int
    gauge_victim: int
    juggle_vy: float  # 浮空弹起速度(命中浮空/空中者时 >0,否则 0)


@dataclass(frozen=True)
class FighterSnapshot:
    """渲染快照(ui 只看这个,不许摸 fighter 内部)。"""

    side: Side
    x: float
    y: float
    facing: int
    state: str
    move_id: Optional[str]
    pose: str  # POSE 键(fighter 已按阶段映射好)
    health: int
    gauge: int
    combo: int  # 自己当前打出的连段数(显示在对手一侧)
