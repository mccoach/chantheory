// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：用户本地设置（集中默认接入 · 替换模式）。
// - 删除旧 viewportState（sIdx/eIdx）机制。
// - 新增：viewRightTs（code|freq → right_ts 毫秒）与 viewBars（code|freq → bars）。
// - 其余 API/行为保持兼容名称但语义按新模式统一（切频/切窗彻底解耦，右端锚定）。
// - 本次变更：新增 setFractalSettings，用于保存分型设置（修复主图设置窗保存时报错）。
// ==============================

import { reactive, toRef, watch } from "vue"; // Vue 响应式 API
import {
  DEFAULT_MA_CONFIGS, // 集中默认：主窗 MA
  DEFAULT_VOL_SETTINGS, // 集中默认：量窗设置
  CHAN_DEFAULTS, // 集中默认：缠论
  DEFAULT_KLINE_STYLE, // 集中默认：K 线样式
  DEFAULT_APP_PREFERENCES, // 集中默认：应用偏好（含 freq/windowPreset 解耦）
  FRACTAL_DEFAULTS, // 引入分型默认
} from "@/constants"; // 统一默认入口

const LS_KEY = "chan_user_settings_v1"; // 本地存储键

function loadFromLocal() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}
function saveToLocal(obj) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj));
  } catch {}
}
function debounce(fn, ms = 300) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
function mergeMaConfigs(fromLocal) {
  const defaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
  const local = fromLocal || {};
  Object.keys(defaults).forEach((key) => {
    if (local[key] && typeof local[key] === "object")
      defaults[key] = { ...defaults[key], ...local[key] };
  });
  return defaults;
}
function mergeVolSettings(fromLocal) {
  const def = JSON.parse(JSON.stringify(DEFAULT_VOL_SETTINGS));
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {};
  const out = { ...def, ...loc };
  out.volBar = { ...def.volBar, ...(loc.volBar || {}) };
  const bp = Number(out.volBar.barPercent);
  out.volBar.barPercent = Number.isFinite(bp)
    ? Math.max(10, Math.min(100, Math.round(bp)))
    : def.volBar.barPercent;
  out.volBar.upColor = String(out.volBar.upColor || def.volBar.upColor);
  out.volBar.downColor = String(out.volBar.downColor || def.volBar.downColor);
  out.mavolStyles = {};
  for (const k of ["MAVOL5", "MAVOL10", "MAVOL20"]) {
    const d = def.mavolStyles[k];
    const v = (loc.mavolStyles && loc.mavolStyles[k]) || {};
    out.mavolStyles[k] = {
      enabled: k in (loc.mavolStyles || {}) ? !!v.enabled : d.enabled,
      period: Math.max(1, parseInt(v.period != null ? v.period : d.period, 10)),
      width: Number.isFinite(+v.width) ? +v.width : d.width,
      style: v.style || d.style,
      color: v.color || d.color,
      namePrefix: String(v.namePrefix || d.namePrefix || "MAVOL"),
    };
  }
  const mp = loc.markerPump || {};
  const md = loc.markerDump || {};
  out.markerPump = { ...def.markerPump, ...mp };
  out.markerDump = { ...def.markerDump, ...md };
  out.markerPump.enabled =
    "enabled" in mp ? !!mp.enabled : def.markerPump.enabled;
  out.markerDump.enabled =
    "enabled" in md ? !!md.enabled : def.markerDump.enabled;
  out.mode = out.mode === "amount" ? "amount" : "vol";
  out.unit = out.unit || "auto";
  out.rvolN = Math.max(1, parseInt(out.rvolN || def.rvolN, 10));
  return out;
}
function mergeKlineStyle(fromLocal) {
  const defaults = DEFAULT_KLINE_STYLE;
  return { ...defaults, ...(fromLocal || {}) };
}
function mergeFractalSettings(fromLocal) {
  const def = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS));
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {};
  const out = { ...def, ...loc };
  out.showStrength = {
    strong: loc?.showStrength?.strong ?? def.showStrength.strong,
    standard: loc?.showStrength?.standard ?? def.showStrength.standard,
    weak: loc?.showStrength?.weak ?? def.showStrength.weak,
  };
  out.topColors = { ...def.topColors, ...(loc.topColors || {}) };
  out.bottomColors = { ...def.bottomColors, ...(loc.bottomColors || {}) };
  out.topShape = loc.topShape || def.topShape;
  out.bottomShape = loc.bottomShape || def.bottomShape;
  out.minTickCount = Number.isFinite(+loc.minTickCount)
    ? +loc.minTickCount
    : def.minTickCount;
  out.minPct = Number.isFinite(+loc.minPct) ? +loc.minPct : def.minPct;
  out.markerMinPx = Number.isFinite(+loc.markerMinPx)
    ? +loc.markerMinPx
    : def.markerMinPx;
  out.markerMaxPx = Number.isFinite(+loc.markerMaxPx)
    ? +loc.markerMaxPx
    : def.markerMaxPx;
  out.markerYOffsetPx = Number.isFinite(+loc.markerYOffsetPx)
    ? +loc.markerYOffsetPx
    : def.markerYOffsetPx;
  out.enabled = (loc.enabled ?? def.enabled) === true;
  out.showConfirmLink = (loc.showConfirmLink ?? def.showConfirmLink) === true;
  const sDef = def.styleByStrength || {};
  const sLoc = loc.styleByStrength || {};
  out.styleByStrength = {
    strong: {
      bottomShape: sLoc?.strong?.bottomShape || sDef?.strong?.bottomShape,
      bottomColor: sLoc?.strong?.bottomColor || sDef?.strong?.bottomColor,
      topShape: sLoc?.strong?.topShape || sDef?.strong?.topShape,
      topColor: sLoc?.strong?.topColor || sDef?.strong?.topColor,
      fill: sLoc?.strong?.fill || sDef?.strong?.fill,
      enabled: (sLoc?.strong?.enabled ?? sDef?.strong?.enabled) === true,
    },
    standard: {
      bottomShape: sLoc?.standard?.bottomShape || sDef?.standard?.bottomShape,
      bottomColor: sLoc?.standard?.bottomColor || sDef?.standard?.bottomColor,
      topShape: sLoc?.standard?.topShape || sDef?.standard?.topShape,
      topColor: sLoc?.standard?.topColor || sDef?.standard?.topColor,
      fill: sLoc?.standard?.fill || sDef?.standard?.fill,
      enabled: (sLoc?.standard?.enabled ?? sDef?.standard?.enabled) === true,
    },
    weak: {
      bottomShape: sLoc?.weak?.bottomShape || sDef?.weak?.bottomShape,
      bottomColor: sLoc?.weak?.bottomColor || sDef?.weak?.bottomColor,
      topShape: sLoc?.weak?.topShape || sDef?.weak?.topShape,
      topColor: sLoc?.weak?.topColor || sDef?.weak?.topColor,
      fill: sLoc?.weak?.fill || sDef?.weak?.fill,
      enabled: (sLoc?.weak?.enabled ?? sDef?.weak?.enabled) === true,
    },
  };
  const cDef = def.confirmStyle || {};
  const cLoc = loc.confirmStyle || {};
  out.confirmStyle = {
    bottomShape: cLoc.bottomShape ?? cDef.bottomShape,
    bottomColor: cLoc.bottomColor ?? cDef.bottomColor,
    topShape: cLoc.topShape ?? cDef.topShape,
    topColor: cLoc.topColor ?? cDef.topColor,
    fill: cLoc.fill ?? cDef.fill,
    enabled: true,
  };
  return out;
}

// NEW: 键（code|freq）用于视图锚点/根数持久化
function viewKey(code, freq) {
  const c = String(code || "").trim();
  const f = String(freq || "").trim();
  return `${c}|${f}`;
}

let state = null; // 单例状态

export function useUserSettings() {
  if (!state) {
    const local = loadFromLocal();
    state = reactive({
      // 可见设置项
      klineStyle: mergeKlineStyle(local.klineStyle),
      maConfigs: mergeMaConfigs(local.maConfigs),
      volSettings: mergeVolSettings(local.volSettings),
      chanSettings: Object.assign({}, CHAN_DEFAULTS, local.chanSettings || {}),
      fractalSettings: mergeFractalSettings(local.fractalSettings),

      // 近期选择（数据窗相关）
      lastSymbol: local.lastSymbol || "",
      lastStart: local.lastStart || "",
      lastEnd: local.lastEnd || "",

      // 快捷键覆盖
      hotkeyOverrides: local.hotkeyOverrides || {},

      // 应用偏好（切频/切窗解耦）
      chartType: local.chartType || DEFAULT_APP_PREFERENCES.chartType,
      freq: local.freq || DEFAULT_APP_PREFERENCES.freq,
      adjust: local.adjust || DEFAULT_APP_PREFERENCES.adjust,
      windowPreset: local.windowPreset || DEFAULT_APP_PREFERENCES.windowPreset,

      // 指标开关
      useMACD:
        typeof local.useMACD === "boolean"
          ? local.useMACD
          : DEFAULT_APP_PREFERENCES.useMACD,
      useKDJ:
        typeof local.useKDJ === "boolean"
          ? local.useKDJ
          : DEFAULT_APP_PREFERENCES.useKDJ,
      useRSI:
        typeof local.useRSI === "boolean"
          ? local.useRSI
          : DEFAULT_APP_PREFERENCES.useRSI,
      useBOLL:
        typeof local.useBOLL === "boolean"
          ? local.useBOLL
          : DEFAULT_APP_PREFERENCES.useBOLL,

      // 可选样式覆盖
      styleOverrides: local.styleOverrides || {},

      // NEW: 右端锚点/可视根数（替换旧 viewportState）
      viewRightTs: local.viewRightTs || {}, // map: key -> right_ts(ms)
      viewBars: local.viewBars || {}, // map: key -> bars
    });

    const saveDebounced = debounce((s) => saveToLocal(s), 300);
    watch(state, (s) => saveDebounced(s), { deep: true });

    const onStorage = (e) => {
      if (e.key !== LS_KEY || !e.newValue) return;
      try {
        const incoming = JSON.parse(e.newValue);
        Object.keys(incoming || {}).forEach((k) => {
          if (k === "klineStyle")
            state.klineStyle = mergeKlineStyle(incoming.klineStyle);
          else if (k === "maConfigs")
            state.maConfigs = mergeMaConfigs(incoming.maConfigs);
          else if (k === "volSettings")
            state.volSettings = mergeVolSettings(incoming.volSettings);
          else if (k === "chanSettings")
            state.chanSettings = Object.assign(
              {},
              CHAN_DEFAULTS,
              incoming.chanSettings || {}
            );
          else if (k === "fractalSettings")
            state.fractalSettings = mergeFractalSettings(
              incoming.fractalSettings
            );
          else if (k in state) state[k] = incoming[k];
        });
      } catch {}
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage);
  }

  // —— Setters —— //
  function setKlineStyle(obj) {
    state.klineStyle = mergeKlineStyle(obj);
  }
  function setMaConfigs(obj) {
    state.maConfigs = mergeMaConfigs(obj);
  }
  function updateMa(key, patch) {
    if (state.maConfigs[key])
      state.maConfigs[key] = { ...state.maConfigs[key], ...patch };
  }
  function setVolSettings(obj) {
    state.volSettings = mergeVolSettings(obj);
  }
  function patchVolSettings(patch) {
    state.volSettings = mergeVolSettings({
      ...state.volSettings,
      ...(patch || {}),
    });
  }
  function setChanSettings(obj) {
    state.chanSettings = Object.assign({}, state.chanSettings, obj || {});
  }
  function patchChanSettings(patch) {
    state.chanSettings = Object.assign({}, state.chanSettings, patch || {});
  }
  // 新增：设置分型参数
  function setFractalSettings(obj) {
    state.fractalSettings = mergeFractalSettings(obj || {});
  }

  function setLastSymbol(s) {
    state.lastSymbol = String(s || "");
  }
  function setLastStart(s) {
    state.lastStart = String(s || "");
  }
  function setLastEnd(s) {
    state.lastEnd = String(s || "");
  }

  function setHotkeyOverrides(overrides) {
    state.hotkeyOverrides = overrides || {};
  }

  function setFreq(f) {
    state.freq = f || DEFAULT_APP_PREFERENCES.freq;
  }
  function setAdjust(adj) {
    state.adjust = adj || DEFAULT_APP_PREFERENCES.adjust;
  }
  function setChartType(t) {
    state.chartType = t || DEFAULT_APP_PREFERENCES.chartType;
  }
  function setWindowPreset(p) {
    state.windowPreset = p || DEFAULT_APP_PREFERENCES.windowPreset;
  }

  function setUseMACD(v) {
    state.useMACD = !!v;
  }
  function setUseKDJ(v) {
    state.useKDJ = !!v;
  }
  function setUseRSI(v) {
    state.useRSI = !!v;
  }
  function setUseBOLL(v) {
    state.useBOLL = !!v;
  }

  function setStyleOverrides(obj) {
    state.styleOverrides = obj || {};
  }
  function updateStyleOverride(chartKey, seriesName, patch) {
    const ck = String(chartKey || ""),
      sn = String(seriesName || "");
    if (!ck || !sn) return;
    const group = { ...(state.styleOverrides[ck] || {}) };
    group[sn] = { ...(group[sn] || {}), ...patch };
    state.styleOverrides = { ...state.styleOverrides, [ck]: group };
  }
  function resetStyleOverride(chartKey, seriesName) {
    const ck = String(chartKey || ""),
      sn = String(seriesName || "");
    if (!ck || !sn) return;
    const group = { ...(state.styleOverrides[ck] || {}) };
    delete group[sn];
    state.styleOverrides = { ...state.styleOverrides, [ck]: group };
  }

  // NEW: 右端锚点 / 可视根数 持久化
  function setRightTs(code, freq, ts) {
    const key = viewKey(code, freq);
    const m = { ...(state.viewRightTs || {}) };
    if (ts == null) delete m[key];
    else m[key] = Number(ts);
    state.viewRightTs = m;
  }
  function getRightTs(code, freq) {
    const key = viewKey(code, freq);
    const val = (state.viewRightTs || {})[key];
    return Number.isFinite(+val) ? +val : null;
  }
  function setViewBars(code, freq, bars) {
    const key = viewKey(code, freq);
    const m = { ...(state.viewBars || {}) };
    if (!Number.isFinite(+bars) || +bars < 1) delete m[key];
    else m[key] = Math.max(1, Math.ceil(+bars));
    state.viewBars = m;
  }
  function getViewBars(code, freq) {
    const key = viewKey(code, freq);
    const val = (state.viewBars || {})[key];
    return Number.isFinite(+val) ? Math.max(1, Math.ceil(+val)) : null;
  }

  // —— 暴露响应式引用与方法 —— //
  return {
    // 状态引用
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
    // NEW: 右端锚点/可视根数
    viewRightTs: toRef(state, "viewRightTs"),
    viewBars: toRef(state, "viewBars"),

    // 方法
    setKlineStyle,
    setMaConfigs,
    updateMa,
    setVolSettings,
    patchVolSettings,
    setChanSettings,
    patchChanSettings,
    setFractalSettings, // 新增导出
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

    // NEW: 右端锚点/根数 API
    setRightTs,
    getRightTs,
    setViewBars,
    getViewBars,
  };
}
