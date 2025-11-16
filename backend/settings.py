# backend/settings.py
# ==============================
# 全局配置（V6.0 - 修改标的列表缺口方法）
# 改动：
#   - symbol_index 的缺口方法从 always_fetch 改为 symbol_index_daily
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
    # 服务器与 CORS
    host: str = os.getenv("CHAN_HOST", "0.0.0.0")
    port: int = int(os.getenv("CHAN_PORT", "8000"))
    debug: bool = os.getenv("CHAN_DEBUG", "1") == "1"
    cors_origins: List[str] = None

    # 本地路径
    data_dir: Path = DEFAULT_DATA_DIR
    db_path: Path = DEFAULT_DB_PATH
    user_config_path: Path = DEFAULT_CONFIG_PATH

    # 网络与重试
    retry_max_attempts: int = int(os.getenv("CHAN_RETRY_MAX_ATTEMPTS", "3"))
    retry_base_delay_ms: int = int(os.getenv("CHAN_RETRY_BASE_DELAY_MS", "3000"))

    # 全局网络限流器
    network_limiter_enabled: bool = os.getenv("CHAN_NETWORK_LIMITER_ENABLED", "1") == "1"
    network_requests_per_second: float = float(os.getenv("CHAN_NETWORK_RPS", "2.0"))
    network_max_burst_tokens: int = int(os.getenv("CHAN_NETWORK_BURST", "3"))

    # 业务常量
    timezone: str = "Asia/Shanghai"
    default_market: str = "CN"
    data_source_name: str = "unified_executor"
    sync_init_start_date: int = 19900101

    # 日志系统
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
# 数据类型完整定义（仅5类）
# ==============================

DATA_TYPE_DEFINITIONS = {
    # P10：交易日历（最高优先级，缺口判断依赖）
    "trade_calendar": {
        "name": "交易日历",
        "category": "trade_calendar",
        "priority": 10,
    },
    
    # P20：当前标的核心数据
    "current_kline": {
        "name": "当前K线",
        "category": "kline",
        "priority": 20,
    },
    "current_factors": {
        "name": "当前复权因子",
        "category": "factors",
        "priority": 20,
    },
    
    # P30：全局数据（优先写入标的列表，以免档案写入时外键约束失败报错）
    "symbol_index": {
        "name": "标的列表",
        "category": "symbol_index",
        "priority": 30,
    },
    
    # P40：当前标的档案（不阻塞渲染）
    "current_profile": {
        "name": "当前档案",
        "category": "profile",
        "priority": 40,
    },
}

# ==============================
# 刷新策略配置
# ==============================

REFRESH_STRATEGIES = {
    # 交易日历：判断最晚日期
    "trade_calendar": {
        "gap_check_method": "calendar_latest_before_today",
    },
    
    # 当前K线：判断到当前时刻
    "current_kline": {
        "gap_check_method": "kline_to_current_time",
    },
    
    # 当前因子：判断今日更新
    "current_factors": {
        "gap_check_method": "info_updated_today",
    },
    
    # 当前档案：判断今日更新
    "current_profile": {
        "gap_check_method": "info_updated_today",
    },
    
    # 标的列表：判断今日更新（修改）
    "symbol_index": {
        "gap_check_method": "symbol_index_daily",
    },
}

# ==============================
# 缺口判断方法注册表
# ==============================

GAP_CHECK_METHODS = {
    "calendar_latest_before_today": "utils.gap_checker.check_calendar_gap",
    "kline_to_current_time": "utils.gap_checker.check_kline_gap_to_current",
    "info_updated_today": "utils.gap_checker.check_info_updated_today",
    "symbol_index_daily": "utils.gap_checker.check_symbol_index_gap",  # ← 新增
    "always_fetch": "lambda **kwargs: True",
}