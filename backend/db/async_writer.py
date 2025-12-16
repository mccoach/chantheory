# backend/db/async_writer.py
# ==============================
# 异步数据库写入队列（V2.1 - 因子压缩 + candles.adjust 版）
# 设计目标：
#   1. 单线程写入（彻底避免锁冲突）
#   2. 批量提交（减少fsync次数，提升性能）
#   3. 自动合并（相同键的记录自动去重）
#   4. 优雅关闭（确保数据落盘）
#   5. 复权因子写入前自动压缩（仅保留数值变化的日期）
#   6. NEW：K线写入支持 adjust 维度（'none'/'qfq'/'hfq'），主键为 (symbol,freq,ts,adjust)
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, List, Any
from datetime import datetime

from backend.db.connection import get_conn
from backend.db.factors import compress_factor_records  # 因子压缩工具
from backend.utils.logger import get_logger

_LOG = get_logger("async_writer")


class AsyncDBWriter:
    """异步数据库写入队列"""
    
    def __init__(self):
        # 任务队列（最大1000个待处理任务）
        self.queue = asyncio.Queue(maxsize=1000)
        self.running = False
        self._task = None
        
        # 批量缓冲区（按表分组）
        self.candles_buffer: List[Dict[str, Any]] = []
        self.factors_buffer: List[Dict[str, Any]] = []
        self.profiles_buffer: List[Dict[str, Any]] = []
        
        # 批量阈值配置
        self.BATCH_SIZE = 500  # 每批最多500条记录
        self.FLUSH_INTERVAL = 0.5  # 最多等待0.5秒
        
        self.last_flush_time = 0
    
    async def start(self):
        """启动写入循环"""
        if self.running:
            _LOG.warning("[异步写入] 队列已在运行")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._write_loop())
        _LOG.info("[异步写入] 队列已启动")
    
    async def stop(self):
        """优雅停止（确保数据落盘）"""
        if not self.running:
            return
        
        _LOG.info("[异步写入] 正在关闭，刷新剩余数据...")
        
        self.running = False
        
        # 强制刷新剩余缓冲
        try:
            await self._flush_all()
        except Exception as e:
            _LOG.error(f"[异步写入] 关闭时刷新失败: {e}")
        
        # 等待写入循环结束
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                _LOG.warning("[异步写入] 关闭超时，强制终止")
        
        _LOG.info("[异步写入] 已安全关闭")
    
    async def write_candles(self, records: List[Dict[str, Any]]):
        """
        提交K线写入请求（异步，立即返回）
        
        Args:
            records: K线记录列表
        """
        if not records:
            return
        
        # 检查队列是否接近饱和
        if self.queue.qsize() > 900:
            _LOG.warning(
                f"[异步写入] 队列接近饱和 ({self.queue.qsize()}/1000)，"
                "等待刷新..."
            )
            await asyncio.sleep(0.1)
        
        await self.queue.put(('candles', records))
    
    async def write_factors(self, records: List[Dict[str, Any]]):
        """
        提交因子写入请求（异步，立即返回）
        
        Args:
            records: 因子记录列表（原始稀疏序列，未压缩）
        """
        if not records:
            return
        
        await self.queue.put(('factors', records))
    
    async def write_profile(self, record: Dict[str, Any]):
        """
        提交档案写入请求（异步，立即返回）
        
        Args:
            record: 档案写入字典
        """
        if not record:
            return
        
        await self.queue.put(('profile', [record]))
    
    async def _write_loop(self):
        """写入循环（单线程执行，避免锁竞争）"""
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                # 等待新任务（超时0.1秒后检查是否需要刷新）
                try:
                    table, payload = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=0.1
                    )

                    # 特殊任务：flush 标记
                    if table == '__flush__':
                        future = payload
                        try:
                            await self._flush_all()
                        finally:
                            # 无论 flush 是否异常，都要唤醒等待者，避免死锁
                            if future is not None and not future.done():
                                future.set_result(True)
                        continue

                    records = payload

                    # 加入对应缓冲区
                    if table == 'candles':
                        self.candles_buffer.extend(records)
                    elif table == 'factors':
                        self.factors_buffer.extend(records)
                    elif table == 'profile':
                        self.profiles_buffer.extend(records)
                    
                except asyncio.TimeoutError:
                    # 超时：检查是否需要刷新
                    pass
                
                # 判断是否需要刷新
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
        """批量刷新所有缓冲区"""
        if not (self.candles_buffer or self.factors_buffer or self.profiles_buffer):
            return
        
        candles_count = len(self.candles_buffer)
        factors_count = len(self.factors_buffer)
        profiles_count = len(self.profiles_buffer)
        
        try:
            await asyncio.to_thread(self._do_batch_write)
            
            _LOG.info(
                f"[批量写入] 成功: "
                f"K线={candles_count}, "
                f"因子={factors_count}, "
                f"档案={profiles_count}"
            )
            
        except Exception as e:
            _LOG.error(f"[批量写入] 失败: {e}", exc_info=True)
            # 清空缓冲（避免重复写入损坏数据）
            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()
    
    async def flush(self):
        """
        等待当前队列与缓冲区全部写入数据库。

        行为：
          - 仅在 self.running=True 时有效；未启动时直接返回；
          - 向内部队列投递一个 '__flush__' 标记，并等待其完成；
          - flush 完成时，确保：
              * 所有在 flush 调用之前排入队列的写入任务均已被处理；
              * 缓冲区数据已通过 _do_batch_write() 提交（commit）。
        """
        if not self.running:
            # 写入器未运行时，无待写入任务，直接返回
            return

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        await self.queue.put(('__flush__', fut))
        await fut
    
    def _do_batch_write(self):
        """
        执行批量写入（同步方法，运行在独立线程）
        
        设计要点：
          - 单次数据库连接
          - 单次事务提交
          - 自动去重（K线按 symbol+freq+ts+adjust，因子按 symbol+date）
          - 因子写入前统一压缩，只保留数值变化的记录
        """
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # ===== 1. 写K线（自动去重，带 adjust）=====
            if self.candles_buffer:
                unique_candles: Dict[tuple, Dict[str, Any]] = {}
                now_iso = datetime.now().isoformat()
                for rec in self.candles_buffer:
                    r = dict(rec)

                    # adjust：缺失或为空都视为 'none'
                    if not r.get("adjust"):
                        r["adjust"] = "none"

                    # updated_at：无条件覆盖为本次写入时间
                    # 语义：这条记录“当前这次被写入/更新”的时间戳
                    r["updated_at"] = now_iso

                    key = (r["symbol"], r["freq"], r["ts"], r["adjust"])
                    unique_candles[key] = r
                
                candles_list = list(unique_candles.values())
                
                sql_k = """
                INSERT INTO candles_raw (
                    symbol, freq, ts,
                    open, high, low, close,
                    volume, amount, turnover_rate,
                    source, updated_at, adjust
                )
                VALUES (
                    :symbol, :freq, :ts,
                    :open, :high, :low, :close,
                    :volume, :amount, :turnover_rate,
                    :source, :updated_at, :adjust
                )
                ON CONFLICT(symbol, freq, ts, adjust) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    amount=excluded.amount,
                    turnover_rate=excluded.turnover_rate,
                    source=excluded.source,
                    updated_at=excluded.updated_at;
                """
                
                cur.executemany(sql_k, candles_list)
                
                _LOG.debug(
                    f"[批量写入] K线: {len(candles_list)} 条 "
                    f"(去重前={len(self.candles_buffer)})"
                )
            
            # ===== 2. 写因子（去重 + 压缩）=====
            if self.factors_buffer:
                # 2.1 去重：同 symbol+date 保留最后一条
                unique_factors: Dict[tuple, Dict[str, Any]] = {}
                for rec in self.factors_buffer:
                    key = (rec['symbol'], rec['date'])
                    unique_factors[key] = rec
                
                factor_list = list(unique_factors.values())
                
                # 2.2 压缩：仅保留因子发生变化的记录
                compressed_list = compress_factor_records(factor_list)
                
                if compressed_list:
                    now = datetime.now().isoformat()
                    for rec in compressed_list:
                        # 无条件覆盖为 now
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
                    _LOG.debug(
                        "[批量写入] 因子：压缩后无有效记录，跳过写入"
                    )
            
            # ===== 3. 写档案（自动去重）=====
            if self.profiles_buffer:
                unique_profiles: Dict[str, Dict[str, Any]] = {}
                for rec in self.profiles_buffer:
                    r = dict(rec)
                    # updated_at：无条件覆盖为本次写入时间
                    r["updated_at"] = datetime.now().isoformat()
                    key = r["symbol"]
                    unique_profiles[key] = r
                
                profiles_list = list(unique_profiles.values())
                
                sql_p = """
                INSERT INTO symbol_profile (
                    symbol,
                    total_shares,
                    float_shares,
                    total_value,
                    nego_value,
                    pe_static,
                    industry,
                    region,
                    concepts,
                    updated_at
                )
                VALUES (
                    :symbol,
                    :total_shares,
                    :float_shares,
                    :total_value,
                    :nego_value,
                    :pe_static,
                    :industry,
                    :region,
                    :concepts,
                    :updated_at
                )
                ON CONFLICT(symbol) DO UPDATE SET
                    total_shares=COALESCE(excluded.total_shares, symbol_profile.total_shares),
                    float_shares=COALESCE(excluded.float_shares, symbol_profile.float_shares),
                    total_value=COALESCE(excluded.total_value, symbol_profile.total_value),
                    nego_value=COALESCE(excluded.nego_value, symbol_profile.nego_value),
                    pe_static=COALESCE(excluded.pe_static, symbol_profile.pe_static),
                    industry=COALESCE(excluded.industry, symbol_profile.industry),
                    region=COALESCE(excluded.region, symbol_profile.region),
                    concepts=COALESCE(excluded.concepts, symbol_profile.concepts),
                    updated_at=excluded.updated_at;
                """
                
                cur.executemany(sql_p, profiles_list)
                
                _LOG.debug(
                    f"[批量写入] 档案: {len(profiles_list)} 条 "
                    f"(去重前={len(self.profiles_buffer)})"
                )
            
            # ===== 4. 统一提交（单次fsync）=====
            conn.commit()
            
            # 5. 清空缓冲区
            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()
            
        except Exception as e:
            # 回滚事务
            conn.rollback()
            
            _LOG.error(f"[批量写入] 事务失败: {e}", exc_info=True)
            
            # 清空缓冲区（避免重复写入损坏数据）
            self.candles_buffer.clear()
            self.factors_buffer.clear()
            self.profiles_buffer.clear()
            
            raise


# ===== 全局单例 =====
_writer: AsyncDBWriter = None


def get_async_writer() -> AsyncDBWriter:
    """获取全局异步写入器单例"""
    global _writer
    if _writer is None:
        _writer = AsyncDBWriter()
    return _writer