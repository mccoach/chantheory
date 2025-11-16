# backend/services/normalizer.py
# ==============================
# 说明：数据标准化器（V7.0 - 修复索引对应问题）
# 核心改造：
#   1. 新增 _extract_market_and_clean_symbol：统一处理代码前缀
#   2. normalize_symbol_list_df：修复索引对应问题（根因性重构）
#   3. 其他函数保持不变（V5.0 NaN安全处理版）
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
# 代码前缀处理辅助函数
# ==============================================================================

def _extract_market_and_clean_symbol(raw_symbol: str) -> Tuple[str, str]:
    """
    从代码中提取市场信息并去除前缀
    
    规则：
      - sh/SH开头 → 市场=SH，去除前缀
      - sz/SZ开头 → 市场=SZ，去除前缀
      - bj/BJ开头 → 市场=BJ，去除前缀
      - 6开头（无前缀） → 市场=SH，保持原样
      - 0/3开头（无前缀） → 市场=SZ，保持原样
      - 4/8/9开头（无前缀） → 市场=BJ，保持原样
      - 其他 → 市场=SH，保持原样
    
    Args:
        raw_symbol: 原始代码（可能带前缀）
    
    Returns:
        (clean_symbol, market): (清洁代码, 市场代码)
    
    Examples:
        >>> _extract_market_and_clean_symbol('sh513000')
        ('513000', 'SH')
        >>> _extract_market_and_clean_symbol('sz159998')
        ('159998', 'SZ')
        >>> _extract_market_and_clean_symbol('000001')
        ('000001', 'SZ')
        >>> _extract_market_and_clean_symbol('600519')
        ('600519', 'SH')
    """
    code = str(raw_symbol or "").strip()
    
    if not code:
        return "", ""
    
    # 规则1：处理显式前缀
    prefix_map = {
        'sh': 'SH',
        'SH': 'SH',
        'sz': 'SZ',
        'SZ': 'SZ',
        'bj': 'BJ',
        'BJ': 'BJ',
    }
    
    for prefix, market in prefix_map.items():
        if code.lower().startswith(prefix.lower()):
            clean = code[len(prefix):]
            return clean, market
    
    # 规则2：无前缀时按首位数字推断
    first_char = code[0] if code else ''
    
    if first_char == '6':
        return code, 'SH'
    elif first_char in ('0', '3'):
        return code, 'SZ'
    elif first_char in ('4', '8', '9'):
        return code, 'BJ'
    else:
        # 默认上交所
        return code, 'SH'

# ==============================================================================
# K线数据标准化（保持V5.0版本不变）
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
# 复权因子标准化（保持V5.0版本不变）
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
# 标的列表标准化（V7.0 - 修复索引对应问题）
# ==============================================================================

def normalize_symbol_list_df(raw_df: pd.DataFrame, category: str) -> Optional[pd.DataFrame]:
    """
    标准化标的列表（前缀规范化版）
    
    核心改造：
      1. 提取代码中的市场前缀（sh/sz/bj）
      2. 去除前缀，统一存储为纯数字代码
      3. 市场信息提取到独立字段
      4. 修复索引对应问题（根因性重构）
    
    输入：
      - raw_df: 原始数据（代码可能带前缀）
      - category: 标的类型（'A', 'ETF', 'LOF'）
    
    输出：
      - symbol: 不带前缀的纯数字代码（如 '513000'）
      - market: 市场代码（'SH', 'SZ', 'BJ'）
      - type: 标的类型（与category对应）
    """
    
    if raw_df is None or raw_df.empty:
        _LOG.error(f"[列表标准化] 输入为空，category={category}")
        return None
    
    df = normalize_dataframe(raw_df)
    
    if df is None or df.empty:
        _LOG.error(f"[列表标准化] 预处理后为空，category={category}")
        return None
    
    # 诊断：打印输入信息
    _LOG.info(f"[列表标准化] category={category}, 输入行数={len(df)}, 列名={df.columns.tolist()}")
    
    # 查找代码列
    code_col = None
    for col in ['code', '代码', 'symbol', '证券代码', 'A股代码', '基金代码']:
        if col in df.columns:
            code_col = col
            _LOG.info(f"[列表标准化] 找到代码列: {code_col}")
            break
    
    if not code_col:
        _LOG.error(f"[列表标准化] 未找到代码列，columns={df.columns.tolist()}")
        return None
    
    # 查找名称列
    name_col = None
    for col in ['name', '名称', '证券简称', 'A股简称', '基金名称']:
        if col in df.columns:
            name_col = col
            _LOG.info(f"[列表标准化] 找到名称列: {name_col}")
            break
    
    if not name_col:
        _LOG.error(f"[列表标准化] 未找到名称列，columns={df.columns.tolist()}")
        return None
    
    # ===== 核心修复：在原df上直接处理，避免索引对应问题 =====
    
    # 定义提取函数（带降级逻辑）
    def extract_code_market(row):
        """从一行数据中提取代码和市场"""
        raw_code = row[code_col] if pd.notna(row[code_col]) else ''
        clean, market = _extract_market_and_clean_symbol(str(raw_code))
        
        # 降级：如果提取的市场为空且有_market_source字段
        if not market and '_market_source' in row and pd.notna(row['_market_source']):
            market = str(row['_market_source'])
        
        return pd.Series({'symbol': clean, 'market': market})
    
    # 应用提取（在原df上操作，索引自动对应）
    extracted = df.apply(extract_code_market, axis=1)
    
    # 构建结果
    result = pd.DataFrame()
    result['symbol'] = extracted['symbol']
    result['market'] = extracted['market']
    result['name'] = df[name_col].astype(str).str.strip()
    result['type'] = category
    
    # 诊断：市场分布
    _LOG.info(f"[列表标准化] 前缀处理完成，市场分布: {result['market'].value_counts().to_dict()}")
    _LOG.info(f"[列表标准化] 代码示例（前3条）: {result['symbol'].head(3).tolist()}")
    
    # 处理上市日期
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
    
    # 去重（按清洁后的代码）
    result = result.drop_duplicates(subset=['symbol']).reset_index(drop=True)
    
    # 过滤空代码
    result = result[result['symbol'].str.len() > 0]
    
    _LOG.info(f"[列表标准化] 输出行数={len(result)}")
    _LOG.info(f"[列表标准化] 前3条数据: {result.head(3).to_dict('records')}")
    
    return result

# ==============================================================================
# 交易日历标准化（保持V5.0版本不变）
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
# 档案标准化（保持V5.0版本不变）
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
    
    # ===== 关键修复：初始化所有必需字段（保证兼容性）=====
    profile_dict = {
        'listing_date': None,
        'total_shares': None,
        'float_shares': None,
        'industry': None,
        'region': None,      # ← 新增默认值
        'concepts': None,    # ← 保持现有逻辑（后续可能处理）
    }
    
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
        
        # ===== 新增：处理 region 字段 =====
        elif item in ['地区', 'region']:
            if pd.notna(value):
                profile_dict['region'] = str(value)
    
    # ===== 关键兼容逻辑：只有至少一个非空字段时才返回 =====
    has_any_value = any(
        v is not None 
        for k, v in profile_dict.items() 
        if k != 'region'  # region 可为空，不影响整体有效性
    )
    
    return profile_dict if has_any_value else None