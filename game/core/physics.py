"""core/physics.py — 纯函数物理(重力/跳弧/走跑/推背/墙角,设计文档 §4.2-4.3、§5.3 A1)。

全部无副作用小函数,fighter 与测试共用同一套公式(契约独立复算的基础)。
统一约定(types.py):y 向上为正、地面 y=0、vy 上正、重力为负;
walk.back / jump.back_vx / dash_back.vx 存"正数大小",方向由调用方乘朝向。

积分方式:空中位移用梯形(半帧校正)—— 每帧位移 = (vy_old + vy_new) / 2。
连续公式 vy0^2/(2|g|) 的离散化误差因此被压到亚像素级,
设计文档 §6 要求"跳高与理论值差 <=2px",普通前向欧拉积分差 4px 是过不了的。
"""
from __future__ import annotations

from .data import SystemCfg


def apply_gravity(vy: float, cfg: SystemCfg) -> float:
    """一帧重力(vy 上正,重力为负 → vy 变小)。"""
    return vy + cfg.gravity


def air_step(y: float, vy: float, cfg: SystemCfg) -> tuple:
    """空中积分一帧(梯形)。返回 (y, vy, landed)。

    landed=True 时 y 已夹回 0、vy 清零(落地瞬间速度作废,不再下坠)。
    y<=0 判落地:与"起跳帧 y=0"不冲突——air 状态进入时 vy0>0,
    第一次积分 y 必然 >0。
    """
    new_vy = vy + cfg.gravity
    y += (vy + new_vy) / 2.0
    if y <= 0.0:
        return 0.0, 0.0, True
    return y, new_vy, False


def jump_arc(kind: str, facing: int, cfg: SystemCfg) -> tuple:
    """跳弧初速 (vx, vy0)。kind: up / small_up / fwd / small_fwd / back / small_back。

    前跳 vx 沿 facing,后跳向身后(-facing × 正数大小 back_vx)。
    """
    j = cfg.jump
    if kind == "up":
        return 0.0, j.big_vy0
    if kind == "small_up":
        return 0.0, j.small_vy0
    if kind == "fwd":
        return facing * j.fwd_vx, j.big_vy0
    if kind == "small_fwd":
        return facing * j.small_fwd_vx, j.small_vy0
    if kind == "back":
        return -facing * j.back_vx, j.big_vy0
    if kind == "small_back":
        return -facing * j.back_vx, j.small_vy0
    raise ValueError(f"未知跳种 {kind!r}")


def jump_peak(vy0: float, cfg: SystemCfg) -> float:
    """理论跳高 vy0^2 / (2|g|)(连续公式,供测试独立复算对表)。"""
    return vy0 * vy0 / (2.0 * abs(cfg.gravity))


def jump_airtime(vy0: float, cfg: SystemCfg) -> int:
    """滞空帧数:用 air_step 同款积分模拟一遍,数到落地为止。

    与 fighter 的实际积分完全同源,测试断言就用它当权威值。
    """
    y, vy, landed, frames = 0.0, vy0, False, 0
    while not landed:
        y, vy, landed = air_step(y, vy, cfg)
        frames += 1
    return frames


def walk_step(direction: str, facing: int, cfg: SystemCfg) -> float:
    """走速(地面 vy 恒 0,只返回 vx)。direction: "fwd" / "back"。"""
    if direction == "fwd":
        return facing * cfg.walk.fwd
    if direction == "back":
        return -facing * cfg.walk.back
    raise ValueError(f"walk_step 只认 fwd/back,得到 {direction!r}")


def run_step(facing: int, cfg: SystemCfg) -> float:
    """跑速(沿 facing)。"""
    return facing * cfg.run.speed


def pushback_resolve(
    x_victim: float, x_attacker: float, pushback: float, lo: float, hi: float
) -> tuple:
    """标准墙角推背(§4.4 第 6 条),返回 (x_victim_new, x_attacker_new)。

    受方沿"远离攻方"方向退 pushback;退到贴界(lo/hi)后,剩余量改由
    攻方往反方向退(被反弹);双方永远夹在 [lo, hi] 内。
    推背在这里是一次性位移量(像素),不是持续速度——契约未给持续帧数。
    """
    way = 1.0 if x_victim >= x_attacker else -1.0
    v_new = min(max(x_victim + way * pushback, lo), hi)
    moved = abs(v_new - x_victim)
    rest = pushback - moved
    a_new = x_attacker
    if rest > 0.0:
        a_new = min(max(x_attacker - way * rest, lo), hi)
    return v_new, a_new


def push_apart(x1: float, x2: float, push_box_w: float, lo: float, hi: float) -> tuple:
    """推挤框重叠时对称推开(§4.3:双方各退重叠量一半),返回 (x1_new, x2_new)。

    只管横向:空中无推挤是 KOF 特色(换边),调用方自行保证只在双方
    都在地面时使用。宽度 = 推挤框 x2-x1(system.json 站/蹲都是 32)。
    """
    if x1 <= x2:
        a, b, swapped = x1, x2, False
    else:
        a, b, swapped = x2, x1, True
    overlap = push_box_w - (b - a)
    if overlap <= 0.0:
        return x1, x2
    a2 = min(max(a - overlap / 2.0, lo), hi)
    b2 = min(max(b + overlap / 2.0, lo), hi)
    if swapped:
        return b2, a2
    return a2, b2


def push_apart_full(x_self: float, x_other: float, w: float, lo: float, hi: float) -> tuple:
    """fighter 逐方调用版:发现自己与对手推挤框重叠时,自己全额退开。

    与对称版 push_apart 的分工:对称版给"同时拥有双方引用"的调用方
    (match 层)一次推净用;逐方版给 Fighter.step 用——每方只动自己,
    后 step 的一方看到已分离即无操作,一轮完成分离(对称版每帧只
    消一半重叠,双方逐帧调用会无限渐近)。返回 (x_self_new, x_other)。
    """
    dx = x_other - x_self
    if abs(dx) >= w:
        return x_self, x_other  # 已分离:不动
    sign = 1.0 if dx >= 0 else -1.0  # dx==0 的罕见兜底:自己向左退
    x = x_other - sign * w  # 退到与对手正好贴框
    return min(max(x, lo), hi), x_other
