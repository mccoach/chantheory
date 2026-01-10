// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\common\useSettingsRenderer.js
// ==============================
// 说明：通用设置项渲染器（数据驱动）
// - 动机：各设置面板的 renderControl 存在大量重复的 h(Component, ...) 逻辑。
// - 职责：根据配置动态渲染设置控件。
// - 设计：
//   * useSettingsRenderer(rendererConfig): 接收渲染配置对象。
//   * rendererConfig: { [itemKey]: { component, getProps, options/getOptions? } }
//
// V2.0 - NEW: select 使用 children 渲染 options（移除 innerHTML 拼接）
// V2.1 - NEW: 工厂函数（标准化复用，保持显式 get/set，不引入 path 魔法）
//   - makeNativeSelect
//   - makeColorInput
//   - makeNumberSpinner
// ==============================

import { h, defineComponent } from "vue";

/**
 * 标准化 options（用于 select）
 * @param {Array<{v:any,label:any}>} optLike
 * @returns {Array<{v:string,label:string}>}
 */
function normalizeOptions(optLike) {
  const arr = Array.isArray(optLike) ? optLike : [];
  return arr
    .map((x) => {
      if (!x) return null;
      const v = x.v != null ? String(x.v) : "";
      const label = x.label != null ? String(x.label) : v;
      if (!v) return null;
      return { v, label };
    })
    .filter(Boolean);
}

function resolveOptions(config, item) {
  if (!config) return [];
  if (typeof config.getOptions === "function") {
    try {
      return normalizeOptions(config.getOptions(item));
    } catch {
      return [];
    }
  }
  return normalizeOptions(config.options);
}

/**
 * 创建一个数据驱动的通用设置控件渲染器
 * @param {object} rendererConfig
 * @returns {{ renderControl: Function }}
 */
export function useSettingsRenderer(rendererConfig) {
  const renderControl = (row, item) => {
    const itemKey = String(item?.key || "");
    const config = rendererConfig ? rendererConfig[itemKey] : null;

    if (!config || !config.component || typeof config.getProps !== "function") {
      return defineComponent({ setup: () => () => null });
    }

    return defineComponent({
      setup() {
        return () => {
          const props = config.getProps(item) || {};
          const comp = config.component;

          // select：用 children 渲染 option，避免 innerHTML 注入不稳定
          if (String(comp) === "select") {
            const opts = resolveOptions(config, item);
            const children = opts.map((o) => h("option", { value: o.v }, o.label));
            return h("select", props, children);
          }

          return h(comp, props);
        };
      },
    });
  };

  return { renderControl };
}

/* ==============================
 * 工厂函数：标准化复用（保持显式 get/set）
 * ============================== */

/**
 * 原生 select 工厂
 * @param {{
 *  options?: Array<{v:any,label:any}>,
 *  getOptions?: (item:any)=>Array<{v:any,label:any}>,
 *  get: (item:any)=>any,
 *  set: (item:any, v:string)=>void,
 *  className?: string
 * }} args
 */
export function makeNativeSelect(args) {
  const className = args?.className || "input";

  return {
    component: "select",
    options: args?.options,
    getOptions: args?.getOptions,
    getProps: (item) => ({
      class: className,
      value: args.get(item),
      onChange: (e) => args.set(item, e.target.value),
    }),
  };
}

/**
 * 原生颜色输入工厂（input[type=color]）
 * @param {{
 *  get: (item:any)=>string,
 *  set: (item:any, v:string)=>void,
 *  className?: string
 * }} args
 */
export function makeColorInput(args) {
  const className = args?.className || "input color";
  return {
    component: "input",
    getProps: (item) => ({
      class: className,
      type: "color",
      value: args.get(item),
      onInput: (e) => args.set(item, e.target.value),
    }),
  };
}

/**
 * NumberSpinner 工厂（组件由调用方传入，避免本模块引入 UI 组件）
 * @param {{
 *  component: any,
 *  get: (item:any)=>any,
 *  set: (item:any, v:any)=>void,
 *  min?: number,
 *  max?: number,
 *  step?: number,
 *  integer?: boolean,
 *  fracDigits?: number,
 *  extraProps?: object
 * }} args
 */
export function makeNumberSpinner(args) {
  const extra = args?.extraProps && typeof args.extraProps === "object" ? args.extraProps : {};

  const propsBase = {};
  if (Number.isFinite(args?.min)) propsBase.min = args.min;
  if (Number.isFinite(args?.max)) propsBase.max = args.max;
  if (Number.isFinite(args?.step)) propsBase.step = args.step;
  if (args?.integer === true) propsBase.integer = true;
  if (Number.isFinite(args?.fracDigits)) propsBase["frac-digits"] = args.fracDigits;

  return {
    component: args.component,
    getProps: (item) => ({
      modelValue: args.get(item),
      ...propsBase,
      ...extra,
      "onUpdate:modelValue": (v) => args.set(item, v),
    }),
  };
}
