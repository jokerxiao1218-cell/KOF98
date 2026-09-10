"""core/projectile.py — 飞行道具实体(能量波,设计文档 §4.4 / §5.3 A3 契约)。

职责:能量波弹体这一"自带状态的纯数据实体"——位置推进、存活判定、
世界坐标判定框、被打掉标记。裁决(combat.resolve_projectile)不在这里。

纪律:零 pygame import;同屏一发限制(move.projectile["max_count"])
由持有方(fighter/match)执行,实体本身不管场上已有几发。

坐标系(全项目约定):y 向上为正、地面 y=0;能量波是地面弹,y 恒 0。
Box 注解的 int 只是源框约定,弹体逐帧平移后世界坐标允许 float
(x 每帧 +3.5 这类非整数步进,取整会引入半像素抖动)。
"""
from __future__ import annotations

from . import types as T


class Projectile:
    """一发能量波。构造:Projectile(move, x, facing, side, bounds)。

    * move:发波招 MoveDef(projectile 参数非空,否则是数据错误 → 报 ValueError);
    * x / facing:发射点世界坐标与飞行方向(+1 右 / −1 左);
    * side:发射方(HitResult.attacker 要用——A3 契约补全,见汇报);
    * bounds=(lo, hi):世界 x 存活区间(含端点,如舞台 [0, 640]);
      出界由 alive 反映为 False,回收由持有方负责。
    """

    def __init__(self, move: T.MoveDef, x: float, facing: int, side: T.Side,
                 bounds: tuple) -> None:
        if move.projectile is None:
            raise ValueError(f"{move.name} 不是发波招(缺 projectile 参数)")
        if facing not in (1, -1):
            raise ValueError(f"facing 应为 ±1,得到 {facing!r}")
        lo, hi = bounds
        if not lo < hi:
            raise ValueError(f"bounds 应为 (lo, hi) 且 lo<hi,得到 {bounds!r}")
        self.move = move
        self.x = float(x)
        self.y = 0.0  # 地面弹,永不离地
        self.facing = facing
        self.side = side
        self._bounds = (lo, hi)
        self._dead = False

    @property
    def speed(self) -> float:
        """弹速(px/帧,来自 move.projectile)。"""
        return self.move.projectile["speed"]

    def step(self) -> None:
        """每帧推进:x += speed × facing(y 不动)。"""
        self.x += self.move.projectile["speed"] * self.facing

    @property
    def alive(self) -> bool:
        """存活 = 没被打掉 且 仍在边界内(含端点)。"""
        lo, hi = self._bounds
        return not self._dead and lo <= self.x <= hi

    def boxes(self) -> tuple:
        """世界坐标判定框(单个):源框相对弹体原点、面朝左时镜像,再平移 x。

        面朝右:[x, x+24);面朝左:镜像后 [x−24, x) —— 框在弹体行进方向一侧。
        """
        box = self.move.projectile["box"]
        b = box.mirrored() if self.facing == -1 else box
        return (T.Box(b.x1 + self.x, b.y1, b.x2 + self.x, b.y2),)

    def on_hit(self) -> None:
        """命中后由调用方调用(裁决在 combat.resolve_projectile,它无副作用)。"""
        self._dead = True
