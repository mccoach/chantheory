# backend/services/config.py
# ==============================
# 说明：用户配置服务（config.json）
# - 单文件管理 + 原子写 + 轮换备份（.bak/.bak2）+ 镜像 config.applied.json
# - 允许用户直接修改 config.json（外部编辑）；提供文件变更检测与自动应用
# - 支持数据库路径迁移（调用 db.migrate_db_file），并更新运行时 settings
# - 本次精简：DEFAULT_CONFIG.symbol_index_categories 收敛为 ["A","ETF","LOF"]
# ==============================

from __future__ import annotations  # 允许前置注解

# 标准库
import threading  # 文件监听线程
import time       # 轮询间隔
from pathlib import Path  # 路径处理
from typing import Dict, Any, Optional  # 类型提示

# 项目内
from backend.settings import settings  # 全局配置（含 db_path/fetch_concurrency/retry 等）
from backend.utils.fileio import atomic_write_json, read_json_safe, file_signature  # 原子写/安全读/签名
from backend.db.sqlite import migrate_db_file  # 数据库迁移（在线复制 + 完整性校验）

# 配置文件与镜像文件路径
CONFIG_PATH: Path = settings.user_config_path                 # 主配置路径
APPLIED_PATH: Path = CONFIG_PATH.with_name("config.applied.json")  # 镜像路径

# 监听控制
_watcher_thread: Optional[threading.Thread] = None  # 监听线程句柄
_watcher_stop = threading.Event()                   # 停止事件
_last_sig: tuple[Optional[float], Optional[int]] = (None, None)  # 上次签名(mtime,size)

# 默认配置（精简版）
DEFAULT_CONFIG: Dict[str, Any] = {
    "db_path": str(settings.db_path),                    # SQLite 路径
    "fetch_concurrency": settings.fetch_concurrency,     # 并发
    "retry_max_attempts": settings.retry_max_attempts,   # 重试次数
    "retry_base_delay_ms": settings.retry_base_delay_ms, # 重试基延迟
    "watchlist": [],                                     # 自选池
    "theme": "dark",                                     # 主题
    # 索引拉取类别与顺序（精简为 A/ETF/LOF）
    "symbol_index_categories": [
        "A", "ETF", "LOF",  # 默认优先级：A → ETF → LOF
    ],
}

def _ensure_config_file() -> Dict[str, Any]:
    """确保 config.json 存在；若不存在则写入默认并创建镜像。"""
    obj, err = read_json_safe(CONFIG_PATH, default=None)  # 读取现有配置（可能不存在）
    if obj is None:                                       # 文件缺失或损坏
        atomic_write_json(CONFIG_PATH, DEFAULT_CONFIG)    # 写默认配置
        atomic_write_json(APPLIED_PATH, DEFAULT_CONFIG)   # 同步镜像
        return DEFAULT_CONFIG                             # 返回默认
    # 镜像缺失则补写
    app, _ = read_json_safe(APPLIED_PATH, default=None)   # 读取镜像
    if app is None:
        atomic_write_json(APPLIED_PATH, obj)              # 同步镜像一次
    # 兼容旧配置：若缺少 symbol_index_categories 则补默认（精简三类）
    if "symbol_index_categories" not in obj:
        obj["symbol_index_categories"] = list(DEFAULT_CONFIG["symbol_index_categories"])
        atomic_write_json(CONFIG_PATH, obj)               # 回写一次
        atomic_write_json(APPLIED_PATH, obj)              # 镜像同步
    return obj                                            # 返回配置对象

def get_config() -> Dict[str, Any]:
    """读取当前配置（不可用则创建默认）。"""
    return _ensure_config_file()                          # 返回配置

def _apply_runtime(cfg: Dict[str, Any]) -> None:
    """将配置应用到运行时（settings 与数据库路径）。"""
    # 应用并发/重试（容错，不抛出）
    try:
        settings.fetch_concurrency = int(cfg.get("fetch_concurrency", settings.fetch_concurrency))
    except Exception:
        pass
    try:
        settings.retry_max_attempts = int(cfg.get("retry_max_attempts", settings.retry_max_attempts))
        settings.retry_base_delay_ms = int(cfg.get("retry_base_delay_ms", settings.retry_base_delay_ms))
    except Exception:
        pass
    # 数据库路径变更则迁移（在线拷贝 + 完整性检查）
    new_db = Path(cfg.get("db_path", str(settings.db_path))).resolve()  # 新路径
    if str(new_db) != str(settings.db_path):                            # 确实变化
        res = migrate_db_file(new_db)                                    # 迁移校验
        if res.get("ok"):                                               # 成功
            settings.db_path = new_db                                    # 切换路径
        else:                                                           # 失败：回滚配置
            cfg["db_path"] = str(settings.db_path)
            atomic_write_json(CONFIG_PATH, cfg)
    # 更新镜像（注意：不把 symbol_index_categories 投射到 settings，避免污染全局）
    atomic_write_json(APPLIED_PATH, cfg)                                 # 镜像“已应用”版本

def set_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    """更新配置（部分字段），并应用到运行时。"""
    current = get_config()                  # 当前配置
    merged = dict(current)                  # 拷贝
    merged.update(patch or {})              # 合并补丁
    atomic_write_json(CONFIG_PATH, merged)  # 写回
    _apply_runtime(merged)                  # 应用（并发/重试/迁移/镜像）
    global _last_sig                        # 更新签名
    _last_sig = file_signature(CONFIG_PATH)
    return merged                           # 返回最新配置

def _watch_loop(interval_sec: float = 2.0) -> None:
    """后台监听 config.json 变更，自动应用；解析失败跳过一轮。"""
    global _last_sig
    _last_sig = file_signature(CONFIG_PATH)       # 初始化签名
    while not _watcher_stop.is_set():             # 循环直到停止
        time.sleep(interval_sec)                  # 等待间隔
        try:
            sig = file_signature(CONFIG_PATH)     # 读取当前签名
            if sig != _last_sig:                  # 发现变化
                cfg, err = read_json_safe(CONFIG_PATH, default=None)
                if cfg is None:                   # 解析失败（可能正在编辑）
                    continue                      # 跳过本轮
                _apply_runtime(cfg)               # 应用新配置
                _last_sig = sig                   # 更新签名
        except Exception:
            continue                              # 容错：不中断监听

def start_watcher() -> None:
    """启动配置文件监听线程（幂等）。"""
    global _watcher_thread
    if _watcher_thread is not None and _watcher_thread.is_alive():  # 已运行
        return
    _watcher_stop.clear()                                            # 清停止标志
    t = threading.Thread(target=_watch_loop, name="config-watcher", daemon=True)  # 守护线程
    t.start()                                                        # 启动
    _watcher_thread = t                                              # 保存句柄

def stop_watcher() -> None:
    """停止监听线程（需要时调用）。"""
    _watcher_stop.set()                                              # 置停止
