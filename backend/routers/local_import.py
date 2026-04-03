# backend/routers/local_import.py
# ==============================
# 盘后数据导入 import 路由
#
# 正式接口：
#   - GET  /api/local-import/candidates
#       * 只读取当前已保存候选结果（轻操作）
#   - POST /api/local-import/candidates/refresh
#       * 显式重新扫描并覆盖当前候选结果（重操作）
#   - POST /api/local-import/start
#   - GET  /api/local-import/status
#   - POST /api/local-import/cancel
#   - POST /api/local-import/retry
#
# 路径设置接口：
#   - GET  /api/local-import/settings
#   - POST /api/local-import/settings/browse
#   - POST /api/local-import/settings
#
# 说明：
#   - SSE 为主状态同步链路
#   - 这些 HTTP 接口承担：
#       * 初始化快照
#       * 用户操作入口
#       * SSE 断连后的状态恢复与纠偏
#
# 当前阶段说明：
#   - 前端只关心聚合数量变化，不展示任务明细
#   - 因此已删除 /api/local-import/tasks 明细接口
#   - 后端唯一实时状态路径统一收敛为：
#       local_import.status
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.services.local_import.candidates import (
    get_import_candidates_snapshot,
    refresh_import_candidates_snapshot,
)
from backend.services.local_import.repository import build_status_snapshot
from backend.services.local_import.orchestrator import (
    start_import_batch,
    cancel_import_batch,
    retry_import_batch,
)
from backend.services.local_import.settings_service import (
    get_local_import_settings,
    browse_local_import_root_dir,
    save_local_import_root_dir,
)
from backend.utils.logger import get_logger, log_event
from backend.utils.errors import http_500_from_exc

router = APIRouter(prefix="/api/local-import", tags=["local-import"])
_LOG = get_logger("local_import.router")


class ImportSelectionItem(BaseModel):
    market: str
    symbol: str
    freq: str


class ImportStartRequest(BaseModel):
    items: List[ImportSelectionItem] = Field(..., min_length=1)


class BatchOpRequest(BaseModel):
    batch_id: str


class BrowseDirRequest(BaseModel):
    initial_dir: Optional[str] = None


class SaveSettingsRequest(BaseModel):
    tdx_vipdoc_dir: str


@router.get("/candidates")
async def api_local_import_candidates(request: Request) -> Dict[str, Any]:
    """
    轻操作：
      - 只读取当前已保存候选结果
      - 不触发重扫描
    """
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="local_import.router",
        level="INFO",
        file=__file__,
        func="api_local_import_candidates",
        line=0,
        trace_id=tid,
        event="local_import.candidates.get.start",
        message="GET /api/local-import/candidates",
    )

    try:
        payload = get_import_candidates_snapshot()

        log_event(
            logger=_LOG,
            service="local_import.router",
            level="INFO",
            file=__file__,
            func="api_local_import_candidates",
            line=0,
            trace_id=tid,
            event="local_import.candidates.get.done",
            message="GET /api/local-import/candidates done",
            extra={
                "ready": bool(payload.get("ready")),
                "rows": len(payload.get("items") or []),
            },
        )
        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="local_import.router",
            level="ERROR",
            file=__file__,
            func="api_local_import_candidates",
            line=0,
            trace_id=tid,
            event="local_import.candidates.get.fail",
            message="GET /api/local-import/candidates failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/candidates/refresh")
async def api_local_import_candidates_refresh(request: Request) -> Dict[str, Any]:
    """
    重操作：
      - 显式触发重扫描
      - 覆盖当前候选结果真相源
      - 只返回轻状态，不返回候选结果本体
    """
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="local_import.router",
        level="INFO",
        file=__file__,
        func="api_local_import_candidates_refresh",
        line=0,
        trace_id=tid,
        event="local_import.candidates.refresh.start",
        message="POST /api/local-import/candidates/refresh",
    )

    try:
        payload = refresh_import_candidates_snapshot()

        log_event(
            logger=_LOG,
            service="local_import.router",
            level="INFO",
            file=__file__,
            func="api_local_import_candidates_refresh",
            line=0,
            trace_id=tid,
            event="local_import.candidates.refresh.done",
            message="POST /api/local-import/candidates/refresh done",
            extra={
                "ready": bool(payload.get("ready")),
                "generated_at": payload.get("generated_at"),
            },
        )
        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="local_import.router",
            level="ERROR",
            file=__file__,
            func="api_local_import_candidates_refresh",
            line=0,
            trace_id=tid,
            event="local_import.candidates.refresh.fail",
            message="POST /api/local-import/candidates/refresh failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/start")
async def api_local_import_start(request: Request, payload: ImportStartRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        items = []
        seen = set()

        for item in payload.items:
            market = str(item.market or "").strip().upper()
            symbol = str(item.symbol or "").strip()
            freq = str(item.freq or "").strip()

            if market not in ("SH", "SZ", "BJ"):
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"非法 market: {market}",
                }
            if not symbol or not symbol.isdigit():
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"非法 symbol: {symbol}",
                }
            if freq not in ("1d", "1m", "5m"):
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"当前仅支持 freq=1d/1m/5m，收到: {freq}",
                }

            key = (market, symbol, freq)
            if key in seen:
                continue
            seen.add(key)

            items.append({
                "market": market,
                "symbol": symbol,
                "freq": freq,
            })

        if not items:
            return {
                "ok": False,
                "display_batch": None,
                "queued_batches": [],
                "ui_message": "items 不能为空",
            }

        resp = await start_import_batch(items)

        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }

    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.get("/status")
async def api_local_import_status(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        snap = build_status_snapshot()
        return {
            "ok": True,
            "display_batch": snap.get("display_batch"),
            "queued_batches": snap.get("queued_batches") or [],
            "ui_message": snap.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/cancel")
async def api_local_import_cancel(request: Request, payload: BatchOpRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        resp = await cancel_import_batch(payload.batch_id)
        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/retry")
async def api_local_import_retry(request: Request, payload: BatchOpRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        resp = await retry_import_batch(payload.batch_id)
        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.get("/settings")
async def api_local_import_settings(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        return get_local_import_settings()
    except Exception as e:
        return {
            "ok": False,
            "tdx_vipdoc_dir": "",
            "message": f"读取配置失败: {e}",
        }


@router.post("/settings/browse")
async def api_local_import_settings_browse(
    request: Request,
    payload: BrowseDirRequest,
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        return await browse_local_import_root_dir(payload.initial_dir)
    except Exception as e:
        return {
            "ok": False,
            "selected_dir": "",
            "message": f"打开文件夹选择窗口失败: {e}",
        }


@router.post("/settings")
async def api_local_import_settings_save(
    request: Request,
    payload: SaveSettingsRequest,
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        return save_local_import_root_dir(payload.tdx_vipdoc_dir)
    except ValueError as e:
        return {
            "ok": False,
            "tdx_vipdoc_dir": str(payload.tdx_vipdoc_dir or "").strip(),
            "message": f"保存失败: {e}",
        }
    except Exception as e:
        return {
            "ok": False,
            "tdx_vipdoc_dir": str(payload.tdx_vipdoc_dir or "").strip(),
            "message": f"保存失败: {e}",
        }
