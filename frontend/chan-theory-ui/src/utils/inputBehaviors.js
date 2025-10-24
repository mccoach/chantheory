// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\inputBehaviors.js
// 统一输入框行为：聚焦自动全选（函数 + Vue 指令）

// 直接函数：传入原生 input/textarea 元素
export function selectAllOnFocus(el) {
  if (!el) return;
  const handler = () => {
    try {
      // 延时 0 以避免某些浏览器在 focus 过程未准备好 selection
      setTimeout(() => el.select(), 0);
    } catch {}
  };
  el.addEventListener("focus", handler);
  // 返回卸载器
  return () => el.removeEventListener("focus", handler);
}

// Vue 指令：v-select-all
export const vSelectAll = {
  mounted(el) {
    // 允许直接用在 input/textarea 或其容器（则自动查找内部可输入元素）
    const target = el.matches("input,textarea")
      ? el
      : el.querySelector("input,textarea");
    selectAllOnFocus(target);
  },
};