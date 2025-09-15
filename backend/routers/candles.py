# E:\AppProject\ChanTheory\backend\routers\candles.py
# ==============================
# 说明：/api/candles 路由（支持 iface_key 选择方法）
# - iface_key（str，可选）：稳定方法键，如 'A_1m_a'、'A_1m_b'、'E_1d_a'。
# - 未提供 iface_key 时，后端按“类别×频率”的主方法（*_a）选择。
# - 其余契约保持不变：start/end 解析、include 与 ma_periods JSON。
# - 本次修改：从 freq 描述中移除 120m。
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 3.8+）

import time                     # 计时
import json                     # 解析 ma_periods JSON
import traceback                # 调试堆栈（DEBUG 时）
from typing import Optional     # 可选类型

from fastapi import APIRouter, Query, Request  # FastAPI 工具
from backend.services.market import get_candles  # 核心服务
from backend.utils.errors import http_500_from_exc  # 统一错误包装
from backend.utils.logger import get_logger, log_event  # 结构化日志
from backend.utils.time import (                   # 时间工具
    normalize_yyyymmdd_range,  # 规范化日期范围
    ms_from_yyyymmdd,          # YYYYMMDD -> 该日 00:00:00 毫秒
    shift_days_yyyymmdd,       # 对 YYYYMMDD 偏移天数
)

_LOG = get_logger("candles")  # 命名 logger

router = APIRouter(prefix="/api", tags=["candles"])  # 路由器

@router.get("/candles")
def api_candles(
    request: Request,  # 请求对象
    code: str = Query(..., description="股票代码，如 600519"),  # 标的代码
    # 修改：从 freq 描述中移除 120m
    freq: str = Query("1d", description="频率：1m|5m|15m|30m|60m|1d|1w|1M"),  # 频率
    start: Optional[str] = Query(None, description="开始时间：毫秒或 YYYY-MM-DD|YYYYMMDD"),  # 开始（可空）
    end: Optional[str] = Query(None, description="结束时间：毫秒或 YYYY-MM-DD|YYYYMMDD"),  # 结束（可空）
    adjust: str = Query("none", description="复权方式：none|qfq|hfq"),  # 复权（前端可选择）
    include: Optional[str] = Query(None, description="指标：ma,macd,kdj,rsi,boll,vol 等（逗号分隔）"),  # 指标包含
    ma_periods: Optional[str] = Query(None, description="MA 周期，JSON 对象字符串：'{\"MA5\":12, \"MA10\":21}'"),  # MA 周期映射
    iface_key: Optional[str] = Query(None, description="方法键，如 A_1m_a / A_1m_b / E_1d_a"),  # 稳定方法键
    trace_id: Optional[str] = Query(None, description="客户端追踪ID（可选）"),  # trace_id
):
    # x-trace-id 优先于 query.trace_id
    tid = request.headers.get("x-trace-id") or trace_id  # 取链路ID

    t0 = time.time()
    # 入参日志
    log_event(
        _LOG, service="candles", level="INFO",
        file=__file__, func="api_candles", line=0, trace_id=tid,
        event="api.candles.start", message="incoming /api/candles",
        extra={"category": "api", "action": "start",
               "request": {"endpoint": "/api/candles", "method": "GET",
                           "query": {"code": code, "freq": freq, "start": start, "end": end,
                                     "adjust": adjust, "include": include, "iface_key": iface_key}}}
    )
    try:
        # 1) 规范化日期窗（整窗右端为“结束日次日 00:00:00 - 1ms”）
        s_ymd, e_ymd = normalize_yyyymmdd_range(start, end)  # 归一化
        start_ms = ms_from_yyyymmdd(s_ymd)  # 起毫秒
        end_ms = ms_from_yyyymmdd(shift_days_yyyymmdd(e_ymd, 1)) - 1  # 止毫秒

        # 2) include 集合化
        include_set = set([s.strip().lower() for s in (include or "").split(",") if s and s.strip()])  # 指标集合

        # 3) 解析 MA 周期映射（固定 key 的 MA 算法）
        ma_periods_dict = {}  # 默认空
        if ma_periods:
            try:
                ma_periods_dict = json.loads(ma_periods)  # 尝试解析 JSON
                if not isinstance(ma_periods_dict, dict):  # 结构校验
                    ma_periods_dict = {}  # 保底字典
            except json.JSONDecodeError:
                ma_periods_dict = {}  # 解析失败兜底

        # 4) 调用服务层
        resp = get_candles(
            symbol=code,
            freq=freq,
            adjust=adjust,
            start_ms=start_ms,
            end_ms=end_ms,
            include=include_set,
            ma_periods_map=ma_periods_dict,
            trace_id=tid,
            preferred_iface_key=iface_key,
        )
        rows = int(resp.get("meta", {}).get("rows") or 0)
        # 出参摘要日志
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
        # 错误日志（脱敏）
        log_event(
            _LOG, service="candles", level="ERROR",
            file=__file__, func="api_candles", line=0, trace_id=tid,
            event="api.candles.fail", message="failed /api/candles",
            extra={"category": "api", "action": "fail",
                   "error_code": "API_CANDLES_FAIL", "error_message": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)
