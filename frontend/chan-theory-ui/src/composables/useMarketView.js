// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js
// ==============================
// V14.0 - 第一性原理版（直接绑定，0冗余监听）
// 
// 核心改造：
//   1. 删除 watch(freq)（冗余监听）
//   2. setFreq 内直接调用 reload()（直接绑定）
//   3. 保留必要的 watch（数据依赖）
// 
// 职责：
//   - 管理行情数据（candles/indicators）
//   - 管理加载状态（loading/error）
//   - 提供操作接口（setFreq/reload/...）
// ==============================

import { ref, watch, computed, toRef } from "vue"
import { fetchCandles } from "@/services/marketService"
import { declareCurrent } from "@/services/ensureDataAPI"
import { fetchFactors } from "@/services/factorsAPI"
import { computeIndicators } from "@/composables/engines/indicators"
import { applyAdjustment } from "@/composables/engines/adjustment"
import { useUserSettings } from "@/composables/useUserSettings"
import { useViewCommandHub } from "@/composables/useViewCommandHub"
import { useEventStream } from "@/composables/useEventStream"

let _abortCtl = null
let _lastReqSeq = 0

const hub = useViewCommandHub()
const eventStream = useEventStream()

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false
  const settings = useUserSettings()

  const code = ref(settings.preferences.lastSymbol || "")
  const freq = ref(settings.preferences.freq || "1d")
  const adjust = toRef(settings.preferences, 'adjust')
  
  const loading = ref(false)
  const error = ref("")
  const meta = ref(null)
  const candles = ref([])
  const rawCandles = ref([])
  const factors = ref([])
  const indicators = ref({})

  const chartType = ref(settings.preferences.chartType || "kline")
  const visibleRange = ref({ startStr: "", endStr: "" })
  const displayBars = ref(0)

  const indicatorConfig = computed(() => ({
    maPeriodsMap: (() => {
      const configs = settings.chartDisplay.maConfigs || {}
      return Object.entries(configs).reduce((acc, [key, conf]) => {
        const n = Number(conf?.period)
        if (Number.isFinite(n) && n > 0) acc[key] = n
        return acc
      }, {})
    })(),
    maConfigs: settings.chartDisplay.maConfigs,
    useMACD: settings.preferences.useMACD,
    useKDJ: settings.preferences.useKDJ,
    useRSI: settings.preferences.useRSI,
    useBOLL: settings.preferences.useBOLL,
  }))

  async function reload(opts = {}) {
    if (!code.value) return

    const currentSymbol = code.value
    const currentFreq = freq.value
    const currentAdjust = adjust.value
    const forceRefresh = opts.force_refresh || false

    try { 
      if (_abortCtl) _abortCtl.abort() 
    } catch {}
    const ctl = new AbortController()
    _abortCtl = ctl
    const mySeq = ++_lastReqSeq

    loading.value = true
    error.value = ""

    try {
      console.log(
        `[MarketView] 🚀 声明需求: ${currentSymbol} ${currentFreq}`,
        forceRefresh ? '(强制拉取)' : '(普通拉取)'
      )
      
      const waitPromise = new Promise((resolve, reject) => {
        const pending = new Set(['kline', 'factors'])
        
        let timer = setTimeout(() => {
          unsubscribe()
          console.error(`[MarketView] ⏱️ 超时 ${currentSymbol}|${currentFreq}`)
          reject(new Error('数据拉取超时'))
        }, 30000)
        
        const unsubscribe = eventStream.subscribe('data_ready', (data) => {
          if (data.symbol !== currentSymbol) return
          
          if (data.category === 'kline' && data.freq === currentFreq) {
            pending.delete('kline')
          }
          
          if (data.category === 'factors') {
            pending.delete('factors')
          }
          
          if (pending.size === 0) {
            clearTimeout(timer)
            unsubscribe()
            resolve(data)
          }
        })
        
        declareCurrent(currentSymbol, currentFreq, { 
          force_fetch: forceRefresh
        }).catch(err => {
          unsubscribe()
          clearTimeout(timer)
          reject(err)
        })
      })
      
      await waitPromise
      
      if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
        return
      }
      
      const [candlesRes, factorsRes] = await Promise.all([
        fetchCandles(currentSymbol, currentFreq, { signal: ctl.signal }),
        fetchFactors(currentSymbol)
      ])
      
      if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
        return
      }
      
      meta.value = candlesRes.meta || {}
      rawCandles.value = candlesRes.candles || []
      factors.value = factorsRes || []
      
      if (candlesRes.meta.all_rows > 0) {
        const adjusted = applyAdjustment(
          rawCandles.value, 
          factors.value, 
          currentAdjust
        )
        
        const computed = computeIndicators(adjusted, indicatorConfig.value)
        
        candles.value = adjusted
        indicators.value = computed
        
        const allRows = adjusted.length
        const minTs = adjusted[0]?.ts
        const maxTs = adjusted[allRows - 1]?.ts
        hub.setDatasetBounds({ minTs, maxTs, totalRows: allRows })
        
        error.value = ""
        console.log(`[MarketView] ✅ 加载成功，共 ${allRows} 根K线`)
        
      } else {
        candles.value = []
        indicators.value = {}
        error.value = '暂无数据'
      }
      
      visibleRange.value = {
        startStr: meta.value.start || "",
        endStr: meta.value.end || "",
      }
      displayBars.value = meta.value.view_rows || 0
      
      settings.setFreq(freq.value)
      
    } catch (e) {
      const msg = String(e?.message || "")
      const isAbort = e?.name === "CanceledError" 
        || e?.code === "ERR_CANCELED" 
        || e?.name === "AbortError" 
        || msg.toLowerCase().includes("canceled") 
        || msg.toLowerCase().includes("aborted")
      
      if (isAbort) {
        return
      }
      
      const isTimeout = msg.includes('超时')
      error.value = isTimeout ? '数据拉取超时' : (e?.message || '请求失败')
      candles.value = []
      indicators.value = {}
      console.error('[MarketView] ❌ 加载失败', e)
      
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false
      }
    }
  }

  // ===== 必要监听1：复权变化 → 数据重算 =====
  watch(adjust, () => {
    if (rawCandles.value.length === 0) return
    
    const adjusted = applyAdjustment(
      rawCandles.value, 
      factors.value, 
      adjust.value
    )
    
    candles.value = adjusted
    indicators.value = computeIndicators(adjusted, indicatorConfig.value)
  })

  // ===== 必要监听2：标的变化 → 自动加载 =====
  watch(code, (newCode) => {
    settings.setLastSymbol(newCode || "")
    hub.execute("ChangeSymbol", { symbol: String(newCode || "") })
    if (autoStart) {
      reload({ force_refresh: false })
    }
  })

  // ===== 必要监听3：命令中枢状态 → 更新 displayBars =====
  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1))
  })

  hub.initFromPersist(code.value, freq.value)
  if (autoStart) {
    reload({ force_refresh: false })
  }

  // ===== 核心函数：setFreq（直接绑定完整流程）=====
  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return
    
    // 步骤1：更新响应式状态
    freq.value = newFreq
    
    // 步骤2：持久化
    settings.setFreq(newFreq)
    
    // 步骤3：同步视图状态（更新 UI 显示）
    hub.execute("ChangeFreq", { 
      freq: newFreq,
      allRows: candles.value.length 
    });
    
    // 步骤4：重新加载数据（自动触发渲染）
    reload({ force_refresh: false })
  }

  function applyPreset(preset) {
    const p = String(preset || "ALL")
    settings.setWindowPreset(p)
    const st = hub.getState()
    hub.execute("ChangeWidthPreset", { presetKey: p, allRows: st.allRows })
  }

  function setBars(bars) {
    const b = Math.max(1, Math.floor(Number(bars || 1)))
    hub.execute("SetBarsManual", { nextBars: b })
  }

  function zoomIn() {
    const v = hub.getState().barsCount || 1
    setBars(Math.ceil(v / 1.2))
  }

  function zoomOut() {
    const v = hub.getState().barsCount || 1
    setBars(Math.ceil(v * 1.2))
  }

  return {
    code, freq, adjust, chartType, 
    loading, error, meta, 
    candles, rawCandles, factors, indicators,
    visibleRange, displayBars,
    setFreq, applyPreset, setBars, zoomIn, zoomOut, reload,
    get allRows() { return Number(meta.value?.all_rows ?? 0) },
  }
}