// frontend/src/composables/useEventStream.js
// ==============================
// 说明：服务端推送事件流管理 (SSE)
// - 建立并维护与后端 /api/events/stream 的长连接。
// - 提供事件订阅接口，供其他 composables 使用。
// ==============================

import { ref, onUnmounted } from 'vue'

// 全局单例 EventSource 连接
let globalEventSource = null
// 事件处理器注册表：{ taskKey: [handler1, handler2, ...] }
const eventHandlers = new Map()

export function useEventStream() {
  const connected = ref(false)
  const lastEventTime = ref(null)

  /**
   * 建立 SSE 连接（全局单例模式）
   */
  function connect() {
    if (globalEventSource) {
      console.log('[SSE] 连接已存在，跳过重复建立')
      return
    }

    // 使用相对路径，开发环境会通过 Vite 代理转发到后端
    const url = '/api/events/stream'
    console.log(`[SSE] 正在连接到 ${url}...`)
    
    globalEventSource = new EventSource(url)

    globalEventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data)
      console.log('[SSE] ✅ 连接已建立', data)
      connected.value = true
    })

    globalEventSource.addEventListener('data_updated', (e) => {
      const data = JSON.parse(e.data)
      console.log('[SSE] 📦 收到数据更新事件', data)
      lastEventTime.value = new Date().toISOString()
      
      // 触发所有注册的处理器
      const key = data.task_key || 'unknown'
      const handlers = eventHandlers.get(key) || []
      console.log(`[SSE] 为 ${key} 触发 ${handlers.length} 个处理器`)
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (err) {
          console.error('[SSE] 处理器执行错误', err)
        }
      })
    })

    globalEventSource.addEventListener('heartbeat', (e) => {
      // 心跳，静默处理
      lastEventTime.value = new Date().toISOString()
    })

    globalEventSource.onerror = (err) => {
      console.warn('[SSE] ⚠️ 连接断开或错误', err)
      connected.value = false
      
      // 清理并重连
      if (globalEventSource) {
        globalEventSource.close()
        globalEventSource = null
      }
      
      console.log('[SSE] 5秒后尝试重连...')
      setTimeout(connect, 5000)
    }
  }

  /**
   * 注册数据更新事件的处理器
   * 
   * @param {string} taskKey - 任务键，如 'candles_600519_1d'
   * @param {function} handler - 处理函数，签名：(eventData) => void
   */
  function onDataUpdated(taskKey, handler) {
    if (!eventHandlers.has(taskKey)) {
      eventHandlers.set(taskKey, [])
    }
    eventHandlers.get(taskKey).push(handler)
    console.log(`[SSE] 注册处理器: ${taskKey}`)
  }

  /**
   * 取消注册（用于组件卸载时清理）
   */
  function offDataUpdated(taskKey, handler) {
    if (eventHandlers.has(taskKey)) {
      const handlers = eventHandlers.get(taskKey)
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  /**
   * 断开连接（慎用，通常应保持全局连接）
   */
  function disconnect() {
    if (globalEventSource) {
      console.log('[SSE] 主动断开连接')
      globalEventSource.close()
      globalEventSource = null
      connected.value = false
    }
  }

  return { 
    connect, 
    disconnect, 
    connected, 
    lastEventTime,
    onDataUpdated, 
    offDataUpdated 
  }
}
