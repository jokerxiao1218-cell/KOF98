"""scripts/demo.py — AI 自对弈整局验收(batch C,设计文档 §6 test_integration)。

用法:
  env -u PYTHONPATH SDL_VIDEODRIVER=dummy .venv/bin/python scripts/demo.py
  env -u PYTHONPATH .venv/bin/python scripts/demo.py --no-images  # 不出图,更快

约定:
  * 种子 42(P1)vs 7(P2)——与 ui.AI_SEED 一致;同一对种子整局可复现;
  * 整场 ≤3 回合(三局两胜)打满到 match_end;
  * 退出码:0 = 整局正常结束;1 = 超帧上限仍未终局;2 = 血量不变量被破坏
    (回合内血量只许不增——负伤害/回血都是 bug);
  * 关键帧截图(first hit / 超杀 / KO / 终局)写 scripts/out/(已 gitignore),
    复用 game/ui 的世界+HUD 绘制(同一渲染路径,截图即集成验证)。
"""
from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import ui  # noqa: E402
from game.core import data  # noqa: E402
from game.core import types as T  # noqa: E402
from game.core.ai import TerryAI  # noqa: E402
from game.core.match import Match  # noqa: E402

SEED_P1, SEED_P2 = 42, 7
MAX_FRAMES = 3600 * 3 + 4000  # 三回合×60秒 + 演出/慢动作余量,再超就是卡死
OUT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "out"


def main(argv=None) -> int:
    no_images = "--no-images" in (argv or sys.argv[1:])
    gamedata = data.load_all()
    m = Match(gamedata.system, gamedata.moves)
    a1 = TerryAI(data.load_ai(), gamedata.moves, gamedata.system)
    a2 = TerryAI(dataclasses.replace(data.load_ai(), seed=SEED_P2),
                 gamedata.moves, gamedata.system)

    shots: list = []  # [(标签, 帧, 快照)]
    shot_rounds: set = set()  # 每回合的 KO 演出只截第一帧
    health = [m.f1.health, m.f2.health]
    frames = 0
    seen_hit = False
    seen_super = False

    while m.phase != "match_end":
        if frames >= MAX_FRAMES:
            print(f"异常:超过 {MAX_FRAMES} 帧仍未终局(phase={m.phase})")
            return 1
        if m.phase == "between_rounds":
            m.next_round()
            health = [m.f1.health, m.f2.health]
            continue
        snap = m.step(a1.next_tick(m.ai_view(T.Side.P1)),
                      a2.next_tick(m.ai_view(T.Side.P2)))
        frames += 1

        for i, fs in enumerate(snap.fighters):  # 不变量:回合内血量不增
            if fs.health > health[i]:
                print(f"异常:血量回升 P{i + 1} {health[i]} → {fs.health}")
                return 2
            health[i] = fs.health

        if not seen_hit and min(fs.health for fs in snap.fighters) < gamedata.system.health:
            seen_hit = True
            shots.append(("first_hit", frames, snap))
        if not seen_super and any(
            fs.move_id and fs.move_id.startswith("power_geyser")
            for fs in snap.fighters
        ):
            seen_super = True
            shots.append(("super", frames, snap))
        if (snap.phase == "round_end" and snap.banners
                and snap.round_no not in shot_rounds):
            shot_rounds.add(snap.round_no)
            shots.append((f"round{snap.round_no}_end", frames, snap))
        if m.phase == "match_end":
            shots.append(("final", frames, m.snapshot()))

    print(f"终局:{frames} 帧,回合 {m.round_no},"
          f"P1 {m.wins[T.Side.P1]} : P2 {m.wins[T.Side.P2]}")
    print(f"胜者:{m.match_winner.value if m.match_winner else '无(双满场)'}")
    if m.round_no > 3:
        print(f"异常:回合数 {m.round_no} > 3")
        return 1
    if not no_images:
        _save_shots(shots, m)
    return 0


def _save_shots(shots, match) -> None:
    """关键帧渲染成 PNG(320×224 ×3,与游戏窗口同路径的绘制代码)。"""
    pygame.init()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shim = _DrawShim(match.cfg, match.moves, 0)
    for tag, frame, snap in shots:
        shim.ticks = frame
        buf = pygame.Surface((ui.W, ui.H))
        buf.fill(ui.BG)
        ui._draw_world(buf, shim, snap)
        ui._draw_hud(buf, match.cfg, snap)
        if snap.banners:
            for i, b in enumerate(snap.banners):
                ui.text(buf, b, 26, (255, 210, 70), ui.W / 2, 78 + i * 30,
                        align="center")
        big = pygame.transform.scale(buf, (ui.WIN_W, ui.WIN_H))
        path = OUT_DIR / f"demo_{tag}_f{frame:05d}.png"
        pygame.image.save(big, str(path))
        print(f"截图:{path.name}")


class _DrawShim:
    """给 ui._draw_world/_pose_surface 喂它们要的字段(system/moves/ticks),
    不拉整个 App。"""

    def __init__(self, system, moves, ticks):
        self.system = system
        self.moves = moves
        self.ticks = ticks


if __name__ == "__main__":
    raise SystemExit(main())
