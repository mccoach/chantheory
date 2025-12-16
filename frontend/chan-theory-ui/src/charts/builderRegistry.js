// src/charts/builderRegistry.js
// ==============================
// 说明：图表构造器注册表（适配器模式核心）
// 职责：
//   - 提供统一的 Builder 查询接口
//   - 支持动态注册（运行时扩展）
//   - 支持按需加载（减少初始 bundle 体积）
// 设计：
//   - 单例模式（全局唯一注册表）
//   - 策略模式（每个 kind 对应一个 builder）
//   - 工厂模式（统一的创建接口）
// ==============================

/**
 * Builder 函数签名（统一接口）
 * 
 * @typedef {Function} ChartBuilder
 * @param {Object} data - 数据参数 {candles, indicators, freq, ...}
 * @param {Object} ui - UI参数 {initialRange, tooltipPositioner, isHovered, ...}
 * @returns {Object} ECharts Option 对象
 * 
 * 约定：
 *   - 所有 builder 必须是纯函数（无副作用）
 *   - 参数顺序固定：(data, ui)
 *   - 返回值必须是合法的 ECharts Option
 */

class ChartBuilderRegistry {
  constructor() {
    /** @type {Map<string, ChartBuilder>} 已加载的构造器 */
    this._builders = new Map();
    
    /** @type {Map<string, Function>} 懒加载器（返回 Promise） */
    this._lazyLoaders = new Map();
  }

  /**
   * 注册构造器（立即加载）
   * 
   * @param {string} kind - 图表类型（如 'MAIN', 'VOL', 'MACD'）
   * @param {ChartBuilder} builder - 构造器函数
   * 
   * @example
   *   registry.register('MAIN', buildMainChartOption)
   */
  register(kind, builder) {
    if (typeof builder !== 'function') {
      console.warn(`[ChartRegistry] Invalid builder for '${kind}'`);
      return;
    }
    this._builders.set(String(kind).toUpperCase(), builder);
  }

  /**
   * 注册懒加载构造器（按需加载）
   * 
   * @param {string} kind - 图表类型
   * @param {Function} loader - 返回 Promise<ChartBuilder> 的函数
   * 
   * @example
   *   registry.registerLazy('MACD', () => 
   *     import('./builders/macd').then(m => m.buildMacdOption)
   *   )
   */
  registerLazy(kind, loader) {
    if (typeof loader !== 'function') {
      console.warn(`[ChartRegistry] Invalid loader for '${kind}'`);
      return;
    }
    this._lazyLoaders.set(String(kind).toUpperCase(), loader);
  }

  /**
   * 获取构造器（自动触发懒加载）
   * 
   * @param {string} kind - 图表类型
   * @returns {Promise<ChartBuilder|null>}
   * 
   * 流程：
   *   1. 检查是否已加载 → 直接返回
   *   2. 检查是否有懒加载器 → 触发加载
   *   3. 都没有 → 返回 null
   */
  async get(kind) {
    const key = String(kind).toUpperCase();
    
    // 1. 已加载
    if (this._builders.has(key)) {
      return this._builders.get(key);
    }
    
    // 2. 懒加载
    if (this._lazyLoaders.has(key)) {
      const loader = this._lazyLoaders.get(key);
      try {
        const mod = await loader();
        const builder = mod?.default || mod;
        if (typeof builder === 'function') {
          this._builders.set(key, builder);
          this._lazyLoaders.delete(key);  // 加载后移除 loader
          return builder;
        }
      } catch (e) {
        console.error(`[ChartRegistry] ❌ Failed to load builder '${key}'`, e);
      }
    }
    
    console.warn(`[ChartRegistry] ⚠️ No builder found for '${kind}'`);
    return null;
  }

  /**
   * 批量注册（便捷方法）
   * 
   * @param {Object<string, ChartBuilder>} builders
   * 
   * @example
   *   registry.registerAll({
   *     'MAIN': buildMainChartOption,
   *     'VOL': buildVolumeOption,
   *   })
   */
  registerAll(builders) {
    Object.entries(builders || {}).forEach(([kind, builder]) => {
      this.register(kind, builder);
    });
  }

  /**
   * 检查是否已注册
   * 
   * @param {string} kind
   * @returns {boolean}
   */
  has(kind) {
    const key = String(kind).toUpperCase();
    return this._builders.has(key) || this._lazyLoaders.has(key);
  }

  /**
   * 获取所有已注册类型
   * 
   * @returns {string[]}
   */
  listKinds() {
    const eager = Array.from(this._builders.keys());
    const lazy = Array.from(this._lazyLoaders.keys());
    return [...new Set([...eager, ...lazy])];
  }

  /**
   * 清空注册表（仅用于测试）
   */
  clear() {
    this._builders.clear();
    this._lazyLoaders.clear();
  }
}

// ===== 单例导出 =====
export const chartBuilderRegistry = new ChartBuilderRegistry();

// ===== 类导出（用于类型提示）=====
export { ChartBuilderRegistry };