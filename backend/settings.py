# backend/settings.py
# ==============================
# 设置中心（统一归口版）
#
# 本轮改动（盘后数据导入 import 第一阶段）：
#   - 新增 tdx_vipdoc_dir：通达信本地盘后数据目录（唯一真相源根目录）
#   - 当前第一阶段只支持从 tdx_vipdoc_dir 递归扫描 .day 文件
#   - 删除旧 after_hours 远程 bulk 专用配置，不再为旧机制保留冗余开关
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
DEFAULT_TDX_HQ_CACHE_DIR: Path = Path(r"D:\TDX_new\T0002\hq_cache")
DEFAULT_TDX_VIPDOC_DIR: Path = Path(r"D:\TDX_new\vipdoc")


@dataclass
class Settings:
    # ==========================================================
    # 一、服务启动相关
    # ==========================================================
    # host/port：FastAPI 服务监听地址与端口
    # - 一般不用改，除非你想让局域网其他设备访问
    host: str = "0.0.0.0"
    port: int = 8000

    # debug：调试开关
    # - True：错误响应会包含更多细节（便于开发）
    # - False：生产模式隐藏细节（更安全）
    debug: bool = True

    # cors_origins：允许哪些前端地址跨域访问后端
    # - 如果你的前端换了端口/域名，需要把新地址加到这里
    cors_origins: List[str] = None

    # ==========================================================
    # 二、本地路径（数据落地位置）
    # ==========================================================
    # data_dir：所有本地数据目录
    data_dir: Path = DEFAULT_DATA_DIR

    # db_path：SQLite 数据库文件路径
    db_path: Path = DEFAULT_DB_PATH

    # user_config_path：用户配置文件路径（config.json）
    user_config_path: Path = DEFAULT_CONFIG_PATH

    # TDX 本地行情缓存目录（symbol_index / profile_snapshot / trade_calendar）
    tdx_hq_cache_dir: Path = DEFAULT_TDX_HQ_CACHE_DIR

    # NEW：通达信盘后本地数据根目录（盘后数据导入 import 唯一真相源）
    # 说明：
    #   - 必须从该根目录开始递归扫描全部子目录
    #   - 当前第一阶段只纳入 .day 文件
    #   - 将来 .lc1 / .lc5 会在同一递归扫描框架下扩展
    tdx_vipdoc_dir: Path = DEFAULT_TDX_VIPDOC_DIR

    # ==========================================================
    # 三、网络与重试（影响“稳定性”与“速度”）
    # ==========================================================
    # retry_max_attempts：请求失败时最多重试次数
    # - 越大：越不容易因为临时网络问题失败，但整体会更慢
    # - 越小：更快失败，更快暴露问题
    retry_max_attempts: int = 3

    # retry_base_delay_ms：重试的基础等待时间（毫秒）
    # - 实际等待会指数增长（第一次等 base，第二次等 2*base...）并带随机抖动
    retry_base_delay_ms: int = 3000

    # ==========================================================
    # 四、全局网络限流（最关键的反爬控制闸门）
    # ==========================================================
    # network_limiter_enabled：是否启用全局限流
    # - True：所有被 @limit_async_network_io 包裹的请求都会被限速
    # - False：不限速，速度可能很快，但更容易触发反爬、被封IP/封UA
    network_limiter_enabled: bool = True

    # network_requests_per_second（RPS）：全系统每秒允许发起多少个网络请求（平均）
    # - 这是你提速最直接的旋钮之一
    # - 例子：2.0 表示全系统平均每秒最多 2 个请求；5.0 表示最多 5 个请求
    # - 你“先尽量快探索边界”，可以先设 5.0
    network_requests_per_second: float = 5.0

    # network_max_burst_tokens：突发令牌数（允许短时间“瞬间多发几个请求”）
    # - 例子：10 表示可以短时间积攒最多 10 个令牌，一口气发 10 个请求后再慢下来
    # - 太小：会显得“卡顿”，吞吐上不去
    # - 太大：可能瞬间打爆对方接口，更容易触发反爬
    network_max_burst_tokens: int = 10

    # ==========================================================
    # 四点一、分源限流（在保留全局限流基础上按数据源再限一次）
    # ==========================================================
    # 说明（小白版）：
    #   - 全局限流：控制全系统总出网速度（总闸门）
    #   - 分源限流：控制某一个数据源（新浪/东财/baostock）自身的出网速度（分闸门）
    #
    # 规则：
    #   - 若某数据源未配置，默认跟随全局限流（不额外限制）
    #   - rps 表示平均每秒允许请求数；burst 表示允许短时间突发的最大令牌数
    provider_limiters: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "sina": {"rps": 1, "burst": 1},
        "eastmoney": {"rps": 1, "burst": 1},
        "baostock": {"rps": 1, "burst": 1},
    })

    # ==========================================================
    # 五、执行器并发（盘后提速的核心）
    # ==========================================================
    # executor_concurrency：同时运行多少个 Task（多少个“工人”并行干活）
    # - 你现在最大瓶颈就是原来只有 1 个工人（并发=1）
    # - 推荐先设 16：会明显提速
    # - 如果你机器配置好也可以试 32（更快，但更容易触发反爬）
    executor_concurrency: int = 8

    # ==========================================================
    # 五点一、Task 级超时兜底（确保前端不再卡死）
    # ==========================================================
    # 语义：单个 Task 从开始执行到结束，最多允许多少秒；
    # 超过则视为 failed，并保证发出 task_done，bulk 状态可推进。
    task_timeout_seconds: float = 30.0

    # ==========================================================
    # 五点二、运行时指标推送（线程数监测）
    # ==========================================================
    runtime_metrics_interval_seconds: float = 3.0

    # ==========================================================
    # 六、业务常量（一般不用动）
    # ==========================================================
    timezone: str = "Asia/Shanghai"
    default_market: str = "CN"
    data_source_name: str = "unified_executor"
    sync_init_start_date: int = 19900101

    # ==========================================================
    # 七、日志系统
    # ==========================================================
    log_file: Path = PROJECT_ROOT / "chan-theory.log"

    # log_level：全局日志级别
    # - INFO：推荐常用
    # - DEBUG：会很吵，但排错更方便
    log_level: str = "INFO"

    # log_max_bytes：单个日志文件最大大小（字节），超过后滚动
    log_max_bytes: int = 16 * 1024 * 1024  # 16MB

    # log_backup_count：最多保留多少个滚动备份文件
    log_backup_count: int = 10

    # log_debug_trace_ids_raw：仅对指定 trace_id 放行 DEBUG（高级用法）
    log_debug_trace_ids_raw: str = ""
    log_debug_trace_ids: List[str] = None

    # log_summary：是否开启摘要模式（True 更省日志体积）
    log_summary: bool = False

    # log_include_request：日志是否包含请求详情
    log_include_request: bool = False

    # log_include_result：日志是否包含结果详情
    log_include_result: bool = False

    # log_module_levels：模块级日志级别覆盖
    log_module_levels_raw: str = ""
    log_module_levels: Dict[str, str] = None

    def __post_init__(self):
        # CORS 默认值
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.db_path).resolve()
        self.user_config_path = Path(self.user_config_path).resolve()
        self.tdx_hq_cache_dir = Path(self.tdx_hq_cache_dir).resolve()
        self.tdx_vipdoc_dir = Path(self.tdx_vipdoc_dir).resolve()

        # trace_id 白名单解析
        raw_trace_ids = str(self.log_debug_trace_ids_raw or "").strip()
        self.log_debug_trace_ids = (
            [s.strip() for s in raw_trace_ids.split(",") if s.strip()]
            if raw_trace_ids else []
        )

        # executor_concurrency 防御性兜底：至少为 1
        try:
            self.executor_concurrency = max(1, int(self.executor_concurrency))
        except Exception:
            self.executor_concurrency = 1

        # network 参数兜底：避免写错导致崩溃
        try:
            self.network_requests_per_second = float(self.network_requests_per_second)
        except Exception:
            self.network_requests_per_second = 2.0

        try:
            self.network_max_burst_tokens = max(1, int(self.network_max_burst_tokens))
        except Exception:
            self.network_max_burst_tokens = 3

        # Task timeout 兜底
        try:
            self.task_timeout_seconds = float(self.task_timeout_seconds)
            if self.task_timeout_seconds <= 0:
                self.task_timeout_seconds = 30.0
        except Exception:
            self.task_timeout_seconds = 30.0

        # runtime metrics interval 兜底
        try:
            self.runtime_metrics_interval_seconds = float(self.runtime_metrics_interval_seconds)
            if self.runtime_metrics_interval_seconds <= 0:
                self.runtime_metrics_interval_seconds = 1.0
        except Exception:
            self.runtime_metrics_interval_seconds = 1.0

        # provider_limiters 兜底
        if not isinstance(self.provider_limiters, dict):
            self.provider_limiters = {}
        # 逐项清洗
        cleaned: Dict[str, Dict[str, Any]] = {}
        for k, v in self.provider_limiters.items():
            if not isinstance(k, str) or not k.strip():
                continue
            if not isinstance(v, dict):
                continue
            try:
                rps = float(v.get("rps", self.network_requests_per_second))
            except Exception:
                rps = float(self.network_requests_per_second)
            try:
                burst = int(v.get("burst", self.network_max_burst_tokens))
                burst = max(1, burst)
            except Exception:
                burst = int(self.network_max_burst_tokens)
            cleaned[k.strip().lower()] = {"rps": rps, "burst": burst}
        self.provider_limiters = cleaned

        self.log_module_levels = {
            "eastmoney_adapter.kline": "WARN",
            "sse_adapter": "WARN",
            "sse_adapter.profile": "WARN",
            "szse_adapter": "WARN",
            "szse_adapter.profile": "WARN",
            "baostock_adapter": "WARN",
            "sina_adapter": "WARN",
        }


settings = Settings()

# ==============================
# 数据类型完整定义
# ==============================

DATA_TYPE_DEFINITIONS = {
    "trade_calendar": {
        "name": "交易日历",
        "category": "trade_calendar",
        "priority": 100,
        "sse_notify": True,
    },
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
    "symbol_index": {
        "name": "标的列表",
        "category": "symbol_index",
        "priority": 300,
        "sse_notify": True,
    },
    "profile_snapshot": {
        "name": "档案快照",
        "category": "profile",
        "priority": 400,
        "sse_notify": True,
    },
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

    说明（小白版）：
      - 这块是为了模拟浏览器请求，降低被识别为“机器人”的概率
      - 一般不用动，除非你遇到某个网站突然开始封禁
    """

    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    ])

    accept_languages: List[str] = field(default_factory=lambda: [
        "zh-CN,zh;q=0.9",
        "zh-CN,zh;q=0.9,en;q=0.8",
        "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "zh-CN,zh-TW;q=0.9,zh;q=0.8",
    ])

    connection_types: List[str] = field(default_factory=lambda: [
        "keep-alive",
        "close",
    ])

    # enable_random_delay：是否在请求间随机睡一会儿（更像真人，但会变慢）
    enable_random_delay: bool = os.getenv("SPIDER_RANDOM_DELAY", "1") == "1"
    random_delay_range: tuple = (0.5, 2.0)

    enable_header_randomization: bool = os.getenv("SPIDER_HEADER_RANDOM", "1") == "1"


spider_config = SpiderConfig()
