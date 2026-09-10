"""tests/test_physics.py — 纯函数物理(重力/跳弧/走跑/推背/墙角,§6 测试计划)。

数值全部从 system.json 加载值断言,不在测试里硬编码;
关键公式(跳高/滞空)在测试内独立复算,不 import 生产实现照抄。
"""
import pytest

from game.core import data, physics


@pytest.fixture(scope="module")
def cfg():
    return data.load_system()


# ---------- 重力与跳弧 ----------


def test_gravity_direction(cfg):
    # vy 向上为正 → apply_gravity 必须减(重力存负数),独立复算一帧
    assert physics.apply_gravity(8.0, cfg) == pytest.approx(8.0 + cfg.gravity)


def test_jump_arc_small_and_big(cfg):
    # 小跳 vy0=+4.0、前小跳 vx 用 small_fwd_vx(设计文档 §4.3 小跳规则)
    j = cfg.jump
    vx, vy0 = physics.jump_arc("small_fwd", 1, cfg)
    assert vy0 == j.small_vy0 and vx == j.small_fwd_vx
    # 大前跳:big_vy0 + fwd_vx
    vx, vy0 = physics.jump_arc("fwd", 1, cfg)
    assert vy0 == j.big_vy0 and vx == j.fwd_vx
    # 后跳向身后(面朝右 → vx 为负),back_vx 存正数大小
    vx, _ = physics.jump_arc("back", 1, cfg)
    assert vx == -j.back_vx
    # 镜像:面朝左的前跳 = 面朝右的后跳方向
    assert physics.jump_arc("fwd", -1, cfg)[0] == pytest.approx(-j.fwd_vx)
    # 原地跳无水平速度
    assert physics.jump_arc("up", 1, cfg)[0] == 0.0


def test_jump_height_matches_theory(cfg):
    """契约独立复算:理论跳高 vy0^2/(2|g|);模拟积分的最高点必须 <=2px 内。

    梯形积分的意义就在这条——前向欧拉会差出 4px 过不了关。
    """
    for vy0 in (cfg.jump.big_vy0, cfg.jump.small_vy0, cfg.juggle_bounce_vy):
        theory = vy0 * vy0 / (2 * abs(cfg.gravity))
        y, vy, peak = 0.0, vy0, 0.0
        while True:
            y, vy, landed = physics.air_step(y, vy, cfg)
            peak = max(peak, y)
            if landed:
                break
        assert abs(peak - theory) <= 2.0, (vy0, peak, theory)
        # 独立实现的理论公式再核一遍 physics 的封装
        assert physics.jump_peak(vy0, cfg) == pytest.approx(theory)


def test_airtime_frames(cfg):
    """滞空帧数精确断言(§6):2*vy0/|g| 取整附近,以积分权威值为准。

    大跳 vy0=8.0:连续公式 2*8/0.35 ≈ 45.7 → 46 帧;
    airtime 用与 fighter 同一套积分,断言逐帧精确值。
    """
    # 测试内独立模拟一遍(不调用 jump_airtime),核 physics 封装没算错
    def sim_airtime(vy0):
        y, vy, n = 0.0, vy0, 0
        while True:
            y, vy, landed = physics.air_step(y, vy, cfg)
            n += 1
            if landed:
                return n

    for vy0 in (cfg.jump.big_vy0, cfg.jump.small_vy0):
        mine, theirs = sim_airtime(vy0), physics.jump_airtime(vy0, cfg)
        assert mine == theirs
        # 连续理论值 2*vy0/|g| 的 ±1 帧内(离散积分的固有差)
        assert abs(mine - 2 * vy0 / abs(cfg.gravity)) <= 1.0


def test_air_step_lands_exactly_at_zero(cfg):
    # 落地帧 y 必须夹回 0、vy 清零(不许穿地、不许留残速)
    y, vy, landed = physics.air_step(0.1, -6.0, cfg)
    assert landed and y == 0.0 and vy == 0.0


# ---------- 走跑 ----------


def test_walk_run_speeds(cfg):
    # 走:前=fwd、后=-back(back 存正数大小);跑沿 facing
    assert physics.walk_step("fwd", 1, cfg) == cfg.walk.fwd
    assert physics.walk_step("back", 1, cfg) == -cfg.walk.back
    assert physics.walk_step("back", -1, cfg) == cfg.walk.back  # 面朝左后退=向右
    assert physics.run_step(1, cfg) == cfg.run.speed
    assert physics.run_step(-1, cfg) == -cfg.run.speed


# ---------- 推背与墙角 ----------


def test_pushback_open_space(cfg):
    # 空场:受方退满 pushback、攻方不动
    v, a = physics.pushback_resolve(300.0, 260.0, 12.0, 0.0, cfg.stage.width)
    assert v == 312.0 and a == 260.0


def test_pushback_corner_attacker_rebounds(cfg):
    """墙角规则(§4.4 第 6 条):受方贴墙退不动 → 攻方被推等量;双方不出界。"""
    w = cfg.stage.width
    # 受方在右墙(x=640)被向右推 → 一步都退不了,攻方退满推背量
    v, a = physics.pushback_resolve(w, 600.0, 12.0, 0.0, w)
    assert v == w and a == 588.0
    # 左墙同理(方向对称)
    v, a = physics.pushback_resolve(0.0, 40.0, 12.0, 0.0, w)
    assert v == 0.0 and a == 52.0


def test_pushback_partial_corner(cfg):
    # 受方离墙只够退一半:受方退到贴墙、攻方退剩下的一半
    w = cfg.stage.width
    v, a = physics.pushback_resolve(636.0, 600.0, 12.0, 0.0, w)
    assert v == w and a == 592.0  # 636+4=640 贴墙,攻方退 12-4=8


def test_pushback_never_out_of_stage(cfg):
    # 枚举边界组合,双方 x 永远在 [0, width] 内(不许把人推出舞台)
    w = cfg.stage.width
    for xv in (0.0, 1.0, w / 2, w - 1.0, w):
        for xa in (0.0, 1.0, w / 2, w - 1.0, w):
            for pb in (0.0, 8.0, 16.0, 40.0):
                v, a = physics.pushback_resolve(xv, xa, pb, 0.0, w)
                assert 0.0 <= v <= w and 0.0 <= a <= w


# ---------- 推挤 ----------


def test_push_apart_no_overlap(cfg):
    # 已分离:原样返回(不许凭空挪人)
    x1, x2 = physics.push_apart(100.0, 200.0, 32.0, 0.0, cfg.stage.width)
    assert (x1, x2) == (100.0, 200.0)


def test_push_apart_symmetric(cfg):
    # 重叠 8px → 各退 4px(对称),中点不动
    w = cfg.stage.width
    x1, x2 = physics.push_apart(100.0, 124.0, 32.0, 0.0, w)
    assert x1 == pytest.approx(96.0) and x2 == pytest.approx(128.0)
    assert (x1 + x2) / 2 == pytest.approx(112.0)  # 原中点 112 保持


def test_push_apart_order_agnostic(cfg):
    # 传参顺序颠倒,同一"人"落点必须一致(在 124 的人两次都到 128)
    w = cfg.stage.width
    a = physics.push_apart(124.0, 100.0, 32.0, 0.0, w)
    b = physics.push_apart(100.0, 124.0, 32.0, 0.0, w)
    assert a[0] == b[1] == pytest.approx(128.0)
    assert a[1] == b[0] == pytest.approx(96.0)


def test_push_apart_clamped_to_stage(cfg):
    # 贴左角两人重叠:推不开满宽也绝不出界
    w = cfg.stage.width
    x1, x2 = physics.push_apart(2.0, 10.0, 32.0, 0.0, w)
    assert 0.0 <= x1 <= w and 0.0 <= x2 <= w
    assert x2 - x1 >= 8.0 or (x1 <= 0.0 or x2 >= w)  # 推不开仅当已到墙
    # 右角同理
    x1, x2 = physics.push_apart(w - 10.0, w - 2.0, 32.0, 0.0, w)
    assert 0.0 <= x1 <= w and 0.0 <= x2 <= w


# ---------- 逐方推挤(fighter 每帧调用版) ----------


def test_push_apart_full_separates_at_once(cfg):
    """fighter 逐方推挤:自己全额退到与对手贴框,一轮分离。

    对称版每帧只消一半重叠,双方逐帧调用会无限渐近(冒烟时 31/32);
    逐方版后 step 的一方看到分离即无操作,一次到位。
    """
    w = cfg.stage.width
    me, other = physics.push_apart_full(300.0, 316.0, 32.0, 0.0, w)
    assert other == 316.0 and me == pytest.approx(284.0)  # 自己退满 16
    # 已分离:原样返回(不许凭空挪)
    me, other = physics.push_apart_full(200.0, 240.0, 32.0, 0.0, w)
    assert (me, other) == (200.0, 240.0)
    # 方向对称:自己在右侧 → 向右退开
    me, other = physics.push_apart_full(316.0, 300.0, 32.0, 0.0, w)
    assert me == pytest.approx(332.0) and other == 300.0
    # 贴角推不开也不出界(被墙顶住就顶住)
    me, _ = physics.push_apart_full(6.0, 20.0, 32.0, 0.0, w)
    assert me == 0.0  # 20-32=-12 → clamp 到 0
