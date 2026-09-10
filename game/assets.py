"""assets.py — 素材层(调色板/精灵装配缓存/中文字体链,设计文档 §4.7 / §5.3 A5)。

sprite(pose_key, frame, facing, palette) -> Surface 是渲染唯一入口:
  * 未注册 pose_key → raise;帧号越界 → 对 poses.POSE_KEYS 取模;
  * 按 (键, 帧, 朝向, 调色板标识) 缓存;facing=-1 是 facing=+1 的整幅镜像
    (pygame.transform.flip,与 core.Box.mirrored 的判定语义一致);
  * 人形键(附录 D 全表)→ art/terry.py 纸娃娃装配,统一 56×100 画布
    (脚底=画布底);特效键 → art/fx.py(无朝向/配色概念);
  * 配色:P1 红马甲经典版 / P2 蓝马甲换色版(设计文档 §3,检索核实)。
字体照 sheepandsheep 惯例:内置 OFL 字体相对 __file__ 定位,check_font_health()
渲染"拳"断言宽度,防静默回退成方块。
红线:任何生成的 PNG 一律不 Read 进会话,验收一律像素采样断言。
"""
from pathlib import Path

import pygame
import pygame.freetype as _ft

from game import poses
from game.art import fx, terry

# 调色板:P1 经典红马甲版 / P2 蓝马甲换色版(KOF 惯例的 2P 换色)
PALETTES = {
    "P1": {
        "cap": (196, 32, 32),       # 红帽
        "hair": (240, 208, 112),    # 金发
        "vest": (200, 44, 44),      # 红马甲背心
        "skin": (240, 188, 148),    # 皮肤
        "glove": (212, 52, 52),     # 红拳套
        "pants": (52, 84, 164),     # 蓝色牛仔裤
        "shoe": (208, 48, 48),      # 运动鞋主体红
        "shoe_white": (238, 238, 238),
    },
    "P2": {
        "cap": (44, 88, 196),
        "hair": (240, 208, 112),
        "vest": (52, 96, 196),     # 蓝马甲(2P 换色)
        "skin": (240, 188, 148),
        "glove": (64, 104, 204),
        "pants": (72, 72, 84),
        "shoe": (60, 100, 200),
        "shoe_white": (238, 238, 238),
    },
}


def load_palette(side) -> dict:
    """side: core.types.Side 或 "P1"/"P2" → 调色板 dict;未知直接报错,不许静默。"""
    key = getattr(side, "name", side)
    if key not in PALETTES:
        raise KeyError(f"未知玩家配色 {side!r},可选 {sorted(PALETTES)}")
    return PALETTES[key]


_FX_KEYS = frozenset(fx.FX_KEYS)
_base_cache = {}        # (键, 帧, 调色板标识) -> 朝右基准版
_sprite_cache = {}      # (键, 帧, 朝向, 调色板标识) -> 对外返回版


def sprite(pose_key, frame, facing, palette):
    """POSE 键 + 帧号 + 朝向 + 调色板 → 整帧 Surface(缓存共享)。"""
    if pose_key not in poses.POSE_KEYS:
        raise KeyError(f"未注册的姿势 {pose_key!r}(可用键见 game/poses.py)")
    if isinstance(frame, bool) or not isinstance(frame, int):
        raise TypeError(f"帧号应为整数,得到 {frame!r}")
    if facing not in (1, -1):
        raise ValueError(f"facing 应为 +1(朝右)/ -1(朝左),得到 {facing!r}")
    pal = terry.normalize_palette(palette)      # 缺色/坏色在这里就炸(特效也校验,
    pid = terry.palette_id(pal)                 # 四参数契约不许静默吞参数错)
    f = frame % poses.POSE_KEYS[pose_key]
    if pose_key in _FX_KEYS:                    # 特效:只吃键+帧,不吃配色
        base_key = (pose_key, f, None)
        if base_key not in _base_cache:
            _base_cache[base_key] = fx.get_surface(pose_key, f)
    else:
        base_key = (pose_key, f, pid)
        if base_key not in _base_cache:
            _base_cache[base_key] = terry.assemble(pose_key, f, pal)
    key = (pose_key, f, facing, pid if pose_key not in _FX_KEYS else None)
    if key not in _sprite_cache:
        if facing == 1:
            _sprite_cache[key] = _base_cache[base_key]
        else:                                   # 整幅镜像:与判定框 mirrored() 同轴
            _sprite_cache[key] = pygame.transform.flip(
                _base_cache[base_key], True, False)
    return _sprite_cache[key]


# ---------------------------------------------------------------- 中文字体链
# 字体文件内置(随仓库走,相对本文件定位不依赖 CWD);OFL 协议文本同目录。
# 回退链:项目内置 → 系统 NotoSansCJK 路径 → SysFont(照 sheepandsheep 实测经验:
# pygame 默认字体渲染中文是破碎占位符;SysFont 名字必须带 sc;路径直载最可靠)。

_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONT_PATH = str(_DIR / "ZCOOLKuaiLe-Regular.ttf")
FONT_SYS_FALLBACK_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SYS_FALLBACK = "notosanscjksc"
EMOJI_FONT_PATH = str(_DIR / "NotoEmoji-VF.ttf")

_font_cache = {}
_emoji_cache = {}


def cn_font(size):
    """中文字体(按字号缓存):内置站酷快乐体 → 系统 Noto 路径 → SysFont。"""
    if size not in _font_cache:
        try:
            _font_cache[size] = pygame.font.Font(FONT_PATH, size)
        except (FileNotFoundError, OSError):
            try:
                _font_cache[size] = pygame.font.Font(FONT_SYS_FALLBACK_PATH, size)
            except (FileNotFoundError, OSError):
                _font_cache[size] = pygame.font.SysFont(FONT_SYS_FALLBACK, size)
    return _font_cache[size]


def emoji_font(size):
    """emoji 字体(Noto Emoji 单色,按字号缓存,供 HUD 图案用)。"""
    if size not in _emoji_cache:
        _emoji_cache[size] = _ft.Font(EMOJI_FONT_PATH, size=size)
    return _emoji_cache[size]


def check_font_health(size=32):
    """启动自检:渲染"拳"字宽度必须 >= size*0.7(破碎占位符只有一半不到)。
    不健康直接 raise(带修复指引),绝不静默顶着方块字运行;健康返回 True。"""
    width = cn_font(size).size("拳")[0]
    if width < size * 0.7:
        raise RuntimeError(
            f"中文字体不可用(渲染'拳'宽 {width}px < {size}*0.7):"
            f"项目字体 {FONT_PATH} 缺失或损坏;回退系统字体需安装"
            f" Noto Sans CJK(Ubuntu: sudo apt install fonts-noto-cjk)"
        )
    return True
