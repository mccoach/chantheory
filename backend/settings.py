# backend/settings.py
# ==============================
# 说明：全局配置中心（V3.1 - 精简版·零过度设计）
# 核心改造：
#   1. 数据类型定义（DATA_TYPE_DEFINITIONS）
#   2. 刷新策略配置（REFRESH_STRATEGIES）
#   3. 缺口判断方法注册表（GAP_CHECK_METHODS）
# 精简原则：
#   - 只提取多处复用的配置
#   - 拒绝过度设计
#   - 保持代码直观性
# ==============================

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

# --- 基础路径定义 ---
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR: Path = Path(os.getenv("CHAN_DATA_DIR", PROJECT_ROOT / "var"))
DEFAULT_DB_PATH: Path = DEFAULT_DATA_DIR / "data.sqlite"
DEFAULT_CONFIG_PATH: Path = DEFAULT_DATA_DIR / "config.json"

@dataclass
class Settings:
    # ==============================
    # ---- 服务器与 CORS ----
    # ==============================
    host: str = os.getenv("CHAN_HOST", "0.0.0.0")
    port: int = int(os.getenv("CHAN_PORT", "8000"))
    debug: bool = os.getenv("CHAN_DEBUG", "1") == "1"
    cors_origins: List[str] = None

    # ==============================
    # ---- 本地路径 ----
    # ==============================
    data_dir: Path = DEFAULT_DATA_DIR
    db_path: Path = DEFAULT_DB_PATH
    user_config_path: Path = DEFAULT_CONFIG_PATH

    # ==============================
    # ---- 网络与重试 ----
    # ==============================
    retry_max_attempts: int = int(os.getenv("CHAN_RETRY_MAX_ATTEMPTS", "3"))
    retry_base_delay_ms: int = int(os.getenv("CHAN_RETRY_BASE_DELAY_MS", "3000"))

    # ==============================
    # ---- 全局网络限流器 ----
    # ==============================
    network_limiter_enabled: bool = os.getenv("CHAN_NETWORK_LIMITER_ENABLED", "1") == "1"
    network_requests_per_second: float = float(os.getenv("CHAN_NETWORK_RPS", "2.0"))
    network_max_burst_tokens: int = int(os.getenv("CHAN_NETWORK_BURST", "3"))

    # ==============================
    # ---- 业务常量 ----
    # ==============================
    timezone: str = "Asia/Shanghai"

    # ==============================
    # ---- 同步全局配置（核心3类） ----
    # ==============================
    sync_init_start_date: int = 19900101  # 统一起始日期
    sync_standard_freqs: List[str] = field(default_factory=lambda: ['1m', '5m', '15m', '30m', '60m', '1d'])  # 标准频率
    sync_on_demand_freqs: List[str] = field(default_factory=lambda: ['1w', '1M'])  # 按需频率
    sync_symbol_categories: List[str] = field(default_factory=lambda: ["A", "ETF", "LOF"])  # 标的列表范围
    sync_data_categories: List[str] = field(default_factory=lambda: ["A", "ETF"])  # 实际拉取数据范围

    # ==============================
    # ---- 业务默认值 ----
    # ==============================
    default_market: str = "CN"  # 默认市场标识
    data_source_name: str = "unified_executor"  # 数据源标识
    
    # ==============================
    # ---- 日志系统 ----
    # ==============================
    log_file: Path = Path(os.getenv("CHAN_LOG_FILE", PROJECT_ROOT / "chan-theory.log"))
    log_level: str = os.getenv("CHAN_LOG_LEVEL", "DEBUG" if os.getenv("CHAN_DEBUG", "1") == "1" else "INFO")
    log_max_bytes: int = int(os.getenv("CHAN_LOG_MAX_BYTES", str(50 * 1024 * 1024)))
    log_backup_count: int = int(os.getenv("CHAN_LOG_BACKUP_COUNT", "5"))
    log_debug_trace_ids_raw: str = os.getenv("CHAN_LOG_DEBUG_TRACE_IDS", "")
    log_debug_trace_ids: List[str] = None
    log_summary: bool = os.getenv("CHAN_LOG_SUMMARY", "0" if os.getenv("CHAN_DEBUG", "1") == "1" else "1") == "1"
    log_include_request: bool = os.getenv("CHAN_LOG_INCLUDE_REQUEST", "0") == "1"
    log_include_result: bool = os.getenv("CHAN_LOG_INCLUDE_RESULT", "0") == "1"
    log_module_levels_raw: str = os.getenv("CHAN_LOG_MODULE_LEVELS", "")
    log_module_levels: Dict[str, str] = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:3000", "http://127.0.0.1:3000",
            ]
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.db_path).resolve()
        self.user_config_path = Path(self.user_config_path).resolve()
        self.log_file = Path(self.log_file).resolve()
        
        raw_trace_ids = str(self.log_debug_trace_ids_raw or "").strip()
        self.log_debug_trace_ids = [s.strip() for s in raw_trace_ids.split(",") if s.strip()] if raw_trace_ids else []
        
        self.log_module_levels = {}
        raw_mod_levels = str(self.log_module_levels_raw or "").strip()
        if raw_mod_levels:
            for pair in raw_mod_levels.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k, v = k.strip(), v.strip().upper()
                    if k and v:
                        self.log_module_levels[k] = v

settings = Settings()

# ==============================
# ---- 数据类型完整定义 ----
# ==============================

DATA_TYPE_DEFINITIONS = {
    # 前端数据
    "frontend_kline_current": {
        "name": "前端标的×前端频率K线",
        "category": "kline",
        "priority": 5,
    },
    
    # 前端信息
    "frontend_profile": {
        "name": "前端标的档案",
        "category": "profile",
        "priority": 10,
    },
    "frontend_factors": {
        "name": "前端标的复权因子",
        "category": "factors",
        "priority": 10,
    },
    "symbol_index": {
        "name": "标的列表",
        "category": "symbol_index",
        "priority": 5,
    },
    "trade_calendar": {
        "name": "交易日历",
        "category": "trade_calendar",
        "priority": 5,
    },
    
    # 后台数据（8个频率：6个标准 + 2个按需）
    "watchlist_kline_1m": {
        "name": "自选池×1m",
        "category": "kline",
        "freq": "1m",
        "priority": 30,
    },
    "watchlist_kline_5m": {
        "name": "自选池×5m",
        "category": "kline",
        "freq": "5m",
        "priority": 30,
    },
    "watchlist_kline_15m": {
        "name": "自选池×15m",
        "category": "kline",
        "freq": "15m",
        "priority": 30,
    },
    "watchlist_kline_30m": {
        "name": "自选池×30m",
        "category": "kline",
        "freq": "30m",
        "priority": 30,
    },
    "watchlist_kline_60m": {
        "name": "自选池×60m",
        "category": "kline",
        "freq": "60m",
        "priority": 30,
    },
    "watchlist_kline_1d": {
        "name": "自选池×1d",
        "category": "kline",
        "freq": "1d",
        "priority": 30,
    },
    "watchlist_kline_1w": {
        "name": "自选池×1w",
        "category": "kline",
        "freq": "1w",
        "priority": 30,
    },
    "watchlist_kline_1M": {
        "name": "自选池×1M",
        "category": "kline",
        "freq": "1M",
        "priority": 30,
    },
    
    # 后台信息
    "watchlist_profile": {
        "name": "自选池档案",
        "category": "profile",
        "priority": 30,
    },
    "watchlist_factors": {
        "name": "自选池因子",
        "category": "factors",
        "priority": 30,
    },
    "all_symbols_profile": {
        "name": "全量档案补缺",
        "category": "profile",
        "priority": 40,
    },
}

# ==============================
# ---- 刷新策略配置 ----
# ==============================

REFRESH_STRATEGIES = {
    # 前端K线：判断到当前时刻
    "frontend_kline_current": {
        "gap_check_method": "kline_to_current_time",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "now",
    },
    
    # 前端档案/因子：判断今日更新
    "frontend_profile": {
        "gap_check_method": "info_updated_today",
    },
    "frontend_factors": {
        "gap_check_method": "info_updated_today",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "now",
    },
    
    # 标的列表：总是拉取
    "symbol_index": {
        "gap_check_method": "always_fetch",
    },
    
    # 交易日历：总是拉取
    "trade_calendar": {
        "gap_check_method": "always_fetch",
    },
    
    # 自选池K线：判断到前收盘
    "watchlist_kline_1m": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_5m": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_15m": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_30m": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_60m": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_1d": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_1w": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    "watchlist_kline_1M": {
        "gap_check_method": "kline_to_last_close",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    
    # 自选池档案/因子：判断今日更新
    "watchlist_profile": {
        "gap_check_method": "info_updated_today",
    },
    "watchlist_factors": {
        "gap_check_method": "info_updated_today",
        "time_range_start": "GLOBAL.sync_init_start_date",
        "time_range_end": "last_trading_day",
    },
    
    # 全量档案：仅补缺
    "all_symbols_profile": {
        "gap_check_method": "record_exists",
    },
}

# ==============================
# ---- 缺口判断方法注册表 ----
# ==============================

GAP_CHECK_METHODS = {
    "kline_to_current_time": "utils.gap_checker.check_kline_gap_to_current",
    "kline_to_last_close": "utils.gap_checker.check_kline_gap_to_last_close",
    "info_updated_today": "utils.gap_checker.check_info_updated_today",
    "record_exists": "utils.gap_checker.check_record_not_exists",
    "always_fetch": "lambda **kwargs: True",
}
