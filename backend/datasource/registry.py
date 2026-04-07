# backend/datasource/registry.py
# ==============================
# 数据源方法目录（最终基础数据收口版）
#
# 正式保留：
#   - TDX 本地基础数据
#
# 正式废弃：
#   - EastMoney K线正式主链
#   - Sina K线正式主链
#   - 旧 stock/fund 多 category K线体系
#
# 说明：
#   - 普通行情远程实时主链不再走 registry/dispatcher
#   - 直接由 services/bars_recipes.py 调用 tdx_remote_adapter
# ==============================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Tuple, Optional

from .providers import tdx_local_adapter


@dataclass(frozen=True)
class MethodDescriptor:
    id: str
    name: str
    provider: str
    category: str
    callable: Callable
    priority: int
    tags: Tuple[str, ...] = field(default_factory=tuple)
    params_template: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


_ALL_METHODS: List[MethodDescriptor] = [
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
    MethodDescriptor(
        id="tdx_local.profile_snapshot",
        name="通达信本地-全市场档案快照",
        provider="tdx_local",
        category="profile_snapshot",
        callable=tdx_local_adapter.get_profile_snapshot_tdx,
        priority=10,
        tags=("local", "tdx", "profile", "snapshot"),
        description="解析 tnf/base.dbf/tdxhy.cfg/tdxzs3.cfg/infoharbor_block.dat，组装全市场 profile 原始快照",
    ),
    MethodDescriptor(
        id="tdx_local.trade_calendar",
        name="通达信本地-完整自然日历",
        provider="tdx_local",
        category="trade_calendar",
        callable=tdx_local_adapter.get_trade_calendar_tdx,
        priority=10,
        tags=("local", "tdx", "calendar"),
        description="基于 needini.dat 节假日集合 + 周六周日规则，构建完整自然日历",
    ),
    MethodDescriptor(
        id="tdx_local.gbbq_events_raw",
        name="通达信本地-gbbq全量原始事件表",
        provider="tdx_local",
        category="gbbq_events_raw",
        callable=tdx_local_adapter.get_gbbq_events_raw_tdx,
        priority=10,
        tags=("local", "tdx", "gbbq", "raw"),
        description="解析 gbbq 并返回全量原始事件表",
    ),
]

METHOD_CATALOG: Dict[str, List[MethodDescriptor]] = {}

for method in _ALL_METHODS:
    METHOD_CATALOG.setdefault(method.category, []).append(method)

for category in METHOD_CATALOG:
    METHOD_CATALOG[category].sort(key=lambda m: m.priority)


def find_method_by_id(method_id: str) -> Optional[MethodDescriptor]:
    for method in _ALL_METHODS:
        if method.id == method_id:
            return method
    return None


def get_methods_for_category(category: str) -> List[MethodDescriptor]:
    return METHOD_CATALOG.get(category, [])
