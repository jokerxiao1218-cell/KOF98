"""POSE 注册表——素材键名与姿势帧数(设计文档附录 D)。

纪律:键名冻结,并行组 A5 只许微调各键的"帧姿势数",不许增删键名;
招式 → 姿势的对应由 terry.json 的 pose_key 字段引用,loader 负责校验覆盖。
本文件零 pygame 依赖,core/data 与 assets 双方都 import 它(不经过 assets,
避免把字体/渲染依赖带进 core 层)。
"""

POSE_KEYS = {
    # 基础状态
    "idle": 4, "walk": 4, "run": 6, "crouch": 1,
    "stand_block": 1, "crouch_block": 1,
    "prejump": 1, "jump": 2, "jump_fall": 2, "land": 1,
    "air_hit": 1, "fall": 2, "knockdown": 1, "wakeup": 1,
    "hit_high": 2, "hit_low": 1, "dash_back": 2,
    "throw_whiff": 2, "throw_grab": 2, "thrown": 1,
    "win": 1, "lose": 1, "intro": 2,
    # 普通技(与 terry.json move_id 同名)
    "st_A": 2, "st_B": 2, "st_C": 3, "st_D": 3,
    "cr_A": 2, "cr_B": 2, "cr_C": 2, "cr_D": 3,
    "j_A": 2, "j_B": 2, "j_C": 3, "j_D": 3,
    # 必杀/超杀(terry.json 用 pose_key 引用,如 power_wave_A → power_wave)
    "power_wave": 3, "burn_knuckle": 4, "crack_shoot": 4,
    "rising_tackle": 4, "power_dunk": 5, "power_geyser": 5,
    # 特效
    "proj_wave": 3, "fx_geyser": 5, "fx_hit": 2, "fx_block": 2,
}
