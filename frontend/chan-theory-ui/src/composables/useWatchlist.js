// frontend/src/composables/useWatchlist.js
// ==============================
// V4.0 - 乐观更新 + 智能同步版
// ==============================

import { ref, readonly } from "vue"
import * as api from "@/services/watchlistService"
import { useEventStream } from "@/composables/useEventStream"

const CACHE_KEY = 'chan_watchlist_v1'
const CACHE_TS_KEY = 'chan_watchlist_ts'
const CACHE_VALID_MS = 24 * 60 * 60 * 1000  // 24小时

const items = ref([])
const loading = ref(false)
const error = ref("")

let _singleton = null

export function useWatchlist() {
  if (_singleton) return _singleton

  const eventStream = useEventStream()

  // ==============================
  // 缓存操作
  // ==============================
  
  function loadFromCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY)
      items.value = raw ? JSON.parse(raw) : []
      console.log(`[自选池] 缓存加载，共 ${items.value.length} 个`)
    } catch {
      items.value = []
    }
  }

  function saveToCache() {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(items.value))
      localStorage.setItem(CACHE_TS_KEY, Date.now().toString())
    } catch {}
  }

  function getCacheAge() {
    try {
      const ts = localStorage.getItem(CACHE_TS_KEY)
      if (!ts) return null
      return Date.now() - Number(ts)
    } catch {
      return null
    }
  }

  // ==============================
  // 智能加载（启动时调用）
  // ==============================
  
  async function smartLoad() {
    // 1. 先读缓存（立即可用）
    loadFromCache()
    
    // 2. 检查新鲜度
    const cacheAge = getCacheAge()
    
    if (cacheAge === null || cacheAge > CACHE_VALID_MS) {
      console.log(`[自选池] 缓存过期，从后端刷新...`)
      await refresh()
    } else {
      const ageMin = Math.floor(cacheAge / 60000)
      console.log(`[自选池] 缓存有效（${ageMin}分钟前更新），跳过刷新`)
    }
  }

  // ==============================
  // SSE 同步（最终一致性保障）
  // ==============================
  
  eventStream.subscribe('watchlist_updated', (data) => {
    items.value = data.items || []
    saveToCache()
    console.log(`[自选池] SSE同步，共 ${items.value.length} 个`)
  })

  // ==============================
  // 后端同步（跨设备/手动刷新）
  // ==============================
  
  async function refresh() {
    loading.value = true
    error.value = ""
    try {
      const data = await api.list()
      items.value = data?.items || []
      saveToCache()
      console.log(`[自选池] 后端同步，共 ${items.value.length} 个`)
    } catch (e) {
      error.value = e?.message || "同步失败"
      console.error('[自选池] 同步失败', e)
    } finally {
      loading.value = false
    }
  }

  // ==============================
  // 核心：乐观更新
  // ==============================
  
  async function addOne(symbol) {
    const sym = String(symbol || "").trim()
    if (!sym) return
    
    // ===== 步骤1：乐观更新（立即生效）=====
    const snapshot = items.value.slice()  // 备份（用于回滚）
    
    // 去重后追加
    const newItems = items.value.filter(item => item.symbol !== sym)
    newItems.push({ 
      symbol: sym, 
      added_at: new Date().toISOString(),
      source: 'manual'
    })
    items.value = newItems
    saveToCache()
    
    console.log(`[自选池] ⚡ 乐观添加 ${sym}（界面已更新）`)
    
    // ===== 步骤2：后台同步（不阻塞）=====
    loading.value = true
    error.value = ""
    
    try {
      await api.add(sym)
      console.log(`[自选池] ✅ 后端确认 ${sym}`)
      // SSE 会推送最终列表，覆盖 items.value
      
    } catch (e) {
      error.value = e?.message || "添加失败"
      console.error(`[自选池] ❌ 后端失败，回滚`, e)
      
      // ===== 步骤3：失败回滚 =====
      items.value = snapshot
      saveToCache()
      
      // 显示错误提示（可选：集成 Toast 组件）
      alert(`添加失败：${e?.message || '网络错误'}`)
      
    } finally {
      loading.value = false
    }
  }

  async function removeOne(symbol) {
    const sym = String(symbol || "").trim()
    if (!sym) return
    
    // ===== 步骤1：乐观删除 =====
    const snapshot = items.value.slice()
    
    items.value = items.value.filter(item => item.symbol !== sym)
    saveToCache()
    
    console.log(`[自选池] ⚡ 乐观删除 ${sym}（界面已更新）`)
    
    // ===== 步骤2：后台同步 =====
    loading.value = true
    error.value = ""
    
    try {
      await api.remove(sym)
      console.log(`[自选池] ✅ 后端确认删除 ${sym}`)
      
    } catch (e) {
      error.value = e?.message || "删除失败"
      console.error(`[自选池] ❌ 后端失败，回滚`, e)
      
      // ===== 步骤3：失败回滚 =====
      items.value = snapshot
      saveToCache()
      
      alert(`删除失败：${e?.message || '网络错误'}`)
      
    } finally {
      loading.value = false
    }
  }
  
  _singleton = {
    items: readonly(items),
    loading: readonly(loading),
    error: readonly(error),
    smartLoad,    // ← 启动时调用
    loadFromCache,
    refresh,
    addOne,
    removeOne,
  }
  
  return _singleton
}