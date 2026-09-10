"""tests/test_ui.py — UI 层无头测试(设计文档 §6 test_ui 组)。

跑法:cd ~/kof98 && ./test.sh
批次:batch B。考卷条目与断言对应:
  * App.step 单帧驱动:注入 KEYDOWN WASD/UIOP → Tick 正确;失焦事件 → 暂停态;
  * 场景栈流转 Title→RoundIntro→Fight→KO→MatchEnd→Title;
  * HUD 像素采样:满血/半血管像素数、MAX 变色、倒计时数字非空;
  * F1 调试框像素(红/黄/绿,考卷把它记在 test_integration,这里一并覆盖);
  * dummy 下建窗正常(窗口呈现改手动 ×3,契约裁决 #18,详见 game/ui.py)。

驱动方式照 sheepandsheep:SDL dummy + 事件以 pygame.event.Event 直注参数,
不 event.post。场景级测试用 vs_ai=False(P2 站桩,确定性),AI 链路在
test_match/test_integration 验。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.core import types as T  # noqa: E402
from game.core.match import Match  # noqa: E402
from game.ui import (  # noqa: E402
    App,
    FightScene,
    HP,
    MatchEndScene,
    RoundIntroScene,
    TitleScene,
)

BAR_RECT = pygame.Rect(6, 8, 140, 9)      # P1 血条(左锚)
GAUGE_RECT = pygame.Rect(6, 212, 140, 6)  # P1 能量槽(左锚)
TIMER_RECT = pygame.Rect(146, 2, 28, 26)  # 计时数字区(画面中心)


def keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key})


def keyup(key):
    return pygame.event.Event(pygame.KEYUP, {"key": key})


def count_color(surf, rect, color, tol=2):
    """矩形内近似色像素数(HUD/描边采样;描边是纯色 1px,容差只防抖动)。"""
    n = 0
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            p = surf.get_at((x, y))
            if (abs(p[0] - color[0]) <= tol and abs(p[1] - color[1]) <= tol
                    and abs(p[2] - color[2]) <= tol):
                n += 1
    return n


def count_all(surf, color, tol=2):
    return count_color(surf, surf.get_rect(), color, tol)


# ---------- 建窗与单帧驱动 ----------


def test_app_boots_headless():
    """dummy 下建窗正常:窗口固定 960×672,逻辑画布 320×224(裁决 #18)。"""
    app = App()
    assert app.screen.get_size() == (960, 672)
    assert app.buf.get_size() == (320, 224)
    assert isinstance(app.scene(), TitleScene)
    app.step([])  # 空事件画一帧不炸


def test_inputstate_maps_keys_to_tick():
    """KEYDOWN WASD/UIOP → Tick:方向进 dirs,按钮按边沿进 pressed/released。"""
    inp = App().input
    inp.handle([keydown(pygame.K_w), keydown(pygame.K_a),
                keydown(pygame.K_s), keydown(pygame.K_o)])
    t = inp.poll()
    assert t.dirs == frozenset({T.Dir.U, T.Dir.L, T.Dir.D})
    assert t.pressed == frozenset({T.Btn.C})
    assert t.released == frozenset()
    inp.handle([keyup(pygame.K_o)])
    t = inp.poll()
    assert t.released == frozenset({T.Btn.C})
    assert t.dirs == frozenset({T.Dir.U, T.Dir.L, T.Dir.D})  # 方向还按着
    # 重复 KEYDOWN(键重复)不该再记边沿
    inp.handle([keydown(pygame.K_o)])
    inp.handle([keydown(pygame.K_o)])
    assert inp.poll().pressed == frozenset()
    inp.handle([keyup(pygame.K_o), keyup(pygame.K_o)])
    assert inp.poll().released == frozenset({T.Btn.C})  # 只记一次抬起


def test_fight_scene_keyboard_reaches_match():
    """键盘事件真的进 Match:按右=前进走,松右+按O=出重拳 st_C。"""
    app = App(vs_ai=False)
    m = Match(app.system, app.moves)
    app.scenes = [FightScene(app, m)]
    app.step([keydown(pygame.K_d)])
    assert m.f1.state == "walk_fwd"  # P1 面右,右=前
    for _ in range(5):
        app.step([])  # 无事件=方向仍按住(InputState 只在 KEYUP 里清)
        assert m.f1.state == "walk_fwd"
    app.step([keyup(pygame.K_d), keydown(pygame.K_o)])
    assert m.f1.state == "attack"
    assert m.f1.view().move_id == "st_C"


def test_focus_lost_and_esc_pause():
    """失焦事件(ACTIVEEVENT gain=0)→ 自动暂停,暂停期场景不推进;ESC 切换。"""
    app = App()
    app.step([keydown(pygame.K_RETURN)])  # 进回合开场
    assert isinstance(app.scene(), RoundIntroScene)
    app.step([pygame.event.Event(pygame.ACTIVEEVENT, {"gain": 0, "state": 1})])
    assert app.paused is True
    frozen = app.scene().t
    app.step([keydown(pygame.K_a)])  # 暂停期:场景帧数冻结
    assert app.scene().t == frozen
    app.step([keydown(pygame.K_ESCAPE)])  # ESC 解除暂停(这一帧场景即恢复推进)
    assert app.paused is False
    app.step([])
    assert app.scene().t == frozen - 2  # 解除帧 + 本帧 = 走了 2 帧


# ---------- 场景栈流转 ----------


def test_scene_flow_title_to_fight():
    app = App()
    app.step([keydown(pygame.K_RETURN)])
    assert isinstance(app.scene(), RoundIntroScene)
    for _ in range(RoundIntroScene.INTRO_FRAMES):
        app.step([])
    assert isinstance(app.scene(), FightScene)


def test_scene_flow_ko_to_match_end_to_title():
    """两回合 KO → MatchEnd → 任意键回 Title(KO 横幅/回合切替全链路)。"""
    app = App(vs_ai=False)
    m = Match(app.system, app.moves)
    app.scenes = [FightScene(app, m)]
    for rnd in range(2):
        m.f2.health = app.moves["st_C"].damage
        m.f2.x = m.f1.x + 60.0
        app.step([keydown(pygame.K_o)])  # 重拳
        for _ in range(30):  # 打到 KO
            app.step([])
            if m.phase == "round_end":
                break
        assert m.phase == "round_end"
        app.step([keyup(pygame.K_o)])  # 真键盘必有抬起;否则 C 常按跨回合
        assert isinstance(app.scene(), FightScene)  # 横幅仍由 Fight 画
        for _ in range(400):  # 演出(KO 慢动作)结束 → 场景切换
            app.step([])
            if not isinstance(app.scene(), FightScene):
                break
        if rnd == 0:
            assert isinstance(app.scene(), RoundIntroScene)  # 自动开下一回合
            for _ in range(RoundIntroScene.INTRO_FRAMES + 2):
                app.step([])
            assert isinstance(app.scene(), FightScene)
    assert isinstance(app.scene(), MatchEndScene)
    app.step([keydown(pygame.K_RETURN)])
    assert isinstance(app.scene(), TitleScene)


# ---------- HUD 像素采样 ----------


def _fresh_fight():
    app = App(vs_ai=False)
    m = Match(app.system, app.moves)
    app.scenes = [FightScene(app, m)]
    app.step([])  # 生成首帧快照
    return app, m


def test_hud_health_bar_full_vs_half():
    app, m = _fresh_fight()
    full = count_color(app.buf, BAR_RECT, HP)
    assert full > BAR_RECT.w * BAR_RECT.h * 0.5  # 满血:条几乎全红
    m.f1.health = app.system.health // 2
    app.step([])
    half = count_color(app.buf, BAR_RECT, HP)
    assert half < full * 0.75  # 半血红像素明显变少
    assert half > full * 0.25


def test_hud_gauge_max_changes_color():
    app, m = _fresh_fight()
    empty = count_color(app.buf, GAUGE_RECT, (250, 200, 60))
    m.f1.gauge = app.system.gauge.max
    app.step([])
    full = count_color(app.buf, GAUGE_RECT, (255, 90, 90))  # MAX 变色
    assert empty == 0  # 空槽时普通能量色一格都没有
    assert full > GAUGE_RECT.w * 3  # 满槽整条 MAX 色


def test_hud_timer_digits_present():
    app, _ = _fresh_fight()
    secs = app.system.round_time_frames // 60
    assert secs >= 10  # 开局两位数
    bright = sum(
        1 for x in range(TIMER_RECT.left, TIMER_RECT.right)
        for y in range(TIMER_RECT.top, TIMER_RECT.bottom)
        if app.buf.get_at((x, y))[0] > 200  # 数字笔画是亮色
    )
    assert bright > 10  # 倒计时数字非空


# ---------- F1 调试框 ----------


def test_f1_debug_boxes_pixels():
    """F1 开启帧新增红/黄/绿描边像素(攻击框/受击框/推挤框)。
    红框取"挥空"的攻击窗:命中后窗口按契约标记已用,不再挂出。"""
    app = App(vs_ai=False)
    m = Match(app.system, app.moves)  # 默认距离 144:st_C 挥空,窗未用
    app.scenes = [FightScene(app, m)]
    app.step([keydown(pygame.K_o)])  # 出重拳
    for _ in range(12):  # 等攻击窗生效(6..8 帧)
        app.step([])
        if m.f1.active_attack() is not None:
            break
    assert m.f1.active_attack() is not None  # 红框必须有东西可画
    before = (count_all(app.buf, (255, 60, 60)),
              count_all(app.buf, (255, 220, 60)),
              count_all(app.buf, (60, 220, 90)))
    app.step([keydown(pygame.K_F1)])
    after = (count_all(app.buf, (255, 60, 60)),
             count_all(app.buf, (255, 220, 60)),
             count_all(app.buf, (60, 220, 90)))
    assert after[0] - before[0] >= 4  # 红:攻击框描边
    assert after[1] - before[1] >= 8  # 黄:双方受击框
    assert after[2] - before[2] >= 8  # 绿:双方推挤框
