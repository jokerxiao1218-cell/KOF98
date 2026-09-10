"""scripts/ascii_pose.py — 纸娃娃姿势的 ASCII 过目工具(batch F 加帧评审用)。

像素 → 字符:色反查 normalize_palette 的单字符色表(帽子c/C、发h/H、
皮肤s/S、马甲v/V、拳套g/G、裤p/P、鞋r/W…,全集见 game/art/terry_base.py
的 docstring),透明 = '.',反查不到 = '?';一帧 56 行文本,直接在终端看。
红线:任何 PNG 不进 AI 会话——想看姿势长相,用本工具,不开图。

用法(在仓库根目录):
  env -u PYTHONPATH .venv/bin/python scripts/ascii_pose.py walk st_A
  env -u PYTHONPATH .venv/bin/python scripts/ascii_pose.py          # 全部人形姿势(很长)
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import assets, poses  # noqa: E402
from game.art import terry  # noqa: E402


def render(key, frame):
    """一帧 → 56 行字符画(每行 56 字符,行号 0 起,脚底在最后几行)。"""
    base_pal = assets.load_palette("P1")
    pal = terry.normalize_palette(base_pal)
    inv = {}
    for ch, rgb in pal.items():
        if len(ch) == 1:                     # 单字符色才进表;撞色留先到者
            inv.setdefault(tuple(rgb), ch)
    s = assets.sprite(key, frame, 1, base_pal)
    w, h = s.get_size()
    rows = []
    for y in range(h):
        rows.append("".join(
            "." if s.get_at((x, y))[3] < 128
            else inv.get(tuple(s.get_at((x, y))[:3]), "?")
            for x in range(w)))
    return rows


def main():
    keys = sys.argv[1:]
    if not keys:
        keys = [k for k in sorted(poses.POSE_KEYS) if k in terry.POSES]
    bad = [k for k in keys if k not in poses.POSE_KEYS]
    if bad:
        sys.exit(f"未注册姿势 {bad}(可用键见 game/poses.py)")
    for key in keys:
        n = poses.POSE_KEYS[key]
        for f in range(n):
            print(f"===== {key} 第{f}/{n}帧(上=头顶,下=画布底)=====")
            print("\n".join(render(key, f)))


if __name__ == "__main__":
    main()
