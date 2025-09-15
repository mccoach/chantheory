// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：用户本地设置（集中默认接入 + 窗长与频率彻底解耦）。
// - 默认值全部来自 constants/index.js；
// - 新增 windowPreset 的持久化（与 freq 解耦）；
// - 其余 API/行为保持不变（跨 Tab 同步/防抖保存）。
// ==============================

import { reactive, toRef, watch } from "vue"; // Vue 响应式 API
import {
  DEFAULT_MA_CONFIGS, // 集中默认：主窗 MA
  DEFAULT_VOL_SETTINGS, // 集中默认：量窗设置
  CHAN_DEFAULTS, // 集中默认：缠论
  DEFAULT_KLINE_STYLE, // 集中默认：K 线样式
  DEFAULT_APP_PREFERENCES, // 集中默认：应用偏好（含 freq/windowPreset 解耦）
} from "@/constants"; // 统一默认入口

const LS_KEY = "chan_user_settings_v1"; // 本地存储键

function loadFromLocal() {
  // 从 localStorage 读取
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveToLocal(obj) {
  // 写回 localStorage
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj));
  } catch {}
}

function debounce(fn, ms = 300) {
  // 简易防抖
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

function mergeMaConfigs(fromLocal) {
  // 合并 MA 设置（本地覆盖默认）
  const defaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
  const local = fromLocal || {};
  Object.keys(defaults).forEach((key) => {
    if (local[key] && typeof local[key] === "object")
      defaults[key] = { ...defaults[key], ...local[key] };
  });
  return defaults;
}

function mergeVolSettings(fromLocal) {
  // 合并量窗设置（本地覆盖默认）
  const def = JSON.parse(JSON.stringify(DEFAULT_VOL_SETTINGS));
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {};
  const out = { ...def, ...loc };

  // 规范 volBar（柱宽范围 10~100）
  out.volBar = { ...def.volBar, ...(loc.volBar || {}) };
  const bp = Number(out.volBar.barPercent);
  out.volBar.barPercent = Number.isFinite(bp)
    ? Math.max(10, Math.min(100, Math.round(bp)))
    : def.volBar.barPercent;
  out.volBar.upColor = String(out.volBar.upColor || def.volBar.upColor);
  out.volBar.downColor = String(out.volBar.downColor || def.volBar.downColor);

  // 规范 MAVOL
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

  // 规范放/缩量标记
  const mp = loc.markerPump || {};
  const md = loc.markerDump || {};
  out.markerPump = { ...def.markerPump, ...mp };
  out.markerDump = { ...def.markerDump, ...md };
  out.markerPump.enabled =
    "enabled" in mp ? !!mp.enabled : def.markerPump.enabled;
  out.markerDump.enabled =
    "enabled" in md ? !!md.enabled : def.markerDump.enabled;

  // 其它字段
  out.mode = out.mode === "amount" ? "amount" : "vol";
  out.unit = out.unit || "auto";
  out.rvolN = Math.max(1, parseInt(out.rvolN || def.rvolN, 10));

  return out;
}

function mergeKlineStyle(fromLocal) {
  // 合并 K 线样式
  const defaults = DEFAULT_KLINE_STYLE;
  return { ...defaults, ...(fromLocal || {}) };
}

let state = null; // 单例状态

export function useUserSettings() {
  if (!state) {
    const local = loadFromLocal();
    state = reactive({
      // 可见设置项（用集中默认回填）
      klineStyle: mergeKlineStyle(local.klineStyle),
      maConfigs: mergeMaConfigs(local.maConfigs),
      volSettings: mergeVolSettings(local.volSettings),
      chanSettings: Object.assign({}, CHAN_DEFAULTS, local.chanSettings || {}),

      // 近期选择（数据窗相关）
      lastSymbol: local.lastSymbol || "",
      lastStart: local.lastStart || "",
      lastEnd: local.lastEnd || "",

      // 快捷键覆盖
      hotkeyOverrides: local.hotkeyOverrides || {},

      // 应用偏好（解耦：freq / windowPreset 各自持久化）
      chartType: local.chartType || DEFAULT_APP_PREFERENCES.chartType,
      freq: local.freq || DEFAULT_APP_PREFERENCES.freq,
      adjust: local.adjust || DEFAULT_APP_PREFERENCES.adjust,
      windowPreset: local.windowPreset || DEFAULT_APP_PREFERENCES.windowPreset,

      // 指标开关持久化
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

      // 可选样式覆盖（图例/线型等个性化）
      styleOverrides: local.styleOverrides || {},
    });

    // 防抖持久化
    const saveDebounced = debounce((s) => saveToLocal(s), 300);
    watch(state, (s) => saveDebounced(s), { deep: true });

    // 跨 Tab 同步（storage 事件）
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
          else if (k in state) state[k] = incoming[k];
        });
      } catch {}
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage);
  }

  // —— Setters（保持原 API，同时新增 setWindowPreset） —— //
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

  // —— 暴露响应式引用 —— //
  return {
    // 状态引用
    klineStyle: toRef(state, "klineStyle"),
    maConfigs: toRef(state, "maConfigs"),
    volSettings: toRef(state, "volSettings"),
    chanSettings: toRef(state, "chanSettings"),
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

    // 方法
    setKlineStyle,
    setMaConfigs,
    updateMa,
    setVolSettings,
    patchVolSettings,
    setChanSettings,
    patchChanSettings,
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
  };
}
