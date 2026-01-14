# backend/settings.py
# ==============================
# V8.1 - After Hours Bulk 设置收敛 + priority 全量 ×10
#
# 改动：
#   1) Settings 新增：
#        - bulk_max_jobs（默认 30000）
#        - after_hours_priority（默认 1000）
#   2) DATA_TYPE_DEFINITIONS.priority 全量乘以 10：
#        10→100, 20→200, 30→300, 40→400
#      仅改变数值尺度，不改变相对优先级顺序。
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
    retry_base_delay_ms: int = int(
        os.getenv("CHAN_RETRY_BASE_DELAY_MS", "3000"))

    # 全局网络限流器
    network_limiter_enabled: bool = os.getenv("CHAN_NETWORK_LIMITER_ENABLED",
                                              "1") == "1"
    network_requests_per_second: float = float(
        os.getenv("CHAN_NETWORK_RPS", "2.0"))
    network_max_burst_tokens: int = int(os.getenv("CHAN_NETWORK_BURST", "3"))

    # 业务常量
    timezone: str = "Asia/Shanghai"
    default_market: str = "CN"
    data_source_name: str = "unified_executor"
    sync_init_start_date: int = 19900101

    # ==============================
    # After Hours Bulk（盘后批量入队）设置
    # ==============================
    # 单次 /api/ensure-data/bulk 允许提交的最大 job 数（建议值，后端不因超限拒绝）
    bulk_max_jobs: int = int(os.getenv("CHAN_BULK_MAX_JOBS", "30000"))
    # 盘后批量任务默认 priority（数值越大优先级越低；1000 低于常规 100/200/300/400）
    after_hours_priority: int = int(os.getenv("CHAN_AFTER_HOURS_PRIORITY", "1000"))

    # 日志系统
    # log_file: 日志文件路径
    log_file: Path = PROJECT_ROOT / "chan-theory.log"

    # log_level: 全局日志级别（字符串）
    # 可选值（不区分大小写）："CRITICAL","ERROR","WARNING","WARN","INFO","DEBUG","NOTSET"
    # 修改方式：直接改这里，例如 log_level="DEBUG"
    log_level: str = "INFO"

    # log_max_bytes: 单个日志文件最大大小（字节），超过后滚动
    log_max_bytes: int = 16 * 1024 * 1024  # 16MB

    # log_backup_count: 最多保留多少个滚动备份文件
    log_backup_count: int = 10

    # log_debug_trace_ids_raw: 保留字段（目前不用环境变量），仍允许你在这里手工填逗号分隔的 trace_id
    log_debug_trace_ids_raw: str = ""
    log_debug_trace_ids: List[str] = None

    # log_summary: 是否开启摘要模式
    #   True  -> 只保留关键字段（推荐生产用）
    #   False -> 保留所有字段（推荐调试用）
    log_summary: bool = True

    # 是否在日志中包含 HTTP 请求详情（endpoint/method/query）
    log_include_request: bool = False

    # 是否在日志中包含结果详情（status_code/rows 等）
    log_include_result: bool = False

    # log_module_levels_raw: 备用的“字符串形式配置”，暂不推荐使用环境变量，在 __post_init__ 里有默认值可直接改
    log_module_levels_raw: str = ""
    log_module_levels: Dict[str, str] = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.db_path).resolve()
        self.user_config_path = Path(self.user_config_path).resolve()
        raw_trace_ids = str(self.log_debug_trace_ids_raw or "").strip()
        self.log_debug_trace_ids = (
            [s.strip() for s in raw_trace_ids.split(",") if s.strip()]
            if raw_trace_ids else []
        )

        # 模块级日志级别默认值（你可以直接改这个字典来调整各模块日志级别）
        # 可选级别同 log_level："CRITICAL","ERROR","WARNING","WARN","INFO","DEBUG","NOTSET"
        self.log_module_levels = {
            "eastmoney_adapter.kline": "WARN",  # 东财K线适配器
            "sse_adapter": "WARN",             # 上交所适配器
            "szse_adapter": "WARN",            # 深交所适配器
            "baostock_adapter": "WARN",        # Baostock 适配器
            "sina_adapter": "WARN",            # 新浪适配器
        }


settings = Settings()

# ==============================
# 数据类型完整定义（仅核心 Task 类型 + watchlist_update）
# ==============================

DATA_TYPE_DEFINITIONS = {
    # P100：交易日历
    "trade_calendar": {
        "name": "交易日历",
        "category": "trade_calendar",
        "priority": 100,
        # 是否在任务结束时通过事件总线 → SSE 通知前端（执行器已不再依赖该字段）
        "sse_notify": True,
    },
    # P200：当前标的核心数据
    "current_kline": {
        "name": "当前K线",
        "category": "kline",
        "priority": 200,
        "sse_notify": True,
    },
    "current_factors": {
        "name": "当前复权因子",
        "category": "factors",
        "priority": 200,
        "sse_notify": True,
    },
    # P300：全局数据（标的列表）
    "symbol_index": {
        "name": "标的列表",
        "category": "symbol_index",
        "priority": 300,
        "sse_notify": True,
    },
    # P400：当前标的档案（不阻塞渲染）
    "current_profile": {
        "name": "当前档案",
        "category": "profile",
        "priority": 400,
        "sse_notify": True,
    },
    # P400：自选池更新（元数据类任务）
    "watchlist_update": {
        "name": "自选池更新",
        "category": "meta",
        "priority": 400,
        "sse_notify": True,
    },
}


# ==============================
# 爬虫通用参数池（V7.2 新增）
# ==============================


@dataclass
class SpiderConfig:
    """
    爬虫通用参数池

    设计原则：
      1. 仅管理与具体接口无关的参数（浏览器特征/语言偏好/连接方式）
      2. 不管理业务逻辑参数（Referer/sqlId/Accept 等）
      3. 支持环境变量覆盖

    职责边界：
      ✅ 负责：User-Agent 池、Accept-Language 池、Connection 池
      ❌ 不负责：Referer（业务逻辑）、Accept（接口类型）、Sec-Fetch-*（固定值）
    """

    # ===== User-Agent 池（核心反爬参数）=====
    user_agents: List[str] = field(default_factory=lambda: [
        # Chrome 140 (Windows) - 2025年1月最新版
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        # Chrome 137 (Windows) - 稳定版
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        # Edge 140 (Windows) - 2025年1月最新版
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
        # Chrome 140 (macOS)
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        # Firefox 133 (Windows) - 2025年1月最新版
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    ])

    # ===== Accept-Language 池（语言偏好混淆）=====
    accept_languages: List[str] = field(default_factory=lambda: [
        "zh-CN,zh;q=0.9",  # Chrome 简洁版（最常见）
        "zh-CN,zh;q=0.9,en;q=0.8",  # +英文
        "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",  # Edge 完整版
        "zh-CN,zh-TW;q=0.9,zh;q=0.8",  # +繁体中文
    ])

    # ===== Connection 类型池（连接行为混淆）=====
    connection_types: List[str] = field(default_factory=lambda: [
        "keep-alive",  # 长连接（95% 真实用户行为）
        "close",  # 短连接（5% 场景）
    ])

    # ===== 反爬策略开关 =====
    enable_random_delay: bool = os.getenv("SPIDER_RANDOM_DELAY", "1") == "1"
    random_delay_range: tuple = (0.5, 2.0)  # 随机延迟范围（秒）
    enable_header_randomization: bool = os.getenv("SPIDER_HEADER_RANDOM",
                                                  "1") == "1"


# 全局单例
spider_config = SpiderConfig()
