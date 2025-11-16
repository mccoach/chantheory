// src/main.js
// ==============================
// V2.0 - 增加构造器启动
// ==============================

import { createApp } from "vue";
import App from "./App.vue";
import "@/styles/global.css";

import InteractionPlugin from "@/interaction/plugin/vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { vSelectAll } from "@/utils/inputBehaviors";

// ===== 新增：启动图表构造器（必须在 createApp 之前）=====
import { bootstrapChartBuilders } from "@/charts/builderBootstrap";
bootstrapChartBuilders();

const app = createApp(App);

const settings = useUserSettings();
app.use(InteractionPlugin, { userOverrides: settings.preferences.hotkeyOverrides });
app.directive("select-all", vSelectAll);

app.mount("#app");