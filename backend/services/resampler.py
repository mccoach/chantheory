# backend/services/resampler.py
# ==============================
# 说明：K线重采样工具（日线 → 周线/月线）
# 职责：当周月线接口失败时，从日线数据重采样
# ==============================

from __future__ import annotations
import pandas as pd
from typing import Optional
from backend.utils.logger import get_logger

_LOG = get_logger("resampler")

def resample_daily_to_weekly(df_daily: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    日线重采样为周线（周五收盘）
    
    Args:
        df_daily: 日线数据（标准格式，包含 ts, open, high, low, close, volume 列）
    
    Returns:
        Optional[pd.DataFrame]: 周线数据，失败返回 None
    """
    try:
        if df_daily is None or df_daily.empty:
            return None
        
        # 复制避免修改原数据
        df = df_daily.copy()
        
        # 将 ts（毫秒时间戳）转为 datetime 索引
        df['datetime'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('datetime')
        
        # 周线聚合（周五收盘）
        df_weekly = df.resample('W-FRI').agg({
            'ts': 'last',       # 最后一根的时间戳
            'open': 'first',    # 第一根的开盘
            'high': 'max',      # 最高价
            'low': 'min',       # 最低价
            'close': 'last',    # 最后一根的收盘
            'volume': 'sum',    # 成交量求和
        })
        
        # 删除空行（没有交易日的周）
        df_weekly = df_weekly.dropna(subset=['close'])
        
        # 重置索引
        df_weekly = df_weekly.reset_index(drop=True)
        
        # 添加可选列（如果原数据有）
        if 'amount' in df.columns:
            df_weekly['amount'] = df.resample('W-FRI')['amount'].sum()
        else:
            df_weekly['amount'] = None
        
        if 'turnover_rate' in df.columns:
            # 换手率：取平均
            df_weekly['turnover_rate'] = df.resample('W-FRI')['turnover_rate'].mean()
        else:
            df_weekly['turnover_rate'] = None
        
        _LOG.info(f"[重采样] 日线 → 周线：{len(df)} → {len(df_weekly)} 根")
        
        return df_weekly
    
    except Exception as e:
        _LOG.error(f"[重采样] 日线 → 周线失败: {e}")
        return None


def resample_daily_to_monthly(df_daily: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    日线重采样为月线（月末收盘）
    
    Args:
        df_daily: 日线数据
    
    Returns:
        Optional[pd.DataFrame]: 月线数据，失败返回 None
    """
    try:
        if df_daily is None or df_daily.empty:
            return None
        
        df = df_daily.copy()
        df['datetime'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('datetime')
        
        # 月线聚合（月末）
        df_monthly = df.resample('M').agg({
            'ts': 'last',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        })
        
        df_monthly = df_monthly.dropna(subset=['close'])
        df_monthly = df_monthly.reset_index(drop=True)
        
        if 'amount' in df.columns:
            df_monthly['amount'] = df.resample('M')['amount'].sum()
        else:
            df_monthly['amount'] = None
        
        if 'turnover_rate' in df.columns:
            df_monthly['turnover_rate'] = df.resample('M')['turnover_rate'].mean()
        else:
            df_monthly['turnover_rate'] = None
        
        _LOG.info(f"[重采样] 日线 → 月线：{len(df)} → {len(df_monthly)} 根")
        
        return df_monthly
    
    except Exception as e:
        _LOG.error(f"[重采样] 日线 → 月线失败: {e}")
        return None