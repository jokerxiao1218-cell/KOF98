"""tests/test_combat.py — 判定与结算(设计文档 §6 测试计划 test_combat 组)。

纯逻辑测试,不碰 pygame,不需要 dummy 驱动。
数值断言一律对附录 A/B 冻结基线;关键公式(缩放/hitstop)在测试内
独立复算,不 import 生产代码的实现(照 sheepandsheep 契约独立复算惯例)。

几何布局约定(本文件全部用例共用):
  P1 攻击者 x=250 面右,攻击框 = 招式源框(面右定义)平移 250;
  受方 P2 x=300,站姿受击框 [285,315)×[0,92)、蹲姿 [285,315)×[0,58)
  (附录 B 基线 30×92 / 30×58,测试内写死以便独立复算)。
"""
import pytest

from game.core import combat
from game.core import data
from game.core import types as T
from game.core.combat import ComboCounter


@pytest.fixture(scope="module")
def moves():
    return data.load_moves()


@pytest.fixture(scope="module")
def cfg():
    return data.load_system()


# 附录 B 基线受击框(写死,不 import 生产实现的换算)
STAND_HURT = T.Box(-15, 0, 15, 92)
CROUCH_HURT = T.Box(-15, 0, 15, 58)


def make_view(x=300.0, *, side=T.Side.P2, facing=-1, crouch=False,
              guarding=False, airborne=False, invulnerable=False):
    """受方只读视图:hurt 框 = 附录 B 基线框平移到 x(空中再抬 60px)。"""
    base = CROUCH_HURT if crouch else STAND_HURT
    y = 60.0 if airborne else 0.0
    hurt = (T.Box(base.x1 + x, base.y1 + y, base.x2 + x, base.y2 + y),)
    return T.FighterView(
        side=side, x=x, y=y, facing=facing, state="idle", move_id=None,
        airborne=airborne, crouching=crouch, guarding=guarding,
        guard_stance="crouch" if crouch else "stand",
        in_hitstun=False, invulnerable=invulnerable, hurt=hurt,
    )


def make_atk(move, x=250.0, *, side=T.Side.P1, window_index=0,
             mirror=False, hit=None):
    """攻击快照:把 move 第 window_index 窗的攻击框平移到世界坐标。

    mirror=True 时先 Box.mirrored(面朝左定义),P2 攻击用。
    投技无判定窗 → 用 hit 参数手造框(§6 unblockable 用例)。
    """
    if hit is None:
        hit = move.windows[window_index].hit
    if mirror:
        hit = [b.mirrored() for b in hit]
    frame = move.windows[window_index].start if move.windows else 0
    world = tuple(T.Box(b.x1 + x, b.y1, b.x2 + x, b.y2) for b in hit)
    return T.ActiveAttack(side=side, move=move, window_index=window_index,
                          frame=frame, world_hit=world)


def fresh_counter(cfg):
    """每次裁决都用全新连段计数器(独立于上一条的击数)。"""
    return ComboCounter(cfg.combo_scaling)


# ---------- 相交 → 命中(金标:附录 A 的 st_C) ----------


def test_hit_golden_st_c(moves, cfg):
    """st_C 框 [280,316)×[60,80) 碰站姿受击框 → 全字段金标(附录 A/B 冻结值)。"""
    r = combat.resolve(make_atk(moves["st_C"]), make_view(), fresh_counter(cfg), cfg)
    assert r is not None
    assert r.kind == "hit"
    assert r.attacker is T.Side.P1 and r.victim is T.Side.P2
    assert r.move == "st_C"
    assert r.damage == 80          # 第一击缩放 100%
    assert r.hitstop == 11         # 附录 B:普通技命中 11
    assert r.stun == 17            # 附录 A:hs=17
    assert r.pushback == 12        # 附录 A:pb 命中 12
    assert r.knockdown == "none"
    assert r.gauge_attacker == 8   # 附录 B:命中普通 +8
    assert r.gauge_victim == 5     # 附录 B:被击 +5
    assert r.juggle_vy == 0.0      # 地面命中不弹起


def test_whiff_no_overlap(moves, cfg):
    # 受方在 400(st_C 框最远到 316)→ whiff,不出任何结算
    r = combat.resolve(make_atk(moves["st_C"]), make_view(x=400.0),
                       fresh_counter(cfg), cfg)
    assert r is None


def test_invulnerable_whiffs(moves, cfg):
    # 起身无敌帧:框相交也打不中(§4.3 wakeup 前 8 帧无敌)
    r = combat.resolve(make_atk(moves["st_C"]),
                       make_view(invulnerable=True), fresh_counter(cfg), cfg)
    assert r is None


# ---------- guard 层级矩阵(§6 六条) ----------


@pytest.mark.parametrize("move_id,victim_crouch,expected", [
    ("st_C", False, "block"),           # mid × 站防 → 挡住
    ("cr_A", True, "block"),            # mid × 蹲防 → 挡住(st_C 拳位高打不中蹲姿,换蹲姿中段技)
    ("cr_B", False, "hit"),             # low × 站防 → 扫堂腿类打穿站防
    ("cr_B", True, "block"),            # low × 蹲防 → 挡住
    ("crack_shoot_B", False, "block"),  # high × 站防 → 挡住
    ("crack_shoot_B", True, "hit"),     # high × 蹲防 → 跳攻击/爆裂踢类打穿蹲防
])
def test_guard_matrix(move_id, victim_crouch, expected, moves, cfg):
    """§6 全 guard 层级矩阵:防住=block,段位不对=照常挨打。"""
    r = combat.resolve(make_atk(moves[move_id]),
                       make_view(crouch=victim_crouch, guarding=True),
                       fresh_counter(cfg), cfg)
    assert r is not None, f"{move_id} 的框必须摆到与受方相交"
    assert r.kind == expected


def test_unblockable_cannot_be_guarded(moves, cfg):
    """§6:unblockable(投技层级)× 任何防御姿态 = 照常 hit。

    throw_fwd 无判定窗(投技不走框),手造一个与受击框重合的攻击框
    只为驱动 resolve 的层级矩阵;投技真实路径走 resolve_throw。
    """
    # make_atk 传"相对攻击者"的源框(平移 250 后即 [280,316)×[0,92),罩住受方)
    atk = make_atk(moves["throw_fwd"], hit=[T.Box(30, 0, 66, 92)])
    for crouch in (False, True):
        r = combat.resolve(atk, make_view(crouch=crouch, guarding=True),
                           fresh_counter(cfg), cfg)
        assert r is not None and r.kind == "hit"


# ---------- 防御分支金标(§6) ----------


def test_block_golden_no_chip(moves, cfg):
    """st_C(chip=0)被站防:不扣血、防御硬直/推背/hitstop/gauge 全按附录 A/B。"""
    r = combat.resolve(make_atk(moves["st_C"]), make_view(guarding=True),
                       fresh_counter(cfg), cfg)
    assert r.kind == "block"
    assert r.damage == 0             # 普通技无削血,防住不扣
    assert r.stun == 12              # 附录 A:bs=12
    assert r.pushback == 14          # 附录 A:pb 防御 14
    assert r.hitstop == 9            # 附录 B:普通技防御 9
    assert r.gauge_attacker == 0     # 攻方被防不涨气
    assert r.gauge_victim == 2       # 附录 B:防御 +2
    assert r.knockdown == "none"     # 防住就不倒
    assert r.juggle_vy == 0.0


def test_block_chip_special(moves, cfg):
    """§6 削血:burn_knuckle_A(chip=10)被站防 → 扣 10(必杀才有削血)。"""
    r = combat.resolve(make_atk(moves["burn_knuckle_A"]),
                       make_view(guarding=True), fresh_counter(cfg), cfg)
    assert r.kind == "block"
    assert r.damage == 10            # 削血 = move.chip
    assert r.stun == 12              # 附录 A:bs=12
    assert r.hitstop == 10           # 附录 B:必杀防御 10


def test_block_sweep_not_knockdown(moves, cfg):
    # 扫堂腿(sweep)被蹲防挡住 → 只推背不倒地
    r = combat.resolve(make_atk(moves["cr_D"]),
                       make_view(crouch=True, guarding=True),
                       fresh_counter(cfg), cfg)
    assert r.kind == "block" and r.knockdown == "none"


# ---------- 连段缩放(独立复算) ----------


def _scale_ref(raw, n, scaling):
    """独立复算(不 import 生产实现):第 N 击 × scaling[min(N−1, 末位)],四舍五入。"""
    pct = scaling[min(n - 1, len(scaling) - 1)]
    return (raw * pct + 50) // 100


def test_combo_scaling_sequence_and_floor(cfg):
    """§6 缩放序列:100/90/80/70/60/50,之后 50 保底(附录 B:第 6 击起)。
    金标期望值逐击手算,不依赖实现公式。
    """
    c = ComboCounter(cfg.combo_scaling)
    assert [c.hit(80) for _ in range(8)] == [80, 72, 64, 56, 48, 40, 40, 40]
    assert c.count == 8


def test_combo_scaling_independent_recompute(cfg):
    """独立复算:35 这类除不尽的伤害逐击对照测试内公式(35×90%=31.5 → 32)。"""
    c = ComboCounter(cfg.combo_scaling)
    for n in range(1, 9):
        assert c.hit(35) == _scale_ref(35, n, cfg.combo_scaling), f"第 {n} 击"


def test_combo_counter_reset(cfg):
    # reset 后回到 100% 第一击(受方恢复可行动时由调用方触发)
    c = ComboCounter(cfg.combo_scaling)
    c.hit(80); c.hit(80); c.hit(80)
    assert c.count == 3
    c.reset()
    assert c.count == 0
    assert c.hit(80) == 80


def test_resolve_feeds_combo_counter(moves, cfg):
    # resolve 的 hit 分支真的吃缩放:同一 counter 第二击 st_C 80 → 72(×90%)
    counter = ComboCounter(cfg.combo_scaling)
    first = combat.resolve(make_atk(moves["st_C"]), make_view(), counter, cfg)
    second = combat.resolve(make_atk(moves["st_C"]), make_view(), counter, cfg)
    assert first.damage == 80 and second.damage == 72


# ---------- 互撞 trade(§6) ----------


def test_trade_both_sides_hit(moves, cfg):
    """§6:同帧双 active 互撞 → 两个 kind="trade"、各自按 hit 规则结算。

    P1 x=250 面右、P2 x=310 面左(攻击框镜像)→ 互相够得着对方。
    """
    atk1 = make_atk(moves["st_C"], x=250.0, side=T.Side.P1)
    view1 = make_view(x=250.0, side=T.Side.P1, facing=1)
    atk2 = make_atk(moves["st_C"], x=310.0, side=T.Side.P2, mirror=True)
    view2 = make_view(x=310.0, side=T.Side.P2)
    out = combat.resolve_trade(atk1, view1, fresh_counter(cfg),
                               atk2, view2, fresh_counter(cfg), cfg)
    assert out is not None
    r1, r2 = out
    assert r1.kind == "trade" and r2.kind == "trade"
    # 各吃一记:r1 是 P1 打 P2、r2 是 P2 打 P1
    assert (r1.attacker, r1.victim) == (T.Side.P1, T.Side.P2)
    assert (r2.attacker, r2.victim) == (T.Side.P2, T.Side.P1)
    assert r1.damage == 80 and r2.damage == 80  # 各自第一击 100%
    assert r1.hitstop == 11 and r1.stun == 17   # 照常按命中档结算


def test_trade_requires_both_sides_reach(moves, cfg):
    # 只有单方够得着(P2 在 500)→ 不算互撞,None 交调用方走单向 resolve
    atk1 = make_atk(moves["st_C"], x=250.0, side=T.Side.P1)
    view1 = make_view(x=250.0, side=T.Side.P1, facing=1)
    atk2 = make_atk(moves["st_C"], x=500.0, side=T.Side.P2, mirror=True)
    view2 = make_view(x=500.0, side=T.Side.P2)
    out = combat.resolve_trade(atk1, view1, fresh_counter(cfg),
                               atk2, view2, fresh_counter(cfg), cfg)
    assert out is None


def test_trade_invulnerable_breaks_trade(moves, cfg):
    # 一方无敌 → 挨不着对方 → 不是互撞(那一方变成纯 whiff)
    atk1 = make_atk(moves["st_C"], x=250.0, side=T.Side.P1)
    view1 = make_view(x=250.0, side=T.Side.P1, facing=1, invulnerable=True)
    atk2 = make_atk(moves["st_C"], x=310.0, side=T.Side.P2, mirror=True)
    view2 = make_view(x=310.0, side=T.Side.P2)
    out = combat.resolve_trade(atk1, view1, fresh_counter(cfg),
                               atk2, view2, fresh_counter(cfg), cfg)
    assert out is None


# ---------- 投技(§6) ----------


def test_throw_fwd_pushback_positive(moves, cfg):
    # 前投(投手面右):受方向投手面前方飞 → pushback = +40
    thrower = make_view(x=250.0, side=T.Side.P1, facing=1)
    r = combat.resolve_throw(thrower, make_view(x=270.0), moves["throw_fwd"], cfg)
    assert r.pushback == 40.0


def test_throw_back_pushback_negative(moves, cfg):
    # 后投(投手面右):受方向投手身后抛 → pushback = −40
    thrower = make_view(x=250.0, side=T.Side.P1, facing=1)
    r = combat.resolve_throw(thrower, make_view(x=270.0), moves["throw_back"], cfg)
    assert r.pushback == -40.0


def test_throw_facing_left_flips_sign(moves, cfg):
    """投手面左时 fwd 仍是"面前方":世界方向翻负 → −40(±40×朝向语义自洽)。"""
    thrower = make_view(x=400.0, side=T.Side.P2, facing=-1)
    victim = make_view(x=380.0, side=T.Side.P1, facing=1)
    r = combat.resolve_throw(thrower, victim, moves["throw_fwd"], cfg)
    assert r.pushback == -40.0


def test_throw_golden_fields(moves, cfg):
    """§6 投技金标:伤害不缩放、hitstop=0、stun=0、hard 倒地、kind=hit、招名记入。"""
    thrower = make_view(x=250.0, side=T.Side.P1, facing=1)
    r = combat.resolve_throw(thrower, make_view(x=270.0), moves["throw_fwd"], cfg)
    assert r.kind == "hit" and r.move == "throw_fwd"
    assert r.attacker is T.Side.P1 and r.victim is T.Side.P2
    assert r.damage == 110      # 附录 A:前投 110,单发不缩放
    assert r.hitstop == 0       # 附录 B:hit_throw = 0
    assert r.stun == 0
    assert r.knockdown == "hard"


# ---------- 浮空弹起(§6) ----------


def test_airborne_juggle_bounce(moves, cfg):
    """§6:浮空受方被命中 → juggle_vy=3.0;地面命中 → 0;被防住 → 不弹起。"""
    atk = make_atk(moves["st_C"])
    r_air = combat.resolve(atk, make_view(airborne=True), fresh_counter(cfg), cfg)
    assert r_air.kind == "hit"
    assert r_air.juggle_vy == cfg.juggle_bounce_vy == 3.0  # 附录 B
    r_gnd = combat.resolve(atk, make_view(), fresh_counter(cfg), cfg)
    assert r_gnd.juggle_vy == 0.0
    r_blk = combat.resolve(atk, make_view(airborne=True, guarding=True),
                           fresh_counter(cfg), cfg)
    assert r_blk.kind == "block" and r_blk.juggle_vy == 0.0


# ---------- 窗级 knockdown 覆盖(§6) ----------


def test_power_dunk_window_knockdown_override(moves, cfg):
    """§6:Power Dunk B 窗 0 覆盖为不倒、窗 1 无覆盖沿用招级 hard
    (附录 A"两段各 55"靠窗级字段精确表达)。"""
    b = moves["power_dunk_B"]
    victim = make_view()
    r0 = combat.resolve(make_atk(b, window_index=0), victim, fresh_counter(cfg), cfg)
    assert r0.knockdown == "none"    # 窗级覆盖生效
    r1 = combat.resolve(make_atk(b, window_index=1), victim, fresh_counter(cfg), cfg)
    assert r1.knockdown == "hard"    # None → 沿用招级


# ---------- hitstop 取值(独立复算) ----------


_HITSTOP_REF_HIT = {"NORMAL": "hit_normal", "SPECIAL": "hit_special",
                    "SUPER": "hit_super", "THROW": "hit_throw"}
_HITSTOP_REF_BLOCK = {"NORMAL": "block_normal", "SPECIAL": "block_special",
                      "SUPER": "block_super"}


def _hitstop_ref(cfg, move, blocked):
    """独立复算:命中/防御 × 普通/必杀/超杀 → system.json 的哪一项(§4.4 第 5 条)。"""
    table = _HITSTOP_REF_BLOCK[move.kind] if blocked else _HITSTOP_REF_HIT[move.kind]
    return getattr(cfg.hitstop, table)


@pytest.mark.parametrize("move_id,hit_expect,block_expect", [
    ("st_C", 11, 9),             # 附录 B:普通 11/9
    ("burn_knuckle_A", 13, 10),  # 附录 B:必杀 13/10
    ("power_geyser_A", 20, 14),  # 附录 B:超杀 20/14
])
def test_hitstop_kind_mapping(move_id, hit_expect, block_expect, moves, cfg):
    """hitstop 取值:与测试内独立实现的映射对照,且等于附录 B 金标。"""
    counter = fresh_counter(cfg)
    r_hit = combat.resolve(make_atk(moves[move_id]), make_view(), counter, cfg)
    r_blk = combat.resolve(make_atk(moves[move_id]), make_view(guarding=True),
                           counter, cfg)
    assert r_hit.hitstop == _hitstop_ref(cfg, moves[move_id], False) == hit_expect
    assert r_blk.hitstop == _hitstop_ref(cfg, moves[move_id], True) == block_expect
