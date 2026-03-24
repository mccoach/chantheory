# backend/services/local_import/candidates.py
# ==============================
# 盘后数据导入 import - 候选快照构建器
#
# 职责：
#   - 消费 runtime 中的扫描快照
#   - 基于扫描结果 + symbol_index 双控筛选
#   - 生成面向前端的候选项列表
#
# 关键规则：
#   - 扫描快照是文件发现真相源
#   - candidates 只消费快照，不自己管理运行时执行逻辑
#   - 必须同时满足：
#       1) 扫描快照中存在文件
#       2) symbol_index 中存在对应 (market, symbol)
#     才能出现在候选快照里
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

from backend.services.local_import.runtime import get_local_import_runtime
from backend.utils.common import get_symbol_record_from_db
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.candidates")


def build_import_candidates_snapshot() -> Dict[str, Any]:
    """
    构建候选快照。

    这里不直接扫描目录，而是统一通过 runtime 获取/刷新扫描快照。
    这样：
      - 打开弹窗时完成唯一一次扫描
      - start / retry / pipeline 可在 TTL 内复用
    """
    runtime = get_local_import_runtime()
    snapshot = runtime.get_or_refresh_scan_snapshot()
    scanned = snapshot.get("items") or []

    items: List[Dict[str, Any]] = []
    for item in scanned:
        meta = get_symbol_record_from_db(symbol=item.symbol, market=item.market)
        if not meta:
            continue

        name = str(meta.get("name") or "").strip()
        if not name:
            continue

        items.append({
            "market": item.market,
            "symbol": item.symbol,
            "freq": item.freq,
            "name": name,
            "class": meta.get("class"),
            "type": meta.get("type"),
            "file_datetime": item.file_datetime,
        })

    items.sort(key=lambda x: (str(x.get("market")), str(x.get("symbol")), str(x.get("freq"))))

    ui_message = None
    if not scanned:
        ui_message = "未扫描到可导入的本地盘后数据文件"
    elif not items:
        ui_message = "已扫描到本地文件，但没有可用于展示导入的有效标的信息"

    _LOG.info(
        "[LOCAL_IMPORT][CANDIDATES] scanned=%s visible=%s snapshot_generated_at=%s",
        len(scanned),
        len(items),
        runtime.get_snapshot_generated_at(),
    )

    return {
        "ok": True,
        "items": items,
        "generated_at": now_iso(),
        "ui_message": ui_message,
    }
