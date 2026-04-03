# backend/db/async_writer.py
# ==============================
# 异步数据库写入队列
#
# 本轮改动：
#   - symbol_profile 批量写入去除逐行 updated_at
#   - 批量快照表同步时间统一由 data_task_status 承担
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, List, Any
from datetime import datetime

from backend.db.connection import get_conn
from backend.db.factors import compress_factor_records
from backend.utils.logger import get_logger

_LOG = get_logger("async_writer")


class AsyncDBWriter:
    """异步数据库写入队列"""

    def __init__(self):
        self.queue = asyncio.Queue(maxsize=1000)
        self.running = False
        self._task = None

        self.candles_buffer: List[Dict[str, Any]] = []
        self.factors_buffer: List[Dict[str, Any]] = []
        self.profiles_buffer: List[Dict[str, Any]] = []

        self.BATCH_SIZE = 500
        self.FLUSH_INTERVAL = 0.5

        self.last_flush_time = 0

    async def start(self):
        if self.running:
            _LOG.warning("[异步写入] 队列已在运行")
            return

        self.running = True
        self._task = asyncio.create_task(self._write_loop())
        _LOG.info("[异步写入] 队列已启动")

    async def stop(self):
        if not self.running:
            return

        _LOG.info("[异步写入] 正在关闭，刷新剩余数据...")

        self.running = False

        try:
            await self._flush_all()
        except Exception as e:
            _LOG.error(f"[异步写入] 关闭时刷新失败: {e}")

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                _LOG.warning("[异步写入] 关闭超时，强制终止")

        _LOG.info("[异步写入] 已安全关闭")

    async def write_candles(self, records: List[Dict[str, Any]]):
        if not records:
            return

        if self.queue.qsize() > 900:
            _LOG.warning(
                f"[异步写入] 队列接近饱和 ({self.queue.qsize()}/1000)，等待刷新..."
            )
            await asyncio.sleep(0.1)

        await self.queue.put(('candles', records))

    async def write_factors(self, records: List[Dict[str, Any]]):
        if not records:
            return

        await self.queue.put(("factors", records))

    async def write_profile(self, records: List[Dict[str, Any]] | Dict[str, Any]):
        if not records:
            return

        if isinstance(records, dict):
            payload = [records]
        else:
            payload = list(records or [])

        if not payload:
            return

        await self.queue.put(("profile", payload))

    async def _write_loop(self):
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                try:
                    table, payload = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=0.1
                    )

                    if table == '__flush__':
                        future = payload
                        try:
                            await self._flush_all()
                        finally:
                            if future is not None and not future.done():
                                future.set_result(True)
                        continue

                    records = payload

                    if table == 'candles':
                        self.candles_buffer.extend(records)
                    elif table == 'factors':
                        self.factors_buffer.extend(records)
                    elif table == 'profile':
                        self.profiles_buffer.extend(records)

                except asyncio.TimeoutError:
                    pass

                now = loop.time()
                should_flush = (
                    len(self.candles_buffer) >= self.BATCH_SIZE or
                    len(self.factors_buffer) >= self.BATCH_SIZE or
                    len(self.profiles_buffer) >= self.BATCH_SIZE or
                    (now - self.last_flush_time) >= self.FLUSH_INTERVAL
                )

                if should_flush and (
                    self.candles_buffer or self.factors_buffer or self.profiles_buffer
                ):
                    await self._flush_all()
                    self.last_flush_time = now

            except Exception as e:
                _LOG.error(f"[异步写入] 循环异常: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _flush_all(self):
        if not (self.candles_buffer or self.factors_buffer or self.profiles_buffer):
            return

        candles_count = len(self.candles_buffer)
        factors_count = len(self.factors_buffer)
        profiles_count = len(self.profiles_buffer)

        try:
            await asyncio.to_thread(self._do_batch_write)

            _LOG.info(
                f"[批量写入] 成功: "
                f"日线={candles_count}, "
                f"因子={factors_count}, "
                f"档案={profiles_count}"
            )

        except Exception as e:
            _LOG.error(f"[批量写入] 失败: {e}", exc_info=True)
            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()

    async def flush(self):
        if not self.running:
            return

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        await self.queue.put(('__flush__', fut))
        await fut

    def _do_batch_write(self):
        conn = get_conn()
        cur = conn.cursor()

        try:
            if self.candles_buffer:
                unique_candles: Dict[tuple, Dict[str, Any]] = {}
                for rec in self.candles_buffer:
                    r = dict(rec)

                    market = str(r.get("market") or "").strip().upper()
                    symbol = str(r.get("symbol") or "").strip()
                    ts = r.get("ts")

                    key = (market, symbol, ts)
                    r["market"] = market
                    r["symbol"] = symbol
                    unique_candles[key] = r

                candles_list = list(unique_candles.values())

                sql_k = """
                INSERT INTO candles_day_raw (
                    market, symbol, ts,
                    open, high, low, close,
                    volume, amount
                )
                VALUES (
                    :market, :symbol, :ts,
                    :open, :high, :low, :close,
                    :volume, :amount
                )
                ON CONFLICT(market, symbol, ts) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    amount=excluded.amount;
                """

                cur.executemany(sql_k, candles_list)

                _LOG.debug(
                    f"[批量写入] 日线: {len(candles_list)} 条 "
                    f"(去重前={len(self.candles_buffer)})"
                )

            if self.factors_buffer:
                unique_factors: Dict[tuple, Dict[str, Any]] = {}
                for rec in self.factors_buffer:
                    key = (rec['symbol'], rec['date'])
                    unique_factors[key] = rec

                factor_list = list(unique_factors.values())
                compressed_list = compress_factor_records(factor_list)

                if compressed_list:
                    now = datetime.now().isoformat()
                    for rec in compressed_list:
                        rec["updated_at"] = now

                    sql_f = """
                    INSERT INTO adj_factors (symbol, date, qfq_factor, hfq_factor, updated_at)
                    VALUES (:symbol, :date, :qfq_factor, :hfq_factor, :updated_at)
                    ON CONFLICT(symbol, date) DO UPDATE SET
                        qfq_factor=excluded.qfq_factor,
                        hfq_factor=excluded.hfq_factor,
                        updated_at=excluded.updated_at;
                    """

                    cur.executemany(sql_f, compressed_list)

                    _LOG.debug(
                        f"[批量写入] 因子: {len(compressed_list)} 条 "
                        f"(原始={len(self.factors_buffer)}, 去重后={len(factor_list)})"
                    )
                else:
                    _LOG.debug("[批量写入] 因子：压缩后无有效记录，跳过写入")

            if self.profiles_buffer:
                unique_profiles: Dict[tuple, Dict[str, Any]] = {}

                for rec in self.profiles_buffer:
                    r = dict(rec)
                    market = str(r.get("market") or "").strip().upper()
                    key = (r.get("symbol"), market)
                    r["market"] = market
                    unique_profiles[key] = r

                profiles_list = list(unique_profiles.values())

                sql_p = """
                INSERT INTO symbol_profile (
                    symbol,
                    market,
                    float_shares,
                    float_value,
                    industry,
                    region,
                    concepts
                )
                VALUES (
                    :symbol,
                    :market,
                    :float_shares,
                    :float_value,
                    :industry,
                    :region,
                    :concepts
                )
                ON CONFLICT(symbol, market) DO UPDATE SET
                    float_shares=COALESCE(excluded.float_shares, symbol_profile.float_shares),
                    float_value=COALESCE(excluded.float_value, symbol_profile.float_value),
                    industry=COALESCE(excluded.industry, symbol_profile.industry),
                    region=COALESCE(excluded.region, symbol_profile.region),
                    concepts=COALESCE(excluded.concepts, symbol_profile.concepts);
                """

                cur.executemany(sql_p, profiles_list)

                _LOG.debug(
                    f"[批量写入] 档案: {len(profiles_list)} 条 "
                    f"(去重前={len(self.profiles_buffer)})"
                )

            conn.commit()

            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()

        except Exception as e:
            conn.rollback()

            _LOG.error(f"[批量写入] 事务失败: {e}", exc_info=True)

            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()

            raise


_writer: AsyncDBWriter = None


def get_async_writer() -> AsyncDBWriter:
    global _writer
    if _writer is None:
        _writer = AsyncDBWriter()
    return _writer
