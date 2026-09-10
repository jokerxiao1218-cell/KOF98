"""assets.py — 素材层(调色板/字体/精灵缓存)。

batch 0 只冻结调色板结构;像素纸娃娃装配由并行组 A5 实现(设计文档 §4.7)。
A5 需提供的渲染入口(契约):
    sprite(pose_key, frame, facing, palette) -> Surface,按 (键,帧,朝向,配色) 缓存。
红线:任何生成的 PNG 一律不 Read 进会话,验收一律像素采样断言(设计文档 §4.7)。
配色依据设计文档 §3(特瑞经典配色已检索核实:红帽/金发/红马甲/蓝牛仔/红白鞋)。
"""


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
