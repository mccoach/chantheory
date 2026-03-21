# backend/services/task_model.py
# ==============================
# 说明：Task 模型与构建工具（统一 Task 结构）
#
# 本轮改动：
#   - 支持固定语义最小请求体任务：
#       * symbol_index
#       * profile_snapshot
#   - current_profile 已废弃
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
