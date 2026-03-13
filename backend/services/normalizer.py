# backend/services/normalizer.py
# ==============================
# 数据标准化器
#
# 本轮改动（symbol_index 专项）：
#   - 标的列表标准化已切换为 TDX 本地统一原始字段输入
#   - 删除旧交易所官网字段映射逻辑
#   - symbol_index 输出结构统一为：
#       symbol, market, name, class, type, listing_date
#
# 分类规则原则：
#   - 先粗类型（tdx_coarse_type）
#   - 再市场（market）
#   - 再代码特征（symbol 前缀）
#   - 三项同时命中时，分类才成立
#   - 可判则判，不可判则留空
#
# 【可用分类列表】（强制约束）
# 1. stock：
#    - 主板A股
#    - 创业板股票
#    - 科创板股票
#    - 北交所股票
#    - B股
#    - 优先股
# 2. fund：
#    - 场内ETF
#    - LOF基金
#    - 公募REITs
#    - 封闭式基金
#    - 开放式基金
# 3. bond：
#    - 可转债/可交换债
#    - 国债逆回购
#    - 普通债券
#    - 资产支持证券 (ABS)
# 4. index：
#    - 官方指数
#    - 通达信指数
# 5. other：
#    - 业务办理
#
# 注意：
#   - 绝不输出上述列表之外的新 type 名称
#   - 原表中包含但本轮未被官方规则覆盖的旧规则，保留并标注“推断规则”
# 规则依据：
#   - 上交所代码段分配指南依据上交所2025-12-23发布的《关于扩展分配并启用相关代码段的通知》附件：《上海证券交易所证券交易业务指南第4号——证券代码段分配指南（2025年第5次修订）》
#   - 深交所代码规则依据深交所2026-03-06发布的《深圳证券交易所证券代码区间表（2026年3月修订）》
#   - 北交所代码规则依据北交所2024-04-19发布的《北京证券交易所 全国中小企业股份转让系统证券代码、证券简称编制指引》
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Dict, Any, Tuple, List

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


def normalize_bars_df(raw_df: pd.DataFrame,
                      source_id: str) -> Optional[pd.DataFrame]:
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
        '日期': 'date',
        'date': 'date',
        '时间': 'time',
        'day': 'time',
        'datetime': 'time',
        # OHLC
        '开盘': 'open',
        'open': 'open',
        '收盘': 'close',
        'close': 'close',
        '最高': 'high',
        'high': 'high',
        '最低': 'low',
        'low': 'low',
        # 成交量额
        '成交量': 'volume',
        'volume': 'volume',
        '成交额': 'amount',
        'amount': 'amount',
        # 换手率
        '换手率': 'turnover_rate',
        '换手': 'turnover_rate',
        'turnover': 'turnover_rate',
        'turnover_rate': 'turnover_rate',
    }
    rename_map = {
        col: field_map[col]
        for col in df.columns if col in field_map
    }
    df = df.rename(columns=rename_map)

    has_date = 'date' in df.columns
    has_time = 'time' in df.columns
    time_col = 'time' if has_time else ('date' if has_date else None)

    if not time_col:
        _LOG.error(
            f"[标准化] 未找到时间列，source={source_id}, columns={df.columns.tolist()}")
        return None

    required = ['open', 'high', 'low', 'close']
    if not all(c in df.columns for c in required):
        _LOG.error(
            f"[标准化] 缺少必需字段，source={source_id}, columns={df.columns.tolist()}")
        return None

    is_minutely = has_time
    if is_minutely:
        df['ts'] = df[time_col].apply(_safe_parse_datetime)
    else:
        df['ts'] = df[time_col].apply(_safe_parse_date_to_close)
    df = df.drop(columns=[time_col], errors='ignore')

    # volume：标准化层只做数值化，不做单位换算（单位换算应由数据源适配器明确负责）
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    else:
        df['volume'] = 0.0

    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    else:
        df['amount'] = None

    if 'turnover_rate' in df.columns:
        df['turnover_rate'] = pd.to_numeric(df['turnover_rate'],
                                            errors='coerce') / 100.0
    else:
        df['turnover_rate'] = None

    output_cols = [
        'ts', 'open', 'high', 'low', 'close', 'volume', 'amount',
        'turnover_rate'
    ]
    for col in output_cols:
        if col not in df.columns:
            df[col] = None

    df = df[output_cols].copy()
    df = df.drop_duplicates(subset=['ts']).sort_values('ts').reset_index(
        drop=True)
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

    required_cols = [
        "dividOperateDate", "foreAdjustFactor", "backAdjustFactor"
    ]
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
        lambda v: parse_yyyymmdd(str(v).strip()) if pd.notna(v) else None)
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].astype(int)

    # 2. 数值化前/后复权因子
    df["qfq_factor"] = pd.to_numeric(df["foreAdjustFactor"], errors="coerce")
    df["hfq_factor"] = pd.to_numeric(df["backAdjustFactor"], errors="coerce")

    # 丢弃完全无效的行
    df = df.dropna(subset=["qfq_factor", "hfq_factor"], how="all")

    if df.empty:
        return None

    out = df[["date", "qfq_factor", "hfq_factor"]].drop_duplicates(
        subset=["date"]).sort_values("date").reset_index(drop=True)

    _LOG.info(
        "[因子标准化-Baostock] 标准化完成: source_id=%s, rows=%d",
        source_id,
        len(out),
    )

    return out


# ==============================================================================
# 标的列表标准化（TDX 本地统一字段版）
# ==============================================================================


def _normalize_listing_date(value: Any) -> Optional[int]:
    """
    将原始 listing_date 统一标准化为 int YYYYMMDD。

    设计说明：
      - provider 层约定传入 'YYYYMMDD' 字符串或 None；
      - 这里负责最终转为 int；
      - 额外保留极小防御性容错：若未来别处误传 19910403.0 这类值，也尽量纠正，
        但这不是主路径依赖。
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s or s in ("-", "--", "None", "nan", "<NA>"):
        return None

    if s.isdigit() and len(s) == 8:
        try:
            return int(s)
        except Exception:
            return None

    if s.endswith(".0"):
        s2 = s[:-2]
        if s2.isdigit() and len(s2) == 8:
            try:
                return int(s2)
            except Exception:
                return None

    try:
        return parse_yyyymmdd(s)
    except Exception:
        return None


# ------------------------------------------------------------------------------
# 三键联合分类规则表：
#   (粗类型, 市场, 前缀) -> (class, type)
# 数据结构保持不变：
#   _RULES[coarse_type][market] = [(prefix, class, type), ...]
#
# 说明：
#   - 本轮以你提供的官方规则为主进行替换/补充
#   - 原表中保留但未被本轮官方规则覆盖的内容，以“推断规则”注释保留
#   - 所有 type 强制收敛到固定子类集合中
# ------------------------------------------------------------------------------

_RULES: Dict[int, Dict[str, List[Tuple[str, str, str]]]] = {
    # ==========================================================
    # 2 = 权益（股票 / 指数 / 优先股）
    # ==========================================================
    2: {
        "SH": [
            # 股票及存托凭证类
            ("689", "stock", "科创板股票"),  # 上交所代码规则
            ("688", "stock", "科创板股票"),  # 上交所代码规则
            ("605", "stock", "主板A股"),  # 上交所代码规则
            ("603", "stock", "主板A股"),  # 上交所代码规则
            ("601", "stock", "主板A股"),  # 上交所代码规则
            ("600", "stock", "主板A股"),  # 上交所代码规则
            ("900", "stock", "B股"),  # 上交所代码规则
            ("360", "stock", "优先股"),  # 上交所代码规则
            ("330", "stock", "优先股"),  # 上交所代码规则

            # 申购 / 增发 / 配号 / 其他交易辅助代码（仍归股票主板）
            ("736", "stock", "主板A股"),  # 上交所代码规则
            ("732", "stock", "主板A股"),  # 上交所代码规则

            # 指数
            ("000", "index", "官方指数"),  # 上交所代码规则
            ("99", "index", "通达信指数"),  # 推断规则
            ("88", "index", "通达信指数"),  # 推断规则

            # 业务办理 (指定交易、两融划转、密码服务、身份认证等功能性代码)
            ("799970", "other", "业务办理"),  # 上交所代码规则 (资金前端控制)
            ("799981", "other", "业务办理"),  # 上交所代码规则 (两融余券划转)
            ("799982", "other", "业务办理"),  # 上交所代码规则 (两融还券划转)
            ("799983", "other", "业务办理"),  # 上交所代码规则 (两融担保物划转)
            ("799984", "other", "业务办理"),  # 上交所代码规则 (两融券源划转)
            ("799988", "other", "业务办理"),  # 上交所代码规则 (网络投票密码服务)
            ("799991", "other", "业务办理"),  # 上交所代码规则 (身份认证)
            ("799993", "other", "业务办理"),  # 上交所代码规则 (转融通提醒)
            ("799996", "other", "业务办理"),  # 上交所代码规则 (回购指定撤销)
            ("799997", "other", "业务办理"),  # 上交所代码规则 (回购指定)
            ("799998", "other", "业务办理"),  # 上交所代码规则 (撤销指定)
            ("799999", "other", "业务办理"),  # 上交所代码规则 (指定交易)
        ],
        "SZ": [
            # 股票及存托凭证类
            ("30", "stock", "创业板股票"),  # 深交所代码规则
            ("004", "stock", "主板A股"),  # 深交所代码规则
            ("003", "stock", "主板A股"),  # 深交所代码规则
            ("002", "stock", "主板A股"),  # 深交所代码规则
            ("001", "stock", "主板A股"),  # 深交所代码规则
            ("000", "stock", "主板A股"),  # 深交所代码规则
            ("20", "stock", "B股"),  # 深交所代码规则
            ("140", "stock", "优先股"),  # 深交所代码规则

            # 指数
            ("971", "index", "官方指数"),  # 深交所代码规则
            ("970", "index", "官方指数"),  # 深交所代码规则
            ("98", "index", "官方指数"),  # 深交所代码规则
            ("395", "index", "官方指数"),  # 深交所代码规则，统计指标
            ("399", "index", "官方指数"),  # 深交所代码规则
        ],
        "BJ": [
            ("899", "index", "官方指数"),  # 北交所代码规则
            ("92", "stock", "北交所股票"),  # 北交所代码规则
            ("88", "stock", "北交所股票"),  # 北交所代码规则
            ("87", "stock", "北交所股票"),  # 北交所代码规则
            ("83", "stock", "北交所股票"),  # 北交所代码规则
            ("820", "stock", "优先股"),  # 北交所代码规则
            ("420", "stock", "B股"),  # 北交所代码规则
            ("400", "stock", "北交所股票"),  # 北交所代码规则
        ],
    },

    # ==========================================================
    # 3 = 基金
    # ==========================================================
    3: {
        "SH": [
            # 场内ETF
            ("589", "fund", "场内ETF"),  # 上交所代码规则
            ("588", "fund", "场内ETF"),  # 上交所代码规则
            ("563", "fund", "场内ETF"),  # 上交所代码规则
            ("562", "fund", "场内ETF"),  # 上交所代码规则
            ("561", "fund", "场内ETF"),  # 上交所代码规则
            ("560", "fund", "场内ETF"),  # 上交所代码规则
            ("551", "fund", "场内ETF"),  # 上交所代码规则
            ("530", "fund", "场内ETF"),  # 上交所代码规则
            ("526", "fund", "场内ETF"),  # 上交所代码规则
            ("5209", "fund", "场内ETF"),  # 上交所代码规则
            ("5208", "fund", "场内ETF"),  # 上交所代码规则
            ("5207", "fund", "场内ETF"),  # 上交所代码规则
            ("5206", "fund", "场内ETF"),  # 上交所代码规则
            ("5205", "fund", "场内ETF"),  # 上交所代码规则
            ("518", "fund", "场内ETF"),  # 上交所代码规则
            ("517", "fund", "场内ETF"),  # 上交所代码规则
            ("516", "fund", "场内ETF"),  # 上交所代码规则
            ("515", "fund", "场内ETF"),  # 上交所代码规则
            ("513", "fund", "场内ETF"),  # 上交所代码规则
            ("512", "fund", "场内ETF"),  # 上交所代码规则
            ("511", "fund", "场内ETF"),  # 上交所代码规则
            ("510", "fund", "场内ETF"),  # 上交所代码规则

            # LOF基金
            ("5060", "fund", "LOF基金"),  # 上交所代码规则
            ("502", "fund", "LOF基金"),  # 上交所代码规则
            ("501", "fund", "LOF基金"),  # 上交所代码规则

            # 公募REITs
            ("5080", "fund", "公募REITs"),  # 上交所代码规则

            # 封闭式基金
            ("550", "fund", "封闭式基金"),  # 上交所代码规则
            ("5058", "fund", "封闭式基金"),  # 上交所代码规则
            ("500", "fund", "封闭式基金"),  # 上交所代码规则

            # 封闭式基金
            ("519", "fund", "开放式基金"),  # 上交所代码规则

            # 股票及存托凭证类（实测发现shs.tnf文件中，900代码段粗分类被写成了3而非2，只能在此处增补规则补遗
            ("900", "stock", "B股"),  # 上交所代码规则
        ],
        "SZ": [
            # 场内ETF
            ("159", "fund", "场内ETF"),  # 深交所代码规则
            ("158", "fund", "场内ETF"),  # 深交所代码规则

            # LOF基金
            ("17", "fund", "LOF基金"),  # 深交所代码规则
            ("16", "fund", "LOF基金"),  # 深交所代码规则
            ("151", "fund", "LOF基金"),  # 深交所代码规则
            ("150", "fund", "LOF基金"),  # 深交所代码规则

            # 公募REITs
            ("1819", "fund", "公募REITs"),  # 深交所代码规则
            ("1818", "fund", "公募REITs"),  # 深交所代码规则
            ("1817", "fund", "公募REITs"),  # 深交所代码规则
            ("1816", "fund", "公募REITs"),  # 深交所代码规则
            ("1815", "fund", "公募REITs"),  # 深交所代码规则
            ("1814", "fund", "公募REITs"),  # 深交所代码规则
            ("1813", "fund", "公募REITs"),  # 深交所代码规则
            ("1812", "fund", "公募REITs"),  # 深交所代码规则
            ("1811", "fund", "公募REITs"),  # 深交所代码规则
            ("1810", "fund", "公募REITs"),  # 深交所代码规则
            ("1809", "fund", "公募REITs"),  # 深交所代码规则
            ("1808", "fund", "公募REITs"),  # 深交所代码规则
            ("1807", "fund", "公募REITs"),  # 深交所代码规则
            ("1806", "fund", "公募REITs"),  # 深交所代码规则
            ("1805", "fund", "公募REITs"),  # 深交所代码规则
            ("1804", "fund", "公募REITs"),  # 深交所代码规则
            ("1803", "fund", "公募REITs"),  # 深交所代码规则
            ("1802", "fund", "公募REITs"),  # 深交所代码规则
            ("1801", "fund", "公募REITs"),  # 深交所代码规则

            # 封闭式基金
            ("184", "fund", "封闭式基金"),  # 深交所代码规则
        ],
        "BJ": [
            # 本轮暂无官方 BJ 基金代码规则，保留空
        ],
    },

    # ==========================================================
    # 4 = 债券
    # ==========================================================
    4: {
        "SH": [
            # 国债逆回购
            ("207", "bond", "国债逆回购"),  # 上交所代码规则
            ("206", "bond", "国债逆回购"),  # 上交所代码规则
            ("205", "bond", "国债逆回购"),  # 上交所代码规则
            ("204", "bond", "国债逆回购"),  # 上交所代码规则
            ("203", "bond", "国债逆回购"),  # 上交所代码规则
            ("202", "bond", "国债逆回购"),  # 上交所代码规则
            ("201", "bond", "国债逆回购"),  # 上交所代码规则

            # 可转债/可交换债
            ("1374", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1373", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1372", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1371", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1370", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("132", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("126", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1186", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1185", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1184", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1183", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1182", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1181", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1180", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("113", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1114", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1113", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1112", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1111", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1110", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("110", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1008", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1007", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1006", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1005", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1004", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1003", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1002", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1001", "bond", "可转债/可交换债"),  # 上交所代码规则
            ("1000", "bond", "可转债/可交换债"),  # 上交所代码规则

            # 资产支持证券 (ABS)
            ("26", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("199", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1939", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1938", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1937", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1936", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1935", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1934", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1933", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1932", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1931", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("189", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("183", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("180", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("179", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("169", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("168", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("165", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("159", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("156", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("149", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("146", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("142", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("131", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("128", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1239", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1238", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1237", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1236", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("1235", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("121", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则
            ("112", "bond", "资产支持证券 (ABS)"),  # 上交所代码规则

            # 普通债券
            ("751", "bond", "普通债券"),  # 上交所代码规则，国债预发行及债券分销
            ("282", "bond", "普通债券"),  # 上交所代码规则
            ("281", "bond", "普通债券"),  # 上交所代码规则
            ("280", "bond", "普通债券"),  # 上交所代码规则
            ("272", "bond", "普通债券"),  # 上交所代码规则
            ("271", "bond", "普通债券"),  # 上交所代码规则
            ("270", "bond", "普通债券"),  # 上交所代码规则
            ("25", "bond", "普通债券"),  # 上交所代码规则
            ("247", "bond", "普通债券"),  # 上交所代码规则
            ("246", "bond", "普通债券"),  # 上交所代码规则
            ("245", "bond", "普通债券"),  # 上交所代码规则
            ("244", "bond", "普通债券"),  # 上交所代码规则
            ("243", "bond", "普通债券"),  # 上交所代码规则
            ("242", "bond", "普通债券"),  # 上交所代码规则
            ("241", "bond", "普通债券"),  # 上交所代码规则
            ("240", "bond", "普通债券"),  # 上交所代码规则
            ("238", "bond", "普通债券"),  # 上交所代码规则
            ("237", "bond", "普通债券"),  # 上交所代码规则
            ("236", "bond", "普通债券"),  # 上交所代码规则
            ("235", "bond", "普通债券"),  # 上交所代码规则
            ("234", "bond", "普通债券"),  # 上交所代码规则
            ("233", "bond", "普通债券"),  # 上交所代码规则
            ("232", "bond", "普通债券"),  # 上交所代码规则
            ("231", "bond", "普通债券"),  # 上交所代码规则
            ("230", "bond", "普通债券"),  # 上交所代码规则
            ("198", "bond", "普通债券"),  # 上交所代码规则
            ("197", "bond", "普通债券"),  # 上交所代码规则
            ("196", "bond", "普通债券"),  # 上交所代码规则
            ("194", "bond", "普通债券"),  # 上交所代码规则
            ("188", "bond", "普通债券"),  # 上交所代码规则
            ("186", "bond", "普通债券"),  # 上交所代码规则
            ("185", "bond", "普通债券"),  # 上交所代码规则
            ("184", "bond", "普通债券"),  # 上交所代码规则
            ("1829", "bond", "普通债券"),  # 上交所代码规则
            ("1828", "bond", "普通债券"),  # 上交所代码规则
            ("1827", "bond", "普通债券"),  # 上交所代码规则
            ("1826", "bond", "普通债券"),  # 上交所代码规则
            ("1825", "bond", "普通债券"),  # 上交所代码规则
            ("1824", "bond", "普通债券"),  # 上交所代码规则
            ("1823", "bond", "普通债券"),  # 上交所代码规则
            ("178", "bond", "普通债券"),  # 上交所代码规则
            ("177", "bond", "普通债券"),  # 上交所代码规则
            ("175", "bond", "普通债券"),  # 上交所代码规则
            ("173", "bond", "普通债券"),  # 上交所代码规则
            ("171", "bond", "普通债券"),  # 上交所代码规则
            ("167", "bond", "普通债券"),  # 上交所代码规则
            ("166", "bond", "普通债券"),  # 上交所代码规则
            ("163", "bond", "普通债券"),  # 上交所代码规则
            ("162", "bond", "普通债券"),  # 上交所代码规则
            ("160", "bond", "普通债券"),  # 上交所代码规则
            ("157", "bond", "普通债券"),  # 上交所代码规则
            ("155", "bond", "普通债券"),  # 上交所代码规则
            ("152", "bond", "普通债券"),  # 上交所代码规则
            ("151", "bond", "普通债券"),  # 上交所代码规则
            ("150", "bond", "普通债券"),  # 上交所代码规则
            ("147", "bond", "普通债券"),  # 上交所代码规则
            ("145", "bond", "普通债券"),  # 上交所代码规则
            ("143", "bond", "普通债券"),  # 上交所代码规则
            ("140", "bond", "普通债券"),  # 上交所代码规则
            ("139", "bond", "普通债券"),  # 上交所代码规则
            ("1389", "bond", "普通债券"),  # 上交所代码规则
            ("1388", "bond", "普通债券"),  # 上交所代码规则
            ("1387", "bond", "普通债券"),  # 上交所代码规则
            ("1386", "bond", "普通债券"),  # 上交所代码规则
            ("1385", "bond", "普通债券"),  # 上交所代码规则
            ("1379", "bond", "普通债券"),  # 上交所代码规则
            ("1378", "bond", "普通债券"),  # 上交所代码规则
            ("1377", "bond", "普通债券"),  # 上交所代码规则
            ("1376", "bond", "普通债券"),  # 上交所代码规则
            ("1375", "bond", "普通债券"),  # 上交所代码规则
            ("136", "bond", "普通债券"),  # 上交所代码规则
            ("135", "bond", "普通债券"),  # 上交所代码规则
            ("130", "bond", "普通债券"),  # 上交所代码规则
            ("129", "bond", "普通债券"),  # 上交所代码规则
            ("127", "bond", "普通债券"),  # 上交所代码规则
            ("125", "bond", "普通债券"),  # 上交所代码规则
            ("124", "bond", "普通债券"),  # 上交所代码规则
            ("1234", "bond", "普通债券"),  # 上交所代码规则
            ("1233", "bond", "普通债券"),  # 上交所代码规则
            ("1232", "bond", "普通债券"),  # 上交所代码规则
            ("1231", "bond", "普通债券"),  # 上交所代码规则
            ("1230", "bond", "普通债券"),  # 上交所代码规则
            ("122", "bond", "普通债券"),  # 上交所代码规则
            ("120", "bond", "普通债券"),  # 上交所代码规则
            ("115", "bond", "普通债券"),  # 上交所代码规则
            ("114", "bond", "普通债券"),  # 上交所代码规则
            ("109", "bond", "普通债券"),  # 上交所代码规则
            ("101", "bond", "普通债券"),  # 上交所代码规则
            ("020", "bond", "普通债券"),  # 上交所代码规则
            ("019", "bond", "普通债券"),  # 上交所代码规则
            ("018", "bond", "普通债券"),  # 上交所代码规则
            ("010", "bond", "普通债券"),  # 上交所代码规则
            ("009", "bond", "普通债券"),  # 上交所代码规则
        ],
        "SZ": [
            # 国债逆回购
            ("1320", "bond", "国债逆回购"),  # 深交所代码规则
            ("1318", "bond", "国债逆回购"),  # 深交所代码规则

            # 可转债/可交换债
            ("22", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("128", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("127", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("124", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("123", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1214", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1213", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1212", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1211", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1210", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("120", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1174", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1173", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1172", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1171", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1170", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1159", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1158", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1157", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1156", "bond", "可转债/可交换债"),  # 深交所代码规则
            ("1150", "bond", "可转债/可交换债"),  # 深交所代码规则

            # 资产支持证券 (ABS)
            ("51", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("50", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("146", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("144", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("143", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("139", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("138", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("137", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("136", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("135", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1219", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1218", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1217", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1216", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1215", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1194", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1193", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1192", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1191", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("1190", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则
            ("116", "bond", "资产支持证券 (ABS)"),  # 深交所代码规则

            # 普通债券
            ("59", "bond", "普通债券"),  # 深交所代码规则
            ("58", "bond", "普通债券"),  # 深交所代码规则
            ("57", "bond", "普通债券"),  # 深交所代码规则
            ("56", "bond", "普通债券"),  # 深交所代码规则
            ("52", "bond", "普通债券"),  # 深交所代码规则
            ("19", "bond", "普通债券"),  # 深交所代码规则
            ("1899", "bond", "普通债券"),  # 深交所代码规则
            ("1898", "bond", "普通债券"),  # 深交所代码规则
            ("1897", "bond", "普通债券"),  # 深交所代码规则
            ("1896", "bond", "普通债券"),  # 深交所代码规则
            ("1895", "bond", "普通债券"),  # 深交所代码规则
            ("149", "bond", "普通债券"),  # 深交所代码规则
            ("148", "bond", "普通债券"),  # 深交所代码规则
            ("134", "bond", "普通债券"),  # 深交所代码规则
            ("133", "bond", "普通债券"),  # 深交所代码规则
            ("130", "bond", "普通债券"),  # 深交所代码规则
            ("118", "bond", "普通债券"),  # 深交所代码规则
            ("1179", "bond", "普通债券"),  # 深交所代码规则
            ("1178", "bond", "普通债券"),  # 深交所代码规则
            ("1177", "bond", "普通债券"),  # 深交所代码规则
            ("1176", "bond", "普通债券"),  # 深交所代码规则
            ("1175", "bond", "普通债券"),  # 深交所代码规则
            ("1155", "bond", "普通债券"),  # 深交所代码规则
            ("1154", "bond", "普通债券"),  # 深交所代码规则
            ("1153", "bond", "普通债券"),  # 深交所代码规则
            ("1152", "bond", "普通债券"),  # 深交所代码规则
            ("1151", "bond", "普通债券"),  # 深交所代码规则
            ("114", "bond", "普通债券"),  # 深交所代码规则
            ("112", "bond", "普通债券"),  # 深交所代码规则
            ("111", "bond", "普通债券"),  # 深交所代码规则
            ("110", "bond", "普通债券"),  # 深交所代码规则
            ("10", "bond", "普通债券"),  # 深交所代码规则
        ],
        "BJ": [
            ("821", "bond", "普通债券"),  # 北交所代码规则
            ("810", "bond", "可转债/可交换债"),  # 北交所代码规则
        ],
    },
}


def _match_by_rules(coarse_type: int, market: str,
                    symbol: str) -> Tuple[Optional[str], Optional[str]]:
    """
    三键联合分类：
      1) 先粗类型
      2) 再市场
      3) 再代码前缀

    只有三项同时命中时，分类才成立。
    """
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()

    if not m or not s:
        return None, None

    market_rules = _RULES.get(int(coarse_type), {}).get(m, [])
    for prefix, cls, typ in market_rules:
        if s.startswith(prefix):
            return cls, typ

    return None, None


def _classify_tdx_symbol(
        market: str, symbol: str,
        coarse_type: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    返回:
      (class, type)

    规则：
      - 先粗类型
      - 再市场
      - 再代码前缀
      - 三键联合命中才成立
      - 可判则判，不可判则留空
    """
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()

    try:
        ct = int(coarse_type)
    except Exception:
        return None, None

    if ct not in (2, 3, 4):
        return None, None

    return _match_by_rules(ct, m, s)


def normalize_symbol_list_df(raw_df: pd.DataFrame,
                             source_tag: str = "") -> Optional[pd.DataFrame]:
    """
    标的列表标准化（TDX 本地统一字段版）

    输入字段要求：
      - symbol
      - market
      - name
      - tdx_coarse_type
      - listing_date（可选，约定为 'YYYYMMDD' 字符串或 None）

    输出：
      - symbol
      - market
      - name
      - class
      - type
      - listing_date（int YYYYMMDD 或 None）
    """
    if raw_df is None or raw_df.empty:
        _LOG.error(f"[列表标准化] 输入为空，source_tag={source_tag}")
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        _LOG.error(f"[列表标准化] 预处理后为空，source_tag={source_tag}")
        return None

    required_cols = ["symbol", "market", "name", "tdx_coarse_type"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _LOG.error(
            "[列表标准化] 缺少必要列: %s columns=%s",
            missing,
            list(df.columns),
        )
        return None

    result = pd.DataFrame()
    result["symbol"] = df["symbol"].astype(str).str.strip()
    result["market"] = df["market"].astype(str).str.strip().str.upper()
    result["name"] = df["name"].astype(str).str.strip()
    result["tdx_coarse_type"] = df["tdx_coarse_type"]

    if "listing_date" in df.columns:
        result["listing_date"] = df["listing_date"].apply(
            _normalize_listing_date)
    else:
        result["listing_date"] = None

    # 仅保留 SH / SZ / BJ
    result = result[result["market"].isin(["SH", "SZ", "BJ"])]

    # 基于三键联合分类
    classified = result.apply(
        lambda row: _classify_tdx_symbol(
            market=row.get("market"),
            symbol=row.get("symbol"),
            coarse_type=row.get("tdx_coarse_type"),
        ),
        axis=1,
    )
    result["class"] = [x[0] for x in classified]
    result["type"] = [x[1] for x in classified]

    result = result.drop(columns=["tdx_coarse_type"], errors="ignore")
    result = result.drop_duplicates(subset=["symbol", "market"],
                                    keep="last").reset_index(drop=True)

    _LOG.info(
        "[列表标准化] source_tag=%s 输出行数=%s",
        source_tag,
        len(result),
    )

    return result


# ==============================================================================
# 交易日历标准化（支持 Baostock & 其他来源）
# ==============================================================================


def normalize_trade_calendar_df(
        raw_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    标准化交易日历
    ...
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
            df['is_trading_day'] = pd.to_numeric(df['is_trading_day'],
                                                 errors='coerce')
            before_rows = len(df)
            df = df[df['is_trading_day'] == 1].reset_index(drop=True)
            _LOG.info(
                "[日历标准化] 按 is_trading_day 过滤：%d → %d 行",
                before_rows,
                len(df),
            )
        except Exception as e:
            _LOG.warning("[日历标准化] is_trading_day 过滤失败，保留全部数据: error=%s", e)

    df['date'] = df[date_col].apply(lambda v: parse_yyyymmdd(str(v))
                                    if pd.notna(v) else None)
    df = df.dropna(subset=['date'])
    df['date'] = df['date'].astype(int)

    return df[['date'
               ]].drop_duplicates().sort_values('date').reset_index(drop=True)


# ==============================================================================
# 档案基础信息标准化（EM 源，仅保留非数值字段；数值型市值/股本由 SSE/SZSE 专用管线负责）
# ==============================================================================


def normalize_stock_profile_df(
        raw_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    标准化个股/基金档案（单标的 · EM 源基础版）
    ...
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

    has_any = any(v is not None for k, v in profile.items()
                  if k not in ("concepts", "total_value", "nego_value",
                               "pe_static"))
    return profile if has_any else None
