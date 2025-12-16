# backend/datasource/registry.py
# ==============================
# V10.1 - 精简 + K线统一归口版（无 akshare 依赖）
#
# 说明：
#   - 为了彻底去除业务对 akshare 的依赖，本文件不再引用 akshare_adapter。
#   - 注册的类别包括：
#       1) 标的列表：
#           * stock_list_sh  : 上交所股票列表（SSE）
#           * stock_list_sz  : 深交所股票列表（SZSE）
#           * fund_list_sh   : 上交所场内基金列表（SSE）
#           * fund_list_sz   : 深交所场内基金列表（SZSE）
#       2) 静态与衍生数据（Baostock）：
#           * adj_factor     : 股票前/后复权因子
#           * trade_calendar : 交易日历
#       3) 行情 K 线（东财 / 新浪）：
#           * stock_daily_bars    : A股日K线（东财，不复权/复权由 fqt 控制）
#           * stock_weekly_bars   : A股周K线（东财）
#           * stock_monthly_bars  : A股月K线（东财）
#           * stock_minutely_bars : A股分钟K线（新浪 quotes 通道）
#           * fund_bars           : 场内基金日/周/月K线（东财）
#           * fund_minutely_bars  : 场内基金分钟K线（新浪 quotes 通道）
#
#   - 所有类别均通过 dispatcher.fetch(...) 使用，避免直接依赖具体适配器。
#   - 注意：id 中刻意避免使用 "_em" / "_tx" 字样，防止 normalize_bars_df
#           中对 volume 的“手→股”逻辑被误触发。
# ==============================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Tuple, Optional

# 原子化调用函数
from .providers import sse_adapter
from .providers import szse_adapter
from .providers import baostock_adapter as bs
from .providers import eastmoney_adapter
from .providers import sina_adapter


# --- 1. 方法描述符 (标准化的弹药规格) ---

@dataclass(frozen=True)
class MethodDescriptor:
    """
    定义一个数据获取方法的完整元数据。
    """
    id: str  # 全局唯一ID, 格式: provider.name。例如: "sse.get_stock_list_sh_sse"
    name: str  # 人类可读的名称
    provider: str  # 数据提供商标识符: "sse"/"szse"/"baostock"/"eastmoney"/"sina"
    category: str  # 标准化的数据类别，如 "stock_daily_bars"
    callable: Callable  # 实际调用的函数引用
    priority: int  # 优先级, 数值越小越高。10=主方案, 50=备选, 100=不稳定备用
    tags: Tuple[str, ...] = field(default_factory=tuple)  # 标签, 用于快速过滤
    params_template: Dict[str, Any] = field(default_factory=dict)  # 参数模板, 用于校验和提示
    description: str = ""  # 详细描述


# --- 2. 全部可用方法列表 (军火库清单) ---

_ALL_METHODS: List[MethodDescriptor] = [
    # ==========================================================================
    # 类别: 标的资产列表（只用 SSE/SZSE）
    # ==========================================================================

    # --- A股：上交所股票列表（SSE JSONP）---
    MethodDescriptor(
        id="sse.get_stock_list_sh_sse",
        name="上交所-A股列表 (SSE JSONP)",
        provider="sse",
        category="stock_list_sh",
        callable=sse_adapter.get_stock_list_sh_sse,
        priority=10,
        tags=("stock", "list", "sh", "official", "sse"),
        description="从上交所 JSONP 接口获取沪市股票列表（含主板/科创板）",
    ),

    # --- A股：深交所股票列表（SZSE JSON/XLSX）---
    MethodDescriptor(
        id="szse.get_stock_list_sz_szse",
        name="深交所-A股列表 (SZSE JSON/XLSX)",
        provider="szse",
        category="stock_list_sz",
        callable=szse_adapter.get_stock_list_sz_szse,
        priority=10,
        tags=("stock", "list", "sz", "official", "szse"),
        description="从深交所接口获取深市股票列表",
    ),

    # --- 基金：上交所场内基金列表（SSE JSONP）---
    MethodDescriptor(
        id="sse.get_fund_list_sh_sse",
        name="上交所-场内基金列表 (SSE JSONP)",
        provider="sse",
        category="fund_list_sh",
        callable=sse_adapter.get_fund_list_sh_sse,
        priority=10,
        tags=("fund", "list", "sh", "official", "sse"),
        description="从上交所 ETF 子站获取场内基金列表",
    ),

    # --- 基金：深交所场内基金列表（SZSE JSON/XLSX）---
    MethodDescriptor(
        id="szse.get_fund_list_sz_szse",
        name="深交所-场内基金列表 (SZSE JSON/XLSX)",
        provider="szse",
        category="fund_list_sz",
        callable=szse_adapter.get_fund_list_sz_szse,
        priority=10,
        tags=("fund", "list", "sz", "official", "szse"),
        description="从深交所基金子站获取场内基金列表",
    ),

    # ==========================================================================
    # 类别: 静态与衍生数据（Baostock 因子 + 日历）
    # ==========================================================================

    MethodDescriptor(
        id="baostock.get_adj_factors",
        name="Baostock-前/后复权因子",
        provider="baostock",
        category="adj_factor",
        callable=bs.get_raw_adj_factors_bs,
        priority=10,
        tags=("stock", "factor", "baostock"),
        description="一次性从 Baostock 获取前/后复权因子原始数据（dividOperateDate/foreAdjustFactor/backAdjustFactor）",
    ),

    MethodDescriptor(
        id="baostock.get_trade_calendar",
        name="Baostock-交易日历",
        provider="baostock",
        category="trade_calendar",
        callable=bs.get_trade_calendar_bs,
        priority=10,
        tags=("calendar", "baostock"),
        description="从 Baostock 获取自1990年以来的所有交易日信息（含 is_trading_day 字段）",
    ),

    # ==========================================================================
    # 类别: 行情 K 线（东财 / 新浪）
    # ==========================================================================

    # ---- 股票日K ----
    MethodDescriptor(
        id="eastmoney.stock_daily_kline",
        name="东财-A股日K线",
        provider="eastmoney",
        category="stock_daily_bars",
        callable=eastmoney_adapter.get_kline_em,
        priority=10,
        tags=("stock", "kline", "daily"),
        description="通过 push2his 获取 A 股日K线，freq='1d'，fqt=0/1/2 控制复权方式",
    ),

    # ---- 股票周K ----
    MethodDescriptor(
        id="eastmoney.stock_weekly_kline",
        name="东财-A股周K线",
        provider="eastmoney",
        category="stock_weekly_bars",
        callable=eastmoney_adapter.get_kline_em,
        priority=10,
        tags=("stock", "kline", "weekly"),
        description="通过 push2his 获取 A 股周K线，freq='1w'，fqt=0/1/2 控制复权方式",
    ),

    # ---- 股票月K ----
    MethodDescriptor(
        id="eastmoney.stock_monthly_kline",
        name="东财-A股月K线",
        provider="eastmoney",
        category="stock_monthly_bars",
        callable=eastmoney_adapter.get_kline_em,
        priority=10,
        tags=("stock", "kline", "monthly"),
        description="通过 push2his 获取 A 股月K线，freq='1M'，fqt=0/1/2 控制复权方式",
    ),

    # ---- 股票分钟K（Sina quotes 通道）----
    MethodDescriptor(
        id="sina.stock_minutely_kline",
        name="新浪-A股分钟K",
        provider="sina",
        category="stock_minutely_bars",
        callable=sina_adapter.get_kline_sina,
        priority=10,
        tags=("stock", "kline", "minutely"),
        description="通过 quotes.sina.cn 获取 A 股分钟K线，freq=1m/5m/15m/30m/60m",
    ),

    # ---- 基金日/周/月K（东财 push2his）----
    MethodDescriptor(
        id="eastmoney.fund_kline",
        name="东财-基金日/周/月K线",
        provider="eastmoney",
        category="fund_bars",
        callable=eastmoney_adapter.get_kline_em,
        priority=10,
        tags=("fund", "kline"),
        description="通过 push2his 获取基金日/周/月K线，freq='1d'/'1w'/'1M'，fqt=0/1/2 控制复权方式",
    ),

    # ---- 基金分钟K（Sina quotes 通道）----
    MethodDescriptor(
        id="sina.fund_minutely_kline",
        name="新浪-基金分钟K",
        provider="sina",
        category="fund_minutely_bars",
        callable=sina_adapter.get_kline_sina,
        priority=10,
        tags=("fund", "kline", "minutely"),
        description="通过 quotes.sina.cn 获取基金分钟K线，freq=1m/5m/15m/30m/60m",
    ),
]

# --- 3. 最终导出的方法目录 (按类别分组, 按优先级排序) ---

METHOD_CATALOG: Dict[str, List[MethodDescriptor]] = {}

for method in _ALL_METHODS:
    METHOD_CATALOG.setdefault(method.category, []).append(method)

for category in METHOD_CATALOG:
    METHOD_CATALOG[category].sort(key=lambda m: m.priority)

# --- 4. 辅助查询函数 ---

def find_method_by_id(method_id: str) -> Optional[MethodDescriptor]:
    """通过ID快速查找一个方法描述符。"""
    for method in _ALL_METHODS:
        if method.id == method_id:
            return method
    return None

def get_methods_for_category(category: str) -> List[MethodDescriptor]:
    """获取指定数据类别的所有可用方法，已按优先级排序。"""
    return METHOD_CATALOG.get(category, [])