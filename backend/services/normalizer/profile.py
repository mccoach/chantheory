# backend/services/normalizer/profile.py
# ==============================
# profile_snapshot 标准化
#
# 职责：
#   - 将 provider 层产出的 profile 原始快照标准化为 ready-to-write 结构
#   - 负责：
#       * float_value 计算
#       * concepts 清洗
#       * 行业代码 -> 行业名称
#       * 地域代码 -> 地域名称
#   - 只输出当前极简表所需字段：
#       symbol, market,
#       float_shares, float_value,
#       industry, region, concepts,
#       updated_at(由写库层统一覆盖)
#
# 字段单位约定（经实测确认）：
#   - float_shares : 万股 / 万份
#   - float_value  : 万元
#
# 说明：
#   - base.dbf 中的 float_shares_raw（LTAG）当前按“万股 / 万份”解释；
#   - prev_close 按“元”解释；
#   - 因此：
#       float_shares(万股/万份) × prev_close(元) = 万元
#       float_value(万元) = float_shares × prev_close
#
# 关键原则：
#   - 不制造空白占位记录
#   - provider 只给原始字段，最终解释由 normalizer 完成
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Any, List, Dict

from backend.utils.logger import get_logger
from backend.utils.dataframe import normalize_dataframe
from backend.datasource.local_files import load_tdxzs3_cfg_df

_LOG = get_logger("normalizer.profile")


def _safe_float(val: Any) -> Optional[float]:
    if val in (None, "", "-", "--"):
        return None
    try:
        return float(val)
    except Exception:
        return None


def _normalize_concepts(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        out = []
        seen = set()
        for item in val:
            s = str(item or "").strip()
            if s and s not in seen:
                out.append(s)
                seen.add(s)
        return out
    s = str(val).strip()
    return [s] if s else []


def _load_industry_region_maps() -> tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    从 tdxzs3.cfg 构建：
      - T代码 -> 名称
      - X代码 -> 名称
      - DY编码 -> 地域名称
    """
    t_map: Dict[str, str] = {}
    x_map: Dict[str, str] = {}
    region_map: Dict[str, str] = {}

    try:
        df = load_tdxzs3_cfg_df()
    except Exception as e:
        _LOG.warning("[profile标准化] 加载 tdxzs3.cfg 失败: %s", e)
        return t_map, x_map, region_map

    if df is None or df.empty:
        return t_map, x_map, region_map

    for _, row in df.iterrows():
        cat = str(row.get("category_type") or "").strip()
        extra_code = str(row.get("extra_code") or "").strip()
        name = str(row.get("block_name") or "").strip()

        if not extra_code or not name:
            continue

        if cat == "2":
            t_map[extra_code] = name
        elif cat == "12":
            x_map[extra_code] = name
        elif cat == "3":
            region_map[extra_code] = name

    return t_map, x_map, region_map


def _lookup_industry_name(
    dbf_hy_code: str,
    t_code: str,
    x_code: str,
    t_map: Dict[str, str],
    x_map: Dict[str, str],
) -> Optional[str]:
    """
    行业名称优先级：
      1) tdxhy.cfg 给出的 T代码
      2) tdxhy.cfg 给出的 X代码
      3) base.dbf.HY（若恰好与 T 体系可兼容）
    """
    t_code = str(t_code or "").strip()
    x_code = str(x_code or "").strip()
    dbf_hy_code = str(dbf_hy_code or "").strip()

    if t_code:
        name = t_map.get(t_code)
        if name:
            return name
        for length in (7, 5, 3):
            parent = t_code[:length]
            name = t_map.get(parent)
            if name:
                return name

    if x_code:
        name = x_map.get(x_code)
        if name:
            return name
        for length in (7, 5, 3):
            parent = x_code[:length]
            name = x_map.get(parent)
            if name:
                return name

    if dbf_hy_code:
        name = t_map.get(dbf_hy_code)
        if name:
            return name
        for length in (7, 5, 3):
            parent = dbf_hy_code[:length]
            name = t_map.get(parent)
            if name:
                return name

    return None


def _lookup_region_name(region_code: str, region_map: Dict[str, str]) -> Optional[str]:
    code = str(region_code or "").strip()
    if not code or code in ("0", "154"):
        return None
    return region_map.get(code)


def normalize_profile_snapshot_df(raw_df: pd.DataFrame, source_tag: str = "") -> Optional[pd.DataFrame]:
    """
    标准化 profile_snapshot 原始表。

    provider 原始字段预期包含：
      - symbol
      - market
      - prev_close
      - float_shares_raw
      - industry_code_raw
      - industry_t_code
      - industry_x_code
      - region_code
      - concepts

    输出字段单位：
      - float_shares : 万股 / 万份
      - float_value  : 万元
    """
    if raw_df is None or raw_df.empty:
        _LOG.error("[profile标准化] 输入为空 source_tag=%s", source_tag)
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        _LOG.error("[profile标准化] 预处理后为空 source_tag=%s", source_tag)
        return None

    required_cols = ["symbol", "market"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _LOG.error("[profile标准化] 缺少必要列: %s columns=%s", missing, list(df.columns))
        return None

    t_map, x_map, region_map = _load_industry_region_maps()

    out = pd.DataFrame()
    out["symbol"] = df["symbol"].astype(str).str.strip()
    out["market"] = df["market"].astype(str).str.strip().str.upper()

    # float_shares 单位：万股 / 万份
    if "float_shares_raw" in df.columns:
        out["float_shares"] = df["float_shares_raw"].apply(_safe_float)
    else:
        out["float_shares"] = None

    # float_value 单位：万元
    # 公式依据：
    #   float_shares(万股/万份) × prev_close(元) = 万元
    prev_close_series = df["prev_close"].apply(_safe_float) if "prev_close" in df.columns else None
    if "float_shares_raw" in df.columns and prev_close_series is not None:
        float_shares = out["float_shares"]
        out["float_value"] = [
            (fs * pc if fs is not None and pc is not None else None)
            for fs, pc in zip(float_shares.tolist(), prev_close_series.tolist())
        ]
    else:
        out["float_value"] = None

    # industry：在 normalizer 层完成最终解释
    industry_vals: List[Optional[str]] = []
    for _, row in df.iterrows():
        industry_vals.append(
            _lookup_industry_name(
                dbf_hy_code=row.get("industry_code_raw"),
                t_code=row.get("industry_t_code"),
                x_code=row.get("industry_x_code"),
                t_map=t_map,
                x_map=x_map,
            )
        )
    out["industry"] = industry_vals

    # region：在 normalizer 层完成最终解释
    region_vals: List[Optional[str]] = []
    for _, row in df.iterrows():
        region_vals.append(
            _lookup_region_name(
                region_code=row.get("region_code"),
                region_map=region_map,
            )
        )
    out["region"] = region_vals

    # concepts
    if "concepts" in df.columns:
        out["concepts"] = df["concepts"].apply(_normalize_concepts)
    else:
        out["concepts"] = [[] for _ in range(len(df))]

    # 只保留合法市场
    out = out[out["market"].isin(["SH", "SZ", "BJ"])].copy()

    # 不额外制造空白补位行；provider 传什么，这里只做清洗与去重
    out = out.drop_duplicates(subset=["symbol", "market"], keep="last").reset_index(drop=True)

    _LOG.info("[profile标准化] source_tag=%s 输出行数=%s", source_tag, len(out))
    return out
