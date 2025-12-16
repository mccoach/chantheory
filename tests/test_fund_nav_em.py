# tests/test_fund_nav_em.py
# ==============================
# 说明：东财基金历史净值接口简单测试程序
#
# 用途：
#   - 直接按 F5 运行，验证 backend.datasource.providers.eastmoney_adapter.nav
#     中 get_fund_nav_em 的基本功能是否正常：
#       * 是否能正常请求东财 F10 /f10/lsjz 接口；
#       * 是否能跨页拉取全量数据并拼成一个 DataFrame；
#       * 字段结构是否符合设计：['date','nav','acc_nav','pct_change',...]
#
# 运行方式：
#   1. 确保当前工作目录为项目根目录（包含 backend/ 和 tests/）；
#   2. 在 VS Code / PyCharm 中打开本文件，直接按 F5 运行；
#   3. 观察控制台输出的行数和前几行数据。
#
# 注意：
#   - 本测试程序只做最基础的联通性与结构验证，不做断言框架集成；
#   - 若需要集成到 pytest，可在后续基于本文件改造为正式用例。
# ==============================

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import pandas as pd

# 确保可以 import backend.* （默认 F5 从项目根目录运行时不需要这段；
# 若你的运行环境无法识别 backend 包，可手动将项目根加入 sys.path）
if "backend" not in sys.modules:
    # 以当前文件所在目录的上级目录作为项目根
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from backend.datasource.providers.eastmoney_adapter.nav_em import get_fund_nav_em  # noqa: E402
from backend.utils.logger import get_logger  # noqa: E402

_LOG = get_logger("tests.test_fund_nav_em")


async def _run_single_test(
    fund_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    """
    对单个基金代码执行一次净值拉取测试，并打印简要信息。

    Args:
        fund_code: 基金代码（如 '510130','159102'）
        start_date: 起始日期（可选，'YYYY-MM-DD' 或兼容格式）
        end_date: 截止日期（可选，'YYYY-MM-DD' 或兼容格式）
    """
    print("=" * 80)
    print(
        f"测试基金：{fund_code}  start={start_date or '-'}  end={end_date or '-'}")
    print("-" * 80)

    try:
        df: pd.DataFrame = await get_fund_nav_em(
            fund_code=fund_code,
            start_date=start_date,
            end_date=end_date,
            page_size=200,
        )
    except Exception as e:
        print(f"[ERROR] get_fund_nav_em 发生异常：{e}")
        _LOG.error(f"[测试] get_fund_nav_em({fund_code}) 异常: {e}", exc_info=True)
        return

    print(f"行数：{len(df)}")
    if df.empty:
        print("DataFrame 为空。可能是：代码错误 / 日期范围无数据 / 网络问题。")
        return

    print("\n字段列表：")
    print(list(df.columns))

    print("\n前 5 行：")
    print(df.head(5).to_string(index=False))

    print("\n最后 3 行：")
    print(df.tail(3).to_string(index=False))


async def main() -> None:
    """
    主测试入口：

    - 用两个你提供过抓包示例的 ETF 做测试：
        * 510130：中盘 ETF
        * 159102：中小板 ETF
    - 第一次：不限制日期，拉取可用的全量历史净值；
    - 第二次：示例性增加一个带 end_date 的调用，验证日期过滤逻辑。
    """
    # 示例1：510130，全量
    await _run_single_test("510130", start_date=None, end_date=None)

    # 示例2：159102，限制 end_date
    # await _run_single_test("159102", start_date=None, end_date="2025-12-07")


if __name__ == "__main__":
    # 直接按 F5 运行本文件时，从这里启动异步测试
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试被手动中断。")
