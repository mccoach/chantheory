// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：追加历史记录（symbolHistory）
// - 新增 state.symbolHistory: [{symbol:string, ts:number}]（MRU）
// - 新增方法：addSymbolHistoryEntry(symbol)，getSymbolHistoryList()（时间倒序，最大50在消费侧截断）
// 其他原有逻辑不变。
import { reactive, toRef, watch } from "vue"; // 引入 Vue 响应式与工具 API
import {
  DEFAULT_MA_CONFIGS, // MA 默认配置（兜底）
  DEFAULT_VOL_SETTINGS, // 量窗默认配置（兜底）
  CHAN_DEFAULTS, // 缠论默认（兜底）
  DEFAULT_KLINE_STYLE, // K 线样式默认（兜底）
  DEFAULT_APP_PREFERENCES, // 应用偏好默认（兜底）
  FRACTAL_DEFAULTS, // 分型默认（兜底）
} from "@/constants"; // 唯一可信默认来源

// 单文件本地存储键（集中持久化所有用户设置）
const LS_KEY = "chan_user_settings_v1"; // LocalStorage 键名

// 组合键：将 code 与 freq 拼为 "code|freq" 用于视图键（rightTs/viewBars/atRightEdge/lastFocus）
function viewKey(code, freq) {
  const c = String(code || "").trim(); // 规范代码字符串
  const f = String(freq || "").trim(); // 规范频率字符串
  return `${c}|${f}`; // 返回组合键
}

// 读取本地 JSON（失败返回空对象）
function loadFromLocal() {
  try {
    // 保护读取过程
    const raw = localStorage.getItem(LS_KEY); // 读取文本
    return raw ? JSON.parse(raw) : {}; // 解析或返回空对象
  } catch {
    // 解析失败兜底
    return {}; // 返回空对象
  }
}

// 保存到本地 JSON（失败忽略以保证上层逻辑不被阻断）
function saveToLocal(obj) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj));
  } catch {} // 写入字符串
}

// 简单防抖工具：减少频繁保存到 LocalStorage 的开销
function debounce(fn, ms = 300) {
  let t = null; // 定时器句柄
  return (...args) => {
    // 返回防抖包装
    clearTimeout(t); // 清理上一次
    t = setTimeout(() => fn(...args), ms); // 延迟执行
  };
}

// 单例状态对象（全局仅初始化一次）
let state = null; // 单例缓存

// 保留合并器：mergeFractalSettings
function mergeFractalSettings(fromLocal) {
  const def = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS)); // 深拷贝默认（避免引用漂移）
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {}; // 本地对象（容错）

  // 基础平铺浅合并（简化：不做值域规范化，由 UI 控制保证有效性）
  const out = { ...def, ...loc }; // 合并到 out

  // 三档显示开关：按本地优先，缺失回退默认
  out.showStrength = {
    strong: loc?.showStrength?.strong ?? def.showStrength.strong, // 强分型显示
    standard: loc?.showStrength?.standard ?? def.showStrength.standard, // 标准分型显示
    weak: loc?.showStrength?.weak ?? def.showStrength.weak, // 弱分型显示
  };

  // 颜色与形状浅合并（顶层覆盖）
  out.topColors = { ...def.topColors, ...(loc.topColors || {}) }; // 顶分颜色
  out.bottomColors = { ...def.bottomColors, ...(loc.bottomColors || {}) }; // 底分颜色
  out.topShape = loc.topShape ?? def.topShape; // 顶分形状
  out.bottomShape = loc.bottomShape ?? def.bottomShape; // 底分形状

  // 结构化参数浅合并（UI 控件确保数值有效；这里不做强规范化）
  out.minTickCount = loc.minTickCount ?? def.minTickCount; // 最小 tick（保留本地值）
  out.minPct = loc.minPct ?? def.minPct; // 最小百分比（保留本地值）
  out.markerMinPx = loc.markerMinPx ?? def.markerMinPx; // 标记最小宽
  out.markerMaxPx = loc.markerMaxPx ?? def.markerMaxPx; // 标记最大宽
  out.markerYOffsetPx = loc.markerYOffsetPx ?? def.markerYOffsetPx; // 标记与极值间距
  out.enabled = (loc.enabled ?? def.enabled) === true; // 总开关

  // 风格按三档浅合并（启用开关遵循本地优先）
  const sDef = def.styleByStrength || {}; // 默认风格
  const sLoc = loc.styleByStrength || {}; // 本地风格
  out.styleByStrength = {
    strong: {
      bottomShape: sLoc?.strong?.bottomShape ?? sDef?.strong?.bottomShape, // 强-底符号
      bottomColor: sLoc?.strong?.bottomColor ?? sDef?.strong?.bottomColor, // 强-底颜色
      topShape: sLoc?.strong?.topShape ?? sDef?.strong?.topShape, // 强-顶符号
      topColor: sLoc?.strong?.topColor ?? sDef?.strong?.topColor, // 强-顶颜色
      fill: sLoc?.strong?.fill ?? sDef?.strong?.fill, // 强-填充
      enabled: (sLoc?.strong?.enabled ?? sDef?.strong?.enabled) === true, // 强-启用
    },
    standard: {
      bottomShape: sLoc?.standard?.bottomShape ?? sDef?.standard?.bottomShape, // 标-底符号
      bottomColor: sLoc?.standard?.bottomColor ?? sDef?.standard?.bottomColor, // 标-底颜色
      topShape: sLoc?.standard?.topShape ?? sDef?.standard?.topShape, // 标-顶符号
      topColor: sLoc?.standard?.topColor ?? sDef?.standard?.topColor, // 标-顶颜色
      fill: sLoc?.standard?.fill ?? sDef?.standard?.fill, // 标-填充
      enabled: (sLoc?.standard?.enabled ?? sDef?.standard?.enabled) === true, // 标-启用
    },
    weak: {
      bottomShape: sLoc?.weak?.bottomShape ?? sDef?.weak?.bottomShape, // 弱-底符号
      bottomColor: sLoc?.weak?.bottomColor ?? sDef?.weak?.bottomColor, // 弱-底颜色
      topShape: sLoc?.weak?.topShape ?? sDef?.weak?.topShape, // 弱-顶符号
      topColor: sLoc?.weak?.topColor ?? sDef?.weak?.topColor, // 弱-顶颜色
      fill: sLoc?.weak?.fill ?? sDef?.weak?.fill, // 弱-填充
      enabled: (sLoc?.weak?.enabled ?? sDef?.weak?.enabled) === true, // 弱-启用
    },
  };

  // 保留：确认分型样式与“enabled 合并规则”不变（满足不变量令牌）
  const cDef = def.confirmStyle || {}; // 默认确认样式
  const cLoc = loc.confirmStyle || {}; // 本地确认样式
  out.confirmStyle = {
    bottomShape: cLoc.bottomShape ?? cDef.bottomShape, // 底分确认符号
    bottomColor: cLoc.bottomColor ?? cDef.bottomColor, // 底分确认颜色
    topShape: cLoc.topShape ?? cDef.topShape, // 顶分确认符号
    topColor: cLoc.topColor ?? cDef.topColor, // 顶分确认颜色
    fill: cLoc.fill ?? cDef.fill, // 填充方式
    enabled: (cLoc.enabled ?? cDef.enabled) === true, // 关键：本地优先且最终为布尔真（不变量守护）
  };

  return out; // 返回浅合并结果
}

// —— 导出主函数：useUserSettings（最简逻辑） —— //
export function useUserSettings() {
  // 首次调用时初始化单例状态
  if (!state) {
    const local = loadFromLocal(); // 读取本地设置对象
    state = reactive({
      // 建立响应式状态
      // —— 主要设置（默认值 + 浅合并覆盖） —— //
      klineStyle: { ...DEFAULT_KLINE_STYLE, ...(local.klineStyle || {}) }, // K线样式（浅合并）
      maConfigs: { ...DEFAULT_MA_CONFIGS, ...(local.maConfigs || {}) }, // MA 配置（浅合并）
      volSettings: { ...DEFAULT_VOL_SETTINGS, ...(local.volSettings || {}) }, // 量窗设置（浅合并）
      chanSettings: { ...CHAN_DEFAULTS, ...(local.chanSettings || {}) }, // 缠论设置（浅合并）
      fractalSettings: mergeFractalSettings(local.fractalSettings || {}), // 分型设置（保留合并器）

      // —— 近期选择与偏好（浅合并） —— //
      lastSymbol: local.lastSymbol || "", // 最近标的
      lastStart: local.lastStart || "", // 最近起始（占位）
      lastEnd: local.lastEnd || "", // 最近结束（占位）
      hotkeyOverrides: local.hotkeyOverrides || {}, // 快捷键覆盖
      chartType: local.chartType || DEFAULT_APP_PREFERENCES.chartType, // 主图类型
      freq: local.freq || DEFAULT_APP_PREFERENCES.freq, // 默认频率
      adjust: local.adjust || DEFAULT_APP_PREFERENCES.adjust, // 默认复权
      windowPreset: local.windowPreset || DEFAULT_APP_PREFERENCES.windowPreset, // 默认窗宽
      useMACD:
        typeof local.useMACD === "boolean"
          ? local.useMACD
          : DEFAULT_APP_PREFERENCES.useMACD, // MACD 开关
      useKDJ:
        typeof local.useKDJ === "boolean"
          ? local.useKDJ
          : DEFAULT_APP_PREFERENCES.useKDJ, // KDJ 开关
      useRSI:
        typeof local.useRSI === "boolean"
          ? local.useRSI
          : DEFAULT_APP_PREFERENCES.useRSI, // RSI 开关
      useBOLL:
        typeof local.useBOLL === "boolean"
          ? local.useBOLL
          : DEFAULT_APP_PREFERENCES.useBOLL, // BOLL 开关
      styleOverrides: local.styleOverrides || {}, // 样式覆盖集合

      // —— 视图持久化：右端锚点/可视根数/触底状态 —— //
      viewRightTs: local.viewRightTs || {}, // code|freq → rightTs(ms)
      viewBars: local.viewBars || {}, // code|freq → bars(int)
      viewAtRightEdge: local.viewAtRightEdge || {}, // code|freq → boolean（新增）
      // —— 新增：最后聚焦 ts 持久化 —— //
      viewLastFocusTs: local.viewLastFocusTs || {}, // code|freq → ts(ms)

      // —— 新增：指标窗持久化（数组；元素形如 {kind: 'MACD'}；顺序保留） —— //
      indicatorPanes: Array.isArray(local.indicatorPanes)
        ? local.indicatorPanes.map((x) => ({ kind: String(x?.kind || "MACD") }))
        : [],

      // 新增：历史记录（MRU） [{symbol, ts}]
      symbolHistory: Array.isArray(local.symbolHistory)
        ? local.symbolHistory.filter(
            (x) => x && typeof x.symbol === "string" && Number.isFinite(+x.ts)
          )
        : [],
    });

    // 防抖保存，减少 LocalStorage 写开销
    const saveDebounced = debounce((s) => saveToLocal(s), 300); // 构造防抖保存
    watch(state, (s) => saveDebounced(s), { deep: true }); // 深度监听变更即保存

    // 跨窗口/标签 storage 同步：当 LS_KEY 变化时，合并入当前状态（浅合并）
    const onStorage = (e) => {
      if (e.key !== LS_KEY || !e.newValue) return; // 非本键或空跳过
      try {
        const incoming = JSON.parse(e.newValue); // 解析新值
        Object.keys(incoming || {}).forEach((k) => {
          // 遍历合并项
          if (k === "klineStyle")
            state.klineStyle = {
              ...DEFAULT_KLINE_STYLE,
              ...(incoming.klineStyle || {}),
            };
          // 浅合并
          else if (k === "maConfigs")
            state.maConfigs = {
              ...DEFAULT_MA_CONFIGS,
              ...(incoming.maConfigs || {}),
            };
          // 浅合并
          else if (k === "volSettings")
            state.volSettings = {
              ...DEFAULT_VOL_SETTINGS,
              ...(incoming.volSettings || {}),
            };
          // 浅合并
          else if (k === "chanSettings")
            state.chanSettings = {
              ...CHAN_DEFAULTS,
              ...(incoming.chanSettings || {}),
            };
          // 浅合并
          else if (k === "fractalSettings")
            state.fractalSettings = mergeFractalSettings(
              incoming.fractalSettings || {}
            );
          // 合并器
          else if (k === "viewLastFocusTs")
            state.viewLastFocusTs = {
              ...(incoming.viewLastFocusTs || {}),
            };
          // 新增：最后聚焦 ts
          // 新增：指标窗列表（浅合并）
          else if (k === "indicatorPanes")
            state.indicatorPanes = Array.isArray(incoming.indicatorPanes)
              ? incoming.indicatorPanes.map((x) => ({
                  kind: String(x?.kind || "MACD"),
                }))
              : [];
          else if (k === "symbolHistory")
            state.symbolHistory = Array.isArray(incoming.symbolHistory)
              ? incoming.symbolHistory.filter(
                  (x) =>
                    x && typeof x.symbol === "string" && Number.isFinite(+x.ts)
                )
              : [];
          else if (k in state) state[k] = incoming[k];
        });
      } catch {} // 解析失败忽略
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage); // 注册 storage 监听
  }

  // —— Setter/Getter：简化为浅合并（保留正确性由 UI 输入保证），并集中导出 —— //

  // K 线样式：默认 + 覆盖（浅合并）
  function setKlineStyle(obj) {
    state.klineStyle = { ...DEFAULT_KLINE_STYLE, ...(obj || {}) }; // 浅合并赋值
  }

  // MA 配置：默认 + 覆盖（浅合并）
  function setMaConfigs(obj) {
    state.maConfigs = { ...DEFAULT_MA_CONFIGS, ...(obj || {}) }; // 浅合并赋值
  }

  // 单条 MA 的局部更新（若存在该键）
  function updateMa(key, patch) {
    if (state.maConfigs[key])
      state.maConfigs[key] = {
        ...(state.maConfigs[key] || {}),
        ...(patch || {}),
      }; // 浅合并
  }

  // 量窗设置：默认 + 覆盖（浅合并）
  function setVolSettings(obj) {
    state.volSettings = { ...DEFAULT_VOL_SETTINGS, ...(obj || {}) }; // 浅合并赋值
  }

  // 量窗增量 patch（浅合并）
  function patchVolSettings(patch) {
    state.volSettings = { ...(state.volSettings || {}), ...(patch || {}) }; // 浅合并（不做深层规范化）
  }

  // 缠论设置：浅合并（默认 + patch）
  function setChanSettings(obj) {
    state.chanSettings = { ...(state.chanSettings || {}), ...(obj || {}) }; // 浅合并赋值
  }

  // 缠论增量设置：浅合并
  function patchChanSettings(patch) {
    state.chanSettings = { ...(state.chanSettings || {}), ...(patch || {}) }; // 浅合并赋值
  }

  // 分型设置：保留合并器（满足不变量 + 明确 confirmStyle.enabled 约束）
  function setFractalSettings(obj) {
    state.fractalSettings = mergeFractalSettings(obj || {}); // 合并器赋值
  }

  // 近期选择与偏好：直接赋值或浅合并
  function setLastSymbol(s) {
    state.lastSymbol = String(s || "");
  } // 设置最近标的
  function setLastStart(s) {
    state.lastStart = String(s || "");
  } // 设置最近起始（占位）
  function setLastEnd(s) {
    state.lastEnd = String(s || "");
  } // 设置最近结束（占位）

  // 快捷键覆盖：直接赋值（对象）
  function setHotkeyOverrides(overrides) {
    state.hotkeyOverrides = overrides || {};
  } // 设置快捷键覆盖

  // 应用偏好：直接赋值或浅合并
  function setFreq(f) {
    state.freq = f || DEFAULT_APP_PREFERENCES.freq;
  } // 频率
  function setAdjust(adj) {
    state.adjust = adj || DEFAULT_APP_PREFERENCES.adjust;
  } // 复权
  function setChartType(t) {
    state.chartType = t || DEFAULT_APP_PREFERENCES.chartType;
  } // 主图类型
  function setWindowPreset(p) {
    state.windowPreset = p || DEFAULT_APP_PREFERENCES.windowPreset;
  } // 窗宽
  function setUseMACD(v) {
    state.useMACD = !!v;
  } // MACD
  function setUseKDJ(v) {
    state.useKDJ = !!v;
  } // KDJ
  function setUseRSI(v) {
    state.useRSI = !!v;
  } // RSI
  function setUseBOLL(v) {
    state.useBOLL = !!v;
  } // BOLL

  // 样式覆盖：字典浅合并更新
  function setStyleOverrides(obj) {
    state.styleOverrides = obj || {};
  } // 整表覆盖
  function updateStyleOverride(chartKey, seriesName, patch) {
    const ck = String(chartKey || ""),
      sn = String(seriesName || ""); // 规范键
    if (!ck || !sn) return; // 空保护
    const group = { ...(state.styleOverrides[ck] || {}) }; // 读取现组
    group[sn] = { ...(group[sn] || {}), ...(patch || {}) }; // 浅合并
    state.styleOverrides = { ...state.styleOverrides, [ck]: group }; // 写回
  }
  function resetStyleOverride(chartKey, seriesName) {
    const ck = String(chartKey || ""),
      sn = String(seriesName || "");
    if (!ck || !sn) return;
    const group = { ...(state.styleOverrides[ck] || {}) }; // 读取现组
    delete group[sn]; // 删除该系列
    state.styleOverrides = { ...state.styleOverrides, [ck]: group }; // 写回
  }

  // —— 视图持久化：右端锚点/可视根数/触底状态 —— //
  function setRightTs(code, freq, ts) {
    const key = viewKey(code, freq); // 组合键
    const m = { ...(state.viewRightTs || {}) }; // 拷贝映射
    if (ts == null) delete m[key];
    else m[key] = Number(ts); // 写值或删除
    state.viewRightTs = m; // 写回
  }
  function getRightTs(code, freq) {
    const key = viewKey(code, freq); // 组合键
    const val = (state.viewRightTs || {})[key]; // 读取值
    return Number.isFinite(+val) ? +val : null; // 返回毫秒或 null
  }
  function setViewBars(code, freq, bars) {
    const key = viewKey(code, freq); // 组合键
    const m = { ...(state.viewBars || {}) }; // 拷贝映射
    if (!Number.isFinite(+bars) || +bars < 1) delete m[key]; // 非法则删除
    else m[key] = Math.max(1, Math.ceil(+bars)); // 规范为整数下限 1
    state.viewBars = m; // 写回
  }
  function getViewBars(code, freq) {
    const key = viewKey(code, freq); // 组合键
    const val = (state.viewBars || {})[key]; // 读取值
    return Number.isFinite(+val) ? Math.max(1, Math.ceil(+val)) : null; // 返回整数或 null
  }
  // 新增：触底状态持久化（窗口切片右端是否位于全量数据最右端）
  function setAtRightEdge(code, freq, isAtRight) {
    const key = viewKey(code, freq); // 组合键
    const m = { ...(state.viewAtRightEdge || {}) }; // 拷贝映射
    m[key] = !!isAtRight; // 布尔化写入
    state.viewAtRightEdge = m; // 写回
  }
  function getAtRightEdge(code, freq) {
    const key = viewKey(code, freq); // 组合键
    return !!(state.viewAtRightEdge || {})[key]; // 返回布尔值
  }

  // 新增：最后聚焦 ts（跨窗体一致，供键盘移动起点）
  function setLastFocusTs(code, freq, ts) {
    const key = viewKey(code, freq);
    const m = { ...(state.viewLastFocusTs || {}) };
    if (ts == null) delete m[key];
    else m[key] = Number(ts);
    state.viewLastFocusTs = m;
  }
  function getLastFocusTs(code, freq) {
    const key = viewKey(code, freq);
    const val = (state.viewLastFocusTs || {})[key];
    return Number.isFinite(+val) ? +val : null;
  }

  // 新增：指标窗列表持久化（浅合并，记录 kind 与顺序；id 由页面运行时生成）
  function setIndicatorPanes(arr) {
    state.indicatorPanes = Array.isArray(arr)
      ? arr.map((x) => ({ kind: String(x?.kind || "MACD") }))
      : [];
  }
  function getIndicatorPanes() {
    return Array.isArray(state.indicatorPanes)
      ? state.indicatorPanes.map((x) => ({ kind: String(x?.kind || "MACD") }))
      : [];
  }

  // 新增：历史（MRU）
  function addSymbolHistoryEntry(symbol) {
    const sym = String(symbol || "").trim();
    if (!sym) return;
    const nowTs = Date.now();
    const list = Array.isArray(state.symbolHistory)
      ? state.symbolHistory.slice()
      : [];
    const idx = list.findIndex((x) => String(x.symbol || "") === sym);
    if (idx >= 0) list.splice(idx, 1); // 去重
    list.unshift({ symbol: sym, ts: nowTs });
    // 容量控制（保留较大容量以便跨页，但消费侧用 slice(0,50)）
    const MAX_STORE = 200;
    state.symbolHistory = list.slice(0, MAX_STORE);
  }
  function getSymbolHistoryList() {
    const list = Array.isArray(state.symbolHistory)
      ? state.symbolHistory.slice()
      : [];
    // 时间倒序
    return list.sort((a, b) => Number(b.ts || 0) - Number(a.ts || 0));
  }

  // —— 暴露响应式引用与方法（保持原接口名，便于现有调用对接） —— //
  return {
    // 响应式引用（toRef：保留响应特性）
    klineStyle: toRef(state, "klineStyle"),
    maConfigs: toRef(state, "maConfigs"),
    volSettings: toRef(state, "volSettings"),
    chanSettings: toRef(state, "chanSettings"),
    fractalSettings: toRef(state, "fractalSettings"),
    lastSymbol: toRef(state, "lastSymbol"),
    lastStart: toRef(state, "lastStart"),
    lastEnd: toRef(state, "lastEnd"),
    hotkeyOverrides: toRef(state, "hotkeyOverrides"),
    chartType: toRef(state, "chartType"),
    freq: toRef(state, "freq"),
    adjust: toRef(state, "adjust"),
    windowPreset: toRef(state, "windowPreset"),
    useMACD: toRef(state, "useMACD"),
    useKDJ: toRef(state, "useKDJ"),
    useRSI: toRef(state, "useRSI"),
    useBOLL: toRef(state, "useBOLL"),
    styleOverrides: toRef(state, "styleOverrides"),
    viewRightTs: toRef(state, "viewRightTs"),
    viewBars: toRef(state, "viewBars"),
    viewAtRightEdge: toRef(state, "viewAtRightEdge"),
    viewLastFocusTs: toRef(state, "viewLastFocusTs"), // 新增：最后聚焦 ts
    indicatorPanes: toRef(state, "indicatorPanes"), // 新增：指标窗列表
    symbolHistory: toRef(state, "symbolHistory"), // 新增历史

    // Setter/Getter
    setKlineStyle,
    setMaConfigs,
    updateMa,
    setVolSettings,
    patchVolSettings,
    setChanSettings,
    patchChanSettings,
    setFractalSettings,
    setLastSymbol,
    setLastStart,
    setLastEnd,
    setHotkeyOverrides,
    setFreq,
    setAdjust,
    setChartType,
    setWindowPreset,
    setUseMACD,
    setUseKDJ,
    setUseRSI,
    setUseBOLL,
    setStyleOverrides,
    updateStyleOverride,
    resetStyleOverride,
    setRightTs,
    getRightTs,
    setViewBars,
    getViewBars, // 视图锚点/根数
    setAtRightEdge,
    getAtRightEdge, // 触底状态（新增）
    setLastFocusTs, // 新增：最后聚焦 ts
    getLastFocusTs, // 新增：读取最后聚焦 ts
    setIndicatorPanes, // 新增：设置指标窗列表
    getIndicatorPanes, // 新增：读取指标窗列表
    addSymbolHistoryEntry, // 历史
    getSymbolHistoryList,
  };
}
