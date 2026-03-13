# E:\AppProject\ChanTheory\scripts\test_listing_tdx.py
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ========= 关键修复：把项目根目录加入模块搜索路径 =========
# 这样无论你在 VSCode 里从 scripts/ 用 F5 跑，还是命令行跑，都能 import backend
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../ChanTheory
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ======================================================


async def main() -> None:
    # 你已把函数名改为 get_security_list_pytdx
    from backend.datasource.providers.pytdx_adapter.listing_tdx import get_security_list_pytdx

    # 输出文件：默认放到项目 var/ 目录（你也可以改成绝对路径）
    out_path = (PROJECT_ROOT / "var" / "pytdx_security_list1.txt").resolve()

    # 你要测试更多 market，就改 markets=[0,1,2,...]
    df = await get_security_list_pytdx(
        markets=[3],
        page_size=1000,
        dump_txt=True,
        dump_txt_path=str(out_path),
        connect_timeout=5.0,
    )

    print("=== pytdx security list fetched ===")
    print("rows:", 0 if df is None else len(df))
    if df is not None:
        print("columns:", list(df.columns))

        print("\n--- head(5) ---")
        print(df.head(5).to_string(index=False))

        print("\n--- tail(5) ---")
        print(df.tail(5).to_string(index=False))

        # 小白友好：简单看看是否存在同 code 不同 market 的情况
        if "market" in df.columns and "code" in df.columns:
            dup_code = df.groupby("code")["market"].nunique()
            cross_market_same_code = int((dup_code > 1).sum())
            print("\n[check] codes appearing in multiple markets:",
                  cross_market_same_code)

    print("\ndumped_to:", str(out_path))


if __name__ == "__main__":
    asyncio.run(main())
