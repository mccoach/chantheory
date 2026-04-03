# backend/db/__init__.py
# ==============================
# DB 模块导出接口
#
# 本轮改动：
#   - 新增 gbbq_events_raw 原始事件表操作导出
#   - watchlist 正式升级为 (symbol, market) 双主键语义
# ==============================

from backend.db.connection import get_conn, close_all_connections
from backend.db.schema import init_schema, ensure_initialized

from backend.db.candles import (
    upsert_candles_day_raw,
    select_candles_day_raw,
    get_latest_ts_from_day_raw,
)

from backend.db.factors import (
    upsert_factors,
    select_factors,
    get_latest_factor_date,
)

from backend.db.gbbq_events import (
    upsert_gbbq_events_raw,
    select_gbbq_events_raw,
    get_gbbq_events_row_count,
)

from backend.db.symbols import (
    upsert_symbol_index,
    select_symbol_index,
    get_listing_date,
    upsert_symbol_profile,
    select_symbol_profile,
)

from backend.db.watchlist import (
    insert_watchlist,
    delete_watchlist,
    select_user_watchlist,
)

from backend.db.calendar import (
    upsert_trade_calendar,
    is_trading_day,
    get_recent_trading_days,
    select_trading_days_in_range,
)

from backend.db.data_task_status import (
    upsert_data_task_status,
    mark_data_task_running,
    mark_data_task_success,
    mark_data_task_failed,
    mark_data_task_idle,
    select_data_task_status,
    select_all_data_task_status,
)

__all__ = [
    "get_conn",
    "close_all_connections",
    "init_schema",
    "ensure_initialized",

    "upsert_candles_day_raw",
    "select_candles_day_raw",
    "get_latest_ts_from_day_raw",

    "upsert_factors",
    "select_factors",
    "get_latest_factor_date",

    "upsert_gbbq_events_raw",
    "select_gbbq_events_raw",
    "get_gbbq_events_row_count",

    "upsert_symbol_index",
    "select_symbol_index",
    "get_listing_date",
    "upsert_symbol_profile",
    "select_symbol_profile",

    "insert_watchlist",
    "delete_watchlist",
    "select_user_watchlist",

    "upsert_trade_calendar",
    "is_trading_day",
    "get_recent_trading_days",
    "select_trading_days_in_range",

    "upsert_data_task_status",
    "mark_data_task_running",
    "mark_data_task_success",
    "mark_data_task_failed",
    "mark_data_task_idle",
    "select_data_task_status",
    "select_all_data_task_status",
]