// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\hotkeys\registry.js
// ==============================
// V2.0 - 增强调试日志
// ==============================

import { ref } from "vue";
import { toCombo, isReservedBrowserCombo } from "./core.js";

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
    
    // ===== 新增：调试日志 =====
    console.log('[HotkeyService] 🎹 服务已创建', {
      defaultScopes: Object.keys(defaultKeymap),
      initialScope: this.scopeStack.value
    });
  }

  destroy() {
    // 销毁（移除监听）
    window.removeEventListener("keydown", this._onKeydown, { capture: true });
    console.log('[HotkeyService] 🎹 服务已销毁');
  }

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
    });
    return merged;
  }

  registerHandlers(scope, map) {
    // 注册命令处理器
    this.handlers[scope] = Object.assign(
      // 覆盖追加
      {},
      this.handlers[scope] || {},
      map || {}
    );
    
    // ===== 新增：注册成功日志 =====
    const cmdCount = Object.keys(map || {}).length;
    console.log(`[HotkeyService] ✅ 已注册 ${scope} 作用域（${cmdCount} 个命令）`, Object.keys(map || {}));
  }

  unregisterHandlers(scope) {
    delete this.handlers[scope];
    console.log(`[HotkeyService] 🗑️ 已注销 ${scope} 作用域`);
  }

  pushScope(scope) {
    const s = this.scopeStack.value.slice();
    s.push(scope);
    this.scopeStack.value = s;
    console.log(`[HotkeyService] 📌 压入作用域: ${scope}，当前栈:`, this.scopeStack.value);
  }

  popScope(scope) {
    // 弹出作用域
    if (!scope) {
      const s = this.scopeStack.value.slice();
      if (s.length > 1) s.pop();
      this.scopeStack.value = s;
      console.log(`[HotkeyService] 📌 弹出作用域，当前栈:`, this.scopeStack.value);
      return;
    }
    const s = this.scopeStack.value.filter((x) => x !== scope);
    if (!s.length) s.push("global");
    this.scopeStack.value = s;
    console.log(`[HotkeyService] 📌 移除作用域: ${scope}，当前栈:`, this.scopeStack.value);
  }

  setBinding(scope, command, combo) {
    // 这个方法现在逻辑上被 setUserOverrides 覆盖，但保留以防未来需要单点修改
    const currentScopeOverrides = this.userOverrides[scope] || {};
    // 移除旧的绑定
    Object.keys(currentScopeOverrides).forEach((c) => {
      if (currentScopeOverrides[c] === command) {
        delete currentScopeOverrides[c];
      }
    });
    // 添加新的绑定
    if (combo) {
      currentScopeOverrides[combo] = command;
    }
    this.userOverrides[scope] = currentScopeOverrides;
  }

  setUserOverrides(overrides) {
    // 接收完整的、按 scope 组织的 overrides 对象
    this.userOverrides = overrides || {};
    console.log('[HotkeyService] 🔄 用户覆盖已更新', Object.keys(overrides || {}));
  }

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

    const stack = [...this.scopeStack.value].reverse();
    
    // ===== 新增：调试日志（仅开发环境）=====
    if (import.meta.env.DEV) {
      console.log(`[HotkeyService] 🎹 按键: ${combo}，作用域栈:`, stack);
    }
    
    for (const scope of stack) {
      // 逐层匹配
      const map = this.keymap[scope] || {}; // 合并映射
      const cmd = map[combo]; // 查命令
      if (!cmd) continue; // 未映射 → 下一个

      const handler =
        (this.handlers[scope] || {})[cmd] || // 先找当前作用域
        (this.handlers["global"] || {})[cmd]; // 再找 global

      if (!handler) {
        // ===== 新增：未找到处理器的警告 =====
        console.warn(`[HotkeyService] ⚠️ 未找到处理器: scope=${scope}, cmd=${cmd}`);
        
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
        continue;
      }

      // ===== 新增：执行处理器的日志 =====
      console.log(`[HotkeyService] ✅ 执行: scope=${scope}, cmd=${cmd}, combo=${combo}`);
      
      e.preventDefault();
      try {
        handler(e, { scope, cmd, combo }); // 调用处理器
      } catch (err) {
        console.error(`[HotkeyService] ❌ 处理器执行失败: ${cmd}`, err);
      }
      return;
    }
    
    // ===== 新增：未匹配任何处理器的日志 =====
    if (import.meta.env.DEV) {
      console.log(`[HotkeyService] 🔇 未匹配: combo=${combo}`);
    }
  }
}