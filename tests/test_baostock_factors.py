# tests/test_baostock_factors.py
# ==============================
# 说明：
#   - 用于手工测试 Baostock 复权因子适配器：
#       backend.datasource.providers.baostock_adapter.get_raw_adj_factors_bs
#   - 直接运行本文件即可：
#       python -m tests.test_baostock_factors
#   - 依赖：
#       pip install baostock akshare pandas
# ==============================

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# --- 确保可以以模块方式导入 backend.* ---
# 当前文件：E:\AppProject\ChanTheory\tests\test_baostock_factors.py
# 项目根：  E:\AppProject\ChanTheory  ← parents[1]
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.datasource.providers.baostock_adapter import (  # noqa: E402
    get_raw_adj_factors_bs,
)
from backend.utils.logger import get_logger  # noqa: E402

_LOG = get_logger("test_baostock_factors")


async def main():
    """
    手工测试入口：
      - 调用 get_raw_adj_factors_bs 拉取指定股票的复权因子
      - 打印 DataFrame 基本信息和前几行
    """
    # ===== 1. 配置测试参数 =====
    # symbol 为 A 股代码（不带前缀），且在 Baostock 中存在。
    # 与 symbol_index 无强依赖（baostock_adapter 内部只用 prefix_symbol_with_market，
    # 若你尚未同步 symbol_index，也可以临时注释掉该调用再测 HTTP 连接本身）。
    symbol = "300300"  # 示例：浦发银行
    start_date = "1990-01-01"
    end_date = "2025-12-31"

    print("=" * 80)
    print(f"测试 Baostock 复权因子: symbol={symbol}, {start_date} → {end_date}")
    print("=" * 80)

    # ===== 2. 实际调用适配器 =====
    try:
        df = await get_raw_adj_factors_bs(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        print(f"[ERROR] 调用 get_raw_adj_factors_bs 失败: {e}")
        return

    # ===== 3. 打印结果概览 =====
    if df is None or df.empty:
        print("[RESULT] 返回为空 DataFrame（无数据或拉取失败）")
        return

    print(f"[RESULT] 成功获取 {len(df)} 条记录")
    print("\n[Columns] 列名：", list(df.columns))
    print("\n[Head] 前 5 行：")
    print(df.head())

    # 核心列简单检查
    required_cols = [
        "code",
        "dividOperateDate",
        "foreAdjustFactor",
        "backAdjustFactor",
        "adjustFactor",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"\n[WARN] 缺少预期列：{missing}")
    else:
        print("\n[OK] 所有预期列均存在")

    print("\n[Sample] 关键列示例：")
    print(
        df[["code", "dividOperateDate", "foreAdjustFactor", "backAdjustFactor"]]
        .head()
        .to_string(index=False)
    )


if __name__ == "__main__":
    # 以异步方式运行测试
    asyncio.run(main())