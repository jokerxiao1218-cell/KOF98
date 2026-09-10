"""tests/test_projectile.py — 飞行道具(设计文档 §6 测试计划 test_projectile 组)。

纯逻辑测试,不碰 pygame。数值断言对附录 A/B 冻结基线。
"同屏一发"(max_count)与"命中标记"由持有方(fighter/match)执行,
不在本文件——这里只验弹体实体与弹体裁决本身。

几何布局:受方 P2 x=300(站姿受击框 [285,315)×[0,92));
能量波 A 弹框 [x, x+24)×[0,20)、速度 3.5px/帧 → 与受方相交需 x>261 且 x<315
(测试内独立心算,驱动"飞过去才命中"的时序断言)。
"""
import pytest

from game.core import combat
from game.core import data
from game.core import types as T
from game.core.combat import ComboCounter
from game.core.projectile import Projectile


@pytest.fixture(scope="module")
def moves():
    return data.load_moves()


@pytest.fixture(scope="module")
def cfg():
    return data.load_system()


# 附录 B 基线(写死以便独立复算)
STAND_HURT = T.Box(-15, 0, 15, 92)
BOUNDS = (0.0, 640.0)  # 附录 B:舞台宽 640


def make_view(x=300.0, *, side=T.Side.P2, guarding=False, crouch=False):
    """受方只读视图(hurt 框 = 附录 B 基线框平移到 x)。"""
    base = T.Box(-15, 0, 15, 58) if crouch else STAND_HURT
    return T.FighterView(
        side=side, x=x, y=0.0, facing=-1, state="idle", move_id=None,
        airborne=False, crouching=crouch, guarding=guarding,
        guard_stance="crouch" if crouch else "stand",
        in_hitstun=False, invulnerable=False,
        hurt=(T.Box(base.x1 + x, base.y1, base.x2 + x, base.y2),),
    )


def fresh(cfg):
    return ComboCounter(cfg.combo_scaling)


# ---------- 实体:推进与存活 ----------


def test_step_advances_by_speed(moves):
    """§6:A 版能量波 3.5px/帧(附录 A),按朝向前进。"""
    p = Projectile(moves["power_wave_A"], x=250.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    assert p.x == 250.0
    p.step()
    assert p.x == 253.5  # 250 + 3.5
    p.step()
    assert p.x == 257.0


def test_step_facing_left(moves):
    # 面左发射 → 往左飞(速度大小不变,方向随 facing)
    p = Projectile(moves["power_wave_A"], x=250.0, facing=-1,
                  side=T.Side.P1, bounds=BOUNDS)
    p.step()
    assert p.x == 246.5  # 250 − 3.5


def test_power_wave_c_speed(moves):
    # C 版弹速 4.5(附录 A)
    p = Projectile(moves["power_wave_C"], x=250.0, facing=1,
                   side=T.Side.P2, bounds=BOUNDS)
    p.step()
    assert p.x == 254.5


def test_y_always_zero(moves):
    # 地面弹:y 恒 0,飞多久都不离地
    p = Projectile(moves["power_wave_A"], x=100.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    for _ in range(20):
        p.step()
    assert p.y == 0.0


# ---------- 实体:判定框 ----------


def test_boxes_facing_right(moves):
    # 面右:弹体框在发射点行进方向一侧 [x, x+24)(源框 [0,0,24,20))
    p = Projectile(moves["power_wave_A"], x=250.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    (b,) = p.boxes()
    assert (b.x1, b.y1, b.x2, b.y2) == (250.0, 0, 274.0, 20)


def test_boxes_facing_left(moves):
    """§6:facing=−1 时 boxes() 在 x 左侧(Box.mirrored 后平移)。"""
    p = Projectile(moves["power_wave_A"], x=250.0, facing=-1,
                   side=T.Side.P1, bounds=BOUNDS)
    (b,) = p.boxes()
    assert (b.x1, b.y1, b.x2, b.y2) == (226.0, 0, 250.0, 20)
    assert b.x2 <= p.x  # 整个框在弹体原点左边


# ---------- 实体:存活 ----------


def test_alive_within_bounds_and_leaves(moves):
    """§6 出界消失:alive = 在 [0,640](含端点)且未被打掉,出界即 False。"""
    p = Projectile(moves["power_wave_A"], x=636.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    assert p.alive            # 还在界内
    p.step(); p.step()        # 636 → 643
    assert not p.alive        # 出右界
    q = Projectile(moves["power_wave_A"], x=4.0, facing=-1,
                   side=T.Side.P2, bounds=BOUNDS)
    assert q.alive
    q.step()                  # 4 → 0.5
    assert q.alive            # 端点内仍算活
    q.step()                  # 0.5 → −3
    assert not q.alive


def test_on_hit_marks_dead(moves):
    # 命中后调用方标 dead:还在界内也判死
    p = Projectile(moves["power_wave_A"], x=264.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    assert p.alive
    p.on_hit()
    assert not p.alive


# ---------- 裁决:命中/whiff/防御 ----------


def test_projectile_flies_and_connects(moves, cfg):
    """时序几何:发射点 250 打不到 300 处受方;step 3 帧仍差 0.5px,第 4 帧命中。

    独立复算:相交需弹框 x2=x+24 > 285 且 x1=x < 315 → 261 < x < 315;
    250→253.5→257→260.5(框到 284.5,差 0.5 打不到)→264 命中。
    """
    p = Projectile(moves["power_wave_A"], x=250.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    view = make_view()
    assert combat.resolve_projectile(p, view, fresh(cfg), cfg) is None
    for _ in range(3):
        p.step()
    assert p.x == 260.5
    assert combat.resolve_projectile(p, view, fresh(cfg), cfg) is None  # 284.5 < 285
    p.step()
    assert p.x == 264.0
    r = combat.resolve_projectile(p, view, fresh(cfg), cfg)
    assert r is not None and r.kind == "hit"


def test_resolve_projectile_hit_golden(moves, cfg):
    """§6 弹命中金标(附录 A/B):远程攻方不涨气、只冻受方是约定。"""
    p = Projectile(moves["power_wave_A"], x=264.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    r = combat.resolve_projectile(p, make_view(), fresh(cfg), cfg)
    assert r is not None
    assert r.kind == "hit" and r.move == "power_wave_A"
    assert r.attacker is T.Side.P1 and r.victim is T.Side.P2
    assert r.damage == 60         # 附录 A:能量波A 60,第一击 100%
    assert r.hitstop == 8         # 附录 B:projectile_victim=8(只冻结受方)
    assert r.stun == 16           # 附录 A:hs=16
    assert r.pushback == 8        # 附录 A:pb 命中 8
    assert r.knockdown == "none"
    assert r.gauge_attacker == 0  # 远程命中不涨气(约定,move.gauge_gain=4 也不给)
    assert r.gauge_victim == 5     # 被击 +5
    assert r.juggle_vy == 0.0


def test_resolve_projectile_block_chip(moves, cfg):
    """§6:防御弹 → 削血 8(power_wave_A chip=8),硬直/推背按防御档。"""
    p = Projectile(moves["power_wave_A"], x=264.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    r = combat.resolve_projectile(p, make_view(guarding=True), fresh(cfg), cfg)
    assert r.kind == "block"
    assert r.damage == 8          # 削血 = chip
    assert r.hitstop == 8         # 防御弹同样只冻结受方 8 帧
    assert r.stun == 11           # 附录 A:bs=11
    assert r.pushback == 10       # 附录 A:pb 防御 10
    assert r.gauge_victim == 2 and r.gauge_attacker == 0


def test_resolve_projectile_whiff(moves, cfg):
    # 弹够不着(受方在 400,弹框最远 274)→ None
    p = Projectile(moves["power_wave_A"], x=250.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    assert combat.resolve_projectile(p, make_view(x=400.0), fresh(cfg), cfg) is None


def test_resolve_projectile_no_side_effects(moves, cfg):
    """§6:命中后调用方标 dead——裁决自身必须无副作用(不动弹、不判死)。"""
    p = Projectile(moves["power_wave_A"], x=264.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    r = combat.resolve_projectile(p, make_view(), fresh(cfg), cfg)
    assert r is not None
    assert p.x == 264.0 and p.alive   # resolve 没有顺手做任何事
    p.on_hit()                         # 标 dead 是调用方的责任
    assert not p.alive


def test_projectile_scaling_via_counter(moves, cfg):
    # 弹伤害同样吃连段缩放:同一 counter 第二发 60 → 54(×90%)
    counter = fresh(cfg)
    p = Projectile(moves["power_wave_A"], x=264.0, facing=1,
                   side=T.Side.P1, bounds=BOUNDS)
    first = combat.resolve_projectile(p, make_view(), counter, cfg)
    second = combat.resolve_projectile(p, make_view(), counter, cfg)
    assert first.damage == 60 and second.damage == 54
