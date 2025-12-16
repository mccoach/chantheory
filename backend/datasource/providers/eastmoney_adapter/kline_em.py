# backend/datasource/providers/eastmoney_adapter/kline_em.py
# ==============================
# 说明：东方财富行情适配器 - 股票K线原子接口（V1.6 · 预热 URL 由调用方显式指定版）
#
# 职责：
#   - 封装对东财 push2his K 线接口的 HTTP 调用；
#   - 支持 A 股股票 8 种频率：
#       * 1 分钟：  freq='1m'  → klt=1
#       * 5 分钟：  freq='5m'  → klt=5
#       * 15 分钟： freq='15m' → klt=15
#       * 30 分钟： freq='30m' → klt=30
#       * 60 分钟： freq='60m' → klt=60
#       * 日线：    freq='1d'  → klt=101
#       * 周线：    freq='1w'  → klt=102
#       * 月线：    freq='1M'  → klt=103
#   - **默认拉“不复权”数据（fqt=0），也支持通过参数指定前复权/后复权（fqt=1/2）**，
#     以满足你对“默认不复权，但可选复权模式”的需求；
#   - 输出结构化的 pandas.DataFrame，不做业务级字段重命名（由 normalizer 层处理）。
#
# 关键约束：
#   - **所有“市场 / 标的类型”等基础信息，一律从本地 symbol_index 表获取；**
#   - 不再通过代码前缀猜测市场，symbol_index 是市场信息的唯一上游。
#
# 新版要点（V1.4）：
#   - 使用 backend.utils.http_sessions 进行站点级 Session 预热与 AsyncClient 复用：
#       * 预热 https://www.eastmoney.com/ 获取真实 Cookie；
#       * 每站点每天只选一次 UA；
#       * 业务请求的 headers 基于 client.headers（即“预热时的指纹”），只在必要字段上覆盖；
#   - 函数名已改为 get_kline_em（原 get_stock_kline_em）；
#   - 删除业务层手写 Cookie，完全依赖 AsyncClient 的 cookie jar；
#   - lmt 固定写死为 "50000"，以尽可能获取最全量数据（你已验证该值可用）。
#
# 设计风格：
#   - 完全对齐 sse_adapter / szse_adapter / baostock_adapter：
#       * 函数为 async def；
#       * 使用 limit_async_network_io 做全局异步限流；
#       * 使用 async_retry_call 提供指数退避重试；
#       * 使用 spider_toolkit 生成 UA / Accept-Language / Connection / sec-ch-ua；
#       * 使用 strip_jsonp 解析 JSON/JSONP 外壳（本文件针对东财增加一层更强容错解析 _strip_em_jsonp）；
#   - 单一职责：
#       * 不写 DB、不做复权/换手率语义解释、不做 K 线补齐；
#       * 仅保证“把远端 klines 字符串 → 标准 DataFrame”。
#
# 远程接口说明（基于你提供的抓包）：
#
#   基础 URL：
#     https://push2his.eastmoney.com/api/qt/stock/kline/get
#
#   关键 Query 参数：
#     - secid:   股票标识，格式为 "{market}.{code}"：
#                  * 上交所 A 股：market=1 → "1.600519"
#                  * 深交所 A 股：market=0 → "0.000001"
#                **本适配器不再通过代码首位猜测市场，统一从 symbol_index.market 获取：**
#                  * symbol_index.market='SH' → secid='1.600519'
#                  * symbol_index.market='SZ' → secid='0.000001'
#                若 symbol_index 中没有该 symbol 或 market 为空/非 SH/SZ，将抛出 ValueError，
#                调用方应先完成标的列表同步。
#
#     - klt:     K 线类型：
#                  1   → 1 分钟    (freq='1m')
#                  5   → 5 分钟    (freq='5m')
#                  15  → 15 分钟   (freq='15m')
#                  30  → 30 分钟   (freq='30m')
#                  60  → 60 分钟   (freq='60m')
#                  101 → 日 K      (freq='1d')
#                  102 → 周 K      (freq='1w')
#                  103 → 月 K      (freq='1M')
#
#     - fqt:     复权方式：
#                  0 → 不复权（默认）
#                  1 → 前复权
#                  2 → 后复权
#                **本适配器通过 get_kline_em 的 fqt 参数显式控制该值，
#                  默认仍为不复权（fqt=0），兼容你原有“不复权为主”的模式。**
#
#     - end:     结束日期，格式 "YYYYMMDD"（示例：20251202）
#                语义：取到 end 当日为止的历史数据。
#                若调用方不传，默认使用今日（Asia/Shanghai）。
#
#     - lmt:     返回条数上限（limit），典型值 210 / 1000 等。
#
#     - fields1: 静态字段选择，本适配器沿用你的抓包值：
#                  "f1,f2,f3,f4,f5,f6"
#                （与 klines 无直接关系，可视为固定模板参数）
#
#     - fields2: K 线字段选择，本适配器沿用你的抓包值：
#                  "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
#
#     - cb:      JSONP 回调名（例如 "quote_jp1"），
#                本适配器使用 spider_toolkit.generate_jsonp_callback()
#                自动生成唯一回调名。
#
#   响应示例（JSONP 外壳）：
#
#     quote_jp1({
#       "rc": 0,
#       "rt": 17,
#       "svr": 177617930,
#       "lt": 1,
#       "full": 0,
#       "dlmkts": "",
#       "data": {
#           "code": "600519",
#           "market": 1,
#           "name": "贵州茅台",
#           "decimal": 2,
#           "dktotal": 5813,
#           "preKPrice": 1427.15,
#           "klines": [
#             "2025-01-20,1433.40,1447.20,1462.19,1432.40,31410,4647626351.00,2.09,1.40,20.05,0.25",
#             ...
#           ]
#       }
#     });
#
#   klines 每一项的字段含义（fields2 = f51~f61）：
#
#     日 / 周 / 月 K（示例：2025-01-20,1433.40,1447.20,1462.19,1432.40,...）：
#       f51: 日期          → "YYYY-MM-DD"
#       f52: 开盘价        → float
#       f53: 收盘价        → float
#       f54: 最高价        → float
#       f55: 最低价        → float
#       f56: 成交量        → float，单位：手（本适配器会 ×100 转为股）
#       f57: 成交额        → float，单位：元
#       f58: 振幅          → float，单位：%
#       f59: 涨跌幅        → float，单位：%
#       f60: 涨跌额        → float，单位：元
#       f61: 换手率        → float，单位：%
#
#     分钟 K（示例：2025-12-02 09:31,1448.00,1449.55,1451.92,1446.00,...）：
#       f51: 时间戳        → "YYYY-MM-DD HH:MM"
#       f52~f61: 含义与上面完全一致。
#
#   输出 DataFrame 字段：
#
#     - 对于日/周/月线：
#         'date'        : str  (YYYY-MM-DD)
#         'open'        : float
#         'close'       : float
#         'high'        : float
#         'low'         : float
#         'volume'      : float (单位：股，已从“手”乘以 100)
#         'amount'      : float (单位：元)
#         'amplitude'   : float (%)
#         'pct_change'  : float (%)
#         'change'      : float (元)
#         'turnover'    : float (%)
#
#     - 对于分钟线（1m/5m/15m/30m/60m）：
#         'time'        : str  (YYYY-MM-DD HH:MM)
#         其他列同上。
#
#   与 normalizer 的契合点：
#     - normalizer.normalize_bars_df 的字段映射支持：
#         * 'date' / 'time' → 时间列；
#         * 'open'/'high'/'low'/'close' → 价格列；
#         * 'volume' → 成交量；
#         * 'amount' → 成交额；
#         * 'turnover' → 换手率（随后会自动除以 100 转为比率）。
#     - 因此本适配器产出的 DataFrame 可以直接送入 normalize_bars_df，
#       获得统一的 ts/open/high/low/close/volume/... 结构。
#
# 关键更新：
#   - 使用 utils.spider_toolkit.strip_jsonp(text) 做统一 JSON/JSONP 脱壳，
#     不再依赖 callback 名，也不再需要本地的 _strip_em_jsonp。
#   - 请求头 Accept-Encoding 去掉 br/zstd，仅保留 "gzip, deflate"，
#     避免在环境未安装 brotli/zstd 时拿到无法自动解压的压缩流。
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional

import pandas as pd
import httpx
import json

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger
from backend.utils.time import today_ymd, parse_yyyymmdd
from backend.utils.common import get_symbol_market_from_db

from backend.utils.spider_toolkit import (
    generate_jsonp_callback,
    generate_cache_buster,
    strip_jsonp,
)

from backend.utils.http_sessions import (
    get_site_client, )

_LOG = get_logger("eastmoney_adapter.kline")

# 预热 URL：调用方在此显式指定（已由你前期测试验证）
# EM_PREHEAT_URL = "https://quote.eastmoney.com/"
EM_PREHEAT_URL = "https://www.eastmoney.com/"

# ==============================================================================
# 内部辅助函数
# ==============================================================================


def _detect_em_market(symbol: str) -> str:
    """
    通过 symbol_index.market 判定东方财富 secid 的 market 标识。

    规则：
      - 从本地 DB 的 symbol_index 表读取 market 字段：
          * 'SH' → 东方财富 market='1'
          * 'SZ' → 东方财富 market='0'
      - 若 symbol_index 中无此标的，或者 market 为空/非 SH/SZ：
          → 抛出 ValueError，提示“请先完成标的列表同步”。

    说明：
      - 遵循你的约束：**市场/标的类型等基础信息只信任本地 symbol_index**，
        禁止根据代码前缀进行任何猜测。
    """
    s = (symbol or "").strip()
    if not s:
        raise ValueError("EastMoney kline: symbol is empty")

    market = get_symbol_market_from_db(s)
    if not market:
        raise ValueError(
            f"EastMoney kline: symbol '{s}' not found in symbol_index "
            f"或其 market 字段为空，请先完成标的列表同步（symbol_index）。")

    m = str(market).strip().upper()
    if m == "SH":
        return "1"
    if m == "SZ":
        return "0"

    raise ValueError(
        f"EastMoney kline: unsupported market='{market}' for symbol='{s}'. "
        f"当前仅支持 A 股沪深市场（SH/SZ）。")


def _map_freq_to_klt(freq: str) -> int:
    """
    将系统内频率字符串映射为东财 klt 参数。

    支持的输入（不区分大小写）：
      - '1m' / '1f'   → 1
      - '5m' / '5f'   → 5
      - '15m' / '15f' → 15
      - '30m' / '30f' → 30
      - '60m' / '60f' → 60
      - '1d'          → 101
      - '1w'          → 102
      - '1M'          → 103

    若 freq 不在上述范围内，将抛出 ValueError。
    """
    f = (freq or "").strip()
    f_lower = f.lower()

    minute_map = {
        "1m": 1,
        "1f": 1,
        "5m": 5,
        "5f": 5,
        "15m": 15,
        "15f": 15,
        "30m": 30,
        "30f": 30,
        "60m": 60,
        "60f": 60,
    }
    if f_lower in minute_map:
        return minute_map[f_lower]

    if f_lower == "1d":
        return 101
    if f_lower == "1w":
        return 102
    if f == "1M":
        return 103

    raise ValueError(f"Unsupported freq for EastMoney kline: {freq}")


def _parse_klines_to_df(klines: List[str]) -> pd.DataFrame:
    """
    将 data.klines 列表解析为 DataFrame。

    输入：
      - klines: 每个元素为形如
          日/周/月线： "2025-01-20,1433.40,1447.20,1462.19,1432.40,31410,..."
          分钟线：     "2025-12-02 09:31,1448.00,1449.55,1451.92,1446.00,858,..."

    输出：
      - DataFrame，列：
          * 对于日期串（无空格）：'date', open, close, high, low, volume, ...
          * 对于时间串（含空格）：'time', open, close, high, low, volume, ...

    字段含义（对应 fields2 = f51~f61）：
      - f51: date/time 字符串
      - f52: open
      - f53: close
      - f54: high
      - f55: low
      - f56: volume (手) —— 此处会 ×100 转为“股”
      - f57: amount (元)
      - f58: amplitude (%)
      - f59: pct_change (%)
      - f60: change (元)
      - f61: turnover (%)
    """
    records: List[Dict[str, Any]] = []

    for raw in klines or []:
        try:
            parts = str(raw).split(",")
            if len(parts) < 6:
                continue

            ts_str = parts[0].strip()
            has_time = " " in ts_str

            rec: Dict[str, Any] = {}
            if has_time:
                rec["time"] = ts_str
            else:
                rec["date"] = ts_str

            # 价格与成交
            rec["open"] = float(parts[1])
            rec["close"] = float(parts[2])
            rec["high"] = float(parts[3])
            rec["low"] = float(parts[4])

            # 成交量：远端单位为“手”，统一转为“股”
            vol = float(parts[5])
            rec["volume"] = vol * 100.0  # 手 → 股

            # 成交额（元）
            rec["amount"] = float(parts[6])

            # 之后的字段可能缺失，需容错
            rec["amplitude"] = float(
                parts[7]) if len(parts) > 7 and parts[7] != "" else None
            rec["pct_change"] = float(
                parts[8]) if len(parts) > 8 and parts[8] != "" else None
            rec["change"] = float(
                parts[9]) if len(parts) > 9 and parts[9] != "" else None
            rec["turnover"] = float(
                parts[10]) if len(parts) > 10 and parts[10] != "" else None

            records.append(rec)
        except Exception:
            # 单行解析失败不应影响整体，直接跳过该行
            continue

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


# ==============================================================================
# 对外原子接口（重命名版）
# ==============================================================================


@limit_async_network_io
async def get_kline_em(
    symbol: str,
    freq: str,
    end: Optional[str] = None,
    fqt: int = 0,
) -> pd.DataFrame:
    """
    [A股股票 K 线 · 东财 push2his 接口 · 复权方式可选，默认不复权]

    设计用途：
      - 为“统一行情体系 / 缺口填补 / 替换不稳定 AkShare 接口”提供原子级弹药；
      - 暂不直接挂入 dispatcher.registry，先作为实验性数据源使用；
      - 默认只拉“不复权”数据（fqt=0），满足你对股票行情不复权的要求；
      - 通过 fqt 参数显式支持前复权/后复权模式：
          * fqt=0 → 不复权
          * fqt=1 → 前复权
          * fqt=2 → 后复权
      - **市场信息完全依赖 symbol_index.market，不再做任何代码推断。**

    参数：
      - symbol (str):
          * 股票代码，不带市场前缀，例如：
              '600519'（贵州茅台）
              '000001'（平安银行）
          * 本函数会从 symbol_index 表中读取该 symbol 的 market 字段：
              'SH' → secid='1.600519'
              'SZ' → secid='0.000001'
          * 若 symbol_index 中不存在该 symbol 或 market 非 SH/SZ，将抛出 ValueError。

      - freq (str):
          * 支持 8 种频率（不区分大小写）：
              '1m' / '1f'   → 1 分钟 K 线（klt=1）
              '5m' / '5f'   → 5 分钟 K 线（klt=5）
              '15m' / '15f' → 15 分钟 K 线（klt=15）
              '30m' / '30f' → 30 分钟 K 线（klt=30）
              '60m' / '60f' → 60 分钟 K 线（klt=60）
              '1d'          → 日 K（klt=101）
              '1w'          → 周 K（klt=102）
              '1M'          → 月 K（klt=103）
          * 若传入其他字符串，将抛出 ValueError。

      - end (str | None):
          * 结束日期，格式建议 'YYYYMMDD'，例如 '20251202'；
          * 若为 None，则默认使用今日（Asia/Shanghai 时区）；
          * 内部使用 parse_yyyymmdd 进行宽松解析：
              - '2025-12-02' / '2025/12/02' / 20251202 等均可。

      - fqt (int):
          * 复权方式：
              0 → 不复权（默认）
              1 → 前复权
              2 → 后复权
          * 若传入其他数值，将抛出 ValueError 以避免产生语义不明的请求。

    返回：
      - pandas.DataFrame：
          * 对于日/周/月线：
              列：'date','open','close','high','low','volume','amount',
                  'amplitude','pct_change','change','turnover'
          * 对于分钟线：
              列：'time','open','close','high','low','volume','amount',
                  'amplitude','pct_change','change','turnover'

      - 若请求 / 解析失败，将抛出异常（由 async_retry_call 统筹重试）；
      - 若远端返回空 klines，则返回空 DataFrame。

    其他关键约束：
      - 本函数不做任何“复权因子合成/拆分”、“前后复权切换”等逻辑：
          * 对于 fqt=0/1/2，仅将其透明传递给东财接口；
          * 复权相关更细致工作交由 Baostock 因子 + normalizer 层统一实现。
      - 本函数不做缺口判断，也不写 DB：
          * 仅作为纯数据源，由上游同步执行器 / 业务服务控制调用频率。
      - 单次请求的 lmt 固定为 50000，以尽可能获取全量数据。
    """
    sym = (symbol or "").strip()
    if not sym:
        _LOG.warning("[东财K线] 空 symbol，直接返回空 DataFrame")
        return pd.DataFrame()

    # 解析市场 & klt
    try:
        market_flag = _detect_em_market(sym)
        klt = _map_freq_to_klt(freq)
    except ValueError as e:
        _LOG.error(f"[东财K线] 参数错误: {e}")
        raise

    # 解析 fqt（复权方式）
    try:
        fqt_int = int(fqt)
    except Exception:
        raise ValueError(f"EastMoney kline: fqt must be int (0/1/2), got {fqt!r}")
    if fqt_int not in (0, 1, 2):
        raise ValueError(f"EastMoney kline: unsupported fqt={fqt_int}, expected 0/1/2")

    # 结束日期：默认今日
    if end is None:
        end_ymd = today_ymd()
    else:
        end_ymd = parse_yyyymmdd(end)
    end_str = f"{end_ymd:08d}"

    # 构造 secid
    secid = f"{market_flag}.{sym}"

    base_url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    # ===== 步骤1：生成动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("quote_jp")
    cache_buster = generate_cache_buster()

    # ===== 步骤2：构造查询参数 =====
    params: Dict[str, Any] = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",  # 模板 ut
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": str(klt),
        "fqt": str(fqt_int),  # 复权方式：0/1/2 由参数决定
        "end": end_str,  # 结束日期（YYYYMMDD）
        "lmt": "50000",  # 固定为 50000，尽量获取全量
        "cb": callback_name,  # JSONP 回调名
        "_": cache_buster,  # 防缓存
    }

    # 构造 Referer：如 https://quote.eastmoney.com/concept/sh600519.html
    try:
        if sym.startswith("6"):
            referer_code = f"sh{sym}"
        else:
            referer_code = f"sz{sym}"
    except Exception:
        referer_code = sym

    _LOG.info(
        "[东财K线] 开始拉取股票K线",
        extra={
            "symbol": sym,
            "secid": secid,
            "freq": freq,
            "klt": klt,
            "end": end_str,
            "limit": params["lmt"],
            "fqt": params["fqt"],
        },
    )

    # ===== 步骤4：执行请求（带 async_retry_call 重试）=====
    async def _do_request() -> pd.DataFrame:
        # 使用我们显式指定的预热 URL 取得站点 client
        client = await get_site_client(EM_PREHEAT_URL, force_preheat=False)

        # 从 client.headers 拿默认头作为基础
        try:
            client_default_headers = dict(client.headers)
        except Exception:
            client_default_headers = {}

        headers: Dict[str, str] = dict(client_default_headers)

        headers.update({
            "Referer":
            f"https://quote.eastmoney.com/concept/{referer_code}.html",
            "Host": "push2his.eastmoney.com",
            "Sec-Fetch-Dest": "script",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-site",

            # 强制保证 Accept-Encoding 不包含 br/zstd
            "Accept-Encoding": "gzip, deflate",
        })

        # 打印本次请求要发送的头和当前 Cookie，用于和旧版对比
        try:
            cookie_list = [str(c) for c in client.cookies.jar]
        except Exception:
            cookie_list = []

        detail = {
            "symbol": sym,
            "freq": freq,
            "client_default_headers": client_default_headers,
            "request_headers": headers,
            "cookies_in_client": cookie_list,
        }
        # 修改：调试级别改为 DEBUG，避免在 INFO 级别大量输出头/Cookie 细节
        _LOG.debug(
            "[东财K线] 调试：请求头与 Cookie 对比 detail=%s",
            json.dumps(detail, ensure_ascii=False),
        )

        resp = await client.get(base_url,
                                params=params,
                                headers=headers,
                                timeout=10.0)
        resp.raise_for_status()

        raw_text = resp.text

        # 统一 JSON/JSONP 脱壳
        data = strip_jsonp(raw_text)

        # 验证结构
        if not isinstance(data, dict) or "data" not in data:
            _LOG.warning(
                "[东财K线] 响应结构异常",
                extra={
                    "symbol": sym,
                    "freq": freq,
                    "keys":
                    list(data.keys()) if isinstance(data, dict) else None,
                    "text_preview": raw_text[:300],
                },
            )
            return pd.DataFrame()

        payload = data.get("data") or {}
        klines_raw = payload.get("klines") or []

        if not klines_raw:
            _LOG.warning(
                "[东财K线] 无 klines 数据",
                extra={
                    "symbol": sym,
                    "freq": freq,
                    "code": payload.get("code"),
                    "name": payload.get("name"),
                    "text_preview": raw_text[:300],
                },
            )
            return pd.DataFrame()

        df = _parse_klines_to_df(klines_raw)

        _LOG.info(
            "[东财K线] 拉取成功",
            extra={
                "symbol": sym,
                "freq": freq,
                "rows": len(df),
                "code": payload.get("code"),
                "stock_name": payload.get("name"),
            },
        )

        return df

    df_result = await async_retry_call(_do_request)

    # 保证返回 DataFrame（失败或空数据时为 empty DataFrame）
    return df_result if isinstance(df_result, pd.DataFrame) else pd.DataFrame()
