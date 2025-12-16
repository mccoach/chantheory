# backend/services/data_recipes/common.py
# ==============================
# 说明：data_recipes 包内部通用小工具
#
# 当前只提供：
#   - bool_param(task, key, default)：从 Task.params 中读取布尔参数。
# ==============================

from __future__ import annotations

from typing import Any

from backend.services.task_model import Task


def bool_param(task: Task, key: str, default: bool = False) -> bool:
    """
    从 Task.params 中读取布尔参数。

    Args:
        task  : Task 对象
        key   : 参数名
        default: 默认值

    Returns:
        bool: 参数转为布尔后的值
    """
    v: Any = task.params.get(key, default)
    return bool(v)