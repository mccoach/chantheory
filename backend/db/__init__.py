# backend/db/__init__.py
# ==============================
# V3.0 - 删除废弃的 tasks 模块导出
# ==============================

from backend.db.connection import get_conn, close_all_connections
from backend.db.schema import init_schema, ensure_initialized

# K线数据操作
from backend.db.candles import (
    upsert_candles_raw,
    select_candles_raw,
    get_latest_ts_from_raw,
)

# 复权因子操作
from backend.db.factors import (
    upsert_factors,
    select_factors,
    get_latest_factor_date,
)

# 标的元数据操作
from backend.db.symbols import (
    upsert_symbol_index,
    select_symbol_index,
    get_listing_date,
    upsert_symbol_profile,
    select_symbol_profile,
)

# 自选池操作
from backend.db.watchlist import (
    insert_watchlist,
    delete_watchlist,
    select_user_watchlist,
    update_watchlist_tags,
    update_watchlist_sort_order,
)

# 交易日历操作
from backend.db.calendar import (
    upsert_trade_calendar,
    is_trading_day,
    get_recent_trading_days,
    select_trading_days_in_range,
)

__all__ = [
    # 连接与Schema
    'get_conn', 'close_all_connections', 'init_schema', 'ensure_initialized',
    
    # K线
    'upsert_candles_raw', 'select_candles_raw', 'get_latest_ts_from_raw',
    
    # 因子
    'upsert_factors', 'select_factors', 'get_latest_factor_date',
    
    # 标的
    'upsert_symbol_index', 'select_symbol_index', 'get_listing_date',
    'upsert_symbol_profile', 'select_symbol_profile',
    
    # 自选池
    'insert_watchlist', 'delete_watchlist', 'select_user_watchlist',
    'update_watchlist_tags', 'update_watchlist_sort_order',
    
    # 日历
    'upsert_trade_calendar', 'is_trading_day', 'get_recent_trading_days',
    'select_trading_days_in_range',
]
