# backend/datasource/providers/sse_adapter/profile_test.py
# ==============================
# 上交所股票 / 基金档案适配器 · 全接口本地联调脚本
#
# 说明：
#   - 仅用于本地开发时快速验证 profile.py 中各接口是否能正常返回数据。
#   - 不参与正式业务逻辑，也不会被 FastAPI 或统一执行器引用。
#   - 运行方式（在项目根目录）：
#       python -m backend.datasource.providers.sse_adapter.profile_test
#
# 覆盖接口：
#   1) get_stock_profile_basic_sh_sse         · 公司基本信息
#   2) get_stock_trading_stats_sh_sse        · 股票成交统计（日/月/年）
#   3) get_stock_share_structure_sh_sse      · 股本结构
#   4) get_fund_profile_basic_sh_sse         · 基金基本信息
#   5) get_fund_trading_stats_sh_sse         · 基金成交统计（日/月/年）
#   6) get_fund_scale_sh_sse                 · 基金规模（时间序列 / 单日）
# ==============================

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

import pandas as pd

from backend.datasource.providers.sse_adapter.profile_sse import (
    get_stock_profile_basic_sh_sse,
    get_stock_trading_stats_sh_sse,
    get_stock_share_structure_sh_sse,
    get_fund_profile_basic_sh_sse,
    get_fund_trading_stats_sh_sse,
    get_fund_scale_sh_sse,
)


async def _run_and_print(
    title: str,
    coro: Callable[[], Awaitable[pd.DataFrame]],
    max_rows: int = 3,
) -> None:
    """
    统一的调用 + 竖版打印工具。

    打印风格：
      - 先打印标题和总行数
      - 再按行（Row 0 / Row 1 / ...）逐一打印
      - 每行按“字段名: 值”竖着列出，便于完整查看所有字段和值
      - 若结果行数大于 max_rows，仅打印前 max_rows 行，最后提示剩余行数
    """
    print("=" * 80)
    print(f"{title}")
    print("-" * 80)
    try:
        df = await coro()
        if df is None or df.empty:
            print("结果：空 DataFrame（无数据）")
        else:
            total_rows = len(df)
            cols = list(df.columns)
            print(f"结果行数：{total_rows}")
            print("字段列表：", cols)
            print("-" * 80)

            rows_to_show = min(max_rows, total_rows)
            for i in range(rows_to_show):
                row = df.iloc[i]
                print(f"Row {i}:")
                for col in cols:
                    val = row[col]
                    print(f"  {col}: {val}")
                print("-" * 40)

            if total_rows > rows_to_show:
                print(f"... 其余 {total_rows - rows_to_show} 行已省略")

    except Exception as e:
        print(f"[ERROR] 调用异常：{e}")
    print()  # 空行分隔


async def main() -> None:
    """
    全接口测试入口。

    说明：
      - 使用固定的示例代码，便于重复测试：
          * 股票：600000 / 600006
          * 基金：510300（沪深300ETF）
      - 日期参数仅作为示例，可以根据实际需要修改。
    """
    # ===== 1. 股票：公司基本信息 =====
    await _run_and_print(
        "1) 股票公司基本信息 · get_stock_profile_basic_sh_sse('600000')",
        lambda: get_stock_profile_basic_sh_sse("600000"),
    )

    # ===== 2. 股票：成交统计（日/月/年）=====
    # 日度：指定日期
    await _run_and_print(
        "2.1) 股票成交统计(日度) · get_stock_trading_stats_sh_sse('600006', 'D', tx_date='2025-11-26')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="D",
            tx_date="2025-11-26",
        ),
    )

    # 月度：指定月份（任意该月的一天）
    await _run_and_print(
        "2.2) 股票成交统计(月度) · get_stock_trading_stats_sh_sse('600006', 'M', tx_date_mon='2025-10-01')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="M",
            tx_date_mon="20231001",
        ),
    )

    # 月度：指定月份（任意该月的一天）
    await _run_and_print(
        "2.2) 股票成交统计(月度) · get_stock_trading_stats_sh_sse('600006', 'M', tx_date_mon='2025-10-01')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="M",
            tx_date_mon="",
        ),
    )

    # 月度：指定月份（任意该月的一天）
    await _run_and_print(
        "2.2) 股票成交统计(月度) · get_stock_trading_stats_sh_sse('600006', 'M', tx_date_mon='2025-10-01')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="M",
        ),
    )

    # 年度：指定年份
    await _run_and_print(
        "2.3) 股票成交统计(年度) · get_stock_trading_stats_sh_sse('600006', 'Y', tx_date_year='2024')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="Y",
            tx_date_year="20231234",
        ),
    )
    await _run_and_print(
        "2.3) 股票成交统计(年度) · get_stock_trading_stats_sh_sse('600006', 'Y', tx_date_year='2024')",
        lambda: get_stock_trading_stats_sh_sse(
            sec_code="600006",
            date_type="Y",
            tx_date_year="20231214",
        ),
    )

    # ===== 3. 股票：股本结构 =====
    await _run_and_print(
        "3) 股票股本结构 · get_stock_share_structure_sh_sse('600006')",
        lambda: get_stock_share_structure_sh_sse("600006"),
    )

    # ===== 4. 基金：基本信息 =====
    await _run_and_print(
        "4) 基金基本信息 · get_fund_profile_basic_sh_sse('510300')",
        lambda: get_fund_profile_basic_sh_sse("510300"),
    )

    # ===== 5. 基金：成交统计（日/月/年）=====
    # 日度：指定日期
    await _run_and_print(
        "5.1) 基金成交统计(日度) · get_fund_trading_stats_sh_sse('510300', 'D', tx_date='2025-11-26')",
        lambda: get_fund_trading_stats_sh_sse(
            sec_code="510300",
            date_type="D",
            tx_date="2025-11-26",
        ),
    )

    # 月度：指定月份
    await _run_and_print(
        "5.2) 基金成交统计(月度) · get_fund_trading_stats_sh_sse('510300', 'M', tx_date_mon='2025-10-01')",
        lambda: get_fund_trading_stats_sh_sse(
            sec_code="510300",
            date_type="M",
            tx_date_mon="20251001",
        ),
    )

    # 年度：指定年份
    await _run_and_print(
        "5.3) 基金成交统计(年度) · get_fund_trading_stats_sh_sse('510300', 'Y', tx_date_year='2024')",
        lambda: get_fund_trading_stats_sh_sse(
            sec_code="510300",
            date_type="Y",
            tx_date_year="20220528",
        ),
    )

    # ===== 6. 基金：规模（时间序列 / 单日）=====
    # 规模时间序列：最近 N 日
    await _run_and_print(
        "6.1) 基金规模时间序列 · get_fund_scale_sh_sse('510300', page_size=5)",
        lambda: get_fund_scale_sh_sse(
            sec_code="510300",
            stat_date=None,
        ),
    )

    # 单日规模：指定日期
    await _run_and_print(
        "6.2) 基金单日规模 · get_fund_scale_sh_sse('510300', stat_date='2025-11-26')",
        lambda: get_fund_scale_sh_sse(
            sec_code="510300",
            stat_date="2025-11-26",
            # page_size=1,  # 无效，仅 SEARCH_L 时不使用
        ),
    )

    print("=" * 80)
    print("所有接口测试完成。")
    print("=" * 80)


if __name__ == "__main__":
    # 在命令行下运行模块时执行全接口测试
    asyncio.run(main())