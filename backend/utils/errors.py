# backend/utils/errors.py
# ==============================
# 说明：统一错误与响应工具
# - 定义应用级错误 AppError（带 code/message）
# - 提供将异常转换为 FastAPI HTTPException 的工具
# - DEBUG 开关由 settings 控制（生产隐藏回溯）
# ==============================

from __future__ import annotations  # 兼容注解
# 标准库
import traceback  # 堆栈
from typing import Optional, Dict, Any  # 类型提示
# 第三方
from fastapi import HTTPException  # FastAPI 异常
# 项目内
from backend.settings import settings  # 配置

class AppError(Exception):
    """应用级错误（带 code/message，用于业务可预期错误）"""
    def __init__(self, code: str, message: str):
        super().__init__(message)  # 传给基类
        self.code = code  # 错误码
        self.message = message  # 错误信息

def http_500_from_exc(e: Exception, trace_id: Optional[str] = None) -> HTTPException:
    """将任意异常转换为 HTTP 500，DEBUG 时包含回溯，非 DEBUG 返回通用对象"""
    if isinstance(e, AppError):  # 应用级错误可用 400/422 更合适（此处统一转 500 由上层决定）
        payload: Dict[str, Any] = {"code": e.code, "message": e.message, "trace_id": trace_id}  # 负载
        return HTTPException(status_code=500, detail=payload)  # 抛出
    if settings.debug:  # 调试模式
        payload = {"code": "INTERNAL", "message": str(e), "trace": traceback.format_exc(), "trace_id": trace_id}  # 包含回溯
    else:  # 生产模式
        payload = {"code": "INTERNAL", "message": "internal error", "trace_id": trace_id}  # 隐藏细节
    return HTTPException(status_code=500, detail=payload)  # 返回 HTTP 异常
