"""tests/test_anim.py — 出招 timing 对齐(素材系统 v2,设计文档 §11.2B)。

跑法:cd ~/kof98 && ./test.sh
核心黄金断言:判定窗生效的每一拍,显示的必须是"挥出帧"(n-1-k+i)——
这就是"打击帧=判定帧";对程序绘制与真实贴图同样生效(同一函数)。
纯函数测试(attack_anim_frame 只吃 MoveDef + 数字)。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (game.ui 模块级 import 需要;不初始化显示)

import pytest  # noqa: E402

from game import poses  # noqa: E402
from game.core.data import load_moves  # noqa: E402
from game.ui import attack_anim_frame  # noqa: E402


@pytest.fixture(scope="module")
def moves():
    return load_moves()


def test_st_c_strike_exactly_on_window(moves):
    n = poses.POSE_KEYS["st_C"]  # 3 帧:起手/挥出/收招
    mv = moves["st_C"]
    s, e = mv.windows[0].start, mv.windows[0].end
    assert attack_anim_frame(mv, s - 1, n) == 0   # 窗前最后一拍仍是起手
    for af in range(s, e + 1):
        assert attack_anim_frame(mv, af, n) == 1   # 判定期逐拍=挥出帧
    assert attack_anim_frame(mv, e + 1, n) == 2   # 窗后进收招


def test_golden_all_moves_strike_aligns(moves):
    """全招黄金断言:每个判定窗内每一拍 → 对应挥出帧(数据驱动,不挑招)。"""
    for name, mv in moves.items():
        if mv.kind == "THROW" or not mv.windows:
            continue  # 投技不走攻击取帧;发波招另有专项
        n = poses.POSE_KEYS[mv.pose_key]
        k = min(len(mv.windows), n - 1)
        for i, w in enumerate(mv.windows):
            expect = n - 1 - k + i
            end = w.end if w.end >= 0 else w.start + 2
            for af in range(w.start, end + 1):
                got = attack_anim_frame(mv, af, n)
                assert got == expect, (
                    f"{name}:窗{i} af={af} 期望挥出帧{expect},得到{got}")


def test_power_wave_strike_at_projectile_start(moves):
    """发波招无判定窗 → projectile.start(14/18)当打击时刻。"""
    for name, sp in (("power_wave_A", 14), ("power_wave_C", 18)):
        mv = moves[name]
        n = poses.POSE_KEYS[mv.pose_key]  # 3
        assert attack_anim_frame(mv, sp - 1, n) == 0   # 发射前:起手
        for af in range(sp, sp + 3):
            assert attack_anim_frame(mv, af, n) == 1  # 发射拍:挥出
        assert attack_anim_frame(mv, sp + 3, n) == 2   # 发射后:收招


def test_power_dunk_two_windows_hold_through_gap(moves):
    """Power Dunk 双窗:窗间空隙保持第一挥出帧(手臂不缩回),过末窗收招。"""
    mv = moves["power_dunk_B"]
    n = poses.POSE_KEYS[mv.pose_key]  # 5 帧:起手×2/挥出×2/收招
    w1, w2 = mv.windows[0], mv.windows[1]
    assert attack_anim_frame(mv, w2.start - 1, n) == 2  # 窗间:第 1 挥出帧
    assert attack_anim_frame(mv, w2.start, n) == 3      # 第 2 窗起:第 2 挥出帧
    assert attack_anim_frame(mv, w2.end + 1, n) == 4   # 过末窗:收招
    # 全程取帧单调不回跳(起手 0..1 → 挥出 2..3 → 收招 4)
    seq = [attack_anim_frame(mv, af, n) for af in range(mv.total)]
    assert seq == sorted(seq)


def test_startup_windup_spreads(moves):
    """起手帧均匀铺满 startup:st_C 6 帧起手期显示帧 0(n=3 时只有 1 张起手)。"""
    mv = moves["st_C"]
    for af in range(mv.windows[0].start):
        assert attack_anim_frame(mv, af, 3) == 0


def test_single_frame_pose_degrades_to_zero(moves):
    for mv in (moves["st_C"], moves["power_dunk_B"], moves["power_wave_A"]):
        assert attack_anim_frame(mv, 3, 1) == 0  # n≤1 退化
