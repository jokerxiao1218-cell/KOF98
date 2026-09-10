"""core/combat.py — 判定与结算(纯裁决层,设计文档 §4.4 / §5.3 A3 契约)。

职责:
  * resolve / resolve_trade / resolve_throw / resolve_projectile:
    攻击框×受击框 → HitResult 的无副作用计算,不持有 Fighter 状态;
  * ComboCounter:连段计数与伤害缩放(自带状态的纯数据实体)。

纪律:零 pygame import;本文件不改任何数值(全部来自 SystemCfg / MoveDef)。

裁决规则(§4.4,与 types.py docstring 对齐):
  * 攻击框任一与受击框任一相交 → 判定成立,否则 whiff(None);
  * 受方 invulnerable(起身无敌/招式无敌)→ 直接 whiff(框相交也打不中);
  * guard 层级:mid 站蹲皆可防 / low 仅蹲防 / high 仅站防 / unblockable 不可防;
  * block 结算:不按 move.damage 走,扣削血 chip —— HitResult.damage 字段在
    防御时承载削血值(st_C 这类 chip=0 的招被防住就是 damage=0);
    防住就不倒地(knockdown 一律 "none",连扫堂腿被蹲防也只是推背);
    被防不构成连段(不进 ComboCounter);
  * hit 结算:伤害经 ComboCounter 缩放;hitstop 按招 kind(NORMAL/SPECIAL/
    SUPER)查 system.json 的命中/防御两档;
  * 浮空受方被命中 → juggle_vy = cfg.juggle_bounce_vy,其余场合 0;
  * 窗级 knockdown 覆盖:windows[window_index].knockdown 非 None 时压过招级
    (Power Dunk 第一段不倒、第二段沿招级 hard);
  * trade:同帧双方 active 互与对方 hurt 相交(且双方均非无敌)才成立,
    两个结果各按 hit 规则结算后把 kind 标成 "trade"(挨的一记照常浮空弹起);
  * 投技:不判框(距离与状态由调用方确认)、伤害不缩放、hitstop=hit_throw(=0)、
    pushback 带符号——基值 fwd=+40 / back=−40 再乘投手 facing,保证"受方向
    投手面前方/身后飞"的语义在任意朝向下成立(投手面右时正是 +40/−40);
  * 弹体:hitstop 用 projectile_victim(只冻结受方,攻方 0——约定),
    远程命中攻方不涨气(gauge_attacker=0);防御规则与近身攻击一致。

"一次攻击只结算一次"(命中标记)不在这里:由 fighter 承担
(types.py ActiveAttack docstring——命中后本窗不再挂出)。
"""
from __future__ import annotations

import dataclasses

from . import types as T
from .data import SystemCfg

# move.kind → system.json hitstop 键(命中/防御两档)。
# THROW 正常不走 resolve(投技无判定窗,走 resolve_throw),表中兜底防止 KeyError。
_HITSTOP_HIT = {
    "NORMAL": "hit_normal",
    "SPECIAL": "hit_special",
    "SUPER": "hit_super",
    "THROW": "hit_throw",
}
_HITSTOP_BLOCK = {
    "NORMAL": "block_normal",
    "SPECIAL": "block_special",
    "SUPER": "block_super",
    # 无 block_throw:THROW 招 loader 强制 guard=unblockable,不可能进防御分支
}


def _hitstop_for(cfg: SystemCfg, move_kind: str, blocked: bool) -> int:
    """按招式 kind 与命中/防御,查 system.json 的 hitstop 帧数。"""
    key = (_HITSTOP_BLOCK if blocked else _HITSTOP_HIT)[move_kind]
    return getattr(cfg.hitstop, key)


def _guard_blocks(move_guard: str, view: T.FighterView) -> bool:
    """防御层级矩阵(§4.4 第 2 条):受方当前姿态能否挡住这一招。"""
    if not view.guarding:
        return False
    if move_guard == "mid":
        return True  # 中段:站防蹲防都能挡
    if move_guard == "low":
        return view.guard_stance == "crouch"  # 下段:只有蹲防挡得住
    if move_guard == "high":
        return view.guard_stance == "stand"  # 上段:只有站防挡得住
    return False  # unblockable(以及任何未知层级都不许静默挡住)


def _knockdown_of(atk: T.ActiveAttack) -> str:
    """倒地类型:窗级覆盖优先(非 None),否则招级。"""
    wins = atk.move.windows
    if 0 <= atk.window_index < len(wins):
        kd = wins[atk.window_index].knockdown
        if kd is not None:
            return kd
    return atk.move.knockdown


def _strikes(atk: T.ActiveAttack, view: T.FighterView) -> bool:
    """whiff 判定的公共部分:框相交且受方非无敌 → 这一击打得上。"""
    if view.invulnerable:
        return False
    return any(h.overlaps(v) for h in atk.world_hit for v in view.hurt)


# ---------- 单方裁决 ----------


def resolve(
    atk: T.ActiveAttack,
    victim: T.FighterView,
    counter: "ComboCounter",
    cfg: SystemCfg,
) -> T.HitResult | None:
    """攻击×受方 → HitResult;框不相交/受方无敌 → None(whiff)。

    受方在防御姿态且层级可挡 → kind="block";否则 kind="hit"。
    缩放只在 hit 分支生效(被防不构成连段)。
    """
    if not _strikes(atk, victim):
        return None
    move = atk.move
    if _guard_blocks(move.guard, victim):
        return T.HitResult(
            attacker=atk.side,
            victim=victim.side,
            kind="block",
            move=move.name,
            damage=move.chip,  # 削血:防御时 HitResult.damage 承载 chip 值
            hitstop=_hitstop_for(cfg, move.kind, True),
            stun=move.blockstun,
            pushback=move.pushback_block,
            knockdown="none",  # 防住就不倒地
            gauge_attacker=0,
            gauge_victim=cfg.gauge.on_block,
            juggle_vy=0.0,
        )
    return T.HitResult(
        attacker=atk.side,
        victim=victim.side,
        kind="hit",
        move=move.name,
        damage=counter.hit(move.damage),  # 连段缩放(第 N 击 ×scaling[...])
        hitstop=_hitstop_for(cfg, move.kind, False),
        stun=move.hitstun,
        pushback=move.pushback_hit,
        knockdown=_knockdown_of(atk),
        gauge_attacker=move.gauge_gain,
        gauge_victim=cfg.gauge.on_hit_taken,
        juggle_vy=cfg.juggle_bounce_vy if victim.airborne else 0.0,
    )


def resolve_trade(
    atk_a: T.ActiveAttack,
    view_a: T.FighterView,
    counter_a: "ComboCounter",
    atk_b: T.ActiveAttack,
    view_b: T.FighterView,
    counter_b: "ComboCounter",
    cfg: SystemCfg,
) -> tuple[T.HitResult, T.HitResult] | None:
    """互撞裁决:双方 active 互与对方 hurt 相交(且均非无敌)→ 各吃一记。

    参数配对:atk_a/view_a/counter_a 同属一方(A 的攻击打 view_b,
    用 A 自己的连段计数缩放);返回顺序同为 (A 打中 B, B 打中 A)。
    只有单方够得着、或有一方无敌 → None(由调用方走单向 resolve)。
    """
    if not (_strikes(atk_a, view_b) and _strikes(atk_b, view_a)):
        return None
    r_a = resolve(atk_a, view_b, counter_a, cfg)
    r_b = resolve(atk_b, view_a, counter_b, cfg)
    if r_a is None or r_b is None:
        return None  # 双保险:防御判定理论上不会同时挡住双方(出招态不防御)
    return (
        dataclasses.replace(r_a, kind="trade"),
        dataclasses.replace(r_b, kind="trade"),
    )


def resolve_throw(
    thrower: T.FighterView,
    victim: T.FighterView,
    move: T.MoveDef,
    cfg: SystemCfg,
) -> T.HitResult:
    """投技结算(抓取成立与否由调用方确认,这里只算结果)。

    伤害不缩放(单发,不进 ComboCounter)、hitstop=cfg.hitstop.hit_throw(=0)、
    stun=0(倒地演出替代硬直)、knockdown="hard"、pushback 带符号。
    gauge:攻方按 move.gauge_gain(投技基线为 0),受方不按"挨打涨气"
    结算(契约未列投技受方涨气,保守取 0,见 A3 汇报)。
    """
    sign = 1.0 if move.input["dir"] == "fwd" else -1.0
    return T.HitResult(
        attacker=thrower.side,
        victim=victim.side,
        kind="hit",
        move=move.name,
        damage=move.damage,
        hitstop=cfg.hitstop.hit_throw,
        stun=0,
        pushback=40.0 * sign * thrower.facing,  # fwd=面前方抛、back=向身后抛
        knockdown="hard",
        gauge_attacker=move.gauge_gain,
        gauge_victim=0,
        juggle_vy=0.0,
    )


# ---------- 弹体裁决(实体在 projectile.py) ----------


def resolve_projectile(
    proj,  # projectile.Projectile(避免循环 import,鸭子类型即可)
    victim: T.FighterView,
    counter: "ComboCounter",
    cfg: SystemCfg,
) -> T.HitResult | None:
    """弹体×受方 → HitResult;纯函数:不标 dead、不动弹体、不查 alive。

    命中后由调用方 proj.on_hit() 标 dead(§4.4 约定);
    hitstop 只冻结受方(projectile_victim),攻方 0;
    远程命中攻方不涨气(gauge_attacker=0,即便 move.gauge_gain>0)。
    防御规则与近身攻击一致(层级矩阵 + 削血 chip)。
    """
    if victim.invulnerable:
        return None
    if not any(pb.overlaps(v) for pb in proj.boxes() for v in victim.hurt):
        return None
    move = proj.move
    if _guard_blocks(move.guard, victim):
        return T.HitResult(
            attacker=proj.side,
            victim=victim.side,
            kind="block",
            move=move.name,
            damage=move.chip,  # 防御弹削血(能量波A 被防扣 8)
            hitstop=cfg.hitstop.projectile_victim,
            stun=move.blockstun,
            pushback=move.pushback_block,
            knockdown="none",  # 防住就不倒地
            gauge_attacker=0,
            gauge_victim=cfg.gauge.on_block,
            juggle_vy=0.0,
        )
    return T.HitResult(
        attacker=proj.side,
        victim=victim.side,
        kind="hit",
        move=move.name,
        damage=counter.hit(move.damage),
        hitstop=cfg.hitstop.projectile_victim,
        stun=move.hitstun,
        pushback=move.pushback_hit,
        knockdown=move.knockdown,  # 弹体无判定窗,直接招级
        gauge_attacker=0,  # 远程命中不涨气(约定)
        gauge_victim=cfg.gauge.on_hit_taken,
        juggle_vy=cfg.juggle_bounce_vy if victim.airborne else 0.0,
    )


# ---------- 连段计数与伤害缩放 ----------


class ComboCounter:
    """连段计数与伤害缩放(§4.3:100/90/80/70/60/50…,50 保底)。

    缩放:第 N 击(N 从 1 起)伤害 = 四舍五入(raw × scaling[min(N−1, 末位)] / 100)。
    四舍五入用整数式 (raw*pct+50)//100(正数域;不用 round() 避开银行家舍入,
    35×90%=31.5 这类 .5 恒向上)。
    reset() 由调用方在受方恢复可行动时触发;count 供 HUD 显示。
    """

    def __init__(self, scaling) -> None:
        self._scaling = tuple(scaling)
        if not self._scaling:
            raise ValueError("combo_scaling 不能为空")
        self._count = 0

    @property
    def count(self) -> int:
        """当前连段已结算的击数。"""
        return self._count

    def hit(self, raw_damage: int) -> int:
        """结算一击:返回缩放后伤害,内部计数 +1(超出表尾一直按末位)。"""
        idx = min(self._count, len(self._scaling) - 1)
        self._count += 1
        return (raw_damage * self._scaling[idx] + 50) // 100

    def reset(self) -> None:
        """受方恢复可行动时由调用方调用,计数清零。"""
        self._count = 0
