"""art/fx.py — 特效四键(设计文档 §4.7 / §5.3 A5 契约)。

get_surface(key, frame) -> Surface:
  proj_wave  能量波弹体 3 帧(44×28,沿地面滚动,锯齿相位演进)
  fx_geyser  能量喷泉爆发 5 帧(68×92,小柱→喷天→全盛→回落→消散)
  fx_hit     命中火花 2 帧(22×22,星形爆裂→外散)
  fx_block   防御火花 2 帧(20×22,蓝白盾光→碎环)
未注册键直接 raise;帧号取模(与 assets.sprite 同规矩)。
能量系统一橙黄白(KOF98 Power Wave 的暖色),防御系蓝白。

绘制走两条 mota50 纪律:①规则形状用程序画,但先拼成字符画行再交给
art.paint 统一校验(行长不齐/非法字符一样 raise,绝不静默画歪);
②Surface 按 (键,帧) 缓存。特效不吃角色调色板(P1/P2 的波都是橙色)。
"""
import pygame

from . import paint

FX_KEYS = ("proj_wave", "fx_geyser", "fx_hit", "fx_block")

# fx 专用色:暖色能量 + 蓝白防御
_PAL = {
    "o": (255, 150, 50),    # 橙
    "y": (255, 224, 120),   # 亮黄
    "w": (255, 255, 244),   # 白芯
    "d": (168, 76, 30),     # 暗橙(接地/收尾)
    "b": (110, 180, 255),   # 亮蓝
    "B": (40, 90, 230),     # 深蓝
    "c": (210, 240, 255),   # 冰白
}


def _grid(w, h):
    return [["." for _ in range(w)] for _ in range(h)]


def _put(g, x, y, ch):
    """带边界保护的落笔(越界丢弃,生成器不必逐点判断)。"""
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = ch


# ---------------------------------------------------------------- 能量波弹体

def _proj_wave_rows(phase):
    """44×28:竖椭圆波体 + 白芯 + 顶部锯齿尖 + 接地暗橙底带(相位滚动)。"""
    W, H = 44, 28
    g = _grid(W, H)
    for y in range(H):
        for x in range(W):
            dx = (x - 21.5) / 8.0
            dy = (y - 16.0) / 10.0
            r = dx * dx + dy * dy
            if r < 0.30:
                g[y][x] = "w"          # 白芯
            elif r < 0.72:
                g[y][x] = "y"          # 亮黄主体
            elif r < 1.00:
                g[y][x] = "o"          # 橙色外圈
    # 顶部锯齿尖(三枚,随相位左右平移)
    for k in range(3):
        cx = 9 + k * 13 + phase * 3
        for i in range(4):
            _put(g, cx + i, 7 - i, "y" if i < 2 else "o")
            _put(g, cx - i, 7 - i, "o")
    # 两侧飞沫
    for fx, fy in ((4, 12 + phase), (39, 18 - phase), (2, 20)):
        _put(g, fx, fy, "o")
    # 接地底带 + 上缘锯齿
    for x in range(5, 39):
        for y in (25, 26, 27):
            g[y][x] = "d"
        if (x + phase * 2) % 6 < 3:
            g[24][x] = "o"
    # 底带亮斑
    for x in range(9, 36, 4):
        g[26][x] = "o"
    return ["".join(r) for r in g]


# ---------------------------------------------------------------- 能量喷泉

_GEYSER_STAGES = [       # (柱半宽, 柱顶y, 爆发半径, 溅点数, 溅点半径)
    (5, 70, 0, 0, 0),    # 帧0 蓄势小柱
    (8, 50, 9, 8, 14),   # 帧1 喷起
    (13, 26, 18, 18, 22),# 帧2 全盛
    (8, 44, 12, 12, 18), # 帧3 回落
    (3, 62, 5, 6, 12),   # 帧4 消散
]


def _geyser_rows(f):
    """68×92:底部喷柱 + 顶部爆发团 + 四溅能量点(逐帧涨落)。"""
    W, H = 68, 92
    half, top, burst, dots, dot_r = _GEYSER_STAGES[f]
    cx = W // 2
    g = _grid(W, H)
    # 柱体:从画布底喷到 top
    for y in range(H - 1, top - 1, -1):
        depth = (H - 1 - y) / max(1, H - 1 - top)     # 0 顶 → 1 底
        w = half + int(depth * 2)
        for x in range(cx - w, cx + w + 1):
            t = (x - cx) / (w + 1)
            if abs(t) < 0.35:
                ch = "w" if depth < 0.5 else "y"
            elif abs(t) < 0.8:
                ch = "y"
            else:
                ch = "o"
            _put(g, x, y, ch)
    # 顶部爆发团
    if burst:
        for y in range(top - burst, top + burst // 2):
            for x in range(cx - burst, cx + burst + 1):
                dx = (x - cx) / (burst + 0.5)
                dy = (y - top) / (burst * 0.8 + 0.5)
                r = dx * dx + dy * dy
                if r < 0.22:
                    g[y][x] = "w"
                elif r < 0.62:
                    g[y][x] = "y"
                elif r < 1.0:
                    g[y][x] = "o"
    # 四溅能量点(确定性散布,不用随机)
    for i in range(dots):
        ang = i * 2.399963            # 黄金角,散得开
        rr = dot_r + (i % 3) * 3
        px = int(cx + rr * __import__("math").cos(ang))
        py = int(top + 6 - rr * abs(__import__("math").sin(ang)))
        _put(g, px, py, "y" if i % 2 else "o")
        _put(g, px + 1, py - 1, "o")
    return ["".join(r) for r in g]


# ---------------------------------------------------------------- 命中/防御火花

def _hit_rows(f):
    """22×22:帧0 八向星形爆裂(白芯黄臂橙缘);帧1 外散碎点。"""
    W, H = 22, 22
    g = _grid(W, H)
    cx = cy = 11
    if f == 0:
        for k in range(8):                 # 八条辐射臂
            ang = k * 0.7853981634
            for i in range(3, 10):
                x = int(cx + i * __import__("math").cos(ang))
                y = int(cy + i * __import__("math").sin(ang))
                _put(g, x, y, "y" if i < 7 else "o")
        for y in range(8, 15):             # 白芯
            for x in range(8, 15):
                dx, dy = x - 11, y - 11
                if dx * dx + dy * dy < 8:
                    g[y][x] = "w"
        for x, y in ((4, 4), (17, 4), (4, 17), (17, 17)):  # 对角橙点
            _put(g, x, y, "o")
    else:
        for k in range(8):                 # 外圈碎点
            ang = k * 0.7853981634 + 0.3926991
            for i in (8, 9):
                x = int(cx + i * __import__("math").cos(ang))
                y = int(cy + i * __import__("math").sin(ang))
                _put(g, x, y, "o")
        for y in range(10, 13):            # 残留小黄芯
            for x in range(10, 13):
                g[y][x] = "y"
    return ["".join(r) for r in g]


def _block_rows(f):
    """20×22:帧0 蓝白竖盾光;帧1 外扩碎环。"""
    W, H = 20, 22
    g = _grid(W, H)
    cx, cy = 10, 11
    if f == 0:
        for y in range(H):
            for x in range(W):
                dx = (x - cx) / 6.5
                dy = (y - cy) / 9.5
                r = dx * dx + dy * dy
                if r < 0.35:
                    g[y][x] = "c"
                elif r < 0.80:
                    g[y][x] = "b"
                elif r < 1.00:
                    g[y][x] = "B"
        for i in range(4):                 # 竖向亮条(盾面高光)
            _put(g, cx - 1, 5 + i * 4, "w")
            _put(g, cx + 1, 5 + i * 4, "w")
    else:
        for k in range(10):                # 外扩碎点环
            ang = k * 0.6283185
            for i, ch in ((8, "b"), (9, "B")):
                x = int(cx + i * __import__("math").cos(ang))
                y = int(cy + i * __import__("math").sin(ang) * 1.2)
                _put(g, x, y, ch)
        _put(g, cx, cy, "c")               # 残留冰白点
    return ["".join(r) for r in g]


# 形状注册表(帧数与 poses.POSE_KEYS 的特效键一致,键名冻结)
FX_SHAPES = {
    "proj_wave": [_proj_wave_rows(0), _proj_wave_rows(1), _proj_wave_rows(2)],
    "fx_geyser": [_geyser_rows(f) for f in range(5)],
    "fx_hit": [_hit_rows(0), _hit_rows(1)],
    "fx_block": [_block_rows(0), _block_rows(1)],
}


_cache = {}


def get_surface(key, frame):
    """特效键 + 帧号 → Surface(帧号取模;未注册键直接 raise)。"""
    if key not in FX_SHAPES:
        raise KeyError(f"未注册的特效 {key!r}(可用:{list(FX_KEYS)})")
    frames = FX_SHAPES[key]
    f = frame % len(frames)
    ck = (key, f)
    if ck not in _cache:
        _cache[ck] = paint(f"fx:{key}:{f}", frames[f], _PAL)
    return _cache[ck]
