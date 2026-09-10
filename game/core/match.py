"""core/match.py — 对局编排(batch B,设计文档 §4.8/§5.3)。

职责:把 fighter / motion / combat / projectile 串成一场完整对局——回合状态机、
hitstop 冻结、攻击双向裁决、投技结算、弹体生成与回收、摄像机与边界、
计时 / KO / 超时判定、连段计数生命周期、只读快照(MatchSnapshot)。

纪律:零 pygame(core 层);本文件不定义任何数值(全部来自 SystemCfg / MoveDef)。

hitstop 冻结模型(§4.4"命中 11/13/20、防御 9/10/14、投 0、弹受方 8"):
  * 每方一个冻结计数 freeze[side]。近身命中/防御:攻受双方都冻
    (等效"全局冻结 11 帧"——考卷原话);弹体命中:只冻受方(攻方照动);
    投技 hitstop=0 不冻结。
  * 冻结方跳过状态推进(但输入照喂进缓冲,搓招不丢;恢复帧合并)。
  * 冻结方不挂攻击窗、不结算投技、不发弹(帧没推进,不能开新判定);
    被冻结的受方照常挨打(受击状态静止,可被自由方继续连段)。
  * 有任何一方冻结的帧,回合计时不走。

管线(fighting 态每帧,顺序固定):
  1. 双方喂输入(motion.feed)→ triggers 暂存(hitstop 冻结期照喂);
  2. 双方 fighter.step(对手视图取帧首快照,保证双方对称;冻结方跳过);
  3. 攻击裁决:双方 active 先试 trade(互撞各吃一记),不成再各自单向 resolve;
  4. 投技:THROW_GRAB 进入当帧结算一次(victim.can_be_thrown 复查,
     抓取瞬间对手变不可抓 = 抓空,攻方播完动作无伤害);
  5. 弹体生成:attack_frame == projectile["start"] 那帧,同屏该方最多
     max_count 发(前弹未灭再搓不产新弹);
  6. 弹体推进 + resolve_projectile(命中即 on_hit 回收);
  7. 攻方墙角回推:physics.pushback_resolve 的第二返回值(A1 的 apply_hit
     只动受方拿不到对手,剩余量由本层补给攻方——见 apply_hit docstring);
  8. 连段计数 reset:受方脱离受击链(受击/浮空/倒地/起身/被投)时清零;
  9. 摄像机中点跟随 + clamp,双方夹进 [cam+edge, cam+view_w−edge];
  10. 计时(冻结帧不走);KO / 双 KO / 超时 → round_end(胜者 perform,冻结演出)。

回合状态机:
  fighting →(KO/超时)round_end(冻结 120 帧)→ 胜场达 rounds_to_win →
  match_end;否则 between_rounds(等调用方 next_round;gauge 按构造参数保留)
  → fighting 下一回合。
  双 KO:双方各记一胜(KOF 规则);PERFECT = 胜者满血;超时同血 = 平局双方各记一胜。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import combat, physics
from . import types as T
from .data import SystemCfg
from .fighter import (
    ATTACK,
    BLOCKSTUN,
    FALL,
    Fighter,
    HIT_AIR,
    HIT_CROUCH,
    HIT_STAND,
    KNOCKDOWN,
    THROW_GRAB,
    THROWN,
    WAKEUP,
)
from .motion import MotionInput
from .projectile import Projectile

# 回合结束演出帧数(裁量:2 秒定格供 UI 挂横幅)
ROUND_END_FRAMES = 120

# 弹体发射点离角色脚底中心的前向偏移 px(裁量)
PROJECTILE_SPAWN_OFFSET = 20.0

# 受击链:受方处于这些状态时攻方的连段计数保持,脱离即清零
_COMBO_ALIVE = {
    HIT_STAND, HIT_CROUCH, BLOCKSTUN, HIT_AIR, FALL,
    KNOCKDOWN, WAKEUP, THROWN, THROW_GRAB,
}


def _merge_triggers(stashed: Optional[T.FrameTriggers],
                    fresh: T.FrameTriggers) -> T.FrameTriggers:
    """hitstop 暂存的 triggers 合并:specials 旧的优先(先搓的先出,容量 1),
    dash 任一为真即真(双击不因定格丢失)。"""
    if stashed is None:
        return fresh
    return T.FrameTriggers(
        stashed.specials or fresh.specials,
        stashed.dash_fwd or fresh.dash_fwd,
        stashed.dash_back or fresh.dash_back,
    )


@dataclass(frozen=True)
class ProjectileView:
    """弹体的只读渲染视图。"""

    move_id: str
    x: float
    facing: int


@dataclass(frozen=True)
class MatchSnapshot:
    """一帧对局的只读快照(ui 只看这个,不许摸 Match/Fighter 内部)。"""

    phase: str  # fighting / round_end / between_rounds / match_end
    frame: int  # 本回合第几帧(hitstop 冻结帧也计,ui 动画相位用)
    round_no: int  # 第几回合(1 起)
    timer_frames: int  # 本回合剩余帧(60 帧 = 1 秒)
    wins: tuple  # (P1 胜场, P2 胜场)
    camera_x: int
    fighters: tuple  # (FighterSnapshot, FighterSnapshot) 按 P1/P2
    attack_frames: tuple  # (int|None, int|None) attack 态招内帧(ui 对动画相位)
    projectiles: tuple  # tuple[ProjectileView, ...]
    banners: tuple  # 回合结束时的一次性横幅,如 ("PERFECT", "K.O.")
    round_winner: Optional[T.Side]
    match_winner: Optional[T.Side]


class Match:
    """一场三局两胜对局(P1/P2 都由外部喂 Tick:键盘或 AI)。"""

    def __init__(self, cfg: SystemCfg, moves: dict, keep_gauge: bool = True) -> None:
        self.cfg = cfg
        self.moves = moves
        self.keep_gauge = keep_gauge
        self.round_no = 1
        self.wins = {T.Side.P1: 0, T.Side.P2: 0}
        self.match_winner: Optional[T.Side] = None
        self.phase = "fighting"
        self._spawn_round({T.Side.P1: 0, T.Side.P2: 0})

    # ---------- 回合生命周期 ----------

    def _spawn_round(self, gauge: dict) -> None:
        """建新回合的全部实体(fighter/motion/计数/弹体/计时);gauge 注入保留。"""
        self.f1 = Fighter(self.cfg, self.moves, T.Side.P1)
        self.f2 = Fighter(self.cfg, self.moves, T.Side.P2)
        for f, g in ((self.f1, gauge[T.Side.P1]), (self.f2, gauge[T.Side.P2])):
            f.gauge = g
        self.motion = {
            T.Side.P1: MotionInput(self.cfg.input, self.moves),
            T.Side.P2: MotionInput(self.cfg.input, self.moves),
        }
        self.counter = {  # 键 = 攻方:缩放的是"该方连打对方"的计数
            T.Side.P1: combat.ComboCounter(self.cfg.combo_scaling),
            T.Side.P2: combat.ComboCounter(self.cfg.combo_scaling),
        }
        self.projectiles: list = []
        self.freeze = {T.Side.P1: 0, T.Side.P2: 0}  # hitstop 每方独立计数
        self.round_timer = self.cfg.round_time_frames
        self.frame = 0
        self._stashed = {T.Side.P1: None, T.Side.P2: None}
        self._throw_done = {T.Side.P1: False, T.Side.P2: False}
        self.banners: tuple = ()
        self.round_winner: Optional[T.Side] = None
        self.end_timer = 0
        self.cam_x = 0
        self._camera()

    def next_round(self) -> None:
        """between_rounds 时开下一回合(重建角色,gauge 按 keep_gauge 保留)。"""
        if self.phase != "between_rounds":
            raise RuntimeError(f"只能在 between_rounds 开下一回合,当前 {self.phase!r}")
        self.round_no += 1
        gauge = {
            s: (self._f(s).gauge if self.keep_gauge else 0)
            for s in (T.Side.P1, T.Side.P2)
        }
        self._spawn_round(gauge)
        self.phase = "fighting"

    # ---------- 每帧驱动 ----------

    def step(self, tick_p1: T.Tick, tick_p2: T.Tick) -> MatchSnapshot:
        """推进一帧并返回快照。round_end 只倒演出计时;
        between_rounds / match_end 完全定格(等 next_round / 重建)。"""
        if self.phase == "round_end":
            self.end_timer -= 1
            if self.end_timer <= 0:
                self._settle_after_round()
            return self._snapshot()
        if self.phase != "fighting":
            return self._snapshot()

        self.frame += 1
        ticks = {T.Side.P1: tick_p1, T.Side.P2: tick_p2}

        # 1) 输入照喂(冻结期也进缓冲,搓招不丢)
        for side in (T.Side.P1, T.Side.P2):
            f = self._f(side)
            tr = self.motion[side].feed(ticks[side], f.facing)
            self._stashed[side] = _merge_triggers(self._stashed[side], tr)

        # 2) 双方推进(对手视图取帧首快照 → 对称;冻结方跳过并扣冻结计数)
        frozen_now = {s: self.freeze[s] > 0 for s in (T.Side.P1, T.Side.P2)}
        views = {T.Side.P1: self.f1.view(), T.Side.P2: self.f2.view()}
        for side in (T.Side.P1, T.Side.P2):
            other = T.Side.P2 if side is T.Side.P1 else T.Side.P1
            if frozen_now[side]:
                self.freeze[side] -= 1
                continue
            f = self._f(side)
            tr = self._stashed[side]
            self._stashed[side] = None
            f.step(tr if tr is not None else T.EMPTY_TRIGGERS,
                   ticks[side], views[other])

        # 3) 攻击裁决:trade 优先,不成再单向(冻结方不挂窗)
        a1 = None if frozen_now[T.Side.P1] else self.f1.active_attack()
        a2 = None if frozen_now[T.Side.P2] else self.f2.active_attack()
        pair = None
        if a1 is not None and a2 is not None:
            pair = combat.resolve_trade(
                a1, self.f1.view(), self.counter[T.Side.P1],
                a2, self.f2.view(), self.counter[T.Side.P2], self.cfg,
            )
        if pair is not None:
            self._apply_hit(T.Side.P1, self.f2, pair[0])
            self._apply_hit(T.Side.P2, self.f1, pair[1])
        else:
            if a1 is not None:
                r = combat.resolve(a1, self.f2.view(), self.counter[T.Side.P1], self.cfg)
                if r is not None:
                    self._apply_hit(T.Side.P1, self.f2, r)
            if a2 is not None:
                r = combat.resolve(a2, self.f1.view(), self.counter[T.Side.P2], self.cfg)
                if r is not None:
                    self._apply_hit(T.Side.P2, self.f1, r)

        # 4) 投技结算(THROW_GRAB 进入当帧一次;受方复查可抓性;冻结方不结算)
        for side in (T.Side.P1, T.Side.P2):
            other = T.Side.P2 if side is T.Side.P1 else T.Side.P1
            atk, victim = self._f(side), self._f(other)
            if frozen_now[side]:
                continue  # 冻结方帧没推进,保持待结算标记
            if atk.state == THROW_GRAB:
                if not self._throw_done[side]:
                    self._throw_done[side] = True
                    mv = atk.current_throw()
                    if mv is not None and victim.can_be_thrown():
                        r = combat.resolve_throw(
                            atk.view(), victim.view(), mv, self.cfg,
                        )
                        self._apply_hit(side, victim, r)
            else:
                self._throw_done[side] = False

        # 5) 弹体生成(发波帧一次性;同屏 max_count;冻结方不发)
        for side in (T.Side.P1, T.Side.P2):
            if frozen_now[side]:
                continue
            f = self._f(side)
            af = f.attack_frame()
            if af is None:
                continue
            mv = self.moves[f.view().move_id]
            if mv.projectile is None or af != mv.projectile["start"]:
                continue
            alive_mine = sum(
                1 for p in self.projectiles if p.alive and p.side == side
            )
            if alive_mine >= mv.projectile["max_count"]:
                continue
            self.projectiles.append(Projectile(
                mv, f.x + PROJECTILE_SPAWN_OFFSET * f.facing,
                f.facing, side, (0.0, float(self.cfg.stage.width)),
            ))

        # 6) 弹体推进与裁决(不受攻方冻结影响——弹一离手就自己飞)
        for proj in self.projectiles:
            proj.step()
            victim = self._f(T.Side.P2 if proj.side is T.Side.P1 else T.Side.P1)
            if not proj.alive:
                continue
            r = combat.resolve_projectile(
                proj, victim.view(), self.counter[proj.side], self.cfg,
            )
            if r is not None:
                proj.on_hit()
                self._apply_hit(proj.side, victim, r, melee=False)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # 8) 连段计数清零(受方脱离受击链)
        for side in (T.Side.P1, T.Side.P2):
            other = T.Side.P2 if side is T.Side.P1 else T.Side.P1
            if self._f(other).state not in _COMBO_ALIVE:
                self.counter[side].reset()

        # 9) 摄像机与边界
        self._camera()

        # 10) 计时与回合终了判定(本帧有任何冻结 → 计时不走)
        if not any(frozen_now.values()):
            self.round_timer -= 1
            if (self.f1.health <= 0 or self.f2.health <= 0
                    or self.round_timer <= 0):
                self._end_round()

        return self._snapshot()

    # ---------- 结算辅助 ----------

    def _apply_hit(self, atk_side: T.Side, victim: Fighter, res: T.HitResult,
                   melee: bool = True) -> None:
        """把 HitResult 落到双方:受方 apply_hit、攻方 on_attack_landed、
        hitstop 冻结(近身双方同冻=全局;弹只冻受方);近身再补攻方墙角回推
        (pushback_resolve 第二返回值,A1 只动受方拿不到攻方——契约)。"""
        atk = self._f(atk_side)
        v0, a0 = victim.x, atk.x
        victim.apply_hit(res)
        atk.on_attack_landed(res)
        if res.hitstop > 0:
            self.freeze[victim.side] = max(self.freeze[victim.side], res.hitstop)
            if melee:
                self.freeze[atk_side] = max(self.freeze[atk_side], res.hitstop)
        mv = self.moves.get(res.move)
        is_throw = mv is not None and mv.kind == "THROW"
        if (melee and not is_throw and res.kind in ("hit", "block", "trade")
                and res.knockdown == "none" and res.juggle_vy == 0.0):
            # 只有"普通受击/防御"分支受方真的被推了;倒地/浮空/投不走这里
            _, a_new = physics.pushback_resolve(
                v0, a0, res.pushback, 0.0, float(self.cfg.stage.width),
            )
            atk.x = a_new

    def _camera(self) -> None:
        """中点跟随 + clamp;双方夹进可视边内(§4.5)。"""
        mid = (self.f1.x + self.f2.x) / 2.0
        lo, hi = self.cfg.camera.clamp
        cam = min(max(int(mid - self.cfg.camera.follow_mid_offset), lo), hi)
        self.cam_x = cam
        left = cam + self.cfg.camera.edge_margin
        right = cam + self.cfg.view.w - self.cfg.camera.edge_margin
        for f in (self.f1, self.f2):
            if f.x < left:
                f.x = float(left)
            elif f.x > right:
                f.x = float(right)

    # ---------- 回合终局 ----------

    def _end_round(self) -> None:
        """定胜负:双 KO → 各记一胜;单边 KO → PERFECT 判定;超时 → 血多者胜,
        同血平局(双方各记一胜)。胜者 WIN、败者 LOSE(表演态定格)。"""
        self.phase = "round_end"
        self.end_timer = ROUND_END_FRAMES
        h1, h2 = self.f1.health, self.f2.health
        if h1 <= 0 and h2 <= 0:
            self.wins[T.Side.P1] += 1
            self.wins[T.Side.P2] += 1
            self.round_winner = None
            self.banners = ("DOUBLE K.O.",)
            self.f1.perform("lose")
            self.f2.perform("lose")
        elif h2 <= 0:
            self._round_win(T.Side.P1, h1)
        elif h1 <= 0:
            self._round_win(T.Side.P2, h2)
        elif h1 > h2:
            self._time_over(T.Side.P1)
        elif h2 > h1:
            self._time_over(T.Side.P2)
        else:
            self.wins[T.Side.P1] += 1
            self.wins[T.Side.P2] += 1
            self.round_winner = None
            self.banners = ("TIME OVER", "DRAW")
            self.f1.perform("lose")
            self.f2.perform("lose")

    def _round_win(self, side: T.Side, winner_health: int) -> None:
        self.wins[side] += 1
        self.round_winner = side
        perfect = winner_health >= self.cfg.health
        self.banners = ("PERFECT", "K.O.") if perfect else ("K.O.",)
        self._f(side).perform("win")
        other = T.Side.P2 if side is T.Side.P1 else T.Side.P1
        self._f(other).perform("lose")

    def _time_over(self, side: T.Side) -> None:
        self.wins[side] += 1
        self.round_winner = side
        self.banners = ("TIME OVER",)
        self._f(side).perform("win")
        other = T.Side.P2 if side is T.Side.P1 else T.Side.P1
        self._f(other).perform("lose")

    def _settle_after_round(self) -> None:
        """round_end 演出结束:够胜场 → match_end;否则 between_rounds。"""
        need = self.cfg.rounds_to_win
        w1, w2 = self.wins[T.Side.P1], self.wins[T.Side.P2]
        if w1 >= need and w2 >= need:
            self.phase = "match_end"  # 双方同时满场(连续双 KO):无冠军
            self.match_winner = None
        elif w1 >= need:
            self.phase = "match_end"
            self.match_winner = T.Side.P1
        elif w2 >= need:
            self.phase = "match_end"
            self.match_winner = T.Side.P2
        else:
            self.phase = "between_rounds"

    # ---------- 只读访问 ----------

    def _f(self, side: T.Side) -> Fighter:
        return self.f1 if side is T.Side.P1 else self.f2

    def _other(self, side: T.Side) -> Fighter:
        return self.f2 if side is T.Side.P1 else self.f1

    def ai_view(self, side: T.Side) -> T.AiView:
        """组装 AI 决策视图(AI 只看得到这些)。"""
        me, opp = self._f(side), self._other(side)
        view_w = self.cfg.view.w
        cornered = (me.x <= self.cam_x + 32.0
                    or me.x >= self.cam_x + view_w - 32.0)
        opp_proj = any(p.alive and p.side != side for p in self.projectiles)
        return T.AiView(
            dist=int(abs(me.x - opp.x)),
            own_health=me.health,
            own_gauge=me.gauge,
            facing=me.facing,
            opp_airborne=opp.view().airborne,
            opp_attacking=opp.state == ATTACK,
            opp_projectile=opp_proj,
            self_cornered=cornered,
        )

    def _snapshot(self) -> MatchSnapshot:
        return MatchSnapshot(
            phase=self.phase,
            frame=self.frame,
            round_no=self.round_no,
            timer_frames=max(self.round_timer, 0),
            wins=(self.wins[T.Side.P1], self.wins[T.Side.P2]),
            camera_x=self.cam_x,
            fighters=(self.f1.snapshot(), self.f2.snapshot()),
            attack_frames=(self.f1.attack_frame(), self.f2.attack_frame()),
            projectiles=tuple(
                ProjectileView(p.move.name, p.x, p.facing)
                for p in self.projectiles if p.alive
            ),
            banners=self.banners,
            round_winner=self.round_winner,
            match_winner=self.match_winner,
        )
