# szse_excel_demo.py
# ==============================
# 说明：
#   - 这是一个独立测试脚本，用于验证从深交所直接下载全量 Excel 文件的方案。
#   - 解决了 JSON 接口强制分页 20 条的限制。
#   - 运行后会请求下载，成功后提示用户输入保存路径。
# ==============================

import requests
import random
import os
import pandas as pd
import io

# 导入项目内的爬虫工具（如果你在项目根目录下运行，确保 python path 正确）
# 如果报错找不到模块，可以将下面的导入改为硬编码的 headers
try:
    from backend.utils.spider_toolkit import (
        pick_user_agent,
        pick_accept_language,
        pick_connection,
    )
    HAS_TOOLKIT = True
except ImportError:
    HAS_TOOLKIT = False

# 1. 基础 URL
BASE_URL = "https://www.szse.cn/api/report/ShowReport"

def get_headers():
    """构造请求头"""
    if HAS_TOOLKIT:
        ua = pick_user_agent()
        lang = pick_accept_language()
        conn = pick_connection()
    else:
        # 兜底硬编码
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        lang = "zh-CN,zh;q=0.9"
        conn = "keep-alive"

    return {
        "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Host": "www.szse.cn",
        "User-Agent": ua,
        "Accept-Language": lang,
        "Connection": conn,
    }

def fetch_and_save_excel():
    """
    拉取深交所全量股票列表 (Excel流)
    """
    print(f"🚀 正在连接深交所接口: {BASE_URL}")
    
    # 构造参数：关键是 SHOWTYPE=xlsx
    params = {
        "SHOWTYPE": "xlsx",      # <--- 核心：请求 Excel 文件，绕过 JSON 分页限制
        "CATALOGID": "1110",     # 1110=股票列表, 1105=基金列表, 1812_zs=指数列表
        "TABKEY": "tab2",
        "random": str(random.random()),
    }
    
    headers = get_headers()
    
    print(f"📋 请求参数: {params}")
    
    try:
        # 发起请求（stream=True 适合大文件，虽然这个文件通常只有几百KB到几MB）
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        
        # 简单的内容类型检查
        content_type = resp.headers.get('Content-Type', '')
        print(f"📡 响应状态: {resp.status_code}, 类型: {content_type}, 大小: {len(resp.content)/1024:.2f} KB")
        
        if b"html" in resp.content[:100] or b"{" in resp.content[:10]:
            print("❌ 警告：响应内容看起来像 HTML 或 JSON，可能不是 Excel 文件！反爬虫可能触发了。")
            print(f"内容预览: {resp.text[:200]}")
            return

        # --- 交互式保存 ---
        print("\n✅ 数据拉取成功（二进制流）。")
        default_name = "szse_stocks_full.xlsx"
        default_path = os.path.join(os.getcwd(), default_name)
        
        print(f"请输入保存路径 (直接回车默认为: {default_path})")
        user_path = input("👉 保存路径: ").strip()
        
        save_path = user_path if user_path else default_path
        
        # 确保目录存在
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        # 写入文件
        with open(save_path, "wb") as f:
            f.write(resp.content)
            
        print(f"\n💾 文件已保存至: {save_path}")
        
        # --- 验证数据量 ---
        print("\n🔍 正在读取 Excel 验证行数...")
        try:
            # 读取 Excel，强制把代码列转为字符串，防止 000001 变成 1
            df = pd.read_excel(save_path, dtype={'A股代码': str, '代码': str})
            
            print(f"📊 数据统计:")
            print(f"   - 总行数: {len(df)}")
            print(f"   - 列清单: {list(df.columns)}")
            print(f"\n   - 前 3 行预览:")
            print(df.head(3).to_string())
            
            if len(df) > 50:
                print(f"\n🎉 验证成功！获取到了 {len(df)} 条数据，突破了 20 条限制。")
            else:
                print(f"\n⚠️ 警告：数据量依然很少 ({len(df)} 条)，请检查接口行为。")
                
        except Exception as e:
            print(f"❌ Excel 读取失败 (可能是格式不兼容或未安装 openpyxl): {e}")

    except Exception as e:
        print(f"❌ 请求发生异常: {e}")

if __name__ == "__main__":
    fetch_and_save_excel()