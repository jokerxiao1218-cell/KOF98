"""art/stage.py — 美国街头黄昏背景(设计文档 §4.7 / §5.3 A5 契约)。

draw(surface, cam_x):往 320×224 的渲染画面上按摄像机横移画背景。
  * 视差四层:天空(不动,无限远)→ 远楼群(0.5 速)→ 中楼群(0.75 速)
    → 近景(1.0 速:近楼/铁丝网/路灯/地面)——层宽按 320 + 320×速度 预画整条,
    draw 时 blit 窗口,单帧成本 = 4 次 blit;
  * 地面从 y=190 起(system.stage.ground_y,渲染层概念;本模块不 import core,
    数值按设计文档附录 B 写死并注释);
  * 全部确定性绘制(固定间隔/取模公式撒窗撒点,不用随机),同帧必然同图;
  * cam_x 合法域 [0, 320](舞台宽 640 − 画面 320),越界直接 raise 不许静默。
"""
import pygame

VIEW_W, VIEW_H = 320, 224        # 逻辑分辨率
CAM_MAX = 320                    # 摄像机最大横移(舞台 640 − 画面 320)
GROUND_Y = 190                   # 地面起始行(与 system.json stage.ground_y 一致)

_layer_cache = {}


def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _layer(name, builder):
    """层缓存:同层只画一次。"""
    if name not in _layer_cache:
        _layer_cache[name] = builder()
    return _layer_cache[name]


# ---------------------------------------------------------------- 天空(不动层)

def _build_sky():
    """黄昏渐变:顶部暗红棕 → 地平线亮橙;低垂大太阳;几条暗橙云带。"""
    s = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    top = (112, 44, 46)          # 天顶暗红棕(暖)
    horizon = (255, 132, 52)     # 地平线亮橙
    for y in range(VIEW_H):
        t = y / (VIEW_H - 1)
        # 上 3/5 是纯渐变;往下逐渐压暗成远处的城市暮色
        if t < 0.6:
            c = _lerp(top, horizon, t / 0.6)
        else:
            c = _lerp(horizon, (176, 84, 54), (t - 0.6) / 0.4)
        for x in range(VIEW_W):
            s.set_at((x, y), c)
    # 太阳:低垂在地平线上方(cx=252, cy=132)
    cx, cy = 252, 132
    for y in range(cy - 16, cy + 9):
        for x in range(cx - 16, cx + 17):
            dx, dy = x - cx, (y - cy) * 1.15
            r = (dx * dx + dy * dy) ** 0.5
            if r <= 9:
                s.set_at((x, y), (255, 224, 132))        # 日核
            elif r <= 14:
                s.set_at((x, y), (255, 176, 84))         # 日晕
    # 云带:三条水平暗橙条(黄昏卷云)
    for cy2, cx2, cw in ((46, 40, 120), (58, 190, 150), (74, 90, 200)):
        for x in range(cx2, cx2 + cw):
            y = cy2 + (x % 7 == 0)       # 下缘波浪
            s.set_at((x, y), (196, 84, 56))
            s.set_at((x, y + 1), (176, 72, 50))
    return s


# ---------------------------------------------------------------- 远/中楼群

def _build_far():
    """远楼剪影层(480×224,0.5 速):矮楼 + 稀疏亮窗。"""
    w = VIEW_W + CAM_MAX // 2              # 480
    s = pygame.Surface((w, VIEW_H), pygame.SRCALPHA)
    base_y = 150                           # 远楼地平线(被近层压住下半)
    for i, bx in enumerate(range(0, w, 52)):
        bw = 26 + (i * 37) % 22            # 楼宽变化(确定性)
        bh = 34 + (i * 53) % 46            # 楼高变化
        top_y = base_y - bh
        for y in range(top_y, base_y):
            for x in range(bx + (i % 3) * 4, bx + (i % 3) * 4 + bw):
                s.set_at((x, y), (96, 52, 64))
        if i % 4 == 3:                     # 部分楼顶天线
            ax = bx + bw // 2
            for y in range(top_y - 9, top_y):
                s.set_at((ax, y), (96, 52, 64))
        for y in range(top_y + 6, base_y - 4, 8):      # 稀疏亮窗
            for x in range(bx + 5, bx + bw - 4, 7):
                if (x * 31 + y * 17) % 37 < 9:
                    s.set_at((x, y), (255, 180, 90))
                    s.set_at((x + 1, y), (255, 180, 90))
    return s


def _build_mid():
    """中楼剪影层(560×224,0.75 速):更高的楼 + 更密亮窗 + 水塔。"""
    w = VIEW_W + (CAM_MAX * 3) // 4        # 560
    s = pygame.Surface((w, VIEW_H), pygame.SRCALPHA)
    base_y = 188
    for i, bx in enumerate(range(0, w, 64)):
        bw = 34 + (i * 41) % 26
        bh = 60 + (i * 67) % 88
        top_y = base_y - bh
        for y in range(top_y, base_y):
            for x in range(bx, bx + bw):
                s.set_at((x, y), (68, 38, 52))
        if i % 5 == 2:                     # 楼顶水塔
            for y in range(top_y - 8, top_y):
                for x in range(bx + bw // 2 - 4, bx + bw // 2 + 5):
                    s.set_at((x, y), (68, 38, 52))
        for y in range(top_y + 8, base_y - 8, 7):       # 密集亮窗
            for x in range(bx + 4, bx + bw - 4, 6):
                if (x * 29 + y * 13) % 41 < 14:
                    s.set_at((x, y), (255, 196, 110))
                    s.set_at((x, y + 1), (255, 196, 110))
    return s


# ---------------------------------------------------------------- 近景层

def _build_near():
    """近景层(640×224,1.0 速):画面两侧高楼 + 铁丝网围栏 + 路灯 + 地面。"""
    w = VIEW_W + CAM_MAX                    # 640
    s = pygame.Surface((w, VIEW_H), pygame.SRCALPHA)
    # 两侧高楼(进画面才可见,框住擂台)
    for bx, bw in ((0, 76), (560, 80)):
        for y in range(26, GROUND_Y):
            for x in range(bx, bx + bw):
                s.set_at((x, y), (44, 26, 38))
        for y in range(36, 160, 14):        # 大亮窗格
            for x in range(bx + 8, bx + bw - 8, 10):
                if (x + y) % 3:
                    for dy in range(8):
                        for dx in range(5):
                            s.set_at((x + dx, y + dy), (255, 206, 112))
    # 铁丝网围栏(y156..189:竖柱 + 横丝)
    for x in range(96, 552, 32):
        for y in range(156, GROUND_Y):
            s.set_at((x, y), (72, 66, 72))
            s.set_at((x + 1, y), (72, 66, 72))
    for y in (158, 170, 182):
        for x in range(96, 552):
            if (x + y) % 2 == 0:            # 网眼感
                s.set_at((x, y), (58, 54, 60))
    # 路灯 3 根
    for lx in (140, 330, 500):
        for y in range(102, GROUND_Y):
            for dx in range(3):
                s.set_at((lx + dx, y), (52, 46, 56))
        for dy in range(4):                 # 灯头亮块
            for dx in range(7):
                s.set_at((lx - 2 + dx, 98 + dy), (255, 228, 148))
        for r in (3, 5):                    # 淡光晕(半透明)
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 200, 110, 90 if r == 5 else 120), (r, r), r)
            s.blit(glow, (lx + 1 - r, 100 - r), special_flags=pygame.BLEND_RGBA_ADD)
    # 地面:y190..197 人行道(砖缝),198 路缘,199..223 柏油
    for y in range(GROUND_Y, 198):
        for x in range(w):
            s.set_at((x, y), (118, 86, 60))
    for x in range(0, w, 24):              # 人行道砖缝
        for y in range(GROUND_Y, 198):
            s.set_at((x, y), (94, 66, 46))
    for x in range(w):                     # 路缘亮线
        s.set_at((x, 198), (152, 142, 118))
    for y in range(199, VIEW_H):
        for x in range(w):
            s.set_at((x, y), (64, 58, 62))
    for x in range(20, w, 60):             # 柏油白色虚线
        for y in range(208, 212):
            for dx in range(24):
                s.set_at((x + dx, y), (198, 188, 168))
    for y in range(214, 220):              # 井盖
        for x in range(198, 206):
            dx, dy = x - 202, y - 217
            if dx * dx + dy * dy <= 9:
                s.set_at((x, y), (52, 48, 52))
    for x, y in ((90, 204), (260, 218), (420, 202), (560, 216)):  # 裂纹暗点
        s.set_at((x, y), (54, 50, 54))
        s.set_at((x + 1, y), (54, 50, 54))
    return s


# ---------------------------------------------------------------- 对外入口

def draw(surface, cam_x):
    """把背景画进 320×224 的画面;cam_x ∈ [0,320],越界 raise。"""
    cam_x = int(cam_x)
    if cam_x < 0 or cam_x > CAM_MAX:
        raise ValueError(f"cam_x 越界:{cam_x}(合法范围 0~{CAM_MAX})")
    surface.blit(_layer("sky", _build_sky), (0, 0))
    surface.blit(_layer("far", _build_far), (-cam_x // 2, 0))
    surface.blit(_layer("mid", _build_mid), (-(cam_x * 3) // 4, 0))
    surface.blit(_layer("near", _build_near), (-cam_x, 0))
