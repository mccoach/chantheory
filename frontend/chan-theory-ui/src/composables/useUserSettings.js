// src/composables/useUserSettings.js
// ==============================
// 说明：用户本地设置（全量）
// 本次变更：mergeVolSettings 增加 markerPump/markerDump 的 enabled 规范化与合并。
import { reactive, toRef, watch } from "vue";
import {
  DEFAULT_MA_CONFIGS,
  DEFAULT_VOL_SETTINGS,
  CHAN_DEFAULTS,
} from "@/constants";

const LS_KEY = "chan_user_settings_v1";

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
  const def = JSON.parse(JSON.stringify(DEFAULT_VOL_SETTINGS)); // 深拷贝默认
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {};
  const out = { ...def, ...loc }; // 一次性展开（保留未知字段）

  // 规范 volBar
  out.volBar = { ...def.volBar, ...(loc.volBar || {}) };
  const bp = Number(out.volBar.barPercent);
  out.volBar.barPercent = Number.isFinite(bp)
    ? Math.max(10, Math.min(100, Math.round(bp)))
    : def.volBar.barPercent;
  out.volBar.upColor = String(out.volBar.upColor || def.volBar.upColor);
  out.volBar.downColor = String(out.volBar.downColor || def.volBar.downColor);

  // 规范 MAVOL（三条）
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

  // 规范 markerPump / markerDump：合并+布尔化 enabled
  const mp = loc.markerPump || {};
  const md = loc.markerDump || {};
  out.markerPump = { ...def.markerPump, ...mp };
  out.markerDump = { ...def.markerDump, ...md };
  out.markerPump.enabled =
    "enabled" in mp ? !!mp.enabled : def.markerPump.enabled;
  out.markerDump.enabled =
    "enabled" in md ? !!md.enabled : def.markerDump.enabled;

  // 其它简单字段
  out.mode = out.mode === "amount" ? "amount" : "vol";
  out.unit = out.unit || "auto";
  out.rvolN = Math.max(1, parseInt(out.rvolN || def.rvolN, 10));

  return out;
}

function mergeKlineStyle(fromLocal) {
  const defaults = {
    barPercent: 100,
    upColor: "#f56c6c",
    downColor: "#26a69a",
    subType: "candlestick",
  };
  return { ...defaults, ...(fromLocal || {}) };
}

let state = null;

export function useUserSettings() {
  if (!state) {
    const local = loadFromLocal();
    state = reactive({
      klineStyle: mergeKlineStyle(local.klineStyle),
      maConfigs: mergeMaConfigs(local.maConfigs),
      volSettings: mergeVolSettings(local.volSettings),
      chanSettings: Object.assign({}, CHAN_DEFAULTS, local.chanSettings || {}),
      lastSymbol: local.lastSymbol || "",
      lastStart: local.lastStart || "",
      lastEnd: local.lastEnd || "",
      hotkeyOverrides: local.hotkeyOverrides || {},
      chartType: local.chartType || "kline",
      freq: local.freq || "1d",
      adjust: local.adjust || "none",
      useMACD: typeof local.useMACD === "boolean" ? local.useMACD : true,
      useKDJ: !!local.useKDJ,
      useRSI: !!local.useRSI,
      useBOLL: !!local.useBOLL,
      styleOverrides: local.styleOverrides || {},
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
          else if (k in state) state[k] = incoming[k];
        });
      } catch {}
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage);
  }

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
    if (import.meta.env?.DEV) {
      try {
        console.log("[SETTINGS][setVolSettings][in]", JSON.parse(JSON.stringify(obj)));
      } catch {}
    }
    state.volSettings = mergeVolSettings(obj);
    if (import.meta.env?.DEV) {
      try {
        console.log("[SETTINGS][setVolSettings][out]", JSON.parse(JSON.stringify(state.volSettings)));
      } catch {}
    }
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
    state.freq = f || "1d";
  }
  function setAdjust(adj) {
    state.adjust = adj || "none";
  }
  function setChartType(t) {
    state.chartType = t || "kline";
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

  return {
    klineStyle: toRef(state, "klineStyle"),
    maConfigs: toRef(state, "maConfigs"),
    volSettings: toRef(state, "volSettings"),
    chanSettings: toRef(state, "chanSettings"),
    lastSymbol: toRef(state, "lastSymbol"),
    lastStart: toRef(state, "lastStart"),
    lastEnd: toRef(state, "lastEnd"),
    hotkeyOverrides: toRef(state, "hotkeyOverrides"),
    freq: toRef(state, "freq"),
    adjust: toRef(state, "adjust"),
    chartType: toRef(state, "chartType"),
    useMACD: toRef(state, "useMACD"),
    useKDJ: toRef(state, "useKDJ"),
    useRSI: toRef(state, "useRSI"),
    useBOLL: toRef(state, "useBOLL"),
    styleOverrides: toRef(state, "styleOverrides"),
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
    setUseMACD,
    setUseKDJ,
    setUseRSI,
    setUseBOLL,
    setStyleOverrides,
    updateStyleOverride,
    resetStyleOverride,
  };
}
