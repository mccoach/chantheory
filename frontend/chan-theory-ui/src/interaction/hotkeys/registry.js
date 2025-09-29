// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\hotkeys\registry.js
// ==============================
// 说明：热键服务（作用域栈 + 键位映射 + 命令处理 + 内置默认行为）
// 变更点：扩展输入白名单，允许在输入框内触发额外组合（Ctrl+Comma / F1 / Alt+R / Alt+E / ArrowDown / ArrowUp / Enter）。
// ==============================

import { ref } from "vue"; // 引入响应式
import { toCombo, isReservedBrowserCombo } from "./core.js"; // 引入归一化与保留判断

export class HotkeyService {
  // 定义热键服务类
  constructor(defaultKeymap) {
    // 构造函数
    this.defaultKeymap = defaultKeymap || {}; // 默认键位映射
    this.userOverrides = {}; // 用户覆盖（scope -> combo -> command）
    this.handlers = {}; // 命令处理器（scope -> command -> fn）
    this.scopeStack = ref(["global"]); // 作用域栈（顶层优先，默认 global）
    this.ui = { showSettings: ref(false) }; // UI 状态：设置弹窗显隐
    this._onKeydown = this._onKeydown.bind(this); // 绑定 this
    window.addEventListener("keydown", this._onKeydown, {
      // 注册键盘监听（捕获阶段）
      capture: true,
    });
  } // 结束构造

  destroy() {
    // 销毁（移除监听）
    window.removeEventListener("keydown", this._onKeydown, { capture: true });
  } // 结束销毁

  get keymap() {
    // 计算属性：合并后的键位表
    const merged = {}; // 合并结果
    const scopes = new Set([
      // 所有 scope（默认 + 覆盖）
      ...Object.keys(this.defaultKeymap),
      ...Object.keys(this.userOverrides || {}),
    ]); // 结束集合
    scopes.forEach((s) => {
      // 遍历 scope
      merged[s] = Object.assign(
        // 合并（默认优先，覆盖后应用）
        {},
        this.defaultKeymap[s] || {},
        this.userOverrides[s] || {}
      );
    }); // 结束遍历
    return merged; // 返回合并映射
  } // 结束 keymap

  registerHandlers(scope, map) {
    // 注册命令处理器
    this.handlers[scope] = Object.assign(
      // 覆盖追加
      {},
      this.handlers[scope] || {},
      map || {}
    );
  } // 结束注册

  unregisterHandlers(scope) {
    // 注销某 scope 处理器
    delete this.handlers[scope]; // 删除映射
  } // 结束注销

  pushScope(scope) {
    // 压入作用域
    const s = this.scopeStack.value.slice(); // 拷贝当前栈
    s.push(scope); // 追加
    this.scopeStack.value = s; // 写回
  } // 结束 pushScope

  popScope(scope) {
    // 弹出作用域
    if (!scope) {
      // 无参数：弹最顶层（保留 global）
      const s = this.scopeStack.value.slice(); // 拷贝
      if (s.length > 1) s.pop(); // 弹出顶层
      this.scopeStack.value = s; // 写回
      return; // 返回
    } // 结束无参分支
    const s = this.scopeStack.value.filter((x) => x !== scope); // 过滤指定 scope
    if (!s.length) s.push("global"); // 保底 global
    this.scopeStack.value = s; // 写回
  } // 结束 popScope

  setBinding(scope, command, combo) {
    // 设置单条覆盖（命令→组合）
    const km = this._invert(this.keymap[scope] || {}); // 反转映射（combo->cmd → cmd->combo）
    Object.keys(this.userOverrides[scope] || {}).forEach((c) => {
      // 删除旧绑定
      if ((this.userOverrides[scope] || {})[c] === command)
        // 同命令
        delete this.userOverrides[scope][c]; // 删除
    });
    if (combo) {
      // 设置新组合
      this.userOverrides[scope] = this.userOverrides[scope] || {};
      this.userOverrides[scope][combo] = command; // 赋值
    }
  } // 结束 setBinding

  setUserOverrides(overrides) {
    // 设置整表覆盖
    this.userOverrides = overrides || {}; // 覆盖
  } // 结束 setUserOverrides

  getBindings(scope) {
    // 获取“命令 → 组合”视图
    const merged = this.keymap[scope] || {}; // 合并映射
    return this._invert(merged); // 反转（返回 cmd->combo）
  } // 结束 getBindings

  _invert(obj) {
    // 反转 {a:b} → {b:a}
    const out = {}; // 结果
    Object.keys(obj || {}).forEach((k) => (out[obj[k]] = k)); // 遍历反转
    return out; // 返回
  } // 结束 _invert

  focusNextPrev(dir = +1) {
    // 默认行为：在输入可聚焦元素间切换
    const candidates = Array.from(
      // 查找可见可用输入控件
      document.querySelectorAll(
        'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [contenteditable="true"]'
      )
    ).filter((el) => {
      // 过滤不可见
      const rs = getComputedStyle(el); // 读取样式
      return (
        rs.display !== "none" &&
        rs.visibility !== "hidden" &&
        el.offsetParent !== null
      );
    }); // 结束过滤
    if (!candidates.length) return; // 无可用项
    const active = document.activeElement; // 当前聚焦
    let idx = candidates.indexOf(active); // 索引
    idx = idx < 0 ? (dir > 0 ? -1 : 0) : idx; // 初始位置
    const next =
      candidates[(idx + dir + candidates.length) % candidates.length]; // 计算下一个
    if (next && typeof next.focus === "function") next.focus(); // 聚焦
  } // 结束 focusNextPrev

  _onKeydown(e) {
    // 全局 keydown 处理
    const combo = toCombo(e); // 组合规范化
    if (!combo) return; // 无组合 → 忽略

    if (isReservedBrowserCombo(e)) return; // 浏览器保留 → 放行

    const tag = ((e.target && e.target.tagName) || "").toLowerCase(); // 标签名
    const inInput =
      tag === "input" ||
      tag === "textarea" ||
      (e.target && e.target.isContentEditable); // 是否输入环境
    const inputWhitelist = new Set([
      // 输入环境白名单组合
      "Escape", // 取消
      "Ctrl+Enter", // 确认
      "Meta+Enter", // 确认（Mac）
      "Tab", // 下一个输入
      "Shift+Tab", // 上一个输入
      "Ctrl+Right", // 快速跳转下一个输入
      "Ctrl+Left", // 快速跳转上一个输入
      "Ctrl+Comma", // 打开设置
      "F1", // 帮助/设置
      "Alt+R", // 刷新
      "Alt+E", // 导出菜单
      "ArrowDown", // 下拉下移
      "ArrowUp", // 下拉上移
      "Enter", // 确认
      "ArrowLeft", // 键盘向左
      "ArrowRight", // 键盘向右
    ]); // 结束白名单
    if (inInput && !inputWhitelist.has(combo)) return; // 输入环境且不在白名单 → 忽略

    const stack = [...this.scopeStack.value].reverse(); // 作用域（顶层优先）
    for (const scope of stack) {
      // 逐层匹配
      const map = this.keymap[scope] || {}; // 合并映射
      const cmd = map[combo]; // 查命令
      if (!cmd) continue; // 未映射 → 下一个

      const handler =
        (this.handlers[scope] || {})[cmd] || // 先找当前作用域
        (this.handlers["global"] || {})[cmd]; // 再找 global

      if (!handler) {
        // 没有处理器 → 尝试内置
        if (cmd === "focusNextField") {
          // 内置：下一个输入
          e.preventDefault(); // 阻止默认
          this.focusNextPrev(+1); // 跳转
          return; // 返回
        }
        if (cmd === "focusPrevField") {
          // 内置：上一个输入
          e.preventDefault(); // 阻止默认
          this.focusNextPrev(-1); // 跳转
          return; // 返回
        }
        if (cmd === "openHotkeySettings" || cmd === "openHotkeyHelp") {
          // 内置：打开设置/帮助
          e.preventDefault(); // 阻止默认
          this.ui.showSettings.value = true; // 显示设置
          return; // 返回
        }
        continue; // 没有处理器也非内置 → 查下一作用域
      } // 结束无处理器分支

      e.preventDefault(); // 有处理器 → 阻止默认
      try {
        handler(e, { scope, cmd, combo }); // 调用处理器
      } catch (err) {
        console.error("hotkey handler error:", err); // 错误日志
      }
      return; // 已处理 → 结束
    } // 结束作用域遍历
  } // 结束 _onKeydown
} // 结束 HotkeyService 类
