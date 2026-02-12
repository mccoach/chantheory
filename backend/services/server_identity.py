# backend/services/server_identity.py
# ==============================
# 后端进程身份（After Hours Bulk v2.1.2 必需）
#
# 职责：
#   - 提供 backend_instance_id（进程启动生成，重启必变）
#   - 提供 server_time（ISO）
# ==============================

from __future__ import annotations

import uuid
from typing import Optional
from backend.utils.time import now_iso

_backend_instance_id: Optional[str] = None


def init_backend_instance_id() -> str:
    global _backend_instance_id
    if _backend_instance_id is None:
        _backend_instance_id = f"BE_{uuid.uuid4().hex[:12]}"
    return _backend_instance_id


def get_backend_instance_id() -> str:
    if _backend_instance_id is None:
        return init_backend_instance_id()
    return _backend_instance_id


def get_server_time_iso() -> str:
    return now_iso()
