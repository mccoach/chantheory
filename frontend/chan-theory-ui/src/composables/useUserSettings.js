// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：用户本地设置（集中默认接入 · 替换模式）。
// - 删除旧 viewportState（sIdx/eIdx）机制。
// - 新增：viewRightTs（code|freq → right_ts 毫秒）与 viewBars（code|freq → bars）。
// - 其余 API/行为保持兼容名称但语义按新模式统一（切频/切窗彻底解耦，右端锚定）。
// - 修复：mergeFractalSettings 中 confirmStyle.enabled 合并逻辑，尊重用户设置（不再硬编码为 true）。
// ==============================

import { reactive, toRef, watch } from "vue"; // 引入 Vue 响应式 API
import {
  DEFAULT_MA_CONFIGS, // 主图 MA 默认配置（集中来源）
  DEFAULT_VOL_SETTINGS, // 量窗默认设置（集中来源）
  CHAN_DEFAULTS, // 缠论默认设置（集中来源）
  DEFAULT_KLINE_STYLE, // K 线样式默认（集中来源）
  DEFAULT_APP_PREFERENCES, // 应用偏好默认（含 freq/windowPreset/指标开关）
  FRACTAL_DEFAULTS, // 分型默认（含 markerYOffsetPx 与 confirmStyle）
} from "@/constants"; // 常量统一出口（唯一可信源）

// 本地存储键（单一对象存储所有用户设置）
const LS_KEY = "chan_user_settings_v1"; // LocalStorage 键名

function loadFromLocal() {
  // 从 LocalStorage 读取 JSON，失败则返回空对象
  try {
    const raw = localStorage.getItem(LS_KEY); // 读原始字符串
    return raw ? JSON.parse(raw) : {}; // 解析为对象或空对象
  } catch {
    return {}; // 解析失败回退空对象
  }
}

function saveToLocal(obj) {
  // 将设置对象持久化到 LocalStorage，失败忽略
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj)); // 写入序列化文本
  } catch {}
}

function debounce(fn, ms = 300) {
  // 防抖：减少频繁写 LocalStorage 的开销
  let t = null; // 定时器句柄
  return (...args) => {
    // 返回包装函数
    clearTimeout(t); // 清除上一次定时器
    t = setTimeout(() => fn(...args), ms); // 延迟执行
  };
}

function mergeMaConfigs(fromLocal) {
  // 合并 MA 配置：默认 + 本地覆盖（同键合并）
  const defaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS)); // 深拷贝默认
  const local = fromLocal || {}; // 本地对象
  Object.keys(defaults).forEach((key) => {
    if (local[key] && typeof local[key] === "object")
      // 有本地覆盖且为对象
      defaults[key] = { ...defaults[key], ...local[key] }; // 合并到默认
  });
  return defaults; // 返回合并结果
}

function mergeVolSettings(fromLocal) {
  // 合并量窗设置：默认 + 本地覆盖（层级字段按需合并）
  const def = JSON.parse(JSON.stringify(DEFAULT_VOL_SETTINGS)); // 深拷贝默认
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {}; // 本地对象
  const out = { ...def, ...loc }; // 平铺合并一层
  out.volBar = { ...def.volBar, ...(loc.volBar || {}) }; // 合并 volBar 子对象
  const bp = Number(out.volBar.barPercent); // 柱宽百分比
  out.volBar.barPercent = Number.isFinite(bp)
    ? Math.max(10, Math.min(100, Math.round(bp))) // 规范化范围 10~100
    : def.volBar.barPercent; // 回退默认
  out.volBar.upColor = String(out.volBar.upColor || def.volBar.upColor); // 阳色
  out.volBar.downColor = String(out.volBar.downColor || def.volBar.downColor); // 阴色

  out.mavolStyles = {}; // 构造 MAVOL 样式对象
  for (const k of ["MAVOL5", "MAVOL10", "MAVOL20"]) {
    // 遍历三条 MAVOL
    const d = def.mavolStyles[k]; // 默认配置项
    const v = (loc.mavolStyles && loc.mavolStyles[k]) || {}; // 本地覆盖项
    out.mavolStyles[k] = {
      // 合并并规范化
      enabled: k in (loc.mavolStyles || {}) ? !!v.enabled : d.enabled, // 启用开关
      period: Math.max(1, parseInt(v.period != null ? v.period : d.period, 10)), // 周期整数化
      width: Number.isFinite(+v.width) ? +v.width : d.width, // 线宽
      style: v.style || d.style, // 线型
      color: v.color || d.color, // 颜色
      namePrefix: String(v.namePrefix || d.namePrefix || "MAVOL"), // 名称前缀
    };
  }

  const mp = loc.markerPump || {}; // 放量标记本地
  const md = loc.markerDump || {}; // 缩量标记本地
  out.markerPump = { ...def.markerPump, ...mp }; // 合并放量标记设置
  out.markerDump = { ...def.markerDump, ...md }; // 合并缩量标记设置
  out.markerPump.enabled =
    "enabled" in mp ? !!mp.enabled : def.markerPump.enabled; // 启用规范
  out.markerDump.enabled =
    "enabled" in md ? !!md.enabled : def.markerDump.enabled; // 启用规范

  out.mode = out.mode === "amount" ? "amount" : "vol"; // 模式规范化
  out.unit = out.unit || "auto"; // 单位策略占位
  out.rvolN = Math.max(1, parseInt(out.rvolN || def.rvolN, 10)); // RVOL 基期规范化
  return out; // 返回结果
}

function mergeKlineStyle(fromLocal) {
  // 合并 K 线样式：默认 + 本地覆盖
  const defaults = DEFAULT_KLINE_STYLE; // 默认直接引用
  return { ...defaults, ...(fromLocal || {}) }; // 平铺合并
}

function mergeFractalSettings(fromLocal) {
  // 合并分型设置：默认 + 本地覆盖（含三档样式与确认样式）
  const def = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS)); // 深拷贝默认
  const loc = fromLocal && typeof fromLocal === "object" ? fromLocal : {}; // 本地对象
  const out = { ...def, ...loc }; // 平铺合并基础字段

  out.showStrength = {
    // 三档显示开关（优先本地）
    strong: loc?.showStrength?.strong ?? def.showStrength.strong, // 强
    standard: loc?.showStrength?.standard ?? def.showStrength.standard, // 标准
    weak: loc?.showStrength?.weak ?? def.showStrength.weak, // 弱
  };
  out.topColors = { ...def.topColors, ...(loc.topColors || {}) }; // 顶分颜色合并
  out.bottomColors = { ...def.bottomColors, ...(loc.bottomColors || {}) }; // 底分颜色合并
  out.topShape = loc.topShape || def.topShape; // 顶分形状
  out.bottomShape = loc.bottomShape || def.bottomShape; // 底分形状

  // 显著度参数规范化（最小 tick / 最小百分比 / 判断条件）
  out.minTickCount = Number.isFinite(+loc.minTickCount)
    ? +loc.minTickCount
    : def.minTickCount; // 最小 tick
  out.minPct = Number.isFinite(+loc.minPct) ? +loc.minPct : def.minPct; // 最小幅度 %
  out.markerMinPx = Number.isFinite(+loc.markerMinPx)
    ? +loc.markerMinPx
    : def.markerMinPx; // 标记最小宽
  out.markerMaxPx = Number.isFinite(+loc.markerMaxPx)
    ? +loc.markerMaxPx
    : def.markerMaxPx; // 标记最大宽
  out.markerYOffsetPx = Number.isFinite(+loc.markerYOffsetPx)
    ? +loc.markerYOffsetPx
    : def.markerYOffsetPx; // 与 bar 间距（px）
  out.enabled = (loc.enabled ?? def.enabled) === true; // 总开关（若后续使用）

  const sDef = def.styleByStrength || {}; // 三档样式默认对象
  const sLoc = loc.styleByStrength || {}; // 三档样式本地对象
  out.styleByStrength = {
    // 合并三档样式
    strong: {
      bottomShape: sLoc?.strong?.bottomShape || sDef?.strong?.bottomShape, // 底分符号
      bottomColor: sLoc?.strong?.bottomColor || sDef?.strong?.bottomColor, // 底分颜色
      topShape: sLoc?.strong?.topShape || sDef?.strong?.topShape, // 顶分符号
      topColor: sLoc?.strong?.topColor || sDef?.strong?.topColor, // 顶分颜色
      fill: sLoc?.strong?.fill || sDef?.strong?.fill, // 填充
      enabled: (sLoc?.strong?.enabled ?? sDef?.strong?.enabled) === true, // 启用
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

  const cDef = def.confirmStyle || {}; // 确认分型样式默认
  const cLoc = loc.confirmStyle || {}; // 确认分型样式本地
  out.confirmStyle = {
    // 修复：尊重本地 enabled
    bottomShape: cLoc.bottomShape ?? cDef.bottomShape, // 底分符号
    bottomColor: cLoc.bottomColor ?? cDef.bottomColor, // 底分颜色
    topShape: cLoc.topShape ?? cDef.topShape, // 顶分符号
    topColor: cLoc.topColor ?? cDef.topColor, // 顶分颜色
    fill: cLoc.fill ?? cDef.fill, // 填充方式
    enabled: (cLoc.enabled ?? cDef.enabled) === true, // 关键修复：不再硬编码 true
  };

  return out; // 返回合并后的分型设置对象
}

// NEW: 键（code|freq）用于视图锚点/根数持久化
function viewKey(code, freq) {
  // 将标的代码与频率拼接为键（形如 "600519|1d"）
  const c = String(code || "").trim(); // 规范代码
  const f = String(freq || "").trim(); // 规范频率
  return `${c}|${f}`; // 组合键返回
}

// 单例状态对象（初始化一次）
let state = null; // 用于缓存用户设置响应式对象

export function useUserSettings() {
  // 前端任意处调用该函数，获得单例设置响应式引用与 setter 方法
  if (!state) {
    // 首次调用创建状态
    const local = loadFromLocal(); // 读取本地存储对象
    state = reactive({
      // 构造响应式状态对象
      // 可见设置项（主图/量窗/缠论/分型）
      klineStyle: mergeKlineStyle(local.klineStyle), // K线样式
      maConfigs: mergeMaConfigs(local.maConfigs), // MA 配置
      volSettings: mergeVolSettings(local.volSettings), // 量窗设置
      chanSettings: Object.assign({}, CHAN_DEFAULTS, local.chanSettings || {}), // 缠论设置（简单合并）
      fractalSettings: mergeFractalSettings(local.fractalSettings), // 分型设置（修复 confirmStyle.enabled）

      // 近期选择（数据窗相关）
      lastSymbol: local.lastSymbol || "", // 最近标的代码
      lastStart: local.lastStart || "", // 最近起始日期（占位）
      lastEnd: local.lastEnd || "", // 最近结束日期（占位）

      // 快捷键覆盖（作用域→组合→命令）
      hotkeyOverrides: local.hotkeyOverrides || {}, // 快捷键映射覆盖

      // 应用偏好（切频/切窗解耦）
      chartType: local.chartType || DEFAULT_APP_PREFERENCES.chartType, // 主图类型
      freq: local.freq || DEFAULT_APP_PREFERENCES.freq, // 默认频率
      adjust: local.adjust || DEFAULT_APP_PREFERENCES.adjust, // 默认复权
      windowPreset: local.windowPreset || DEFAULT_APP_PREFERENCES.windowPreset, // 默认窗宽

      // 指标开关（主图副窗）
      useMACD:
        typeof local.useMACD === "boolean"
          ? local.useMACD
          : DEFAULT_APP_PREFERENCES.useMACD, // MACD
      useKDJ:
        typeof local.useKDJ === "boolean"
          ? local.useKDJ
          : DEFAULT_APP_PREFERENCES.useKDJ, // KDJ
      useRSI:
        typeof local.useRSI === "boolean"
          ? local.useRSI
          : DEFAULT_APP_PREFERENCES.useRSI, // RSI
      useBOLL:
        typeof local.useBOLL === "boolean"
          ? local.useBOLL
          : DEFAULT_APP_PREFERENCES.useBOLL, // BOLL

      // 可选样式覆盖（按图表/系列名分组）
      styleOverrides: local.styleOverrides || {}, // 图例/系列样式覆盖集合

      // NEW: 可视窗持久化（右端锚点与根数）
      viewRightTs: local.viewRightTs || {}, // map: key -> right_ts(ms)
      viewBars: local.viewBars || {}, // map: key -> bars
    });

    const saveDebounced = debounce((s) => saveToLocal(s), 300); // 防抖保存 LocalStorage
    watch(state, (s) => saveDebounced(s), { deep: true }); // 深度监听状态变化并保存

    const onStorage = (e) => {
      // 跨标签/窗口同步 LocalStorage
      if (e.key !== LS_KEY || !e.newValue) return; // 非本键或空值跳过
      try {
        const incoming = JSON.parse(e.newValue); // 解析新值
        Object.keys(incoming || {}).forEach((k) => {
          // 遍历合并字段
          if (k === "klineStyle")
            state.klineStyle = mergeKlineStyle(
              incoming.klineStyle
            ); // 合并 K线样式
          else if (k === "maConfigs")
            state.maConfigs = mergeMaConfigs(
              incoming.maConfigs
            ); // 合并 MA 配置
          else if (k === "volSettings")
            state.volSettings = mergeVolSettings(
              incoming.volSettings
            ); // 合并量窗设置
          else if (k === "chanSettings")
            state.chanSettings = Object.assign(
              {},
              CHAN_DEFAULTS,
              incoming.chanSettings || {}
            ); // 缠论设置
          else if (k === "fractalSettings")
            state.fractalSettings = mergeFractalSettings(
              incoming.fractalSettings
            ); // 分型设置（修复生效）
          else if (k in state) state[k] = incoming[k]; // 其它简单字段直接赋值
        });
      } catch {}
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage); // 监听 storage 事件实现跨标签同步
  }

  // —— Setters（写接口） —— //
  function setKlineStyle(obj) {
    state.klineStyle = mergeKlineStyle(obj);
  } // 设置 K 线样式
  function setMaConfigs(obj) {
    state.maConfigs = mergeMaConfigs(obj);
  } // 设置 MA 配置
  function updateMa(key, patch) {
    if (state.maConfigs[key])
      state.maConfigs[key] = { ...state.maConfigs[key], ...patch };
  } // 局部更新 MA

  function setVolSettings(obj) {
    state.volSettings = mergeVolSettings(obj);
  } // 设置量窗配置
  function patchVolSettings(patch) {
    state.volSettings = mergeVolSettings({
      ...state.volSettings,
      ...(patch || {}),
    });
  } // 量窗增量

  function setChanSettings(obj) {
    state.chanSettings = Object.assign({}, state.chanSettings, obj || {});
  } // 设置缠论
  function patchChanSettings(patch) {
    state.chanSettings = Object.assign({}, state.chanSettings, patch || {});
  } // 缠论增量

  function setFractalSettings(obj) {
    state.fractalSettings = mergeFractalSettings(obj || {});
  } // 设置分型（修复生效）

  function setLastSymbol(s) {
    state.lastSymbol = String(s || "");
  } // 设置最近标的
  function setLastStart(s) {
    state.lastStart = String(s || "");
  } // 设置最近起始（占位）
  function setLastEnd(s) {
    state.lastEnd = String(s || "");
  } // 设置最近结束（占位）

  function setHotkeyOverrides(overrides) {
    state.hotkeyOverrides = overrides || {};
  } // 快捷键覆盖设置

  function setFreq(f) {
    state.freq = f || DEFAULT_APP_PREFERENCES.freq;
  } // 设置频率
  function setAdjust(adj) {
    state.adjust = adj || DEFAULT_APP_PREFERENCES.adjust;
  } // 设置复权
  function setChartType(t) {
    state.chartType = t || DEFAULT_APP_PREFERENCES.chartType;
  } // 设置主图类型
  function setWindowPreset(p) {
    state.windowPreset = p || DEFAULT_APP_PREFERENCES.windowPreset;
  } // 设置窗宽

  function setUseMACD(v) {
    state.useMACD = !!v;
  } // 指标开关
  function setUseKDJ(v) {
    state.useKDJ = !!v;
  } // 指标开关
  function setUseRSI(v) {
    state.useRSI = !!v;
  } // 指标开关
  function setUseBOLL(v) {
    state.useBOLL = !!v;
  } // 指标开关

  function setStyleOverrides(obj) {
    state.styleOverrides = obj || {};
  } // 设置样式覆盖集合
  function updateStyleOverride(chartKey, seriesName, patch) {
    // 单系列样式覆盖更新
    const ck = String(chartKey || ""),
      sn = String(seriesName || ""); // 规范键
    if (!ck || !sn) return; // 空参数保护
    const group = { ...(state.styleOverrides[ck] || {}) }; // 读取当前组
    group[sn] = { ...(group[sn] || {}), ...patch }; // 合并补丁
    state.styleOverrides = { ...state.styleOverrides, [ck]: group }; // 写回覆盖集合
  }
  function resetStyleOverride(chartKey, seriesName) {
    // 移除单系列样式覆盖
    const ck = String(chartKey || ""),
      sn = String(seriesName || "");
    if (!ck || !sn) return;
    const group = { ...(state.styleOverrides[ck] || {}) }; // 读取组
    delete group[sn]; // 删除该系列覆盖
    state.styleOverrides = { ...state.styleOverrides, [ck]: group }; // 写回
  }

  // NEW: 右端锚点 / 可视根数 持久化（替换旧 viewportState）
  function setRightTs(code, freq, ts) {
    // 设置右端锚点毫秒
    const key = viewKey(code, freq); // 组合键
    const m = { ...(state.viewRightTs || {}) }; // 复制映射
    if (ts == null) delete m[key]; // 空则删除映射
    else m[key] = Number(ts); // 否则写入毫秒值
    state.viewRightTs = m; // 写回映射
  }
  function getRightTs(code, freq) {
    // 获取右端锚点毫秒
    const key = viewKey(code, freq); // 组合键
    const val = (state.viewRightTs || {})[key]; // 读取值
    return Number.isFinite(+val) ? +val : null; // 正常毫秒返回，否则 null
  }
  function setViewBars(code, freq, bars) {
    // 设置可视根数
    const key = viewKey(code, freq); // 组合键
    const m = { ...(state.viewBars || {}) }; // 复制映射
    if (!Number.isFinite(+bars) || +bars < 1)
      delete m[key]; // 非法 bars 删除映射
    else m[key] = Math.max(1, Math.ceil(+bars)); // bars 规范化为整数下限 1
    state.viewBars = m; // 写回映射
  }
  function getViewBars(code, freq) {
    // 获取可视根数
    const key = viewKey(code, freq); // 组合键
    const val = (state.viewBars || {})[key]; // 读取值
    return Number.isFinite(+val) ? Math.max(1, Math.ceil(+val)) : null; // bars 整数返回，否则 null
  }

  // —— 暴露响应式引用与方法 —— //
  return {
    // 状态引用（toRef 保持响应式）
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

    // 方法（setter）
    setKlineStyle,
    setMaConfigs,
    updateMa,
    setVolSettings,
    patchVolSettings,
    setChanSettings,
    patchChanSettings,
    setFractalSettings, // 修复生效：设置分型
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
