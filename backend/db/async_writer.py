# backend/db/async_writer.py
# ==============================
# 异步数据库写入队列（V1.0）
# 设计目标：
#   1. 单线程写入（彻底避免锁冲突）
#   2. 批量提交（减少fsync次数，提升性能）
#   3. 自动合并（相同键的记录自动去重）
#   4. 优雅关闭（确保数据落盘）
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Tuple
from datetime import datetime
from collections import defaultdict

from backend.db.connection import get_conn
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
        self.candles_buffer = []
        self.factors_buffer = []
        self.profiles_buffer = []
        
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
            records: 因子记录列表
        """
        if not records:
            return
        
        await self.queue.put(('factors', records))
    
    async def write_profile(self, record: Dict[str, Any]):
        """
        提交档案写入请求（异步，立即返回）
        
        Args:
            record: 档案记录字典
        """
        if not record:
            return
        
        await self.queue.put(('profile', [record]))
    
    async def _write_loop(self):
        """写入循环（单线程执行，避免锁竞争）"""
        while self.running:
            try:
                # 等待新任务（超时0.1秒后检查是否需要刷新）
                try:
                    table, records = await asyncio.wait_for(
                        self.queue.get(), 
                        timeout=0.1
                    )
                    
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
                now = asyncio.get_event_loop().time()
                should_flush = (
                    len(self.candles_buffer) >= self.BATCH_SIZE or
                    len(self.factors_buffer) >= self.BATCH_SIZE or
                    len(self.profiles_buffer) >= self.BATCH_SIZE or
                    (now - self.last_flush_time) >= self.FLUSH_INTERVAL
                )
                
                if should_flush and (self.candles_buffer or self.factors_buffer or self.profiles_buffer):
                    await self._flush_all()
                    self.last_flush_time = now
            
            except Exception as e:
                _LOG.error(f"[异步写入] 循环异常: {e}", exc_info=True)
                await asyncio.sleep(0.1)
    
    async def _flush_all(self):
        """批量刷新所有缓冲区"""
        if not (self.candles_buffer or self.factors_buffer or self.profiles_buffer):
            return
        
        # 统计（用于日志）
        candles_count = len(self.candles_buffer)
        factors_count = len(self.factors_buffer)
        profiles_count = len(self.profiles_buffer)
        
        # ===== 关键：在独立线程中执行同步写入 =====
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
    
    def _do_batch_write(self):
        """
        执行批量写入（同步方法，运行在独立线程）
        
        设计要点：
          - 单次数据库连接
          - 单次事务提交
          - 自动去重（K线按 symbol+freq+ts，因子按 symbol+date）
        """
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # ===== 1. 写K线（自动去重）=====
            if self.candles_buffer:
                # 去重：保留最后一次写入（字典推导式，key=唯一键）
                unique_candles = {}
                for rec in self.candles_buffer:
                    key = (rec['symbol'], rec['freq'], rec['ts'])
                    unique_candles[key] = rec
                
                candles_list = list(unique_candles.values())
                
                sql_k = """
                INSERT INTO candles_raw (symbol, freq, ts, open, high, low, close, volume, amount, turnover_rate, source, fetched_at)
                VALUES (:symbol, :freq, :ts, :open, :high, :low, :close, :volume, :amount, :turnover_rate, :source, :fetched_at)
                ON CONFLICT(symbol, freq, ts) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
                    volume=excluded.volume, amount=excluded.amount, turnover_rate=excluded.turnover_rate,
                    source=excluded.source, fetched_at=excluded.fetched_at;
                """
                
                cur.executemany(sql_k, candles_list)
                
                _LOG.debug(
                    f"[批量写入] K线: {len(candles_list)} 条 "
                    f"(去重前={len(self.candles_buffer)})"
                )
            
            # ===== 2. 写因子（自动去重）=====
            if self.factors_buffer:
                # 去重：保留最后一次写入
                unique_factors = {}
                for rec in self.factors_buffer:
                    key = (rec['symbol'], rec['date'])
                    unique_factors[key] = rec
                
                factors_list = list(unique_factors.values())
                
                sql_f = """
                INSERT INTO adj_factors (symbol, date, qfq_factor, hfq_factor, updated_at)
                VALUES (:symbol, :date, :qfq_factor, :hfq_factor, :updated_at)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    qfq_factor=excluded.qfq_factor,
                    hfq_factor=excluded.hfq_factor,
                    updated_at=excluded.updated_at;
                """
                
                cur.executemany(sql_f, factors_list)
                
                _LOG.debug(
                    f"[批量写入] 因子: {len(factors_list)} 条 "
                    f"(去重前={len(self.factors_buffer)})"
                )
            
            # ===== 3. 写档案（自动去重）=====
            if self.profiles_buffer:
                # 去重：保留最后一次写入
                unique_profiles = {}
                for rec in self.profiles_buffer:
                    key = rec['symbol']
                    unique_profiles[key] = rec
                
                profiles_list = list(unique_profiles.values())
                
                sql_p = """
                INSERT INTO symbol_profile (symbol, listing_date, total_shares, float_shares, industry, region, concepts, updated_at)
                VALUES (:symbol, :listing_date, :total_shares, :float_shares, :industry, :region, :concepts, :updated_at)
                ON CONFLICT(symbol) DO UPDATE SET
                    listing_date=COALESCE(excluded.listing_date, symbol_profile.listing_date),
                    total_shares=COALESCE(excluded.total_shares, symbol_profile.total_shares),
                    float_shares=COALESCE(excluded.float_shares, symbol_profile.float_shares),
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