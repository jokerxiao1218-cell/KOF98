"""tests/test_sprites.py — 真贴图管线(素材系统 v2,设计文档 §11.3)。

跑法:cd ~/kof98 && ./test.sh
全部用**合成贴图**自测(测试内用 pygame 画小格 PNG + 临时 manifest),
零版权素材;版权图目录 game/sprites/ 被 gitignore,本套测试不依赖它
存在与否(第 10 条用空目录钉死回退路径的确定性)。
"""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

import game.core.types as T  # noqa: E402
from game import poses, sprites  # noqa: E402
from game.sprites import RealSprites, SpriteError  # noqa: E402

MARKERS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
           (255, 0, 255), (0, 255, 255)]


def make_sheet_png(path, cols, rows, fw, fh):
    """合成 sheet:第 i 格左上角 4×4 填第 i 个标记色,其余透明。"""
    surf = pygame.Surface((cols * fw, rows * fh), pygame.SRCALPHA)
    for i in range(cols * rows):
        r, c = divmod(i, cols)
        cell = pygame.Surface((fw, fh), pygame.SRCALPHA)
        for x in range(4):
            for y in range(4):
                cell.set_at((x, y), (*MARKERS[i % len(MARKERS)], 255))
        surf.blit(cell, (c * fw, r * fh))
    pygame.image.save(surf, str(path))


def build_dir(tmp_path, manifest, sheets=()):
    """建一个临时真图目录:manifest + 若干合成 sheet PNG。"""
    d = tmp_path / "terry"
    d.mkdir(parents=True, exist_ok=True)
    for name, args in sheets:
        make_sheet_png(d / name, *args)
    (d / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return d


STRIP_MANIFEST = {
    "scale": 1,
    "poses": {
        "idle": {"sheet": "s.png", "strip": {
            "count": 4, "fw": 20, "fh": 30, "ax": 10, "ay": 30}},
    },
}


# ---------- 加载与切格 ----------


def test_strip_loading_anchor_and_frames(tmp_path):
    reg = RealSprites(build_dir(tmp_path, STRIP_MANIFEST,
                                [("s.png", (4, 1, 20, 30))]))
    reg.load()
    assert reg.has("idle") and reg.frame_count("idle") == 4
    assert not reg.has("walk")  # manifest 没配的姿势 → 回退标记
    for f in range(4):
        s = reg.surface("idle", f, 1, "P1")
        assert s.get_size() == (20, 30)  # 脚底=画布底、水平居中(对称锚)
        assert s.get_at((1, 1))[:3] == MARKERS[f]  # 第 f 格的标记色
    assert reg.surface("idle", 4, 1, "P1").get_at((1, 1))[:3] == MARKERS[0]


def test_asymmetric_anchor_centers_foot(tmp_path):
    """锚点不在正中(ax=15/格宽20)→ 衬底画布加宽,脚底中心仍水平居中。"""
    m = {"poses": {"st_C": {"sheet": "s.png", "frames": [
        {"x": 0, "y": 0, "w": 20, "h": 30, "ax": 15, "ay": 30}]}}}
    reg = RealSprites(build_dir(tmp_path, m, [("s.png", (1, 1, 20, 30))]))
    reg.load()
    s = reg.surface("st_C", 0, 1, "P1")
    assert s.get_size() == (30, 30)  # 2*max(ax, w-ax)=30
    assert s.get_at((1, 1))[:3] == MARKERS[0]  # 帧 blit 在画布左上


def test_scale_down_by_two(tmp_path):
    m = {"scale": 2, "poses": {"idle": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 40, "fh": 60, "ax": 20, "ay": 60}}}}
    reg = RealSprites(build_dir(tmp_path, m, [("s.png", (1, 1, 40, 60))]))
    reg.load()
    s = reg.surface("idle", 0, 1, "P1")
    assert s.get_size() == (20, 30)  # 缩回原尺寸
    assert s.get_at((1, 1))[:3] == MARKERS[0]


def test_rows_grid(tmp_path):
    m = {"poses": {"run": {"sheet": "s.png", "strip": {
        "count": 6, "fw": 20, "fh": 30, "ax": 10, "ay": 30, "rows": 3}}}}
    # rows=3 → 每行 ceil(6/3)=2 格:sheet 造 2 列 × 3 行
    reg = RealSprites(build_dir(tmp_path, m, [("s.png", (2, 3, 20, 30))]))
    reg.load()
    assert reg.frame_count("run") == 6
    # 第 5 格(i=4)在第 3 行第 1 列 → 行列切格没串
    assert reg.surface("run", 4, 1, "P1").get_at((1, 1))[:3] == MARKERS[4]


def test_facing_flip_mirrors_marker(tmp_path):
    reg = RealSprites(build_dir(tmp_path, STRIP_MANIFEST,
                                [("s.png", (4, 1, 20, 30))]))
    reg.load()
    right = reg.surface("idle", 0, 1, "P1")
    left = reg.surface("idle", 0, -1, "P1")
    assert left.get_at((18, 1))[:3] == MARKERS[0]   # 标记被镜像到右边
    assert left.get_at((1, 1))[:3] == right.get_at((18, 1))[:3]


def test_p2_swap_lut(tmp_path):
    m = {"scale": 1, "swap_p2": [[[255, 0, 0], [0, 0, 255]]],
         "poses": {"idle": {"sheet": "s.png", "strip": {
             "count": 1, "fw": 20, "fh": 30, "ax": 10, "ay": 30}}}}
    reg = RealSprites(build_dir(tmp_path, m, [("s.png", (1, 1, 20, 30))]))
    reg.load()
    assert reg.surface("idle", 0, 1, "P1").get_at((1, 1))[:3] == (255, 0, 0)
    assert reg.surface("idle", 0, 1, "P2").get_at((1, 1))[:3] == (0, 0, 255)
    assert reg.surface("idle", 0, 1, "P1").get_at((1, 1))[:3] == (255, 0, 0)


# ---------- 回退与错误(不许静默) ----------


def test_absent_dir_is_legit_fallback(tmp_path):
    reg = RealSprites(tmp_path / "nope")
    reg.load()  # 目录不存在:合法回退态,不炸
    assert not reg.pose_keys()
    assert not reg.has("idle")


def test_assets_fallback_procedural(tmp_path, monkeypatch):
    """默认注册表指向空目录 → assets.sprite 走程序纸娃娃(56×100)。"""
    empty = RealSprites(tmp_path / "empty")
    empty.load()
    monkeypatch.setattr(sprites, "_registry", empty)
    from game import assets
    s = assets.sprite("idle", 0, 1, assets.load_palette(T.Side.P1))
    assert s.get_size() == (56, 100)  # 程序绘制画布


def test_assets_real_path_end_to_end(tmp_path, monkeypatch):
    """默认注册表指向合成真图目录 → assets.sprite 返回切格图(集成点)。"""
    reg = RealSprites(build_dir(tmp_path, STRIP_MANIFEST,
                                [("s.png", (4, 1, 20, 30))]))
    reg.load()
    monkeypatch.setattr(sprites, "_registry", reg)
    from game import assets
    import game.core.types as T
    s = assets.sprite("idle", 1, 1, assets.load_palette(T.Side.P1))
    assert s.get_size() == (20, 30)            # 真图路径(非 56×100)
    assert s.get_at((1, 1))[:3] == MARKERS[1]   # 第 1 帧标记
    p2 = assets.sprite("idle", 1, 1, assets.load_palette(T.Side.P2))
    assert p2.get_size() == (20, 30)  # P2 无换色表时原样出图


def test_default_registry_bad_manifest_warns_and_falls_back(
        tmp_path, monkeypatch, capsys):
    """坏 manifest:default_registry 打 stderr 警告 + 整包回退(不静默不炸);
    严格路径(测试/体检直接 load)必须炸。"""
    d = tmp_path / "bad"
    d.mkdir()
    (d / "manifest.json").write_text("{}", encoding="utf-8")  # 缺 poses
    with pytest.raises(SpriteError, match="poses"):
        RealSprites(d).load()  # 严格路径先证明确实会炸
    broken = RealSprites(d)
    monkeypatch.setattr(sprites, "_registry", broken)
    sprites.default_registry()  # 宽恕路径:捕获 → 警告 → 空注册表
    assert not sprites.default_registry().pose_keys()
    assert sprites.default_registry().loaded
    err = capsys.readouterr().err
    assert "sprite_check" in err  # 警告里指路体检脚本


@pytest.mark.parametrize("bad,match", [
    ({"poses": {"walk2": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 20, "fh": 30, "ax": 10, "ay": 30}}}}, "未注册"),
    ({"poses": {"proj_wave": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 20, "fh": 30, "ax": 10, "ay": 30}}}}, "特效"),
    ({"poses": {"idle": {"sheet": "没有.png", "strip": {
        "count": 1, "fw": 20, "fh": 30, "ax": 10, "ay": 30}}}},
     "sheet 文件不存在"),
    ({"poses": {"idle": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 0, "fh": 30, "ax": 0, "ay": 30}}}}, "fw"),
    ({"poses": {"idle": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 20, "fh": 30, "ax": 25, "ay": 30}}}}, "ax"),
    ({"scale": 2, "poses": {"idle": {"sheet": "s.png", "strip": {
        "count": 1, "fw": 21, "fh": 30, "ax": 10, "ay": 30}}}}, "除不尽"),
    ({"scale": "2", "poses": {}}, "scale"),
    ({"poses": {"idle": {"sheet": "s.png"}}}, "strip"),
    ({"poses": {"idle": {"sheet": "s.png", "frames": [
        {"x": 0, "y": 0, "w": 20, "h": 0, "ax": 10, "ay": 0}]}}}, "h"),
])
def test_bad_manifests_raise(tmp_path, bad, match):
    d = tmp_path / "bad"
    d.mkdir()
    if "s.png" in json.dumps(bad):
        make_sheet_png(d / "s.png", 1, 1, 40, 60)
    (d / "manifest.json").write_text(
        json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SpriteError, match=match):
        RealSprites(d).load()


def test_pose_key_must_be_registered_shape(tmp_path):
    """真图姿势键必须 ⊆ poses.POSE_KEYS(打错键名当场报错)。"""
    d = build_dir(tmp_path, STRIP_MANIFEST, [("s.png", (4, 1, 20, 30))])
    reg = RealSprites(d)
    reg.load()
    for key in reg.pose_keys():
        assert key in poses.POSE_KEYS
