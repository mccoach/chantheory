// frontend/src/composables/useEventStream.js
// ==============================
// V8.0 - 统一事件名版
// ==============================

import { ref } from 'vue'

let globalEventSource = null
const eventHandlers = new Map()

export function useEventStream() {
  const connected = ref(false)
  const lastEventTime = ref(null)

  function connect() {
    if (globalEventSource) {
      console.log('[SSE] 连接已存在')
      return
    }

    console.log('[SSE] 正在连接...')
    globalEventSource = new EventSource('/api/events/stream')

    // 连接建立
    globalEventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data)
      console.log('[SSE] ✅ 已连接', data)
      connected.value = true
    })

    // ===== 核心：统一的数据就绪事件 =====
    globalEventSource.addEventListener('data_ready', (e) => {
      const data = JSON.parse(e.data)
      // 增加详细日志
      console.log(`[SSE] 📦 收到原始事件`, {
          raw_data: e.data,  // ← 查看原始JSON
          parsed: data,
          timestamp: new Date().toISOString(),
          current_subscribers: eventHandlers.get('data_ready')?.size || 0  // ← 有几个订阅者
      })
      console.log(`[SSE] 📦 data_ready`, {
        category: data.category,
        symbol: data.symbol,
        freq: data.freq,
        status: data.status
      })
      lastEventTime.value = new Date().toISOString()
      _notifyHandlers('data_ready', data)
    })

    // 自选池更新事件
    globalEventSource.addEventListener('watchlist_updated', (e) => {
      const data = JSON.parse(e.data)
      console.log('[SSE] 📝 watchlist_updated', {
        action: data.action,
        symbol: data.symbol,
        count: data.items?.length
      })
      _notifyHandlers('watchlist_updated', data)
    })

    // 系统告警
    globalEventSource.addEventListener('system_alert', (e) => {
      const data = JSON.parse(e.data)
      console.error('[SSE] 🚨 系统告警', data)
      _notifyHandlers('system_alert', data)
    })

    // 心跳
    globalEventSource.addEventListener('heartbeat', () => {
      lastEventTime.value = new Date().toISOString()
    })

    // 错误处理
    globalEventSource.onerror = (err) => {
      console.warn('[SSE] 连接断开', err)
      connected.value = false
      
      if (globalEventSource) {
        globalEventSource.close()
        globalEventSource = null
      }
      
      setTimeout(connect, 5000)
    }
  }

  function subscribe(eventType, handler) {
    if (!eventHandlers.has(eventType)) {
      eventHandlers.set(eventType, new Set())
    }
    eventHandlers.get(eventType).add(handler)
    
    return () => {
      const handlers = eventHandlers.get(eventType)
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  function _notifyHandlers(eventType, data) {
    const handlers = eventHandlers.get(eventType)
    if (!handlers || handlers.size === 0) return
    
    handlers.forEach(handler => {
      try {
        handler(data)
      } catch (err) {
        console.error(`[SSE] 处理器错误 (${eventType})`, err)
      }
    })
  }

  function disconnect() {
    if (globalEventSource) {
      globalEventSource.close()
      globalEventSource = null
      connected.value = false
    }
  }

  return { connect, disconnect, connected, lastEventTime, subscribe }
}