# backend/datasource/providers/eastmoney_adapter/__init__.py
# ==============================
# 东方财富行情适配器包 (EastMoney · V1.1)
#
# 当前导出：
#   - get_kline_em    : A股股票 K 线（支持 8 种频率，fqt=0/1/2 复权方式可选）
#   - get_fund_nav_em : 基金历史净值（F10 /f10/lsjz，全量自动翻页）
#
# 说明：
#   - 本包仅封装东财 push2his 历史 K 线接口与 F10 历史净值接口的原子调用，
#     不做任何业务级聚合与入库操作；
#   - 与 akshare_adapter / sse_adapter / szse_adapter / baostock_adapter
#     处于同一层级，供 dispatcher/服务层按需组合调用。
# ==============================

from __future__ import annotations

from .kline_em import get_kline_em
from .nav_em import get_fund_nav_em

__all__ = [
    "get_kline_em",
    "get_fund_nav_em",
]