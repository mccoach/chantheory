# backend/tests/test_eastmoney_kline.py
# ==============================
# 说明：东方财富 K 线原子接口测试脚本（手工运行版）
#
# 目的：
#   - 覆盖 A 股各类标的 + 各类周期频率，对 get_kline_em 做一次端到端验证；
#   - 仅作为开发/联调时的手工测试脚本，不参与生产运行。
#
# 覆盖范围：
#   1. 标的类型（基于 symbol_index.class/type）：
#       - 上证主板 A 股   ：600519  （贵州茅台）
#       - 深证主板 A 股   ：000001  （平安银行）
#       - 创业板 A 股     ：300750  （宁德时代）
#       - 上证 ETF 基金  ：510300  （沪深300ETF）
#       - 深证 LOF 基金  ：161005  （富国天惠成长混合LOF）
#
#      说明：
#        - get_kline_em 底层只依赖 symbol_index.market，不校验 class/type，
#          因此对 ETF/LOF 也可使用（只要 symbol_index 有 market）。
#
#   2. 周期频率（freq）：
#       - '1m'  : 1 分钟 K 线
#       - '5m'  : 5 分钟 K 线
#       - '15m' : 15 分钟 K 线
#       - '30m' : 30 分钟 K 线
#       - '60m' : 60 分钟 K 线
#       - '1d'  : 日 K
#       - '1w'  : 周 K
#       - '1M'  : 月 K
#
#   3. 复权方式（fqt）：
#       - 本测试脚本当前仅验证 **不复权模式**（fqt=0），
#         确保与系统默认行为保持一致；
#       - 如需联调前复权/后复权，可在 _test_single_case 中调整 fqt=1/2。
#
# 运行前置条件：
#   - 已完成标的列表同步（symbol_index 已就绪），否则会看到类似错误：
#       "symbol '600519' not found in symbol_index 或其 market 字段为空..."
#   - 推荐先跑一次：
#       * 后端已启动时：调用 /api/symbols/refresh 或 /api/symbols/refresh-force；
#       * 或在 Python 里：await backend.services.symbol_sync.sync_all_symbols()
#
# 使用方式（命令行）：
#   - 在项目根目录下执行：
#       python -m backend.tests.test_eastmoney_kline
#
#   - 或直接指定文件运行：
#       python E:\AppProject\ChanTheory\backend\tests\test_eastmoney_kline.py
#
# 输出：
#   - 每个 [symbol × freq] 组合会打印一条概览：
#       [OK] 600519 1d  rows=210  cols=['date','open',...]
#       [OK] 510300 5m  rows=200  cols=['time','open',...]
#   - 若 symbol_index 不存在该标的、或网络失败、或响应结构异常，会打印 [SKIP]/[ERROR] 原因说明。
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
from backend.datasource.providers import eastmoney_adapter
from backend.db.symbols import select_symbol_index
from backend.utils.logger import get_logger
from backend.utils.time import today_ymd

_LOG = get_logger("test.eastmoney_kline")

# ==============================================================================
# 2. 测试配置：标的 & 频率
# ==============================================================================

# 测试用标的列表（你可以按需增删）
TEST_SYMBOLS: List[str] = [
    # "600519",  # 上证主板 A 股  - 贵州茅台
    # "000001",  # 深证主板 A 股  - 平安银行
    # "300750",  # 创业板 A 股    - 宁德时代
    "510300",  # 上证 ETF 基金  - 沪深300ETF
    "161005",  # 深证 LOF 基金  - 富国天惠
]

# 测试用频率列表（覆盖 8 种）
TEST_FREQS: List[str] = [
    "1m",
    "5m",
    # "15m",
    # "30m",
    # "60m",
    "1d",
    # "1w",
    # "1M",
]

# 当前测试使用的复权方式（0=不复权；1=前复权；2=后复权）
TEST_FQT: int = 0

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
      - 若 symbol_index 中无该 symbol：打印 [SKIP_DB] 并返回；
      - 否则：
          * 调用 get_kline_em(symbol, freq, end=today, fqt=TEST_FQT)
          * 打印 DataFrame 概览（行数、列名、前 2 行示例）。
    """
    if not _symbol_exists_in_db(symbol):
        print(f"[SKIP_DB] symbol_index 中不存在 {symbol}，请先同步标的列表")
        return

    end_ymd = today_ymd()
    end_str = f"{end_ymd:08d}"

    try:
        df: pd.DataFrame = await eastmoney_adapter.get_kline_em(
            symbol=symbol,
            freq=freq,
            end=end_str,
            fqt=TEST_FQT,
        )
    except Exception as e:
        print(f"[ERROR] symbol={symbol} freq={freq} 调用异常：{e}")
        _LOG.error(
            "[测试] EastMoney K 线接口异常",
            extra={"symbol": symbol, "freq": freq, "fqt": TEST_FQT, "error": str(e)},
        )
        return

    if df is None or df.empty:
        print(f"[WARN] symbol={symbol} freq={freq} fqt={TEST_FQT} 返回空 DataFrame")
        return

    cols = list(df.columns)
    head_rows = df.head(2).to_dict(orient="records")

    print(
        f"[OK] symbol={symbol:<6} freq={freq:<3} fqt={TEST_FQT} "
        f"rows={len(df):>4} cols={cols}"
    )
    print(f"     sample[0:2]={head_rows}")


async def run_all_tests() -> None:
    """按 symbol × freq 组合顺序依次执行测试。"""
    print("=" * 80)
    print("EastMoney K-Line Adapter Test - 股票/基金 × 各频率 (fqt=0 不复权)")
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