"""tests/test_motion.py — 输入系统:缓冲/指令识别/蓄力/双击(设计文档 §6 test_motion 组)。

跑法:cd ~/kof98 && env -u PYTHONPATH .venv/bin/python -m pytest tests/test_motion.py -v
全部用合成 Tick 流逐帧喂 MotionInput;窗口数值一律从 system.json 的 input 节读
(方向窗24/按钮缓冲10/DP窗18/双QCF窗40/蓄力40帧/双击8帧),不在测试里写死。
"""
import pytest

from game.core.data import load_moves, load_system
from game.core.motion import MotionInput, relativize
from game.core.types import Dir, Btn, Tick


def t(dirs=(), pressed=()):
    """按帧构造 Tick:dirs=本帧按住的绝对方向(斜角=组合),pressed=本帧按下的按钮。"""
    return Tick(frozenset(dirs), frozenset(pressed), frozenset())


def run(mi, ticks, facing=1):
    """喂一串 Tick,返回每帧的 FrameTriggers 列表(下标=帧号)。"""
    return [mi.feed(tk, facing) for tk in ticks]


@pytest.fixture(scope="module")
def cfg():
    return load_system().input


@pytest.fixture(scope="module")
def moves():
    return load_moves()


# ---------- 相对化记法 ----------


def test_relativize_notation():
    # 数字键盘记法与镜像换算:facing=+1 物理 R=前(6)、↓+R=3;
    # facing=-1 物理 L=前(6)、↓+L=3、↓+R=1;U/D 不随朝向变。
    assert relativize(frozenset({Dir.R}), 1) == "6"
    assert relativize(frozenset({Dir.L}), 1) == "4"
    assert relativize(frozenset({Dir.D, Dir.R}), 1) == "3"
    assert relativize(frozenset({Dir.L}), -1) == "6"
    assert relativize(frozenset({Dir.D, Dir.L}), -1) == "3"
    assert relativize(frozenset({Dir.D, Dir.R}), -1) == "1"
    assert relativize(frozenset({Dir.U}), -1) == "8"


# ---------- QCF / 宽容 / 方向窗 / 按钮缓冲 ----------


def test_qcf_c_exactly_once(cfg, moves):
    # ↓↘→+C 逐帧(帧0↓ 帧1↓→ 帧2→ 完成),空几帧后在缓冲窗内按 C:
    # 恰好触发 power_wave_C 一次,后续帧不重复(窗已消耗)。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [
        t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)),
        t(), t(), t(),
        t((), (Btn.C,)), t(), t(),
    ])
    assert trigs[6].specials == ("power_wave_C",)  # 触发落在按钮按下那一帧
    assert sum(1 for x in trigs if x.specials) == 1  # 整条流只此一次
    assert trigs[7].specials == () and trigs[8].specials == ()


def test_lenient_missing_diagonal(cfg, moves):
    # 宽容:2→6 直接跳过 3(键盘斜角=两轴同按,常被漏采)仍算 QCF;
    # QCB(2→4)同理。按钮 C/A 区分同指令的轻重版本。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.D,)), t((Dir.R,)), t((), (Btn.C,))])
    assert trigs[2].specials == ("power_wave_C",)
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.D,)), t((Dir.D, Dir.L)), t((Dir.L,)), t((), (Btn.A,))])
    assert trigs[3].specials == ("burn_knuckle_A",)


def test_dir_window_boundary(cfg, moves):
    # 方向窗:↓@0 →@24 首尾间隔恰 24(=dir_window)→ 仍算窗内触发;
    # 间隔 31(>24)超窗 → 不触发。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,))] + [t() for _ in range(23)] + [t((Dir.R,)), t((), (Btn.C,))]
    trigs = run(mi, ticks)  # 帧0↓ 帧1..23空 帧24→ 帧25 C
    assert trigs[25].specials == ("power_wave_C",)
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,))] + [t() for _ in range(30)] + [t((Dir.R,)), t((), (Btn.C,))]
    trigs = run(mi, ticks)  # 帧0↓ 帧1..30空 帧31→ 帧32 C:span=31>24
    assert all(not x.specials for x in trigs)


def test_button_buffer_window(cfg, moves):
    # 指令完成于帧1(↓@0 →@1);按钮与完成帧的间隔 <= button_buffer(10)
    # 才触发:第 9 帧按 → 触发;恰第 10 帧按 → 仍触发(<=);第 11 帧按 → 不触发。
    def press_after(gap):
        mi = MotionInput(cfg, moves)
        ticks = [t((Dir.D,)), t((Dir.R,))] + [t() for _ in range(gap - 1)] \
            + [t((), (Btn.C,))]
        return run(mi, ticks)[-1].specials  # 按钮落在帧 1+gap

    assert press_after(9) == ("power_wave_C",)
    assert press_after(10) == ("power_wave_C",)
    assert press_after(11) == ()


# ---------- 蓄力 ----------


def test_charge_40_then_release_button(cfg, moves):
    # 按住 ↓ 40 帧(帧0..39)后 ↑+A 同帧 → rising_tackle_A;
    # 满蓄后 charge_ready("8") 为 True,释放方向一出现即清零转 False。
    mi = MotionInput(cfg, moves)
    for _ in range(40):
        mi.feed(t((Dir.D,)), 1)
    assert mi.charge_ready("8")
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ("rising_tackle_A",)
    assert not mi.charge_ready("8")
    # 按钮 C 版本按按下的按钮区分
    mi = MotionInput(cfg, moves)
    for _ in range(40):
        mi.feed(t((Dir.D,)), 1)
    assert mi.feed(t((Dir.U,), (Btn.C,)), 1).specials == ("rising_tackle_C",)


def test_charge_39_not_enough(cfg, moves):
    # 阈值 40:按住 39 帧时 ↑+A 不触发,charge_ready 也为 False(差一帧)。
    mi = MotionInput(cfg, moves)
    for _ in range(39):
        mi.feed(t((Dir.D,)), 1)
    assert not mi.charge_ready("8")
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ()


def test_charge_interrupt_resets(cfg, moves):
    # 中途穿插一帧 ↑ → 蓄力清零重计:穿插后再按 39 帧仍不够;
    # 重新按满 40 帧才出(证明计数从穿插点重新起算)。
    mi = MotionInput(cfg, moves)
    for _ in range(20):
        mi.feed(t((Dir.D,)), 1)
    mi.feed(t((Dir.U,)), 1)  # 打断
    for _ in range(39):
        mi.feed(t((Dir.D,)), 1)
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ()
    mi = MotionInput(cfg, moves)
    for _ in range(20):
        mi.feed(t((Dir.D,)), 1)
    mi.feed(t((Dir.U,)), 1)
    for _ in range(40):
        mi.feed(t((Dir.D,)), 1)
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ("rising_tackle_A",)


def test_charge_release_button_window(cfg, moves):
    # 满蓄后出现 ↑(帧40)起,按钮须在 4 帧内按下(设计文档 §4.5):
    # 帧44(第 4 帧)按 A → 触发;帧45(第 5 帧)→ 超窗不触发。
    mi = MotionInput(cfg, moves)
    for _ in range(40):
        mi.feed(t((Dir.D,)), 1)
    mi.feed(t((Dir.U,)), 1)  # 帧40:释放方向出现
    for _ in range(3):
        mi.feed(t((Dir.U,)), 1)  # 帧41..43 继续按住 ↑
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ("rising_tackle_A",)
    mi = MotionInput(cfg, moves)
    for _ in range(40):
        mi.feed(t((Dir.D,)), 1)
    mi.feed(t((Dir.U,)), 1)
    for _ in range(4):
        mi.feed(t((Dir.U,)), 1)  # 帧41..44
    assert mi.feed(t((Dir.U,), (Btn.A,)), 1).specials == ()


# ---------- DP(→↓↘)----------


def test_dp_power_dunk(cfg, moves):
    # DP 指令 R;D;D+R;B 在 18 帧窗内 → power_dunk_B;
    # 同指令换 D 按钮 → power_dunk_D(按钮区分版本)。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.R,)), t((Dir.D,)), t((Dir.D, Dir.R)), t((), (Btn.B,))])
    assert trigs[3].specials == ("power_dunk_B",)
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.R,)), t((Dir.D,)), t((Dir.D, Dir.R)), t((), (Btn.D,))])
    assert trigs[3].specials == ("power_dunk_D",)


def test_dp_window_exceeded(cfg, moves):
    # DP 窗 18 帧:6@0 … 3@20 首尾间隔 20 > 18 → 不触发。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.R,))] + [t() for _ in range(18)] \
        + [t((Dir.D,)), t((Dir.D, Dir.R)), t((), (Btn.B,))]
    trigs = run(mi, ticks)  # 帧0→ 帧1..18空 帧19↓ 帧20↓→ 帧21 B
    assert all(not x.specials for x in trigs)


def test_dp_lenient_missing_diagonal(cfg, moves):
    # DP 也享受对角宽容:6→2 后缺 3(直接按 B)仍算完成。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.R,)), t((Dir.D,)), t((), (Btn.B,))])
    assert trigs[2].specials == ("power_dunk_B",)


# ---------- 超杀(长指令优先)----------


def test_super_priority_over_single_qcf(cfg, moves):
    # 双 QCF+A:同一结尾同时匹配双段超杀与单段 QCF,长指令优先——
    # 只输出 power_geyser_A;缓冲窗内紧接着再按 C 也不漏出 power_wave(窗已消耗)。
    mi = MotionInput(cfg, moves)
    qcf = (t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)))
    ticks = qcf + qcf + (t((), (Btn.A,)), t(), t(), t((), (Btn.C,)))
    trigs = run(mi, ticks)  # 帧0..5 双QCF,帧6 A,帧9 C
    assert trigs[6].specials == ("power_geyser_A",)
    assert [x.specials[0] for x in trigs if x.specials] == ["power_geyser_A"]
    mi = MotionInput(cfg, moves)
    trigs = run(mi, qcf + qcf + (t((), (Btn.C,)),))
    assert trigs[6].specials == ("power_geyser_C",)


def test_super_window_expired_falls_back(cfg, moves):
    # 双 QCF 首尾拉到 43 帧(>40)→ 超杀不成立;第二段单 QCF 自身
    # 在 24 帧窗内,退回识别 power_wave_A(长指令不成立时让位单段)。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,))] \
        + [t() for _ in range(38)] \
        + [t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)), t((), (Btn.A,))]
    trigs = run(mi, ticks)  # 第一段帧0..2,第二段帧41..43,帧44 A
    assert trigs[44].specials == ("power_wave_A",)


# ---------- 镜像(facing=-1 同一招)----------


def test_mirror_qcf_same_move(cfg, moves):
    # P2 面朝左:物理 ↓、↓←、←(搓的方向与面朝右时相反)相对化后
    # 正是 ↓↘→,按 C 识别出同一招 power_wave_C。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,)), t((Dir.D, Dir.L)), t((Dir.L,)), t(), t((), (Btn.C,))]
    assert run(mi, ticks, facing=-1)[4].specials == ("power_wave_C",)


def test_mirror_qcb_and_dp(cfg, moves):
    # 镜像 QCB:面朝左时物理 ↓、↓→、→ 相对化 = 2,1,4 → burn_knuckle_A;
    # 镜像 DP:物理 ←、↓、↓← 相对化 = 6,2,3 → power_dunk_B。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)), t((), (Btn.A,))]
    assert run(mi, ticks, facing=-1)[3].specials == ("burn_knuckle_A",)
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.L,)), t((Dir.D,)), t((Dir.D, Dir.L)), t((), (Btn.B,))]
    assert run(mi, ticks, facing=-1)[3].specials == ("power_dunk_B",)


def test_mirror_dash(cfg, moves):
    # 镜像双击:面朝左时物理"左"是前 → 双击左 = dash_fwd;双击右 = dash_back。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.L,)), t(), t((Dir.L,))], facing=-1)
    assert trigs[2].dash_fwd and not trigs[2].dash_back
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.R,)), t(), t((Dir.R,))], facing=-1)
    assert trigs[2].dash_back and not trigs[2].dash_fwd


# ---------- 双击前冲 / 后撤 ----------


def test_dash_window(cfg, moves):
    # 双击窗口:松开(帧1)后 8 帧内再按下 → dash_fwd 恰一帧;
    # 第 9 帧(帧10)再按下 → 超窗不触发。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.R,)), t()] + [t() for _ in range(7)] + [t((Dir.R,)), t()]
    trigs = run(mi, ticks)  # 帧0按 帧1松 帧2..8空 帧9再按 帧10
    assert trigs[9].dash_fwd
    assert not trigs[10].dash_fwd  # 触发恰一帧,下一帧即熄灭
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.R,)), t()] + [t() for _ in range(8)] + [t((Dir.R,))]
    trigs = run(mi, ticks)  # 帧10 再按:10-1=9 > 8
    assert not trigs[10].dash_fwd


def test_dash_back_direction(cfg, moves):
    # 双击后方向(物理左)→ dash_back;同帧前后方向各自独立互不干扰。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.L,)), t(), t((Dir.L,))])
    assert trigs[2].dash_back and not trigs[2].dash_fwd


def test_dash_resets_after_trigger(cfg, moves):
    # 触发后该方向检测重置:同一连击串里的第三下不再触发(触发的那次
    # 按下不作为新序列第一下);重新 按下→松开→按下 才再次触发。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.R,)), t(), t((Dir.R,)), t(), t((Dir.R,)), t(), t((Dir.R,))])
    assert trigs[2].dash_fwd   # 帧0按 帧1松 帧2按:触发
    assert not trigs[4].dash_fwd  # 重置后帧2的按下未开启新序列,帧4不算双击
    assert trigs[6].dash_fwd   # 帧4按 帧5松 帧6按:新序列成立


# ---------- 边缘 ----------


def test_button_same_frame_as_final_direction(cfg, moves):
    # 按钮与指令最后一个方向同一帧按下(→+C 同帧)也能识别:间隔 0。
    mi = MotionInput(cfg, moves)
    trigs = run(mi, [t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,), (Btn.C,))])
    assert trigs[2].specials == ("power_wave_C",)


def test_repeat_press_no_refire(cfg, moves):
    # 触发后缓冲窗内重复按 C → 不重复触发(窗已消耗);
    # 重新完整搓一遍 ↓↘→ 再按 C → 才再次触发(需重新搓)。
    mi = MotionInput(cfg, moves)
    ticks = [
        t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)), t((), (Btn.C,)),
        t(), t((), (Btn.C,)),
        t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)), t((), (Btn.C,)),
    ]
    trigs = run(mi, ticks)
    assert trigs[3].specials == ("power_wave_C",)
    assert trigs[5].specials == ()
    assert trigs[9].specials == ("power_wave_C",)


def test_two_buttons_one_output(cfg, moves):
    # 同帧按 A+C(搓完 QCF):specials 契约保证每帧至多 1 条——
    # 轻重两版本不会同时出,落选版本下一帧也不补发。
    mi = MotionInput(cfg, moves)
    ticks = [t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)), t((), (Btn.A, Btn.C)), t()]
    trigs = run(mi, ticks)
    assert len(trigs[3].specials) == 1
    assert trigs[4].specials == ()


def test_only_moves_in_table(cfg, moves):
    # 识别只对 moves 里存在的招负责(从数据读,不硬编码招名):
    # 只装 power_wave_A/burn_knuckle_A 两招,双 QCF+A 触发的是 power_wave_A
    # (表里没有超杀可让位);↓↙←+A 触发 burn_knuckle_A。
    subset = {k: moves[k] for k in ("power_wave_A", "burn_knuckle_A")}
    mi = MotionInput(cfg, subset)
    qcf = (t((Dir.D,)), t((Dir.D, Dir.R)), t((Dir.R,)))
    trigs = run(mi, qcf + qcf + (t((), (Btn.A,)),))
    assert trigs[6].specials == ("power_wave_A",)
    mi = MotionInput(cfg, subset)
    trigs = run(mi, [t((Dir.D,)), t((Dir.D, Dir.L)), t((Dir.L,)), t((), (Btn.A,))])
    assert trigs[3].specials == ("burn_knuckle_A",)
