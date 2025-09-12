# backend/routers/symbols.py
# ==============================
# 说明：符号索引路由（精简版）
# 仅聚焦三类：A / ETF / LOF
# - 类别与顺序来自 config.json 的 symbol_index_categories（仅允许 A/ETF/LOF）
# - 各类别实现“主接口 + 后备接口”加载，并归一为 (symbol,name,market,type)
# - 合并按“类别优先级”覆盖（A > ETF > LOF），symbol 为键
# - 仅 UPSERT（不删除），空结果跳过
# - 快照摘要：by_type、by_type_market 与 delta_by_type（total/new/updated/untouched）
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 Python 3.8+）

# 第三方
from fastapi import APIRouter, Query, Request  # FastAPI 路由/查询参数/请求对象

# 标准库
import threading                      # 并发锁
from concurrent.futures import ThreadPoolExecutor  # 线程池
from datetime import datetime         # 时间
from typing import Optional, List, Dict, Any, Tuple, Callable  # 类型
import time                           # 计时
import random                         # 抖动
import importlib                      # 动态导入
import contextlib                     # 重定向 stdout/stderr
import io                             # 缓冲
import logging as py_logging          # 日志

# 项目内
from backend.utils.errors import http_500_from_exc  # 错误包装
from backend.db.sqlite import (                     # DB 接口
    upsert_symbol_index,
    select_symbol_index,
    get_conn,
    insert_symbol_index_summary,
)
from backend.settings import settings               # 全局设置（并发/重试）
from backend.utils.logger import (                  # 结构化日志工具
    get_logger, log_event, next_span_id,
)
from backend.services.config import get_config      # 读取用户配置（类别顺序）

# 路由器与 logger
router = APIRouter(prefix="/api", tags=["symbols"])  # 前缀 /api
_LOG: py_logging.Logger = get_logger("symbols")      # 本模块命名 logger

# 内存状态（仅提示用）
_SYMBOL_INDEX_CACHE = {
    "data": [],               # 最近一次成功合并的内存快照
    "updated_at": None,       # 最近构建完成时间
    "building": False,        # 是否构建中
    "lock": threading.Lock(), # 互斥锁
}

# —— 工具：延迟导入 / 静默输出 ——
def _lazy_import_ak():
    """延迟导入 akshare，降低冷启动/导入失败的风险。"""
    return importlib.import_module("akshare")

@contextlib.contextmanager
def _silence_stdout_stderr():
    """静默第三方库的打印（with 作用域内生效）。"""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        yield

# —— 工具：基础归一与市场推断 ——
def _norm_code_name(df, code_candidates: List[str], name_candidates: List[str]) -> List[Tuple[str, str]]:
    """从 DataFrame 中解析出 (symbol, name)，失败或列缺失返回空。"""
    try:
        import pandas as pd
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return []
        x = df.copy()
        x.columns = [str(c).strip() for c in x.columns]  # 列名去空白
        c_code = next((c for c in code_candidates if c in x.columns), None)
        c_name = next((c for c in name_candidates if c in x.columns), None)
        if not c_code or not c_name:
            return []
        out: List[Tuple[str, str]] = []
        for _, r in x.iterrows():
            sym = str(r.get(c_code, "")).strip()
            nam = str(r.get(c_name, "")).strip()
            if sym and nam:
                out.append((sym, nam))
        return out
    except Exception:
        return []

def _infer_market_for_a(code: str) -> str:
    """A股市场兜底：按代码前缀推断 SH/SZ/BJ。"""
    c = (code or "").strip()
    if not c:
        return ""
    # 上证（含科创：688/689）
    if c.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    # 深证（含主板/中小板/创业板：000/001/002/003/300/301）
    if c.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    # 北证（常见：43x、83x、87x、以及 8 开头新三板转板）
    if c.startswith(("430", "831", "832", "833", "834", "835", "836", "837", "838", "839", "871", "872", "873", "874", "875", "876", "877", "878", "879")):
        return "BJ"
    return ""  # 未识别

def _infer_market_by_prefix_general(code: str) -> str:
    """ETF/LOF 等通用兜底：按代码���缀推断 SH/SZ。"""
    c = (code or "").strip()
    if not c:
        return ""
    # 典型：上证 ETF 多为 5/51x；深证多为 15x/16x
    if c.startswith(("5", "51", "56", "58")) or (len(c) == 6 and c.startswith("5")):
        return "SH"
    if c.startswith(("15", "16")) or (len(c) == 6 and c.startswith(("15", "16"))):
        return "SZ"
    return ""  # 未识别

# —— 工具：短重试（指数退避 + 抖动） ——
def _retry_call(fn: Callable[[], Any], attempts: int = None, base_ms: int = None) -> Any:
    """可重试调用（指数退避 + 抖动）。"""
    a = int(getattr(settings, "retry_max_attempts", 0) or 2) if attempts is None else int(attempts)
    base = int(getattr(settings, "retry_base_delay_ms", 500)) if base_ms is None else int(base_ms)
    last_exc = None
    for i in range(a + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if i >= a:
                break
            delay = base * (2 ** i) / 1000.0
            delay *= (0.8 + 0.4 * random.random())
            time.sleep(delay)
    raise last_exc

# —— 类别加载器（A / ETF / LOF） ——
def _load_a(trace_id: Optional[str]) -> List[Dict[str, str]]:
    """A 股：主接口 + 后备合并（沪/深/北）。"""
    t0 = time.time()
    span = next_span_id("A")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_a", line=0, trace_id=trace_id,
              event="symbols.fetch.start", message="fetch A-share (A) begin",
              extra={"category": "fetch", "action": "start", "args": {"primary": "stock_info_a_code_name", "fallback": ["stock_info_sh_name_code","stock_info_sz_name_code","stock_info_bj_name_code"]}, "span_id": span})
    items: List[Dict[str, str]] = []
    try:
        ak = _lazy_import_ak()
        # 主：沪深京全量
        pairs_primary: List[Tuple[str, str]] = []
        with _silence_stdout_stderr():
            try:
                df_main = _retry_call(lambda: ak.stock_info_a_code_name())
                pairs_primary = _norm_code_name(df_main, ["code", "证券代码", "A股代码"], ["name", "证券简称", "A股简称"])
            except Exception:
                pairs_primary = []
        # 备：上证（主板/科创）+ 深证（A股列表）+ 北证
        pairs_fallback: List[Tuple[str, str]] = []
        with _silence_stdout_stderr():
            # 上证：主板A股
            try:
                df_sh_a = _retry_call(lambda: ak.stock_info_sh_name_code(symbol="主板A股"))
                pairs_fallback += _norm_code_name(df_sh_a, ["证券代码", "code"], ["证券简称", "name"])
            except Exception:
                pass
            # 上证：科创板
            try:
                df_kc = _retry_call(lambda: ak.stock_info_sh_name_code(symbol="科创板"))
                pairs_fallback += _norm_code_name(df_kc, ["证券代码", "code"], ["证券简称", "name"])
            except Exception:
                pass
            # 深证：A股列表
            try:
                df_sz_a = _retry_call(lambda: ak.stock_info_sz_name_code(symbol="A股列表"))
                pairs_fallback += _norm_code_name(df_sz_a, ["A股代码", "code"], ["A股简称", "name"])
            except Exception:
                pass
            # 北证
            try:
                df_bj = _retry_call(lambda: ak.stock_info_bj_name_code())
                pairs_fallback += _norm_code_name(df_bj, ["证券代码", "code"], ["证券简称", "name"])
            except Exception:
                pass
        # 合并（主优先，后备补充）
        seen = set()
        merged_pairs: List[Tuple[str, str]] = []
        for sym, nam in (pairs_primary or []):
            if sym not in seen:
                seen.add(sym); merged_pairs.append((sym, nam))
        for sym, nam in (pairs_fallback or []):
            if sym not in seen:
                seen.add(sym); merged_pairs.append((sym, nam))
        # 归一为 items
        for sym, nam in merged_pairs:
            items.append({
                "symbol": sym,
                "name": nam,
                "market": _infer_market_for_a(sym),
                "type": "A",
            })
        # 日志
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_a", line=0, trace_id=trace_id,
                  event="symbols.fetch.done", message="fetch A-share (A) done",
                  extra={"category": "fetch", "action": "done", "duration_ms": int((time.time()-t0)*1000), "result": {"rows": len(items)}, "span_id": span})
        return items
    except Exception as e:
        log_event(_LOG, service="symbols", level="WARN", file=__file__, func="_load_a", line=0, trace_id=trace_id,
                  event="symbols.fetch.fail", message="fetch A-share (A) failed",
                  extra={"category": "fetch", "action": "fail", "duration_ms": int((time.time()-t0)*1000),
                         "error_code": "AKSHARE_A_LIST_FAIL", "error_message": str(e), "span_id": span})
        return []

def _load_etf(trace_id: Optional[str]) -> List[Dict[str, str]]:
    """ETF：主接口 + 后备。"""
    t0 = time.time()
    span = next_span_id("ETF")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_etf", line=0, trace_id=trace_id,
              event="symbols.fetch.start", message="fetch ETF begin",
              extra={"category": "fetch", "action": "start", "args": {"primary": "fund_etf_spot_em", "fallback": ["fund_etf_category_sina(ETF基金)"]}, "span_id": span})
    items: List[Dict[str, str]] = []
    try:
        ak = _lazy_import_ak()
        pairs: List[Tuple[str, str]] = []
        with _silence_stdout_stderr():
            # 主：东财 ETF
            try:
                df = _retry_call(lambda: ak.fund_etf_spot_em())
                pairs = _norm_code_name(df, ["代码", "code"], ["名称", "name"])
            except Exception:
                pairs = []
            # 备：新浪 ETF 基金
            if not pairs:
                try:
                    df2 = _retry_call(lambda: ak.fund_etf_category_sina(symbol="ETF基金"))
                    pairs = _norm_code_name(df2, ["代码", "code"], ["名称", "name"])
                except Exception:
                    pairs = []
        # 归一
        seen = set()
        for sym, nam in (pairs or []):
            if sym in seen:
                continue
            seen.add(sym)
            items.append({
                "symbol": sym,
                "name": nam,
                "market": _infer_market_by_prefix_general(sym),
                "type": "ETF",
            })
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_etf", line=0, trace_id=trace_id,
                  event="symbols.fetch.done", message="fetch ETF done",
                  extra={"category": "fetch", "action": "done", "duration_ms": int((time.time()-t0)*1000), "result": {"rows": len(items)}, "span_id": span})
        return items
    except Exception as e:
        log_event(_LOG, service="symbols", level="WARN", file=__file__, func="_load_etf", line=0, trace_id=trace_id,
                  event="symbols.fetch.fail", message="fetch ETF failed",
                  extra={"category": "fetch", "action": "fail", "duration_ms": int((time.time()-t0)*1000),
                         "error_code": "AKSHARE_ETF_LIST_FAIL", "error_message": str(e), "span_id": span})
        return []

def _load_lof(trace_id: Optional[str]) -> List[Dict[str, str]]:
    """LOF：主接口 + 后备。"""
    t0 = time.time()
    span = next_span_id("LOF")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_lof", line=0, trace_id=trace_id,
              event="symbols.fetch.start", message="fetch LOF begin",
              extra={"category": "fetch", "action": "start", "args": {"primary": "fund_lof_spot_em", "fallback": ["fund_etf_category_sina(LOF基金)"]}, "span_id": span})
    items: List[Dict[str, str]] = []
    try:
        ak = _lazy_import_ak()
        pairs: List[Tuple[str, str]] = []
        with _silence_stdout_stderr():
            # 主：东财 LOF
            try:
                df = _retry_call(lambda: ak.fund_lof_spot_em())
                pairs = _norm_code_name(df, ["代码", "code"], ["名称", "name"])
            except Exception:
                pairs = []
            # 备：新浪 LOF 基金
            if not pairs:
                try:
                    df2 = _retry_call(lambda: ak.fund_etf_category_sina(symbol="LOF基金"))
                    pairs = _norm_code_name(df2, ["代码", "code"], ["名称", "name"])
                except Exception:
                    pairs = []
        # 归一
        seen = set()
        for sym, nam in (pairs or []):
            if sym in seen:
                continue
            seen.add(sym)
            items.append({
                "symbol": sym,
                "name": nam,
                "market": _infer_market_by_prefix_general(sym),
                "type": "LOF",
            })
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_load_lof", line=0, trace_id=trace_id,
                  event="symbols.fetch.done", message="fetch LOF done",
                  extra={"category": "fetch", "action": "done", "duration_ms": int((time.time()-t0)*1000), "result": {"rows": len(items)}, "span_id": span})
        return items
    except Exception as e:
        log_event(_LOG, service="symbols", level="WARN", file=__file__, func="_load_lof", line=0, trace_id=trace_id,
                  event="symbols.fetch.fail", message="fetch LOF failed",
                  extra={"category": "fetch", "action": "fail", "duration_ms": int((time.time()-t0)*1000),
                         "error_code": "AKSHARE_LOF_LIST_FAIL", "error_message": str(e), "span_id": span})
        return []

# —— 合并优先级与实现（A > ETF > LOF） ——
_TYPE_PRIORITY = {
    "A":   100,  # A 股优先级最高
    "ETF":  90,  # ETF 次之
    "LOF":  80,  # LOF 再次
}

def _merge_items(buckets: List[Tuple[str, List[Dict[str, str]]]], trace_id: Optional[str]) -> List[Dict[str, str]]:
    """按类别优先级合并多桶结果（symbol 为键）。"""
    t0 = time.time()
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_merge_items", line=0, trace_id=trace_id,
              event="symbols.merge.start", message="merge buckets start",
              extra={"category": "merge", "action": "start"})
    merged: Dict[str, Dict[str, str]] = {}
    prio: Dict[str, int] = {}
    for typ, arr in buckets:
        p = _TYPE_PRIORITY.get(typ, 0)
        for it in (arr or []):
            sym = str(it.get("symbol", "")).strip()
            if not sym:
                continue
            curr = prio.get(sym, -1)
            if p >= curr:
                merged[sym] = {
                    "symbol": sym,
                    "name": str(it.get("name", "")).strip(),
                    "market": str(it.get("market", "")).strip(),
                    "type": str(it.get("type", "")).strip(),
                }
                prio[sym] = p
    out = list(merged.values())
    out.sort(key=lambda x: x["symbol"])
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_merge_items", line=0, trace_id=trace_id,
              event="symbols.merge.done", message="merge buckets done",
              extra={"category": "merge", "action": "done", "duration_ms": int((time.time()-t0)*1000), "result": {"rows": len(out)}})
    return out

# —— UPSERT（不删除） ——
def _upsert_db_only(items: List[Dict[str, str]], trace_id: Optional[str]) -> Dict[str, Any]:
    """将 items 写入 symbol_index（仅 UPSERT，空结果跳过）。"""
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM symbol_index;")
    old_rows = int(cur.fetchone()[0] or 0)
    new_rows = int(len(items) or 0)
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_upsert_db_only", line=0, trace_id=trace_id,
              event="db.upsert.begin", message="UPSERT symbol_index begin (no delete)",
              extra={"category": "db", "action": "start", "db": {"table": "symbol_index"}, "result": {"summary": f"old_rows={old_rows}, new_rows={new_rows}"}})
    if new_rows <= 0:
        log_event(_LOG, service="symbols", level="WARN", file=__file__, func="_upsert_db_only", line=0, trace_id=trace_id,
                  event="db.upsert.skip", message="skip empty merged items; keep existing",
                  extra={"category": "db", "action": "fail"})
        return {"ok": False, "skipped": True, "old_rows": old_rows, "new_rows": new_rows}
    ts = datetime.now().isoformat()
    rows = [(it["symbol"], it["name"], it.get("market",""), it.get("type",""), ts) for it in items]
    if rows:
        upsert_symbol_index(rows)
    cur.execute("SELECT COUNT(1) FROM symbol_index;")
    total_rows = int(cur.fetchone()[0] or 0)
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_upsert_db_only", line=0, trace_id=trace_id,
              event="db.upsert.done", message="UPSERT symbol_index done",
              extra={"category": "db", "action": "upsert", "result": {"summary": f"total_rows={total_rows}"}})
    return {"ok": True, "skipped": False, "old_rows": old_rows, "new_rows": new_rows, "total_rows": total_rows}

# —— 差分统计（按 type：new/updated/untouched + total） ——
def _diff_counts_by_type(old_list: List[Dict[str, Any]], new_items: List[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    """基于写前旧集与本次合并结果，统计每类 new/updated/untouched；total 稍后以写后分组补齐。"""
    old_by_sym_type: Dict[str, str] = {}
    for r in (old_list or []):
        try:
            old_by_sym_type[str(r.get("symbol","")).strip()] = str(r.get("type","")).strip()
        except Exception:
            continue
    new_by_sym_type: Dict[str, str] = {}
    for it in (new_items or []):
        try:
            new_by_sym_type[str(it.get("symbol","")).strip()] = str(it.get("type","")).strip()
        except Exception:
            continue
    old_syms = set(old_by_sym_type.keys())
    new_syms = set(new_by_sym_type.keys())
    only_new = new_syms - old_syms       # 纯新增
    inter = new_syms & old_syms          # 覆盖更新（存在即视为更新）
    untouched = old_syms - new_syms      # 本次未覆盖（未更新）
    out: Dict[str, Dict[str, int]] = {}
    def inc(t: str, k: str, n: int=1):
        if not t:
            return
        out.setdefault(t, {"total": 0, "new": 0, "updated": 0, "untouched": 0})
        out[t][k] = out[t].get(k, 0) + n
    for s in only_new:
        inc(new_by_sym_type.get(s,""), "new", 1)
    for s in inter:
        inc(new_by_sym_type.get(s,""), "updated", 1)
    for s in untouched:
        inc(old_by_sym_type.get(s,""), "untouched", 1)
    return out

# —— 仅三类支持 —— 
_SUPPORTED_CATEGORIES = ["A","ETF","LOF"]  # 限定范围

def _build_tasks_by_config(trace_id: Optional[str]) -> List[Tuple[str, Callable[[Optional[str]], List[Dict[str, str]]]]]:
    """根据 config.json 构造（有序）抓取任务列表，仅允许 A/ETF/LOF。"""
    # 类别到加载器映射
    loader_map: Dict[str, Callable[[Optional[str]], List[Dict[str, str]]]] = {
        "A": _load_a,
        "ETF": _load_etf,
        "LOF": _load_lof,
    }
    # 读取配置并过滤非法条目
    cfg = get_config()
    raw = cfg.get("symbol_index_categories") or []
    ordered = [c for c in raw if isinstance(c, str) and c.strip().upper() in loader_map]
    # 追加漏项（保证三类都能覆盖，若用户只选部分则按其选择）
    for c in _SUPPORTED_CATEGORIES:
        if c not in ordered and c in loader_map:
            ordered.append(c)
    # 观测：执行顺序
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_build_tasks_by_config", line=0, trace_id=trace_id,
              event="symbols.plan", message="symbol index categories planned",
              extra={"category": "task", "action": "plan", "result": {"summary": ",".join(ordered)}})
    # 产出任务
    return [(c, loader_map[c]) for c in ordered]

def _build_symbol_index_full(trace_id: Optional[str]) -> List[Dict[str, str]]:
    """执行并发抓取 → 合并为统一索引列表（不落库）。"""
    t0 = time.time()
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_build_symbol_index_full", line=0, trace_id=trace_id,
              event="symbols.refresh.fetch", message="fetch categories begin",
              extra={"category": "task", "action": "start"})
    tasks = _build_tasks_by_config(trace_id)
    max_workers = max(1, min(int(getattr(settings, "fetch_concurrency", 3)), 6))
    results: List[Tuple[str, List[Dict[str, str]]]] = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="symidx") as ex:
        futs = [(typ, ex.submit(fn, trace_id)) for typ, fn in tasks]
        for typ, fut in futs:
            try:
                arr = fut.result(timeout=180)
            except Exception as e:
                log_event(_LOG, service="symbols", level="WARN", file=__file__, func="_build_symbol_index_full", line=0, trace_id=trace_id,
                          event="symbols.fetch.fail", message=f"fetch {typ} failed",
                          extra={"category": "fetch", "action": "fail", "error_code": "FUTURE_FETCH_FAIL", "error_message": str(e)})
                arr = []
            results.append((typ, arr))
    merged = _merge_items(results, trace_id)
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_build_symbol_index_full", line=0, trace_id=trace_id,
              event="symbols.refresh.fetch_done", message="fetch categories done",
              extra={"category": "task", "action": "done", "duration_ms": int((time.time()-t0)*1000), "result": {"rows": len(merged)}})
    return merged

def _refresh_index_async() -> None:
    """后台刷新（不阻塞）：抓取合并 → 差分统计 → UPSERT → 快照摘要。"""
    with _SYMBOL_INDEX_CACHE["lock"]:
        if _SYMBOL_INDEX_CACHE["building"]:
            return
        _SYMBOL_INDEX_CACHE["building"] = True
    trace_id = f"task-{int(time.time()*1000)}"
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_refresh_index_async", line=0, trace_id=trace_id,
              event="symbols.refresh.start", message="symbol index build started",
              extra={"category": "task", "action": "start"})
    def _job():
        try:
            # 写前旧集
            old_items = select_symbol_index()
            # 抓取合并
            items = _build_symbol_index_full(trace_id)
            # 差分统计（total 稍后补）
            delta_by_type = _diff_counts_by_type(old_items, items)
            # 写库
            res = _upsert_db_only(items, trace_id)
            if res.get("ok"):
                conn = get_conn(); cur = conn.cursor()
                # 写后：类型聚合
                cur.execute("SELECT type, COUNT(1) AS n FROM symbol_index GROUP BY type ORDER BY n DESC;")
                by_type = [{"type": r[0], "n": r[1]} for r in cur.fetchall()]
                # 写后：类型×市场聚合
                cur.execute("SELECT type, market, COUNT(1) AS n FROM symbol_index GROUP BY type, market ORDER BY n DESC;")
                by_type_market = [{"type": r[0], "market": r[1], "n": r[2]} for r in cur.fetchall()]
                # total 覆盖回 delta
                total_map = {d["type"]: d["n"] for d in by_type}
                delta_list = []
                for typ, m in (delta_by_type or {}).items():
                    delta_list.append({
                        "type": typ,
                        "total": int(total_map.get(typ, 0)),
                        "new": int(m.get("new", 0)),
                        "updated": int(m.get("updated", 0)),
                        "untouched": int(m.get("untouched", 0)),
                    })
                # 写快照
                insert_symbol_index_summary(datetime.now().isoformat(),
                                            int(res.get("total_rows") or 0),
                                            by_type,
                                            by_type_market,
                                            delta_by_type=delta_list)
                # 内存快照用于 UI 提示
                with _SYMBOL_INDEX_CACHE["lock"]:
                    _SYMBOL_INDEX_CACHE["data"] = items
                    _SYMBOL_INDEX_CACHE["updated_at"] = datetime.now().isoformat()
            # 复位
            with _SYMBOL_INDEX_CACHE["lock"]:
                _SYMBOL_INDEX_CACHE["building"] = False
            log_event(_LOG, service="symbols", level="INFO", file=__file__, func="_refresh_index_async", line=0, trace_id=trace_id,
                      event="symbols.refresh.done", message="symbol index build finished",
                      extra={"category": "task", "action": "done", "result": {"summary": ("upserted" if res.get("ok") else "skipped")}})
        except Exception as e:
            # 异常：记录并复位
            log_event(_LOG, service="symbols", level="ERROR", file=__file__, func="_refresh_index_async", line=0, trace_id=trace_id,
                      event="symbols.refresh.fail", message="symbol index build failed",
                      extra={"category": "task", "action": "fail", "error_code": "SYMBOLS_REFRESH_FAIL", "error_message": str(e)})
            with _SYMBOL_INDEX_CACHE["lock"]:
                _SYMBOL_INDEX_CACHE["building"] = False
    threading.Thread(target=_job, name="symbol-index-rebuild", daemon=True).start()

# —— 路由：读取/刷新/汇总 ——
@router.get("/symbols/index")
def api_get_symbol_index(
    request: Request,
    refresh: Optional[int] = Query(0, description="传 1 可后台刷新"),
):
    """返回当前索引（优先 DB），可选触发后台刷新。"""
    tid = request.headers.get("x-trace-id")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_get_symbol_index", line=0, trace_id=tid,
              event="api.read", message="GET /symbols/index",
              extra={"category": "api", "action": "select", "request": {"endpoint": "/api/symbols/index", "method": "GET", "query": {"refresh": refresh}}})
    try:
        if refresh:
            _refresh_index_async()
        db_items = select_symbol_index()
        with _SYMBOL_INDEX_CACHE["lock"]:
            payload = {
                "updated_at": _SYMBOL_INDEX_CACHE["updated_at"],
                "rows": len(db_items),
                "building": _SYMBOL_INDEX_CACHE["building"],
                "items": db_items,
                "trace_id": tid,
            }
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_get_symbol_index", line=0, trace_id=tid,
                  event="api.read.done", message="GET /symbols/index done",
                  extra={"category": "api", "action": "done", "result": {"status_code": 200, "summary": f"building={payload['building']}, rows={payload['rows']}"}})
        return payload
    except Exception as e:
        log_event(_LOG, service="symbols", level="ERROR", file=__file__, func="api_get_symbol_index", line=0, trace_id=tid,
                  event="api.read.fail", message="GET /symbols/index failed",
                  extra={"category": "api", "action": "fail", "error_code": "API_SYMBOLS_INDEX_FAIL", "error_message": str(e)})
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/symbols/refresh")
def api_refresh_symbol_index(request: Request) -> Dict[str, Any]:
    """手动触发后台刷新（立即返回）。"""
    tid = request.headers.get("x-trace-id")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_refresh_symbol_index", line=0, trace_id=tid,
              event="api.write", message="POST /symbols/refresh",
              extra={"category": "api", "action": "start"})
    try:
        _refresh_index_async()
        resp = {"ok": True, "building": True, "trace_id": tid}
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_refresh_symbol_index", line=0, trace_id=tid,
                  event="api.write.done", message="POST /symbols/refresh done",
                  extra={"category": "api", "action": "done", "result": {"status_code": 200}})
        return resp
    except Exception as e:
        log_event(_LOG, service="symbols", level="ERROR", file=__file__, func="api_refresh_symbol_index", line=0, trace_id=tid,
                  event="api.write.fail", message="POST /symbols/refresh failed",
                  extra={"category": "api", "action": "fail", "error_code": "API_SYMBOLS_REFRESH_FAIL", "error_message": str(e)})
        raise http_500_from_exc(e, trace_id=tid)

@router.get("/symbols/summary")
def api_symbols_summary(request: Request) -> Dict[str, Any]:
    """返回索引聚合（by_type / by_type_market），并尽量附带最新 delta。"""
    tid = request.headers.get("x-trace-id")
    log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_symbols_summary", line=0, trace_id=tid,
              event="api.read", message="GET /symbols/summary",
              extra={"category": "api", "action": "select"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT type, COUNT(1) AS n FROM symbol_index GROUP BY type ORDER BY n DESC;")
        by_type = [{"type": r[0], "n": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT type, market, COUNT(1) AS n FROM symbol_index GROUP BY type, market ORDER BY n DESC;")
        by_type_market = [{"type": r[0], "market": r[1], "n": r[2]} for r in cur.fetchall()]
        # 读取最近快照的 delta（可选）
        try:
            from backend.db.sqlite import get_latest_symbol_index_summary
            latest = get_latest_symbol_index_summary() or {}
            latest_delta = latest.get("delta_by_type") or []
            snapshot_at = latest.get("snapshot_at")
        except Exception:
            latest_delta = []
            snapshot_at = None
        payload = {"ok": True, "by_type": by_type, "by_type_market": by_type_market, "latest_delta": latest_delta, "snapshot_at": snapshot_at, "trace_id": tid}
        log_event(_LOG, service="symbols", level="INFO", file=__file__, func="api_symbols_summary", line=0, trace_id=tid,
                  event="api.read.done", message="GET /symbols/summary done",
                  extra={"category": "api", "action": "done", "result": {"status_code": 200}})
        return payload
    except Exception as e:
        log_event(_LOG, service="symbols", level="ERROR", file=__file__, func="api_symbols_summary", line=0, trace_id=tid,
                  event="api.read.fail", message="GET /symbols/summary failed",
                  extra={"category": "api", "action": "fail", "error_code": "API_SYMBOLS_SUMMARY_FAIL", "error_message": str(e)})
        raise http_500_from_exc(e, trace_id=tid)

# —— 启动即尝试后台刷新（不阻塞） ——
try:
    _refresh_index_async()
except Exception as e:
    log_event(_LOG, service="symbols", level="WARN", file=__file__, func="<module>", line=0, trace_id=None,
              event="symbols.bootstrap.warn", message="bootstrap refresh failed",
              extra={"category": "task", "action": "fail", "error_code": "BOOTSTRAP_REFRESH_FAIL", "error_message": str(e)})
