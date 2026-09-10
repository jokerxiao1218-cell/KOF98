"""tests/test_match.py — 对局编排(设计文档 §6 测试计划 test_match 组)。

跑法:cd ~/kof98 && ./test.sh
批次:batch B。考卷条目与断言对应:
  * 完整三局两胜:2:0 / 2:1 / 双 KO 各记一局 / 超时血多者胜 / 同血平局;
  * 摄像机:中点跟随 + clamp,角色不越 [cam+8, cam+312];
  * hitstop:近身命中全局冻结 11 帧再恢复推进;弹体命中只冻受方 8 帧
    (§4.4"弹受方 8",攻方照动);
  * 能量波:发波帧生成、同屏 1 发(前弹未灭再搓不产新弹);
  * AI 集成冒烟:双 AI 自对弈不崩、血量界内、同种子两次跑结果一致。
纯逻辑测试,不碰 pygame。
"""
import dataclasses

import pytest

from game.core import types as T
from game.core.ai import TerryAI
from game.core.data import load_ai, load_moves, load_system
from game.core.match import ROUND_END_FRAMES, Match

E = T.EMPTY_TICK


@pytest.fixture(scope="module")
def system():
    return load_system()


@pytest.fixture(scope="module")
def moves():
    return load_moves()


def tick(dirs=(), pressed=(), released=()):
    return T.Tick(frozenset(dirs), frozenset(pressed), frozenset(released))


def qcf_a():
    """P1(面右)的 QCF+A 输入流:2 → 3 → 6 → 按A(§4.6 记法)。"""
    d, r = T.Dir.D, T.Dir.R
    return [tick((d,))] * 4 + [tick((d, r))] * 2 + [tick((r,))] * 2 + [
        tick((r,), (T.Btn.A,))
    ]


def land_st_c(m, atk_side):
    """atk 方贴近对手出一记站姿重拳,推进到命中帧返回。
    距离 60px 在 st_C 攻击框(60..66)×受击框(±15)的重叠区间 (45, 81) 内。
    """
    atk, victim = (m.f1, m.f2) if atk_side is T.Side.P1 else (m.f2, m.f1)
    victim.x = atk.x + 60.0 * atk.facing
    h0 = victim.health  # KO 场景预扣过血 → 必须以"这一拳真挨上"为命中判据
    press = tick(pressed=(T.Btn.C,))
    m.step(*((press, E) if atk_side is T.Side.P1 else (E, press)))
    for _ in range(15):
        m.step(E, E)
        if victim.health < h0 or m.phase != "fighting":
            return
    raise AssertionError("st_C 未命中")


def finish_round(m):
    """把 round_end 演出帧耗完(120 帧 → between_rounds / match_end)。"""
    for _ in range(ROUND_END_FRAMES):
        m.step(E, E)


# ---------- 管线冒烟 ----------


def test_idle_pipeline_smoke(system, moves):
    m = Match(system, moves)
    for _ in range(300):
        s = m.step(E, E)
    assert s.phase == "fighting"
    assert s.wins == (0, 0) and s.banners == ()
    assert s.timer_frames == system.round_time_frames - 300
    assert s.camera_x == 160  # (248+392)/2 − 160
    assert s.projectiles == ()
    for fs in s.fighters:
        assert fs.health == system.health and fs.state == "idle"


# ---------- 普通技命中与结算 ----------


def test_st_c_lands_damage_and_gauge(system, moves):
    m = Match(system, moves)
    land_st_c(m, T.Side.P1)
    assert m.f2.health == system.health - moves["st_C"].damage  # 80,首击 100%
    assert m.f1.gauge == moves["st_C"].gauge_gain  # 命中涨气(攻方)
    assert m.f2.gauge == system.gauge.on_hit_taken  # 挨打涨气(受方)
    assert m.f2.state == "hit_stand"
    # 推背:受方远离攻方 12px(一次性位移,无墙角)
    assert m.f2.x == pytest.approx(m.f1.x + 60.0 + moves["st_C"].pushback_hit)


def test_melee_hitstop_freezes_both(system, moves):
    """近身命中:攻受双方冻结 hit_normal 帧(=考卷"全局冻结 11 帧"),
    期间位置/状态/计时全停;冻结结束后恢复推进。"""
    m = Match(system, moves)
    land_st_c(m, T.Side.P1)
    n = system.hitstop.hit_normal
    assert m.freeze == {T.Side.P1: n, T.Side.P2: n}
    x1, x2, st = m.f1.x, m.f2.x, m.f2.state
    timer0 = m.round_timer
    for _ in range(n):
        m.step(E, E)
    assert m.f1.x == x1 and m.f2.x == x2  # 定格
    assert m.f2.state == st  # 硬直计时也停
    assert m.round_timer == timer0  # 计时冻结
    m.step(E, E)  # 冻结结束后的第一帧:恢复推进
    assert m.round_timer == timer0 - 1


def test_block_no_chip_but_stun_and_gauge(system, moves):
    """st_C 被站防:削血 chip=0 → 不掉血;受方涨气 on_block;攻方 0;
    双方冻结 block_normal 帧;受方进 blockstun 且被推离。"""
    m = Match(system, moves)
    m.f2.x = m.f1.x + 55.0
    guard = tick((T.Dir.R,))  # P2 面左,身后 = 右
    m.step(tick(pressed=(T.Btn.C,)), guard)
    for _ in range(12):
        m.step(E, guard)
        if m.f2.state == "blockstun":
            break
    assert m.f2.state == "blockstun"
    assert m.f2.health == system.health  # st_C chip=0
    assert m.f2.gauge == system.gauge.on_block
    assert m.f1.gauge == 0  # 被防攻方不涨气
    assert m.freeze == {T.Side.P1: system.hitstop.block_normal,
                        T.Side.P2: system.hitstop.block_normal}
    assert m.f2.x - m.f1.x >= 70.0  # 防御推背(55 起步 + 后撤 + pushback_block)


def test_attacker_corner_pushback(system, moves):
    """受方贴墙:推背只推得动一部分,剩余量改由攻方退
    (physics.pushback_resolve 第二返回值,A1 留给 match 的集成点)。"""
    m = Match(system, moves)
    m.f1.x, m.f2.x = 560.0, 632.0  # dx=72 在命中区间;受方顶到可视右缘
    m.step(tick(pressed=(T.Btn.C,)), E)
    a0 = m.f1.x
    for _ in range(15):
        m.step(E, E)
        if m.f2.health < system.health:
            break
    assert m.f2.health == system.health - moves["st_C"].damage
    # 受方 632 → 舞台界 640 只推得动 8px,余下 4px 反给攻方(远离受方);
    # 受方随后被摄像机夹回可视右缘(界外推背与可视夹紧的相互作用,批 D 调参点)
    space = system.stage.width - 632.0
    rest = moves["st_C"].pushback_hit - space
    assert m.f1.x == pytest.approx(a0 - rest)
    assert m.f1.x < a0  # 攻方确实被推开了
    wall = system.camera.clamp[1] + system.view.w - system.camera.edge_margin
    assert m.f2.x == pytest.approx(float(wall))


# ---------- 回合终局 ----------


def test_ko_perfect_banner(system, moves):
    m = Match(system, moves)
    m.f2.health = moves["st_C"].damage
    land_st_c(m, T.Side.P1)
    s = m.step(E, E)
    assert s.phase == "round_end"
    assert s.banners == ("PERFECT", "K.O.")  # 胜者满血 → PERFECT
    assert s.round_winner is T.Side.P1
    assert s.wins == (1, 0)
    assert s.fighters[0].state == "win" and s.fighters[1].state == "lose"


def test_double_ko_counts_both(system, moves):
    m = Match(system, moves)
    m.f2.x = m.f1.x + 60.0
    m.f1.health = 10
    m.f2.health = 10
    both = tick(pressed=(T.Btn.C,))
    m.step(both, both)  # 同帧对拍 → trade 互吃 → 双 KO
    for _ in range(15):
        s = m.step(E, E)
        if s.phase != "fighting":
            break
    assert s.phase == "round_end"
    assert s.banners == ("DOUBLE K.O.",)
    assert s.wins == (1, 1)  # 各记一胜(KOF 规则)
    assert s.round_winner is None


def test_timeout_healthier_wins(system, moves):
    m = Match(system, moves)
    m.round_timer = 5
    m.f2.health = 600
    for _ in range(6):
        s = m.step(E, E)
    assert s.phase == "round_end"
    assert s.banners == ("TIME OVER",)
    assert s.round_winner is T.Side.P1  # 血多者胜
    assert s.wins == (1, 0)


def test_timeout_draw_counts_both(system, moves):
    m = Match(system, moves)
    m.round_timer = 5
    for _ in range(6):
        s = m.step(E, E)
    assert s.phase == "round_end"
    assert s.banners == ("TIME OVER", "DRAW")
    assert s.wins == (1, 1)
    assert s.round_winner is None
    assert s.fighters[0].state == "lose" and s.fighters[1].state == "lose"


# ---------- 三局两胜 ----------


def test_match_2_0_with_gauge_carryover(system, moves):
    m = Match(system, moves)
    for rnd in (1, 2):
        m.f2.health = moves["st_C"].damage
        land_st_c(m, T.Side.P1)
        assert m.phase == "round_end"
        finish_round(m)
        if rnd == 1:
            assert m.phase == "between_rounds"
            assert m.f1.gauge == moves["st_C"].gauge_gain
            m.next_round()
            # gauge 保留到下一回合,血量回满,计时重置
            assert m.phase == "fighting" and m.round_no == 2
            assert m.f1.gauge == moves["st_C"].gauge_gain
            assert m.f2.gauge == system.gauge.on_hit_taken
            assert m.f1.health == system.health
            assert m.round_timer == system.round_time_frames
    assert m.phase == "match_end"
    assert m.match_winner is T.Side.P1
    assert m.wins[T.Side.P1] == 2 and m.wins[T.Side.P2] == 0


def test_match_2_1(system, moves):
    m = Match(system, moves)
    m.f1.health = moves["st_C"].damage  # 第 1 回合 P2 满 PERFECT 拿下
    land_st_c(m, T.Side.P2)
    assert m.round_winner is T.Side.P2
    assert m.wins[T.Side.P1] == 0 and m.wins[T.Side.P2] == 1
    finish_round(m)
    m.next_round()
    for _ in range(2):  # 第 2、3 回合 P1 连扳两局
        m.f2.health = moves["st_C"].damage
        land_st_c(m, T.Side.P1)
        finish_round(m)
        if m.phase == "between_rounds":
            m.next_round()
    assert m.phase == "match_end"
    assert m.match_winner is T.Side.P1
    assert m.wins[T.Side.P1] == 2 and m.wins[T.Side.P2] == 1


# ---------- 摄像机 ----------


def test_camera_follow_and_clamp(system, moves):
    m = Match(system, moves)
    m.f1.x, m.f2.x = 200.0, 400.0
    s = m.step(E, E)
    assert s.camera_x == 140  # 中点 300 − follow_mid_offset 160
    m.f1.x, m.f2.x = 10.0, 40.0
    s = m.step(E, E)
    assert s.camera_x == 0  # 左端 clamp
    m.f1.x, m.f2.x = 630.0, 638.0
    s = m.step(E, E)
    assert s.camera_x == system.camera.clamp[1]  # 320 = 舞台宽−视图宽
    assert s.fighters[1].x == pytest.approx(
        s.camera_x + system.view.w - system.camera.edge_margin)  # 夹回可视右缘
    for case in (s,):
        for fs in case.fighters:  # 考卷不变量:不越 [cam+8, cam+312]
            assert s.camera_x + system.camera.edge_margin <= fs.x
            assert fs.x <= s.camera_x + system.view.w - system.camera.edge_margin


# ---------- 能量波 ----------


def test_power_wave_spawn_at_frame(system, moves):
    m = Match(system, moves)
    for t in qcf_a():
        m.step(t, E)
    spawn = None
    for _ in range(25):  # 发波帧 = 按下后第 14 拍,留足余量
        s = m.step(E, E)
        if s.projectiles:
            spawn = s
            break
    assert spawn is not None
    pv = spawn.projectiles[0]
    assert pv.move_id == "power_wave_A" and pv.facing == 1
    assert 0.0 < pv.x - m.f1.x < 30.0  # 从拳前出发
    assert spawn.attack_frames[0] == moves["power_wave_A"].projectile["start"]
    x0 = pv.x
    s = m.step(E, E)
    assert s.projectiles[0].x - x0 == pytest.approx(
        moves["power_wave_A"].projectile["speed"])  # 匀速 3.5px/帧


def test_power_wave_single_on_screen(system, moves):
    """同屏 1 发:前弹未灭时再搓 QCF+A,招打得出来但不产新弹;
    前弹消失后可以再发。"""
    m = Match(system, moves)
    m.f2.x = 640.0  # 拉远,让第一发存活期盖过第二次发波尝试
    for t in qcf_a():
        m.step(t, E)
    for _ in range(25):
        s = m.step(E, E)
        if s.projectiles:
            break
    assert len(s.projectiles) == 1
    for _ in range(70):  # 等 P1 收招回 idle(波还在飞)
        if m.f1.state == "idle":
            break
        m.step(E, E)
    assert any(p.alive for p in m.projectiles)  # 第一发还活着
    for t in qcf_a():  # 第二次 QCF+A
        m.step(t, E)
    saw_spawn = False
    for _ in range(25):
        s = m.step(E, E)
        af = s.attack_frames[0]
        if af is not None and af >= moves["power_wave_A"].projectile["start"]:
            saw_spawn = True
            assert len(s.projectiles) <= 1  # 旧弹未灭 → 不产新弹
    assert saw_spawn  # 第二招确实打到了发波帧
    assert m.f2.health == system.health  # 波还没飞到 P2
    for _ in range(400):  # 等第一发消失(打中或出界)
        s = m.step(E, E)
        if not s.projectiles:
            break
    assert not s.projectiles
    for _ in range(70):
        if m.f1.state == "idle":
            break
        m.step(E, E)
    for t in qcf_a():  # 第三次:前弹已灭 → 能再发
        m.step(t, E)
    respawn = False
    for _ in range(25):
        s = m.step(E, E)
        if s.projectiles:
            respawn = True
            break
    assert respawn


def test_projectile_freezes_victim_only(system, moves):
    """弹体命中:hitstop 只冻受方(projectile_victim 帧),攻方照常行动
    ——§4.4"弹受方 8"与近身全局冻结的区别点。"""
    m = Match(system, moves)
    for t in qcf_a():
        m.step(t, E)
    for _ in range(200):
        m.step(E, E)
        if m.f2.health < system.health:
            break
    assert m.f2.health == system.health - moves["power_wave_A"].damage
    n = system.hitstop.projectile_victim
    assert m.freeze == {T.Side.P1: 0, T.Side.P2: n}  # 攻方不冻
    assert m.f2.state == "hit_stand"
    x2, s2 = m.f2.x, m.f2.state
    press_a = tick(pressed=(T.Btn.A,))
    entered = False
    for _ in range(n):  # 受方冻结期,攻方还能出招(此时已收招完)
        m.step(press_a, E)
        if m.f1.state == "attack":
            entered = True
    assert entered  # 冻结只属于受方,攻方行动自由
    assert m.f2.x == x2 and m.f2.state == s2  # 受方全程定格
    assert m.freeze == {T.Side.P1: 0, T.Side.P2: 0}  # 冻结耗尽


# ---------- AI 集成 ----------


def test_ai_self_play_invariants(system, moves):
    ai = load_ai()
    a1 = TerryAI(ai, moves, system)
    a2 = TerryAI(dataclasses.replace(ai, seed=7), moves, system)  # 错开种子
    m = Match(system, moves)
    for _ in range(600):
        s = m.step(a1.next_tick(m.ai_view(T.Side.P1)),
                   a2.next_tick(m.ai_view(T.Side.P2)))
        assert s.phase in ("fighting", "round_end", "between_rounds", "match_end")
        for fs in s.fighters:
            assert 0 <= fs.health <= system.health
            assert 0.0 <= fs.x <= system.stage.width
        assert s.timer_frames >= 0
    # 同种子跑两遍完全一致(Match + TerryAI 双重确定性)
    m2 = Match(system, moves)
    b1 = TerryAI(ai, moves, system)
    b2 = TerryAI(dataclasses.replace(ai, seed=7), moves, system)
    for _ in range(600):
        s2 = m2.step(b1.next_tick(m2.ai_view(T.Side.P1)),
                     b2.next_tick(m2.ai_view(T.Side.P2)))
    assert s.fighters == s2.fighters and s.wins == s2.wins
    assert s.timer_frames == s2.timer_frames
