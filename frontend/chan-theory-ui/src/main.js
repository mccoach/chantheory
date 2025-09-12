// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\main.js
// ==============================
// 说明：前端入口文件（修复快捷键响应式）
// - 快捷键插件：传入整个 reactive 的 settings.hotkeyOverrides 对象，而不是它的 .value，保证插件内部能 watch 到变更。
// ==============================

import { createApp } from "vue";                             // Vue 应用创建
import App from "./App.vue";                                   // 根组件
import "@/styles/global.css";                               // 全局样式

import InteractionPlugin from "@/interaction/plugin/vue";     // 快捷键插件
import { useUserSettings } from "@/composables/useUserSettings"; // 用户设置

const app = createApp(App);                                    // 创建 Vue 应用

const settings = useUserSettings();                          // 用户设置实例
// 修复：传入整个 hotkeyOverrides ref，让插件内部可以 watch
app.use(InteractionPlugin, { userOverrides: settings.hotkeyOverrides }); // 传入响应式 ref，而不是 .value

app.mount("#app");                                             // 挂载
