"""core/ai.py — 入门 AI(虚拟手柄,设计文档 §4.6 / §5.3 A4 契约)。

核心思想:AI = 虚拟手柄。它产出与人类键盘完全相同的 Tick 流,走同一条输入
管线;绝不直接改角色状态、绝不调用 fighter 内部。入门档目标是"能玩":
会追击、会防御、会跳入、偶尔必杀,不是高手。

决策模型(每帧调用 next_tick(view)):
  * 节流:内部帧号 % reaction_interval == 0 的帧才做一次新决策,其余帧
    只执行当前"动作计划"(一个逐帧 (方向持有集, 按钮持有集) 序列)或空输入;
    计划被新决策打断时,按住中的按钮由统一的持有状态差分自动抬起(边沿
    语义永不出错)。
  * 蓄力技(升龙撞)不使用:入门 AI 不实现蓄力逻辑(反应窗口内也搓不出)。
  * 承诺(commit):含按钮的计划(搓招/普通技/投技)执行期间不换计划——
    否则 6 帧一次的决策点会把超杀搓到一半的按钮帧掐掉,招永远出不来。
  * 确定性:唯一随机源是 random.Random(cfg.seed),计划生成全是纯函数;
    同 seed 同 view 序列 → 输出逐帧完全一致(测试/demo 依赖)。
  * 方向换算:决策时把当帧 view.facing 换算成绝对 Dir(fwd/back),
    计划期内沿用;搓招序列的方向一律从 moves 里读该招 input.pattern
    生成,不硬编码招表指令。

决策优先级(反应 > 常规;RNG 抽取顺序固定,保证可复现):
  1. 对手近距离出招(dist<100)→ block_prob 概率按住后 18 帧转防御;
  2. 对手跳入(dist<=antiair_dist)→ antiair_prob 概率 Power Dunk 迎击
     (勘误:不用蓄力升龙撞,反应窗口内出不来);
  3. 场上有对手飞行道具 → projectile_jump_prob 概率小跳过波,
     其余概率按住后防御(内部分流:60% 跳 / 40% 防);
  4. 气满且近距 → super_prob 概率能量喷泉(双QCF+A);
  5. 常规:按距离档(far/mid/close)从 weights 抽动作;己方血量低于
     conservative.own_health_below 或自己贴角时,把 block 权重 +
     conservative.block_bonus 后重归一再抽(保守修正)。

零 pygame;只依赖标准库 random 与 types/data 契约。
"""
from __future__ import annotations

import random

from . import types as T
from .data import AiCfg, SystemCfg

# ---- 任务卡给定的计划常量(ai.json 没有对应旋钮,写死并留档) ----
_BLOCK_REACT_DIST = 100   # 反应1的"近距离出招"判定距离(任务卡定值)
_BLOCK_HOLD_FRAMES = 18   # 防御/转防御计划的按住后方向帧数
_APPROACH_FRAMES = 30     # approach:按住前 30 帧
_WALK_FRAMES = 12         # walk:按住前 12 帧
_RUN_HOLD_FRAMES = 20     # run:双击前后按住的帧数
_JUMP_IN_FRAMES = 24      # jump_in:前+上按住(大跳)
_WAIT_FRAMES = 6          # wait:空 6 帧
_JUMP_TAP_FRAMES = 2      # jump:上短按 2 帧(prejump 4 帧内松上→小跳)

# 权重表/反应里的"动作键" → 搓哪一招(按钮与指令全部从 moves 读,不硬编码):
#   版本选择按任务卡:power_wave=A 快版、crack_shoot=D 重版、burn_knuckle=A、
#   super=A、对空 power_dunk=B(快版)。
_MOVE_OF_ACTION = {
    "power_wave": "power_wave_A",
    "crack_shoot": "crack_shoot_D",
    "burn_knuckle": "burn_knuckle_A",
    "super": "power_geyser_A",
    "antiair": "power_dunk_B",
}

# 数字键盘方位 → 相对语义("fwd"/"back" 由 facing 换算成绝对 Dir)
_NUMPAD_DIRS = {
    "1": ("D", "back"),
    "2": ("D",),
    "3": ("D", "fwd"),
    "4": ("back",),
    "6": ("fwd",),
    "8": ("U",),
}

_EMPTY_DIRS: frozenset = frozenset()
_EMPTY_BTNS: frozenset = frozenset()
_EMPTY_SPEC = (_EMPTY_DIRS, _EMPTY_BTNS)


def _fwd_back(facing: int) -> tuple[T.Dir, T.Dir]:
    """facing(+1 面右 / -1 面左)→ (前方向, 后方向) 的绝对 Dir。"""
    if facing >= 0:
        return T.Dir.R, T.Dir.L
    return T.Dir.L, T.Dir.R


def _numpad_dirs(token: str, fwd: T.Dir, back: T.Dir) -> frozenset:
    """一个数字键盘方位 → 绝对方向持有集(如 "3"↘ = {下, 前})。"""
    out = set()
    for ch in _NUMPAD_DIRS[token]:
        if ch == "D":
            out.add(T.Dir.D)
        elif ch == "U":
            out.add(T.Dir.U)
        elif ch == "fwd":
            out.add(fwd)
        else:
            out.add(back)
    return frozenset(out)


def _hold(dirs: frozenset, frames: int = 1) -> list:
    """生成"按住 dirs 共 frames 帧"的逐帧计划段(不碰按钮)。"""
    return [(dirs, _EMPTY_BTNS)] * frames


class TerryAI:
    """入门档 AI:每帧喂 AiView,吐一个与人类键盘同构的 Tick。"""

    def __init__(self, cfg: AiCfg, moves: dict, system: SystemCfg):
        self._cfg = cfg
        self._moves = moves
        self._system = system
        self._validate()
        self._rng = random.Random(cfg.seed)
        self._frame = 0            # 内部帧计数(next_tick 每调用一次 +1)
        self._plan: list = []      # 逐帧 (dirs 持有集, 按钮持有集) 计划
        self._committed = False    # 含按钮的计划不许被新决策打断
        self._pos = 0              # 计划执行到第几帧
        self._held: frozenset = _EMPTY_BTNS  # 上一帧实际按住中的按钮(边沿差分用)

    # ---------- 主入口 ----------

    def next_tick(self, view: T.AiView) -> T.Tick:
        """每帧调用一次:决策帧做新决策,其余帧继续执行当前计划。"""
        if self._frame % self._cfg.reaction_interval == 0:
            # 承诺期(搓招/出招中)跳过决策点,把按钮帧搓完
            if not (self._committed and self._pos < len(self._plan)):
                self._decide(view)
        spec = self._plan[self._pos] if self._pos < len(self._plan) else _EMPTY_SPEC
        self._pos += 1
        tick = self._emit(spec[0], spec[1])
        self._frame += 1
        return tick

    def _emit(self, dirs: frozenset, btns: frozenset) -> T.Tick:
        """把"本帧应按住的集合"转成 Tick:按钮边沿由前后帧差分得出,
        按下的按钮一定在后续帧被抬起(所有计划持钮都 ≤2 帧)。"""
        pressed = frozenset(btns - self._held)
        released = frozenset(self._held - btns)
        self._held = btns
        return T.Tick(frozenset(dirs), pressed, released)

    # ---------- 决策(只在决策帧读 view) ----------

    def _decide(self, view: T.AiView) -> None:
        band = self._band(view.dist)
        r = self._cfg.reactions
        # 反应1:对手近距离出招(startup 期)→ block_prob 概率转防御
        if view.opp_attacking and view.dist < _BLOCK_REACT_DIST:
            if self._rng.random() < r["block_prob"]:
                self._start("block", view.facing)
                return
        # 反应2:对手跳入且够近 → antiair_prob 概率 Power Dunk 迎击
        # (勘误已定:不用蓄力升龙撞,→↓↘ 反应窗口内出得来)
        if view.opp_airborne and view.dist <= r["antiair_dist"]:
            if self._rng.random() < r["antiair_prob"]:
                self._start("antiair", view.facing)
                return
        # 反应3:场上有对手的飞行道具 → projectile_jump_prob 概率小跳过波,
        # 其余概率按住后防御(内部分流:小跳躲波、防御挡波,二选一必执行)
        if view.opp_projectile:
            if self._rng.random() < r["projectile_jump_prob"]:
                self._start("jump", view.facing)
            else:
                self._start("block", view.facing)
            return
        # 反应4:气满且近距 → super_prob 概率超杀(双QCF+A)
        if view.own_gauge >= self._system.gauge.max and band == "close":
            if self._rng.random() < r["super_prob"]:
                self._start("super", view.facing)
                return
        # 常规决策:距离档权重 + 保守修正后抽取
        weights = self._adjusted_weights(band, view)
        total = sum(weights.values())
        x = self._rng.random() * total
        acc = 0.0
        chosen = list(weights)[-1]  # 浮点兜底:累积误差时取最后一项
        for act, w in weights.items():
            acc += w
            if x < acc:
                chosen = act
                break
        self._start(chosen, view.facing)

    def _band(self, dist: int) -> str:
        """距离三档:far(>bands.far) / close(<bands.close) / 其余 mid。"""
        b = self._cfg.bands
        if dist > b["far"]:
            return "far"
        if dist < b["close"]:
            return "close"
        return "mid"

    def _adjusted_weights(self, band: str, view: T.AiView) -> dict:
        """保守修正:血量低于阈值或自己贴角 → block 权重 +block_bonus,
        其余不动,按新总和抽取(等效重归一)。档位没有 block 键就从 0 加起。"""
        weights = dict(self._cfg.weights[band])
        c = self._cfg.conservative
        if view.own_health < c["own_health_below"] or view.self_cornered:
            weights["block"] = weights.get("block", 0.0) + c["block_bonus"]
        return weights

    def _start(self, action: str, facing: int) -> None:
        """把动作键换成逐帧计划并开始执行。搓招/出招/投技计划带承诺标志。"""
        specs, committed = self._build(action, facing)
        self._plan = specs
        self._committed = committed
        self._pos = 0

    # ---------- 动作 → 逐帧计划 ----------

    def _build(self, action: str, facing: int) -> tuple:
        """返回 (逐帧 [(dirs, btns) 持有集] 列表, 是否承诺期)。

        移动/待机/防御类(无按钮)可被下一个决策帧打断;出招类(含按钮)
        承诺执行到底,防半途掐掉按钮帧。"""
        fwd, back = _fwd_back(facing)

        if action == "approach":       # 追击:按住前 30 帧
            return _hold(frozenset({fwd}), _APPROACH_FRAMES), False
        if action == "walk":           # 走近:按住前 12 帧
            return _hold(frozenset({fwd}), _WALK_FRAMES), False
        if action == "run":            # 前冲:双击前(按1帧、松1帧、再按下按住)
            return (_hold(frozenset({fwd})) + _hold(_EMPTY_DIRS)
                    + _hold(frozenset({fwd}), _RUN_HOLD_FRAMES)), False
        if action == "jump_in":        # 跳入:前+上按住(大跳)24 帧
            return _hold(frozenset({fwd, T.Dir.U}), _JUMP_IN_FRAMES), False
        if action == "jump":           # 小跳:上短按 2 帧(prejump 内松上)
            return _hold(frozenset({T.Dir.U}), _JUMP_TAP_FRAMES), False
        if action == "wait":           # 待机:空 6 帧
            return _hold(_EMPTY_DIRS, _WAIT_FRAMES), False
        if action == "backdash":       # 后撤:后双击(与前冲同构)
            return (_hold(frozenset({back})) + _hold(_EMPTY_DIRS)
                    + _hold(frozenset({back}), _RUN_HOLD_FRAMES)), False
        if action == "block":          # 防御:按住后 18 帧
            return _hold(frozenset({back}), _BLOCK_HOLD_FRAMES), False
        if action == "st_B":           # 站姿轻脚:按 1 帧 + 抬 1 帧(按钮从招表读)
            btn = frozenset({self._move_button("st_B")})
            return [(_EMPTY_DIRS, btn), (_EMPTY_DIRS, _EMPTY_BTNS)], True
        if action == "cr_B":           # 蹲轻脚:按住下 4 帧、第 3 帧按 B
            btn = frozenset({self._move_button("cr_B")})
            down = frozenset({T.Dir.D})
            return ([(down, _EMPTY_BTNS)] * 2 + [(down, btn)]
                    + [(down, _EMPTY_BTNS)]), True
        if action == "throw":          # 投技:按住前、第 2 帧按 C、再松开
            btn = frozenset({self._move_button("throw_fwd")})
            fwdset = frozenset({fwd})
            return [(fwdset, _EMPTY_BTNS), (fwdset, btn), (fwdset, _EMPTY_BTNS)], True
        # 搓招类(power_wave / crack_shoot / burn_knuckle / super / antiair)
        if action in _MOVE_OF_ACTION:
            return self._motion_specs(_MOVE_OF_ACTION[action], fwd, back), True
        raise ValueError(f"ai:未知动作键 {action!r}(权重表/反应表与 ai.py 不同步)")

    def _motion_specs(self, move_id: str, fwd: T.Dir, back: T.Dir) -> list:
        """按招表 input.pattern 逐帧合成搓招序列:每个方位各 1 帧,
        随后按钮帧(dirs 保持 pattern 末方位)+ 一帧松开。
        例:pattern ["2","3","6"] → [↓][↘][→][→+A][→]。
        指令窗(24/18/40 帧)足够容纳,识别器认得出来。"""
        mv = self._moves[move_id]
        pat = mv.input["pattern"]
        btn = T.Btn(mv.input["button"])
        specs = [(_numpad_dirs(p, fwd, back), _EMPTY_BTNS) for p in pat]
        last_dirs = specs[-1][0]
        specs.append((last_dirs, frozenset({btn})))  # 按钮帧:保持末方向
        specs.append((last_dirs, _EMPTY_BTNS))      # 松开帧
        return specs

    def _move_button(self, move_id: str) -> T.Btn:
        """从招表读某招的触发按钮(不硬编码按钮)。"""
        mv = self._moves[move_id]
        return T.Btn(mv.input["button"])

    # ---------- 启动自检(数据不同步就大声报错,不许静默) ----------

    def _validate(self) -> None:
        for act, move_id in _MOVE_OF_ACTION.items():
            mv = self._moves.get(move_id)
            if mv is None:
                raise ValueError(f"ai:动作 {act!r} 需要的招 {move_id!r} 不在招表")
            if mv.input.get("type") != "motion":
                raise ValueError(f"ai:{move_id}.input 应为 motion 型(合成搓招用)")
        for move_id in ("st_B", "cr_B"):
            if self._moves[move_id].input.get("type") != "button":
                raise ValueError(f"ai:{move_id}.input 应为 button 型")
        if self._moves["throw_fwd"].input.get("type") != "throw":
            raise ValueError("ai:throw_fwd.input 应为 throw 型")
        # 权重表里的每个动作键都必须有计划生成器,否则启动即报
        known = {"approach", "walk", "run", "jump_in", "jump", "wait",
                 "backdash", "block", "st_B", "cr_B", "throw"} | set(_MOVE_OF_ACTION)
        for band, weights in self._cfg.weights.items():
            for act in weights:
                if act not in known:
                    raise ValueError(
                        f"ai:weights.{band} 的动作 {act!r} 没有对应的计划生成器")
        for band in self._cfg.weights:
            if band not in ("far", "mid", "close"):
                raise ValueError(f"ai:weights 档位名非法 {band!r}")
