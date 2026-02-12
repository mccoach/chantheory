# backend/routers/server_identity.py
# ==============================
# GET /api/server/identity
# After Hours Bulk v2.1.2 推荐接口
# ==============================

from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter

from backend.services.server_identity import get_backend_instance_id, get_server_time_iso

router = APIRouter(prefix="/api/server", tags=["server"])


@router.get("/identity")
async def api_server_identity() -> Dict[str, Any]:
    return {
        "ok": True,
        "backend_instance_id": get_backend_instance_id(),
        "server_time": get_server_time_iso(),
    }
