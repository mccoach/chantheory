# backend/services/local_import/candidates.py
# ==============================
# 盘后数据导入 import - 候选快照构建器
#
# 职责：
#   - 基于扫描结果 + symbol_index 双控筛选
#   - 生成面向前端的候选项列表
#
# 关键规则：
#   - 本地文件扫描结果才是候选范围真相源
#   - symbol_index 只是补充展示信息来源
#   - 必须同时满足：
#       1) 扫描到文件
#       2) symbol_index 中存在对应 (market, symbol)
#     才能出现在候选快照里
#
# 输出字段严格对齐 ImportCandidateItem：
#   - market
#   - symbol
#   - freq
#   - name
#   - class
#   - type
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

from backend.services.local_import.scan import scan_importable_files
from backend.utils.common import get_symbol_record_from_db
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.candidates")


def build_import_candidates_snapshot() -> Dict[str, Any]:
    """
    构建候选快照。

    Returns:
        {
          "ok": True,
          "items": [...],
          "generated_at": "...",
          "ui_message": ...
        }
    """
    scanned = scan_importable_files()

    items: List[Dict[str, Any]] = []
    for item in scanned:
        meta = get_symbol_record_from_db(symbol=item.symbol, market=item.market)
        if not meta:
            # 双控筛选：没有 symbol_index 展示信息的残缺项不返回给前端
            continue

        name = str(meta.get("name") or "").strip()
        if not name:
            # 候选列表必须只保留完整可识别标的信息
            continue

        items.append({
            "market": item.market,
            "symbol": item.symbol,
            "freq": item.freq,
            "name": name,
            "class": meta.get("class"),
            "type": meta.get("type"),
        })

    items.sort(key=lambda x: (str(x.get("market")), str(x.get("symbol")), str(x.get("freq"))))

    ui_message = None
    if not scanned:
        ui_message = "未扫描到可导入的本地盘后数据文件"
    elif not items:
        ui_message = "已扫描到本地文件，但没有可用于展示导入的有效标的信息"

    _LOG.info(
        "[LOCAL_IMPORT][CANDIDATES] scanned=%s visible=%s",
        len(scanned),
        len(items),
    )

    return {
        "ok": True,
        "items": items,
        "generated_at": now_iso(),
        "ui_message": ui_message,
    }
