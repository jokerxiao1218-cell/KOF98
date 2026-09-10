#!/usr/bin/env bash
cd "$(dirname "$0")"
# 屏蔽系统环境变量(如 ROS)对 venv 的污染——mota50/sheepandsheep 同款
unset PYTHONPATH
exec .venv/bin/python game/main.py
