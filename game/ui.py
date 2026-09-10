"""game/ui.py — 渲染与交互层(batch B,设计文档 §4.7/§4.8)。

结构(照 sheepandsheep 的 App.step 无头驱动样板):
  * App:场景栈 + 主循环;run() 真跑(clock 节流 60fps 逻辑帧锁),
    step(events) 单帧驱动供无头测试——事件以参数注入,不 event.post;
  * InputState:键盘 → 每帧一个 Tick(附录 E:WASD 方向、UIOP 招式);
  * 场景:Title → RoundIntro → Fight →(回合内 KO 横幅)→ MatchEnd → Title;
  * 画面:内部 320×224 画布 → transform.scale ×3 → 960×672 窗口。

窗口呈现(契约裁决 #18,记设计文档):原计划用 pygame.SCALED 自动
整数放大,但 SCALED 会自选倍数(1080p 屏选 4×=1280×896),与文档承诺
的 960×672 不符 → 固定 960×672 窗口 + 手动 ×3 放大;dummy 无头环境
同一代码路径,零特判。

世界坐标 → 屏幕:x 减 camera_x;y 翻转(screen_y = ground_y − world_y,
全项目 y 向上为正的约定只在这一个换算点落地)。角色/特效锚点一律
"脚底中心"。

全局键:ESC 暂停(定格,F1 调试可叠加)、F1 调试框(红=攻击框、
黄=受击框、绿=推挤框)、失焦自动暂停(ACTIVEEVENT gain=0 +
WINDOWFOCUSLOST 双兼容)。

KO 慢动作:round_end 的前 20 个对局帧按 3 帧 1 步放慢(摔出/KO 定格
更有分量),其后正常速倒计时。
"""
from __future__ import annotations

import dataclasses

import pygame

from game import assets, poses
from game.art import fx, stage
from game.core import data
from game.core import types as T
from game.core.ai import TerryAI
from game.core.match import ROUND_END_FRAMES, Match

# ---------- 画布几何(320×224 ×3 = 960×672,数值来自 system.json 基线) ----------

W, H = 320, 224
WIN_W, WIN_H = 960, 672

# ---------- 键位(附录 E:WASD 方向 / UIOP 拳脚) ----------

KEY_DIRS = {
    pygame.K_w: T.Dir.U,
    pygame.K_a: T.Dir.L,
    pygame.K_s: T.Dir.D,
    pygame.K_d: T.Dir.R,
}
KEY_BTNS = {
    pygame.K_u: T.Btn.A,
    pygame.K_i: T.Btn.B,
    pygame.K_o: T.Btn.C,
    pygame.K_p: T.Btn.D,
}

# ---------- 配色 ----------

BG = (16, 14, 20)
TEXT = (232, 228, 220)
DIM = (150, 146, 150)
GOLD = (250, 200, 60)
HP = (224, 48, 48)
HP_BACK = (64, 16, 20)
GAUGE = (250, 200, 60)
GAUGE_MAX = (255, 90, 90)

# 姿势动画速率:每几帧进一格(非攻击态;攻击态用招内帧号对相位)
ANIM_RATE = {
    "idle": 10, "walk": 7, "run": 5, "jump": 6, "jump_fall": 6,
    "fall": 6, "dash_back": 6,
    # 反应姿势速率对齐硬直时长(hitstun 14~20 / 躺地 12 / 起身 24),
    # 配合姿势帧龄锚定:整段演出在硬直内从第 0 帧按序播完(§11.3)
    "knockdown": 6, "hit_high": 5, "hit_low": 8, "wakeup": 10,
    # intro 100 帧:三段演出各 ~40 帧后定格在战姿(§10.12 ⑧,不再循环)
    "intro": 40,
}

# HUD 几何
BAR_W, BAR_H = 140, 9
BAR_Y = 8
GAUGE_Y, GAUGE_H = 212, 6

AI_SEED = 7  # P2 对手 AI 种子(与 ai.json 的 42 错开,避免镜像自对弈;裁量)


# ---------- 基础绘制 ----------


def text(surf, s, size, color, x, y, align="left"):
    """中文文本;align ∈ left/center/right。字体来自 assets(缺字会 raise)。"""
    img = assets.cn_font(size).render(str(s), True, color)
    r = img.get_rect()
    if align == "center":
        r.center = (int(x), int(y))
    elif align == "right":
        r.right, r.y = int(x), int(y)
    else:
        r.topleft = (int(x), int(y))
    surf.blit(img, r)


def _create_screen():
    """建 960×672 窗口(见模块 docstring 裁决 #18:手动 ×3,不用 SCALED)。"""
    return pygame.display.set_mode((WIN_W, WIN_H))


def attack_anim_frame(move, af, n):
    """出招取帧(§11.2B 打击帧=判定帧;纯函数,零 pygame)。

    姿势 n 帧布局:[起手…(n-1-k 帧), 挥出×k(每判定窗一帧), 收招(末帧)];
    k = 判定窗数(发波招无窗 → projectile.start 当打击时刻)。
    af 落在窗辖区(窗 start 到下一窗 start 前)→ 显示该窗的挥出帧,
    判定生效的那一拍正是最"狠"的姿势;过末窗 → 收招;n≤1 退化为 0。
    """
    if n <= 1:
        return 0
    if move.windows:
        marks = [(w.start, w.end if w.end >= 0 else w.start + 2)
                 for w in move.windows]
        k = len(marks)
    elif move.projectile:
        sp = move.projectile.get("start", 0)
        marks = [(sp, sp + 2)]
        k = 1
    else:
        marks = [(0, 0)]
        k = 1
    k = min(k, n - 1)
    windup_n = n - 1 - k
    first_start = marks[0][0]
    if af < first_start:  # 起手:均匀铺满 startup,逐帧逼近挥出
        if windup_n <= 0:
            return n - 1 - k
        return min(af * windup_n // max(first_start, 1), windup_n - 1)
    for i in range(k):  # 窗辖区:本窗起 → 下一窗起(末窗到收招)
        next_start = marks[i + 1][0] if i + 1 < k else marks[i][1] + 1
        if af < next_start:
            return n - 1 - k + i
    return n - 1  # 收招


def _pose_surface(app, fs, af):
    """快照 → 姿势 Surface:攻击态按打击帧对齐取相位;其余优先用
    姿势帧龄(FightScene/RoundIntro 锚定,受击/起身/开场演出从第 0 帧
    按序播,不受全局节拍随机相位影响),无锚定(demo 静态绘制)退回
    全局帧数。"""
    n = poses.POSE_KEYS[fs.pose]  # 未注册姿势 KeyError:要炸就炸,不许静默
    if af is not None and fs.move_id:
        mv = app.moves.get(fs.move_id)
        f = attack_anim_frame(mv, af, n) if mv is not None else af % n
    elif af is not None:
        f = af % n
    else:
        base = app.ticks
        ages = getattr(app, "pose_ages", None)
        if ages and fs.side in ages:
            base = ages[fs.side]
        f = base // ANIM_RATE.get(fs.pose, 9) % n
    return assets.sprite(fs.pose, f, fs.facing, assets.load_palette(fs.side))


def _advance_pose_ages(app, snap, last_pose):
    """姿势帧龄锚定(素材 v2 §11.3):换姿势归零、否则 +1——多帧反应/
    演出按状态入口顺序从第 0 帧播。只在场景推进帧调用:暂停期不涨,
    KO 慢动作期随慢速推进走。"""
    ages = app.pose_ages
    for fs in snap.fighters:
        if last_pose.get(fs.side) != fs.pose:
            last_pose[fs.side] = fs.pose
            ages[fs.side] = 0
        else:
            ages[fs.side] = ages.get(fs.side, -1) + 1


def _draw_world(surf, app, snap):
    """舞台 + 弹体 + 双方角色(世界坐标 → 屏幕,P2 先画、P1 压上层)。"""
    cam = snap.camera_x
    gy = app.system.stage.ground_y
    stage.draw(surf, cam)
    for pv in snap.projectiles:
        img = fx.get_surface("proj_wave", app.ticks // 4 % 3)
        surf.blit(img, (pv.x - cam - img.get_width() / 2,
                        gy - img.get_height()))
    for fs, af in reversed(list(zip(snap.fighters, snap.attack_frames))):
        img = _pose_surface(app, fs, af)
        surf.blit(img, (fs.x - cam - img.get_width() / 2,
                        gy - fs.y - img.get_height()))
        if af is not None and fs.move_id and fs.move_id.startswith("power_geyser"):
            gey = fx.get_surface("fx_geyser", af % 5)  # 超杀喷泉演出
            surf.blit(gey, (fs.x - cam + 30 * fs.facing - gey.get_width() / 2,
                            gy - gey.get_height()))


def _draw_hud(surf, syscfg, snap):
    """血条/计时/胜点/能量槽/连段(只读快照,零内部状态)。"""
    f1, f2 = snap.fighters
    max_hp = syscfg.health

    def hp_bar(fs, right=False):
        w = max(0, int(BAR_W * fs.health / max_hp))
        x = (W - 6 - BAR_W) if right else 6
        pygame.draw.rect(surf, HP_BACK, (x, BAR_Y, BAR_W, BAR_H))
        if right:  # 右侧条从右端锚定收缩
            pygame.draw.rect(surf, HP, (W - 6 - w, BAR_Y, w, BAR_H))
        else:
            pygame.draw.rect(surf, HP, (x, BAR_Y, w, BAR_H))
        pygame.draw.rect(surf, (250, 250, 250), (x, BAR_Y, BAR_W, BAR_H), 1)

    hp_bar(f1)
    hp_bar(f2, right=True)

    secs = snap.timer_frames // 60
    color = TEXT if secs > 10 else (255, 90, 60)
    text(surf, f"{secs:02d}", 20, color, W / 2, BAR_Y + BAR_H / 2, align="center")

    for i in range(snap.wins[0]):  # 胜点:血条下小圆
        pygame.draw.circle(surf, GOLD, (12 + i * 9, 26), 3)
    for i in range(snap.wins[1]):
        pygame.draw.circle(surf, GOLD, (W - 12 - i * 9, 26), 3)

    for fs, right in ((f1, False), (f2, True)):
        w = max(0, int(BAR_W * fs.gauge / syscfg.gauge.max))
        full = fs.gauge >= syscfg.gauge.max
        color = GAUGE_MAX if full else GAUGE
        x = (W - 6 - BAR_W) if right else 6
        pygame.draw.rect(surf, (40, 34, 16), (x, GAUGE_Y, BAR_W, GAUGE_H))
        if right:
            pygame.draw.rect(surf, color, (W - 6 - w, GAUGE_Y, w, GAUGE_H))
        else:
            pygame.draw.rect(surf, color, (x, GAUGE_Y, w, GAUGE_H))
        if full:  # MAX 变色 + 小标
            text(surf, "MAX", 10, GAUGE_MAX,
                 (W - 6) if right else 6, GAUGE_Y - 12,
                 align="right" if right else "left")

    if f1.combo >= 2:  # 连段数挂在挨打方一侧(KOF 惯例)
        text(surf, f"{f1.combo} HITS", 13, GOLD, W - 8, 36, align="right")
    if f2.combo >= 2:
        text(surf, f"{f2.combo} HITS", 13, GOLD, 8, 36)


def _overlay_paused(surf):
    """暂停遮罩:半透明暗幕 + 提示(不破坏定格底图)。"""
    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 140))
    surf.blit(veil, (0, 0))
    text(surf, "已暂停", 28, TEXT, W / 2, H / 2 - 16, align="center")
    text(surf, "ESC 继续 · F1 调试框", 13, DIM, W / 2, H / 2 + 16, align="center")


# ---------- 输入 ----------


class InputState:
    """键盘 → 每帧一个 Tick:held 集 + 本帧边沿(按下/抬起)。"""

    def __init__(self):
        self._dirs: set = set()
        self._btns: set = set()
        self._pressed: frozenset = frozenset()
        self._released: frozenset = frozenset()

    def handle(self, events) -> None:
        pressed, released = set(), set()
        for e in events:
            if e.type == pygame.KEYDOWN:
                d = KEY_DIRS.get(e.key)
                if d is not None:
                    self._dirs.add(d)
                b = KEY_BTNS.get(e.key)
                if b is not None and b not in self._btns:  # 边沿只认首按
                    self._btns.add(b)
                    pressed.add(b)
            elif e.type == pygame.KEYUP:
                d = KEY_DIRS.get(e.key)
                if d is not None:
                    self._dirs.discard(d)
                b = KEY_BTNS.get(e.key)
                if b is not None and b in self._btns:
                    self._btns.discard(b)
                    released.add(b)
        self._pressed = frozenset(pressed)
        self._released = frozenset(released)

    def poll(self) -> T.Tick:
        """取走本帧 Tick(边沿取后即清,重复 poll 只剩 held)。"""
        t = T.Tick(frozenset(self._dirs), self._pressed, self._released)
        self._pressed = self._released = frozenset()
        return t


# ---------- 场景 ----------


class Scene:
    """场景基类:step 推进(事件进来)、draw 画进 320×224 画布。"""

    def __init__(self, app):
        self.app = app

    def step(self, events):
        pass

    def draw(self, surf):
        pass

    def _go(self, scene):
        self.app.scenes = [scene]


class TitleScene(Scene):
    """标题:按任意键开局(ESC/F1 等功能键不算"任意键")。"""

    def step(self, events):
        for e in events:
            if (e.type == pygame.KEYDOWN
                    and e.key not in (pygame.K_ESCAPE, pygame.K_F1)):
                self._go(RoundIntroScene(self.app, Match(
                    self.app.system, self.app.moves)))
                return

    def draw(self, surf):
        stage.draw(surf, 160)
        gy = self.app.system.stage.ground_y
        spr = _pose_surface_from_static(self.app, "idle", T.Side.P1, 1)
        surf.blit(spr, (150 - spr.get_width() / 2, gy - spr.get_height()))
        text(surf, "拳皇98", 40, GOLD, W / 2, 62, align="center")
        text(surf, "复刻 · TERRY BOGARD vs AI", 13, TEXT, W / 2, 100, align="center")
        text(surf, "WASD 移动(双击前=前冲) · UIOP 拳脚", 12, DIM, W / 2, 132, align="center")
        text(surf, "F1 调试框 · ESC 暂停", 12, DIM, W / 2, 148, align="center")
        if self.app.ticks // 20 % 2 == 0:
            text(surf, "按 任意键 开始", 15, GOLD, W / 2, 178, align="center")


def _pose_surface_from_static(app, pose, side, facing):
    n = poses.POSE_KEYS[pose]
    f = app.ticks // ANIM_RATE.get(pose, 9) % n
    return assets.sprite(pose, f, facing, assets.load_palette(side))


class RoundIntroScene(Scene):
    """回合开场:ROUND n + FIGHT!,结束切 Fight。"""

    INTRO_FRAMES = 100  # 60 帧 ROUND n + 40 帧 FIGHT!(裁量)

    def __init__(self, app, match):
        super().__init__(app)
        self.match = match
        self.t = self.INTRO_FRAMES
        # 姿势帧龄锚定:intro 三帧演出从第 0 帧按序播(素材 v2 §11.3)
        app.pose_ages = {}
        self._last_pose = {}

    def step(self, events):
        self.t -= 1
        _advance_pose_ages(self.app, self.match.snapshot(), self._last_pose)
        if self.t <= 0:
            self._go(FightScene(self.app, self.match))

    def draw(self, surf):
        _draw_world(surf, self.app, self.match.snapshot())
        if self.t > 40:
            text(surf, f"ROUND {self.match.round_no}", 24, GOLD,
                 W / 2, 84, align="center")
        else:
            text(surf, "FIGHT!", 32, (255, 90, 60), W / 2, 84, align="center")


class FightScene(Scene):
    """对战:P1 键盘 / P2 AI;KO 慢动作;火花;横幅;回合/终局流转。"""

    def __init__(self, app, match):
        super().__init__(app)
        self.match = match
        self.ai = TerryAI(
            dataclasses.replace(data.load_ai(), seed=AI_SEED),
            app.moves, app.system,
        )
        self.snap = None
        self._slowmo = 0
        self._sparks: list = []  # [x, y, 剩余帧, fx键]
        self._last_hp = [match.f1.health, match.f2.health]
        self._last_state = [match.f1.state, match.f2.state]
        # 姿势帧龄锚定:接管 App.pose_ages(上一场/开场场景的表作废)
        app.pose_ages = {}
        self._last_pose = {}

    def step(self, events):
        app = self.app
        app.input.handle(events)
        p1 = app.input.poll()
        m = self.match
        if m.phase == "fighting":
            p2 = (self.ai.next_tick(m.ai_view(T.Side.P2))
                  if app.vs_ai else T.EMPTY_TICK)
            self.snap = m.step(p1, p2)
            _advance_pose_ages(app, self.snap, self._last_pose)
            self._update_sparks()
        elif m.phase == "round_end":
            # KO 慢动作:前 20 个对局帧 3 帧 1 步,其后正常速
            early = m.end_timer > ROUND_END_FRAMES - 20
            self._slowmo += 1
            if not early or self._slowmo % 3 == 0:
                self.snap = m.step(T.EMPTY_TICK, T.EMPTY_TICK)
                _advance_pose_ages(app, self.snap, self._last_pose)
        elif m.phase == "between_rounds":
            m.next_round()
            self._go(RoundIntroScene(app, m))
        elif m.phase == "match_end":
            self._go(MatchEndScene(app, m, self.snap or m.snapshot()))

    def _update_sparks(self):
        for i, fs in enumerate(self.snap.fighters):
            if fs.health < self._last_hp[i]:  # 掉血 → 命中火花
                self._sparks.append([fs.x, fs.y + 50.0, 8, "fx_hit"])
            elif (fs.state == "blockstun"
                  and self._last_state[i] != "blockstun"):  # 防御火花
                self._sparks.append([fs.x, fs.y + 50.0, 6, "fx_block"])
            self._last_hp[i] = fs.health
            self._last_state[i] = fs.state
        for sp in self._sparks:
            sp[2] -= 1
        self._sparks = [sp for sp in self._sparks if sp[2] > 0]

    def draw(self, surf):
        snap = self.snap
        if snap is None:  # 场景刚建还没 step 过:画世界底子
            snap = self.match.snapshot()
        _draw_world(surf, self.app, snap)
        gy = self.app.system.stage.ground_y
        for sx, sy, t, key in self._sparks:
            img = fx.get_surface(key, (8 - t) % poses.POSE_KEYS[key])
            surf.blit(img, (sx - snap.camera_x - img.get_width() / 2,
                            gy - sy - img.get_height() / 2))
        _draw_hud(surf, self.app.system, snap)
        if snap.phase == "round_end" and snap.banners:
            for i, b in enumerate(snap.banners):
                text(surf, b, 26, (255, 210, 70),
                     W / 2, 78 + i * 30, align="center")
        if self.app.debug:
            self._debug_draw(surf)

    def _debug_draw(self, surf):
        """F1:红=攻击框、黄=受击框、绿=推挤框(世界 Box → 屏幕描边)。"""
        cam = self.match.cam_x
        gy = self.app.system.stage.ground_y
        for f in (self.match.f1, self.match.f2):
            v = f.view()
            for b in v.hurt:
                _box_outline(surf, b, cam, gy, (255, 220, 60))
            aa = f.active_attack()
            if aa is not None:
                for b in aa.world_hit:
                    _box_outline(surf, b, cam, gy, (255, 60, 60))
            pb = self.app.system.push_boxes["stand"]  # 相对脚底中心 → 平移到世界
            _box_outline(surf, T.Box(v.x + pb.x1, pb.y1, v.x + pb.x2, pb.y2),
                         cam, gy, (60, 220, 90))


def _box_outline(surf, b, cam, gy, color):
    r = pygame.Rect(int(b.x1 - cam), int(gy - b.y2),
                    int(b.x2 - b.x1), int(b.y2 - b.y1))
    pygame.draw.rect(surf, color, r, 1)


class MatchEndScene(Scene):
    """终局:P1/P2 WIN 或 DRAW,按任意键回标题。"""

    def __init__(self, app, match, snap):
        super().__init__(app)
        self.match = match
        self.snap = snap

    def step(self, events):
        for e in events:
            if (e.type == pygame.KEYDOWN
                    and e.key not in (pygame.K_ESCAPE, pygame.K_F1)):
                self._go(TitleScene(self.app))
                return

    def draw(self, surf):
        _draw_world(surf, self.app, self.snap)
        w = self.snap.match_winner
        label = {T.Side.P1: "P1 WIN", T.Side.P2: "P2 WIN"}.get(w, "DRAW GAME")
        text(surf, label, 34, GOLD, W / 2, 80, align="center")
        text(surf, "按 任意键 回到标题", 14, TEXT, W / 2, 130, align="center")


# ---------- 主程序 ----------


class App:
    """场景栈 + 单帧驱动;run() 真跑,step() 给无头测试。"""

    def __init__(self, vs_ai=True):
        pygame.init()
        assets.check_font_health()  # 中文字体自检:破碎占位符直接报错
        pygame.display.set_caption("拳皇98 复刻 · TERRY vs AI")
        self.screen = _create_screen()
        self.buf = pygame.Surface((W, H))  # 320×224 逻辑画布
        self.clock = pygame.time.Clock()
        self.running = True
        self.ticks = 0
        self.pose_ages = None  # 姿势帧龄锚定表;None=未锚定(按全局 ticks)
        self.vs_ai = vs_ai
        self.paused = False
        self.debug = False
        self.input = InputState()
        gamedata = data.load_all()  # 三份 JSON 全量校验(失败即炸,不静默)
        self.system = gamedata.system
        self.moves = gamedata.moves
        self.scenes = [TitleScene(self)]

    def scene(self):
        return self.scenes[-1]

    def step(self, events):
        """一帧:全局键处理 → 场景推进 → 渲染(暂停时定格 + 遮罩)。"""
        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        for e in events:
            if e.type == pygame.QUIT:
                self.running = False
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F1:
                    self.debug = not self.debug
                elif e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
            elif focus_lost is not None and e.type == focus_lost:
                self.paused = True  # 失焦自动暂停(窗口版)
            elif (e.type == pygame.ACTIVEEVENT
                    and getattr(e, "gain", 1) == 0):
                self.paused = True  # 失焦自动暂停(兼容事件)
        if not self.paused:
            self.scene().step(events)
            self.ticks += 1
        self._render()

    def _render(self):
        self.buf.fill(BG)
        self.scene().draw(self.buf)
        if self.paused:
            _overlay_paused(self.buf)
        pygame.transform.scale(self.buf, (WIN_W, WIN_H), self.screen)
        pygame.display.flip()

    def run(self):
        """主循环:事件泵照常(太久不泵系统会判死),clock 节流 60fps。"""
        while self.running:
            self.step(pygame.event.get())
            self.clock.tick(self.system.fps)
        pygame.quit()
