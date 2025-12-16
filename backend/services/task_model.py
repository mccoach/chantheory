# backend/services/task_model.py
# ==============================
# 说明：Task 模型与构建工具（统一 Task 结构）
#
# 设计要点：
#   - 一次 HTTP 请求 = 一个 Task；
#   - Task 内部字段与《Task / Job / SSE 两级体系最终共识说明》对齐；
#   - 提供 create_task(...) 工具函数，用于从请求载荷构建 Task；
#   - class 字段（股票/基金）统一从 symbol_index 表推断。
# ==============================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from backend.settings import DATA_TYPE_DEFINITIONS
from backend.db.symbols import select_symbol_index
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

_LOG = get_logger("task_model")


@dataclass
class Task:
    """
    Task：一次请求对应的主任务。

    字段语义与共识文档保持一致：
      - type    : 'current_kline' / 'symbol_index' / 'trade_calendar' / ...
      - scope   : 'symbol' / 'global' / ...
      - symbol  : 标的代码（scope='symbol' 时必填）
      - freq    : 频率，仅 current_kline 有意义
      - adjust  : 复权方式：'none'/'qfq'/'hfq'
      - cls     : 标的类别：'stock'/'fund'/None（从 symbol_index 推断）
      - params  : 任务专属参数（如 force_fetch/start_date/end_date 等）
      - metadata: 运行时元信息（如 priority/created_at/source 等）
    """

    task_id: str
    trace_id: Optional[str]

    type: str
    scope: str

    symbol: Optional[str] = None
    freq: Optional[str] = None
    adjust: str = "none"
    cls: Optional[str] = None

    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _infer_class_from_db(symbol: Optional[str]) -> Optional[str]:
    """
    从 symbol_index 表推断标的类别 class：'stock'/'fund'/None
    """
    s = (symbol or "").strip()
    if not s:
        return None

    try:
        rows = select_symbol_index(symbol=s)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception as e:
        _LOG.warning(
            "[Task] 推断标的 class 失败 symbol=%s error=%s",
            s,
            e,
        )
        return None


def _normalize_adjust(raw: Optional[str]) -> str:
    adj = (raw or "none").lower().strip()
    return adj if adj in ("none", "qfq", "hfq") else "none"


def _generate_task_id(
    task_type: str,
    scope: str,
    symbol: Optional[str],
    freq: Optional[str],
    adjust: str,
    source: str,
    trace_id: Optional[str],
) -> str:
    """
    生成可读性强的 task_id。

    格式示例：
      current_kline:symbol:510300:5m:qfq@20251212T071936(src=api/ensure-data,trace=REQ123)
      symbol_index:global:ALL@20251212T071936(src=startup,trace=NA)
    """
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    base_parts = [task_type, scope]

    if scope == "symbol" and symbol:
        base_parts.append(symbol)
    else:
        base_parts.append("ALL")

    if freq:
        base_parts.append(freq)
    if adjust != "none":
        base_parts.append(adjust)

    base = ":".join(base_parts)
    src = (source or "").split("/")[-1] or "unknown"
    tid = trace_id or "NA"

    return f"{base}@{ts}(src={src},trace={tid})"


def create_task(
    *,
    type: str,
    scope: str,
    symbol: Optional[str],
    freq: Optional[str],
    adjust: Optional[str],
    trace_id: Optional[str],
    params: Optional[Dict[str, Any]] = None,
    source: str = "",
    priority: Optional[int] = None,
) -> Task:
    """
    从上层传入的语义参数构建 Task 对象。

    参数：
      - type     : 任务类型，如 'current_kline'/'symbol_index'/'trade_calendar'...
      - scope    : 'symbol'/'global'/...
      - symbol   : 标的代码（scope='symbol' 时建议非空）
      - freq     : K 线频率（仅 current_kline 时使用）
      - adjust   : 复权方式；仅 current_kline 时使用
      - trace_id : 前端透传的 x-trace-id
      - params   : 任务参数（包含 force_fetch/start_date/end_date 等）
      - source   : 调用来源（如 'api/ensure-data'/'api/symbols/refresh'/'startup'）
      - priority : 可选优先级，若为空则从 DATA_TYPE_DEFINITIONS 中读取

    返回：
      - Task 实例（已填充 class/metadata 等）
    """
    t = (type or "").strip()
    sc = (scope or "").strip() or "symbol"
    sym = (symbol or "").strip() or None
    fq = (freq or "").strip() or None
    adj = _normalize_adjust(adjust)

    # 推断 class（仅 symbol 维度任务才有必要）
    cls = _infer_class_from_db(sym) if sc == "symbol" else None

    # 读取默认优先级（DATA_TYPE_DEFINITIONS）
    dt_def = DATA_TYPE_DEFINITIONS.get(t, {})
    default_prio = int(dt_def.get("priority", 100))
    prio = int(priority) if priority is not None else default_prio

    task_id = _generate_task_id(
        task_type=t,
        scope=sc,
        symbol=sym,
        freq=fq,
        adjust=adj,
        source=source,
        trace_id=trace_id,
    )

    md: Dict[str, Any] = {
        "priority": prio,
        "created_at": now_iso(),
        "source": source or "",
    }

    if params:
        # 拷贝一份以防上层修改
        p = dict(params)
    else:
        p = {}

    # 将 force_fetch 从顶层单独字段也塞进 params，统一入口
    if "force_fetch" not in p:
        # 默认为 False
        p["force_fetch"] = False

    task = Task(
        task_id=task_id,
        trace_id=trace_id,
        type=t,
        scope=sc,
        symbol=sym,
        freq=fq,
        adjust=adj,
        cls=cls,
        params=p,
        metadata=md,
    )

    _LOG.info(
        "[Task] 创建任务 type=%s scope=%s symbol=%s freq=%s adjust=%s class=%s priority=%s task_id=%s",
        t,
        sc,
        sym,
        fq,
        adj,
        cls,
        prio,
        task_id,
    )

    return task