"""tests/test_data.py — 数据 loader 与校验(设计文档 §6 测试计划 test_data 组)。

跑法:cd ~/kof98 && ./test.sh
批次:batch 0(契约冻结);数值断言对齐设计文档附录 A/B/C 基线。
纯逻辑测试,不碰 pygame,不需要 dummy 驱动。
"""
import json

import pytest

from game import poses
from game.core import data
from game.core.data import DataError


@pytest.fixture(scope="module")
def moves():
    return data.load_moves()


@pytest.fixture(scope="module")
def system():
    return data.load_system()


@pytest.fixture(scope="module")
def ai():
    return data.load_ai()


@pytest.fixture(scope="module")
def raw_moves():
    # 模块级一次读盘,后面所有异常用例都在这份深拷贝上改
    return json.loads((data.DATA_DIR / "terry.json").read_text(encoding="utf-8"))


# ---------- 正常加载(附录 A 基线的金标断言) ----------


def test_moves_count_and_unique(moves):
    # 26 招:8 地面普通 + 4 空中普通 + 10 必杀(5种×ABCD版) + 2 超杀 + 2 投
    assert len(moves) == 26
    assert len(set(moves)) == len(moves)


def test_st_c_golden(moves):
    """st_C 重拳按附录 A:6/3/16 帧、伤 80、硬直 17/12、推背 12/14、可取消必杀和超杀。"""
    c = moves["st_C"]
    assert c.windows[0].start == 6 and c.windows[0].end == 8
    assert c.damage == 80 and c.hitstun == 17 and c.blockstun == 12
    assert c.pushback_hit == 12 and c.pushback_block == 14
    assert set(c.cancels) == {"special", "super"}
    assert c.guard == "mid" and c.knockdown == "none"


def test_total_recompute(moves):
    """契约独立复算(照 sheepandsheep 套路,不依赖生产代码的属性):
    startup + active + recovery == total。
    """
    for name in ("st_A", "st_C", "cr_D", "burn_knuckle_A", "power_geyser_A"):
        m = moves[name]
        w = m.windows[0]
        active = w.end - w.start + 1
        recovery = m.total - m.windows[-1].end - 1
        assert w.start + active + recovery == m.total, name


def test_cr_d_sweep_low(moves):
    # 扫堂腿:低段(站防挡不住)+ 扫倒
    d = moves["cr_D"]
    assert d.guard == "low" and d.knockdown == "sweep"


def test_air_moves_until_land(moves):
    # 空中四技:判定直到落地(end=-1)、高段(蹲防挡不住)
    for name in ("j_A", "j_B", "j_C", "j_D"):
        m = moves[name]
        assert m.stance == "air" and m.windows[0].end == -1 and m.guard == "high", name


def test_power_wave_projectile(moves):
    a = moves["power_wave_A"]
    assert a.windows == ()
    assert a.projectile["speed"] == 3.5 and a.projectile["max_count"] == 1
    assert a.projectile["start"] == 14  # 发波帧=附录A帧数表的 startup(14/—/26)
    assert a.total == 40 and a.damage == 60 and a.chip == 8
    assert moves["power_wave_C"].projectile["speed"] == 4.5
    assert moves["power_wave_C"].projectile["start"] == 18
    assert moves["power_wave_C"].total == 48


def test_rising_tackle_charge(moves):
    a = moves["rising_tackle_A"]
    assert a.input["type"] == "charge"
    assert a.input["charge_dir"] == "2" and a.input["release_dir"] == "8"
    assert (0, 7) in a.invuln and a.total == 46 and a.damage == 110
    assert moves["rising_tackle_C"].damage == 140


def test_power_dunk_two_windows(moves):
    """Power Dunk 两段判定:第一段窗覆盖为不倒地,第二段沿用招级 hard。"""
    b = moves["power_dunk_B"]
    assert len(b.windows) == 2
    assert b.windows[0].knockdown == "none"
    assert b.windows[1].knockdown is None  # None = 沿用招级
    assert b.knockdown == "hard"
    assert b.windows[1].start > b.windows[0].end  # 两窗不重叠


def test_super_cost_rule(moves):
    for name, m in moves.items():
        if m.kind == "SUPER":
            assert m.gauge_cost > 0, name
        else:
            assert m.gauge_cost == 0, name
    g = moves["power_geyser_A"]
    assert g.damage == 300 and g.gauge_cost == 100 and g.total == 49


def test_throw_defs(moves):
    f = moves["throw_fwd"]
    assert f.kind == "THROW" and f.guard == "unblockable" and f.throw_range == 28
    assert f.windows == () and f.projectile is None and f.motion is None
    assert f.damage == 110 and f.total == 25
    assert moves["throw_back"].input["dir"] == "back"
    for name in ("throw_fwd", "throw_back"):
        assert moves[name].pose_key == "throw_grab"


def test_pose_coverage(moves):
    # 每一招的 pose_key 必须在注册表里(loader 已校验,这里兜底再验一遍防绕过)
    for name, m in moves.items():
        assert m.pose_key in poses.POSE_KEYS, name


def test_motion_specs(moves):
    assert moves["burn_knuckle_A"].motion == {"vx": 6.0, "frames": 18}
    assert moves["crack_shoot_B"].motion["until"] == "land"
    assert moves["power_dunk_B"].motion["from_frame"] == 14
    assert moves["rising_tackle_C"].motion["vy0"] == 8.0


# ---------- system 基线(附录 B) ----------


def test_system_golden(system):
    s = system
    assert (s.view.w, s.view.h, s.view.scale) == (320, 224, 3)
    assert s.fps == 60 and s.health == 1000 and s.round_time_frames == 3600
    assert s.rounds_to_win == 2
    assert s.gravity == -0.35  # y 向上为正 → 重力必须为负
    assert s.jump.big_vy0 == 8.0 and s.jump.small_vy0 == 4.0
    assert s.walk.fwd == 2.4 and s.walk.back == 2.0
    assert s.run.speed == 4.6
    assert s.hitstop.hit_normal == 11 and s.hitstop.hit_super == 20
    assert s.stage.ground_y == 190 and s.stage.start_x == (248, 392)
    assert s.input.button_buffer == 10 and s.input.charge_frames == 40
    assert s.throw_range == 28


def test_combo_scaling(system):
    sc = system.combo_scaling
    assert sc[0] == 100 and sc[-1] == 50
    # 单调不增(伤害越打越少)
    assert all(a >= b for a, b in zip(sc, sc[1:]))


def test_stage_camera_consistent(system):
    # 摄像机 clamp 上限必须正好 = 舞台宽 - 视图宽,否则会看到舞台外
    assert system.camera.clamp[1] == system.stage.width - system.view.w
    assert system.stage.width > system.view.w


def test_body_boxes(system):
    assert system.hurt_boxes["stand"] == data.T.Box(-15, 0, 15, 92)
    assert system.hurt_boxes["crouch"] == data.T.Box(-15, 0, 15, 58)
    assert set(system.push_boxes) == {"stand", "crouch"}


# ---------- ai 基线(附录 C) ----------


def test_ai_golden(ai):
    assert ai.seed == 42 and ai.reaction_interval == 6
    assert ai.bands == {"far": 160, "close": 90}
    assert set(ai.weights) == {"far", "mid", "close"}
    for band, w in ai.weights.items():
        assert abs(sum(w.values()) - 1.0) <= 0.02, band
    r = ai.reactions
    assert r["block_prob"] == 0.55 and r["antiair_prob"] == 0.75 and r["antiair_dist"] == 120


# ---------- 异常:校验必须报 DataError 并带定位信息,不许静默 ----------


def _mutate_move(raw, name, **changes):
    d = json.loads(json.dumps(raw))
    for m in d["moves"]:
        if m["name"] == name:
            m.update(changes)
            return d
    raise AssertionError(f"找不到招 {name}")


def test_negative_window_start(raw_moves):
    bad = _mutate_move(raw_moves, "st_C", windows=[{"start": -1, "end": 8, "hit": [[30, 60, 66, 80]]}])
    with pytest.raises(DataError, match="st_C"):
        data.build_moves(bad)


def test_invalid_box(raw_moves):
    bad = _mutate_move(raw_moves, "st_A", windows=[{"start": 3, "end": 4, "hit": [[24, 58, 10, 74]]}])
    with pytest.raises(DataError, match="判定框"):
        data.build_moves(bad)


def test_box_below_ground(raw_moves):
    # y1 为负 = 判定框伸到地底下,必须报错
    bad = _mutate_move(raw_moves, "cr_B", windows=[{"start": 4, "end": 6, "hit": [[22, -12, 50, 28]]}])
    with pytest.raises(DataError, match="y1"):
        data.build_moves(bad)


def test_zero_damage(raw_moves):
    bad = _mutate_move(raw_moves, "st_B", damage=0)
    with pytest.raises(DataError, match="damage"):
        data.build_moves(bad)


def test_missing_field(raw_moves):
    d = json.loads(json.dumps(raw_moves))
    for m in d["moves"]:
        if m["name"] == "st_B":
            del m["damage"]
            break
    with pytest.raises(DataError, match="缺字段 damage"):
        data.build_moves(d)


def test_super_without_cost(raw_moves):
    bad = _mutate_move(raw_moves, "power_geyser_A", gauge_cost=0)
    with pytest.raises(DataError, match="SUPER"):
        data.build_moves(bad)


def test_throw_with_windows(raw_moves):
    bad = _mutate_move(raw_moves, "throw_fwd", windows=[{"start": 3, "end": 4, "hit": [[20, 40, 50, 80]]}])
    with pytest.raises(DataError, match="投技"):
        data.build_moves(bad)


def test_unknown_pose_key(raw_moves):
    bad = _mutate_move(raw_moves, "st_D", pose_key="st_D_never")
    with pytest.raises(DataError, match="未注册姿势"):
        data.build_moves(bad)


def test_strike_with_no_windows_no_projectile(raw_moves):
    bad = _mutate_move(raw_moves, "st_D", windows=[])
    with pytest.raises(DataError, match="既无判定窗也不发波"):
        data.build_moves(bad)


def test_duplicate_move_name(raw_moves):
    d = json.loads(json.dumps(raw_moves))
    d["moves"].append(json.loads(json.dumps(d["moves"][0])))  # 复制第一招 → 重名
    with pytest.raises(DataError, match="重复"):
        data.build_moves(d)


def _raw_system():
    return json.loads((data.DATA_DIR / "system.json").read_text(encoding="utf-8"))


def test_system_positive_gravity():
    bad = _raw_system()
    bad["gravity"] = 0.35
    with pytest.raises(DataError, match="gravity"):
        data.build_system(bad)


def test_system_wrong_fps():
    bad = _raw_system()
    bad["fps"] = 30
    with pytest.raises(DataError, match="fps"):
        data.build_system(bad)


def test_system_bad_scaling():
    bad = _raw_system()
    bad["combo_scaling"] = [100, 120, 80]
    with pytest.raises(DataError, match="combo_scaling"):
        data.build_system(bad)


def test_ai_weight_sum():
    bad = json.loads((data.DATA_DIR / "ai.json").read_text(encoding="utf-8"))
    bad["weights"]["far"]["wait"] = 0.05  # 和掉到 0.85
    with pytest.raises(DataError, match="权重和"):
        data.build_ai(bad)


def test_ai_bad_reaction_key():
    bad = json.loads((data.DATA_DIR / "ai.json").read_text(encoding="utf-8"))
    bad["reactions"]["blok_prob"] = 0.5  # 手滑打错键名,必须被抓住
    with pytest.raises(DataError, match="未知键"):
        data.build_ai(bad)
