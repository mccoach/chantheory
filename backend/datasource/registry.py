# backend/datasource/registry.py
# ==============================
# 数据源方法目录 V11.0
#
# 本轮改动（symbol_index 专项）：
#   - 标的列表主数据源已从交易所官网爬取切换为 TDX 本地文件解析
#   - symbol list category 改为按市场分三类：
#       * symbol_list_sh
#       * symbol_list_sz
#       * symbol_list_bj
#
# 说明：
#   - 其他 provider（SSE/SZSE/Baostock/EastMoney/Sina）仍保留给其他业务使用
#   - 本轮只移除 symbol_index 主链路对旧官网列表方案的依赖
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
from .providers import tdx_local_adapter


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
    # 类别: 标的资产列表（主数据源已切换为 TDX 本地文件）
    # ==========================================================================

    MethodDescriptor(
        id="tdx_local.symbol_list_sh",
        name="通达信本地-上交所全量标的列表",
        provider="tdx_local",
        category="symbol_list_sh",
        callable=tdx_local_adapter.get_symbol_list_sh_tdx,
        priority=10,
        tags=("local", "tdx", "symbol", "list", "sh"),
        description="解析 hq_cache/shs.tnf，并左连接 base.dbf 的 listing_date",
    ),

    MethodDescriptor(
        id="tdx_local.symbol_list_sz",
        name="通达信本地-深交所全量标的列表",
        provider="tdx_local",
        category="symbol_list_sz",
        callable=tdx_local_adapter.get_symbol_list_sz_tdx,
        priority=10,
        tags=("local", "tdx", "symbol", "list", "sz"),
        description="解析 hq_cache/szs.tnf，并左连接 base.dbf 的 listing_date",
    ),

    MethodDescriptor(
        id="tdx_local.symbol_list_bj",
        name="通达信本地-北交所全量标的列表",
        provider="tdx_local",
        category="symbol_list_bj",
        callable=tdx_local_adapter.get_symbol_list_bj_tdx,
        priority=10,
        tags=("local", "tdx", "symbol", "list", "bj"),
        description="解析 hq_cache/bjs.tnf，并左连接 base.dbf 的 listing_date（匹配不到则为空）",
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
