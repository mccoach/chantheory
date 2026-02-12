# backend/utils/executor_identity.py
# ==============================
# 说明：执行器实例身份（进程级）
#
# 设计目的：
#   - 提供一个与“执行器实现细节”解耦的进程级 executor_instance_id；
#   - 避免 task_events <-> unified_sync_executor <-> data_recipes 的循环导入；
#   - 该 ID 在进程生命周期内固定，用于 After Hours Bulk 的 runtime.executor_instance_id
#     与“重启 stale 纠偏”判定。
# ==============================

from __future__ import annotations

import uuid

_EXECUTOR_INSTANCE_ID: str = str(uuid.uuid4())


def get_executor_instance_id() -> str:
    """获取当前进程的执行器实例ID（进程生命周期内固定）。"""
    return _EXECUTOR_INSTANCE_ID
