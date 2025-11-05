# backend/services/normalizer.py
# ==============================
# 说明：数据标准化器（V5.0 - NaN安全处理版）
# 核心改造：
#   1. 所有 pandas.apply 使用 pd.notna() 判断NaN
#   2. 时间处理直接使用 time.py 标准函数
#   3. 字段识别失败时打印详细日志
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Dict, Any

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
    
    # 步骤1：基础预处理
    df = normalize_dataframe(raw_df)
    
    if df is None or df.empty:
        return None
    
    # 步骤2：字段识别与映射
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
    
    # 步骤3：识别K线类型
    has_date = 'date' in df.columns
    has_time = 'time' in df.columns
    time_col = 'time' if has_time else 'date' if has_date else None
    
    if not time_col:
        _LOG.error(f"[标准化] 未找到时间列，source={source_id}, columns={df.columns.tolist()}")
        return None
    
    required = ['open', 'high', 'low', 'close']
    if not all(c in df.columns for c in required):
        _LOG.error(f"[标准化] 缺少必需字段，source={source_id}, columns={df.columns.tolist()}")
        return None
    
    # 步骤4：时间戳生成
    is_minutely = has_time
    
    if is_minutely:
        df['ts'] = df[time_col].apply(_safe_parse_datetime)
    else:
        df['ts'] = df[time_col].apply(_safe_parse_date_to_close)
    
    df = df.drop(columns=[time_col], errors='ignore')
    
    # 步骤5：单位转换
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
    
    # 步骤6：输出标准格式
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
# 复权因子标准化
# ==============================================================================

def normalize_adj_factors_df(raw_df: pd.DataFrame, source_id: str) -> Optional[pd.DataFrame]:
    """标准化复权因子"""
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    
    if df is None or df.empty:
        return None
    
    date_col = None
    for col in ['date', '日期']:
        if col in df.columns:
            date_col = col
            break
    
    if not date_col:
        _LOG.error(f"[因子标准化] 未找到日期列，columns={df.columns.tolist()}")
        return None
    
    factor_col = None
    for col in ['qfq_factor', 'hfq_factor', 'factor']:
        if col in df.columns:
            factor_col = col
            break
    
    if not factor_col:
        _LOG.error(f"[因子标准化] 未找到因子列，columns={df.columns.tolist()}")
        return None
    
    df['date'] = df[date_col].apply(
        lambda v: parse_yyyymmdd(str(v)) if pd.notna(v) else None
    )
    df = df.dropna(subset=['date'])
    df['date'] = df['date'].astype(int)
    
    df['factor'] = pd.to_numeric(df[factor_col], errors='coerce')
    df = df.dropna(subset=['factor'])
    
    df = df[['date', 'factor']].drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    
    return df

# ==============================================================================
# 标的列表标准化
# ==============================================================================

def normalize_symbol_list_df(raw_df: pd.DataFrame, category: str) -> Optional[pd.DataFrame]:
    """标准化标的列表"""
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    
    if df is None or df.empty:
        return None
    
    code_col = None
    for col in ['code', '代码', 'symbol', '证券代码', 'A股代码', '基金代码']:
        if col in df.columns:
            code_col = col
            break
    
    if not code_col:
        _LOG.error(f"[列表标准化] 未找到代码列，columns={df.columns.tolist()}")
        return None
    
    name_col = None
    for col in ['name', '名称', '证券简称', 'A股简称', '基金名称']:
        if col in df.columns:
            name_col = col
            break
    
    if not name_col:
        _LOG.error(f"[列表标准化] 未找到名称列，columns={df.columns.tolist()}")
        return None
    
    result = pd.DataFrame()
    result['symbol'] = df[code_col].astype(str).str.strip()
    result['name'] = df[name_col].astype(str).str.strip()
    
    if '_market_source' in df.columns:
        result['market'] = df['_market_source']
    else:
        def infer_market(code: str) -> str:
            code = str(code).strip()
            if code.startswith('6'):
                return 'SH'
            elif code.startswith(('0', '3')):
                return 'SZ'
            elif code.startswith(('4', '8', '9')):
                return 'BJ'
            else:
                return 'SH'
        
        result['market'] = result['symbol'].apply(infer_market)
    
    result['type'] = category
    
    # ===== 关键修复：NaN安全处理 =====
    listing_date_col = None
    for col in ['上市日期', 'A股上市日期', 'listing_date']:
        if col in df.columns:
            listing_date_col = col
            break
    
    if listing_date_col:
        result['listing_date'] = df[listing_date_col].apply(
            lambda v: parse_yyyymmdd(str(v)) if pd.notna(v) else None
        )
    else:
        result['listing_date'] = None
    
    result['total_shares'] = None
    result['float_shares'] = None
    result['industry'] = None
    
    result = result.drop_duplicates(subset=['symbol']).reset_index(drop=True)
    
    return result

# ==============================================================================
# 交易日历标准化
# ==============================================================================

def normalize_trade_calendar_df(raw_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """标准化交易日历"""
    if raw_df is None or raw_df.empty:
        return None
    
    df = normalize_dataframe(raw_df)
    
    if df is None or df.empty:
        return None
    
    date_col = None
    for col in ['trade_date', 'date', '日期', 'day']:
        if col in df.columns:
            date_col = col
            break
    
    if not date_col:
        _LOG.error(f"[日历标准化] 未找到日期列，columns={df.columns.tolist()}")
        return None
    
    df['date'] = df[date_col].apply(
        lambda v: parse_yyyymmdd(str(v)) if pd.notna(v) else None
    )
    df = df.dropna(subset=['date'])
    df['date'] = df['date'].astype(int)
    
    return df[['date']].drop_duplicates().sort_values('date').reset_index(drop=True)

# ==============================================================================
# 档案标准化
# ==============================================================================

def normalize_stock_profile_df(raw_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """标准化个股档案"""
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
    
    profile_dict = {}
    
    for _, row in df.iterrows():
        item = str(row[item_col]).strip()
        value = row[value_col]
        
        if item in ['上市时间', '上市日期', 'listing_date']:
            try:
                if pd.notna(value):
                    profile_dict['listing_date'] = parse_yyyymmdd(str(value))
            except Exception:
                pass
        
        elif item in ['总股本', 'total_shares']:
            try:
                if pd.notna(value):
                    profile_dict['total_shares'] = float(value)
            except Exception:
                pass
        
        elif item in ['流通股', '流通股本', 'float_shares']:
            try:
                if pd.notna(value):
                    profile_dict['float_shares'] = float(value)
            except Exception:
                pass
        
        elif item in ['行业', 'industry', '所属行业']:
            if pd.notna(value):
                profile_dict['industry'] = str(value)
        
        elif item in ['地区', 'region']:
            if pd.notna(value):
                profile_dict['region'] = str(value)
    
    return profile_dict if profile_dict else None