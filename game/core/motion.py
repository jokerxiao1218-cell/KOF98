"""core/motion.py — 输入缓冲 + 指令识别 + 蓄力 + 双击前冲(设计文档 §4.5 / §5.3 A2)。

职责:
  * 每帧被喂一个 Tick(绝对方向) + facing,把方向相对化后进识别器;
    镜像问题在本层一次解决(facing=-1 时同一物理输入识别出同一招)。
  * 输出 FrameTriggers:specials 至多 1 条(长指令优先:超杀 > 必杀)、
    dash_fwd / dash_back。本模块不知道"气够不够"——超杀照常输出,发不发由
    fighter 层决定。

纪律:零 pygame 依赖(core 层);只用标准库;招式全部从 moves 的 input
定义读,不硬编码招名;窗口数值全部从 input_cfg 读,不写死。
"""
from __future__ import annotations

from . import types as T

# ---------- 相对方向 ↔ 数字键盘记法 ----------

# 对角数字:识别宽容里,pattern 中的对角帧(3/1/9/7)可以缺失
# (2→6 直接跳过 3 仍算 QCF;斜角在键盘上本就是两轴同按,常被漏采)。
_DIAGONALS = frozenset("1379")

# 数字 → 轴集合("2"→竖直下,"3"→下+前 …)。蓄力/双击按轴判定,
# 而不是按整数字比对:按住 ↓→(3) 仍算"按着 ↓"。
_DIGIT_AXES = {
    "1": frozenset("DL"), "2": frozenset("D"), "3": frozenset("DR"),
    "4": frozenset("L"), "5": frozenset(), "6": frozenset("R"),
    "7": frozenset("UL"), "8": frozenset("U"), "9": frozenset("UR"),
}


def _abs_to_rel(dirs, facing: int) -> frozenset:
    """绝对方向集合 → 相对轴集合({"U","D","L","R"},L/R 已按 facing 反转)。

    U/D 不受 facing 影响;facing=+1 时物理 R=前(→轴 "R"),L=后;
    facing=-1 反转。斜角=组合持有(按住 D+R → {"D","R"} 即 "3")。
    """
    rel = set()
    for d in dirs:
        name = d.value if isinstance(d, T.Dir) else str(d)
        if name == "U":
            rel.add("U")
        elif name == "D":
            rel.add("D")
        elif name == "L":
            rel.add("R" if facing < 0 else "L")
        elif name == "R":
            rel.add("L" if facing < 0 else "R")
    return frozenset(rel)


def _digit(axes) -> str:
    """相对轴集合 → 数字键盘字符。

    病态组合的确定性处理(键盘允许同时按下):
      * 上下同按({U,D}…)按"出现上"处理("8" 系)——蓄力释放判定宁敏感勿迟钝;
      * 左右同按互相抵消(只看竖直轴)。
    """
    vert = "U" if "U" in axes else ("D" if "D" in axes else "")
    horiz = ""
    if "L" in axes and "R" not in axes:
        horiz = "L"
    elif "R" in axes and "L" not in axes:
        horiz = "R"
    return {
        ("U", "L"): "7", ("U", "R"): "9", ("U", ""): "8",
        ("D", "L"): "1", ("D", "R"): "3", ("D", ""): "2",
        ("", "L"): "4", ("", "R"): "6", ("", ""): "5",
    }[(vert, horiz)]


def relativize(dirs, facing: int) -> str:
    """绝对方向集合 → 相对角色的数字键盘字符(2=↓ 3=↘ 6=前 4=后 …,5=中性)。"""
    return _digit(_abs_to_rel(dirs, facing))


class MotionInput:
    """每帧喂一个 Tick,内部维护缓冲,输出 FrameTriggers。

    缓冲(设计文档 §4.5):
      * 方向历史:相对方向"状态变化"序列(只在变化时追加,带帧号),
        保留最近 max(各识别窗) 帧——最大窗是双 QCF 的 40 帧,只留
        dir_window(24)将识别不出拉长的双段超杀。
      * 按钮按下事件(带帧号)保留 button_buffer 帧。
    """

    def __init__(self, input_cfg, moves: dict):
        # 窗口参数全从 cfg 读(data 层已校验 >=1),不写死
        self._dir_window = input_cfg.dir_window
        self._button_buffer = input_cfg.button_buffer
        self._dp_window = input_cfg.dp_window
        self._dq_window = input_cfg.double_qcf_window
        self._charge_frames = input_cfg.charge_frames
        self._dash_tap_window = input_cfg.dash_tap_window

        # 识别只对存在的招负责:从数据读,不硬编码招名。
        # motion 招:同 pattern 多按钮版本(如 power_wave_A/C)按按下的
        # 按钮区分;charge 招按 (charge_dir, release_dir) 对累计蓄力。
        self._motion_moves = []  # [(move_id, pattern, button, kind)]
        self._charge_moves = []  # [(move_id, charge_dir, release_dir, button, kind)]
        for mid, m in moves.items():
            spec = m.input
            if spec["type"] == "motion":
                self._motion_moves.append(
                    (mid, tuple(spec["pattern"]), spec["button"], m.kind)
                )
            elif spec["type"] == "charge":
                self._charge_moves.append(
                    (mid, spec["charge_dir"], spec["release_dir"], spec["button"], m.kind)
                )

        self._frame = -1  # feed 一次自增,首帧为 0(全项目约定 0 起算)
        # 方向历史:[(帧号, 相对数字)] 仅在变化时追加;起始态记一次 "5"
        self._dir_hist = [(-1, "5")]
        self._prev_rel = "5"
        # 按钮按下事件缓冲:[(帧号, 按钮名)]
        self._press_buf = []

        # 蓄力状态:charge_dir 数字 → 已连续持有的帧数(期间出现过
        # release_dir 就清零重计)。按 (charge_dir, release_dir) 索引。
        self._charge_hold = {}  # (cd, rd) -> 已持帧数
        self._charge_armed = {}  # (cd, rd) -> 满蓄力后未过期的帧号(释放+按钮窗)
        for _mid, cd, rd, _btn, _kind in self._charge_moves:
            self._charge_hold[(cd, rd)] = 0
            self._charge_armed[(cd, rd)] = None

        # 双击检测:相对前轴("R")/后轴("L")各自记
        #   _dash_armed:已出现"第一下按下"、待松开
        #   _tap:松开发生在哪一帧(待窗内再按下);None=无进行中的序列
        self._dash_armed = {"R": False, "L": False}
        self._tap = {"R": None, "L": None}
        self._held_axes = frozenset()  # 上一帧的相对轴集合(算边沿用)

        # 已触发记录 {(move_id, 完成帧)}:同一完成点不因缓冲窗内重复
        # 按按钮而重复触发(窗已消耗,想再出必须重新搓)
        self._fired = set()

    # ---------------- 每帧入口 ----------------

    def feed(self, tick: T.Tick, facing: int) -> T.FrameTriggers:
        """每帧调用一次:内部帧计数自增,返回本帧触发。

        tick.dirs 是绝对方向持有集;tick.pressed 是本帧按下的按钮边沿
        (tick.released 本模块用不到——按钮缓冲只认按下)。
        """
        now = self._frame + 1
        self._frame = now

        axes = _abs_to_rel(tick.dirs, facing)
        cur = _digit(axes)

        # 方向历史:只在相对数字"变化"时追加(带帧号)
        if cur != self._prev_rel:
            self._dir_hist.append((now, cur))
            self._prev_rel = cur
        # 裁剪:保留最大窗(双 QCF 窗 40 > dir_window 24;只留 24 帧将
        # 识别不出拉长到 40 帧的双段超杀)
        keep = max(self._dir_window, self._dp_window, self._dq_window)
        cut = now - keep
        if len(self._dir_hist) > 1 and self._dir_hist[0][0] < cut:
            self._dir_hist = [e for e in self._dir_hist if e[0] >= cut]

        # 按钮按下事件缓冲
        for b in tick.pressed:
            self._press_buf.append((now, b.value if isinstance(b, T.Btn) else str(b)))
        cut = now - self._button_buffer
        if self._press_buf and self._press_buf[0][0] < cut:
            self._press_buf = [e for e in self._press_buf if e[0] >= cut]

        # 蓄力状态机先更新(同帧 释放方向+按钮 也能触发)
        self._update_charge(axes, now)

        # 双击前冲/后撤(相对前/后轴的 按下→松开→窗内再按下)
        dash_fwd, dash_back = self._update_dash(axes, now)

        # 指令识别:缓冲里的按钮按下 × 方向历史上刚完成的指令
        special = self._fire_specials(now)

        return T.FrameTriggers((special,) if special else (), dash_fwd, dash_back)

    # ---------------- 双击前冲 / 后撤 ----------------

    def _update_dash(self, axes, now: int):
        """相对前轴/后轴的边沿检测:按下→松开→dash_tap_window 帧内再按下。

        触发即整体重置该方向检测(触发的那次按下不作为新序列的第一下,
        想再冲必须重新 按下→松开→按下)。
        """
        fwd = back = False
        for axis, was in (("R", "R" in self._held_axes), ("L", "L" in self._held_axes)):
            present = axis in axes
            if present and not was:  # 本帧按下该方向
                r = self._tap[axis]
                if r is not None and now - r <= self._dash_tap_window:
                    if axis == "R":
                        fwd = True
                    else:
                        back = True
                    self._tap[axis] = None  # 触发即重置
                    self._dash_armed[axis] = False
                else:
                    # 新序列的第一下(过期/无进行中的释放窗也走到这里,重新起算)
                    self._tap[axis] = None
                    self._dash_armed[axis] = True
            elif not present and was:  # 本帧松开该方向
                if self._dash_armed[axis]:
                    self._tap[axis] = now  # 进入"待窗内再按下"
                self._dash_armed[axis] = False
        self._held_axes = axes
        return fwd, back

    # ---------------- 蓄力 ----------------

    # 设计文档 §4.5:满蓄力后出现释放方向,4 帧内按按钮 → 触发。
    # 这个 4 帧是设计文档定死的行为参数,system.json 的 input 节没有对应键,
    # 故为模块常量(不是调参项;要改走文档变更流程)。
    _RELEASE_BTN_WINDOW = 4

    def _update_charge(self, axes, now: int):
        """每个 (charge_dir, release_dir) 对的蓄力计数。

        按轴判定:按住 ↓→(1/2/3,竖直下轴在场)都算"按着 2";
        一旦出现释放轴(如 8 的上轴:7/8/9)→ 计数清零;满 charge_frames
        帧后出现释放方向 → 进入"4 帧内按按钮"的武装窗。
        """
        for (cd, rd) in self._charge_hold:
            held = _DIGIT_AXES[cd] <= axes
            released = bool(axes & _DIGIT_AXES[rd])
            if released:
                if self._charge_hold[(cd, rd)] >= self._charge_frames:
                    self._charge_armed[(cd, rd)] = now
                self._charge_hold[(cd, rd)] = 0
            elif held:
                self._charge_hold[(cd, rd)] += 1
            else:
                # 中性/水平方向都算中断("持续持有"要求不间断)
                self._charge_hold[(cd, rd)] = 0

    def charge_ready(self, release_dir: str) -> bool:
        """蓄力查询:存在以 release_dir 为释放方向的蓄力招,当前已连续
        按住 charge_dir >= charge_frames 帧且期间未出现 release_dir。

        满蓄后一出现释放方向计数就清零,所以这里为 True 意味着
        "现在松开再按按钮就能出招"。
        """
        for (cd, rd), hold in self._charge_hold.items():
            if rd == release_dir and hold >= self._charge_frames:
                return True
        return False

    # ---------------- 指令识别(motion 招) ----------------

    def _fire_specials(self, now: int):
        """本帧要出的招(move_id)或 None。

        按钮缓冲里每个按下事件 × 方向历史上刚完成的指令配对。缓冲语义
        照设计文档 §4.5"搓完指令稍后按拳有效":指令完成帧 c 在按钮帧 f
        之前(或同帧),且间隔 <= button_buffer;先按后搓不算——按钮必须
        落在完成点之后。长指令优先:超杀压过用同一结尾的单段必杀;触发即
        消耗方向历史到完成点为止(窗已消耗,漏不出第二次触发)。
        """
        if not self._press_buf:
            return None  # 一切触发都始于一次按钮按下
        cands = []  # (排序键, move_id, 完成帧, 消耗动作)
        for mid, pat, btn, kind in self._motion_moves:
            for f, b in self._press_buf:
                if b != btn:
                    continue
                c = self._latest_completion(pat)
                if c is None or f < c or f - c > self._button_buffer:
                    continue
                if (mid, c) in self._fired:
                    continue
                # 同一招同一完成点只算一个候选(缓冲里重复按下不放大候选)
                cands.append(((kind != "SUPER", -len(pat), -c, mid), mid, c, None))
                break
        for mid, cd, rd, btn, kind in self._charge_moves:
            r = self._charge_armed.get((cd, rd))
            if r is None:
                continue
            for f, b in self._press_buf:
                if b == btn and r <= f <= r + self._RELEASE_BTN_WINDOW:
                    cands.append(((kind != "SUPER", 0, -r, mid), mid, r, (cd, rd)))
                    break
        if not cands:
            return None
        cands.sort(key=lambda t: t[0])
        _, mid, c, charge_key = cands[0]
        if charge_key is not None:
            self._charge_armed[charge_key] = None  # 蓄力释放窗已消耗
        else:
            self._consume_history(c)  # 方向历史吃到完成点为止
        self._fired.add((mid, c))
        return mid

    def _consume_history(self, upto: int):
        """触发后把 <= upto 的方向历史吃掉:同一次搓招不再喂出第二个触发
        (超杀触发后,垫在底下的单 QCF 也一并消耗)。

        吃得精光时,把"仍在按住的方向"重锚到当前帧——它本来早就在按,
        但原始条目已被吃;重锚后以它开头的指令(如 DP 的 →)仍可匹配,
        且要滚完后续方向才算数,只会更宽容不会凭空触发。
        """
        kept = [e for e in self._dir_hist if e[0] > upto]
        self._dir_hist = kept if kept else [(self._frame, self._prev_rel)]

    def _window_for(self, pattern) -> int:
        """pattern 用的识别窗:双段超杀窗 / DP 窗 / 普通单段窗。"""
        if len(pattern) >= 5:
            return self._dq_window
        if len(pattern) == 3 and pattern[0] in ("4", "6") \
                and pattern[1] == "2" and pattern[2] in _DIAGONALS:
            return self._dp_window
        return self._dir_window

    def _latest_completion(self, pattern):
        """pattern 在方向历史上的最晚完成帧(窗口内、对角帧可缺),无则 None。

        完成点 = 最后被匹配元素的帧。候选完成点从晚到早试:条目 j 匹配
        pattern[-1];若 pattern[-1] 是对角(可缺),j 也可以只匹配
        pattern[-2](尾部对角缺失,完成点提前)。
        """
        hist = self._dir_hist
        n = len(pattern)
        window = self._window_for(pattern)
        for j in range(len(hist) - 1, -1, -1):
            d = hist[j][1]
            ends = []
            if d == pattern[-1]:
                ends.append(n - 1)
            if pattern[-1] in _DIAGONALS and n >= 2 and d == pattern[-2]:
                ends.append(n - 2)
            for k in ends:
                first = self._match_back(pattern, k, j)
                if first is not None and hist[j][0] - first <= window:
                    return hist[j][0]
        return None

    def _match_back(self, pattern, k: int, j: int):
        """hist[j] 固定匹配 pattern[k],倒序给 pattern[0..k-1] 找尽量晚的
        匹配(窗最紧)。返回首元素帧号,配不齐返回 None。

        pattern 中间的对角帧一律跳过不找——跳过永远不比匹配差
        (2→6 直接衔接正是宽容规则),找不到对角绝不是失败。
        """
        hist = self._dir_hist
        hi = j
        first = hist[j][0]
        for m in range(k - 1, -1, -1):
            p = pattern[m]
            if p in _DIAGONALS:
                continue  # 中间对角可缺:直接跨过
            hi -= 1
            while hi >= 0 and hist[hi][1] != p:
                hi -= 1
            if hi < 0:
                return None
            first = hist[hi][0]
        return first
