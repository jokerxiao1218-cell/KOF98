"""conftest.py — 考场环境契约(batch G 补)。

钉死默认真图注册表为"无真图"回退态:机器上装没装
game/sprites/terry/manifest.json 不许影响考卷结果——否则同一套题
在新鲜 clone 上绿、在本机上红,考试成绩取决于环境而非代码。

分工不变:
  * test_art/test_anim/test_ui 等经 assets.sprite 考的是**程序纸娃娃
    (回退路径)**,环境固定为无真图;
  * test_sprites 用注入注册表考**真图路径**(含 assets 集成端到端),
    自己 monkeypatch,不受本钉死影响。
断言零改动,只固定考场环境。
"""
import pytest

from game import sprites


@pytest.fixture(scope="session", autouse=True)
def _pin_registry_to_fallback(tmp_path_factory):
    empty = sprites.RealSprites(tmp_path_factory.mktemp("no_sprites"))
    sprites._registry = empty          # load() 在空目录上 = 合法回退态
    yield
