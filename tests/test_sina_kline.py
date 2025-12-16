# backend/tests/test_sina_kline.py
# ==============================
# 说明：新浪 K 线原子接口测试脚本（手工运行版）
#
# 目的：
#   - 覆盖 A 股 / ETF 各类标的 + 各类周期频率，对 get_kline_sina 做一次端到端验证；
#   - 仅作为开发/联调时的手工测试脚本，不参与生产运行。
#
# 覆盖范围：
#   1. 标的类型（与 EastMoney 测试脚本保持一致）：
#       - 上证主板 A 股   ：600519  （贵州茅台）【如需可解注释】
#       - 深证主板 A 股   ：000001  （平安银行）
#       - 创业板 A 股     ：300750  （宁德时代）
#       - 上证 ETF 基金  ：510300  （沪深300ETF）
#       - 深证 ETF 基金  ：159102  （中小板指数 ETF）
#
#      说明：
#        - get_kline_sina 内部使用 ak_symbol_with_prefix 自动补 'sh'/'sz'，
#          不依赖 symbol_index.market，理论上不需要本地 DB 支持；
#        - 本测试脚本仍可选用 symbol_index 存在检查，主要用于对齐 EastMoney 测试行为。
#
#   2. 周期频率（freq）：
#       - '1m'  : 1 分钟 K 线
#       - '5m'  : 5 分钟 K 线
#       - '15m' : 15 分钟 K 线
#       - '30m' : 30 分钟 K 线
#       - '60m' : 60 分钟 K 线
#       - '1d'  : 日 K
#       - '1w'  : 周 K（scale=1680，新浪约定 1680 分钟 = 1 周）
#
# 运行前置条件：
#   - 不强制要求 symbol_index 存在，但若你希望在同一环境下对比 EastMoney/Sina，
#     推荐同样先执行一次标的列表同步，便于后续扩展为组合测试。
#
# 使用方式（命令行）：
#   - 在项目根目录下执行：
#       python -m backend.tests.test_sina_kline
#
#   - 或直接指定文件运行：
#       python E:\AppProject\ChanTheory\backend\tests\test_sina_kline.py
#
# 输出：
#   - 每个 [symbol × freq] 组合会打印一条概览：
#       [OK] 600519 1d  rows=1970  cols=['date','open',...]
#       [OK] 510300 5m  rows=2000 cols=['time','open',...]
#   - 若网络失败或响应结构异常，会打印 [ERROR] 原因说明。
# ==============================

from __future__ import annotations

import os
import sys
import asyncio
from typing import List

import pandas as pd

# ==============================================================================
# 1. 手动修正 sys.path：确保可以 import backend.*
# ==============================================================================

# 当前文件所在目录：.../ChanTheory/tests
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 项目根目录：.../ChanTheory
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 现在才能安全导入 backend 包
from backend.datasource.providers import sina_adapter
from backend.db.symbols import select_symbol_index
from backend.utils.logger import get_logger

_LOG = get_logger("test.sina_kline")

# ==============================================================================
# 2. 测试配置：标的 & 频率
# ==============================================================================

# 测试用标的列表（你可以按需增删）
TEST_SYMBOLS: List[str] = [
    "600519",  # 上证主板 A 股  - 贵州茅台
    "000001",  # 深证主板 A 股  - 平安银行
    "300750",  # 创业板 A 股    - 宁德时代
    "510300",  # 上证 ETF 基金  - 沪深300ETF
    "159102",  # 深证 ETF 基金  - 中小板指数 ETF
]

# 测试用频率列表（覆盖分钟 / 日 / 周）
TEST_FREQS: List[str] = [
    "1m",
    "5m",
    # "15m",
    # "30m",
    # "60m",
    "1d",
    "1w",
]

# 均线参数（当前适配器不会使用返回的 ma 字段，这里统一传 "no" 关闭）
TEST_MA: str = "no"

# 若你希望在运行测试前检查 symbol_index 中是否存在该 symbol，可打开该开关
ENABLE_DB_SYMBOL_CHECK: bool = False

# ==============================================================================
# 3. 工具函数
# ==============================================================================

def _symbol_exists_in_db(symbol: str) -> bool:
    """辅助：检查 symbol_index 中是否存在该 symbol。"""
    rows = select_symbol_index(symbol=symbol)
    return bool(rows)


async def _test_single_case(symbol: str, freq: str) -> None:
    """
    测试单个 [symbol × freq] 组合。

    行为：
      - 若 ENABLE_DB_SYMBOL_CHECK=True 且 symbol_index 中无该 symbol：
          打印 [SKIP_DB] 并返回；
      - 否则：
          * 调用 get_kline_sina(symbol, freq, ma=TEST_MA)
          * 打印 DataFrame 概览（行数、列名、前 2 行示例）。
    """
    if ENABLE_DB_SYMBOL_CHECK and not _symbol_exists_in_db(symbol):
        print(f"[SKIP_DB] symbol_index 中不存在 {symbol}，请先同步标的列表")
        return

    try:
        df: pd.DataFrame = await sina_adapter.get_kline_sina(
            symbol=symbol,
            freq=freq,
            ma=TEST_MA,
        )
    except Exception as e:
        print(f"[ERROR] symbol={symbol} freq={freq} 调用异常：{e}")
        _LOG.error(
            "[测试] Sina K 线接口异常",
            extra={"symbol": symbol, "freq": freq, "ma": TEST_MA, "error": str(e)},
        )
        return

    if df is None or df.empty:
        print(f"[WARN] symbol={symbol} freq={freq} 返回空 DataFrame")
        return

    cols = list(df.columns)
    head_rows = df.head(2).to_dict(orient="records")

    print(
        f"[OK] symbol={symbol:<6} freq={freq:<3} "
        f"rows={len(df):>4} cols={cols}"
    )
    print(f"     sample[0:2]={head_rows}")


async def run_all_tests() -> None:
    """按 symbol × freq 组合顺序依次执行测试。"""
    print("=" * 80)
    print("Sina K-Line Adapter Test - 股票/基金 × 各频率 (CN_MarketDataService.getKLineData)")
    print("=" * 80)

    for symbol in TEST_SYMBOLS:
        print(f"\n----- 测试标的: {symbol} -----")
        for freq in TEST_FREQS:
            await _test_single_case(symbol, freq)


def main() -> None:
    """同步入口：封装 asyncio.run。"""
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n[INFO] 测试被用户中断")


if __name__ == "__main__":
    main()