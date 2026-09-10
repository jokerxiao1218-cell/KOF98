"""scripts/sprite_check.py — 真贴图体检(素材系统 v2,设计文档 §11.2A)。

用法:
  .venv/bin/python scripts/sprite_check.py                 # 校验+覆盖表+预览图
  .venv/bin/python scripts/sprite_check.py --probe a.png   # 探测 sheet 网格建议
  .venv/bin/python scripts/sprite_check.py --colors a.png  # 主色榜(配 swap_p2)

退出码:0 = 通过(或尚未安装真图,如实提示);1 = manifest/贴图有错。
预览图写 scripts/out/sprite_preview.png,给你过目用(绝不让机器人读图,
红线照旧)。把 manifest 模板从 scripts/manifest.example.json 复制到
game/sprites/terry/manifest.json 起步。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "scripts" / "out"

import pygame  # noqa: E402

from game import poses, sprites  # noqa: E402

FX_KEYS = ("proj_wave", "fx_geyser", "fx_hit", "fx_block")


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) == 2 and args[0] == "--probe":
        return probe(REPO / args[1])
    if len(args) == 2 and args[0] == "--colors":
        return colors(REPO / args[1])

    reg = sprites.RealSprites()
    try:
        reg.load()
    except sprites.SpriteError as e:
        print(f"✗ {e}")
        return 1
    if not reg.pose_keys():
        print("未安装真图(game/sprites/terry/ 无 manifest)——当前全程序绘制。")
        print("放图后从 scripts/manifest.example.json 复制模板开始配置。")
        return 0

    print(f"已配置真图姿势 {len(reg.pose_keys())} 个,覆盖表:")
    real = missing = 0
    for key in poses.POSE_KEYS:
        if key in FX_KEYS:
            continue  # 特效永远程序绘制
        if reg.has(key):
            real += 1
            print(f"  真图 {key:<16} {reg.frame_count(key)} 帧")
        else:
            missing += 1
            print(f"  回退 {key:<16} {poses.POSE_KEYS[key]} 帧(程序绘制)")
    print(f"合计:真图 {real} / 回退 {missing}(特效 4 键固定程序绘制)")
    path = preview(reg)
    print(f"预览图:{path}(请打开过目:切格、朝向、锚点对不对)")
    return 0


def preview(reg) -> Path:
    """全部真图帧渲染成 contact sheet(标签:姿势名+帧号)。"""
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    keys = reg.pose_keys()
    cell_w = max(reg.surface(k, f, 1, "P1").get_width()
                 for k in keys for f in range(reg.frame_count(k)))
    cell_h = max(reg.surface(k, f, 1, "P1").get_height()
                 for k in keys for f in range(reg.frame_count(k)))
    pad, label_h = 6, 14
    from game import assets  # 标签字体
    rows = [(k, reg.frame_count(k)) for k in keys]
    h = pad + sum(label_h + cell_h + pad for _ in rows)
    w = pad + max(n for _, n in rows) * (cell_w + pad)
    sheet = pygame.Surface((w, h))
    sheet.fill((24, 22, 30))
    y = pad
    for key, n in rows:
        img = assets.cn_font(11).render(key, True, (220, 216, 200))
        sheet.blit(img, (pad, y))
        y += label_h
        for f in range(n):
            s = reg.surface(key, f, 1, "P1")
            sheet.blit(s, (pad + f * (cell_w + pad), y + cell_h - s.get_height()))
        y += cell_h + pad
    path = OUT / "sprite_preview.png"
    pygame.image.save(sheet, str(path))
    return path


def probe(png_path) -> int:
    """按背景色探测网格:全背景的行/列 → 空隙 → 建议切格参数。"""
    if not png_path.is_file():
        print(f"✗ 文件不存在:{png_path}")
        return 1
    pygame.init()
    img = pygame.image.load(str(png_path)).convert_alpha()
    w, h = img.get_size()
    bg = img.get_at((0, 0))

    # 背景列/行(整行整列都是背景色) → 连续段 = 格子边界
    cols = [x for x in range(w) if all(img.get_at((x, y))[:3] == bg[:3]
                                      for y in range(h))]
    rows = [y for y in range(h) if all(img.get_at((x, y))[:3] == bg[:3]
                                      for x in range(w))]
    def runs(idx, total):
        idx_set = set(idx)
        out = []
        s = None
        for i in range(total):
            blank_here = i in idx_set
            if blank_here and s is None:
                s = i
            elif not blank_here and s is not None:
                out.append((s, i - 1))
                s = None
        if s is not None:
            out.append((s, total - 1))
        return out

    col_runs = runs(cols, w)
    row_runs = runs(rows, h)
    cells_x = [r for r in col_runs if r[1] - r[0] < w // 2]  # 空隙段(太宽=留白不算)
    cells_y = [r for r in row_runs if r[1] - r[0] < h // 2]
    if not cells_x and not cells_y:
        print("没探测出背景空隙——sheet 可能是无间隔排布或背景不纯净。")
        print("请人工数格:总宽÷列数=fw,总高÷行数=fh,填进 manifest。")
        return 1
    fw = w // max(len(cells_x) + 1, 1)
    fh = h // max(len(cells_y) + 1, 1)
    count = (w // fw if fw else 0) * (h // fh if fh else 0)
    print(f"图幅 {w}×{h},背景 {tuple(bg[:3])}")
    print(f"猜测:fw={fw} fh={fh} 每行 {w // fw if fw else '?'} 格,"
          f"每列 {h // fh if fh else '?'} 格,共约 {count} 格")
    print(f"建议 strip:{{\"count\":{count}, \"fw\":{fw}, \"fh\":{fh},"
          f" \"ax\":{fw // 2}, \"ay\":{fh}}}")
    print("(ax/ay 是脚底中心,请对照预览图微调;切完跑本脚本看预览)")
    return 0


def colors(png_path) -> int:
    """主色榜:配 swap_p2 换色 LUT 用(挑红系换蓝系)。"""
    if not png_path.is_file():
        print(f"✗ 文件不存在:{png_path}")
        return 1
    pygame.init()
    img = pygame.image.load(str(png_path)).convert_alpha()
    cnt = Counter()
    for x in range(img.get_width()):
        for y in range(img.get_height()):
            p = img.get_at((x, y))
            if p[3] > 0:
                cnt[(p[0], p[1], p[2])] += 1
    print(f"非透明色 {len(cnt)} 种,前 15:")
    for rgb, n in cnt.most_common(15):
        print(f"  {rgb} × {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
