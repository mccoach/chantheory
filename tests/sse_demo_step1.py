# sse_fund_demo_step1.py
# ==============================
# 说明：
#   - 这是一个最小可运行的测试脚本，用于验证上交所 FUND_LIST 接口是否能正常访问。
#   - 完全独立，不依赖你现有项目代码，只需要安装 requests 即可：
#       pip install requests
#   - 后续如果测试成功，我们再把逻辑迁移到 sse_official_adapter.py 里，做成
#       async def get_fund_list_sh_official(...)
# ==============================

import time
import json
import requests
import random
from typing import Dict, Any, List

# 导入爬虫工具包
from backend.utils.spider_toolkit import (
    pick_user_agent,  # 随机选择 UA
    pick_accept_language,  # 随机选择语言
    pick_connection,  # 随机选择连接方式
    generate_jsonp_callback,  # 生成唯一回调名
    generate_cache_buster,  # 生成时间戳
    generate_sec_ch_ua,  #生成 sec-ch-ua 头
    strip_jsonp,  # 解析 JSONP
)

# 1. 基础 URL（基金列表接口）
base_url = "https://query.sse.com.cn/sseQuery/commonQuery.do"

# ===== 步骤1：生成动态参数（防缓存/防冲突）=====
callback_name = generate_jsonp_callback("jsonpCallback")
timestamp = generate_cache_buster()

def build_params() -> dict:
    rand_value = str(random.random())

    params: Dict[str, str] = {
        # === 必填业务参数 ===
        "STOCK_TYPE": "",  # str ，股票类别过滤， (1=主板A股，2=主板B股，8=创业板，空=全部)
        "REG_PROVINCE": "",  # str ，省份过滤 (六位数字省份编码，空=全部)
        "CSRC_CODE": "",  # str ，证监会行业代码过滤 (空=全部)
        "STOCK_CODE": "",  # 股票代码过滤 (空=全部)
        "COMPANY_STATUS":
        "2,4,5,7,8",  # str ，公司状态过滤（以半角逗号分隔的状态码），"2,4,5,7,8"为官网默认设置，每个数字具体含义待确认，留空""会返回更多

        # === 上交所内部参数（固定值，来源：官网 JS） ===
        "sqlId":
        "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",  # （固定不变）上交所内部预设好的 SQL 模板 ID，指示服务器执行哪段预定义查询，保持现状不能随意修改
        "type":
        "inParams",  # （固定不变）上交所预设查询参数类型，配合 sqlId 使用，一般是和后端的 Query 组件强绑定的开关，预先在页面里的 JS 里写死，保持现状不能随意修改

        # === 分页参数 ===，
        "isPagination":
        "false",  # 是否开启分页，true/false，为 true 时，pageHelp.* 参数生效。为 false 时，直接返回全量，不受分页数量限制

        # 以下分页参数仅"isPagination": "true" 时生效，留存备用
        "pageHelp.cacheSize": "1",
        "pageHelp.beginPage": "1",  # str，开始页码
        "pageHelp.pageSize":
        "20000",  # str，单页返回条数，分页生效时，实测最大值为2000，即便设置超过2000的数值，返回数量也被限制为2000
        "pageHelp.pageNo": "1",  # str，当前页码
        "pageHelp.endPage": "1",  # str，结束页码

        # === 动态参数（防缓存）===
        "jsonCallBack":
        callback_name,  # JSONP 回调名，格式：jsonpCallback + 8位随机数，外部函数生成，直接调用
        "_": timestamp,  # 防缓存时间戳 (13位毫秒)，外部函数生成，直接调用
    }
    return params, callback_name


def build_headers() -> dict:

    # ===== 步骤3：生成通用参数（从 settings 池中随机选择）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()

    # ===== 步骤4：根据 UA 生成匹配的 sec-ch-ua =====
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers = {
        # === 个性化参数（接口专属，直接写死）===
        "Referer": "https://www.sse.com.cn/",  # 来源页（官网首页）
        "Accept": "*/*",  # 接受类型（与官网一致）
        "Host": "query.sse.com.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，固定值）===
        "Sec-Fetch-Dest": "script",  # JSONP 请求固定为 script
        "Sec-Fetch-Mode": "no-cors",  # 跨域模式
        "Sec-Fetch-Site": "same-site",  # 同站请求（sse.com.cn → query.sse.com.cn）

        # === 通用参数（从 settings 池中随机选择）===
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,

        # === 浏览器压缩支持（固定值）===
        "Accept-Encoding": "gzip, deflate, br, zstd",
    }

    # === 补充 sec-ch-ua 系列（仅 Chrome/Edge 携带）===
    if sec_ch_ua:  # Firefox 返回空字符串，不添加
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"  # 非移动设备
        headers["sec-ch-ua-platform"] = '"Windows"'  # 操作系统

    return headers


def strip_jsonp(text: str, callback: str) -> dict:
    """
    解析 JSONP：去掉前后的回调函数壳，返回 Python dict

    形如：
      fund_list_sh({...json...});
    """
    prefix = callback + "("
    suffix = ");"

    s = text.strip()

    if s.startswith(prefix) and s.endswith(suffix):
        json_str = s[len(prefix):-len(suffix)]
    else:
        # 非标准情况：粗暴从第一个 "(" 到最后一个 ")" 截取
        first_paren = s.find("(")
        last_paren = s.rfind(")")
        if first_paren >= 0 and last_paren > first_paren:
            json_str = s[first_paren + 1:last_paren]
        else:
            # 兜底：当成普通 JSON 解析
            json_str = s

    return json.loads(json_str)


def fetch_symbol_list():
    """
    拉取一组基金列表数据，并打印结构信息

    你可以尝试两组调用：
      1) 股票类等：
         fund_type="00",
         sub_class="01,02,03,04,06,08,09,31,32,33,34,35,36,37,38"

      2) 货币等：
         fund_type="10",
         sub_class="11,14,15"
    """
    params, rand_value = build_params()
    headers = build_headers()

    print("请求地址：", base_url)
    print("请求参数：", params)
    print("请求头：", headers)

    resp = requests.get(base_url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    print("\n原始响应前 200 字符：")
    print(resp.text[:200])

    data = strip_jsonp(resp.text, rand_value)

    print("\n解析后的顶层键：", list(data.keys()))

    # 参考上交所通用结构，数据可能在 pageHelp.data 或 pageHelp.content 或 result 里
    rows = None
    if isinstance(data, dict):
        page_help = data.get("pageHelp")
        if isinstance(page_help, dict):
            rows = page_help.get("data") or page_help.get("content")
        if rows is None and "result" in data:
            rows = data["result"]

    if not rows:
        print("没有找到 pageHelp.data / pageHelp.content / result，返回结构需要再检查。")
        return

    print(f"\n一共获取到 {len(rows)} 条记录")
    print("第一条记录：")
    print(rows[0])


if __name__ == "__main__":
    # 示例1：基金类型 00（多子类）
    print("====== 测试 ======")
    fetch_symbol_list()

    # 你也可以取消下面的注释，测试另一组 fundType=10
    # print("\n====== 测试：fundType=10, subClass=11,14,15 ======")
    # fetch_fund_list(
    #     fund_type="10",
    #     sub_class="11,14,15",
    # )
