"""tests/test_integration.py — 端到端验收(batch C,设计文档 §6)。

跑法:cd ~/kof98 && ./test.sh
考卷条目与断言对应:
  * 脚本化人类输入流(含一记 QCF+C 能量波)打 AI:60 秒(3600 帧)内
    回合必有终局(KO 或超时由计时保证),全程无异常,回合内血量单调不增;
  * demo:种子 42/7 AI 自对弈整场(≤3 回合),子进程退出码 0,跨进程可复现;
  * F1 调试开关像素断言在 tests/test_ui.py::test_f1_debug_boxes_pixels
    (考卷记在 test_integration,已一并覆盖,此处不重复跑)。

无头:SDL dummy;事件以 pygame.event.Event 直注(照 sheepandsheep)。
"""
import os
import re
import subprocess
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.ui import App, FightScene, RoundIntroScene  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key})


def keyup(key):
    return pygame.event.Event(pygame.KEYUP, {"key": key})


def test_scripted_human_vs_ai_full_round():
    """人类脚本(搓出 QCF+C 能量波 + 乱按流)真打 AI 一整回合。"""
    app = App()  # vs_ai=True:P2 交给入门 AI
    app.step([keydown(pygame.K_RETURN)])
    for _ in range(RoundIntroScene.INTRO_FRAMES):
        app.step([])
    scene = app.scene()
    assert isinstance(scene, FightScene)
    m = scene.match

    script = []  # QCF+C:↓↓↘→ + O(重拳版能量波,窗口 24/缓冲 10)
    script += [[keydown(pygame.K_s)]] * 4
    script += [[keydown(pygame.K_s), keydown(pygame.K_d)]] * 2
    # 松开下键再保持右:键盘没有"帧设 dirs",必须靠 keyup 才能从 3 走到 6
    script += [[keyup(pygame.K_s), keydown(pygame.K_d)]] * 2
    script.append([keydown(pygame.K_o)])
    # 乱按流:一按一抬不留常按态,方向/跳/四键轮着来(含蹲防/跳跃)
    cycle = [pygame.K_d, pygame.K_d, pygame.K_w, pygame.K_o, pygame.K_i,
             pygame.K_s, pygame.K_u, pygame.K_p]
    script += [[keydown(k), keyup(k)] for k in (cycle[i % 8] for i in range(4200))]

    health = [m.f1.health, m.f2.health]
    saw_projectile = False
    frames = 0
    for evs in script:
        app.step(evs)
        frames += 1
        snap = scene.snap
        if snap is not None:
            if snap.projectiles:
                saw_projectile = True
            for i, fs in enumerate(snap.fighters):
                assert fs.health <= health[i], "回合内血量不许回升"
                health[i] = fs.health
        if m.phase != "fighting":
            break
    assert m.phase != "fighting"  # 60 秒内回合必有终局(计时兜底)
    assert frames <= 3600 + 10  # 战斗帧预算(不含开场白)
    assert saw_projectile  # QCF+C 从键盘一路通到弹体生成,全链路验证


def test_demo_self_play_exit_zero():
    """demo 子进程:AI 自对弈整场,退出码 0,输出含终局信息,≤3 回合。"""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    cmd = [str(REPO / ".venv" / "bin" / "python"),
           str(REPO / "scripts" / "demo.py"), "--no-images"]
    out = []
    for _ in range(2):  # 跑两遍:跨进程结果必须一致(确定性)
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=180, env=env, cwd=str(REPO))
        assert p.returncode == 0, p.stdout + p.stderr
        assert "终局" in p.stdout and "胜者" in p.stdout
        out.append(p.stdout)
    assert out[0] == out[1]  # 同种子两次整局逐字节一致
    m = re.search(r"回合 (\d+)", out[0])
    assert m is not None and int(m.group(1)) <= 3  # 三局两胜最多 3 回合
