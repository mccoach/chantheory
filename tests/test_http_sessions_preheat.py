# tests/test_preheat_single_introspect.py
# ==============================
# 说明：单次预热 + 单次 API 调用 · 全量打印调试工具
#
# 使用方式：
#   1. 激活 venv，在项目根目录运行：
#        python tests/test_preheat_single_introspect.py
#   2. 按提示输入：
#        PREHEAT_URL: 预热页面（以 http/https 开头）
#        API_URL    : 接口完整地址（建议从浏览器 Network 复制，带上 ? 和参数）
#        REFERER    : （可选）指定本次 API 请求的 Referer，如果留空则不设置 Referer
#
# 程序会：
#   - 使用 spider_toolkit 生成一套“模拟浏览器”的基础头；
#   - 用同一个 AsyncClient 先请求 PREHEAT_URL，再请求 API_URL；
#   - 对每一步打印：
#       * 请求头（Request Headers）
#       * 响应状态码 + 响应头（Response Headers）
#       * 当前 Cookie Jar 中的 Cookie 列表（域名/名称/值）
#       * API 响应体前 500 字符（避免刷屏）
# ==============================

import asyncio
import sys
from urllib.parse import urlparse

import httpx

# 确保可以导入 backend 包
if "backend" not in sys.modules:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_sec_ch_ua,
)


def _validate_url(name: str, url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError(f"{name} 不能为空")
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        raise ValueError(f"{name} 必须以 http:// 或 https:// 开头：{url!r}")
    if not parsed.hostname:
        raise ValueError(f"{name} 缺少有效的 host：{url!r}")
    return url


async def run_once(preheat_url: str, api_url: str, referer: str | None) -> None:
    preheat_url = _validate_url("PREHEAT_URL", preheat_url)
    api_url = _validate_url("API_URL", api_url)

    # ===== 1. 构造“接近浏览器”的基础头 =====
    ua = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(ua)

    base_headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": accept_language,
        "Connection": connection,
        # 不要接受 br/zstd，避免环境不支持解压
        "Accept-Encoding": "gzip, deflate",
    }
    if sec_ch_ua:
        base_headers["sec-ch-ua"] = sec_ch_ua
        base_headers["sec-ch-ua-mobile"] = "?0"
        base_headers["sec-ch-ua-platform"] = '"Windows"'

    async with httpx.AsyncClient(timeout=10.0, headers=base_headers) as client:
        print("=============================================")
        print("Step 1: 预热请求")
        print(f"  PREHEAT_URL: {preheat_url}")

        # === 1.1 发起预热请求 ===
        try:
            resp_pre = await client.get(preheat_url)
        except Exception as e:
            print(f"  预热请求异常: {type(e).__name__}: {e}")
            return

        # === 1.2 打印预热请求头 ===
        print("\n  [预热] Request Headers:")
        try:
            req_headers_pre = dict(resp_pre.request.headers)
        except Exception:
            req_headers_pre = {}
        for k, v in req_headers_pre.items():
            print(f"    {k}: {v}")

        # === 1.3 打印预热响应头 ===
        print("\n  [预热] Response Status & Headers:")
        print(f"    Status: {resp_pre.status_code}")
        resp_headers_pre = dict(resp_pre.headers)
        for k, v in resp_headers_pre.items():
            print(f"    {k}: {v}")

        # === 1.4 打印当前 Cookie Jar ===
        print("\n  [预热] Cookies in client jar AFTER preheat:")
        jar_cookies = list(client.cookies.jar)
        if not jar_cookies:
            print("    (empty)")
        else:
            for c in jar_cookies:
                try:
                    dom = getattr(c, "domain", None)
                    name = getattr(c, "name", None)
                    value = getattr(c, "value", None)
                    print(f"    domain={dom!r}, name={name!r}, value={value!r}")
                except Exception:
                    print("   ", c)

        # ===== 2. API 请求 =====
        print("\n=============================================")
        print("Step 2: API 请求")
        print(f"  API_URL: {api_url}")
        if referer:
            print(f"  使用 Referer: {referer}")
        else:
            print("  不设置 Referer（可在下次测试中尝试添加）")

        # === 2.1 构造本次 API 请求头（在 base_headers 基础上可选加入 Referer）===
        api_headers = dict(client.headers)
        api_headers.setdefault("Accept", "*/*")
        # 再次确保不出现 br/zstd
        api_headers["Accept-Encoding"] = "gzip, deflate"
        if referer:
            api_headers["Referer"] = referer

        # === 2.2 发起 API 请求 ===
        try:
            resp_api = await client.get(api_url, headers=api_headers)
        except Exception as e:
            print(f"  API 请求异常: {type(e).__name__}: {e}")
            return

        # === 2.3 打印 API 请求头 ===
        print("\n  [API] Request Headers:")
        req_headers_api = dict(resp_api.request.headers)
        for k, v in req_headers_api.items():
            print(f"    {k}: {v}")

        # === 2.4 打印 API 响应头 ===
        print("\n  [API] Response Status & Headers:")
        print(f"    Status: {resp_api.status_code}")
        resp_headers_api = dict(resp_api.headers)
        for k, v in resp_headers_api.items():
            print(f"    {k}: {v}")

        # === 2.5 打印响应体前 500 字符（避免刷屏）===
        print("\n  [API] Response Body (前 500 字符，可能被截断):")
        text = resp_api.text
        preview = text[:500]
        print("    ", preview.replace("\n", "\\n") + ("..." if len(text) > 500 else ""))

        print("\n=============================================")
        print("一次预热 + 一次 API 调用已完成，你可以根据以上输出，")
        print("前后更换 PREHEAT_URL / REFERER / UA 等做对比，自己观察哪一项变化影响最大。")
        print("=============================================")


if __name__ == "__main__":
    print("=== 单次预热 + 单次 API 调用 · 全量打印工具 ===")
    print("提示：")
    print("  - PREHEAT_URL：你想作为预热的页面（必须以 http:// 或 https:// 开头）")
    print("  - API_URL    ：你实际要调用的接口完整地址（建议从浏览器 Network 复制，带上 ? 和参数）")
    print("  - REFERER    ：可选；若你在浏览器抓包中看到接口有明确 Referer，这里也填同一个。")
    print()

    try:
        preheat_url = input("请输入 PREHEAT_URL (预热地址): ").strip()
        api_url = input("请输入 API_URL (接口地址): ").strip()
        referer = input("请输入 REFERER (可空，直接回车跳过): ").strip() or None
    except KeyboardInterrupt:
        print("\n中止。")
        sys.exit(0)

    asyncio.run(run_once(preheat_url, api_url, referer))