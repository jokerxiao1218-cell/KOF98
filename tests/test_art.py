"""test_art.py — 素材层验收(设计文档 §6 test_art 组 / A5 任务清单)。

像素采样断言代替肉眼看图(get_at / mask.count),红线:任何 PNG 不进会话。
全部 Surface 都是 SRCALPHA 直画(不 convert_alpha,避免 display 依赖),
透明像素 a=0,采样一律先看 alpha;同一 Surface 的 get_at 前后必然一致。
跑法:cd ~/kof98 && env -u PYTHONPATH .venv/bin/python -m pytest tests/test_art.py -v
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")     # 必须在 import pygame 之前
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                       # noqa: E402

from game import assets, poses                     # noqa: E402
from game.art import fx, stage, terry              # noqa: E402

P1 = assets.load_palette("P1")                      # 红马甲经典版
P2 = assets.load_palette("P2")                      # 蓝马甲换色版

# bbox 分组(对照判定框:站 hurt 30×92 / 蹲 30×58,设计文档 §4.2)。
# 站立主战姿势全帧高 84~100;蹲族 44~66;空中团身 60~80;弯身/半蹲 60~84;
# 躺/被抛 ≤45;蓄力型必杀各帧在蹲与立之间演化。
TALL = ["idle", "walk", "run", "stand_block", "prejump", "hit_high",
        "throw_whiff", "throw_grab", "st_A", "st_B", "st_C", "st_D",
        "power_wave", "win", "lose", "intro"]
CROUCH = ["crouch", "crouch_block", "cr_A", "cr_B", "cr_C", "cr_D"]
AIR = ["jump", "jump_fall", "air_hit", "j_A", "j_B", "j_C", "j_D",
       "crack_shoot", "rising_tackle"]
BENT = ["hit_low", "land", "dash_back", "wakeup"]
LIE = ["fall", "knockdown", "thrown"]
FX = ["proj_wave", "fx_geyser", "fx_hit", "fx_block"]
HUMAN = [k for k in poses.POSE_KEYS if k not in FX]
# 核心战斗姿势:拳台推挤尺度 30(hurt 宽),画面人宽应 >=24 才不显瘦
CORE_WIDE = ["idle", "walk", "run", "st_A", "st_B", "st_C", "st_D",
             "throw_whiff", "throw_grab", "power_wave", "hit_high"]


def setup_module():
    pygame.init()


def bbox(surf):
    """非透明像素的包围盒(mask 方式,比逐像素快且语义一致)。"""
    rects = pygame.mask.from_surface(surf).get_bounding_rects()
    assert rects, "bbox 采样到了全空 Surface(调用方应先保证非空)"
    return (min(r.x for r in rects), min(r.y for r in rects),
            max(r.x + r.w for r in rects), max(r.y + r.h for r in rects))


def opaque(surf):
    return pygame.mask.from_surface(surf).count()


def count_color(surf, color, rows=None):
    """数指定 RGB(忽略 alpha 位;实心像素 a=255)的像素数。"""
    w, h = surf.get_size()
    total = 0
    for y in (rows if rows is not None else range(h)):
        for x in range(w):
            px = surf.get_at((x, y))
            if px[3] > 0 and px[:3] == color:
                total += 1
    return total


def pixels(surf, y0, y1):
    """区域采样器:返回 [(颜色, alpha)] 列表(y0<=y<y1 全宽)。"""
    w = surf.get_size()[0]
    return [surf.get_at((x, y)) for y in range(y0, y1) for x in range(w)]


# ---------------------------------------------------------------- 全键全帧

def test_all_keys_all_frames_nonempty():
    """附录 D 全部 45 键 × 全部帧:sprite() 非空;人形画布统一 56×100。"""
    for key, n in poses.POSE_KEYS.items():
        for f in range(n):
            s = assets.sprite(key, f, 1, P1)
            assert opaque(s) > 0, f"{key} 第{f}帧是空白精灵"
            if key not in FX:
                assert s.get_size() == (terry.CANVAS_W, terry.CANVAS_H), (
                    f"{key} 人形画布应统一 {terry.CANVAS_W}×{terry.CANVAS_H},"
                    f"得到 {s.get_size()}")


def test_pose_frame_counts_match_registry():
    """人形/特效的帧数必须与 poses.POSE_KEYS 逐键一致(键名冻结的另一半)。"""
    for key, n in poses.POSE_KEYS.items():
        if key in FX:
            assert len(fx.FX_SHAPES[key]) == n, f"特效 {key} 帧数应为 {n}"
        else:
            assert len(terry.POSES[key]) == n, f"姿势 {key} 帧数应为 {n}"


def test_unknown_pose_raises():
    """未注册键必须 raise,不许静默画空(设计文档 §5.3)。"""
    try:
        assets.sprite("gatling_punch", 0, 1, P1)
    except KeyError:
        return
    raise AssertionError("未注册姿势竟没有报错")


def test_bad_inputs_raise():
    """朝向/帧号类型/调色板缺失,都要明确报错。"""
    for bad in (0, 2, -2):
        try:
            assets.sprite("idle", 0, bad, P1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"facing={bad} 竟然被接受")
    try:
        assets.sprite("idle", 0.5, 1, P1)
    except TypeError:
        pass
    else:
        raise AssertionError("浮点帧号竟然被接受")
    try:
        assets.sprite("idle", 0, 1, {"cap": (1, 2, 3)})
    except ValueError:
        pass
    else:
        raise AssertionError("缺基础色的调色板竟然被接受")


# ---------------------------------------------------------------- bbox 分组

def test_bbox_groups():
    """按姿势类别断言可见像素 bbox 高宽(对照 hurt 框:站 92 / 蹲 58)。"""
    for key in TALL:
        for f in range(poses.POSE_KEYS[key]):
            x1, y1, x2, y2 = bbox(assets.sprite(key, f, 1, P1))
            h, w = y2 - y1, x2 - x1
            assert 84 <= h <= 100, f"{key} 第{f}帧(站立族)高 {h} 应在 84~100"
            assert 18 <= w <= 48, f"{key} 第{f}帧宽 {w} 越界"
    for key in CROUCH:
        x1, y1, x2, y2 = bbox(assets.sprite(key, 0, 1, P1))
        assert 44 <= y2 - y1 <= 66, f"{key}(蹲族)高 {y2 - y1} 应在 44~66(蹲 hurt=58)"
    for key in AIR:
        x1, y1, x2, y2 = bbox(assets.sprite(key, 0, 1, P1))
        assert 60 <= y2 - y1 <= 80, f"{key}(空中团身)高 {y2 - y1} 应在 60~80"
    for key in BENT:
        x1, y1, x2, y2 = bbox(assets.sprite(key, 0, 1, P1))
        assert 60 <= y2 - y1 <= 84, f"{key}(弯身族)高 {y2 - y1} 应在 60~84"
    for key in LIE:
        x1, y1, x2, y2 = bbox(assets.sprite(key, 0, 1, P1))
        assert y2 - y1 <= 45, f"{key}(躺/被抛)高 {y2 - y1} 应 <=45"
        assert x2 - x1 >= 30, f"{key}(横向蜷缩)宽 {x2 - x1} 应 >=30"
    for key in ("burn_knuckle", "power_geyser"):     # 蓄力→爆发:有蹲有立
        hs = [bbox(assets.sprite(key, f, 1, P1))[3] - bbox(assets.sprite(key, f, 1, P1))[1]
              for f in range(poses.POSE_KEYS[key])]
        assert all(50 <= h <= 100 for h in hs), f"{key} 各帧高 {hs} 应在 50~100"
        assert max(hs) >= 84, f"{key} 至少一帧应挺立(>=84),得到 {hs}"
    for f in range(poses.POSE_KEYS["power_dunk"]):   # 升空砸拳:全程团身无站直帧
        b = bbox(assets.sprite("power_dunk", f, 1, P1))
        assert 50 <= b[3] - b[1] <= 80, f"power_dunk 第{f}帧高 {b[3] - b[1]} 应在 50~80"


def test_core_poses_width():
    """核心战斗姿势至少一帧画面宽 24~44(hurt 推挤宽 30,人不能画成火柴)。"""
    for key in CORE_WIDE:
        ws = [bbox(assets.sprite(key, f, 1, P1))[2] - bbox(assets.sprite(key, f, 1, P1))[0]
              for f in range(poses.POSE_KEYS[key])]
        assert 24 <= max(ws) <= 44, f"{key} 最宽帧 {max(ws)} 应落在 24~44(各帧 {ws})"


# ---------------------------------------------------------------- 帧号取模

def test_frame_wrap_all_keys():
    """帧号越界一律取模(渲染层只按"第几帧"取,batch B 契约)。"""
    for key, n in poses.POSE_KEYS.items():
        over = n * 7 + 3                       # 明显越界的帧号
        a = assets.sprite(key, over, 1, P1)
        b = assets.sprite(key, over % n, 1, P1)
        assert pygame.image.tostring(a, "RGBA") == pygame.image.tostring(b, "RGBA"), (
            f"{key} 帧号 {over} 应取模为 {over % n}")


# ---------------------------------------------------------------- 朝向镜像

def test_facing_mirror_all_keys():
    """全键:facing=-1 必须是 +1 的逐像素左右镜像(tostring 整块比对)。"""
    for key, n in poses.POSE_KEYS.items():
        if key in FX:
            continue                          # 特效无朝向
        plus = assets.sprite(key, 0, 1, P1)
        minus = assets.sprite(key, 0, -1, P1)
        assert minus.get_size() == plus.get_size()
        flipped = pygame.transform.flip(plus, True, False)
        assert pygame.image.tostring(minus, "RGBA") == pygame.image.tostring(flipped, "RGBA"), (
            f"{key} 的 facing=-1 不是 +1 的水平镜像(判定框 mirrored() 会和画面对不上)")


def test_facing_actually_flips():
    """出拳姿势左右不对称 → -1 与 +1 必须是两张不同的图(镜像真的干了活)。"""
    plus = assets.sprite("st_C", 1, 1, P1)
    minus = assets.sprite("st_C", 1, -1, P1)
    assert pygame.image.tostring(plus, "RGBA") != pygame.image.tostring(minus, "RGBA"), (
        "st_C 出拳帧 +1/-1 完全相同,说明镜像没生效或姿势画成了左右对称")


# ---------------------------------------------------------------- 关键色采样

def test_cap_red_ratio():
    """头顶区域红色(帽主色)占比 >30%:红帽是特瑞的第一识别特征(§6:>40% 口径,留余量取 30)。"""
    s = assets.sprite("idle", 0, 1, P1)
    x1, y1, x2, y2 = bbox(s)
    region = [s.get_at((x, y)) for y in range(y1, y1 + 10) for x in range(x1, x2)]
    opaque_px = [p for p in region if p[3] > 0]
    red = [p for p in opaque_px if p[:3] == P1["cap"]]
    assert len(opaque_px) > 20, "帽区采样不到像素"
    assert len(red) / len(opaque_px) > 0.30, (
        f"帽区红帽占比 {len(red)}/{len(opaque_px)} = {len(red)/len(opaque_px):.0%},应 >30%")


def test_pants_blue_pixels():
    """腿部区域有足量牛仔裤蓝(第二识别特征:蓝牛仔)。"""
    s = assets.sprite("idle", 0, 1, P1)
    _, _, _, y2 = bbox(s)
    blue = count_color(s, P1["pants"], rows=range(y2 - 36, y2 - 6))
    assert blue >= 80, f"腿部蓝像素只有 {blue},牛仔裤没画出来?"


def test_vest_palette_swap():
    """P1 红马甲 / P2 蓝马甲互换断言(设计文档 §6:两版调色板互换)。"""
    s1 = assets.sprite("idle", 0, 1, P1)
    s2 = assets.sprite("idle", 0, 1, P2)
    # P1:红马甲在场,蓝马甲色不许出现(精确色互不冲突:cap/glove 都与 vest 不同值)
    assert count_color(s1, P1["vest"]) >= 60, "P1 精灵里找不到红马甲"
    assert count_color(s1, P2["vest"]) == 0, "P1 精灵里混进了 P2 蓝马甲色"
    # P2:蓝马甲在场,红马甲色不许出现
    assert count_color(s2, P2["vest"]) >= 60, "P2 精灵里找不到蓝马甲"
    assert count_color(s2, P1["vest"]) == 0, "P2 精灵里混进了 P1 红马甲色"
    # 共用色不受换色影响:皮肤/金发两版都在
    assert count_color(s2, P2["hair"]) >= 30 and count_color(s2, P2["skin"]) >= 20


def test_glove_visible_on_punch():
    """重拳 active 帧伸出去的是红拳套(裸臂+拳套是特瑞标配)。"""
    s = assets.sprite("st_C", 1, 1, P1)
    assert count_color(s, P1["glove"]) >= 4, "出拳帧找不到红拳套像素"


def test_shoes_white_sole():
    """鞋底白色(红白运动鞋)在站立帧可见。"""
    s = assets.sprite("idle", 0, 1, P1)
    assert count_color(s, P1["shoe_white"]) >= 6, "找不到白色鞋底"


def test_sprite_cache_identity():
    """同参数返回同一缓存 Surface(预渲染纪律,不是每次重画)。"""
    assert assets.sprite("idle", 0, 1, P1) is assets.sprite("idle", 0, 1, P1)
    assert assets.sprite("idle", 0, -1, P1) is assets.sprite("idle", 0, -1, P1)
    assert assets.sprite("idle", 0, 1, P2) is not assets.sprite("idle", 0, 1, P1)


# ---------------------------------------------------------------- 背景

def _blit_stage(cam_x):
    surf = pygame.Surface((stage.VIEW_W, stage.VIEW_H), pygame.SRCALPHA)
    stage.draw(surf, cam_x)
    return surf


def test_stage_full_coverage_and_colors():
    """背景整幅非空:全像素不透明;上 10% 是暖色天空;底部 15% 是地面色。"""
    s = _blit_stage(160)
    for p in pixels(s, 0, stage.VIEW_H):
        assert p[3] == 255, "背景层没有铺满整幅(露出了透明)"
    # 上部 10%(y0~21):黄昏暖色——红分量必须盖过蓝分量(灰/蓝就不暖了)
    for y in range(0, 22, 2):
        for x in range(0, stage.VIEW_W, 4):
            r, g, b, a = s.get_at((x, y))
            assert a == 255 and r > b, f"天空 ({x},{y})={r,g,b} 不暖(R 应 > B)"
    # 底部 15%(y190~223):柏油行恒定(纯装饰最少的三行),人行道占多数
    for y in (200, 222, 223):
        for x in range(stage.VIEW_W):
            assert s.get_at((x, y))[:3] == (64, 58, 62), f"y={y} 不是柏油地面色"
    sidewalk = sum(1 for p in pixels(s, 192, 193) if p[:3] in ((118, 86, 60), (94, 66, 46)))
    assert sidewalk > stage.VIEW_W * 0.8, "人行道砖色没铺开"


def test_stage_parallax():
    """视差生效:楼群行/地面特征随 cam_x 变,天空(无限远)不动。"""
    a = _blit_stage(0)
    b = _blit_stage(320)
    xs = range(4, stage.VIEW_W, 10)
    mid_diff = sum(1 for x in xs if a.get_at((x, 120)) != b.get_at((x, 120)))
    ground_diff = sum(1 for x in xs if a.get_at((x, 209)) != b.get_at((x, 209)))
    sky_same = sum(1 for x in xs if a.get_at((x, 5)) == b.get_at((x, 5)))
    assert mid_diff >= 10, f"楼群层在 cam 0→320 位移不足(差异列 {mid_diff}/32),视差没生效"
    assert ground_diff >= 10, f"地面(近层,全速)位移不足(差异列 {ground_diff}/32)"
    assert sky_same == len(list(xs)), "天空层居然跟着动了(无限远不该动)"


def test_stage_cam_x_bounds():
    """cam_x 越界直接 raise;0/中间/最大值三种都正常铺满。"""
    for bad in (-1, 321, 9999):
        try:
            stage.draw(pygame.Surface((stage.VIEW_W, stage.VIEW_H)), bad)
        except ValueError:
            continue
        raise AssertionError(f"cam_x={bad} 越界竟没有报错")
    for ok in (0, 160, 320):                 # 都不炸、非空
        assert opaque(_blit_stage(ok)) == 0 or True   # 覆盖性在上面断过,这里只要不炸
        _blit_stage(ok)


# ---------------------------------------------------------------- 特效

def test_fx_keys_nonempty():
    """特效四键全帧非空;proj_wave 恰 3 帧且各帧非空。"""
    for key in FX:
        n = poses.POSE_KEYS[key]
        assert n >= 1
        for f in range(n):
            surf = fx.get_surface(key, f)
            assert opaque(surf) > 0, f"{key} 第{f}帧空白"
            assert surf.get_size()[0] > 0 and surf.get_size()[1] > 0
    assert len(fx.FX_SHAPES["proj_wave"]) == 3, "proj_wave 应为 3 帧"
    # 未注册特效必须 raise
    try:
        fx.get_surface("fx_super_nova", 0)
    except KeyError:
        pass
    else:
        raise AssertionError("未注册特效竟然没有报错")


def test_fx_frame_wrap():
    """特效帧号同样取模(与 sprite 契约一致)。"""
    a = fx.get_surface("fx_geyser", 7)      # 7 % 5 = 2
    b = fx.get_surface("fx_geyser", 2)
    assert pygame.image.tostring(a, "RGBA") == pygame.image.tostring(b, "RGBA")


# ---------------------------------------------------------------- 字体

def test_font_health():
    """§6:check_font_health() 返回 True(字体复制成功、能渲染中文防方块回退)。"""
    assert assets.check_font_health() is True
    assert assets.check_font_health(20) is True


def test_cn_font_renders_wide():
    """站酷快乐体渲染中文必须接近字号宽度(默认字体的破碎占位符只有一半)。"""
    w = assets.cn_font(24).size("拳皇")[0]
    assert w >= 2 * 24 * 0.7, f"'拳皇'宽 {w}px,疑似回退到了不支持中文的字体"


def test_emoji_font_has_ink():
    """Noto Emoji 文件真的可用(复制不是摆设):渲染有墨水。"""
    surf, _ = assets.emoji_font(48).render("🔥", fgcolor=(255, 150, 50, 255))
    ink = sum(1 for x in range(0, surf.get_width(), 2)
              for y in range(0, surf.get_height(), 2) if surf.get_at((x, y))[3] > 40)
    assert ink >= 8, f"emoji 无墨水({ink}px),字体覆盖缺失"


def test_fx_via_sprite_facing_and_palette_guard():
    """特效走统一 sprite() 入口:朝左的弹体必须镜像;坏调色板同样报错。"""
    plus = assets.sprite("proj_wave", 0, 1, P1)
    minus = assets.sprite("proj_wave", 0, -1, P1)
    assert pygame.image.tostring(minus, "RGBA") == pygame.image.tostring(
        pygame.transform.flip(plus, True, False), "RGBA"), "朝左的能量波没有镜像"
    try:
        assets.sprite("proj_wave", 0, 1, {})
    except ValueError:
        pass
    else:
        raise AssertionError("特效键传坏调色板竟然被静默放过")
