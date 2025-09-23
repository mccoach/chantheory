# E:\AppProject\ChanTheory\backend\routers\candles.py
# ==============================
# 说明：/api/candles 路由（增强：服务端一次成型计算“可视切片”）
# - 新增入参：
#   * window_preset（可选）：5D/10D/1M/3M/6M/1Y/3Y/5Y/ALL
#   * bars（可选）：目标可见根数（整数，优先于 window_preset）
#   * anchor_ts（可选）：右端锚点（毫秒），用于定位 e_idx（candles.ts ≤ anchor_ts 的最后一根）
# - 返回：
#   * meta 增补：all_rows、view_rows、view_start_idx、view_end_idx、window_preset_effective
#   * candles 返回 ALL（全量序列）；前端仅根据 view_start_idx/view_end_idx 设置 dataZoom
# - 其余契约保持（freq/adjust/include/ma_periods 等）
from __future__ import annotations  # 允许前置注解（兼容 3.8+）

import time                     # 计时
import json                     # 解析 ma_periods JSON
from typing import Optional     # 可选类型

from fastapi import APIRouter, Query, Request  # FastAPI 工具
from backend.services.market import get_candles  # 核心服务
from backend.utils.errors import http_500_from_exc  # 统一错误包装
from backend.utils.logger import get_logger, log_event  # 结构化日志
from backend.utils.time import (
    normalize_yyyymmdd_range,  # 仍保留兼容（不强依赖）
)

_LOG = get_logger("candles")  # 命名 logger
router = APIRouter(prefix="/api", tags=["candles"])  # 路由器

@router.get("/candles")
def api_candles(
    request: Request,
    code: str = Query(..., description="股票代码，如 600519"),
    freq: str = Query("1d", description="频率：1m|5m|15m|30m|60m|1d|1w|1M"),
    # 新增：统一“服务端计算视图窗口”的参数（bars 优先于 window_preset）
    window_preset: Optional[str] = Query(None, description="窗宽预设：5D|10D|1M|3M|6M|1Y|3Y|5Y|ALL"),
    bars: Optional[int] = Query(None, description="目标可见根数（整数，优先级高于 window_preset）"),
    anchor_ts: Optional[int] = Query(None, description="右端锚点（毫秒）；未提供则取数据右端"),
    # 保留：指标与 MA 周期
    adjust: str = Query("none", description="复权方式：none|qfq|hfq"),
    include: Optional[str] = Query(None, description="指标：ma,macd,kdj,rsi,boll,vol（逗号分隔）"),
    ma_periods: Optional[str] = Query(None, description="MA 周期，JSON 字符串：'{\"MA5\":12, \"MA10\":21}'"),
    # 兼容：iface_key/trace_id（不改变）
    iface_key: Optional[str] = Query(None, description="方法键，如 A_1m_a / A_1m_b / E_1d_a"),
    trace_id: Optional[str] = Query(None, description="客户端追踪ID（可选）"),
):
    # x-trace-id 优先
    tid = request.headers.get("x-trace-id") or trace_id

    t0 = time.time()
    log_event(
        _LOG, service="candles", level="INFO",
        file=__file__, func="api_candles", line=0, trace_id=tid,
        event="api.candles.start", message="incoming /api/candles",
        extra={"category": "api", "action": "start",
               "request": {"endpoint": "/api/candles", "method": "GET",
                           "query": {"code": code, "freq": freq,
                                     "window_preset": window_preset, "bars": bars, "anchor_ts": anchor_ts,
                                     "adjust": adjust, "include": include, "iface_key": iface_key}}}
    )
    try:
        # 解析 include
        include_set = set([s.strip().lower() for s in (include or "").split(",") if s and s.strip()])

        # 解析 MA 周期映射
        ma_periods_dict = {}
        if ma_periods:
            try:
                ma_periods_dict = json.loads(ma_periods)
                if not isinstance(ma_periods_dict, dict):
                    ma_periods_dict = {}
            except json.JSONDecodeError:
                ma_periods_dict = {}

        # 调用服务（由服务端计算“终端可见切片”的 s_idx/e_idx 与 view_rows）
        resp = get_candles(
            symbol=code,
            freq=freq,
            adjust=adjust,
            start_ms=None,
            end_ms=None,
            include=include_set,
            ma_periods_map=ma_periods_dict,
            trace_id=tid,
            preferred_iface_key=iface_key,
            # 新增参数
            window_preset=window_preset,
            bars=bars,
            anchor_ts=anchor_ts,
        )
        rows = int(resp.get("meta", {}).get("rows") or 0)
        log_event(
            _LOG, service="candles", level="INFO",
            file=__file__, func="api_candles", line=0, trace_id=tid,
            event="api.candles.done", message="served /api/candles",
            extra={"category": "api", "action": "done",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "result": {"rows": rows, "status_code": 200}}
        )
        return resp
    except Exception as e:
        log_event(
            _LOG, service="candles", level="ERROR",
            file=__file__, func="api_candles", line=0, trace_id=tid,
            event="api.candles.fail", message="failed /api/candles",
            extra={"category": "api", "action": "fail",
                   "error_code": "API_CANDLES_FAIL", "error_message": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)
