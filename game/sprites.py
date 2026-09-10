"""game/sprites.py — 真实贴图注册表(素材系统 v2,batch E,设计文档 §11.2A)。

职责:加载 `game/sprites/terry/manifest.json` + 用户自备 PNG sheet,
按姿势切格、锚点衬底、P2 换色,给 assets.sprite 提供真图路径。

版权纪律(§11.1 已与用户确认):本目录整体 gitignore,仓库永不收录
版权图;目录不存在 = 合法的"全回退"状态(程序绘制,游戏照跑)。

manifest 格式(键名冻结,scripts/manifest.example.json 有完整样例):
  {
    "scale": 1,                       // sheet 放大倍数,只允许 ≥1 整数
    "swap_p2": [[[196,32,32],[44,88,196]]],   // P2 换色 LUT,逐色对
    "poses": {
      "idle": {"sheet": "idle.png",
               "strip": {"count":4, "fw":56, "fh":100, "ax":28, "ay":100}},
      "st_C": {"sheet": "attacks.png",
               "frames": [{"x":0,"y":0,"w":60,"h":98,"ax":30,"ay":98}]}
    }
  }
  * strip = 均匀网格(左→右、上→下,可加 "rows":n);frames = 逐帧显式矩形;
  * ax/ay = 帧内"脚底中心"锚点;返回 Surface 一律衬底成"脚底=画布底、
    水平居中",ui 的落点计算零改动;
  * 姿势键必须在 poses.POSE_KEYS 里(打错键名直接报错,不静默);
  * 特效键(proj_wave 等)不走真图,永远程序绘制。

错误纪律:RealSprites.load() 对坏 manifest 抛 SpriteError(带字段路径,
和 core.data.DataError 同风格);default_registry() 捕获后打 stderr 警告
并整包回退(游戏不因半成品 manifest 起不来,但也绝不静默);
scripts/sprite_check.py 走严格路径给出逐项诊断。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame

from game import poses

SPRITE_DIR = Path(__file__).resolve().parent / "sprites" / "terry"


class SpriteError(ValueError):
    """manifest/贴图错误(报错带字段路径,定位到键)。"""


class _Frame:
    """一帧的切格规格 + 锚点(单位:sheet 像素;scale 换算在加载期完成)。"""

    __slots__ = ("x", "y", "w", "h", "ax", "ay")

    def __init__(self, x, y, w, h, ax, ay):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.ax, self.ay = ax, ay


def _need_int(data, path, lo, hi=None):
    v = data
    if isinstance(v, bool) or not isinstance(v, int):
        raise SpriteError(f"{path} 应为整数,得到 {v!r}")
    if v < lo or (hi is not None and v > hi):
        raise SpriteError(f"{path}={v} 越界(合法 {lo}..{hi if hi is not None else '∞'})")
    return v


def _need_rgb(v, path):
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255
                   for c in v)):
        raise SpriteError(f"{path} 应为 [r,g,b](0..255),得到 {v!r}")
    return (int(v[0]), int(v[1]), int(v[2]))


class RealSprites:
    """一份 manifest 的注册表。目录/manifest 缺失 → 空(全回退,不算错)。"""

    def __init__(self, dirpath=SPRITE_DIR):
        self._dir = Path(dirpath)
        self.loaded = False
        self._poses: dict = {}   # pose_key -> (sheet文件名, [_Frame, ...])
        self._sheets: dict = {}  # 文件名 -> Surface
        self._swap: list = []    # [(from_rgb, to_rgb)]
        self._scale = 1
        self._cache: dict = {}    # (pose, frame, facing, side) -> Surface

    # ---------- 加载与校验 ----------

    def load(self) -> None:
        """读 manifest + 全部 sheet,校验一切;坏数据抛 SpriteError。"""
        if self.loaded:
            return
        self.loaded = True
        manifest = self._dir / "manifest.json"
        if not self._dir.is_dir() or not manifest.is_file():
            return  # 没装真图:合法回退态
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise SpriteError(f"manifest.json 读取/解析失败:{e}") from e
        if not isinstance(data, dict):
            raise SpriteError("manifest 顶层应为对象")
        root = "manifest"
        self._scale = _need_int(data.get("scale", 1), f"{root}.scale", 1, 8)
        swap = data.get("swap_p2", [])
        if not isinstance(swap, list):
            raise SpriteError(f"{root}.swap_p2 应为颜色对列表")
        self._swap = []
        for i, pair in enumerate(swap):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise SpriteError(f"{root}.swap_p2[{i}] 应为 [原色, 换色] 两项")
            self._swap.append((_need_rgb(pair[0], f"{root}.swap_p2[{i}][0]"),
                               _need_rgb(pair[1], f"{root}.swap_p2[{i}][1]")))

        poses_data = data.get("poses")
        if not isinstance(poses_data, dict) or not poses_data:
            raise SpriteError(f"{root}.poses 应为非空对象(姿势→切格)")
        for key, spec in poses_data.items():
            path = f"{root}.poses.{key}"
            if key not in poses.POSE_KEYS or key in ("proj_wave", "fx_geyser",
                                                    "fx_hit", "fx_block"):
                raise SpriteError(f"{path}:未注册/特效姿势(可用键见 game/poses.py)")
            self._poses[key] = self._build_pose(path, key, spec)

        for sheet_name in {v[0] for v in self._poses.values()}:
            path = self._dir / sheet_name
            if not path.is_file():
                raise SpriteError(f"sheet 文件不存在:{sheet_name}(相对 manifest)")
            try:
                # 不 convert_alpha:它要求 display 已初始化(无头没有窗口);
                # PNG 的逐像素 alpha 在 load 时就带着,直接可用
                self._sheets[sheet_name] = pygame.image.load(str(path))
            except pygame.error as e:
                raise SpriteError(f"sheet 加载失败 {sheet_name}:{e}") from e

    def _build_pose(self, path, key, spec):
        """一个姿势 → (sheet名, [帧规格...]);scale 换算在此完成。"""
        if not isinstance(spec, dict):
            raise SpriteError(f"{path} 应为对象")
        sheet = spec.get("sheet")
        if not isinstance(sheet, str) or not sheet:
            raise SpriteError(f"{path}.sheet 应为文件名")
        frames = []
        if "strip" in spec:
            st = spec["strip"]
            if not isinstance(st, dict):
                raise SpriteError(f"{path}.strip 应为对象")
            count = _need_int(st.get("count"), f"{path}.strip.count", 1, 4096)
            fw = _need_int(st.get("fw"), f"{path}.strip.fw", 1)
            fh = _need_int(st.get("fh"), f"{path}.strip.fh", 1)
            ax = _need_int(st.get("ax"), f"{path}.strip.ax", 0, fw)
            ay = _need_int(st.get("ay"), f"{path}.strip.ay", 0, fh)
            rows = _need_int(st.get("rows", 1), f"{path}.strip.rows", 1, count)
            if fw % self._scale or fh % self._scale or ax % self._scale or ay % self._scale:
                raise SpriteError(
                    f"{path}.strip:scale={self._scale} 除不尽 fw/fh/ax/ay"
                    "(放大过的图请按原始倍率整数切格)")
            cols = -(-count // rows)  # ceil
            for i in range(count):
                r, c = divmod(i, cols)
                frames.append(_Frame(c * fw, r * fh, fw, fh, ax, ay))
        elif "frames" in spec:
            fr = spec["frames"]
            if not isinstance(fr, list) or not fr:
                raise SpriteError(f"{path}.frames 应为非空数组")
            for i, f in enumerate(fr):
                fp = f"{path}.frames[{i}]"
                if not isinstance(f, dict):
                    raise SpriteError(f"{fp} 应为对象")
                x = _need_int(f.get("x"), f"{fp}.x", 0)
                y = _need_int(f.get("y"), f"{fp}.y", 0)
                w = _need_int(f.get("w"), f"{fp}.w", 1)
                h = _need_int(f.get("h"), f"{fp}.h", 1)
                ax = _need_int(f.get("ax"), f"{fp}.ax", 0, w)
                ay = _need_int(f.get("ay"), f"{fp}.ay", 0, h)
                frames.append(_Frame(x, y, w, h, ax, ay))
        else:
            raise SpriteError(f"{path}:需要 strip(均匀网格)或 frames(逐帧矩形)")
        return (sheet, frames)

    # ---------- 查询与取图 ----------

    def has(self, pose_key) -> bool:
        return pose_key in self._poses

    def frame_count(self, pose_key) -> int:
        return len(self._poses[pose_key][1])

    def pose_keys(self):
        return sorted(self._poses)

    def surface(self, pose_key, frame, facing, side):
        """取一帧:切格 → scale 缩回 → P2 换色 → 锚点衬底 → 朝左镜像。"""
        if not self.has(pose_key):
            raise KeyError(f"真图未覆盖姿势 {pose_key!r}")
        n = self.frame_count(pose_key)
        f = frame % n
        ck = (pose_key, f, facing, side)
        if ck in self._cache:
            return self._cache[ck]
        sheet_name, frames = self._poses[pose_key]
        spec = frames[f]
        img = self._sheets[sheet_name].subsurface(
            pygame.Rect(spec.x, spec.y, spec.w, spec.h)).copy()
        if self._scale > 1:
            img = pygame.transform.scale(
                img, (spec.w // self._scale, spec.h // self._scale))
            ax, ay = spec.ax // self._scale, spec.ay // self._scale
            w = spec.w // self._scale
        else:
            ax, ay, w = spec.ax, spec.ay, spec.w
        if side == "P2" and self._swap:
            lut = {src: dst for src, dst in self._swap}
            for yy in range(img.get_height()):
                for xx in range(img.get_width()):
                    p = img.get_at((xx, yy))
                    rgb = (p[0], p[1], p[2])
                    if p[3] > 0 and rgb in lut:
                        img.set_at((xx, yy), (*lut[rgb], p[3]))
        canvas_w = 2 * max(ax, w - ax)   # 脚底中心水平居中
        canvas_h = ay                     # 脚底 = 画布底(裁掉脚下多余行)
        out = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
        out.blit(img, (canvas_w // 2 - ax, 0), area=pygame.Rect(0, 0, w, ay))
        if facing == -1:
            out = pygame.transform.flip(out, True, False)
        self._cache[ck] = out
        return out


# ---------- 默认注册表(assets 的唯一入口) ----------

_registry: RealSprites | None = None


def default_registry() -> RealSprites:
    """默认目录单例。加载失败 → stderr 警告 + 整包回退(游戏不因此起不来,
    但绝不静默);测试可替换模块级 _registry 注入临时目录。"""
    global _registry
    if _registry is None:
        _registry = RealSprites()
    if not _registry.loaded:
        try:
            _registry.load()
        except SpriteError as e:
            print(f"[sprites] manifest 有问题,整包回退程序绘制:{e}",
                  file=sys.stderr)
            print("[sprites] 跑 scripts/sprite_check.py 逐项定位",
                  file=sys.stderr)
            _registry._poses = {}
            _registry._swap = []
            _registry.loaded = True
    return _registry
