# backend/datasource/registry.py
# ==============================
# 说明: 数据源武器库 - 方法注册表 (The Catalog)
# - 职责:
#   1. 导入所有原子化调用层的适配器函数。
#   2. 为每个函数创建标准化的 `MethodDescriptor`。
#   3. 按数据类别分组，并按优先级排序，构建统一的方法目录 `METHOD_CATALOG`。
# - 设计:
#   - 这是一个静态的、声明式的配置文件，集中管理所有数据源的元数据和策略。
#   - 外部调用者（如 dispatcher）通过查询 `METHOD_CATALOG` 获取执行方案。
# ==============================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Tuple, Optional

# 导入所有原子化调用函数
from .providers import akshare_adapter as ak

# --- 1. 方法描述符 (标准化的弹药规格) ---

@dataclass(frozen=True)
class MethodDescriptor:
    """
    定义一个数据获取方法的完整元数据。
    """
    id: str  # 全局唯一ID, 格式: provider.name。例如: "akshare.get_stock_daily_em"
    name: str  # 人类可读的名称。例如: "东方财富-A股日K线"
    provider: str  # 数据提供商的标识符。例如: "akshare"
    category: str  # 标准化的数据类别。例如: "stock_daily_bars"
    callable: Callable  # 实际调用的函数引用。例如: ak.get_stock_daily_em
    priority: int  # 优先级, 数值越小越高。10=主方案, 50=备选, 100=不稳定备用
    tags: Tuple[str, ...] = field(default_factory=tuple)  # 标签, 用于快速过滤。例如: ('stock', 'daily', 'kline', 'em')
    params_template: Dict[str, Any] = field(default_factory=dict) # 参数模板, 用于校验和提示
    description: str = ""  # 详细描述

# --- 2. 全部可用方法列表 (军火库清单) ---
# 此列表将包含所有数据源的所有可用方法。

_ALL_METHODS: List[MethodDescriptor] = [
    # ==========================================================================
    # 类别: 标的资产列表
    # ==========================================================================
    
    # --- A股 ---
    MethodDescriptor(
        id="akshare.get_stock_list_all_exchanges",
        name="三交易所官网-A股列表(复合)",
        provider="akshare",
        category="stock_list",
        callable=ak.get_stock_list_all_exchanges,
        priority=5,  # 最高优先级
        tags=('stock', 'list', 'official', 'composite'),
        description="从上交所、深交所、北交所官网分别获取并合并，数据最完整"
    ),
    # 原有的单独接口降为备用
    MethodDescriptor(
        id="akshare.get_stock_list_a_em",
        name="东方财富-A股列表",
        provider="akshare",
        category="stock_list",
        callable=ak.get_stock_list_a_em,
        priority=50,  # 降为备用
        tags=('stock', 'list', 'em')
    ),
    # 以下接口可以作为"档案补充"单独保留，或移除（因为已被复合方法包含）
    # MethodDescriptor(id="akshare.get_stock_list_sh", name="上交所-A股列表", provider="akshare", category="stock_list", callable=ak.get_stock_list_sh, priority=10, tags=('stock', 'list', 'sh')),
    # MethodDescriptor(id="akshare.get_stock_list_sz", name="深交所-A股列表", provider="akshare", category="stock_list", callable=ak.get_stock_list_sz, priority=10, tags=('stock', 'list', 'sz')),
    # MethodDescriptor(id="akshare.get_stock_list_bj", name="北交所-A股列表", provider="akshare", category="stock_list", callable=ak.get_stock_list_bj, priority=10, tags=('stock', 'list', 'bj')),
    
    # 以下接口可以作为"档案补充"单独保留，或移除（因为已被复合方法包含）
    MethodDescriptor(id="akshare.get_stock_list_a_em", name="东方财富-A股列表", provider="akshare", category="stock_list", callable=ak.get_stock_list_a_em, priority=50, tags=('stock', 'list', 'em')),
    
    # --- ETF/LOF ---
    MethodDescriptor(id="akshare.get_etf_list_sina", name="新浪财经-ETF列表", provider="akshare", category="etf_list", callable=ak.get_etf_list_sina, priority=10, tags=('etf', 'list', 'sina')),
    MethodDescriptor(id="akshare.get_lof_list_sina", name="新浪财经-LOF列表", provider="akshare", category="lof_list", callable=ak.get_lof_list_sina, priority=10, tags=('lof', 'list', 'sina')),
    MethodDescriptor(id="akshare.get_etf_list_em", name="东方财富-ETF列表(不稳定)", provider="akshare", category="etf_list", callable=ak.get_etf_list_em, priority=100, tags=('etf', 'list', 'em', 'unstable')),
    MethodDescriptor(id="akshare.get_lof_list_em", name="东方财富-LOF列表(不稳定)", provider="akshare", category="lof_list", callable=ak.get_lof_list_em, priority=100, tags=('lof', 'list', 'em', 'unstable')),
    
    # --- 指数 ---
    MethodDescriptor(id="akshare.get_index_list_sina", name="新浪财经-指数列表", provider="akshare", category="index_list", callable=ak.get_index_list_sina, priority=10, tags=('index', 'list', 'sina')),
    MethodDescriptor(id="akshare.get_index_list_em", name="东方财富-指数列表(不稳定)", provider="akshare", category="index_list", callable=ak.get_index_list_em, priority=100, tags=('index', 'list', 'em', 'unstable')),
    
    # --- 板块 ---
    MethodDescriptor(id="akshare.get_industry_board_list_ths", name="同花顺-行业板块列表", provider="akshare", category="industry_board_list", callable=ak.get_industry_board_list_ths, priority=10, tags=('board', 'list', 'industry', 'ths')),
    MethodDescriptor(id="akshare.get_industry_board_list_em", name="东方财富-行业板块列表(不稳定)", provider="akshare", category="industry_board_list", callable=ak.get_industry_board_list_em, priority=100, tags=('board', 'list', 'industry', 'em', 'unstable')),
    MethodDescriptor(id="akshare.get_concept_board_list_em", name="东方财富-概念板块列表(不稳定)", provider="akshare", category="concept_board_list", callable=ak.get_concept_board_list_em, priority=100, tags=('board', 'list', 'concept', 'em', 'unstable')),

    # ==========================================================================
    # 类别: 历史行情数据
    # ==========================================================================
    
    # --- A股 ---
    MethodDescriptor(id="akshare.get_stock_bars", name="东方财富-A股日/周/月K", provider="akshare", category="stock_bars", callable=ak.get_stock_daily_em, priority=10, tags=('stock', 'kline', 'em')),
    MethodDescriptor(id="akshare.get_stock_daily_bars_sina", name="新浪财经-A股日K", provider="akshare", category="stock_bars", callable=ak.get_stock_daily_sina, priority=20, tags=('stock', 'kline', 'daily', 'sina')),
    MethodDescriptor(id="akshare.get_stock_daily_bars_tx", name="腾讯财经-A股日K", provider="akshare", category="stock_bars", callable=ak.get_stock_daily_tx, priority=30, tags=('stock', 'kline', 'daily', 'tx')),
    MethodDescriptor(id="akshare.get_stock_minutely_bars_sina", name="新浪财经-A股分钟K", provider="akshare", category="stock_minutely_bars", callable=ak.get_minutely_sina, priority=10, tags=('stock', 'kline', 'minutely', 'sina')),
    MethodDescriptor(id="akshare.get_stock_minutely_bars_em", name="东方财富-A股分钟K(不稳定)", provider="akshare", category="stock_minutely_bars", callable=ak.get_minutely_em, priority=100, tags=('stock', 'kline', 'minutely', 'em', 'unstable')),
    MethodDescriptor(
        id="akshare.get_stock_weekly_em",
        name="东方财富-A股周K",
        provider="akshare",
        category="stock_bars",
        callable=ak.get_stock_daily_em,  # 复用daily方法，通过period参数区分
        priority=10,
        tags=('stock', 'kline', 'weekly', 'em')
    ),
    MethodDescriptor(
        id="akshare.get_stock_monthly_em",
        name="东方财富-A股月K",
        provider="akshare",
        category="stock_bars",
        callable=ak.get_stock_daily_em,  # 复用daily方法
        priority=10,
        tags=('stock', 'kline', 'monthly', 'em')
    ),
    
    # --- 基金 (ETF/LOF) ---
    MethodDescriptor(id="akshare.get_fund_bars_sina", name="新浪财经-ETF/LOF日K", provider="akshare", category="fund_bars", callable=ak.get_fund_daily_sina, priority=10, tags=('etf', 'lof', 'kline', 'daily', 'sina')),
    MethodDescriptor(id="akshare.get_fund_minutely_bars_sina", name="新浪财经-ETF/LOF分钟K", provider="akshare", category="fund_minutely_bars", callable=ak.get_minutely_sina, priority=10, tags=('etf', 'lof', 'kline', 'minutely', 'sina')),
    MethodDescriptor(id="akshare.get_etf_bars_em", name="东方财富-ETF日K(不稳定)", provider="akshare", category="fund_bars", callable=ak.get_etf_daily_em, priority=100, tags=('etf', 'kline', 'daily', 'em', 'unstable')),
    MethodDescriptor(id="akshare.get_lof_bars_em", name="东方财富-LOF日K(不稳定)", provider="akshare", category="fund_bars", callable=ak.get_lof_daily_em, priority=100, tags=('lof', 'kline', 'daily', 'em', 'unstable')),
    MethodDescriptor(id="akshare.get_etf_minutely_bars_em", name="东方财富-ETF分钟K(不稳定)", provider="akshare", category="fund_minutely_bars", callable=ak.get_etf_minutely_em, priority=100, tags=('etf', 'kline', 'minutely', 'em', 'unstable')),
    MethodDescriptor(id="akshare.get_lof_minutely_bars_em", name="东方财富-LOF分钟K(不稳定)", provider="akshare", category="fund_minutely_bars", callable=ak.get_lof_minutely_em, priority=100, tags=('lof', 'kline', 'minutely', 'em', 'unstable')),

    # --- 指数 ---
    MethodDescriptor(id="akshare.get_index_bars_em", name="东方财富-指数日K", provider="akshare", category="index_bars", callable=ak.get_index_daily_em, priority=10, tags=('index', 'kline', 'daily', 'em')),
    MethodDescriptor(id="akshare.get_index_bars_sina", name="新浪财经-指数日K", provider="akshare", category="index_bars", callable=ak.get_index_daily_sina, priority=20, tags=('index', 'kline', 'daily', 'sina')),
    MethodDescriptor(id="akshare.get_index_bars_tx", name="腾讯财经-指数日K", provider="akshare", category="index_bars", callable=ak.get_index_daily_tx, priority=30, tags=('index', 'kline', 'daily', 'tx')),
    MethodDescriptor(id="akshare.get_index_minutely_sina", name="新浪财经-指数分钟K", provider="akshare", category="index_minutely_bars", callable=ak.get_minutely_sina, priority=10, tags=('index', 'kline', 'minutely', 'sina')),
    MethodDescriptor(id="akshare.get_index_minutely_em", name="东方财富-指数分钟K(不稳定)", provider="akshare", category="index_minutely_bars", callable=ak.get_index_minutely_em, priority=100, tags=('index', 'kline', 'minutely', 'em', 'unstable')),
    
    # ==========================================================================
    # 类别: 静态与衍生数据
    # ==========================================================================
    MethodDescriptor(
        id="akshare.get_qfq_factor", name="新浪财经-前复权因子", provider="akshare", category="adj_factor",
        callable=ak.get_adj_factor, priority=10, tags=('stock', 'factor', 'qfq', 'sina'),
        params_template={'symbol': str, 'adjust_type': 'qfq-factor'},
        description="获取前复权因子"
    ),
    MethodDescriptor(
        id="akshare.get_hfq_factor", name="新浪财经-后复权因子", provider="akshare", category="adj_factor",
        callable=ak.get_adj_factor, priority=10, tags=('stock', 'factor', 'hfq', 'sina'),
        params_template={'symbol': str, 'adjust_type': 'hfq-factor'},
        description="获取后复权因子"
    ),
    MethodDescriptor(id="akshare.get_stock_profile_em", name="东方财富-个股档案", provider="akshare", category="stock_profile", callable=ak.get_stock_profile_em, priority=10, tags=('stock', 'profile', 'em')),
    MethodDescriptor(id="akshare.get_fund_profile_xq", name="雪球-基金档案", provider="akshare", category="fund_profile", callable=ak.get_fund_profile_xq, priority=10, tags=('fund', 'profile', 'xq')),
    MethodDescriptor(id="akshare.get_trade_calendar", name="新浪财经-交易日历", provider="akshare", category="trade_calendar", callable=ak.get_trade_calendar, priority=10, tags=('calendar', 'sina')),
]


# --- 3. 最终导出的方法目录 (按类别分组, 按优先级排序) ---

METHOD_CATALOG: Dict[str, List[MethodDescriptor]] = {}

for method in _ALL_METHODS:
    if method.category not in METHOD_CATALOG:
        METHOD_CATALOG[method.category] = []
    METHOD_CATALOG[method.category].append(method)

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
