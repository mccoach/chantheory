// src/constants/settingsSchema.js
// ==============================
// 说明：设置配置的领域映射Schema（单一真相源）
// 职责：定义所有配置项的归属域，供 useSettingsManager 查询
// 设计：扁平化映射表，避免硬编码
// ==============================

/**
 * 配置领域映射表（设置存储的分类规则）
 * 
 * 结构：{ domain: [settingsKey1, settingsKey2, ...] }
 * 
 * 用途：
 *   - useSettingsManager 根据 settingsKey 查找所属 domain
 *   - useUserSettings 验证配置项是否合法
 *   - LocalStorage 存储时按 domain 分组
 * 
 * 约定：
 *   - domain 必须是 useUserSettings 的顶层属性
 *   - settingsKey 必须在对应 domain 的 state 中存在
 */
export const SETTINGS_SCHEMA = {
  // ===== 图表显示领域 =====
  chartDisplay: [
    'klineStyle',    // K线样式配置（包括原始K线和合并K线）
    'maConfigs',     // MA均线配置（MA5/MA10/.../MA250）
    'volSettings',   // 量窗设置（成交量/成交额/MAVOL/放缩量标记）
  ],
  
  // ===== 缠论参数领域 =====
  chanTheory: [
    'chanSettings',    // 缠论标记配置（涨跌标记/笔/线段/中枢）
    'fractalSettings', // 分型配置（显著度判定/强度样式/确认分型）
  ],
  
  // ===== 应用偏好领域 =====
  preferences: [
    'lastSymbol',       // 最后查看的标的代码
    'freq',             // 当前频率
    'adjust',           // 复权方式
    'chartType',        // 图表类型
    'windowPreset',     // 窗宽预设
    'useMACD',          // 是否启用MACD
    'useKDJ',           // 是否启用KDJ
    'useRSI',           // 是否启用RSI
    'useBOLL',          // 是否启用BOLL
    'hotkeyOverrides',  // 快捷键覆盖配置
    'styleOverrides',   // 样式覆盖配置
    'indicatorPanes',   // 副图窗口配置
    'symbolHistory',    // 标的浏览历史
  ],
  
  // ===== 视图状态领域 =====
  viewState: [
    'viewRightTs',      // 各标的|频率的右端锚点时间戳
    'viewBars',         // 各标的|频率的可见柱数
    'viewAtRightEdge',  // 各标的|频率的触底状态
    'viewLastFocusTs',  // 各标的|频率的最后聚焦时间戳
  ],
};

/**
 * 根据 settingsKey 查找所属域
 * 
 * @param {string} settingsKey - 配置键名（如 'klineStyle'）
 * @returns {string|null} 域名（如 'chartDisplay'），未找到返回 null
 * 
 * @example
 *   findDomainByKey('klineStyle')  → 'chartDisplay'
 *   findDomainByKey('unknown')     → null
 */
export function findDomainByKey(settingsKey) {
  for (const [domain, keys] of Object.entries(SETTINGS_SCHEMA)) {
    if (keys.includes(settingsKey)) {
      return domain;
    }
  }
  return null;
}

/**
 * 验证配置键是否合法
 * 
 * @param {string} settingsKey - 配置键名
 * @returns {boolean} 是否合法
 * 
 * @example
 *   isValidSettingsKey('klineStyle')  → true
 *   isValidSettingsKey('fooBar')      → false
 */
export function isValidSettingsKey(settingsKey) {
  return findDomainByKey(settingsKey) !== null;
}