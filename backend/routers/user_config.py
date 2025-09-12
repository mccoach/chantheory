# backend/routers/user_config.py  # 用户配置路由
# ==============================
# 说明：用户配置路由
# - GET /api/user/config：读取当前配置（config.json）
# - PUT /api/user/config：更新配置（部分字段），并应用到运行时（含 DB 路径迁移）
# - 启动时会由 app.py 调用 config.start_watcher()，支持外部编辑自动生效
# - 本次改动：异常统一 http_500_from_exc；透传 trace_id
# ==============================

from __future__ import annotations  # 启用前置注解

# 第三方
from fastapi import APIRouter, Body, Request  # 路由、请求体、请求对象

# 标准库
from typing import Dict, Any  # 类型注解

# 项目内
from backend.services.config import get_config, set_config  # 配置服务
from backend.utils.errors import http_500_from_exc  # 错误门面

# 创建路由器
router = APIRouter(prefix="/api/user", tags=["user-config"])  # 前缀 /api/user

@router.get("/config")  # GET /api/user/config
def api_get_config(request: Request) -> Dict[str, Any]:  # 函数声明
    """读取当前配置"""  # 说明
    tid = request.headers.get("x-trace-id")  # trace_id
    try:
        return {"ok": True, "config": get_config(), "trace_id": tid}  # 返回配置
    except Exception as e:  # 异常
        raise http_500_from_exc(e, trace_id=tid)  # 统一错误

@router.put("/config")  # PUT /api/user/config
def api_put_config(request: Request, patch: Dict[str, Any] = Body(..., embed=False)) -> Dict[str, Any]:
    """更新配置（部分字段），并立即应用"""  # 说明
    tid = request.headers.get("x-trace-id")  # trace_id
    try:
        merged = set_config(patch or {})  # 合并并应用
        return {"ok": True, "config": merged, "trace_id": tid}  # 返回结果
    except Exception as e:  # 异常
        raise http_500_from_exc(e, trace_id=tid)  # 统一错误
