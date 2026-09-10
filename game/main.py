"""game/main.py — 入口(双跑法样板:mota50/sheepandsheep 同款)。

batch 0 为骨架占位:先过数据校验再拉起空窗;batch B 换成真正的 App/ui。
"""
import sys
from pathlib import Path

if __package__ in (None, ""):  # 兼容 `python game/main.py` 直接跑
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from game.core import data


def main() -> int:
    # 数据先于窗口加载:三份 JSON 校验失败在这里就明确报错退出(不许静默)
    gamedata = data.load_all()

    pygame.init()
    cfg = gamedata.system
    size = (cfg.view.w * cfg.view.scale, cfg.view.h * cfg.view.scale)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("拳皇98复刻·特瑞篇")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
        screen.fill((12, 12, 16))
        pygame.display.flip()
        clock.tick(60)  # 逻辑帧锁 60fps(设计文档 §4.1 选择 2)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
