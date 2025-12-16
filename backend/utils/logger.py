# backend/utils/logger.py
# ==============================
# 说明：全局结构化日志工具（NDJSON 单文件，滚动 50MB×5 · 分级与字段开关版）
# 关键能力：
# - 单一日志文件：settings.log_file（默认项目根 chan-theory.log）
# - 滚动策略：maxBytes=50MB，backupCount=5（settings 可配置）
# - NDJSON：每条日志一行 JSON，便于 tail/grep/jq/filebeat 等处理
# - 级别控制：
#   * 全局级别：settings.log_level（DEV 默认 DEBUG，PROD 默认 INFO）
#   * 模块级覆盖：settings.log_module_levels（如 "symbols=DEBUG,market=INFO"）
#   * trace 定向 DEBUG：settings.log_debug_trace_ids（命中则放行 DEBUG）
# - 字段开关（Summary vs Detailed）：
#   * settings.log_summary=True 时，仅保留“概要字段”
#   * settings.log_include_request / log_include_result 控制是否包含请求/结果细节
# - 低侵入：模块调用 log_event() 即可；内部自动补齐 ts/host/pid/thread 等，并按开关过滤字段
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 3.8+）

# 标准库
import logging  # 日志基础
from logging.handlers import RotatingFileHandler  # 滚动文件处理器
import json  # JSON 序列化
import socket  # 主机名
import os  # 进程号
import threading  # 线程名
from datetime import datetime  # 时间
from typing import Optional, Dict, Any  # 类型注解
import itertools  # 自增计数器

# 项目内
from backend.settings import settings  # 全局配置（含日志配置）

class TimestampRotatingFileHandler(RotatingFileHandler):
    """
    自定义滚动文件处理器：
      - 按大小滚动（沿用 RotatingFileHandler 的 maxBytes / backupCount 逻辑）
      - 滚动时重命名规则：
          base:  /path/to/chan-theory.log
          归档:  /path/to/chan-theory_YYYYMMDD_HHMMSS.log
      - 保留原始扩展名 .log 不变
      - 只保留最近 backupCount 个归档文件（按修改时间排序，旧的删掉）
    """

    def doRollover(self):
        # 先关闭当前文件句柄
        if self.stream:
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        # 如果当前文件不存在（极端情况），直接返回
        if not os.path.exists(self.baseFilename):
            return

        # 计算带时间戳的新文件名
        base, ext = os.path.splitext(self.baseFilename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dfn = f"{base}_{timestamp}{ext}"

        # 如目标名已存在，先删掉
        try:
            if os.path.exists(dfn):
                os.remove(dfn)
        except Exception:
            # 删除失败不应阻止后续重命名
            pass

        # 将当前日志文件重命名为带时间戳的归档文件
        try:
            os.rename(self.baseFilename, dfn)
        except Exception:
            # 重命名失败直接返回，避免影响后续写入
            return

        # 清理多余的旧归档，只保留最近 backupCount 个
        try:
            if self.backupCount > 0:
                base_dir = os.path.dirname(self.baseFilename)
                base_name = os.path.basename(base)
                # 匹配形如 chan-theory_*.log 的文件
                pattern_prefix = os.path.join(base_dir, f"{base_name}_")
                candidates = []
                for name in os.listdir(base_dir or "."):
                    full_path = os.path.join(base_dir, name)
                    if name.startswith(f"{base_name}_") and name.endswith(ext):
                        try:
                            mtime = os.path.getmtime(full_path)
                        except OSError:
                            mtime = 0
                        candidates.append((mtime, full_path))
                # 按修改时间从新到旧排序
                candidates.sort(reverse=True)
                # 保留最新的 backupCount 个，其余删除
                for _, path in candidates[self.backupCount:]:
                    try:
                        os.remove(path)
                    except Exception:
                        # 删除失败不影响整体功能
                        pass
        except Exception:
            # 清理过程出现任何问题都不影响主流程
            pass

        # 重新打开一个新文件，以 baseFilename 继续写
        self.mode = "a"
        try:
            self.stream = self._open()
        except Exception:
            self.stream = None

# -----------------------
# 模块级常量与状态
# -----------------------

_INITIALIZED: bool = False  # 是否已初始化
_HOSTNAME: str = socket.gethostname()  # 主机名
_PID: int = os.getpid()  # 进程 ID
_SPAN_COUNTER = itertools.count(1)  # 简单 span 计数器（用于生成 span_id）

# -----------------------
# 级别与过滤辅助
# -----------------------

def _level_from_str(level: str) -> int:
    """将字符串级别转为 logging 常量；未知时默认 INFO。"""
    lv = str(level or "").strip().upper()  # 规范大小写
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(lv, logging.INFO)  # 缺省 INFO

def _service_min_level(service: str) -> int:
    """返回指定 service 的最低输出级别（模块级覆盖），未设置则返回根级别。"""
    if not service:
        return logging.getLogger().level  # 根级别
    # 从 settings.log_module_levels 中取模块覆盖（如 {'symbols':'DEBUG'}）
    mod = (settings.log_module_levels or {}).get(service, "")  # 字符串级别
    if mod:
        return _level_from_str(mod)  # 模块覆盖
    return logging.getLogger().level  # 根级别

def _should_emit_debug(trace_id: Optional[str]) -> bool:
    """在全局级别高于 DEBUG 时，是否因命中特定 trace_id 而放行 DEBUG。"""
    allow = getattr(settings, "log_debug_trace_ids", [])  # 允许列表
    if not allow or not trace_id:  # 两边缺一不可
        return False  # 不放行
    return str(trace_id).strip() in {str(x).strip() for x in allow}  # 命中放行

# -----------------------
# 初始化与获取 logger
# -----------------------

def init_logger() -> None:
    """初始化根 logger（只执行一次）。"""
    global _INITIALIZED  # 引用模块状态
    if _INITIALIZED:  # 已初始化则返回
        return
    # 根 logger
    root = logging.getLogger()  # 获取根
    root.setLevel(_level_from_str(settings.log_level))  # 设置全局级别
    # 滚动文件处理器
    handler = TimestampRotatingFileHandler(
        filename=str(settings.log_file),  # 日志路径
        maxBytes=int(settings.log_max_bytes),  # 单文件最大字节数
        backupCount=int(settings.log_backup_count),  # 备份份数
        encoding="utf-8",  # UTF-8
    )
    # 简洁 Formatter：仅输出 message（message 已是 JSON）
    handler.setFormatter(logging.Formatter("%(message)s"))  # 行 = message
    root.addHandler(handler)  # 附加处理器
    # 抑制常见三方库的 DEBUG 噪音（保持 WARNING 以上）
    for noisy in ("urllib3", "requests", "botocore", "s3transfer"):
        try:
            logging.getLogger(noisy).setLevel(logging.WARNING)  # 提升门槛
        except Exception:
            pass  # 容错忽略
    _INITIALIZED = True  # 标记完成

def set_level(level: str) -> None:
    """动态调整全局日志级别（用于临时升级/降级）。"""
    logging.getLogger().setLevel(_level_from_str(level))  # 设置级别

def get_logger(service: str) -> logging.Logger:
    """按服务名返回 logger（继承根处理器与级别）。"""
    init_logger()  # 确保初始化
    return logging.getLogger(service or "app")  # 返回命名 logger

# -----------------------
# 构建与过滤日志记录
# -----------------------

def _now_iso() -> str:
    """本地时区 ISO8601（含偏移）。"""
    return datetime.now().astimezone().isoformat()  # 例如 2025-08-28T00:12:34.567+08:00

def _base_record(
    *,
    service: str,
    level: str,
    file: str,
    func: str,
    line: int,
    trace_id: Optional[str],
    event: str,
    message: str,
) -> Dict[str, Any]:
    """构建记录的基础字段（在 Summary 模式下可能被裁剪）。"""
    return {
        "ts": _now_iso(),  # 时间
        "level": level,  # 级别
        "source_kind": "backend",  # 来源：后端
        "service": service,  # 服务名
        "file": file,  # 文件
        "func": func,  # 函数
        "line": line,  # 行号
        "trace_id": trace_id or "",  # 链路 ID
        "event": event,  # 事件
        "message": message,  # 摘要
        "host": _HOSTNAME,  # 主机
        "pid": _PID,  # 进程
        "thread": threading.current_thread().name,  # 线程
        "app": {  # 应用元信息
            "name": "ChanTheory",  # 名称
            "version": "1.0.0",  # 版本
            "env": "DEV" if settings.debug else "PROD",  # 环境
        },
    }

def _apply_summary_filter(rec: Dict[str, Any], is_error: bool) -> Dict[str, Any]:
    """根据开关过滤字段：
    - Summary 模式：仅保留概要字段 + 可选的 request/result/db
    - 非 Summary：保留全部
    - 错误：即使 Summary，也保留 file/func/line 以便定位
    """
    # 若非 Summary 模式，直接返回原记录
    if not bool(getattr(settings, "log_summary", False)):
        return rec  # 详尽模式保留全部
    # Summary 模式：定义保留的核心键
    essentials = {
        "ts", "level", "source_kind", "service", "event", "message", "trace_id",
        "category", "action", "duration_ms",
        "error_code", "error_message",  # 错误概要
    }
    # DB 概要字段（通常有用）
    db_keep = {"db"}  # db 子对象整体保留（其中的表名/影响行/事务）
    # 结果概要字段（只保留 summary/rows 等小尺寸）
    result_keep = {"result"} if bool(getattr(settings, "log_include_result", False)) else set()
    # 请求概要（仅当开关开启）
    request_keep = {"request"} if bool(getattr(settings, "log_include_request", False)) else set()
    # 错误时，额外保留文件位置信息以利定位
    position_keep = {"file", "func", "line"} if is_error else set()
    # 允许保留的键集合
    allow = essentials | db_keep | result_keep | request_keep | position_keep
    # 构造新记录（只留允许的键）
    out = {k: v for k, v in rec.items() if k in allow}
    # 如果 result 存在，且是 dict，建议再做一次“仅保留小字段”的过滤（防止调用方传大对象）
    if "result" in out and isinstance(out["result"], dict):
        # 仅保留常见小字段
        small = {}
        for k in ("status_code", "rows", "bytes", "summary", "truncated"):
            if k in out["result"]:
                small[k] = out["result"][k]
        out["result"] = small
    # 同理对 request 也可裁剪（这里只保留 endpoint/method/query）
    if "request" in out and isinstance(out["request"], dict):
        rq = out["request"]
        small_rq = {}
        for k in ("endpoint", "method", "query", "params", "body_size"):
            if k in rq:
                small_rq[k] = rq[k]
        out["request"] = small_rq
    return out  # 返回过滤后的记录

def next_span_id(prefix: str = "span") -> str:
    """生成一个简单的 span_id（用于标记链路子步骤）。"""
    return f"{prefix}-{next(_SPAN_COUNTER):04d}"  # 如 span-0001

# -----------------------
# 对外主函数：记录事件
# -----------------------

def log_event(
    logger: logging.Logger,
    *,
    service: str,
    level: str,
    file: str,
    func: str,
    line: int,
    trace_id: Optional[str],
    event: str,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
    force_debug: bool = False,
) -> None:
    """记录一条结构化日志（NDJSON），自动按开关裁剪字段与分级放行。
    参数：
    - logger：通过 get_logger(service) 获取的命名 logger
    - service：服务名（模块名），用于模块级别覆盖
    - level：文本级别（"DEBUG"/"INFO"/"WARN"/"ERROR"）
    - file/func/line：源位置（用于错误定位）
    - trace_id：调用链路 ID（API/后台任务）
    - event：事件名（如 "symbols.fetch.start"）
    - message：人可读摘要
    - extra：建议字段（dict），包含 category/action/duration_ms/request/result/db/error_code 等
    - force_debug：强制以 DEBUG 记录（便于特定场景放行）
    """
    # 计算目标与模块级最低级别
    target_level = _level_from_str(level)  # 目标级别
    min_level = _service_min_level(service)  # 模块最低级别
    root_level = logging.getLogger().level  # 根级别

    # 判断是否放行（级别不足 → 丢弃），但支持 trace 定向 DEBUG 或 force_debug 放行
    if target_level < min_level:
        # 仅当目标是 DEBUG 且命中 trace_id 或强制放行时，才写入
        if not (target_level == logging.DEBUG and (_should_emit_debug(trace_id) or force_debug)):
            return  # 丢弃该条
    # 构造基础记录
    rec = _base_record(
        service=service, level=level, file=file, func=func, line=line,
        trace_id=trace_id, event=event, message=message,
    )
    # 合并扩展字段
    if extra:
        try:
            rec.update(extra)  # 合并上下文（如 category/action/request/result/db）
        except Exception:
            # 容错：扩展合并失败不应阻断日志
            pass
    # 是否错误（用于 Summary 模式下保留 file/func/line）
    is_error = (target_level >= logging.ERROR) or (str(rec.get("action", "")).lower() in {"fail", "error"})
    # 应用 Summary 过滤（根据 settings.log_summary 与 include_request/result 开关）
    rec = _apply_summary_filter(rec, is_error=is_error)
    # 序列化为紧凑 JSON 行（分隔符紧凑、保留中文）
    try:
        text = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        # 序列化失败兜底：写一条错误日志（尽力）
        text = f'{{"ts":"{_now_iso()}","level":"ERROR","service":"{service}","event":"logger.serialize.fail","message":"failed to serialize log record"}}'
        target_level = logging.ERROR  # 强制错误级别

    # 按级别输出（即使全局级别较高，前面已做过“是否放行”的判断）
    if target_level >= logging.ERROR:
        logger.error(text)
    elif target_level >= logging.WARNING:
        logger.warning(text)
    elif target_level >= logging.INFO:
        logger.info(text)
    else:
        logger.debug(text)

# 初始化（模块导入即生效）
init_logger()  # 确保处理器安装
