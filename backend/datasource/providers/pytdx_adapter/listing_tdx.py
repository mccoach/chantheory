# backend/datasource/providers/pytdx_adapter/listing_tdx.py
# ==============================
# 说明：pytdx HQ 标的列表适配器（原子接口 · V1.3 · 使用 host_selector 模块）
#
# 职责：
#   - 仅封装对 pytdx HQ 的"证券列表/代码表"拉取：
#       * TdxHq_API.get_security_count(market)
#       * TdxHq_API.get_security_list(market, start)
#   - 协议强制分页：在本适配器内部完成分页拉取与合并
#   - 返回 pandas.DataFrame（不做业务级标准化/分类/过滤/入库）
#
# 关键点（按你的明确要求）：
#   - 服务器选优与 newhost.lst 同步由 host_selector 独立模块负责
#   - 连接顺序固定：top1 -> top2 -> top3（一次失败立刻降级，不重试）
#   - top3 全失败：触发一次强制重测（重新解析/测速），再按 top1..top3 尝试
#   - 若仍失败：抛异常（并已有 system.alert 让前端弹窗提示）
#   - 去重：仅按 (market, code) 去重
# ==============================

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.utils.async_limiter import limit_provider_network_io
from backend.utils.logger import get_logger
from backend.datasource.providers.pytdx_adapter.host_selector import ensure_top3

_LOG = get_logger("pytdx_adapter")

try:
    from pytdx.hq import TdxHq_API
except ImportError as e:
    raise ImportError(
        "pytdx library is required but not installed. "
        "Please install it via: pip install pytdx"
    ) from e


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _dump_txt_comma(df: pd.DataFrame, *, out_path: str) -> None:
    if df is None:
        return
    p = Path(out_path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, header=True, sep=",", encoding="utf-8")
    _LOG.info("[pytdx] dumped security list to txt: %s rows=%d", str(p), len(df))


def _fetch_one_market_sync(*, api: TdxHq_API, market: int, page_size: int) -> pd.DataFrame:
    total = api.get_security_count(int(market))
    try:
        total_n = int(total or 0)
    except Exception:
        total_n = 0

    if total_n <= 0:
        _LOG.warning("[pytdx] market=%s get_security_count returned %r", market, total)
        return pd.DataFrame()

    pages = (total_n + page_size - 1) // page_size
    skipped_pages = 0
    rows_all: List[Dict[str, Any]] = []

    for i in range(pages):
        start = i * page_size
        try:
            part = api.get_security_list(int(market), int(start)) or []
        except Exception as e:
            skipped_pages += 1
            _LOG.warning(
                "[pytdx] page fetch failed, skipping: market=%s start=%s error=%s(%s)",
                market, start, type(e).__name__, e,
            )
            continue

        if not isinstance(part, list):
            continue

        for item in part:
            if not isinstance(item, dict):
                continue
            r = dict(item)
            r["market"] = int(market)
            if "code" in r:
                r["code"] = _safe_str(r.get("code"))
            if "name" in r:
                r["name"] = _safe_str(r.get("name"))
            rows_all.append(r)

    if skipped_pages > 0:
        _LOG.warning("[pytdx] market=%s skipped_pages=%d/%d", market, skipped_pages, pages)

    if not rows_all:
        return pd.DataFrame()

    df = pd.DataFrame(rows_all)

    if "market" in df.columns and "code" in df.columns:
        df = df.drop_duplicates(subset=["market", "code"], keep="last")

    return df.reset_index(drop=True)


def _try_connect_one(ip: str, port: int, connect_timeout: float) -> Optional[TdxHq_API]:
    api = TdxHq_API(raise_exception=True)
    try:
        ok = api.connect(str(ip), int(port), time_out=float(connect_timeout))
        if not ok:
            return None
        return api
    except Exception:
        try:
            api.disconnect()
        except Exception:
            pass
        return None


@limit_provider_network_io("pytdx")
async def get_security_list_pytdx(
    *,
    markets: Optional[List[int]] = None,
    page_size: int = 1000,
    dump_txt: bool = False,
    dump_txt_path: str = "",
    connect_timeout: float = 5.0,
    ping_timeout: float = 1.0,
) -> pd.DataFrame:
    mks = markets if isinstance(markets, list) and markets else [0, 1]
    try:
        ps = max(1, int(page_size))
    except Exception:
        ps = 1000

    # 1) 获取 top3（若无则内部会触发同步/测速）
    top3, err = await asyncio.to_thread(ensure_top3, ping_timeout=float(ping_timeout), force_retest=False)
    if err or not top3:
        raise RuntimeError(f"tdx host selection failed: {err}")

    # 2) 固定 top1->top2->top3 尝试连接（一次失败立刻降级，不重试）
    api = None
    for h in top3:
        ip = h["ip"]
        port = h["port"]
        api = await asyncio.to_thread(_try_connect_one, ip, port, float(connect_timeout))
        if api is not None:
            _LOG.info("[pytdx] connected host=%s:%s", ip, port)
            break

    # 3) top3 全失败：强制重测一次（重新解析/测速）再试一轮
    if api is None:
        top3_2, err2 = await asyncio.to_thread(ensure_top3, ping_timeout=float(ping_timeout), force_retest=True)
        if err2 or not top3_2:
            raise RuntimeError(f"tdx host selection failed after retest: {err2}")

        for h in top3_2:
            ip = h["ip"]
            port = h["port"]
            api = await asyncio.to_thread(_try_connect_one, ip, port, float(connect_timeout))
            if api is not None:
                _LOG.info("[pytdx] connected host(after retest)=%s:%s", ip, port)
                break

    if api is None:
        raise RuntimeError("pytdx connect failed for top3 (after retest)")

    # 4) 拉取数据
    try:
        def _sync_run() -> pd.DataFrame:
            parts: List[pd.DataFrame] = []
            for mk in mks:
                parts.append(_fetch_one_market_sync(api=api, market=int(mk), page_size=ps))

            if not parts:
                return pd.DataFrame()

            df_all = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
            if df_all is None or df_all.empty:
                return pd.DataFrame()

            if "market" in df_all.columns and "code" in df_all.columns:
                df_all = df_all.drop_duplicates(subset=["market", "code"], keep="last")

            return df_all.reset_index(drop=True)

        df = await asyncio.to_thread(_sync_run)

    finally:
        try:
            api.disconnect()
        except Exception:
            pass

    # 5) 可选落地 txt
    if bool(dump_txt):
        path = (dump_txt_path or "").strip() or "var/pytdx_security_list.txt"
        await asyncio.to_thread(_dump_txt_comma, df, out_path=path)

    _LOG.info(
        "[pytdx] fetch done rows=%s columns=%s",
        len(df) if isinstance(df, pd.DataFrame) else None,
        list(df.columns) if isinstance(df, pd.DataFrame) else None,
    )

    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
