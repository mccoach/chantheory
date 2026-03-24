# backend/services/local_import/scan.py
# ==============================
# 盘后数据导入 import - 本地文件递归扫描器
#
# 职责：
#   - 从 settings.tdx_vipdoc_dir 根目录递归扫描所有子目录
#   - 按扩展名过滤当前支持的文件类型
#   - 通过文件名解析 (market, symbol, freq)
#   - 生成标准扫描快照（唯一真相源原料）
#
# 设计原则：
#   - 扫描职责只归 scan 层
#   - 不由 candidates / orchestrator 各自重复扫描
#   - 扫描结果同时服务：
#       1) 候选展示
#       2) 执行阶段 file_path 索引
#
# 当前阶段：
#   - 只纳入 .day
#   - .day -> freq = 1d
# ==============================

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from backend.settings import settings
from backend.utils.logger import get_logger
from backend.utils.time import now_iso

_LOG = get_logger("local_import.scan")


@dataclass(frozen=True)
class LocalImportFileItem:
    market: str
    symbol: str
    freq: str
    ext: str
    file_path: str
    file_name: str
    file_datetime: Optional[str]


_SUPPORTED_EXT_TO_FREQ: Dict[str, str] = {
    ".day": "1d",
    # 未来扩展：
    # ".lc1": "1m",
    # ".lc5": "5m",
}


def _normalize_market_text(raw: str) -> Optional[str]:
    s = str(raw or "").strip().upper()
    if s in ("SH", "SZ", "BJ"):
        return s
    return None


def _parse_market_symbol_freq_from_file_name(file_name: str) -> Optional[Tuple[str, str, str, str]]:
    """
    从文件名解析 (market, symbol, freq, ext)。

    规则：
      - 文件名必须形如：
          sh600000.day
          sz000001.day
          bj920000.day
      - 市场和代码只从文件名解析，不依赖目录结构
    """
    name = str(file_name or "").strip()
    if not name or "." not in name:
        return None

    path_obj = Path(name)
    ext = str(path_obj.suffix or "").strip().lower()
    stem = str(path_obj.stem or "").strip()

    freq = _SUPPORTED_EXT_TO_FREQ.get(ext)
    if not freq:
        return None

    if len(stem) < 3:
        return None

    market_raw = stem[:2]
    symbol = stem[2:].strip()

    market = _normalize_market_text(market_raw)
    if not market:
        return None

    if not symbol or not symbol.isdigit():
        return None

    return market, symbol, freq, ext


def _format_file_mtime(path: Path) -> Optional[str]:
    """
    将文件最后修改时间格式化为：
      YYYY-MM-DD HH:mm:ss
    """
    try:
        ts = float(path.stat().st_mtime)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def scan_importable_files() -> List[LocalImportFileItem]:
    """
    递归扫描 tdx_vipdoc_dir 下当前支持导入的文件。
    """
    root = Path(settings.tdx_vipdoc_dir).resolve()
    if not root.exists():
        _LOG.warning("[LOCAL_IMPORT][SCAN] vipdoc root not found: %s", str(root))
        return []

    items: List[LocalImportFileItem] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        parsed = _parse_market_symbol_freq_from_file_name(path.name)
        if not parsed:
            continue

        market, symbol, freq, ext = parsed
        file_datetime = _format_file_mtime(path)

        items.append(LocalImportFileItem(
            market=market,
            symbol=symbol,
            freq=freq,
            ext=ext,
            file_path=str(path.resolve()),
            file_name=path.name,
            file_datetime=file_datetime,
        ))

    # 同一 (market, symbol, freq) 若扫描到多个文件，按绝对路径字典序稳定去重，保留最后一个
    dedup: Dict[Tuple[str, str, str], LocalImportFileItem] = {}
    for item in sorted(items, key=lambda x: (x.market, x.symbol, x.freq, x.file_path)):
        dedup[(item.market, item.symbol, item.freq)] = item

    out = list(dedup.values())
    out.sort(key=lambda x: (x.market, x.symbol, x.freq))

    _LOG.info(
        "[LOCAL_IMPORT][SCAN] scanned importable files=%s root=%s",
        len(out),
        str(root),
    )
    return out


def build_file_index(items: Optional[List[LocalImportFileItem]] = None) -> Dict[Tuple[str, str, str], str]:
    """
    构建执行期 file_path 索引：
      (market, symbol, freq) -> file_path
    """
    source = items if items is not None else scan_importable_files()

    index: Dict[Tuple[str, str, str], str] = {}
    for item in source:
        key = (item.market, item.symbol, item.freq)
        index[key] = item.file_path

    return index


def build_scan_snapshot() -> Dict[str, Any]:
    """
    构建标准扫描快照。

    返回结构：
      {
        "generated_at": "...",
        "items": [LocalImportFileItem, ...],
        "file_index": {(market, symbol, freq): file_path, ...}
      }
    """
    items = scan_importable_files()
    file_index = build_file_index(items)

    return {
        "generated_at": now_iso(),
        "items": items,
        "file_index": file_index,
    }
