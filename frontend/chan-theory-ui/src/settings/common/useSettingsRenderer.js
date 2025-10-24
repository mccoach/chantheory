// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\common\useSettingsRenderer.js
// ==============================
// 说明：通用设置项渲染器（数据驱动）
// - 动机：各设置面板的 renderControl 函数存在大量重复的 h(Component, ...) 逻辑。
// - 职责：提供一个通用的、可复用的机制，根据配置动态渲染设置控件。
// - 设计：
//   * useSettingsRenderer(rendererConfig): 接收一个渲染配置对象。
//   * rendererConfig: { [itemKey]: { component: VueComponent|string, getProps: (draft) => object } }
// - 返回：{ renderControl(row, item) } 函数，供 SettingsGrid 的槽位使用。
// ==============================

import { h, defineComponent } from "vue";

/**
 * 创建一个数据驱动的通用设置控件渲染器
 * @param {object} rendererConfig - 渲染配置对象
 * @returns {{ renderControl: Function }}
 */
export function useSettingsRenderer(rendererConfig) {
  /**
   * 根据行和项的配置，渲染具体的控件
   * @param {object} row - SettingsGrid 传入的行数据
   * @param {object} item - SettingsGrid 传入的项数据
   * @returns {VNode | null}
   */
  const renderControl = (row, item) => {
    const itemKey = String(item.key || "");
    const config = rendererConfig ? rendererConfig[itemKey] : null;

    if (!config || !config.component || typeof config.getProps !== "function") {
      // 如果没有找到配置，返回一个空的占位组件
      return defineComponent({
        setup: () => () => null,
      });
    }

    // 使用 defineComponent 创建一个动态组件
    return defineComponent({
      setup() {
        // 直接使用 h 函数创建并返回虚拟节点
        // getProps 函数负责从 draft 中读取值并构建 props 对象
        return () => h(config.component, config.getProps(item));
      },
    });
  };

  return { renderControl };
}