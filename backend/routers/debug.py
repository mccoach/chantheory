# backend/routers/debug.py
# ==============================
# 说明：调试与诊断路由（AkShare 原始日线列名/样例）
# - 本轮变更：将原先的 print 调试输出替换为结构化日志 log_event，符合 NDJSON/trace_id 规范；
#   其余业务逻辑与返回不变。
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 3.8+）

from fastapi import APIRouter, Query, Request  # FastAPI 路由与参数
from typing import Optional, Dict, Any         # 类型注解
import importlib                                # 动态导入

from backend.utils.errors import http_500_from_exc  # 统一错误包装
from backend.utils.time import normalize_yyyymmdd_range  # 统一时间窗解析/规范

# 结构化日志（替代 print）
from backend.utils.logger import get_logger, log_event  # 统一 NDJSON 日志工具
_LOG = get_logger("debug")  # 命名 logger

router = APIRouter(prefix="/api/debug", tags=["debug"])  # 路由前缀/分组

def _lazy_import_ak():
    """延迟导入 akshare，避免冷启动阻塞。"""
    return importlib.import_module("akshare")

@router.get("/daily_columns")
def api_debug_daily_columns(
    request: Request,  # 请求对象（可取 headers/trace_id）
    code: str = Query(..., description="股票代码，如 600519"),  # 标的代码
    start: Optional[str] = Query(None, description="YYYYMMDD|YYYY-MM-DD|毫秒（可选）"),  # 开始
    end: Optional[str] = Query(None, description="YYYYMMDD|YYYY-MM-DD|毫秒（可选）"),    # 结束
    adjust: str = Query("none", description="复权：none|qfq|hfq"),  # 复权类型
) -> Dict[str, Any]:
    """
    调试：直接走 AkShare 拉日线，回传原始列名与样例。
    - 仅用于诊断，无缓存与落库行为。
    - 变更点：使用结构化日志记录入参与规范化后的出参，不再使用 print。
    """
    tid = request.headers.get("x-trace-id")  # 追踪 ID（贯通前后端）
    try:
        ak = _lazy_import_ak()  # 延迟导入 AkShare

        # 入参日志（结构化 INFO）
        log_event(
            _LOG, service="debug", level="INFO",
            file=__file__, func="api_debug_daily_columns", line=0, trace_id=tid,
            event="api.debug.daily_columns.start",
            message="incoming request",
            extra={"category": "api", "action": "start", "request": {"code": code, "start": start, "end": end, "adjust": adjust}}
        )

        # 统一补齐/交换：缺省则 start=19900101，end=今天；若 start>end 自动交换
        s_ymd, e_ymd = normalize_yyyymmdd_range(start, end, default_start=19900101)
        start_s = f"{s_ymd:08d}"  # AkShare 需要 YYYYMMDD 字符串
        end_s = f"{e_ymd:08d}"

        # adjust 参数：AkShare 对不复权使用 ""（空串）；qfq/hfq 原样传递
        adj = "" if adjust == "none" else adjust

        # 出参日志（将要发往 AkShare 的参数快照）
        log_event(
            _LOG, service="debug", level="INFO",
            file=__file__, func="api_debug_daily_columns", line=0, trace_id=tid,
            event="api.debug.daily_columns.normalized",
            message="normalized params for akshare",
            extra={"category": "api", "action": "normalized", "request": {"code": code, "start": start_s, "end": end_s, "adjust_sent": adj}}
        )

        # 调用 AkShare（直接取原始日线）
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_s,
            end_date=end_s,
            adjust=adj,  # 关键修复：不再传 None
        )

        # 整理输出：原始列名与去空白列名
        cols_raw = [str(c) for c in (df.columns.tolist() if df is not None else [])]  # 原列名
        cols_trim = [str(c).strip() for c in (df.columns.tolist() if df is not None else [])]  # 去空白
        sample = df.head(5).to_dict(orient="records") if (df is not None and not df.empty) else []  # 前 5 行样例

        # 成功日志（行数简要）
        log_event(
            _LOG, service="debug", level="INFO",
            file=__file__, func="api_debug_daily_columns", line=0, trace_id=tid,
            event="api.debug.daily_columns.done",
            message="akshare fetched",
            extra={"category": "api", "action": "done", "result": {"rows": int(len(df) if df is not None else 0)}}
        )

        # 回传数据（与原逻辑一致）
        return {
            "ok": True,
            "symbol": code,
            "adjust": adjust,
            "start": start_s,
            "end": end_s,
            "columns_raw": cols_raw,
            "columns_trimmed": cols_trim,
            "rows": int(len(df) if df is not None else 0),
            "sample_head": sample,
            "trace_id": tid,
        }
    except Exception as e:
        # 失败日志（ERROR）
        log_event(
            _LOG, service="debug", level="ERROR",
            file=__file__, func="api_debug_daily_columns", line=0, trace_id=tid,
            event="api.debug.daily_columns.fail",
            message="debug daily_columns failed",
            extra={"category": "api", "action": "fail", "error_code": "DEBUG_DAILY_COLUMNS_FAIL", "error_message": str(e)}
        )
        # 统一错误包装（DEBUG=True 时含回溯）
        raise http_500_from_exc(e, trace_id=tid)
