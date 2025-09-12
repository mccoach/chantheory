# backend/routers/storage.py
# ==============================
# 说明：存储管理路由（简化）
# - GET  /api/storage/usage                数据库用量与表行数
# - POST /api/storage/cleanup              清理数据（收口：不再支持 freqs 数组，仅单 freq；freq 为空则使用 '%'）
# - POST /api/storage/cache/cleanup        触发 LRU/TTL 清理缓存（立即执行一次）
# - POST /api/storage/migrate              迁移数据库路径
# - POST /api/storage/vacuum               VACUUM 清理
# - GET  /api/storage/integrity            完整性检查
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 3.8+）

from fastapi import APIRouter, Body, Request  # 导入 FastAPI 路由工具
from typing import Dict, Any, Optional  # 类型注解

# 导入数据库与服务接口
from backend.db.sqlite import (
    get_usage, integrity_check, vacuum_optimize, get_conn,  # 用量/校验/VACUUM/连接
)
from backend.services.storage import cleanup_cache  # 缓存清理服务
from backend.services.config import set_config  # 配置写入（迁移 DB 用）
from backend.utils.errors import http_500_from_exc  # 统一错误包装

# 创建路由器（分组为 storage）
router = APIRouter(prefix="/api/storage", tags=["storage"])

@router.get("/usage")
def api_storage_usage(request: Request) -> Dict[str, Any]:
    """
    用量查看：
    - 返回当前数据库路径、大小与各表行数快照
    """
    tid = request.headers.get("x-trace-id")  # 读取 trace_id（贯通链路）
    try:
        return {"ok": True, "usage": get_usage(), "trace_id": tid}  # 正常返回
    except Exception as e:
        # 异常统一包装为 HTTP 500（生产隐藏堆栈）
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/cache/cleanup")
def api_cache_cleanup(request: Request) -> Dict[str, Any]:
    """
    LRU/TTL 缓存清理：
    - 立即执行一次 cleanup_cache（内部按阈值/TTL 驱动）
    """
    tid = request.headers.get("x-trace-id")  # 链路 ID
    try:
        res = cleanup_cache()  # 执行清理
        return {"ok": True, "result": res, "trace_id": tid}  # 返回结果
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/cleanup")
def api_storage_cleanup(request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    清理数据（收口版）：
    - 不再支持 freqs 数组；仅支持单次清理（传单个 freq）。freq 缺省时使用 '%'（模糊匹配）。
    - 语义：
      * table='cache'：
          - freq 缺省 → freq='%'；未提供 start_ms/end_ms → 删除整分区；提供任一 → 按窗口删除。
      * table='daily'：
          - 需 confirm=true 以避免误删；
          - 对 1d 长期表按窗口删除（start_ms/end_ms 缺省则整表该 symbol）。
    - 参数：
      { table, symbol, freq?, start_ms?, end_ms?, confirm? }
    - 返回：
      { ok, deleted, trace_id }
    """
    tid = request.headers.get("x-trace-id")  # 贯通链路 ID
    try:
        # 读取参数（收口：不再兼容 freqs）
        table = str(payload.get("table", "")).strip().lower()  # 表类型（要求显式传入）
        symbol = str(payload.get("symbol", "")).strip()        # 标的代码
        freq_single = str(payload.get("freq", "")).strip()     # 单个频率（可空）
        start_ms = payload.get("start_ms")                     # 开始毫秒（可空）
        end_ms = payload.get("end_ms")                         # 结束毫秒（可空）
        confirm = bool(payload.get("confirm", False))          # daily 确认

        # 基本校验
        if table not in {"cache", "daily"}:
            return {"ok": False, "error": "table must be 'cache' or 'daily'", "trace_id": tid}
        if not symbol:
            return {"ok": False, "error": "symbol is required", "trace_id": tid}

        # 连接数据库
        conn = get_conn()
        cur = conn.cursor()

        total_deleted = 0  # 删除计数

        # ---- cache 表清理 ---------------------------------------------------
        if table == "cache":
            # freq 为空则使用 '%'（删除该 symbol 下所有 freq）
            fval = freq_single or "%"
            if start_ms is None and end_ms is None:
                # 整分区删除
                cur.execute(
                    "DELETE FROM candles_cache WHERE symbol=? AND freq LIKE ? ESCAPE '\\' AND adjust='none';",
                    (symbol, fval),
                )
                total_deleted += int(cur.rowcount or 0)
                # 删除 meta
                cur.execute(
                    "DELETE FROM cache_meta WHERE symbol=? AND freq LIKE ? ESCAPE '\\' AND adjust='none';",
                    (symbol, fval),
                )
                conn.commit()
                return {"ok": True, "deleted": total_deleted, "trace_id": tid}
            else:
                # 窗口删除
                ts0 = 0 if start_ms is None else int(start_ms)
                ts1 = 2**63 - 1 if end_ms is None else int(end_ms)
                cur.execute(
                    """
                    DELETE FROM candles_cache
                    WHERE symbol=? AND freq LIKE ? ESCAPE '\\' AND adjust='none' AND ts BETWEEN ? AND ?;
                    """,
                    (symbol, fval, ts0, ts1),
                )
                total_deleted += int(cur.rowcount or 0)
                conn.commit()
                return {"ok": True, "deleted": total_deleted, "trace_id": tid}

        # ---- daily 表清理（长期 1d） ----------------------------------------
        if table == "daily":
            # 安全约束：需要 confirm=true
            if not confirm:
                return {"ok": False, "error": "confirm=true required to delete daily", "trace_id": tid}
            ts0 = 0 if start_ms is None else int(start_ms)
            ts1 = 2**63 - 1 if end_ms is None else int(end_ms)
            cur.execute(
                "DELETE FROM candles WHERE symbol=? AND freq='1d' AND adjust='none' AND ts BETWEEN ? AND ?;",
                (symbol, ts0, ts1),
            )
            total_deleted += int(cur.rowcount or 0)
            conn.commit()
            return {"ok": True, "deleted": total_deleted, "trace_id": tid}

        # 不达分支兜底
        return {"ok": False, "error": "invalid request", "trace_id": tid}

    except Exception as e:
        # 统一错误处理
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/migrate")
def api_storage_migrate(request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    迁移数据库文件：
    - 参数：{ db_path }
    - 行为：写入 config.json（由 watcher 执行在线迁移与切换）
    """
    tid = request.headers.get("x-trace-id")  # 链路 ID
    try:
        new_path = str(payload.get("db_path", "")).strip()  # 新路径
        if not new_path:
            return {"ok": False, "error": "db_path is required", "trace_id": tid}  # 参数缺失
        cfg = set_config({"db_path": new_path})  # 写配置（后台 watcher 执行迁移）
        return {"ok": True, "config": cfg, "trace_id": tid}  # 返回应用后配置
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/vacuum")
def api_storage_vacuum(request: Request) -> Dict[str, Any]:
    """
    VACUUM 优化：
    - 释放未使用空间、整理页结构
    """
    tid = request.headers.get("x-trace-id")  # 链路 ID
    try:
        vacuum_optimize()  # 执行 VACUUM
        return {"ok": True, "trace_id": tid}  # 成功
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.get("/integrity")
def api_storage_integrity(request: Request) -> Dict[str, Any]:
    """
    完整性校验：
    - PRAGMA integrity_check；返回 {ok,message}
    """
    tid = request.headers.get("x-trace-id")  # 链路 ID
    try:
        ok, msg = integrity_check()  # 校验
        return {"ok": ok, "message": msg, "trace_id": tid}  # 返回
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)
