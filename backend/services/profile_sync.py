# backend/services/profile_sync.py
# ==============================
# 说明：SSE / SZSE 档案聚合服务（单标的一次快照）
#
# 职责：
#   - 基于 symbol_index 中的 market/class/type 信息，选择对应交易所的 profile 接口；
#   - 从 SSE / SZSE 原子接口获取股本 / 市值 / 行业 / 地区 / PE 等字段；
#   - 按你提供的 JSON 规范做单位转换和两位小数保留；
#   - 仅返回 ready-to-write 的 dict，不做 DB 写入。
#
# 使用方式（由 UnifiedSyncExecutor 调用）：
#   >>> from backend.services import profile_sync
#   >>> snapshot = await profile_sync.fetch_profile_snapshot("600000")
#   >>> # 然后交给 async_writer / upsert_symbol_profile 落库
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import datetime

import pandas as pd

from backend.db.symbols import select_symbol_index
from backend.utils.logger import get_logger, log_event

# 直接使用原子化适配器（保持 HTTP/反爬逻辑都在 providers 层）
from backend.datasource.providers import sse_adapter
from backend.datasource.providers import szse_adapter

_LOG = get_logger("profile_sync")


# ==============================================================================
# 公共工具
# ==============================================================================

def _round2(x: Optional[float]) -> Optional[float]:
    """统一两位小数；None/NaN → None。"""
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    if pd.isna(v):
        return None
    return round(v, 2)


def _safe_float_from_str(x: Any, remove_comma: bool = True) -> Optional[float]:
    """字符串安全转 float，支持去千分位。失败返回 None。"""
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    if remove_comma:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _normalize_region_name(name: Optional[str]) -> Optional[str]:
    """
    简单归一化地区名称，主要用于沪市：
      - 去掉常见后缀：'省'、'市'、'自治区'、'壮族自治区'、'回族自治区'、'维吾尔自治区'、'特别行政区'
      - 例如：'内蒙古自治区' → '内蒙古'，'上海市' → '上海'
    """
    if not name:
        return None
    s = str(name).strip()
    # 特殊长后缀先处理
    long_suffixes = [
        "维吾尔自治区",
        "壮族自治区",
        "回族自治区",
        "特别行政区",
        "自治区",
    ]
    for suf in long_suffixes:
        if s.endswith(suf):
            return s[: -len(suf)]
    # 常见短后缀
    for suf in ["省", "市"]:
        if s.endswith(suf) and len(s) > 1:
            return s[:-1]
    return s


# ==============================================================================
# 主入口
# ==============================================================================

async def fetch_profile_snapshot(symbol: str) -> Optional[Dict[str, Any]]:
    """
    拉取单个标的的档案快照（根据 symbol_index 决定走 SSE / SZSE 哪条路径）。

    返回值：
      - dict，包含：
          symbol, total_shares, float_shares,
          total_value, nego_value, pe_static,
          industry, region, concepts=None, updated_at
      - None 表示获取失败或 symbol_index 中无该标的。
    """
    symbol = str(symbol or "").strip()
    if not symbol:
        return None

    # 1. 从 symbol_index 获取基础信息：market / class / type
    index_rows = select_symbol_index(symbol=symbol)
    if not index_rows:
        _LOG.warning(f"[profile] symbol_index 中不存在 {symbol}，跳过档案同步")
        return None

    idx = index_rows[0]
    market = (idx.get("market") or "").upper()
    sec_class = (idx.get("class") or "").lower()
    sec_type = (idx.get("type") or "").strip()

    # 统一快照骨架（全部字段键存在，默认 None）
    snapshot: Dict[str, Any] = {
        "symbol": symbol,
        "total_shares": None,
        "float_shares": None,
        "total_value": None,
        "nego_value": None,
        "pe_static": None,
        "industry": None,
        "region": None,
        "concepts": None,
    }

    log_event(
        logger=_LOG,
        service="profile_sync",
        level="INFO",
        file=__file__,
        func="fetch_profile_snapshot",
        line=0,
        trace_id=None,
        event="profile.sync.start",
        message=f"开始同步档案 {symbol}",
        extra={"symbol": symbol, "market": market, "class": sec_class, "type": sec_type},
    )

    # 2. 根据 market/class/type 选择路径
    try:
        if market == "SH" and sec_class == "stock":
            await _fill_sh_stock(snapshot)
        elif market == "SH" and sec_class == "fund":
            await _fill_sh_fund(snapshot)
        elif market == "SZ" and sec_class == "stock":
            await _fill_sz_stock(snapshot)
        elif market == "SZ" and sec_class == "fund":
            await _fill_sz_fund(snapshot)
        else:
            _LOG.warning(f"[profile] 未识别的组合 market={market}, class={sec_class}，跳过 {symbol}")
            return None

    except Exception as e:
        log_event(
            logger=_LOG,
            service="profile_sync",
            level="ERROR",
            file=__file__,
            func="fetch_profile_snapshot",
            line=0,
            trace_id=None,
            event="profile.sync.error",
            message=f"档案同步失败 {symbol}: {e}",
            extra={"symbol": symbol},
        )
        return None

    log_event(
        logger=_LOG,
        service="profile_sync",
        level="INFO",
        file=__file__,
        func="fetch_profile_snapshot",
        line=0,
        trace_id=None,
        event="profile.sync.done",
        message=f"档案同步完成 {symbol}",
        extra={"symbol": symbol, "snapshot": {k: v for k, v in snapshot.items() if k != "concepts"}},
    )

    return snapshot


# ==============================================================================
# 沪市股票：SSE basic + share + value
# ==============================================================================

async def _fill_sh_stock(snapshot: Dict[str, Any]) -> None:
    symbol = snapshot["symbol"]

    company_code = symbol
    sec_code = symbol

    # 0) 公司概况：行业 / 地区（来自 basic_sh_sse）
    df_basic = await sse_adapter.get_stock_profile_basic_sh_sse(company_code=company_code)
    if df_basic is not None and not df_basic.empty:
        row = df_basic.iloc[0]
        industry = row.get("CSRC_CODE_DESC")
        region_raw = row.get("AREA_NAME")  # 如 '上海市' / '内蒙古自治区'
        snapshot["industry"] = str(industry).strip() if industry not in (None, "") else None
        snapshot["region"] = _normalize_region_name(region_raw)

    # 1) 股本情况：share_sh_sse
    df_share = await sse_adapter.get_stock_profile_share_sh_sse(company_code=company_code)
    if df_share is not None and not df_share.empty:
        row = df_share.iloc[0]
        total = _safe_float_from_str(row.get("TOTAL_DOMESTIC_VOL"))  # 境内上市总股本（万股）
        free = _safe_float_from_str(row.get("A_UNLIMIT_VOL"))  # A股流通股本（万股）

        snapshot["total_shares"] = _round2(total)
        snapshot["float_shares"] = _round2(free)

    # 2) 市值 & PE：value_sh_sse（日度）
    df_val = await sse_adapter.get_stock_profile_value_sh_sse(sec_code=sec_code, date_type="D")
    if df_val is not None and not df_val.empty:
        row = df_val.iloc[0]

        total_val_wan = _safe_float_from_str(row.get("TOTAL_VALUE"))  # 万元
        nego_val_wan = _safe_float_from_str(row.get("NEGO_VALUE"))  # 万元
        pe = _safe_float_from_str(row.get("PE_RATE"), remove_comma=False)

        # 万元 → 亿元： / 1e4
        if total_val_wan is not None:
            snapshot["total_value"] = _round2(total_val_wan / 1e4)
        if nego_val_wan is not None:
            snapshot["nego_value"] = _round2(nego_val_wan / 1e4)

        snapshot["pe_static"] = _round2(pe)


# ==============================================================================
# 沪市基金：SSE fund_share + fund_value
# ==============================================================================

async def _fill_sh_fund(snapshot: Dict[str, Any]) -> None:
    symbol = snapshot["symbol"]

    # 1) 基金规模：share_sh_sse（万份）
    df_share = await sse_adapter.get_fund_profile_share_sh_sse(sec_code=symbol)
    if df_share is not None and not df_share.empty:
        row = df_share.iloc[0]
        tot_vol = _safe_float_from_str(row.get("TOT_VOL"))  # 万份
        snapshot["total_shares"] = _round2(tot_vol)

    # 2) 市值 & PE：value_sh_sse（日度）
    df_val = await sse_adapter.get_fund_profile_value_sh_sse(sec_code=symbol, date_type="D")
    if df_val is not None and not df_val.empty:
        row = df_val.iloc[0]

        total_val_wan = _safe_float_from_str(row.get("TOTAL_VALUE"))  # 万元
        nego_val_wan = _safe_float_from_str(row.get("NEGO_VALUE"))  # 万元
        pe_raw = row.get("PE_RATE")

        if total_val_wan is not None:
            snapshot["total_value"] = _round2(total_val_wan / 1e4)
        if nego_val_wan is not None:
            snapshot["nego_value"] = _round2(nego_val_wan / 1e4)

        # 基金 PE 多数为 "-"，需按规范转 NULL
        pe = _safe_float_from_str(pe_raw, remove_comma=False)
        snapshot["pe_static"] = _round2(pe)


# ==============================================================================
# 深市股票：SZSE basic + realtime
# ==============================================================================

async def _fill_sz_stock(snapshot: Dict[str, Any]) -> None:
    symbol = snapshot["symbol"]

    # 1) 基本信息：companyGeneralization（股本 / 行业 / 地区）
    df_basic = await szse_adapter.get_stock_profile_basic_sz_szse(sec_code=symbol)
    if df_basic is not None and not df_basic.empty:
        row = df_basic.iloc[0]

        # 总股本/流通股本：单位万股，带千分位
        total = _safe_float_from_str(row.get("agzgb"))
        free = _safe_float_from_str(row.get("agltgb"))
        # 行业 / 地区
        industry = row.get("sshymc")
        region = row.get("sheng")

        snapshot["total_shares"] = _round2(total)
        snapshot["float_shares"] = _round2(free)
        snapshot["industry"] = str(industry).strip() if industry not in (None, "") else None
        snapshot["region"] = str(region).strip() if region not in (None, "") else None

    # 2) 实时关键指标：stockKeyIndexGeneralization（总/流通市值、PE）
    df_rt = await szse_adapter.get_stock_profile_realtime_sz_szse(sec_code=symbol)
    if df_rt is not None and not df_rt.empty:
        # 第一行：now_* 指标
        row_now = df_rt.iloc[0]  # now_cjbs / now_cjje / now_syl / now_hsl / now_sjzz / now_ltsz / ...
        total_val = _safe_float_from_str(row_now.get("now_sjzz"))  # 亿元
        nego_val = _safe_float_from_str(row_now.get("now_ltsz"))  # 亿元
        pe = _safe_float_from_str(row_now.get("now_syl"), remove_comma=False)

        snapshot["total_value"] = _round2(total_val)
        snapshot["nego_value"] = _round2(nego_val)
        snapshot["pe_static"] = _round2(pe)


# ==============================================================================
# 深市基金：SZSE 列表 + 本地计算规模 / 市值（方案 A）
# ==============================================================================

async def _fill_sz_fund(snapshot: Dict[str, Any]) -> None:
    """
    深市基金档案（ETF 等场内基金）

    方案 A：在档案抓取时直接调用深交所基金列表接口，从单行记录中计算：
      - total_shares: 当前规模(份) / 1e4  （万份）
      - total_value : 当前规模(份) * 净值 / 1e8 （亿元，两位小数）

    说明：
      - 不额外拉取其他接口，直接使用列表里的“当前规模(份)”和“净值”字段；
      - 若净值缺失，则仅填 total_shares，total_value 保持 None；
      - float_shares / nego_value / pe_static / industry / region 仍按规范留空。
    """
    symbol = snapshot["symbol"]

    # 拉取深交所基金列表（XLSX，全量），然后按代码过滤单行
    df = await szse_adapter.get_fund_list_sz_szse()
    if df is None or df.empty:
        _LOG.warning(f"[profile] 深市基金 {symbol} 列表为空，无法计算规模/市值")
        return

    try:
        df_match = df[df["基金代码"].astype(str).str.strip() == symbol]
    except KeyError:
        _LOG.warning(
            f"[profile] 深市基金 {symbol} 列表中缺少 '基金代码' 列，当前列名={df.columns.tolist()}"
        )
        return

    if df_match.empty:
        _LOG.warning(f"[profile] 深市基金 {symbol} 未在列表中找到对应记录")
        return

    row = df_match.iloc[0]

    # 当前规模(份)
    current_amount = _safe_float_from_str(row.get("当前规模(份)"))
    # 注意：列名为“净值”，不是“基金净值”
    nav = _safe_float_from_str(row.get("净值"))

    # 先尽力填 total_shares：当前规模(份) / 1e4 → 万份
    if current_amount is not None:
        snapshot["total_shares"] = _round2(current_amount / 1e4)
    else:
        _LOG.warning(
            f"[profile] 深市基金 {symbol} 无法从列表中解析 当前规模(份)，"
            f"原始值={row.get('当前规模(份)')}"
        )

    # 若净值存在，再计算 total_value；否则保持 None
    if current_amount is not None and nav is not None:
        snapshot["total_value"] = _round2(current_amount * nav / 1e8)
    elif current_amount is not None and nav is None:
        _LOG.warning(
            f"[profile] 深市基金 {symbol} 列表中缺失净值，仅填总份额，"
            f"当前规模={row.get('当前规模(份)')}, 净值={row.get('净值')}"
        )
    else:
        # 两者都取不到就没法做任何事
        _LOG.warning(
            f"[profile] 深市基金 {symbol} 无法从列表中解析 当前规模/净值，"
            f"当前规模={row.get('当前规模(份)')}, 净值={row.get('净值')}"
        )