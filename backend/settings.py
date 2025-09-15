# backend/settings.py
# ==============================
# 说明：全局配置与路径计算（扩展日志分级与字段开关）
# 关键新增：
# - 日志级别与文件滚动：log_file/log_level/log_max_bytes/log_backup_count
# - 定向 trace_id DEBUG：log_debug_trace_ids（CSV）
# - 字段与分级开关：
#   * log_summary（True=仅概要字段，默认 DEV=False/PROD=True 建议按需调整）
#   * log_include_request（是否输出 request 细节）
#   * log_include_result（是否输出 result 细节）
#   * log_module_levels（按模块覆盖级别，如 "symbols=DEBUG,market=INFO"）
# ==============================

from __future__ import annotations  # 注解前置

import os  # 环境变量
from pathlib import Path  # 路径处理
from dataclasses import dataclass  # 数据类
from typing import List, Dict  # 类型注解

# 项目根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]  # backend/ 上一级
# 默认数据目录
DEFAULT_DATA_DIR: Path = Path(os.getenv("CHAN_DATA_DIR", PROJECT_ROOT / "var"))  # var 目录
# 默认数据库路径
DEFAULT_DB_PATH: Path = DEFAULT_DATA_DIR / "data.sqlite"  # SQLite 文件
# 默认配置文件路径
DEFAULT_CONFIG_PATH: Path = DEFAULT_DATA_DIR / "config.json"  # 用户配置

@dataclass  # 定义设置类
class Settings:
    # ---- 服务器与 CORS ----
    host: str = os.getenv("CHAN_HOST", "0.0.0.0")  # 监听地址
    port: int = int(os.getenv("CHAN_PORT", "8000"))  # 端口
    debug: bool = os.getenv("CHAN_DEBUG", "1") == "1"  # 调试开关（DEV=True/PROD=False）
    cors_origins: List[str] = None  # CORS 白名单

    # ---- 本地路径 ----
    data_dir: Path = DEFAULT_DATA_DIR  # 数据目录
    db_path: Path = DEFAULT_DB_PATH  # DB 路径
    user_config_path: Path = DEFAULT_CONFIG_PATH  # 配置文件

    # ---- 并发/重试（简化） ----
    fetch_concurrency: int = int(os.getenv("CHAN_FETCH_CONCURRENCY", "3"))  # 并发数
    retry_max_attempts: int = int(os.getenv("CHAN_RETRY_MAX_ATTEMPTS", "0"))  # 重试次数
    retry_base_delay_ms: int = int(os.getenv("CHAN_RETRY_BASE_DELAY_MS", "500"))  # 重试基延迟

    # ---- 缓存与清理策略 ----
    cache_max_rows: int = int(os.getenv("CHAN_CACHE_MAX_ROWS", "5000000"))  # 缓存最大行数
    cache_ttl_days: int = int(os.getenv("CHAN_CACHE_TTL_DAYS", "60"))  # TTL 天数
    cache_cleanup_interval_min: int = int(os.getenv("CHAN_CACHE_CLEANUP_INTERVAL_MIN", "30"))  # 清理频率

    # ---- 1d 近端判定 ----
    daily_fresh_cutoff_hour: int = int(os.getenv("CHAN_DAILY_FRESH_CUTOFF_HOUR", "18"))  # 当日最新的截止小时

    # ---- 时区与后台任务 ----
    timezone: str = "Asia/Shanghai"  # 时区
    autostart_watchlist_sync: bool = os.getenv("CHAN_AUTOSTART_WATCHLIST_SYNC", "0") == "1"  # 启动时是否同步自选

    # ---- 日志（文件与级别） ----
    log_file: Path = Path(os.getenv("CHAN_LOG_FILE", PROJECT_ROOT / "chan-theory.log"))  # 日志路径
    log_level: str = os.getenv("CHAN_LOG_LEVEL", "DEBUG" if os.getenv("CHAN_DEBUG", "1") == "1" else "INFO")  # 级别
    log_max_bytes: int = int(os.getenv("CHAN_LOG_MAX_BYTES", str(50 * 1024 * 1024)))  # 50MB
    log_backup_count: int = int(os.getenv("CHAN_LOG_BACKUP_COUNT", "5"))  # 备份 5 份

    # ---- 日志（定向与字段开关） ----
    log_debug_trace_ids_raw: str = os.getenv("CHAN_LOG_DEBUG_TRACE_IDS", "")  # trace 白名单（CSV）
    log_debug_trace_ids: List[str] = None  # 解析后的列表
    # Summary 模式：仅概要字段（建议：DEV 默认 0，PROD 默认 1；此处以环境为主）
    log_summary: bool = os.getenv("CHAN_LOG_SUMMARY", "0" if os.getenv("CHAN_DEBUG", "1") == "1" else "1") == "1"
    # 是否包含 request/result 细节（默认关闭，按需开启）
    log_include_request: bool = os.getenv("CHAN_LOG_INCLUDE_REQUEST", "0") == "1"
    log_include_result: bool = os.getenv("CHAN_LOG_INCLUDE_RESULT", "0") == "1"
    # 模块级别覆盖："symbols=DEBUG,market=INFO"
    log_module_levels_raw: str = os.getenv("CHAN_LOG_MODULE_LEVELS", "")
    log_module_levels: Dict[str, str] = None  # 解析后的映射

    def __post_init__(self):
        # CORS 白名单默认
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:3000", "http://127.0.0.1:3000",
            ]
        # 路径规范化与目录存在性
        self.data_dir.mkdir(parents=True, exist_ok=True)  # 确保 var 目录
        self.db_path = Path(self.db_path).resolve()  # 规范 DB 路径
        self.user_config_path = Path(self.user_config_path).resolve()  # 规范配置文件
        self.log_file = Path(self.log_file).resolve()  # 规范日志文件路径
        # 解析 trace 白名单
        raw = str(self.log_debug_trace_ids_raw or "").strip()
        self.log_debug_trace_ids = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
        # 解析模块级别映射（例：symbols=DEBUG,market=INFO）
        self.log_module_levels = {}
        raw_mod = str(self.log_module_levels_raw or "").strip()
        if raw_mod:
            for pair in raw_mod.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip().upper()
                    if k and v:
                        self.log_module_levels[k] = v

# 创建全局 settings 实例
settings = Settings()
