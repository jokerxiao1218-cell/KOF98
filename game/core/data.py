"""core/data.py — terry/system/ai 三份数据 JSON 的加载与校验(设计文档 §5.1)。

纪律:
  * 校验失败抛 DataError(带 "文件:条目:字段" 路径),绝不静默画歪;
  * 零 pygame 依赖;调参只改 game/data/*.json,不改本文件(设计文档 §2)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import types as T
from .. import poses

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DataError(Exception):
    """数据非法。message 带字段路径,方便定位。"""


# ---------- 基础小工具(每个都明确报错,不静默) ----------


def _load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise DataError(f"{filename}:文件不存在({path})")
    try:
        with path.open(encoding="utf-8") as f:
            v = json.load(f)
    except json.JSONDecodeError as e:
        raise DataError(f"{filename}:JSON 语法错误:{e}") from e
    if not isinstance(v, dict):
        raise DataError(f"{filename}:顶层必须是对象")
    return v


def _need(d: dict, key: str, ctx: str):
    if key not in d:
        raise DataError(f"{ctx}:缺字段 {key}")
    return d[key]


def _int(v, ctx: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise DataError(f"{ctx} 应为整数,得到 {v!r}")
    return v


def _num(v, ctx: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise DataError(f"{ctx} 应为数字,得到 {v!r}")
    return float(v)


def _str(v, ctx: str, allow_empty: bool = False) -> str:
    if not isinstance(v, str) or (not allow_empty and not v):
        raise DataError(f"{ctx} 应为非空字符串,得到 {v!r}")
    return v


def _box(v, ctx: str) -> T.Box:
    if (
        not isinstance(v, (list, tuple))
        or len(v) != 4
        or not all(isinstance(i, int) and not isinstance(i, bool) for i in v)
    ):
        raise DataError(f"{ctx} 判定框应为 [x1,y1,x2,y2] 四个整数,得到 {v!r}")
    x1, y1, x2, y2 = v
    if x2 <= x1 or y2 <= y1:
        raise DataError(f"{ctx} 判定框要求 x2>x1 且 y2>y1,得到 {v!r}")
    if y1 < 0:
        raise DataError(f"{ctx} 判定框 y1 应 >=0(0=脚底,y 向上为正),得到 {v!r}")
    return T.Box(x1, y1, x2, y2)


def _boxes(v, ctx: str, nonempty: bool = True) -> tuple:
    if not isinstance(v, list):
        raise DataError(f"{ctx} 应为列表,得到 {v!r}")
    if nonempty and not v:
        raise DataError(f"{ctx} 不能为空列表")
    return tuple(_box(b, f"{ctx}[{i}]") for i, b in enumerate(v))


def _in(v, allowed: set, ctx: str) -> str:
    if v not in allowed:
        raise DataError(f"{ctx} 应为 {sorted(allowed)} 之一,得到 {v!r}")
    return v


# ---------- system 配置结构 + 构建 ----------


@dataclass(frozen=True)
class ViewCfg:
    w: int
    h: int
    scale: int


@dataclass(frozen=True)
class StageCfg:
    width: int
    ground_y: int
    start_x: tuple  # (P1, P2)


@dataclass(frozen=True)
class GaugeCfg:
    max: int
    hit_normal: int
    hit_special: int
    on_hit_taken: int
    on_block: int


@dataclass(frozen=True)
class HitstopCfg:
    hit_normal: int
    hit_special: int
    hit_super: int
    hit_throw: int
    block_normal: int
    block_special: int
    block_super: int
    projectile_victim: int


@dataclass(frozen=True)
class WalkCfg:
    fwd: float
    back: float  # 正数大小(向后走)


@dataclass(frozen=True)
class RunCfg:
    speed: float
    stop_frames: int


@dataclass(frozen=True)
class JumpCfg:
    prejump: int
    big_vy0: float
    small_vy0: float
    fwd_vx: float
    small_fwd_vx: float
    back_vx: float  # 正数大小(向后跳)
    air_attack_land_lag: int
    air_lag: int


@dataclass(frozen=True)
class DashBackCfg:
    frames: int
    vx: float  # 正数大小(向身后)
    vy0: float


@dataclass(frozen=True)
class WakeupCfg:
    frames: int
    invuln_frames: int


@dataclass(frozen=True)
class CameraCfg:
    follow_mid_offset: int
    clamp: tuple  # (min, max)
    edge_margin: int


@dataclass(frozen=True)
class InputCfg:
    dir_window: int
    button_buffer: int
    dp_window: int
    double_qcf_window: int
    charge_frames: int
    dash_tap_window: int


@dataclass(frozen=True)
class SystemCfg:
    view: ViewCfg
    stage: StageCfg
    fps: int
    health: int
    round_time_frames: int
    rounds_to_win: int
    gauge: GaugeCfg
    hitstop: HitstopCfg
    walk: WalkCfg
    run: RunCfg
    gravity: float  # 负数(向上为正约定)
    jump: JumpCfg
    dash_back: DashBackCfg
    wakeup: WakeupCfg
    juggle_bounce_vy: float
    combo_scaling: tuple
    hurt_boxes: dict  # {"stand": Box, "crouch": Box}
    push_boxes: dict
    camera: CameraCfg
    input: InputCfg
    throw_range: int


def build_system(d: dict, filename: str = "system.json") -> SystemCfg:
    ctx = filename
    view = _need(d, "view", ctx)
    stage = _need(d, "stage", ctx)
    gauge = _need(d, "gauge", ctx)
    hitstop = _need(d, "hitstop", ctx)
    walk = _need(d, "walk", ctx)
    run = _need(d, "run", ctx)
    jump = _need(d, "jump", ctx)
    dash = _need(d, "dash_back", ctx)
    wakeup = _need(d, "wakeup", ctx)
    camera = _need(d, "camera", ctx)
    inputc = _need(d, "input", ctx)

    v = ViewCfg(
        w=_int(_need(view, "w", f"{ctx}:view"), f"{ctx}:view.w"),
        h=_int(_need(view, "h", f"{ctx}:view"), f"{ctx}:view.h"),
        scale=_int(_need(view, "scale", f"{ctx}:view"), f"{ctx}:view.scale"),
    )
    if v.w < 100 or v.h < 100 or v.scale < 1:
        raise DataError(f"{ctx}:view 分辨率/放大倍数不合理 {v}")

    sxx = _need(stage, "start_x", f"{ctx}:stage")
    if not isinstance(sxx, list) or len(sxx) != 2:
        raise DataError(f"{ctx}:stage.start_x 应为 [P1x, P2x]")
    s = StageCfg(
        width=_int(_need(stage, "width", f"{ctx}:stage"), f"{ctx}:stage.width"),
        ground_y=_int(_need(stage, "ground_y", f"{ctx}:stage"), f"{ctx}:stage.ground_y"),
        start_x=(_int(sxx[0], f"{ctx}:stage.start_x[0]"), _int(sxx[1], f"{ctx}:stage.start_x[1]")),
    )
    if s.width <= v.w:
        raise DataError(f"{ctx}:stage.width({s.width}) 必须 > view.w({v.w}),否则摄像机无处可移")
    if not (0 < s.ground_y < v.h):
        raise DataError(f"{ctx}:stage.ground_y 应在画面内(0~{v.h}),得到 {s.ground_y}")
    if not (0 <= s.start_x[0] < s.start_x[1] < s.width):
        raise DataError(f"{ctx}:stage.start_x 应满足 0<=P1x<P2x<width,得到 {s.start_x}")

    fps = _int(_need(d, "fps", ctx), f"{ctx}:fps")
    if fps != 60:
        raise DataError(f"{ctx}:fps 必须 =60(逻辑帧锁是设计前提,帧数据都按 60fps 定义),得到 {fps}")
    health = _int(_need(d, "health", ctx), f"{ctx}:health")
    if health <= 0:
        raise DataError(f"{ctx}:health 应 >0")
    rtf = _int(_need(d, "round_time_frames", ctx), f"{ctx}:round_time_frames")
    if rtf <= 0:
        raise DataError(f"{ctx}:round_time_frames 应 >0")
    rtw = _int(_need(d, "rounds_to_win", ctx), f"{ctx}:rounds_to_win")
    if not 1 <= rtw <= 3:
        raise DataError(f"{ctx}:rounds_to_win 应为 1~3")

    g = GaugeCfg(
        max=_int(_need(gauge, "max", f"{ctx}:gauge"), f"{ctx}:gauge.max"),
        hit_normal=_int(_need(gauge, "hit_normal", f"{ctx}:gauge"), f"{ctx}:gauge.hit_normal"),
        hit_special=_int(_need(gauge, "hit_special", f"{ctx}:gauge"), f"{ctx}:gauge.hit_special"),
        on_hit_taken=_int(_need(gauge, "on_hit_taken", f"{ctx}:gauge"), f"{ctx}:gauge.on_hit_taken"),
        on_block=_int(_need(gauge, "on_block", f"{ctx}:gauge"), f"{ctx}:gauge.on_block"),
    )
    if g.max <= 0 or any(x < 0 for x in (g.hit_normal, g.hit_special, g.on_hit_taken, g.on_block)):
        raise DataError(f"{ctx}:gauge 数值非法 {g}")

    h = HitstopCfg(
        hit_normal=_int(_need(hitstop, "hit_normal", f"{ctx}:hitstop"), f"{ctx}:hitstop.hit_normal"),
        hit_special=_int(_need(hitstop, "hit_special", f"{ctx}:hitstop"), f"{ctx}:hitstop.hit_special"),
        hit_super=_int(_need(hitstop, "hit_super", f"{ctx}:hitstop"), f"{ctx}:hitstop.hit_super"),
        hit_throw=_int(_need(hitstop, "hit_throw", f"{ctx}:hitstop"), f"{ctx}:hitstop.hit_throw"),
        block_normal=_int(_need(hitstop, "block_normal", f"{ctx}:hitstop"), f"{ctx}:hitstop.block_normal"),
        block_special=_int(_need(hitstop, "block_special", f"{ctx}:hitstop"), f"{ctx}:hitstop.block_special"),
        block_super=_int(_need(hitstop, "block_super", f"{ctx}:hitstop"), f"{ctx}:hitstop.block_super"),
        projectile_victim=_int(
            _need(hitstop, "projectile_victim", f"{ctx}:hitstop"), f"{ctx}:hitstop.projectile_victim"
        ),
    )
    if any(getattr(h, name) < 0 for name in h.__dataclass_fields__):
        raise DataError(f"{ctx}:hitstop 帧数应全部 >=0")

    w = WalkCfg(
        fwd=_num(_need(walk, "fwd", f"{ctx}:walk"), f"{ctx}:walk.fwd"),
        back=_num(_need(walk, "back", f"{ctx}:walk"), f"{ctx}:walk.back"),
    )
    if w.fwd <= 0 or w.back <= 0:
        raise DataError(f"{ctx}:walk 速度应为正数(大小),得到 {w}")

    r = RunCfg(
        speed=_num(_need(run, "speed", f"{ctx}:run"), f"{ctx}:run.speed"),
        stop_frames=_int(_need(run, "stop_frames", f"{ctx}:run"), f"{ctx}:run.stop_frames"),
    )
    if r.speed <= 0 or r.stop_frames < 0:
        raise DataError(f"{ctx}:run 数值非法 {r}")

    gravity = _num(_need(d, "gravity", ctx), f"{ctx}:gravity")
    if gravity >= 0:
        raise DataError(f"{ctx}:gravity 必须 <0(全项目约定 vy 向上为正),得到 {gravity}")

    j = JumpCfg(
        prejump=_int(_need(jump, "prejump", f"{ctx}:jump"), f"{ctx}:jump.prejump"),
        big_vy0=_num(_need(jump, "big_vy0", f"{ctx}:jump"), f"{ctx}:jump.big_vy0"),
        small_vy0=_num(_need(jump, "small_vy0", f"{ctx}:jump"), f"{ctx}:jump.small_vy0"),
        fwd_vx=_num(_need(jump, "fwd_vx", f"{ctx}:jump"), f"{ctx}:jump.fwd_vx"),
        small_fwd_vx=_num(_need(jump, "small_fwd_vx", f"{ctx}:jump"), f"{ctx}:jump.small_fwd_vx"),
        back_vx=_num(_need(jump, "back_vx", f"{ctx}:jump"), f"{ctx}:jump.back_vx"),
        air_attack_land_lag=_int(
            _need(jump, "air_attack_land_lag", f"{ctx}:jump"), f"{ctx}:jump.air_attack_land_lag"
        ),
        air_lag=_int(_need(jump, "air_lag", f"{ctx}:jump"), f"{ctx}:jump.air_lag"),
    )
    if j.prejump < 1:
        raise DataError(f"{ctx}:jump.prejump 应 >=1")
    if not (0 < j.small_vy0 < j.big_vy0):
        raise DataError(f"{ctx}:jump 应满足 0 < small_vy0 < big_vy0(小跳更矮),得到 {j.small_vy0}/{j.big_vy0}")
    if j.fwd_vx < 0 or j.small_fwd_vx < 0 or j.back_vx < 0:
        raise DataError(f"{ctx}:jump 前后跳 vx 存正数大小,不应为负")
    if j.air_lag < 0 or j.air_attack_land_lag < 0:
        raise DataError(f"{ctx}:jump 落地 lag 应 >=0")

    db = DashBackCfg(
        frames=_int(_need(dash, "frames", f"{ctx}:dash_back"), f"{ctx}:dash_back.frames"),
        vx=_num(_need(dash, "vx", f"{ctx}:dash_back"), f"{ctx}:dash_back.vx"),
        vy0=_num(_need(dash, "vy0", f"{ctx}:dash_back"), f"{ctx}:dash_back.vy0"),
    )
    if db.frames < 1 or db.vx <= 0 or db.vy0 < 0:
        raise DataError(f"{ctx}:dash_back 数值非法 {db}(vx 存正数大小,语义向身后)")

    wk = WakeupCfg(
        frames=_int(_need(wakeup, "frames", f"{ctx}:wakeup"), f"{ctx}:wakeup.frames"),
        invuln_frames=_int(_need(wakeup, "invuln_frames", f"{ctx}:wakeup"), f"{ctx}:wakeup.invuln_frames"),
    )
    if wk.frames < 1 or not 0 <= wk.invuln_frames <= wk.frames:
        raise DataError(f"{ctx}:wakeup 数值非法 {wk}")

    juggle = _num(_need(d, "juggle_bounce_vy", ctx), f"{ctx}:juggle_bounce_vy")
    if juggle < 0:
        raise DataError(f"{ctx}:juggle_bounce_vy 应 >=0")

    scaling_raw = _need(d, "combo_scaling", ctx)
    if not isinstance(scaling_raw, list) or not scaling_raw:
        raise DataError(f"{ctx}:combo_scaling 应为非空列表")
    scaling = tuple(_int(x, f"{ctx}:combo_scaling[{i}]") for i, x in enumerate(scaling_raw))
    if any(not 0 < x <= 100 for x in scaling):
        raise DataError(f"{ctx}:combo_scaling 每项应为 (0,100],得到 {scaling}")
    if any(a < b for a, b in zip(scaling, scaling[1:])):
        raise DataError(f"{ctx}:combo_scaling 应单调不增(伤害越打越少),得到 {scaling}")

    def _boxpair(key: str) -> dict:
        raw = _need(d, key, ctx)
        if not isinstance(raw, dict) or set(raw) != {"stand", "crouch"}:
            raise DataError(f"{ctx}:{key} 应只含 stand/crouch 两键")
        return {k: _box(raw[k], f"{ctx}:{key}.{k}") for k in raw}

    hurt_boxes = _boxpair("hurt_boxes")
    push_boxes = _boxpair("push_boxes")

    cam_raw = camera
    clamp_raw = _need(cam_raw, "clamp", f"{ctx}:camera")
    if not isinstance(clamp_raw, list) or len(clamp_raw) != 2:
        raise DataError(f"{ctx}:camera.clamp 应为 [min, max]")
    cam = CameraCfg(
        follow_mid_offset=_int(
            _need(cam_raw, "follow_mid_offset", f"{ctx}:camera"), f"{ctx}:camera.follow_mid_offset"
        ),
        clamp=(_int(clamp_raw[0], f"{ctx}:camera.clamp[0]"), _int(clamp_raw[1], f"{ctx}:camera.clamp[1]")),
        edge_margin=_int(_need(cam_raw, "edge_margin", f"{ctx}:camera"), f"{ctx}:camera.edge_margin"),
    )
    if cam.clamp[0] < 0 or cam.clamp[0] >= cam.clamp[1] or cam.clamp[1] > s.width - v.w:
        raise DataError(
            f"{ctx}:camera.clamp 应满足 0<=min<max<=stage.width-view.w({s.width - v.w}),得到 {cam.clamp}"
        )
    if cam.edge_margin < 0:
        raise DataError(f"{ctx}:camera.edge_margin 应 >=0")

    ic = InputCfg(
        dir_window=_int(_need(inputc, "dir_window", f"{ctx}:input"), f"{ctx}:input.dir_window"),
        button_buffer=_int(_need(inputc, "button_buffer", f"{ctx}:input"), f"{ctx}:input.button_buffer"),
        dp_window=_int(_need(inputc, "dp_window", f"{ctx}:input"), f"{ctx}:input.dp_window"),
        double_qcf_window=_int(_need(inputc, "double_qcf_window", f"{ctx}:input"), f"{ctx}:input.double_qcf_window"),
        charge_frames=_int(_need(inputc, "charge_frames", f"{ctx}:input"), f"{ctx}:input.charge_frames"),
        dash_tap_window=_int(_need(inputc, "dash_tap_window", f"{ctx}:input"), f"{ctx}:input.dash_tap_window"),
    )
    if any(getattr(ic, name) < 1 for name in ic.__dataclass_fields__):
        raise DataError(f"{ctx}:input 各窗口应 >=1")

    throw_range = _int(_need(d, "throw_range", ctx), f"{ctx}:throw_range")
    if throw_range <= 0:
        raise DataError(f"{ctx}:throw_range 应 >0")

    return SystemCfg(
        view=v, stage=s, fps=fps, health=health, round_time_frames=rtf, rounds_to_win=rtw,
        gauge=g, hitstop=h, walk=w, run=r, gravity=gravity, jump=j, dash_back=db, wakeup=wk,
        juggle_bounce_vy=juggle, combo_scaling=scaling, hurt_boxes=hurt_boxes,
        push_boxes=push_boxes, camera=cam, input=ic, throw_range=throw_range,
    )


# ---------- 招式表构建 ----------

_KINDS = {"NORMAL", "SPECIAL", "SUPER", "THROW"}
_STANCES = {"stand", "crouch", "air"}
_GUARDS = {"mid", "low", "high", "unblockable"}
_KNOCKDOWNS = {"none", "air_juggle", "sweep", "hard"}
_CANCELS = {"special", "super"}
_MOTION_KEYS = {"vx", "vy0", "frames", "from_frame", "until"}
_INPUT_TYPES = {"button", "motion", "charge", "throw"}
_NUMPAD = {"1", "2", "3", "4", "6", "8"}
_BUTTONS = {"A", "B", "C", "D"}


def _build_windows(raw, ctx: str) -> tuple:
    if not isinstance(raw, list):
        raise DataError(f"{ctx} 应为列表")
    out = []
    last_end = -1
    for i, w in enumerate(raw):
        wctx = f"{ctx}[{i}]"
        if not isinstance(w, dict):
            raise DataError(f"{wctx} 应为对象")
        start = _int(_need(w, "start", wctx), f"{wctx}.start")
        end = _int(_need(w, "end", wctx), f"{wctx}.end")
        if start < 0:
            raise DataError(f"{wctx}.start 应 >=0,得到 {start}")
        if end == -1:
            pass  # "直到落地"仅空中技可用,交给 _build_move 按 stance 裁决
        elif end < start:
            raise DataError(f"{wctx} 要求 end>=start(或 end=-1 表示直到落地),得到 {start}~{end}")
        if start <= last_end:
            raise DataError(f"{wctx}.start 应晚于上一窗结束({last_end}),判定窗不许重叠")
        hit = _boxes(_need(w, "hit", wctx), f"{wctx}.hit")
        kd = w.get("knockdown")
        if kd is not None:
            _in(kd, _KNOCKDOWNS, f"{wctx}.knockdown")
        out.append(T.AttackWindow(start, end, hit, kd))
        last_end = end
    return tuple(out)


def _build_input(raw, ctx: str) -> dict:
    if not isinstance(raw, dict):
        raise DataError(f"{ctx} 应为对象")
    t = _in(_need(raw, "type", ctx), _INPUT_TYPES, f"{ctx}.type")
    out = {"type": t}
    if t == "button":
        out["button"] = _in(_need(raw, "button", ctx), _BUTTONS, f"{ctx}.button")
    elif t == "motion":
        pat = _need(raw, "pattern", ctx)
        if not isinstance(pat, list) or not pat:
            raise DataError(f"{ctx}.pattern 应为非空列表")
        out["pattern"] = [
            _in(p, _NUMPAD, f"{ctx}.pattern[{i}]") for i, p in enumerate(pat)
        ]
        out["button"] = _in(_need(raw, "button", ctx), _BUTTONS, f"{ctx}.button")
    elif t == "charge":
        out["charge_dir"] = _in(_need(raw, "charge_dir", ctx), _NUMPAD, f"{ctx}.charge_dir")
        out["release_dir"] = _in(_need(raw, "release_dir", ctx), _NUMPAD, f"{ctx}.release_dir")
        if out["charge_dir"] == out["release_dir"]:
            raise DataError(f"{ctx} 蓄力方向与释放方向不应相同")
        out["button"] = _in(_need(raw, "button", ctx), _BUTTONS, f"{ctx}.button")
    else:  # throw
        out["dir"] = _in(_need(raw, "dir", ctx), {"fwd", "back"}, f"{ctx}.dir")
        out["button"] = _in(_need(raw, "button", ctx), {"C", "D"}, f"{ctx}.button")
    return out


def _build_motion(raw, ctx: str, total: int) -> dict:
    if not isinstance(raw, dict):
        raise DataError(f"{ctx} 应为对象")
    extra = set(raw) - _MOTION_KEYS
    if extra:
        raise DataError(f"{ctx} 含未知键 {sorted(extra)},允许 {sorted(_MOTION_KEYS)}")
    out = dict(raw)
    for k in ("vx", "vy0", "frames", "from_frame"):
        if k in out:
            out[k] = _num(out[k], f"{ctx}.{k}")
    if "until" in out:
        _in(out["until"], {"land", "frames"}, f"{ctx}.until")
        if out["until"] == "land" and "vy0" not in out:
            raise DataError(f"{ctx} until=land 需要起始上抛速度 vy0")
    if "frames" in out and out["frames"] < 1:
        raise DataError(f"{ctx}.frames 应 >=1")
    if "from_frame" in out and not 0 <= out["from_frame"] < total:
        raise DataError(f"{ctx}.from_frame 应在 0~total-1 内")
    return out


def _build_move(m: dict, ctx: str) -> T.MoveDef:
    name = _str(_need(m, "name", ctx), f"{ctx}.name")
    ctx = f"{ctx}({name})"  # 后续报错都带上招名
    kind = _in(_need(m, "kind", ctx), _KINDS, f"{ctx}.kind")
    stance = _in(_need(m, "stance", ctx), _STANCES, f"{ctx}.stance")
    pose_key = _str(_need(m, "pose_key", ctx), f"{ctx}.pose_key")
    if pose_key not in poses.POSE_KEYS:
        raise DataError(f"{ctx}.pose_key 引用未注册姿势 {pose_key!r}(见 game/poses.py)")

    damage = _int(_need(m, "damage", ctx), f"{ctx}.damage")
    if damage <= 0:
        raise DataError(f"{ctx}.damage 应 >0")
    chip = _int(_need(m, "chip", ctx), f"{ctx}.chip")
    if chip < 0:
        raise DataError(f"{ctx}.chip 应 >=0")
    hitstun = _int(_need(m, "hitstun", ctx), f"{ctx}.hitstun")
    blockstun = _int(_need(m, "blockstun", ctx), f"{ctx}.blockstun")
    if hitstun < 0 or blockstun < 0:
        raise DataError(f"{ctx} 硬直帧应 >=0")
    pb_hit = _num(_need(m, "pushback_hit", ctx), f"{ctx}.pushback_hit")
    pb_block = _num(_need(m, "pushback_block", ctx), f"{ctx}.pushback_block")
    if pb_hit < 0 or pb_block < 0:
        raise DataError(f"{ctx} 推背应 >=0")
    guard = _in(_need(m, "guard", ctx), _GUARDS, f"{ctx}.guard")
    knockdown = _in(_need(m, "knockdown", ctx), _KNOCKDOWNS, f"{ctx}.knockdown")
    cancels_raw = _need(m, "cancels", ctx)
    if not isinstance(cancels_raw, list):
        raise DataError(f"{ctx}.cancels 应为列表")
    for i, c in enumerate(cancels_raw):
        _in(c, _CANCELS, f"{ctx}.cancels[{i}]")
    cancels = tuple(cancels_raw)
    gauge_gain = _int(_need(m, "gauge_gain", ctx), f"{ctx}.gauge_gain")
    if gauge_gain < 0:
        raise DataError(f"{ctx}.gauge_gain 应 >=0")
    gauge_cost = _int(_need(m, "gauge_cost", ctx), f"{ctx}.gauge_cost")
    if gauge_cost < 0:
        raise DataError(f"{ctx}.gauge_cost 应 >=0")
    if (kind == "SUPER") != (gauge_cost > 0):
        raise DataError(f"{ctx}:kind=SUPER 必须且只允许超杀耗气(gauge_cost>0),得到 {kind}/{gauge_cost}")
    total = _int(_need(m, "total", ctx), f"{ctx}.total")
    if total <= 0:
        raise DataError(f"{ctx}.total 应 >0")

    invuln_raw = m.get("invuln", [])
    if not isinstance(invuln_raw, list):
        raise DataError(f"{ctx}.invuln 应为列表")
    invuln = []
    for i, r in enumerate(invuln_raw):
        if not isinstance(r, list) or len(r) != 2:
            raise DataError(f"{ctx}.invuln[{i}] 应为 [起,止] 两整数")
        a, b = _int(r[0], f"{ctx}.invuln[{i}][0]"), _int(r[1], f"{ctx}.invuln[{i}][1]")
        if not 0 <= a <= b < total:
            raise DataError(f"{ctx}.invuln[{i}] 区间应满足 0<=a<=b<total({total}),得到 {a}~{b}")
        invuln.append((a, b))

    windows = _build_windows(_need(m, "windows", ctx), f"{ctx}.windows")
    for w in windows:
        if w.start >= total or (w.end >= 0 and w.end >= total):
            raise DataError(f"{ctx}.windows[{w.start}~{w.end}] 超出总帧数 total={total}")
    if any(w.end == -1 for w in windows) and stance != "air":
        raise DataError(f"{ctx}:end=-1(直到落地)只允许空中技")
    if stance == "air" and any(w.end != -1 for w in windows):
        raise DataError(f"{ctx}:空中技判定窗 end 应为 -1(直到落地)")

    hurt_raw = m.get("hurt_boxes")
    hurt = None if hurt_raw is None else _boxes(hurt_raw, f"{ctx}.hurt_boxes")

    proj_raw = m.get("projectile")
    proj = None
    if proj_raw is not None:
        if not isinstance(proj_raw, dict):
            raise DataError(f"{ctx}.projectile 应为对象")
        extra = set(proj_raw) - {"speed", "box", "max_count"}
        if extra:
            raise DataError(f"{ctx}.projectile 含未知键 {sorted(extra)}")
        speed = _num(_need(proj_raw, "speed", f"{ctx}.projectile"), f"{ctx}.projectile.speed")
        if speed <= 0:
            raise DataError(f"{ctx}.projectile.speed 应 >0")
        max_count = _int(_need(proj_raw, "max_count", f"{ctx}.projectile"), f"{ctx}.projectile.max_count")
        if max_count < 1:
            raise DataError(f"{ctx}.projectile.max_count 应 >=1")
        proj = {
            "speed": speed,
            "box": _box(_need(proj_raw, "box", f"{ctx}.projectile"), f"{ctx}.projectile.box"),
            "max_count": max_count,
        }

    motion_raw = m.get("motion")
    motion = None if motion_raw is None else _build_motion(motion_raw, f"{ctx}.motion", total)

    input_spec = _build_input(_need(m, "input", ctx), f"{ctx}.input")
    if input_spec["type"] != "throw" and kind == "THROW":
        raise DataError(f"{ctx}:THROW 招的 input.type 必须 throw")
    if input_spec["type"] == "throw" and kind != "THROW":
        raise DataError(f"{ctx}:非 THROW 招不许用 throw 输入")

    throw_range = m.get("throw_range")
    if kind == "THROW":
        if windows or proj is not None:
            raise DataError(f"{ctx}:投技不应有判定窗/发波(抓取走独立路径)")
        if guard != "unblockable":
            raise DataError(f"{ctx}:投技 guard 必须为 unblockable")
        throw_range = _int(_need(m, "throw_range", ctx), f"{ctx}.throw_range")
        if throw_range <= 0:
            raise DataError(f"{ctx}.throw_range 应 >0")
        if motion is not None:
            raise DataError(f"{ctx}:投技不应有 motion(位移由 fighter 按约定脚本执行)")
    else:
        if throw_range is not None:
            raise DataError(f"{ctx}:非投技不许设 throw_range")
        if not windows and proj is None:
            raise DataError(f"{ctx}:既无判定窗也不发波,这招打不到人")

    if stance == "air" and motion is not None and motion.get("vy0", 0) < 0:
        raise DataError(f"{ctx}:空中技 motion.vy0 应 >=0(向上为正)")

    return T.MoveDef(
        name=name,
        label=_str(_need(m, "label", ctx), f"{ctx}.label"),
        kind=kind, stance=stance, pose_key=pose_key,
        damage=damage, chip=chip, hitstun=hitstun, blockstun=blockstun,
        pushback_hit=pb_hit, pushback_block=pb_block,
        guard=guard, knockdown=knockdown, cancels=cancels,
        gauge_gain=gauge_gain, gauge_cost=gauge_cost,
        total=total, invuln=tuple(invuln), windows=windows,
        hurt_boxes=hurt, projectile=proj, motion=motion,
        input=input_spec, throw_range=throw_range,
    )


def build_moves(d: dict, filename: str = "terry.json") -> dict:
    moves_raw = _need(d, "moves", filename)
    if not isinstance(moves_raw, list) or not moves_raw:
        raise DataError(f"{filename}:moves 应为非空列表")
    out: dict = {}
    for i, m in enumerate(moves_raw):
        if not isinstance(m, dict):
            raise DataError(f"{filename}:moves[{i}] 应为对象")
        md = _build_move(m, f"{filename}:moves[{i}]")
        if md.name in out:
            raise DataError(f"{filename}:moves 招名重复 {md.name!r}")
        out[md.name] = md
    return out


# ---------- AI 配置 ----------


@dataclass(frozen=True)
class AiCfg:
    seed: int
    reaction_interval: int
    bands: dict  # {"far": int, "close": int}
    weights: dict  # {"far": {动作: 权重}, "mid": ..., "close": ...}
    reactions: dict
    conservative: dict


_REACTION_KEYS = {"block_prob", "antiair_prob", "antiair_dist", "super_prob", "projectile_jump_prob"}


def build_ai(d: dict, filename: str = "ai.json") -> AiCfg:
    ctx = filename
    seed = _int(_need(d, "seed", ctx), f"{ctx}.seed")
    if seed < 0:
        raise DataError(f"{ctx}:seed 应 >=0")
    interval = _int(_need(d, "reaction_interval", ctx), f"{ctx}.reaction_interval")
    if interval < 1:
        raise DataError(f"{ctx}:reaction_interval 应 >=1(反应延迟按帧计)")

    bands = _need(d, "bands", ctx)
    if not isinstance(bands, dict) or set(bands) != {"far", "close"}:
        raise DataError(f"{ctx}:bands 应只含 far/close 两键")
    far = _int(_need(bands, "far", f"{ctx}:bands"), f"{ctx}:bands.far")
    close = _int(_need(bands, "close", f"{ctx}:bands"), f"{ctx}:bands.close")
    if not close < far:
        raise DataError(f"{ctx}:bands 应满足 close < far,得到 {close}/{far}")
    if close <= 0 or far <= 0:
        raise DataError(f"{ctx}:bands 距离应为正")

    weights = _need(d, "weights", ctx)
    if not isinstance(weights, dict) or set(weights) != {"far", "mid", "close"}:
        raise DataError(f"{ctx}:weights 应只含 far/mid/close 三档")
    for band, w in weights.items():
        if not isinstance(w, dict) or not w:
            raise DataError(f"{ctx}:weights.{band} 应为非空对象")
        total = 0.0
        for act, p in w.items():
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
                raise DataError(f"{ctx}:weights.{band}.{act} 权重应为 0~1,得到 {p!r}")
            total += p
        if abs(total - 1.0) > 0.02:
            raise DataError(f"{ctx}:weights.{band} 权重和应为 1.0±0.02,得到 {total:.3f}")

    reactions = _need(d, "reactions", ctx)
    if not isinstance(reactions, dict):
        raise DataError(f"{ctx}:reactions 应为对象")
    extra = set(reactions) - _REACTION_KEYS
    if extra:
        raise DataError(f"{ctx}:reactions 含未知键 {sorted(extra)},允许 {sorted(_REACTION_KEYS)}")
    for k in ("block_prob", "antiair_prob", "super_prob", "projectile_jump_prob"):
        v = _num(_need(reactions, k, f"{ctx}:reactions"), f"{ctx}:reactions.{k}")
        if not 0 <= v <= 1:
            raise DataError(f"{ctx}:reactions.{k} 应为 0~1")
    adist = _int(_need(reactions, "antiair_dist", f"{ctx}:reactions"), f"{ctx}:reactions.antiair_dist")
    if adist <= 0:
        raise DataError(f"{ctx}:reactions.antiair_dist 应 >0")

    conservative = _need(d, "conservative", ctx)
    if not isinstance(conservative, dict):
        raise DataError(f"{ctx}:conservative 应为对象")
    hb = _int(
        _need(conservative, "own_health_below", f"{ctx}:conservative"), f"{ctx}:conservative.own_health_below"
    )
    if hb < 0:
        raise DataError(f"{ctx}:conservative.own_health_below 应 >=0")
    bb = _num(_need(conservative, "block_bonus", f"{ctx}:conservative"), f"{ctx}:conservative.block_bonus")
    if not 0 <= bb <= 1:
        raise DataError(f"{ctx}:conservative.block_bonus 应为 0~1")

    return AiCfg(
        seed=seed, reaction_interval=interval,
        bands={"far": far, "close": close}, weights=weights,
        reactions=dict(reactions), conservative=dict(conservative),
    )


# ---------- 对外入口 ----------


@dataclass(frozen=True)
class GameData:
    moves: dict
    system: SystemCfg
    ai: AiCfg


def load_moves() -> dict:
    return build_moves(_load_json("terry.json"))


def load_system() -> SystemCfg:
    return build_system(_load_json("system.json"))


def load_ai() -> AiCfg:
    return build_ai(_load_json("ai.json"))


def load_all() -> GameData:
    return GameData(load_moves(), load_system(), load_ai())
