"""tests/test_fighter.py — Fighter 状态机逐帧断言(设计文档 §6 test_fighter 组)。

帧语义(与实现约定一致,不与生产代码共享逻辑):
  * 按下按钮的那次 step 结束时招内帧号=0;之后每次 step +1。
  * apply_hit 是帧间调用(match 结算阶段),stun=17 → 之后第 17 次 step
    仍处于硬直、第 18 次恢复。
数值一律从 terry.json / system.json 加载值断言,不硬编码。
"""
import pytest

from game.core import physics
from game.core import types as T
from game.core.data import load_moves, load_system
from game.core.fighter import Fighter

EMPTY = T.EMPTY_TICK


@pytest.fixture(scope="module")
def cfg():
    return load_system()


@pytest.fixture(scope="module")
def moves():
    return load_moves()


# ---------- 测试内合成小工具(不建新文件) ----------


def mk(cfg, moves, side=T.Side.P1):
    return Fighter(cfg, moves, side)


def mk_hit(cfg, moves, move_id="st_C", kind="hit", **over):
    """按契约语义合成 HitResult:block 时 damage=chip、stun=blockstun。"""
    m = moves[move_id]
    blocked = kind == "block"
    d = dict(
        attacker=T.Side.P2,
        victim=T.Side.P1,
        kind=kind,
        move=move_id,
        damage=m.chip if blocked else m.damage,
        hitstop=cfg.hitstop.block_normal if blocked else cfg.hitstop.hit_normal,
        stun=m.blockstun if blocked else m.hitstun,
        pushback=m.pushback_block if blocked else m.pushback_hit,
        knockdown="none" if blocked else m.knockdown,
        gauge_attacker=0 if blocked else m.gauge_gain,
        gauge_victim=cfg.gauge.on_block if blocked else cfg.gauge.on_hit_taken,
        juggle_vy=0.0,
    )
    d.update(over)
    return T.HitResult(**d)


def press(*btns):
    return T.Tick(frozenset(), frozenset(btns), frozenset())


def hold(*dirs):
    return T.Tick(frozenset(dirs), frozenset(), frozenset())


def spec(mid):
    return T.FrameTriggers((mid,), False, False)


def idle_view(cfg, moves):
    return Fighter(cfg, moves, T.Side.P2).view()


# ---------- 普通技逐帧(st_C / st_A / cr_D) ----------


def test_st_c_frame_by_frame(cfg, moves):
    """st_C:窗 [start..end] 帧有判定、之外无;total 步后回 idle。

    为什么这条是核心:startup/active/recovery 全由 JSON 驱动,
    逐帧断言等于验证"帧号推进+窗匹配"两个机制同时正确。
    """
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)  # 第 0 帧
    assert f.state == "attack" and f.snapshot().move_id == "st_C"
    w = moves["st_C"].windows[0]
    for k in range(moves["st_C"].total):
        assert f.attack_frame() == k, k
        aa = f.active_attack()
        if w.start <= k <= w.end:
            assert aa is not None, k
            assert aa.window_index == 0 and aa.frame == k
        else:
            assert aa is None, k
        if k + 1 < moves["st_C"].total:
            f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 第 total 次 step 收招
    assert f.state == "idle" and f.active_attack() is None


def test_st_c_world_hitbox(cfg, moves):
    """攻击框世界化:x 平移到脚底 + 面右不镜像(P1 x=248)。

    契约:world_hit = 窗内 Box 按 facing 镜像后平移到世界坐标。
    """
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    for _ in range(moves["st_C"].windows[0].start):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    aa = f.active_attack()
    assert aa is not None
    (b,) = aa.world_hit
    src = moves["st_C"].windows[0].hit[0]
    assert (b.x1, b.x2) == (f.x + src.x1, f.x + src.x2)
    assert (b.y1, b.y2) == (f.y + src.y1, f.y + src.y2)  # y 也世界化(跳攻击)


def test_st_c_world_hitbox_facing_left(cfg, moves):
    # P2 面左:框镜像(x 取负),攻击朝 -x 方向伸出
    f = mk(cfg, moves, T.Side.P2)
    opp = Fighter(cfg, moves, T.Side.P1).view()
    assert f.facing == -1
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    for _ in range(moves["st_C"].windows[0].start):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    aa = f.active_attack()
    (b,) = aa.world_hit
    src = moves["st_C"].windows[0].hit[0]
    assert (b.x1, b.x2) == (f.x - src.x2, f.x - src.x1)  # mirrored


def test_st_a_and_cr_d_windows(cfg, moves):
    # 同一机制在另外两招上再验(轻拳 startup 3 / 扫堂腿 low+sweep)
    for name, btn, dirset in (
        ("st_A", T.Btn.A, frozenset()),
        ("cr_D", T.Btn.D, frozenset({T.Dir.D})),
    ):
        f = mk(cfg, moves)
        opp = idle_view(cfg, moves)
        if dirset:
            f.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)  # 先蹲下
        f.step(T.EMPTY_TRIGGERS, T.Tick(dirset, frozenset({btn}), frozenset()), opp)
        assert f.snapshot().move_id == name
        w = moves[name].windows[0]
        for k in range(moves[name].total):
            assert (f.active_attack() is not None) == (w.start <= k <= w.end), (name, k)
            if k + 1 < moves[name].total:
                f.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)


# ---------- 受击硬直:输入无效 + 缓冲续发 ----------


def test_hitstun_blocks_all_input(cfg, moves):
    """hitstun 期间喂满键盘(方向+四钮+必杀+前冲)状态纹丝不动。

    "纹丝不动"包括 x:硬直中的任何 tick 都不许产生位移(被推由 apply_hit
    在帧间完成)。第 18 次 step 恢复(契约:stun=17 → 17 帧内不变)。
    """
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    stun = moves["st_C"].hitstun
    f.apply_hit(mk_hit(cfg, moves, "st_C", stun=stun))
    assert f.state == "hit_stand"
    x0 = f.x
    crazy = T.Tick(
        frozenset({T.Dir.L, T.Dir.R, T.Dir.U, T.Dir.D}),
        frozenset({T.Btn.A, T.Btn.B, T.Btn.C, T.Btn.D}),
        frozenset(),
    )
    chaos = T.FrameTriggers((), True, True)  # 特意不含 specials:纯"输入无效"验证;
    # specials 的缓冲续发行为由 test_buffered_special_autofires_on_recovery 专测
    for i in range(stun):
        f.step(chaos, crazy, opp)
        assert f.state == "hit_stand", i
        assert f.x == x0, i
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 第 stun+1 次 step
    assert f.state == "idle"


def test_buffered_special_autofires_on_recovery(cfg, moves):
    """缓冲续发:硬直中喂的 specials 存入,恢复帧自动触发(超杀照查气)。"""
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.apply_hit(mk_hit(cfg, moves))
    f.step(spec("burn_knuckle_A"), EMPTY, opp)  # 硬直第 1 帧: specials 进 pending
    assert f.state == "hit_stand" and f._pending == "burn_knuckle_A"
    for _ in range(moves["st_C"].hitstun - 1):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 恢复帧:自动续发
    assert f.state == "attack" and f.snapshot().move_id == "burn_knuckle_A"
    assert f.attack_frame() == 0  # 恢复帧即新招第 0 帧


def test_buffered_super_still_needs_gauge(cfg, moves):
    # 缓冲里的超杀同样先查气:气不够丢弃,不回落普通技
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.apply_hit(mk_hit(cfg, moves))
    f.step(spec("power_geyser_C"), EMPTY, opp)
    assert f.gauge < moves["power_geyser_C"].gauge_cost  # 前提:气确实不够
    for _ in range(moves["st_C"].hitstun):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 恢复帧
    assert f.state == "idle"  # 气不够 → 忽略
    f2 = mk(cfg, moves)
    f2.gauge = moves["power_geyser_C"].gauge_cost
    f2.apply_hit(mk_hit(cfg, moves))
    f2.step(spec("power_geyser_C"), EMPTY, opp)
    for _ in range(moves["st_C"].hitstun):
        f2.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f2.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f2.state == "attack" and f2.snapshot().move_id == "power_geyser_C"
    assert f2.gauge == 0


def test_hitstun_crouching_victim_enters_hit_crouch(cfg, moves):
    # 蹲姿受击进 hit_crouch(pose=hit_low),恢复后回 idle
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)
    assert f.state == "crouch"
    f.apply_hit(mk_hit(cfg, moves, "cr_B"))
    assert f.state == "hit_crouch" and f.snapshot().pose == "hit_low"


# ---------- 取消窗 ----------


def test_cancel_from_st_c(cfg, moves):
    """st_C(可取消)在 active/recovery 期喂必杀 specials → 直接切新招。

    帧号从 0 重计;投技不可取消由 cancels 只含 special/super 天然保证。
    """
    for k in (moves["st_C"].windows[0].start, 8, 10, 13):  # 6..13 代表帧
        f = mk(cfg, moves)
        opp = idle_view(cfg, moves)
        f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
        for _ in range(k):
            f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        assert f.snapshot().move_id == "st_C"
        f.step(spec("power_wave_C"), EMPTY, opp)  # 第 k 帧喂取消
        assert f.snapshot().move_id == "power_wave_C", k
        assert f.attack_frame() == 0, k  # 新招 startup 从 0 计
        assert f.state == "attack"


def test_no_cancel_from_st_d(cfg, moves):
    # st_D cancels=[]:同样喂 specials 不切招、帧号照常推进
    assert moves["st_D"].cancels == ()
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.D), opp)
    for _ in range(moves["st_D"].windows[0].start):  # 走到 active 前夕
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(spec("power_wave_C"), EMPTY, opp)
    assert f.snapshot().move_id == "st_D"
    assert f.attack_frame() == moves["st_D"].windows[0].start + 1


def test_cancel_uses_gauge_for_super(cfg, moves):
    # st_C 取消进超杀:气够 → 切 + 扣气
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.gauge = moves["power_geyser_C"].gauge_cost
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    for _ in range(moves["st_C"].windows[0].start):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(spec("power_geyser_C"), EMPTY, opp)
    assert f.snapshot().move_id == "power_geyser_C"
    assert f.gauge == 0


# ---------- 小跳 / 大跳 ----------


def _run_jump(f, opp, cfg, hold_u_frames):
    """跑一遍完整跳:返回 (滞空帧数, 最高点)。"""
    tu = hold(T.Dir.U)
    f.step(T.EMPTY_TRIGGERS, tu, opp)  # 进 prejump(帧 0)
    assert f.state == "prejump"
    for _ in range(cfg.jump.prejump - 2):
        f.step(T.EMPTY_TRIGGERS, tu, opp)
    # 第 3 帧起松开 U(小跳)或继续按住(大跳)
    tail = tu if hold_u_frames else EMPTY
    f.step(T.EMPTY_TRIGGERS, tail, opp)  # 第 prejump-1 帧
    f.step(T.EMPTY_TRIGGERS, tail, opp)  # timer<=1 → 起跳步
    assert f.state == "air", f.state
    # 起跳步(prejump→air 转移)的物理段已按 air 积分一次 = 滞空第 1 帧
    frames, peak = 1, f.y
    while f.state == "air":
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        frames += 1
        peak = max(peak, f.y)
    return frames, peak


def test_small_jump(cfg, moves):
    """prejump 第 3 帧松开上 → 小跳:vy0=small_vy0(用滞空帧数+跳高证明)。

    独立复算:跳高 = vy0^2/(2|g|)(连续公式,梯形积分误差亚像素);
    滞空帧数用 physics.jump_airtime 同源积分的权威值。
    """
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    frames, peak = _run_jump(f, opp, cfg, hold_u_frames=False)
    vy0 = cfg.jump.small_vy0
    assert abs(peak - vy0 * vy0 / (2 * abs(cfg.gravity))) <= 2.0
    assert frames == physics.jump_airtime(vy0, cfg)
    assert f.state == "idle"  # 空跳落地 lag=cfg.jump.air_lag(=0)


def test_big_jump(cfg, moves):
    # 按住 U → 大跳:8.0²/(2·0.35)≈91.4px,误差 <=2px;滞空精确帧数
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    frames, peak = _run_jump(f, opp, cfg, hold_u_frames=True)
    vy0 = cfg.jump.big_vy0
    assert abs(peak - vy0 * vy0 / (2 * abs(cfg.gravity))) <= 2.0
    assert frames == physics.jump_airtime(vy0, cfg)
    assert f.state == "idle"


def test_air_attack_lands_with_lag(cfg, moves):
    # 跳中按 C 出 j_C:判定到落地(end=-1),落地 lag=air_attack_land_lag(2)
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    for _ in range(cfg.jump.prejump + 1):
        f.step(T.EMPTY_TRIGGERS, hold(T.Dir.U), opp)
    assert f.state == "air"
    vy_kept = f.vy
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    assert f.snapshot().move_id == "j_C" and f.state == "attack"
    # 出招瞬间速度保留:出招步的物理段继续正常积分(vy 按重力衰减一格)
    assert f.vy == pytest.approx(vy_kept + cfg.gravity)
    saw_active = False
    while f.state == "attack":
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        saw_active = saw_active or f.active_attack() is not None
    assert saw_active  # 空中窗确实挂出过
    assert f.state == "land" and f._timer == cfg.jump.air_attack_land_lag
    for _ in range(cfg.jump.air_attack_land_lag):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.state == "idle"


# ---------- 投技 ----------


def _throw_tick(cfg, moves):
    # 前+C(面朝右:前=R);投招与按钮从 JSON 读,不硬编码
    mv = moves["throw_fwd"]
    return T.Tick(
        frozenset({T.Dir.R if True else T.Dir.L}),
        frozenset({T.Btn[mv.input["button"]]}),
        frozenset(),
    )


def test_throw_grab_in_range(cfg, moves):
    """距离恰好 = throw_range → throw_grab;受方状态可被外部观察。

    抓取成立后受方进 thrown 由上层(match 调 resolve_throw+apply_hit)
    完成;fighter 侧只保证攻方进 throw_grab 并按 total 帧播放。
    """
    f = mk(cfg, moves)
    o = mk(cfg, moves, T.Side.P2)
    o.x = f.x + moves["throw_fwd"].throw_range
    f.step(T.EMPTY_TRIGGERS, _throw_tick(cfg, moves), o.view())
    assert f.state == "throw_grab"
    assert o.state == "idle"  # 受方此刻仍正常(上层尚未结算)
    assert f.snapshot().pose == "throw_grab"  # 状态可被外部观察
    for _ in range(moves["throw_fwd"].total - 1):
        f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
        assert f.state == "throw_grab"
    f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
    assert f.state == "idle"  # 3+2+20 = total 帧播完


def test_throw_whiff_out_of_range(cfg, moves):
    # 距离 throw_range+1 → whiff,播 12 帧不抓人
    from game.core.fighter import THROW_WHIFF_FRAMES

    f = mk(cfg, moves)
    o = mk(cfg, moves, T.Side.P2)
    o.x = f.x + moves["throw_fwd"].throw_range + 1
    f.step(T.EMPTY_TRIGGERS, _throw_tick(cfg, moves), o.view())
    assert f.state == "throw_whiff"
    assert o.state == "idle"  # 没抓到人
    for _ in range(THROW_WHIFF_FRAMES - 1):
        f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
        assert f.state == "throw_whiff"
    f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
    assert f.state == "idle"


def test_throw_whiff_vs_hitstun_victim(cfg, moves):
    # 对手 in_hitstun(不可抓)→ whiff,即使距离够
    f = mk(cfg, moves)
    o = mk(cfg, moves, T.Side.P2)
    o.apply_hit(
        T.HitResult(
            attacker=T.Side.P1, victim=T.Side.P2, kind="hit", move="st_C",
            damage=moves["st_C"].damage, hitstop=cfg.hitstop.hit_normal,
            stun=moves["st_C"].hitstun, pushback=moves["st_C"].pushback_hit,
            knockdown="none", gauge_attacker=0, gauge_victim=0, juggle_vy=0.0,
        )
    )
    assert o.view().in_hitstun and not o.can_be_thrown()
    o.x = f.x + moves["throw_fwd"].throw_range
    f.step(T.EMPTY_TRIGGERS, _throw_tick(cfg, moves), o.view())
    assert f.state == "throw_whiff"


def test_thrown_victim_script(cfg, moves):
    """受方被投:pushback 带符号直接位移 40px,落地进 knockdown。"""
    f = mk(cfg, moves)
    sign = 40.0 * 1.0 * -1  # combat:40 * dir(fwd=1) * 投手 facing(P2=-1)
    thr = T.HitResult(
        attacker=T.Side.P2, victim=T.Side.P1, kind="hit", move="throw_fwd",
        damage=moves["throw_fwd"].damage, hitstop=cfg.hitstop.hit_throw,
        stun=0, pushback=sign, knockdown="hard",
        gauge_attacker=0, gauge_victim=0, juggle_vy=0.0,
    )
    x0 = f.x
    f.apply_hit(thr)
    assert f.state == "thrown"
    assert f.x == pytest.approx(x0 + sign)  # 不再乘朝向(契约)
    opp = idle_view(cfg, moves)
    while f.state == "thrown":
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.state == "knockdown"  # 落地进倒地链,不经过 hitstun


def test_can_be_thrown_matrix(cfg, moves):
    """可被抓矩阵:正常态可投;浮空/硬直/倒地/攻击/投技中不可投。"""
    opp = idle_view(cfg, moves)
    yes = mk(cfg, moves)
    assert yes.can_be_thrown()
    yes.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)  # 蹲
    assert yes.can_be_thrown()  # 蹲可被投
    yes2 = mk(cfg, moves)
    yes2.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)  # 后走(=站防)
    assert yes2.can_be_thrown()  # 防御态可被投(KOF 惯例)

    no = mk(cfg, moves)
    no.apply_hit(mk_hit(cfg, moves))  # hitstun
    assert not no.can_be_thrown()
    no2 = mk(cfg, moves)
    no2.apply_hit(mk_hit(cfg, moves, juggle_vy=cfg.juggle_bounce_vy))
    assert not no2.can_be_thrown()  # 浮空不可投
    no3 = mk(cfg, moves)
    no3.step(T.EMPTY_TRIGGERS, press(T.Btn.A), opp)  # 攻击中
    assert not no3.can_be_thrown()
    no4 = mk(cfg, moves)
    no4.apply_hit(mk_hit(cfg, moves, "cr_D"))  # sweep → 倒地链
    assert no4.state == "knockdown" and not no4.can_be_thrown()


# ---------- 浮空链 ----------


def test_juggle_airborne_lands_knockdown(cfg, moves):
    """空中被打:juggle_vy>0 → hit_air 弹起 → fall → 落地 knockdown。"""
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.apply_hit(mk_hit(cfg, moves, juggle_vy=cfg.juggle_bounce_vy))
    assert f.state == "hit_air" and f.vy == cfg.juggle_bounce_vy
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.y > 0.0  # 开始上升
    saw_fall = False
    while f.state != "knockdown":
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        saw_fall = saw_fall or f.state == "fall"
    assert saw_fall  # 上升→下落两段都经历过
    assert f.y == 0.0


def test_wakeup_invuln_frames(cfg, moves):
    """起身 24 帧、前 invuln_frames(8)帧无敌(§4.3)。"""
    from game.core.fighter import KNOCKDOWN_LYDOWN

    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.apply_hit(mk_hit(cfg, moves, "cr_D"))  # sweep 倒地
    while f.state != "wakeup":
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    invuln = 0
    while f.state == "wakeup":
        # 先判后 step:进入 wakeup 的那次 step(倒地→起身的转移步)就是
        # 起身第 1 帧,前 invuln_frames 帧从它数起
        if f.view().invulnerable:
            invuln += 1
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert invuln == cfg.wakeup.invuln_frames
    assert f.state == "idle"
    # 躺地段同样无敌(裁量:倒地不可被追打)
    f2 = mk(cfg, moves)
    f2.apply_hit(mk_hit(cfg, moves, "cr_D"))
    assert f2.state == "knockdown" and f2.view().invulnerable


def test_move_invuln_frames(cfg, moves):
    # 招式无敌区间:升龙撞 invuln [0,7] → 帧 0..7 无敌、第 8 帧起不无敌
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    inv = moves["rising_tackle_A"].invuln[0]
    f.step(spec("rising_tackle_A"), EMPTY, opp)
    for k in range(moves["rising_tackle_A"].total):
        assert f.view().invulnerable == (inv[0] <= k <= inv[1]), k
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)


# ---------- 防御 ----------


def test_guard_flags(cfg, moves):
    # 按住后 → 站姿防御标志;蹲+后 → 蹲防(guard_stance=crouch)
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)
    assert f.state == "walk_back"  # 拉后 = 后走 + 站防(KOF 惯例)
    v = f.view()
    assert v.guarding and v.guard_stance == "stand"
    f2 = mk(cfg, moves)
    f2.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)
    f2.step(T.EMPTY_TRIGGERS, hold(T.Dir.D, T.Dir.L), opp)
    assert f2.state == "block_crouch"
    v2 = f2.view()
    assert v2.guarding and v2.guard_stance == "crouch"


def test_block_result_applies_chip_and_stun(cfg, moves):
    """防御结算:block → 扣 chip、进 blockstun(blockstun 帧)、被防涨气。"""
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)  # 后走=站防;同时缓存对手 x
    x0 = f.x
    f.apply_hit(mk_hit(cfg, moves, "st_C", kind="block"))
    assert f.state == "blockstun"
    assert f.health == cfg.health - moves["st_C"].chip
    assert f.gauge == cfg.gauge.on_block
    for _ in range(moves["st_C"].blockstun):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        assert f.state == "blockstun"
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)  # 恢复帧仍拉后 → 保持防御
    assert f.state == "block_stand"
    # 推背:远离攻方(攻方在右 x=392)→ 向左退 pushback_block
    assert f.x == pytest.approx(x0 - moves["st_C"].pushback_block)


# ---------- 气量 ----------


def test_gauge_gains(cfg, moves):
    # 攻方命中涨气(move.gauge_gain)、受方挨打涨气(gauge.on_hit_taken)
    f = mk(cfg, moves)
    f.on_attack_landed(mk_hit(cfg, moves))
    assert f.gauge == moves["st_C"].gauge_gain
    assert f.combo == 1
    v = mk(cfg, moves)
    v.apply_hit(mk_hit(cfg, moves))
    assert v.gauge == cfg.gauge.on_hit_taken
    # 上限夹紧:气已满再加 → 不超 max
    full = mk(cfg, moves)
    full.gauge = cfg.gauge.max
    full.on_attack_landed(mk_hit(cfg, moves))
    assert full.gauge == cfg.gauge.max


def test_super_gauge_gate(cfg, moves):
    # 气不足:不出招、不扣气(不回落普通技);气满:出招且清空
    opp = idle_view(cfg, moves)
    cost = moves["power_geyser_C"].gauge_cost
    f = mk(cfg, moves)
    f.gauge = cost - 1
    f.step(spec("power_geyser_C"), EMPTY, opp)
    assert f.state == "idle" and f.gauge == cost - 1
    g = mk(cfg, moves)
    g.gauge = cost
    g.step(spec("power_geyser_C"), EMPTY, opp)
    assert g.state == "attack" and g.snapshot().move_id == "power_geyser_C"
    assert g.gauge == 0


def test_health_floor(cfg, moves):
    # 血下限 0:连吃大伤害不许为负
    f = mk(cfg, moves)
    for _ in range(10):
        f.apply_hit(mk_hit(cfg, moves, "power_geyser_C", juggle_vy=0.0))
    assert f.health == 0


# ---------- run / dash_back / 走速 ----------


def test_run_speed_frame_by_frame(cfg, moves):
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.FrameTriggers((), True, False), hold(T.Dir.R), opp)
    assert f.state == "run"
    x0 = f.x
    for i in range(1, 6):
        f.step(T.EMPTY_TRIGGERS, hold(T.Dir.R), opp)
        assert f.x == pytest.approx(x0 + cfg.run.speed * i)  # 4.6px/f 沿 facing
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 松开前 → 制动
    assert f.state == "run_stop"
    for _ in range(cfg.run.stop_frames - 1):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        assert f.state == "run_stop"
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.state == "idle"  # run_stop = cfg.run.stop_frames 帧


def test_dash_back_arc(cfg, moves):
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.FrameTriggers((), False, True), hold(T.Dir.L), opp)
    assert f.state == "dash_back"
    # 触发步的物理段已按弧线积分一格(vy0 已衰减一帧重力)
    assert f.vy == pytest.approx(cfg.dash_back.vy0 + cfg.gravity)
    assert f.vx == pytest.approx(-f.facing * cfg.dash_back.vx)  # 向身后
    peak = f.y
    for _ in range(cfg.dash_back.frames - 1):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        assert f.state == "dash_back"
        peak = max(peak, f.y)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.state == "idle"  # 22 帧固定弧线到点结束
    assert abs(peak - cfg.dash_back.vy0 ** 2 / (2 * abs(cfg.gravity))) <= 2.0


def test_walk_speeds_frame_by_frame(cfg, moves):
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.R), opp)
    assert f.state == "walk_fwd"
    x0 = f.x
    for i in range(1, 4):
        f.step(T.EMPTY_TRIGGERS, hold(T.Dir.R), opp)
        assert f.x == pytest.approx(x0 + cfg.walk.fwd * i)
    b = mk(cfg, moves)
    b.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)
    assert b.state == "walk_back"
    xb = b.x
    for i in range(1, 4):
        b.step(T.EMPTY_TRIGGERS, hold(T.Dir.L), opp)
        assert b.x == pytest.approx(xb - cfg.walk.back * i)  # back 存正数大小


# ---------- 墙角(fighter 层) ----------


def test_corner_victim_stays_in_stage(cfg, moves):
    """受方贴右墙被推:一步不出界(受方侧;攻方回推量由 match 应用,
    pushback_resolve 的攻方回推在 test_physics 已独立验证)。"""
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 缓存对手 x(推背方向用)
    f.x = float(cfg.stage.width)
    f.apply_hit(mk_hit(cfg, moves))  # 推背朝右(远离左侧攻方)
    assert f.x == float(cfg.stage.width)
    assert 0.0 <= f.x <= cfg.stage.width


def test_open_ground_pushback_direction(cfg, moves):
    # 空场:受方沿"远离攻方"方向退 pushback(攻方在右 → 向左退)
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # opp.x = 392(右侧)
    x0 = f.x
    f.apply_hit(mk_hit(cfg, moves))
    assert f.x == pytest.approx(x0 - moves["st_C"].pushback_hit)


# ---------- snapshot pose 与结算杂项 ----------


def test_snapshot_poses(cfg, moves):
    """attack 态 pose=move.pose_key;其余态按状态映射(附录 D 键)。"""
    opp = idle_view(cfg, moves)
    f = mk(cfg, moves)
    assert f.snapshot().pose == "idle"
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.R), opp)
    assert f.snapshot().pose == "walk"
    f.step(T.EMPTY_TRIGGERS, hold(T.Dir.D), opp)
    assert f.snapshot().pose == "crouch"
    a = mk(cfg, moves)
    a.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    assert a.snapshot().pose == moves["st_C"].pose_key  # attack → pose_key
    h = mk(cfg, moves)
    h.apply_hit(mk_hit(cfg, moves, juggle_vy=cfg.juggle_bounce_vy))
    assert h.snapshot().pose == "air_hit"
    w = mk(cfg, moves)
    w.perform("win")
    assert w.snapshot().pose == "win"


def test_window_marked_used_after_hit(cfg, moves):
    """一次攻击只结算一次:命中后本窗不再挂出(契约由 fighter 承担)。"""
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), opp)
    for _ in range(moves["st_C"].windows[0].start):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    assert f.active_attack() is not None
    f.on_attack_landed(mk_hit(cfg, moves))
    assert f.active_attack() is None  # 同窗不再命中
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 帧推进后窗仍标记
    assert f.active_attack() is None


def test_combo_resets_when_opp_recovers(cfg, moves):
    """combo 在自己观察到对手脱离受击态时清零(双方都 step 模拟对局)。"""
    f = mk(cfg, moves)  # 攻方
    o = mk(cfg, moves, T.Side.P2)  # 受方
    o.step(T.EMPTY_TRIGGERS, hold(T.Dir.R), f.view())  # 缓存 f 位置
    o.apply_hit(mk_hit(cfg, moves))
    f.on_attack_landed(mk_hit(cfg, moves))
    assert f.combo == 1
    for _ in range(40):
        f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
        o.step(T.EMPTY_TRIGGERS, EMPTY, f.view())
        if o.state == "idle" and f.combo == 0:
            break
    assert f.combo == 0  # 对手恢复 → 连段终止


def test_pending_buffer_capacity_one(cfg, moves):
    # 缓冲续发容量 1:硬直中后一条 specials 覆盖前一条
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    f.apply_hit(mk_hit(cfg, moves))
    f.step(spec("power_wave_A"), EMPTY, opp)
    f.step(spec("burn_knuckle_C"), EMPTY, opp)  # 新的覆盖旧的
    for _ in range(moves["st_C"].hitstun):
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
    f.step(T.EMPTY_TRIGGERS, EMPTY, opp)  # 恢复帧
    assert f.snapshot().move_id == "burn_knuckle_C"


def test_facing_refresh_on_landing(cfg, moves):
    """空中不翻、落地按相对位置刷新朝向(KOF 换边规则,§4.3)。"""
    f = mk(cfg, moves)
    o = mk(cfg, moves, T.Side.P2)
    o.x = 200.0  # 对手已换到左侧
    f.step(T.EMPTY_TRIGGERS, EMPTY, o.view())
    assert f.facing == -1  # 地面立刻转向对手
    f2 = mk(cfg, moves)
    o_right = mk(cfg, moves, T.Side.P2)  # 起跳时对手仍在右侧
    for _ in range(cfg.jump.prejump + 1):
        f2.step(T.EMPTY_TRIGGERS, hold(T.Dir.U), o_right.view())
    assert f2.state == "air" and f2.facing == 1  # 起跳时面右
    o2 = mk(cfg, moves, T.Side.P2)
    o2.x = 100.0  # 对手跳到我方身后
    f2.step(T.EMPTY_TRIGGERS, EMPTY, o2.view())
    assert f2.facing == 1  # 空中不翻
    while f2.state == "air":
        f2.step(T.EMPTY_TRIGGERS, EMPTY, o2.view())
    assert f2.facing == -1  # 落地瞬间刷新


def test_perform_show_states(cfg, moves):
    # win/lose/intro:外部切入,step 空转(位置/状态不变)
    f = mk(cfg, moves)
    x0 = f.x
    f.perform("win")
    for _ in range(5):
        f.step(T.EMPTY_TRIGGERS, press(T.Btn.C), f.view())
    assert f.state == "win" and f.x == x0
    assert f.snapshot().pose == "win"
    f.perform("lose")
    f.perform("intro")
    with pytest.raises(ValueError):
        f.perform("idle")  # 表演态之外不许经 perform 切入


# ---------- until="land" 招(Power Dunk / 爆裂踢) ----------


def test_power_dunk_until_land(cfg, moves):
    """滑行 from_frame 帧后起跳,落地即结束(total 到了也不悬空回 idle)。"""
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    mo = moves["power_dunk_B"].motion
    f.step(spec("power_dunk_B"), EMPTY, opp)
    assert f.state == "attack"
    # 逐帧:每步位移 = vx*facing(until=land 招滑行段与空中段同速),
    # 落地那步(进 land)位移归零,不计
    steps, peak, saw_air = 0, 0.0, False
    guard = 0
    while f.state == "attack" and guard < 100:
        prev = f.x
        f.step(T.EMPTY_TRIGGERS, EMPTY, opp)
        steps += 1
        guard += 1
        peak = max(peak, f.y)
        saw_air = saw_air or f.y > 0.0
        if steps <= mo["from_frame"]:
            # 滑行帧(from_frame 前)水平位移恒为 vx*facing
            assert f.x - prev == pytest.approx(mo["vx"] * f.facing), steps
    assert saw_air
    assert abs(peak - mo["vy0"] ** 2 / (2 * abs(cfg.gravity))) <= 2.0  # 跳高精确
    assert f.state == "land"  # 落地直接进落地流程,不悬空
    assert steps > moves["power_dunk_B"].total  # 滞空超出 total:验证钳帧逻辑


def test_crack_shoot_lifts_on_frame_zero(cfg, moves):
    # from_frame 缺省 0:出招第 0 帧就升空(触发步物理段已积分)
    f = mk(cfg, moves)
    opp = idle_view(cfg, moves)
    mo = moves["crack_shoot_B"].motion
    f.step(spec("crack_shoot_B"), EMPTY, opp)
    assert f.y > 0.0
    assert f.vy == pytest.approx(mo["vy0"] + cfg.gravity)
