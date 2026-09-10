"""core/fighter.py — 角色状态机(设计文档 §4.3 状态表、§5.3 A1 契约)。

状态族(全部状态名是冻结字符串,snapshot/view 对外暴露):
  基础 idle/walk_fwd/walk_back/crouch
  移动 prejump(4f)→air→land;run→run_stop;dash_back(22f 固定弧线)
  防御 block_stand/block_crouch/blockstun
  攻击 attack(move_id)(startup/active/recovery 由 windows/total 驱动,帧号 0 起)
  硬直 hit_stand/hit_crouch
  浮空 hit_air→fall→落地 knockdown→wakeup(前 8 帧无敌)
  投技 throw_whiff(12f)/throw_grab(3+2+20f)/thrown(受方脚本位移)
  表演 win/lose/intro(空实现,外部经 perform() 切入)

帧语义约定(与 §6 测试逐帧断言对齐):
  * 出招瞬间 attack_frame=0(按下的那次 step 结束时招内帧号=0);
    之后每次 step 帧号 +1;帧号达到 total 时该次 step 直接转 idle。
  * 硬直类计时 _timer 为"剩余帧数":apply/进入时设置,每次 step 减 1,
    减到 0 后的下一次 step 恢复(即 stun=17 → 第 18 次 step 恢复)。
  * 空中积分一律走 physics.air_step(梯形),跳高才能贴住理论公式。

自由裁量值(契约未给数据字段,集中在此、batch D 可挪进 system.json):
  * KNOCKDOWN_LYDOWN=12:倒地躺的帧数(knockdown → wakeup 之间);
  * THROW_WHIFF_FRAMES=12:投技失败动作帧数(任务契约文字给定 12);
  * until="land" 的地面必杀落地 lag 用 jump.air_attack_land_lag。
"""
from __future__ import annotations

from . import physics
from . import types as T
from .data import SystemCfg

# ---------- 状态名(冻结字符串) ----------
IDLE = "idle"
WALK_FWD = "walk_fwd"
WALK_BACK = "walk_back"
CROUCH = "crouch"
PREJUMP = "prejump"
AIR = "air"
LAND = "land"
RUN = "run"
RUN_STOP = "run_stop"
DASH_BACK = "dash_back"
BLOCK_STAND = "block_stand"
BLOCK_CROUCH = "block_crouch"
BLOCKSTUN = "blockstun"
ATTACK = "attack"
HIT_STAND = "hit_stand"
HIT_CROUCH = "hit_crouch"
HIT_AIR = "hit_air"
FALL = "fall"
KNOCKDOWN = "knockdown"
WAKEUP = "wakeup"
THROW_WHIFF = "throw_whiff"
THROW_GRAB = "throw_grab"
THROWN = "thrown"
WIN = "win"
LOSE = "lose"
INTRO = "intro"

_SHOW = {WIN, LOSE, INTRO}  # 表演态:step 空转,只能外部切入/切出
# 不可行动状态(§4.3"缓冲续发"的存入面):受击/防御硬直/浮空受击/倒地/落地 lag
_UNACTABLE = {
    HIT_STAND, HIT_CROUCH, BLOCKSTUN, HIT_AIR, FALL, KNOCKDOWN, WAKEUP,
    LAND, RUN_STOP, THROW_WHIFF, THROW_GRAB, THROWN,
}
_THROWABLE_BLOCK = {KNOCKDOWN, WAKEUP, ATTACK, THROW_WHIFF, THROW_GRAB, THROWN}
_POSE_MAP = {  # 非攻击态 → pose 键(附录 D)
    IDLE: "idle", WALK_FWD: "walk", WALK_BACK: "walk", CROUCH: "crouch",
    PREJUMP: "prejump", AIR: "jump", LAND: "land", RUN: "run", RUN_STOP: "run",
    DASH_BACK: "dash_back", BLOCK_STAND: "stand_block",
    BLOCK_CROUCH: "crouch_block", HIT_STAND: "hit_high", HIT_CROUCH: "hit_low",
    HIT_AIR: "air_hit", FALL: "fall", KNOCKDOWN: "knockdown", WAKEUP: "wakeup",
    THROW_WHIFF: "throw_whiff", THROW_GRAB: "throw_grab", THROWN: "thrown",
    WIN: "win", LOSE: "lose", INTRO: "intro",
}

KNOCKDOWN_LYDOWN = 12  # 躺地帧数(裁量,见模块 docstring)
THROW_WHIFF_FRAMES = 12  # 投技失败动作帧数(裁量:契约文字给定 12,无 JSON 字段)


class Fighter:
    """单个角色实体。只认 cfg/moves 里的数值,不存任何硬编码招数。"""

    def __init__(self, cfg: SystemCfg, moves: dict, side: T.Side) -> None:
        self.cfg = cfg
        self.moves = moves  # dict[str, MoveDef]
        self.side = side
        self.x: float = float(cfg.stage.start_x[0 if side is T.Side.P1 else 1])
        self.y: float = 0.0
        self.vx: float = 0.0  # 地面移动/跳水平速度(绝对方向)
        self.vy: float = 0.0
        self.facing: int = 1 if side is T.Side.P1 else -1
        self.health: int = cfg.health
        self.gauge: int = 0
        self.state: str = IDLE
        self._timer: int = 0  # 硬直/阶段剩余帧(语义见模块 docstring)
        self._attack_move: T.MoveDef | None = None  # attack 态的当前招
        self._attack_frame: int = 0  # 招内帧号(0 起)
        self._used_windows: frozenset = frozenset()  # 本招已结算窗(命中后不再挂出)
        self._pending: str | None = None  # 缓冲续发(容量 1,新的覆盖旧的)
        self._blockstun_stance: str = "stand"  # blockstun 期间保持的防御姿态
        self._opp_x: float = self.x  # 最近一次 step 缓存的对手 x(推背方向用)
        self._opp_view: T.FighterView | None = None  # 最近一次对手视图(结算/观察用)
        self._lifted: bool = False  # until="land" 招是否已到起跳帧
        self._fresh_attack: bool = False  # 本 step 刚出招(出招帧不推帧号)
        self.combo: int = 0  # 自己作为攻方的连段数(对手脱离受击态时清零)

    # ---------- 方向换算(前/后 = 按 facing 的绝对 Dir) ----------

    def _dir_fwd(self) -> T.Dir:
        return T.Dir.R if self.facing > 0 else T.Dir.L

    def _dir_back(self) -> T.Dir:
        return T.Dir.L if self.facing > 0 else T.Dir.R

    def _holding_fwd(self, tick: T.Tick) -> bool:
        return self._dir_fwd() in tick.dirs

    def _holding_back(self, tick: T.Tick) -> bool:
        return self._dir_back() in tick.dirs

    def _holding_down(self, tick: T.Tick) -> bool:
        return T.Dir.D in tick.dirs

    # ---------- 姿态与框 ----------

    def _crouching(self) -> bool:
        """蹲姿:蹲立/蹲防/蹲姿攻击/blockstun 保持蹲防。"""
        if self.state in (CROUCH, BLOCK_CROUCH):
            return True
        if self.state == BLOCKSTUN:
            return self._blockstun_stance == "crouch"
        if self.state == ATTACK and self._attack_move is not None:
            return self._attack_move.stance == "crouch"
        return False

    def _hurt_boxes(self) -> tuple:
        """本帧受击框(未世界化,相对脚底面朝右)。"""
        if self.state == ATTACK and self._attack_move is not None and self._attack_move.hurt_boxes:
            return self._attack_move.hurt_boxes
        key = "crouch" if self._crouching() else "stand"
        return (self.cfg.hurt_boxes[key],)

    def _push_box_w(self) -> float:
        key = "crouch" if self._crouching() else "stand"
        b = self.cfg.push_boxes[key]
        return float(b.x2 - b.x1)

    def _world_box(self, b: T.Box) -> T.Box:
        """相对框 → 世界框(按 facing 镜像 + 平移脚底;攻击/受击同一规则)。"""
        if self.facing < 0:
            b = b.mirrored()
        return T.Box(self.x + b.x1, self.y + b.y1, self.x + b.x2, self.y + b.y2)

    # ---------- 对外只读接口(§5.3 契约) ----------

    def view(self) -> T.FighterView:
        """只读视图给对手与 combat/match 裁决方。

        guarding 语义:拉住后方向就在防御——站姿后走(walk_back)同时是
        站防(KOF 惯例:拉后既后退又能挡),blockstun 保持被击前的姿态。
        """
        guarding = self.state in (WALK_BACK, BLOCK_STAND, BLOCK_CROUCH, BLOCKSTUN)
        return T.FighterView(
            side=self.side,
            x=self.x,
            y=self.y,
            facing=self.facing,
            state=self.state,
            move_id=self._attack_move.name if self.state == ATTACK else None,
            airborne=self.y > 0.0,
            crouching=self._crouching(),
            guarding=guarding,
            guard_stance="crouch" if self._crouching() else "stand",
            in_hitstun=self.state in (HIT_STAND, HIT_CROUCH, BLOCKSTUN),
            invulnerable=self._invulnerable(),
            hurt=tuple(self._world_box(b) for b in self._hurt_boxes()),
        )

    def _invulnerable(self) -> bool:
        """当前帧无敌:wakeup 前 invuln_frames 帧 + 招式 invuln 区间(闭区间)。"""
        if self.state == WAKEUP:
            return self._timer > self.cfg.wakeup.frames - self.cfg.wakeup.invuln_frames
        if self.state == KNOCKDOWN:
            return True  # 躺地不可被追打(裁量:与起身无敌连成一段)
        if self.state == ATTACK and self._attack_move is not None:
            f = self._attack_frame
            return any(a <= f <= b for a, b in self._attack_move.invuln)
        return False

    def can_be_thrown(self) -> bool:
        """可被抓(§4.4):非浮空、非受击硬直、非倒地起身、非攻击/投技中。"""
        if self.y > 0.0:
            return False
        if self.state in (HIT_STAND, HIT_CROUCH, BLOCKSTUN, HIT_AIR, FALL):
            return False
        if self.state in _THROWABLE_BLOCK:
            return False
        return True

    def attack_frame(self) -> int | None:
        """attack 态的招内帧号(match 层发射弹体/演出对帧时需要,只读)。"""
        return self._attack_frame if self.state == ATTACK else None

    def snapshot(self) -> T.FighterSnapshot:
        """渲染快照。attack 态 pose=move.pose_key;air 态按升/降分 jump/jump_fall。"""
        if self.state == ATTACK and self._attack_move is not None:
            pose = self._attack_move.pose_key
        elif self.state == AIR:
            pose = "jump" if self.vy > 0 else "jump_fall"
        elif self.state == BLOCKSTUN:
            pose = "crouch_block" if self._blockstun_stance == "crouch" else "stand_block"
        else:
            pose = _POSE_MAP[self.state]
        return T.FighterSnapshot(
            side=self.side,
            x=self.x,
            y=self.y,
            facing=self.facing,
            state=self.state,
            move_id=self._attack_move.name if self.state == ATTACK else None,
            pose=pose,
            health=self.health,
            gauge=self.gauge,
            combo=self.combo,
        )

    def perform(self, state: str) -> None:
        """外部切入表演态(win/lose/intro;§4.3 表演状态空实现)。"""
        if state not in _SHOW:
            raise ValueError(f"表演态只认 {sorted(_SHOW)},得到 {state!r}")
        self.state = state

    # ---------- 每帧推进(§5.3:step 契约) ----------

    def step(self, triggers: T.FrameTriggers, tick: T.Tick, opp_view: T.FighterView) -> None:
        """一帧:输入/转移 → 物理积分 → 朝向刷新 → 连段观察 → 地面推挤。

        顺序细节:specials 的处理在状态分发之前(攻击态吃它走取消、
        不可行动态吃它进缓冲、可行动态直接出招);缓冲续发 flush 在
        状态分发之后——硬直 handler 在本帧恢复可行动时,恢复帧即续发。
        """
        self._opp_x = opp_view.x
        self._opp_view = opp_view
        if self.state in _SHOW:
            return  # 表演态空转(§4.3)

        special = triggers.specials[0] if triggers.specials else None
        if special is not None:
            if self.state in _UNACTABLE:
                self._pending = special  # 缓冲续发:容量 1,新的覆盖旧的
            elif self.state == ATTACK:
                self._try_cancel(special)  # 取消规则(§4.3 取消链)
            else:
                self._try_special(special)  # 可行动态直接出招
        # pending 的消费统一走 _advance_state 之后的 _flush_pending:
        # 硬直 handler 在本帧恢复可行动时,恢复帧同一帧完成续发。

        self._advance_state(triggers, tick, opp_view)
        self._flush_pending()
        self._advance_physics()
        self._refresh_facing(opp_view)
        self._watch_combo(opp_view)
        self._push_apart_if_ground(opp_view)

    def _flush_pending(self) -> None:
        """恢复可行动的第一帧消费缓冲(超杀气不够即丢弃,不回落普通技)。"""
        if self._pending is None:
            return
        if self.state in _UNACTABLE or self.state in _SHOW or self.state == ATTACK:
            return  # 尚未恢复/又进了新硬直 → 继续等
        mid, self._pending = self._pending, None
        self._try_special(mid)

    # ---------- 状态分发(每状态一个 handler,显式转移) ----------

    def _advance_state(self, triggers, tick, opp_view) -> None:
        handler = getattr(self, "_st_" + self.state, None)
        if handler is not None:
            handler(triggers, tick, opp_view)

    def _enter(self, state: str, timer: int = 0) -> None:
        self.state = state
        self._timer = timer

    def _common_input(self, triggers, tick, opp_view) -> bool:
        """可行动地面态公共输入(优先级:双击触发 > 投 > 普通技 > 跳 > 蹲)。

        按钮优先于跳:U+C 同帧时先出拳(KOF 跳攻击是"跳起后"按,不是起跳帧)。
        """
        if triggers.dash_fwd:
            self._enter(RUN)
            return True
        if triggers.dash_back:
            self._enter(DASH_BACK, self.cfg.dash_back.frames)
            self.vy = self.cfg.dash_back.vy0
            self.vx = -self.facing * self.cfg.dash_back.vx
            return True
        if self._try_throw(tick, opp_view):
            return True  # 抓/whiff 都算"按钮被投技流程吞掉"
        if self._try_normal(tick):
            return True
        if T.Dir.U in tick.dirs and not self._holding_down(tick):
            self._enter(PREJUMP, self.cfg.jump.prejump)
            return True
        if self._holding_down(tick):
            self._enter(CROUCH)
            return True
        return False

    def _st_idle(self, triggers, tick, opp_view):
        if self._common_input(triggers, tick, opp_view):
            return
        if self._holding_fwd(tick):
            self._enter(WALK_FWD)
        elif self._holding_back(tick):
            self._enter(WALK_BACK)
        # else 保持 idle

    def _st_walk_fwd(self, triggers, tick, opp_view):
        if self._common_input(triggers, tick, opp_view):
            return
        if not self._holding_fwd(tick):
            self._enter(IDLE)

    def _st_walk_back(self, triggers, tick, opp_view):
        if self._common_input(triggers, tick, opp_view):
            return
        if not self._holding_back(tick):
            self._enter(IDLE)

    def _st_crouch(self, triggers, tick, opp_view):
        # 蹲姿顺序:投(后+钮)→ 蹲姿技 → 跳(松 D)→ 蹲防(按后)→ 松 D 站起
        if self._try_throw(tick, opp_view):
            return
        if self._try_normal(tick):
            return
        if T.Dir.U in tick.dirs and not self._holding_down(tick):
            self._enter(PREJUMP, self.cfg.jump.prejump)
            return
        if self._holding_back(tick) and self._holding_down(tick):
            self._enter(BLOCK_CROUCH)  # 蹲+后 = 蹲防(§4.3)
            return
        if not self._holding_down(tick):
            self._enter(IDLE)

    def _st_prejump(self, triggers, tick, opp_view):
        # timer 归零的那次 step 起跳;大小跳按起跳帧 U 是否仍按住判定
        if self._timer <= 1:
            big = T.Dir.U in tick.dirs
            if self._holding_fwd(tick) and not self._holding_back(tick):
                kind = "fwd" if big else "small_fwd"
            elif self._holding_back(tick):
                kind = "back" if big else "small_back"
            else:
                kind = "up" if big else "small_up"
            self.vx, self.vy = physics.jump_arc(kind, self.facing, self.cfg)
            self._enter(AIR)
        else:
            self._timer -= 1

    def _st_air(self, triggers, tick, opp_view):
        # 空中只接普通技(空中技);出招后锁定到落地由 attack 的 end=-1 语义保证
        if tick.pressed:
            self._try_normal(tick)

    def _st_land(self, triggers, tick, opp_view):
        if self._timer <= 1:
            self._enter(IDLE)
        else:
            self._timer -= 1

    def _st_run(self, triggers, tick, opp_view):
        if self._common_input(triggers, tick, opp_view):
            return
        if not self._holding_fwd(tick):
            self._enter(RUN_STOP, self.cfg.run.stop_frames)

    def _st_run_stop(self, triggers, tick, opp_view):
        # 制动期一切输入无效(specials 已在 step 开头进缓冲),到点回 idle
        if self._timer <= 1:
            self._enter(IDLE)
        else:
            self._timer -= 1

    def _st_dash_back(self, triggers, tick, opp_view):
        # 固定 22 帧弧线(§4.3),位移/重力全在物理段;帧数到点回 idle
        if self._timer <= 1:
            self._enter(IDLE)
        else:
            self._timer -= 1

    # ---------- 出招(普通技/必杀/超杀/取消/投技) ----------

    def _enter_attack(self, mv: T.MoveDef) -> None:
        """进攻击态:招内帧号 0 起、命中窗全部重置。

        _fresh_attack 不在这里设:只有"step 开头的 specials 出招/取消"
        (先于状态分发发生,同一 step 还会跑 _st_attack)需要标志;
        按钮出招发生在 handler 内(分发已过),不能标,否则标志残留会
        吞掉下一次 step 的帧推进。
        """
        self.state = ATTACK
        self._attack_move = mv
        self._attack_frame = 0
        self._used_windows = frozenset()
        self._lifted = False  # until="land" 招是否已到起跳帧
        # 空中技:出招瞬间空中速度保留(§4.3 契约),vx/vy 不动;
        # 地面招站定(vx=0,燃烧拳等 motion 段自管位移)
        if mv.stance != "air":
            self.vx = 0.0

    def _try_special(self, move_id: str) -> bool:
        """必杀/超杀出招(可行动地面态调用)。超杀先查气、出招立即扣气;
        气不够直接忽略,不回落成普通技(§4.3 出招规则)。"""
        mv = self.moves.get(move_id)
        if mv is None or mv.kind not in ("SPECIAL", "SUPER"):
            return False
        if self.y > 0.0:
            return False  # 基线必杀全是 stance=stand,空中不搓必杀
        if mv.kind == "SUPER":
            if self.gauge < mv.gauge_cost:
                return False
            self.gauge -= mv.gauge_cost
        self._enter_attack(mv)
        self._fresh_attack = True  # 本次 step 已是新招帧 0,分发时不再推帧
        return True

    def _try_cancel(self, move_id: str) -> None:
        """攻击中收到 specials:取消链规则(§4.3)。

        条件:当前招帧号 < total 且 cancels 含目标招 kind(小写)。
        任务卡契约即此三条,cancels 表外的招不切;THROW 天然不在表内。
        """
        mv = self.moves.get(move_id)
        if mv is None or mv.kind not in ("SPECIAL", "SUPER"):
            return
        cur = self._attack_move
        if cur is None or self._attack_frame >= cur.total:
            return
        if mv.kind.lower() not in cur.cancels:
            return
        if mv.kind == "SUPER":
            if self.gauge < mv.gauge_cost:
                return
            self.gauge -= mv.gauge_cost
        self._enter_attack(mv)  # 新招 startup 从 0 计
        self._fresh_attack = True  # 本次 step 即新招帧 0

    def _try_normal(self, tick: T.Tick) -> bool:
        """普通技:pressed 的按钮 × 当前姿态(站/蹲/空)匹配即出(§4.3)。

        按 terry.json 声明序遍历,同帧多按钮时取先声明的(A<B<C<D 稳定)。
        """
        if not tick.pressed:
            return False
        if self.state == AIR:
            stance = "air"  # 空中技只能 air 状态出
        else:
            stance = "crouch" if self._crouching() else "stand"
        for mv in self.moves.values():
            if mv.kind != "NORMAL" or mv.input.get("type") != "button":
                continue
            if mv.stance != stance:
                continue
            if T.Btn[mv.input["button"]] not in tick.pressed:
                continue
            self._enter_attack(mv)
            return True
        return False

    def _try_throw(self, tick: T.Tick, opp_view: T.FighterView) -> bool:
        """投技触发(§4.3):按住前/后 + 投钮,距离 <= throw_range 且
        对手可被抓 → throw_grab;按了钮但条件不满足 → throw_whiff(§4.4)。"""
        if not tick.pressed:
            return False
        for mv in self.moves.values():
            if mv.input.get("type") != "throw":
                continue
            if T.Btn[mv.input["button"]] not in tick.pressed:
                continue
            want = self._dir_fwd() if mv.input["dir"] == "fwd" else self._dir_back()
            if want not in tick.dirs:
                continue
            if abs(self.x - opp_view.x) <= mv.throw_range and _view_throwable(opp_view):
                self._enter(THROW_GRAB, mv.total)  # 3/2/20 = total 25 帧
            else:
                self._enter(THROW_WHIFF, THROW_WHIFF_FRAMES)
            return True  # 按钮被投流程消费:条件不满足也是 whiff,不出重拳
        return False

    # ---------- 防御 / 硬直 / 倒地 / 投技表演 / 浮空 handler ----------

    def _st_block_stand(self, triggers, tick, opp_view):
        # 站防:松开后回 idle;蹲+后 → 蹲防;U(松 D)可起跳;specials 破防
        if self._holding_down(tick) and self._holding_back(tick):
            self._enter(BLOCK_CROUCH)
            return
        if T.Dir.U in tick.dirs and not self._holding_down(tick):
            self._enter(PREJUMP, self.cfg.jump.prejump)
            return
        if not self._holding_back(tick):
            self._enter(IDLE)

    def _st_block_crouch(self, triggers, tick, opp_view):
        # 蹲防:松 D 站起(仍拉后 → 站防);松后仍蹲
        if not self._holding_down(tick):
            if self._holding_back(tick):
                self._enter(BLOCK_STAND)
            else:
                self._enter(IDLE)
        elif not self._holding_back(tick):
            self._enter(CROUCH)

    def _st_blockstun(self, triggers, tick, opp_view):
        # 防御硬直:到点后仍拉后 → 保持对应姿态防御,否则回 idle
        if self._timer == 0:
            if self._holding_back(tick):
                if self._blockstun_stance == "crouch":
                    self._enter(BLOCK_CROUCH)
                else:
                    self._enter(BLOCK_STAND)
            else:
                self._enter(IDLE)
        else:
            self._timer -= 1

    def _st_hit_stand(self, triggers, tick, opp_view):
        # 受击硬直:一切输入无效(缓冲续发在 step 开头存),到点回 idle
        if self._timer == 0:
            self._enter(IDLE)
        else:
            self._timer -= 1

    _st_hit_crouch = _st_hit_stand  # 蹲姿受击:同样只等计时(姿态由 pose 表现)

    def _st_knockdown(self, triggers, tick, opp_view):
        # 倒地躺 KNOCKDOWN_LYDOWN 帧后自动起身(时长为裁量,见模块 docstring)
        if self._timer <= 1:
            self._enter(WAKEUP, self.cfg.wakeup.frames)
        else:
            self._timer -= 1

    def _st_wakeup(self, triggers, tick, opp_view):
        # 起身 24 帧;前 8 帧无敌由 _invulnerable() 按 timer 算
        if self._timer <= 1:
            self._enter(IDLE)
        else:
            self._timer -= 1

    def _st_throw_whiff(self, triggers, tick, opp_view):
        if self._timer <= 1:
            self._enter(IDLE)
        else:
            self._timer -= 1

    _st_throw_grab = _st_throw_whiff  # 抓取动作:播满 total 帧回 idle

    def _st_thrown(self, triggers, tick, opp_view):
        # 被投:脚本位移在 apply_hit 已完成,这里只等落地(物理段转 knockdown)
        pass

    _st_win = _st_thrown  # 表演态 step 空转(已在 step() 开头拦截,这里兜底)
    _st_lose = _st_thrown
    _st_intro = _st_thrown

    def _st_attack(self, triggers, tick, opp_view):
        """攻击态推进:帧号 +1 与结束判定(total 到点收招)。

        起跳帧检测在物理段(保证 from=0 的招第 0 帧就升空);
        until="land" 招 total 到点但人还在天上时不收招——等物理段落地
        (power_dunk 滑行+滞空 > total,不钳住会悬空回 idle)。
        """
        mv = self._attack_move
        if mv is None:
            self._enter(IDLE)
            return
        if self._fresh_attack:
            # 出招/取消发生在本 step 的开头(输入处理阶段),这次 step 就是
            # 新招的第 0 帧:不推进帧号(与"从 idle 按下出招"的帧 0 语义对齐)
            self._fresh_attack = False
            return
        if self._attack_frame + 1 >= mv.total:
            flying = (
                mv.motion is not None
                and mv.motion.get("until") == "land"
                and self.y > 0.0
            )
            if not flying:
                self._enter(IDLE)  # 帧号 total-1 是最后一帧,本次 step 收招
                return
            self._attack_frame = mv.total - 1  # 悬空:帧号钳住等落地
        else:
            self._attack_frame += 1

    # ---------- 物理段(状态转移后的积分/位移) ----------

    def _advance_physics(self) -> None:
        st = self.state
        if st == AIR:
            self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
            self.x += self.vx
            if landed:
                self.vx = 0.0
                self._land(self.cfg.jump.air_lag)  # 空跳落地 lag=0 → 直接 idle
        elif st == ATTACK:
            self._attack_physics()
        elif st == HIT_AIR:
            self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
            if not landed and self.vy <= 0.0:
                self.state = FALL  # 上升段结束 → 下落段(§4.3 状态表两态)
            if landed:
                self._enter(KNOCKDOWN, KNOCKDOWN_LYDOWN)  # 浮空落地不经过 land
        elif st == FALL:
            self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
            if landed:
                self._enter(KNOCKDOWN, KNOCKDOWN_LYDOWN)
        elif st == THROWN:
            self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
            if landed:
                self._enter(KNOCKDOWN, KNOCKDOWN_LYDOWN)  # 被投落地 → 倒地
        elif st == DASH_BACK:
            if self.y > 0.0 or self.vy > 0.0:
                self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
                self.x += self.vx
                if landed:
                    self.vx = 0.0  # 落地后的残余帧站定恢复
        elif st == WALK_FWD:
            # 走速每帧现算:facing 若被刷新(落地换边)方向立刻正确
            self.x += physics.walk_step("fwd", self.facing, self.cfg)
        elif st == WALK_BACK:
            self.x += physics.walk_step("back", self.facing, self.cfg)
        elif st == RUN:
            self.x += physics.run_step(self.facing, self.cfg)
        # 其余状态(idle/crouch/防御/硬直/倒地/投技/表演)不发生位移

    def _attack_physics(self) -> None:
        """攻击态物理:空中招继承跳速积分;地面招按 motion 参数走。"""
        mv = self._attack_move
        if mv is None:
            return
        if mv.stance == "air":
            # 空中技:出招瞬间速度保留,继续抛物线;判定到落地(end=-1)
            self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
            self.x += self.vx
            if landed:
                self.vx = 0.0
                self._land(self.cfg.jump.air_attack_land_lag)  # 空攻落地 lag=2
            return
        mo = mv.motion
        if mo is None:
            return
        if mo.get("until") == "land":
            if not self._lifted and self._attack_frame >= mo.get("from_frame", 0):
                self.vy = mo["vy0"]  # 起跳帧检测放物理段,保证 from=0 第 0 帧升空
                self._lifted = True
            if self._lifted:
                if "vx" in mo:
                    self.x += mo["vx"] * self.facing  # 起跳后水平持续
                self.y, self.vy, landed = physics.air_step(self.y, self.vy, self.cfg)
                if landed:
                    self.vx = 0.0
                    # until=land 招落地即结束攻击(total 未到也直接进落地流程)
                    self._land(self.cfg.jump.air_attack_land_lag)
            elif "vx" in mo:
                self.x += mo["vx"] * self.facing  # from_frame 前的滑行段
        elif "vx" in mo and self._attack_frame < mo.get("frames", 0):
            # frames 型(燃烧拳):出招起维持 vx*facing 共 frames 帧
            self.x += mo["vx"] * self.facing

    def _land(self, lag: int) -> None:
        if lag > 0:
            self._enter(LAND, lag)
        else:
            self._enter(IDLE)  # lag=0 的落地直接可行动

    # ---------- 朝向 / 连段观察 / 推挤 ----------

    def _refresh_facing(self, opp_view) -> None:
        """站/蹲/落地瞬间刷新朝向;空中不翻(§4.3);攻击中锁向(KOF 惯例,
        裁量:攻击出手后对手绕背也不转头)。"""
        if self.y > 0.0:
            return
        if self.state == ATTACK:
            return
        dx = opp_view.x - self.x
        if dx > 0:
            self.facing = 1
        elif dx < 0:
            self.facing = -1  # dx==0 保持原朝向

    def _watch_combo(self, opp_view) -> None:
        """combo 清零条件:自己观察到对手脱离受击态(§5.3)。"""
        if self.combo == 0:
            return
        busy = (
            opp_view.in_hitstun
            or opp_view.airborne
            or opp_view.state in ("hit_air", "fall", "knockdown", "wakeup", "thrown")
        )
        if not busy:
            self.combo = 0

    def _push_apart_if_ground(self, opp_view) -> None:
        """地面推挤(§4.3):双方都在地面且推挤框重叠 → 对称推开到不重叠。

        空中无推挤(KOF 换边特色);推挤宽 = 双方推挤框半宽之和。
        只修自己的 x——对手在自己 step 时按同样规则修正,结果收敛一致。
        """
        if self.y > 0.0 or opp_view.y > 0.0:
            return
        if self.state in _SHOW or opp_view.state in ("win", "lose", "intro"):
            return
        theirs = self.cfg.push_boxes["crouch" if opp_view.crouching else "stand"]
        joint = (self._push_box_w() + float(theirs.x2 - theirs.x1)) / 2.0
        me, _ = physics.push_apart_full(
            self.x, opp_view.x, joint, 0.0, float(self.cfg.stage.width)
        )
        self.x = me

    # ---------- 攻击挂出 / 结算(§5.3 契约) ----------

    def active_attack(self):
        """当前帧的判定窗(世界坐标);一次攻击每窗只结算一次。

        窗匹配:招内帧号落在 [start, end](end==-1 空中技 = start 起直到
        落地;"落地即结束攻击"保证不会挂到落地后);已用窗不再挂出
        (on_attack_landed 标记)。
        """
        if self.state != ATTACK or self._attack_move is None:
            return None
        mv = self._attack_move
        for wi, win in enumerate(mv.windows):
            if wi in self._used_windows:
                continue
            if win.end == -1:
                hit_now = self._attack_frame >= win.start and self.y > 0.0
            else:
                hit_now = win.start <= self._attack_frame <= win.end
            if not hit_now:
                continue
            world = tuple(self._world_box(b) for b in win.hit)
            return T.ActiveAttack(self.side, mv, wi, self._attack_frame, world)
        return None

    def on_attack_landed(self, hit: T.HitResult) -> None:
        """攻方结算:combo+1(命中才计,被防不构成连段)、涨气、标记窗已用。"""
        if hit.kind in ("hit", "trade"):
            self.combo += 1
        self.gauge = min(self.gauge + hit.gauge_attacker, self.cfg.gauge.max)
        wi = self._cur_window()
        if wi >= 0:
            self._used_windows = self._used_windows | frozenset([wi])

    def _cur_window(self) -> int:
        """当前生效的判定窗序号(标记"已用"用;无窗招返回 -1 不标)。"""
        if self.state != ATTACK or self._attack_move is None:
            return -1
        mv = self._attack_move
        for wi, win in enumerate(mv.windows):
            if win.end == -1:
                if self._attack_frame >= win.start and self.y > 0.0:
                    return wi
            elif win.start <= self._attack_frame <= win.end:
                return wi
        return -1

    def apply_hit(self, hit: T.HitResult) -> None:
        """受方结算:扣血/涨气/推背/进对应受击状态。

        damage 语义(契约同步):hit=已缩放伤害、block=削血值,直接扣。
        投技(moves[hit.move].kind==THROW)例外:pushback 为带符号世界
        位移,直接加;受方进 thrown 走脚本轨迹(水平 40px + 小弹起弧落地)。
        攻方回推量由 match 层用 physics.pushback_resolve 的第二返回值应用
        (A1 的 Fighter 只动自己,拿不到对手引用)。
        """
        self.health = max(0, self.health - hit.damage)
        self.gauge = min(self.gauge + hit.gauge_victim, self.cfg.gauge.max)
        mv = self.moves.get(hit.move)
        if mv is not None and mv.kind == "THROW":
            self.x += hit.pushback  # 带符号,不再乘朝向(契约)
            self.vx = 0.0
            self.vy = self.cfg.juggle_bounce_vy  # 小弹起弧(裁量:落地进 knockdown)
            self._enter(THROWN)
            return
        if hit.juggle_vy > 0.0:
            # 浮空弹起:空中被打 → hit_air(§4.3 浮空链)
            self.vx = 0.0
            self.vy = hit.juggle_vy
            self._enter(HIT_AIR)
            return
        if hit.knockdown in ("sweep", "hard", "air_juggle"):
            # 扫倒/重击倒地:不弹起,直接进倒地链(air_juggle 由弹起分支兜走)
            self.vx = 0.0
            self._enter(KNOCKDOWN, KNOCKDOWN_LYDOWN)
            return
        # 普通受击/防御硬直:推背方向 = 远离攻方(用 step 缓存的对手位置算)
        me, _ = physics.pushback_resolve(
            self.x, self._opp_x, hit.pushback, 0.0, float(self.cfg.stage.width)
        )
        self.x = me
        self.vx = 0.0
        if hit.kind == "block":
            self._blockstun_stance = "crouch" if self._crouching() else "stand"
            self._enter(BLOCKSTUN, hit.stun)
        else:
            target = HIT_CROUCH if self._crouching() else HIT_STAND
            self._enter(target, hit.stun)


def _view_throwable(v: T.FighterView) -> bool:
    """从 FighterView 推导"可被抓"(与 Fighter.can_be_thrown 同语义)。

    FighterView 没冻结 can_be_thrown 字段(契约不可改),投技触发方只能
    由 view 的现有字段推导:浮空/硬直/倒地/攻击/投技中/表演态均不可投。
    """
    if v.airborne or v.in_hitstun:
        return False
    if v.state in (
        "knockdown", "wakeup", "attack",
        "throw_whiff", "throw_grab", "thrown", "win", "lose", "intro",
    ):
        return False
    return True
