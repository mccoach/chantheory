# tests/test_official_adapters.py
# ==============================
# 官方数据源适配器测试脚本
# 职责：
#   1. 调用 sse_adapter 和 szse_adapter 的所有接口
#   2. 验证返回数据格式（DataFrame）
#   3. 打印数据示例，确认字段解析正常
# ==============================

import asyncio
import sys
import os
import pandas as pd
from pathlib import Path

# 添加项目根目录到 path，确保能导入 backend 模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.datasource.providers.sse_adapter.listing_sse import (
    get_stock_list_sh_sse,
    get_fund_list_sh_sse,
    get_index_list_sh_sse
)
from backend.datasource.providers.szse_adapter.listing_szse import (
    get_stock_list_sz_szse,
    get_fund_list_sz_szse,
    get_index_list_sz_szse
)
from backend.utils.logger import init_logger

# 初始化日志（输出到控制台以便观察）
init_logger()

async def run_test(name: str, func):
    print(f"\n{'='*20} 测试: {name} {'='*20}")
    try:
        df = await func()
        if df is None:
            print(f"❌ 失败: 返回 None")
            return

        if df.empty:
            print(f"⚠️ 警告: 返回空 DataFrame")
        else:
            print(f"✅ 成功: 获取 {len(df)} 条记录")
            print(f"   列名: {list(df.columns)}")
            print(f"   示例数据 (前2行):")
            print(df.head(2).to_string())
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    print("🚀 开始测试官方数据源适配器...")
    
    # --- 上交所测试 ---
    print("\n>>> 上交所 (SSE) 接口测试")
    await run_test("上交所-股票列表", get_stock_list_sh_sse)
    await run_test("上交所-基金列表", get_fund_list_sh_sse)
    await run_test("上交所-指数列表", get_index_list_sh_sse)
    
    # --- 深交所测试 ---
    print("\n>>> 深交所 (SZSE) 接口测试")
    await run_test("深交所-股票列表", get_stock_list_sz_szse)
    await run_test("深交所-基金列表", get_fund_list_sz_szse)
    await run_test("深交所-指数列表", get_index_list_sz_szse)

    print("\n🏁 测试结束")

if __name__ == "__main__":
    # Windows 下 asyncio 策略调整（防止 EventLoop 关闭报错）
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())