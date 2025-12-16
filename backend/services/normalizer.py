# backend/services/normalizer.py
# ==============================
# 说明：数据标准化器（V7.2 - 标的列表日期容错版）
#
# 核心职责：
#   - K线标准化（bars）
#   - 复权因子标准化（adj_factors）
#   - 标的列表标准化（symbol_index 所需字段）
#   - 交易日历标准化（trade_calendar）
#   - 档案基础信息标准化（profile 基础字段）
#
# 本次改动：
#   - normalize_symbol_list_df 中 listing_date 的解析改为“宽松容错”：
#       * 空字符串 / '-' / '--' 等视为 None；
#       * 解析失败记录 warning，不再抛异常，避免整批沪市基金同步失败。
#   - normalize_trade_calendar_df 支持 Baostock 返回结构：
#       * 识别 'calendar_date' 作为日期列；
#       * 若存在 'is_trading_day' 列，则在此处过滤 == 1，仅保留交易日。
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Dict, Any, Tuple

from backend.utils.logger import get_logger
from backend.utils.dataframe import normalize_dataframe
from backend.utils.time import (
    parse_yyyymmdd,
    ms_at_market_close,
    ms_from_datetime_string,
    now_ms,
)

_LOG = get_logger("normalizer")

# ==============================================================================
# 代码前缀处理辅助函数（仅在少数场景兜底用；市场主判定依赖 source_tag）
# ==============================================================================

def _extract_market_and_clean_symbol(raw_symbol: str) -> Tuple[str, str]:
    """
    从代码中提取市场信息并去除前缀（兜底用）。
    
    说明：
      - 新架构中，market 的主判定应来自接口源头（SSE/SZSE），
        本函数仅在极端场景下用于容错或日志诊断，而不作为主逻辑。
    """
    code = str(raw_symbol or "").strip()
    if not code:
        return "", ""

    prefix_map = {
        "sh": "SH",
        "SH": "SH",
        "sz": "SZ",
        "SZ": "SZ",
        "bj": "BJ",
        "BJ": "BJ",
    }
    for prefix, market in prefix_map.items():
        if code.lower().startswith(prefix.lower()):
            clean = code[len(prefix):]
            return clean, market

    first_char = code[0] if code else ""
    if first_char == "6":
        return code, "SH"
    if first_char in ("0", "3"):
        return code, "SZ"
    if first_char in ("4", "8", "9"):
        return code, "BJ"
    return code, "SH"

# ==============================================================================
# K线数据标准化
# ==============================================================================

def normalize_bars_df(raw_df: pd.DataFrame, source_id: str) -> Optional[pd.DataFrame]:
    """
    标准化K线数据（完全自包含版）
    
    时间戳规范：
      - 所有K线的 ts 统一表示"收盘时刻"
      - 分钟K线：保持原始时间（如 14:35）
      - 日K线：统一为 15:00
    """
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None
    
    field_map = {
        # 时间列
        '日期': 'date', 'date': 'date',
        '时间': 'time', 'day': 'time', 'datetime': 'time',
        # OHLC
        '开盘': 'open', 'open': 'open',
        '收盘': 'close', 'close': 'close',
        '最高': 'high', 'high': 'high',
        '最低': 'low', 'low': 'low',
        # 成交量额
        '成交量': 'volume', 'volume': 'volume',
        '成交额': 'amount', 'amount': 'amount',
        # 换手率
        '换手率': 'turnover_rate',
        '换手': 'turnover_rate',
        'turnover': 'turnover_rate',
        'turnover_rate': 'turnover_rate',
    }
    rename_map = {col: field_map[col] for col in df.columns if col in field_map}
    df = df.rename(columns=rename_map)
    
    has_date = 'date' in df.columns
    has_time = 'time' in df.columns
    time_col = 'time' if has_time else ('date' if has_date else None)
    
    if not time_col:
        _LOG.error(f"[标准化] 未找到时间列，source={source_id}, columns={df.columns.tolist()}")
        return None
    
    required = ['open', 'high', 'low', 'close']
    if not all(c in df.columns for c in required):
        _LOG.error(f"[标准化] 缺少必需字段，source={source_id}, columns={df.columns.tolist()}")
        return None
    
    is_minutely = has_time
    if is_minutely:
        df['ts'] = df[time_col].apply(_safe_parse_datetime)
    else:
        df['ts'] = df[time_col].apply(_safe_parse_date_to_close)
    df = df.drop(columns=[time_col], errors='ignore')
    
    if 'volume' in df.columns:
        if '_em' in source_id or '_tx' in source_id:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce') * 100
        else:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    else:
        df['volume'] = 0.0
    
    if 'amount' in df.columns:
        if '_tx' in source_id:
            df['volume'] = pd.to_numeric(df['amount'], errors='coerce') * 100
            df['amount'] = None
        else:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    else:
        df['amount'] = None
    
    if 'turnover_rate' in df.columns:
        df['turnover_rate'] = pd.to_numeric(df['turnover_rate'], errors='coerce') / 100.0
    else:
        df['turnover_rate'] = None
    
    output_cols = ['ts', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate']
    for col in output_cols:
        if col not in df.columns:
            df[col] = None
    
    df = df[output_cols].copy()
    df = df.drop_duplicates(subset=['ts']).sort_values('ts').reset_index(drop=True)
    return df

def _safe_parse_datetime(value: Any) -> int:
    """安全解析datetime字符串 → 毫秒时间戳（分钟K线用）"""
    try:
        return ms_from_datetime_string(str(value))
    except Exception as e:
        _LOG.warning(f"[时间戳解析] datetime解析失败: {value}, error={e}")
        return now_ms()

def _safe_parse_date_to_close(value: Any) -> int:
    """安全解析日期 → 收盘时刻（日K线用）"""
    try:
        ymd = parse_yyyymmdd(str(value))
        return ms_at_market_close(ymd)
    except Exception as e:
        _LOG.error(f"[时间戳解析] 日期解析失败: {value}, error={e}")
        return now_ms()

# ==============================================================================
# Baostock 复权因子标准化（一次性前/后复权）
# ==============================================================================

def normalize_baostock_adj_factors_df(
    raw_df: pd.DataFrame,
    source_id: str = "baostock.get_raw_adj_factors_bs",
) -> Optional[pd.DataFrame]:
    """
    标准化 Baostock 的复权因子数据（一次性前/后复权）。

    输入（来自 baostock_adapter.get_raw_adj_factors_bs）：
      - 列至少包含：
          'code',
          'dividOperateDate',   # 'YYYY-MM-DD'
          'foreAdjustFactor',   # 前复权因子
          'backAdjustFactor',   # 后复权因子

    输出：
      - DataFrame，列：
          'date'       : int YYYYMMDD
          'qfq_factor' : float
          'hfq_factor' : float
      - 若输入为空或结构异常，则返回 None。
    """
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None

    required_cols = ["dividOperateDate", "foreAdjustFactor", "backAdjustFactor"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _LOG.error(
            "[因子标准化-Baostock] 缺少必要列: %s, source_id=%s, columns=%s",
            missing,
            source_id,
            list(df.columns),
        )
        return None

    # 1. 解析日期
    df["date"] = df["dividOperateDate"].apply(
        lambda v: parse_yyyymmdd(str(v).strip()) if pd.notna(v) else None
    )
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].astype(int)

    # 2. 数值化前/后复权因子
    df["qfq_factor"] = pd.to_numeric(
        df["foreAdjustFactor"], errors="coerce"
    )
    df["hfq_factor"] = pd.to_numeric(
        df["backAdjustFactor"], errors="coerce"
    )

    # 丢弃完全无效的行
    df = df.dropna(subset=["qfq_factor", "hfq_factor"], how="all")

    if df.empty:
        return None

    out = df[["date", "qfq_factor", "hfq_factor"]].drop_duplicates(
        subset=["date"]
    ).sort_values("date").reset_index(drop=True)

    _LOG.info(
        "[因子标准化-Baostock] 标准化完成: source_id=%s, rows=%d",
        source_id,
        len(out),
    )

    return out

# ==============================================================================
# 标的列表标准化（新语义版，listing_date 宽松解析）
# ==============================================================================

def normalize_symbol_list_df(raw_df: pd.DataFrame, source_tag: str) -> Optional[pd.DataFrame]:
    """
    标的列表标准化（新语义版）

    设计目标：
      1. 明确从“方法源 + 市场 + 股票/基金”推导出 class/type/board/market/listing_date；
      2. 不再依赖模糊的 category 概念，不再兼容旧逻辑；
      3. 所有语义字段（class/type/board/market）只在此处定义，不在 DB 层做二次推断。

    输入：
      - raw_df: 原始 DataFrame（来自 SSE/SZSE 的 listing 接口）
      - source_tag: 字符串，标识调用源，建议值：
          * 'sse_sh_stock' : 上交所股票列表
          * 'sse_sh_fund'  : 上交所基金列表
          * 'szse_sz_stock': 深交所股票列表
          * 'szse_sz_fund' : 深交所基金列表
        （后续在 symbol_sync 中会按此约定调用）

    输出 DataFrame 字段：
      - symbol        (str): 代码（不带前缀）
      - name          (str): 名称（股票简称 / 基金扩展简称）
      - market        (str): 'SH' / 'SZ'
      - class         (str): 'stock' / 'fund'
      - type          (str): 标的类别（A/B/科创/ETF/LOF/实时申赎货币/基础设施公募REITs/...）
      - board         (str): 股票板块 '主板'/'科创板'/'创业板'，基金为 None
      - listing_date  (int|None): 上市日期 YYYYMMDD
    """
    if raw_df is None or raw_df.empty:
        _LOG.error(f"[列表标准化] 输入为空，source_tag={source_tag}")
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        _LOG.error(f"[列表标准化] 预处理后为空，source_tag={source_tag}")
        return None

    _LOG.info(
        f"[列表标准化] source_tag={source_tag}, "
        f"输入行数={len(df)}, 列名={df.columns.tolist()}"
    )

    source_tag = str(source_tag or "").strip()

    # === 不同源的字段映射 ===
    # 1) 上交所股票列表
    if source_tag == "sse_sh_stock":
        code_col = "COMPANY_CODE"
        name_col = "COMPANY_ABBR"
        listing_col = "LIST_DATE"
        market = "SH"
        sec_class = "stock"

        # STOCK_TYPE: 1=主板A股, 2=B股, 8=科创板
        def map_type(row: pd.Series) -> Optional[str]:
            st = str(row.get("STOCK_TYPE") or "").strip()
            if st == "1":
                return "A"
            if st == "2":
                return "B"
            if st == "8":
                # return "科创"
                return "A"
            return None

        # LIST_BOARD: 1=主板, 2=科创板
        def map_board(row: pd.Series) -> Optional[str]:
            lb = str(row.get("LIST_BOARD") or "").strip()
            if lb == "1":
                return "主板"
            if lb == "2":
                return "科创板"
            return None

    # 2) 上交所基金列表
    elif source_tag == "sse_sh_fund":
        code_col = "FUND_CODE"
        name_col = "FUND_EXPANSION_ABBR"
        listing_col = "LISTING_DATE"
        market = "SH"
        sec_class = "fund"

        # CATEGORY: 按前缀大类映射
        def map_type(row: pd.Series) -> Optional[str]:
            cat = str(row.get("CATEGORY") or "").strip().upper()
            if cat.startswith("F1"):
                return "ETF"
            if cat.startswith("F2"):
                return "LOF"
            if cat.startswith("F4"):
                return "实时申赎货币"
            if cat.startswith("F6"):
                return "基础设施公募REITs"
            return None  # 其他类别暂不细分，保留扩展空间

        def map_board(row: pd.Series) -> Optional[str]:
            return None

    # 3) 深交所股票列表
    elif source_tag == "szse_sz_stock":
        code_col = "A股代码"
        name_col = "A股简称"
        listing_col = "A股上市日期"
        market = "SZ"
        sec_class = "stock"

        def map_type(row: pd.Series) -> Optional[str]:
            # 深交所接口为“A股列表”，本次规范中全部视作 A 股
            return "A"

        def map_board(row: pd.Series) -> Optional[str]:
            # '板块'：'主板' / '创业板'
            val = str(row.get("板块") or "").strip()
            if val in ("主板", "创业板"):
                return val
            return None

    # 4) 深交所基金列表
    elif source_tag == "szse_sz_fund":
        code_col = "基金代码"
        name_col = "基金简称"
        listing_col = "上市日期"
        market = "SZ"
        sec_class = "fund"

        def map_type(row: pd.Series) -> Optional[str]:
            # 直接采用“基金类别”原始字段作为 type
            val = str(row.get("基金类别") or "").strip()
            return val or None

        def map_board(row: pd.Series) -> Optional[str]:
            return None

    else:
        _LOG.error(f"[列表标准化] 未知 source_tag={source_tag}")
        return None

    # 必要列检查
    for col in (code_col, name_col):
        if col not in df.columns:
            _LOG.error(
                f"[列表标准化] 缺少必要列: {col}, source_tag={source_tag}, columns={df.columns.tolist()}"
            )
            return None

    result = pd.DataFrame()
    result["symbol"] = df[code_col].astype(str).str.strip()
    result["name"] = df[name_col].astype(str).str.strip()
    result["market"] = market
    result["class"] = sec_class

    # type / board 映射
    result["type"] = df.apply(map_type, axis=1)
    result["board"] = df.apply(map_board, axis=1)

    # B 股支持逻辑：当前规范暂不纳入 B 股，但在此仍实现识别规则，方便未来扩展。
    # 调用方若不希望纳入 B 股，可在上游根据 type=='B' 过滤掉相关记录。

    # listing_date 标准化为 YYYYMMDD 整数
    if listing_col in df.columns:
        def _safe_parse_listing(v: Any) -> Optional[int]:
            s = str(v).strip()
            if not s or s in ("-", "--", "—", "None", "nan"):
                return None
            try:
                return parse_yyyymmdd(s)
            except Exception as e:
                _LOG.warning(
                    f"[列表标准化] listing_date 解析失败: raw={v}, source_tag={source_tag}, error={e}"
                )
                return None

        result["listing_date"] = df[listing_col].apply(_safe_parse_listing)
    else:
        result["listing_date"] = None

    # 清洗空 symbol
    result = result[result["symbol"].str.len() > 0]

    # 去重（按 symbol 去重，保留最后一条）
    result = result.drop_duplicates(subset=["symbol"], keep="last").reset_index(drop=True)

    _LOG.info(
        f"[列表标准化] source_tag={source_tag} 输出行数={len(result)}, "
        f"示例={result.head(3).to_dict('records')}"
    )

    return result

# ==============================================================================
# 交易日历标准化（支持 Baostock & 其他来源）
# ==============================================================================

def normalize_trade_calendar_df(raw_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    标准化交易日历

    支持的输入格式：
      - 列名中包含以下任意一个日期列：
          'trade_date', 'calendar_date', 'date', '日期', 'day'
      - 可选列：
          'is_trading_day'：若存在，则在此处过滤 == 1，仅保留交易日；
                            若不存在，则假定输入已为纯交易日列表。

    输出：
      - 列：['date']，YYYYMMDD 整型，去重升序。
    """
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None
    
    date_col = None
    # 扩展支持 Baostock 的 'calendar_date'
    for col in ['trade_date', 'calendar_date', 'date', '日期', 'day']:
        if col in df.columns:
            date_col = col
            break
    
    if not date_col:
        _LOG.error(f"[日历标准化] 未找到日期列，columns={df.columns.tolist()}")
        return None

    # 若存在 is_trading_day 列，则在此处过滤，仅保留交易日
    if 'is_trading_day' in df.columns:
        try:
            df['is_trading_day'] = pd.to_numeric(df['is_trading_day'], errors='coerce')
            before_rows = len(df)
            df = df[df['is_trading_day'] == 1].reset_index(drop=True)
            _LOG.info(
                "[日历标准化] 按 is_trading_day 过滤：%d → %d 行",
                before_rows,
                len(df),
            )
        except Exception as e:
            _LOG.warning(
                "[日历标准化] is_trading_day 过滤失败，保留全部数据: error=%s", e
            )

    df['date'] = df[date_col].apply(
        lambda v: parse_yyyymmdd(str(v)) if pd.notna(v) else None
    )
    df = df.dropna(subset=['date'])
    df['date'] = df['date'].astype(int)
    
    return df[['date']].drop_duplicates().sort_values('date').reset_index(drop=True)

# ==============================================================================
# 档案基础信息标准化（EM 源，仅保留非数值字段；数值型市值/股本由 SSE/SZSE 专用管线负责）
# ==============================================================================

def normalize_stock_profile_df(raw_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    标准化个股/基金档案（单标的 · EM 源基础版）

    当前用途：
      - 仅用于获取部分基础信息（如总股本/流通股本/行业/地区等）时的兜底解析；
      - 数值型市值、估值类字段（total_value/nego_value/pe_static）将由
        SSE/SZSE 专用 profile 管线提供，不在此处从 EM 源推断。

    返回字段：
      - total_shares: 可用时尝试解析总股本（具体单位由上层决定）
      - float_shares: 同上，流通股本
      - industry: 行业名称
      - region: 地区
      - total_value/nego_value/pe_static/concepts: 预留键，默认 None
    """
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None
    
    item_col = None
    value_col = None
    
    for col in ['item', 'Item', '项目']:
        if col in df.columns:
            item_col = col
            break
    for col in ['value', 'Value', '值']:
        if col in df.columns:
            value_col = col
            break
    if not item_col or not value_col:
        _LOG.error(f"[档案标准化] 未找到item/value列，columns={df.columns.tolist()}")
        return None
    
    profile: Dict[str, Any] = {
        "total_shares": None,
        "float_shares": None,
        "total_value": None,
        "nego_value": None,
        "pe_static": None,
        "industry": None,
        "region": None,
        "concepts": None,
    }
    
    for _, row in df.iterrows():
        item = str(row[item_col]).strip()
        value = row[value_col]
        
        if item in ['总股本', 'total_shares']:
            try:
                if pd.notna(value):
                    profile["total_shares"] = float(value)
            except Exception:
                pass
        elif item in ['流通股', '流通股本', 'float_shares']:
            try:
                if pd.notna(value):
                    profile["float_shares"] = float(value)
            except Exception:
                pass
        elif item in ['行业', 'industry', '所属行业']:
            if pd.notna(value):
                profile["industry"] = str(value)
        elif item in ['地区', 'region']:
            if pd.notna(value):
                profile["region"] = str(value)

    has_any = any(
        v is not None for k, v in profile.items()
        if k not in ("concepts", "total_value", "nego_value", "pe_static")
    )
    return profile if has_any else None