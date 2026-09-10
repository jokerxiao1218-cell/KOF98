"""tests/test_ai.py — 入门 AI(虚拟手柄)测试(设计文档 §6 test_ai 组 + 任务卡细则)。

考的是行为,不是实现细节:
  * 确定性(同 seed 同 view 序列 → 逐 Tick 完全一致;demo/回放依赖);
  * 反应节流(决策帧之间喂新信息,反应间隔−1 帧内输出不变);
  * 距离档分布(1000 种子统计接近类占比落在权重容差内);
  * 保守修正(血量低 → 防御类占比显著升高);
  * 对空反应(Power Dunk 出现率 ≈ antiair_prob);
  * 超杀反应(气满近距 → 双QCF+A 出现率 ≈ super_prob,兼验承诺机制);
  * 合法性(只产合法枚举;按下的按钮 ≤3 帧内必抬起;没按过不许抬);
  * 搓招可识别(简化识别器在输出流里找得到 2→3→6→A);
  * 无蓄力(输出里从不出现连续 ≥40 帧含"下")。
纯逻辑测试,不碰 pygame,不需要 dummy 驱动。
统计断言的容差都按二项分布标准差(σ=√(p(1-p)/n))留 ≥3σ 余量。
"""
import random
from dataclasses import replace

from game.core import data
from game.core import types as T
from game.core.ai import TerryAI

# 模块级一次装真实数据(等效 scope="module" fixture,省得每个辅助函数都传参)
MOVES = data.load_moves()
SYSTEM = data.load_system()
AI_CFG = data.load_ai()


def _view(**kw):
    """构造 AiView:默认远距/满血/无气/无任何威胁标志(纯中性远档视图)。"""
    base = dict(dist=200, own_health=1000, own_gauge=0, facing=1,
                opp_airborne=False, opp_attacking=False, opp_projectile=False,
                self_cornered=False)
    base.update(kw)
    return T.AiView(**base)


def _run(seed, views, cfg=AI_CFG):
    """起一个指定种子的 AI,把 views 逐帧喂进去,返回 Tick 流。"""
    ai = TerryAI(replace(cfg, seed=seed), MOVES, SYSTEM)
    return [ai.next_tick(v) for v in views]


def _varied_views(n=200):
    """200 帧变化的 view:远近/攻防/跳入/波/贴角/换朝向/血量气量全都轮到,
    纯 i 的函数 → 两个实例拿到的一模一样(确定性测试用)。"""
    views = []
    for i in range(n):
        views.append(_view(
            dist=[50, 120, 200, 95, 160, 89][i % 6],
            own_health=[1000, 250, 700, 299, 1000, 500][i % 6],
            own_gauge=100 if i % 4 == 2 else 30,   # 轮到气满,能触发超杀反应
            facing=1 if (i // 10) % 2 == 0 else -1,
            opp_airborne=(i % 7) in (2, 5),
            opp_attacking=(i % 5) == 3,
            opp_projectile=(i % 11) == 4,
            self_cornered=(i % 13) == 0,
        ))
    return views


def _dirs_set(facing):
    """facing 对应的(前, 后)绝对方向,测试侧独立换算(不 import 生产代码)。"""
    if facing >= 0:
        return T.Dir.R, T.Dir.L
    return T.Dir.L, T.Dir.R


# ---------- 确定性 ----------


def test_deterministic_same_seed_same_sequence():
    # seed=42 两个实例,同一 200 帧变化 view 序列,逐帧 Tick 必须完全相等
    views = _varied_views()
    run_a = _run(42, views)
    run_b = _run(42, views)
    assert len(run_a) == 200
    for i, (ta, tb) in enumerate(zip(run_a, run_b)):
        assert ta == tb, f"第 {i} 帧输出分叉:{ta} vs {tb}"
    # 防"两个实例全程都在发呆"的假通过:总得按过按钮、按过方向
    assert any(t.pressed for t in run_a)
    assert any(t.dirs for t in run_a)


def test_different_seed_usually_differs():
    # 反向兜底:不同种子在同一视图序列下不该逐帧全同(否则"确定性"只是输出恒定)
    views = _varied_views()
    assert _run(42, views) != _run(43, views)


# ---------- 反应节流 ----------


def test_reaction_throttle_within_interval():
    # 决策帧(第 6 帧)之后立刻喂 opp_attacking=True,其后 5 帧(=间隔−1)
    # 输出必须与"从未见过攻击"的对照跑完全一致——新信息进不了决策
    neutral = _view(dist=80)   # 近距,让第 12 帧的决策能吃到攻击反应
    attacking = _view(dist=80, opp_attacking=True)
    ctrl = _run(42, [neutral] * 18)
    # 第 0..6 帧同视图,第 7 帧起对手开始出招
    throttled = _run(42, [neutral] * 7 + [attacking] * 11)
    for i in range(7, 12):  # 决策帧 6 之后的 5 帧内不许换计划
        assert throttled[i] == ctrl[i], f"节流失败:第 {i} 帧被新信息改变"


def test_reaction_fires_after_next_decision():
    # 节流的另一半:过下一个决策帧(第 12 帧)后,攻击信息必须真的影响输出
    # (55% 反应概率 → 40 个种子里至少 10 个出现分歧,期望约 22 个)
    neutral = _view(dist=80)
    attacking = _view(dist=80, opp_attacking=True)
    diff = 0
    for seed in range(42, 82):
        ctrl = _run(seed, [neutral] * 18)
        thr = _run(seed, [neutral] * 7 + [attacking] * 11)
        if ctrl[12:18] != thr[12:18]:
            diff += 1
    assert diff >= 10, f"过决策帧后仍无反应({diff}/40),反应链没接上"


# ---------- 距离档分布 ----------


def test_far_band_approach_distribution():
    # 1000 个种子,far 档固定视图喂到第 6 帧取该帧决策(决策帧恰好是 6),
    # 接近类(按住前,即 dirs=={前})占比应落在 approach 权重 0.45±0.08
    views = [_view(dist=200)] * 7
    approach = 0
    n = 1000
    fwd, _ = _dirs_set(1)
    for seed in range(42, 42 + n):
        tick6 = _run(seed, views)[6]
        if tick6.dirs == frozenset({fwd}):
            approach += 1
    ratio = approach / n
    assert 0.37 <= ratio <= 0.53, f"远档接近类占比 {ratio:.3f} 超出 0.45±0.08"


# ---------- 保守修正 ----------


def test_conservative_low_health_blocks_more():
    # 同种子同视图(近距中性),血 100(<300 保守线)vs 血 1000:
    # 前者的防御类决策占比应显著更高(权重 0.20 → 0.35/1.15 ≈ 0.304)
    def block_ratio(health):
        views = [_view(dist=50, own_health=health)] * 8
        n = 500
        hits = 0
        back = T.Dir.L
        for seed in range(42, 42 + n):
            ticks = _run(seed, views)
            # 防御=按住后:第 6 帧决策后,第 6、7 帧都在按住后(后撤是 按-松-按,第 7 帧为空)
            if (ticks[6].dirs == frozenset({back})
                    and ticks[7].dirs == frozenset({back})):
                hits += 1
        return hits / n

    low_ratio = block_ratio(100)
    high_ratio = block_ratio(1000)
    # 期望 0.304 vs 0.200:差 ≥0.06 留了 3σ 余量(差的标准差约 1.4%)
    assert low_ratio >= high_ratio + 0.06, \
        f"保守修正没生效:低血 {low_ratio:.3f} vs 满血 {high_ratio:.3f}"
    assert 0.22 <= low_ratio <= 0.40, f"低血防御占比 {low_ratio:.3f} 异常"
    assert 0.12 <= high_ratio <= 0.28, f"满血防御占比 {high_ratio:.3f} 异常"


# ---------- 对空反应 ----------


def test_antiair_power_dunk_rate():
    # 对手跳入(dist=100 ≤ antiair_dist=120):500 种子统计第 0 帧决策,
    # 出 Power Dunk(→↓↘+B,特征 = [前][下][下+前] 后紧跟按下 B)的
    # 占比应 ≈ antiair_prob 0.75±0.06(σ≈1.9%)
    views = [_view(dist=100, opp_airborne=True)] * 4
    n = 500
    hits = 0
    fwd = T.Dir.R
    for seed in range(42, 42 + n):
        ticks = _run(seed, views)
        if (ticks[0].dirs == frozenset({fwd})
                and ticks[1].dirs == frozenset({T.Dir.D})
                and ticks[2].dirs == frozenset({T.Dir.D, fwd})
                and T.Btn.B in ticks[3].pressed):
            hits += 1
    ratio = hits / n
    assert 0.69 <= ratio <= 0.81, f"对空 Power Dunk 出现率 {ratio:.3f} 超出 0.75±0.06"


# ---------- 超杀反应(兼验承诺机制:超杀 8 帧 > 决策间隔 6,不许被掐) ----------


def test_super_reaction_double_qcf():
    # 气满且近距:500 种子,出现 双QCF+A(↓↘→↓↘→ 后按下 A)的占比
    # 应 ≈ super_prob 0.10±0.05(σ≈1.3%)。按钮帧落在第 6 帧决策点上,
    # 若承诺机制失效,这个签名永远拼不完整 → 该测试必红
    views = [_view(dist=50, own_gauge=100)] * 8
    n = 500
    hits = 0
    fwd = T.Dir.R
    for seed in range(42, 42 + n):
        ticks = _run(seed, views)
        sig = [frozenset({T.Dir.D}), frozenset({T.Dir.D, fwd}), frozenset({fwd})] * 2
        if ([t.dirs for t in ticks[:6]] == sig
                and ticks[6].dirs == frozenset({fwd})
                and T.Btn.A in ticks[6].pressed):
            hits += 1
    ratio = hits / n
    assert 0.05 <= ratio <= 0.15, f"超杀出现率 {ratio:.3f} 超出 0.10±0.05"


# ---------- 输出合法性(500 帧随机 view) ----------


def _random_views(n, seed=123):
    """测试侧固定种子的随机视图流:各种距离/标志/朝向/血量气量都搅进去。"""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        out.append(_view(
            dist=rng.randint(20, 300),
            own_health=rng.randint(0, 1000),
            own_gauge=rng.randint(0, 100),
            facing=rng.choice((1, -1)),
            opp_airborne=rng.random() < 0.2,
            opp_attacking=rng.random() < 0.25,
            opp_projectile=rng.random() < 0.15,
            self_cornered=rng.random() < 0.1,
        ))
    return out


def test_tick_legality_and_edge_pairing():
    # 任意 500 帧随机 view(尾接 6 帧中性把余量冲净):
    # 1) dirs/pressed/released 全是合法枚举;
    # 2) 同帧不许又按又抬同一键;
    # 3) 每个按下的按钮在 ≤3 帧内必有对应抬起;
    # 4) 没按过的按钮不许凭空抬起;
    # 5) 结束时没有按钮悬在按住状态
    views = _random_views(500) + [_view()] * 6
    ticks = _run(777, views)
    legal_dirs, legal_btns = set(T.Dir), set(T.Btn)
    pending = {}  # btn -> 按下时的帧号
    for f, tick in enumerate(ticks):
        assert set(tick.dirs) <= legal_dirs, f"第 {f} 帧非法方向 {tick.dirs}"
        assert set(tick.pressed) <= legal_btns, f"第 {f} 帧非法按钮 {tick.pressed}"
        assert set(tick.released) <= legal_btns, f"第 {f} 帧非法抬起 {tick.released}"
        assert not (tick.pressed & tick.released), f"第 {f} 帧同帧又按又抬 {tick}"
        for b in tick.pressed:
            assert b not in pending, f"第 {f} 帧 {b} 没抬又按(非法边沿)"
            pending[b] = f
        for b in tick.released:
            assert b in pending, f"第 {f} 帧 {b} 没按过就抬(非法边沿)"
            assert f - pending[b] <= 3, f"{b} 按住 {f - pending[b]} 帧才抬,超 3"
            del pending[b]
    assert not pending, f"结束时仍按住未抬:{pending}"


def test_no_charge_motion_ever_output():
    # 入门 AI 不搓蓄力招:全部输出里不得出现连续 ≥40 帧含"下"的方向
    # (升龙撞要 ↓ 蓄 40 帧;我们最长持下就是 cr_B 的 4 帧)
    streak = best = 0
    for tick in _run(777, _random_views(500) + [_view()] * 6):
        streak = streak + 1 if T.Dir.D in tick.dirs else 0
        best = max(best, streak)
    assert best < 40, f"出现连续 {best} 帧含下,像在搓蓄力"


# ---------- 合成搓招可识别(简化识别器,不 import motion.py) ----------


def _find_qcf_a(ticks, facing):
    """测试内简化识别器:依次出现 2(↓)、3(↘)、6(→) 三个相对方向,
    随后 ≤3 帧内按下 A 且仍按住 6。返回命中的起始帧,找不到返回 -1。
    相对方向由测试侧独立换算,不 import 生产代码。"""
    fwd = T.Dir.R if facing > 0 else T.Dir.L
    seq = (frozenset({T.Dir.D}), frozenset({T.Dir.D, fwd}), frozenset({fwd}))
    for i in range(len(ticks) - 4):
        if (ticks[i].dirs, ticks[i + 1].dirs, ticks[i + 2].dirs) != seq:
            continue
        for j in range(i + 3, min(i + 6, len(ticks))):
            if T.Btn.A in ticks[j].pressed and fwd in ticks[j].dirs:
                return i
    return -1


def test_power_wave_motion_is_recognizable():
    # 远档 AI 迟早会抽到能量波:输出的 Tick 流必须真搓得出 ↓↘→+A
    # (识别器在第 4 帧内找到 2→3→6 + A)。远档 power_wave 权重 0.20,
    # 400 帧 ≈ 66 次决策,一次都不中的概率 ~1e-6,断言稳
    views = [_view(dist=200)] * 400
    i = _find_qcf_a(_run(42, views), facing=1)
    assert i >= 0, "seed=42 的远档输出里找不到可识别的 ↓↘→+A 序列"


def test_power_wave_mirrored_facing():
    # 面朝左时同一招应搓出镜像指令(↓↘← 相对=2 3 6,绝对={D},{D,L},{L}+A),
    # 证明 AI 的方向换算没把镜像搓反
    views = [_view(dist=200, facing=-1)] * 400
    i = _find_qcf_a(_run(42, views), facing=-1)
    assert i >= 0, "面朝左时输出里找不到可识别的 ↓↘→+A(镜像)序列"
