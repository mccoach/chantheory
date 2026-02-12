// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\hotkeys\registry.js
// ==============================
// V3.0 - REFACTOR: Hotkey 映射方向拉直为唯一真相源（combo -> command）
//
// 目标：
//   - 唯一真相源：scope -> combo -> command（运行时按 combo 查命令）
//   - UI 展示需要 cmd -> combo：由本类提供唯一派生方法 getCommandToCombo
//   - 删除方向混乱的 getBindings/_invert 旧绕路实现
//
// 保持：
//   - userOverrides 结构仍为 scope -> combo -> cmd（与设置弹窗保存/持久化链路一致）
// ==============================

import { ref } from "vue";
import { toCombo, isReservedBrowserCombo } from "./core.js";

export class HotkeyService {
  constructor(defaultKeymap) {
    this.defaultKeymap = defaultKeymap || {};
    this.userOverrides = {};
    this.handlers = {};
    this.scopeStack = ref(["global"]);
    this._onKeydown = this._onKeydown.bind(this);
    window.addEventListener("keydown", this._onKeydown, { capture: true });
  }

  destroy() {
    window.removeEventListener("keydown", this._onKeydown, { capture: true });
  }

  // 合并后的唯一真相源 keymap：scope -> combo -> cmd
  get keymap() {
    const merged = {};
    const scopes = new Set([
      ...Object.keys(this.defaultKeymap),
      ...Object.keys(this.userOverrides || {}),
    ]);
    scopes.forEach((s) => {
      merged[s] = Object.assign({}, this.defaultKeymap[s] || {}, this.userOverrides[s] || {});
    });
    return merged;
  }

  registerHandlers(scope, map) {
    this.handlers[scope] = Object.assign({}, this.handlers[scope] || {}, map || {});
  }

  unregisterHandlers(scope) {
    delete this.handlers[scope];
  }

  pushScope(scope) {
    const s = this.scopeStack.value.slice();
    s.push(scope);
    this.scopeStack.value = s;
  }

  popScope(scope) {
    if (!scope) {
      const s = this.scopeStack.value.slice();
      if (s.length > 1) s.pop();
      this.scopeStack.value = s;
      return;
    }
    const s = this.scopeStack.value.filter((x) => x !== scope);
    if (!s.length) s.push("global");
    this.scopeStack.value = s;
  }

  setUserOverrides(overrides) {
    // overrides 必须是 scope -> combo -> cmd（真相源方向）
    this.userOverrides = overrides || {};
  }

  // ===== 唯一派生：cmd -> combo（供 UI 展示/编辑）=====
  getCommandToCombo(scope) {
    const s = String(scope || "");
    const map = this.keymap[s] || {};
    const out = {};
    for (const [combo, cmd] of Object.entries(map)) {
      if (!cmd) continue;
      out[String(cmd)] = String(combo);
    }
    return out;
  }

  // ===== UI 若需要 combo -> cmd，也可显式拿到（同真相源）=====
  getComboToCommand(scope) {
    const s = String(scope || "");
    return this.keymap[s] || {};
  }

  focusNextPrev(dir = +1) {
    const candidates = Array.from(
      document.querySelectorAll(
        'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [contenteditable="true"]'
      )
    ).filter((el) => {
      const rs = getComputedStyle(el);
      return rs.display !== "none" && rs.visibility !== "hidden" && el.offsetParent !== null;
    });
    if (!candidates.length) return;
    const active = document.activeElement;
    let idx = candidates.indexOf(active);
    idx = idx < 0 ? (dir > 0 ? -1 : 0) : idx;
    const next = candidates[(idx + dir + candidates.length) % candidates.length];
    if (next && typeof next.focus === "function") next.focus();
  }

  _isEditingNumberSpinnerTarget(e) {
    try {
      const t = e?.target;
      if (!t || typeof t.closest !== "function") return false;

      const root = t.closest('[data-ct-numspin="1"]');
      if (!root) return false;

      return String(root.getAttribute("data-editing") || "0") === "1";
    } catch {
      return false;
    }
  }

  _onKeydown(e) {
    const combo = toCombo(e);
    if (!combo) return;

    if (this._isEditingNumberSpinnerTarget(e)) return;
    if (isReservedBrowserCombo(e)) return;

    const tag = ((e.target && e.target.tagName) || "").toLowerCase();
    const inInput = tag === "input" || tag === "textarea" || (e.target && e.target.isContentEditable);

    const inputWhitelist = new Set([
      "Escape",
      "Ctrl+Enter",
      "Meta+Enter",
      "Tab",
      "Shift+Tab",
      "Ctrl+Right",
      "Ctrl+Left",
      "Ctrl+Comma",
      "F1",
      "Alt+R",
      "Alt+E",
      "ArrowDown",
      "ArrowUp",
      "Enter",
      "ArrowLeft",
      "ArrowRight",
    ]);

    if (inInput && !inputWhitelist.has(combo)) return;

    const stack = [...this.scopeStack.value].reverse();

    for (const scope of stack) {
      const map = this.keymap[scope] || {};
      const cmd = map[combo];
      if (!cmd) continue;

      const handler =
        (this.handlers[scope] || {})[cmd] ||
        (this.handlers["global"] || {})[cmd];

      if (!handler) {
        if (cmd === "focusNextField") {
          e.preventDefault();
          this.focusNextPrev(+1);
          return;
        }
        if (cmd === "focusPrevField") {
          e.preventDefault();
          this.focusNextPrev(-1);
          return;
        }
        continue;
      }

      e.preventDefault();
      try {
        handler(e, { scope, cmd, combo });
      } catch (err) {
        console.error(`[HotkeyService] handler-error cmd=${cmd}`, err);
      }
      return;
    }
  }
}
