"""game/main.py — 启动入口(batch B:接 ui.App 主循环,替换 batch 0 占位)。

双跑法样板(mota50/sheepandsheep 同款):
  * run.sh → .venv/bin/python game/main.py 真机窗口;
  * 无头测试不经过本文件(App.step 直接驱动)。
"""
import sys
from pathlib import Path

if __package__ in (None, ""):  # 兼容 `python game/main.py` 直接跑
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.core import data
from game.ui import App


def main() -> int:
    # 数据先于窗口加载:三份 JSON 校验失败在这里就明确报错退出(不许静默)
    data.load_all()
    App(vs_ai=True).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
