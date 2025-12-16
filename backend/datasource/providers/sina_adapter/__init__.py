# backend/datasource/providers/sina_adapter/__init__.py
# ==============================
# 新浪行情适配器包 (Sina · V1.0)
#
# 当前导出：
#   - get_kline_sina : A股/ETF K 线（分钟 + 日线，CN_MarketData.getKLineData）
#
# 说明：
#   - 本包仅封装新浪历史 K 线接口的原子调用，
#     不做任何业务级聚合与入库操作；
#   - 与 akshare_adapter / sse_adapter / szse_adapter / baostock_adapter /
#     eastmoney_adapter 处于同一层级，供 dispatcher/服务层按需组合调用。
# ==============================

from __future__ import annotations

from .kline_1970_sina import get_kline_sina

__all__ = [
    "get_kline_sina",
]