# backend/db/sqlite.py  # SQLite 连接/DDL/UPSERT/缓存LRU清理/迁移/健康检查（全量）
# ==============================
# 说明：
# - candles/candles_cache 表新增 close_time TEXT，并在列顺序上将 close_time 放在 ts 之前（紧前）。
# - 启动迁移：
#   * 若缺列 → ALTER TABLE 增加 close_time；
#   * 若列顺序不满足“close_time 在 ts 前”，则重建新表并回填（close_time 为空时按 ts 计算）。
# - upsert_candles/upsert_cache_candles 改为“命名占位符 + 字典绑定”（更稳健），并在写库前自动补齐 close_time。
# - 新增两张表：
#   * user_watchlist：本地自选池（权威源），symbol 主键 + 元数据
#   * symbol_history：标的框历史记录（追加式日志）
# ==============================

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, List, Optional, Dict, Any
from datetime import datetime, timedelta
import threading
import json

from backend.settings import settings
from backend.utils.time import format_close_time_str  # 计算人读友好收盘时间

_LOCAL = threading.local()
_GEN: int = 0

def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row

def get_conn() -> sqlite3.Connection:
    global _LOCAL, _GEN
    conn: Optional[sqlite3.Connection] = getattr(_LOCAL, "conn", None)
    gen: Optional[int] = getattr(_LOCAL, "gen", None)
    if conn is not None and gen == _GEN:
        return conn
    if conn is not None:
        try: conn.close()
        except Exception: pass
        setattr(_LOCAL, "conn", None)
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(settings.db_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False
    )
    _apply_pragmas(conn)
    setattr(_LOCAL, "conn", conn)
    setattr(_LOCAL, "gen", _GEN)
    return conn

def _create_candles_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL,
      close_time TEXT,            -- 人读友好的收盘时间（YYYY-MM-DD HH:MM，Asia/Shanghai）
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      fetched_at TEXT NOT NULL,
      revision TEXT,
      PRIMARY KEY (symbol, freq, adjust, ts)
    );
    """)

def _ensure_candles_cache_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_cache (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL,
      close_time TEXT,            -- 人读友好的收盘时间（YYYY-MM-DD HH:MM，Asia/Shanghai）
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      fetched_at TEXT NOT NULL,
      revision TEXT,
      PRIMARY KEY (symbol, freq, adjust, ts)
    );
    """)

def _migrate_drop_trading_status_if_needed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(candles);")
    cols = [r["name"] for r in cur.fetchall()]
    if "trading_status" not in cols:
        return
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_new_tmp (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL,
      close_time TEXT,
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      fetched_at TEXT NOT NULL,
      revision TEXT,
      PRIMARY KEY (symbol, freq, adjust, ts)
    );
    """)
    # 回填时计算 close_time（若旧表无该列，按 ts 生成）
    cur.execute("SELECT symbol,freq,adjust,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision FROM candles;")
    rows = cur.fetchall()
    to_insert = []
    for r in rows:
        ts_val = int(r["ts"])
        to_insert.append({
            "symbol": r["symbol"],
            "freq": r["freq"],
            "adjust": r["adjust"],
            "close_time": format_close_time_str(ts_val, r["freq"]),
            "ts": ts_val,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
            "amount": r["amount"],
            "turnover_rate": r["turnover_rate"],
            "source": r["source"],
            "fetched_at": r["fetched_at"],
            "revision": r["revision"],
        })
    if to_insert:
        cur.executemany("""
        INSERT INTO candles_new_tmp (symbol,freq,adjust,close_time,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision)
        VALUES (:symbol,:freq,:adjust,:close_time,:ts,:open,:high,:low,:close,:volume,:amount,:turnover_rate,:source,:fetched_at,:revision);
        """, to_insert)
    cur.execute("DROP TABLE candles;")
    cur.execute("ALTER TABLE candles_new_tmp RENAME TO candles;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_symfreq ON candles(symbol,freq,adjust,ts);")
    conn.commit()

def _migrate_candles_cache_add_missing_cols(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(candles_cache);")
    cols = {r["name"] for r in cur.fetchall()}
    if "turnover_rate" not in cols:
        try: cur.execute("ALTER TABLE candles_cache ADD COLUMN turnover_rate REAL;")
        except Exception: pass
    if "revision" not in cols:
        try: cur.execute("ALTER TABLE candles_cache ADD COLUMN revision TEXT;")
        except Exception: pass
    if "close_time" not in cols:
        try: cur.execute("ALTER TABLE candles_cache ADD COLUMN close_time TEXT;")
        except Exception: pass
    conn.commit()

def _migrate_add_close_time_if_needed(conn: sqlite3.Connection) -> None:
    """为 candles 表补充 close_time 列（不存在则新增）。"""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(candles);")
    cols = {r["name"] for r in cur.fetchall()}
    if "close_time" not in cols:
        try:
            cur.execute("ALTER TABLE candles ADD COLUMN close_time TEXT;")
        except Exception:
            pass
    conn.commit()

def _reorder_and_backfill_close_time(conn: sqlite3.Connection, table: str) -> None:
    """
    若目标表的列顺序不满足“close_time 在 ts 前”，则重建该表并回填；
    对已有 close_time 为 NULL 的记录，按 ts 计算并填充。
    """
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    info = cur.fetchall()
    cols = [dict(r) for r in info]
    names = [c["name"] for c in cols]
    # 若不存在 close_time，则先补列，再继续处理
    if "close_time" not in names:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN close_time TEXT;")
            conn.commit()
        except Exception:
            pass
        cur.execute(f"PRAGMA table_info({table});")
        info = cur.fetchall()
        cols = [dict(r) for r in info]
        names = [c["name"] for c in cols]
    # 检查顺序：close_time 索引必须小于 ts 索引；否则重建
    try:
        idx_close = names.index("close_time")
        idx_ts = names.index("ts")
    except ValueError:
        return
    if idx_close < idx_ts:
        # 顺序已满足，无需重建；同时做一次回填 NULL
        cur.execute(f"SELECT symbol,freq,adjust,ts,close_time FROM {table} WHERE close_time IS NULL;")
        rows = cur.fetchall()
        for r in rows:
            ct = format_close_time_str(int(r["ts"]), r["freq"])
            cur.execute(f"UPDATE {table} SET close_time=? WHERE symbol=? AND freq=? AND adjust=? AND ts=?;",
                        (ct, r["symbol"], r["freq"], r["adjust"], int(r["ts"])))
        conn.commit()
        return

    # 重建表，列顺序：symbol,freq,adjust,close_time,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision
    new_name = f"{table}_new_reordered"
    cur.execute(f"DROP TABLE IF EXISTS {new_name};")
    cur.execute(f"""
    CREATE TABLE {new_name} (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL,
      close_time TEXT,
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      fetched_at TEXT NOT NULL,
      revision TEXT,
      PRIMARY KEY (symbol, freq, adjust, ts)
    );
    """)
    cur.execute(f"SELECT symbol,freq,adjust,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision,close_time FROM {table};")
    rows = cur.fetchall()
    to_insert = []
    for r in rows:
        ts_val = int(r["ts"])
        ct = r["close_time"] if r["close_time"] else format_close_time_str(ts_val, r["freq"])
        to_insert.append({
            "symbol": r["symbol"],
            "freq": r["freq"],
            "adjust": r["adjust"],
            "close_time": ct,
            "ts": ts_val,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
            "amount": r["amount"],
            "turnover_rate": r["turnover_rate"],
            "source": r["source"],
            "fetched_at": r["fetched_at"],
            "revision": r["revision"],
        })
    if to_insert:
        cur.executemany(f"""
        INSERT INTO {new_name} (symbol,freq,adjust,close_time,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision)
        VALUES (:symbol,:freq,:adjust,:close_time,:ts,:open,:high,:low,:close,:volume,:amount,:turnover_rate,:source,:fetched_at,:revision);
        """, to_insert)
    cur.execute(f"DROP TABLE {table};")
    cur.execute(f"ALTER TABLE {new_name} RENAME TO {table};")
    # 重建常用索引
    if table == "candles":
        cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_symfreq ON candles(symbol,freq,adjust,ts);")
    elif table == "candles_cache":
        cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_cache_symfreq ON candles_cache(symbol,freq,adjust,ts);")
    conn.commit()

def init_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # 创建基础表（close_time 在 ts 前）
    _create_candles_schema(cur)
    _ensure_candles_cache_schema(cur)
    conn.commit()

    # 兼容旧表：交易状态迁移与补列
    _migrate_drop_trading_status_if_needed(conn)
    _migrate_add_close_time_if_needed(conn)
    _migrate_candles_cache_add_missing_cols(conn)

    # 列顺序校正与回填（确保 close_time 在 ts 前，并回填 NULL）
    _reorder_and_backfill_close_time(conn, "candles")
    _reorder_and_backfill_close_time(conn, "candles_cache")

    # 其余表保持不变
    cur.execute("""
    CREATE TABLE IF NOT EXISTS adj_factors (
      symbol TEXT NOT NULL,
      date   INTEGER NOT NULL,
      qfq_factor REAL NOT NULL,
      hfq_factor REAL NOT NULL,
      updated_at TEXT,
      PRIMARY KEY (symbol, date)
    );
    """)
    try:
        cur.execute("PRAGMA table_info(adj_factors);")
        cols = [r["name"] for r in cur.fetchall()]
        if "updated_at" not in cols:
            cur.execute("ALTER TABLE adj_factors ADD COLUMN updated_at TEXT;")
    except Exception:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol TEXT PRIMARY KEY,
      name   TEXT NOT NULL,
      market TEXT,
      type   TEXT,
      updated_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cache_meta (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL,
      last_access TEXT NOT NULL,
      rows INTEGER NOT NULL,
      first_ts INTEGER,
      last_ts  INTEGER,
      PRIMARY KEY (symbol, freq, adjust)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index_summary (
      snapshot_at TEXT PRIMARY KEY,
      total_rows  INTEGER NOT NULL,
      by_type_json TEXT NOT NULL,
      by_type_market_json TEXT NOT NULL,
      delta_by_type_json TEXT
    );
    """)

    # --- 新增：用户自选池表（权威源） ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_watchlist (
      symbol TEXT PRIMARY KEY,      -- 自选标的代码（唯一）
      added_at TEXT NOT NULL,       -- 加入时间（ISO8601）
      source TEXT,                  -- 来源（'user'|'sync' 等）
      note TEXT,                    -- 备注（可空）
      updated_at TEXT               -- 最近修改时间（ISO8601，可空）
    );
    """)

    # --- 新增：标的框历史记录表（追加式日志） ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增ID
      symbol TEXT NOT NULL,                  -- 标的代码
      freq TEXT,                             -- 当时频率（如 '1d'）
      selected_at TEXT NOT NULL,             -- 选择时间（ISO8601）
      source TEXT                            -- 来源（'ui' 等）
    );
    """)
    # 索引：按选择时间倒序查询与按 symbol 查询
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_history_selected_at ON symbol_history(selected_at DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_history_symbol ON symbol_history(symbol);")

    # 索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_symfreq ON candles(symbol,freq,adjust,ts);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_cache_symfreq ON candles_cache(symbol,freq,adjust,ts);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cache_meta_last_access ON cache_meta(last_access);")

    conn.commit()

# ---- 长期表（1d） -------------------------------------------------------------
def upsert_candles(rows: Iterable[Dict[str, Any]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO candles (symbol,freq,adjust,close_time,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision)
    VALUES (:symbol,:freq,:adjust,:close_time,:ts,:open,:high,:low,:close,:volume,:amount,:turnover_rate,:source,:fetched_at,:revision)
    ON CONFLICT(symbol,freq,adjust,ts) DO UPDATE SET
      close_time=excluded.close_time,
      open=excluded.open,
      high=excluded.high,
      low=excluded.low,
      close=excluded.close,
      volume=excluded.volume,
      amount=excluded.amount,
      turnover_rate=excluded.turnover_rate,
      source=excluded.source,
      fetched_at=excluded.fetched_at,
      revision=excluded.revision;
    """
    def _prep(r: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(r or {})
        if not d.get("close_time") and d.get("ts") is not None:
            d["close_time"] = format_close_time_str(int(d["ts"]), d.get("freq"))
        return d
    cur.executemany(sql, [ _prep(r) for r in list(rows) ])
    conn.commit()
    return cur.rowcount

def select_candles(symbol: str, freq: str, adjust: str, ts_begin: Optional[int], ts_end: Optional[int]) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    conds = ["symbol=? AND freq=? AND adjust=?"]
    args: List[Any] = [symbol, freq, adjust]
    if ts_begin is not None:
        conds.append("ts>=?")
        args.append(int(ts_begin))
    if ts_end is not None:
        conds.append("ts<=?")
        args.append(int(ts_end))
    sql = f"SELECT * FROM candles WHERE {' AND '.join(conds)} ORDER BY ts ASC;"
    cur.execute(sql, tuple(args))
    rows = cur.fetchall()
    return [dict(r) for r in rows]

# ---- 复权因子 -----------------------------------------------------------------
def upsert_factors(rows: Iterable[Tuple[str, int, float, float, str]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO adj_factors(symbol, date, qfq_factor, hfq_factor, updated_at)
    VALUES (?,?,?,?,?)
    ON CONFLICT(symbol,date) DO UPDATE SET
      qfq_factor=excluded.qfq_factor,
      hfq_factor=excluded.hfq_factor,
      updated_at=excluded.updated_at;
    """
    cur.executemany(sql, list(rows))
    conn.commit()
    return cur.rowcount

# 新增：查询复权因子
def select_factors(symbol: str, start_ymd: int, end_ymd: int) -> List[Dict[str, Any]]:
    """查询指定标的与日期范围内的复权因子。"""
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT date, qfq_factor, hfq_factor FROM adj_factors WHERE symbol=? AND date BETWEEN ? AND ? ORDER BY date ASC;"
    args = (symbol, start_ymd, end_ymd)
    cur.execute(sql, args)
    rows = cur.fetchall()
    return [dict(r) for r in rows]

# ---- 缓存表/元信息 ------------------------------------------------------------
def upsert_cache_candles(rows: Iterable[Dict[str, Any]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO candles_cache (symbol,freq,adjust,close_time,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at,revision)
    VALUES (:symbol,:freq,:adjust,:close_time,:ts,:open,:high,:low,:close,:volume,:amount,:turnover_rate,:source,:fetched_at,:revision)
    ON CONFLICT(symbol,freq,adjust,ts) DO UPDATE SET
      close_time=excluded.close_time,
      open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
      volume=excluded.volume, amount=excluded.amount, turnover_rate=excluded.turnover_rate,
      source=excluded.source, fetched_at=excluded.fetched_at, revision=excluded.revision;
    """
    def _prep(r: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(r or {})
        if not d.get("close_time") and d.get("ts") is not None:
            d["close_time"] = format_close_time_str(int(d["ts"]), d.get("freq"))
        return d
    cur.executemany(sql, [ _prep(r) for r in list(rows) ])
    conn.commit()
    return cur.rowcount

def select_cache_candles(symbol: str, freq: str, adjust: str, ts_begin: Optional[int], ts_end: Optional[int]) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    conds = ["symbol=? AND freq=? AND adjust=?"]
    args: List[Any] = [symbol, freq, adjust]
    if ts_begin is not None:
        conds.append("ts>=?")
        args.append(int(ts_begin))
    if ts_end is not None:
        conds.append("ts<=?")
        args.append(int(ts_end))
    sql = f"SELECT * FROM candles_cache WHERE {' AND '.join(conds)} ORDER BY ts ASC;"
    cur.execute(sql, tuple(args))
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def get_cache_meta(symbol: str, freq: str, adjust: str="none") -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cache_meta WHERE symbol=? AND freq=? AND adjust=?;", (symbol,freq,adjust))
    row = cur.fetchone()
    return dict(row) if row else None

def touch_cache_meta(symbol: str, freq: str, adjust: str="none") -> None:
    now = datetime.now().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO cache_meta(symbol,freq,adjust,last_access,rows,first_ts,last_ts)
    VALUES (?,?,?,?,0,NULL,NULL)
    ON CONFLICT(symbol,freq,adjust) DO UPDATE SET last_access=excluded.last_access;
    """, (symbol,freq,adjust,now))
    conn.commit()

def rebuild_cache_meta(symbol: str, freq: str, adjust: str="none") -> None:
    """修复变量名，统计并写入 cache_meta。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) AS r, MIN(ts) AS mn, MAX(ts) AS mx FROM candles_cache WHERE symbol=? AND freq=? AND adjust=?;", (symbol,freq,adjust))
    row = cur.fetchone()
    rows = int(row["r"] or 0)
    first_ts = row["mn"]
    last_ts = row["mx"]
    now = datetime.now().isoformat()
    cur.execute("""
    INSERT INTO cache_meta(symbol,freq,adjust,last_access,rows,first_ts,last_ts)
    VALUES (?,?,?,?,?,?,?)
    ON CONFLICT(symbol,freq,adjust) DO UPDATE SET
      last_access=excluded.last_access, rows=excluded.rows, first_ts=excluded.first_ts, last_ts=excluded.last_ts;
    """, (symbol,freq,adjust,now,rows,first_ts,last_ts))
    conn.commit()

def cache_total_rows() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) AS r FROM candles_cache;")
    return int(cur.fetchone()["r"])

def evict_cache_by_lru(max_rows: int, ttl_days: int = 0) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    total = cache_total_rows()
    removed_partitions = 0
    removed_rows = 0
    if total <= max_rows:
        return {"removed_partitions":0, "removed_rows":0, "total_rows":total}
    candidates: List[Tuple[str,str,str]] = []
    seen = set()
    if ttl_days and ttl_days > 0:
        cutoff = (datetime.now() - timedelta(days=int(ttl_days))).isoformat()
        cur.execute("SELECT symbol,freq,adjust FROM cache_meta WHERE last_access < ? ORDER BY last_access ASC;", (cutoff,))
        for r in cur.fetchall():
            key = (r["symbol"], r["freq"], r["adjust"])
            if key not in seen:
                seen.add(key)
                candidates.append(key)
    cur.execute("SELECT symbol,freq,adjust FROM cache_meta ORDER BY last_access ASC;")
    for r in cur.fetchall():
        key = (r["symbol"], r["freq"], r["adjust"])
        if key not in seen:
            seen.add(key)
            candidates.append(key)
    for (sym,freq,adj) in candidates:
        if total <= max_rows:
            break
        cur.execute("SELECT COUNT(1) AS r FROM candles_cache WHERE symbol=? AND freq=? AND adjust=?;", (sym,freq,adj))
        rc = int(cur.fetchone()["r"] or 0)
        if rc > 0:
            cur.execute("DELETE FROM candles_cache WHERE symbol=? AND freq=? AND adjust=?;", (sym,freq,adj))
            removed_rows += rc
            total -= rc
        cur.execute("DELETE FROM cache_meta WHERE symbol=? AND freq=? AND adjust=?;", (sym,freq,adj))
        removed_partitions += 1
        conn.commit()
    return {"removed_partitions":removed_partitions, "removed_rows":removed_rows, "total_rows":total}

# ---- 符号索引与快照/健康/迁移（保持不变） ----
def upsert_symbol_index(rows: Iterable[Tuple[str, str, str, str, str]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO symbol_index(symbol,name,market,type,updated_at)
    VALUES (?,?,?,?,?)
    ON CONFLICT(symbol) DO UPDATE SET
      name=excluded.name,
      market=excluded.market,
      type=excluded.type,
      updated_at=excluded.updated_at;
    """
    cur.executemany(sql, list(rows))
    conn.commit()
    return cur.rowcount

def select_symbol_index() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol,name,market,type,updated_at FROM symbol_index ORDER BY symbol ASC;")
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def insert_symbol_index_summary(snapshot_at: str, total_rows: int,
                                by_type: List[Dict[str, Any]],
                                by_type_market: List[Dict[str, Any]],
                                delta_by_type: Optional[List[Dict[str, Any]]] = None) -> None:
    by_type_json = json.dumps(by_type, ensure_ascii=False)
    by_type_market_json = json.dumps(by_type_market, ensure_ascii=False)
    delta_json = json.dumps(delta_by_type or [], ensure_ascii=False)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT OR REPLACE INTO symbol_index_summary (snapshot_at, total_rows, by_type_json, by_type_market_json, delta_by_type_json)
        VALUES (?, ?, ?, ?, ?);
        """, (snapshot_at, int(total_rows), by_type_json, by_type_market_json, delta_json))
    except Exception:
        cur.execute("""
        INSERT OR REPLACE INTO symbol_index_summary (snapshot_at, total_rows, by_type_json, by_type_market_json)
        VALUES (?, ?, ?, ?);
        """, (snapshot_at, int(total_rows), by_type_json, by_type_market_json))
    conn.commit()

def get_latest_symbol_index_summary() -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT snapshot_at, total_rows, by_type_json, by_type_market_json, delta_by_type_json
        FROM symbol_index_summary
        ORDER BY snapshot_at DESC
        LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            return None
        by_type = json.loads(row["by_type_json"]) if row["by_type_json"] else []
        by_type_market = json.loads(row["by_type_market_json"]) if row["by_type_market_json"] else []
        try:
            delta_by_type = json.loads(row["delta_by_type_json"]) if row["delta_by_type_json"] else []
        except Exception:
            delta_by_type = []
        return {
            "snapshot_at": row["snapshot_at"],
            "total_rows": int(row["total_rows"] or 0),
            "by_type": by_type,
            "by_type_market": by_type_market,
            "delta_by_type": delta_by_type,
        }
    except Exception:
        cur.execute("""
        SELECT snapshot_at, total_rows, by_type_json, by_type_market_json
        FROM symbol_index_summary
        ORDER BY snapshot_at DESC
        LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            return None
        by_type = json.loads(row["by_type_json"]) if row["by_type_json"] else []
        by_type_market = json.loads(row["by_type_market_json"]) if row["by_type_market_json"] else []
        return {
            "snapshot_at": row["snapshot_at"],
            "total_rows": int(row["total_rows"] or 0),
            "by_type": by_type,
            "by_type_market": by_type_market,
            "delta_by_type": [],
        }

# ---- 健康/维护 ----------------------------------------------------------------
def integrity_check() -> Tuple[bool, str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check;")
    row = cur.fetchone()
    msg = row[0] if row else "unknown"
    ok = (str(msg).lower() == "ok")
    return ok, str(msg)

def vacuum_optimize() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("VACUUM;")
    conn.commit()

def get_usage() -> Dict[str, Any]:
    db_path = Path(settings.db_path)
    size_bytes = db_path.stat().st_size if db_path.exists() else 0
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) AS r FROM candles;"); candles_rows = int(cur.fetchone()["r"])
    cur.execute("SELECT COUNT(1) AS r FROM candles_cache;"); cache_rows = int(cur.fetchone()["r"])
    cur.execute("SELECT COUNT(1) AS r FROM adj_factors;"); factors_rows = int(cur.fetchone()["r"])
    cur.execute("SELECT COUNT(1) AS r FROM symbol_index;"); si_rows = int(cur.fetchone()["r"])
    try:
        cur.execute("SELECT COUNT(1) AS r FROM symbol_index_summary;")
        snap_rows = int(cur.fetchone()["r"])
    except Exception:
        snap_rows = 0
    # 新增：统计 user_watchlist 与 symbol_history 行数（便于前端显示用量）
    try:
        cur.execute("SELECT COUNT(1) AS r FROM user_watchlist;"); wl_rows = int(cur.fetchone()["r"])
    except Exception:
        wl_rows = 0
    try:
        cur.execute("SELECT COUNT(1) AS r FROM symbol_history;"); hist_rows = int(cur.fetchone()["r"])
    except Exception:
        hist_rows = 0
    return {
        "db_path": str(db_path),
        "size_bytes": size_bytes,
        "tables": {
            "candles": candles_rows,
            "candles_cache": cache_rows,
            "adj_factors": factors_rows,
            "symbol_index": si_rows,
            "symbol_index_summary": snap_rows,
            "user_watchlist": wl_rows,
            "symbol_history": hist_rows,
        },
        "checked_at": datetime.now().isoformat(),
    }

def migrate_db_file(new_path: Path) -> Dict[str, Any]:
    import shutil
    global _LOCAL, _GEN

    old_path = Path(settings.db_path).resolve()
    new_path = Path(new_path).resolve()
    new_path.parent.mkdir(parents=True, exist_ok=True)

    if old_path.exists():
        shutil.copy2(str(old_path), str(new_path))
        for suf in ("-wal","-shm"):
            p = old_path.with_suffix(old_path.suffix + suf)
            if p.exists():
                try:
                    shutil.copy2(str(p), str(new_path.with_suffix(new_path.suffix + suf)))
                except Exception:
                    pass
    else:
        conn_new = sqlite3.connect(str(new_path), check_same_thread=False)
        _apply_pragmas(conn_new)
        conn_new.close()

    conn_check = sqlite3.connect(str(new_path), check_same_thread=False)
    _apply_pragmas(conn_check)
    try:
        cur = conn_check.cursor()
        cur.execute("PRAGMA integrity_check;")
        row = cur.fetchone()
        msg = row[0] if row else "unknown"
        ok = (str(msg).lower() == "ok")
    finally:
        conn_check.close()

    if ok:
        _GEN += 1
        old_conn = getattr(_LOCAL, "conn", None)
        if old_conn is not None:
            try:
                old_conn.close()
            except Exception:
                pass
            setattr(_LOCAL, "conn", None)
        setattr(_LOCAL, "gen", _GEN)
        return {"ok": True, "new_path": str(new_path), "msg": "migrated"}
    else:
        return {"ok": False, "new_path": str(new_path), "msg": f"integrity_check failed: {msg}"}

def close_conn() -> None:
    conn = getattr(_LOCAL, "conn", None)
    if conn is not None:
        try:
            conn.commit()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        setattr(_LOCAL, "conn", None)

def ensure_initialized() -> None:
    init_schema()

# -------------------------------
# 新增：用户自选池与标的历史的读写方法
# -------------------------------

def upsert_user_watchlist(rows: Iterable[Tuple[str, str, Optional[str], Optional[str], Optional[str]]]) -> int:
    """
    UPSERT 自选池：
      行结构：(symbol, added_at, source, note, updated_at)
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO user_watchlist(symbol, added_at, source, note, updated_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
      added_at=excluded.added_at,
      source=excluded.source,
      note=excluded.note,
      updated_at=excluded.updated_at;
    """
    cur.executemany(sql, list(rows))
    conn.commit()
    return cur.rowcount

def delete_user_watchlist(symbol: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_watchlist WHERE symbol=?;", (symbol,))
    conn.commit()
    return cur.rowcount

def select_user_watchlist() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol, added_at, source, note, updated_at FROM user_watchlist ORDER BY symbol ASC;")
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def insert_symbol_history(rows: Iterable[Tuple[str, Optional[str], str, Optional[str]]]) -> int:
    """
    追加历史记录：
      行结构：(symbol, freq, selected_at, source)
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = "INSERT INTO symbol_history(symbol, freq, selected_at, source) VALUES (?, ?, ?, ?);"
    cur.executemany(sql, list(rows))
    conn.commit()
    return cur.rowcount

def select_symbol_history(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, int(limit or 50))
    cur.execute("SELECT id, symbol, freq, selected_at, source FROM symbol_history ORDER BY selected_at DESC LIMIT ?;", (lim,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def clear_symbol_history() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM symbol_history;")
    conn.commit()
    return cur.rowcount
