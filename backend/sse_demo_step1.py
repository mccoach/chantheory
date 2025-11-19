import requests
import json

# 1. 基础 URL（就是你在浏览器看到的那个 .do 地址）
BASE_URL = "https://query.sse.com.cn/sseQuery/commonQuery.do"

# 2. 请求参数（先按照你抓到的原样写出来）
params = {
    "jsonCallBack": "symbol_index_sh",  # JSONP 回调名，自主命名
    "STOCK_TYPE": "",  # 1 = 主板A股, 2 = 主板B股, 8 = 科创板, 留空 = 不限
    "REG_PROVINCE": "",  # 所属地区, 使用六位省份编码（同身份证号前两位）
    "CSRC_CODE": "",
    "STOCK_CODE": "",
    "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
    "COMPANY_STATUS": "1",  # 公司状态
    "type": "inParams",
    "isPagination": "false",  # 是否分页, true/false
    "pageHelp.cacheSize": "1",
    "pageHelp.beginPage": "1",
    "pageHelp.pageSize": "5000",  # 每页25条，先保持一致
    "pageHelp.pageNo": "1",
    "pageHelp.endPage": "1",
    "_": "1763449326460",  # 时间戳参数，可有可无
}

# 3. 必要的请求头（最关键的是 Referer 和 User-Agent）
headers = {
    "Referer":
    "https://www.sse.com.cn/assortment/stock/list/share/",  # 可以用你浏览器上真正的列表页
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36",
    "Accept":
    "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With":
    "XMLHttpRequest",
}


def fetch_page():
    # 4. 发请求（就是浏览器干的那件事）
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    text = resp.text
    print("原始响应前 200 字符：")
    print(text[:200])

    # 5. 解析 JSONP：去掉前后包裹的回调函数
    # 形如：jsonpCallback29375036({...json...});
    prefix = params["jsonCallBack"] + "("
    suffix = ");"

    if text.startswith(prefix) and text.endswith(suffix):
        json_str = text[len(prefix):-len(suffix)]
    else:
        # 兜底方式：粗暴地从第一个 "(" 到最后一个 ")" 之间截取
        first_paren = text.find("(")
        last_paren = text.rfind(")")
        json_str = text[first_paren + 1:last_paren]

    data = json.loads(json_str)

    # 6. 打印一下顶层结构，确认拿到了什么
    print("\n解析后的顶层键：", list(data.keys()))

    # 一般情况下数据会在 data["result"] 或 data["pageHelp"]["data"] 里
    # 你可以打印出来看一下
    if "result" in data:
        rows = data["result"]
    elif "pageHelp" in data and "data" in data["pageHelp"]:
        rows = data["pageHelp"]["data"]
    else:
        rows = None

    if not rows:
        print("没有找到 result 或 pageHelp.data，返回的结构需要再看一眼。")
    else:
        print(f"\n一共获取到 {len(rows)} 条记录")
        print("第一条记录：")
        print(rows[0])


if __name__ == "__main__":
    fetch_page()
