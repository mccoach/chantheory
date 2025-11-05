# backend/utils/dataframe.py
# ==============================
# 说明：DataFrame 基础预处理工具
# 职责：提供最基础的 DataFrame 清洗（去空格、验证）
# 原则：不做任何业务逻辑，只做最基础的预处理
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional

def normalize_dataframe(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    DataFrame 基础预处理（零业务逻辑版）
    
    职责：
      1. 基础验证（非空检查）
      2. 列名清洗（去除首尾空格）
      3. 返回干净的副本
    
    不做：
      - ❌ 不识别列名含义
      - ❌ 不处理时区
      - ❌ 不转换时间戳
      - ❌ 不映射字段
    
    Args:
        df: 原始DataFrame
    
    Returns:
        Optional[pd.DataFrame]: 预处理后的DataFrame，失败返回None
    
    Examples:
        >>> raw = pd.DataFrame({'  日期  ': [...], ' 开盘 ': [...]})
        >>> clean = normalize_dataframe(raw)
        >>> clean.columns
        Index(['日期', '开盘'], dtype='object')
    """
    # 验证
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    
    # 创建副本（避免修改原数据）
    x = df.copy()
    
    # 列名清洗（唯一职责）
    x.columns = [str(c).strip() for c in x.columns]
    
    return x