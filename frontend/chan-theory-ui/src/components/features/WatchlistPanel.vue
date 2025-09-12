<!-- src/components/features/WatchlistPanel.vue -->
<!-- ============================== -->
<!-- 说明：自选池容器（增删、后台同步、状态展示） -->
<!-- - 启动时加载自选列表与同步状态 -->
<!-- - 支持添加/移除，触发后台同步（不阻塞 UI） -->
<!-- ============================== -->
<template>
  <!-- 外层面板 -->
  <div class="panel-box" style="margin-top: 8px">
    <!-- 标题行 -->
    <div class="row">
      <div class="title">自选池</div>
      <div class="spacer"></div>
      <button class="btn" @click="refresh" :disabled="loading">刷新</button>
      <button class="btn" @click="syncAll" :disabled="loading">
        后台同步全部
      </button>
    </div>

    <!-- 添加入口 -->
    <div class="row" style="margin-top: 8px">
      <input
        class="input"
        v-model="inputSymbol"
        placeholder="输入代码后回车添加（如 600519）"
        @keydown.enter="add"
      />
      <button
        class="btn"
        @click="add"
        :disabled="loading || !inputSymbol.trim()"
      >
        添加
      </button>
    </div>

    <!-- 列表与状态 -->
    <div class="list">
      <div v-for="sym in items" :key="sym" class="item">
        <div class="left">
          <div class="code">{{ sym }}</div>
          <div class="st">
            <span class="kv"
              >运行中: {{ status[sym]?.running ? "是" : "否" }}</span
            >
            <span class="kv">开始: {{ status[sym]?.started_at || "-" }}</span>
            <span class="kv">结束: {{ status[sym]?.finished_at || "-" }}</span>
            <span class="kv" v-if="status[sym]?.error" style="color: #e74c3c"
              >错误: {{ status[sym]?.error }}</span
            >
          </div>
        </div>
        <div class="right">
          <button class="btn" @click="syncOne(sym)" :disabled="loading">
            同步
          </button>
          <button class="btn" @click="removeOne(sym)" :disabled="loading">
            移除
          </button>
        </div>
      </div>
      <div v-if="!items.length" class="empty">暂无自选标的</div>
    </div>

    <!-- 错误显示 -->
    <div v-if="error" class="err">错误：{{ error }}</div>
  </div>
</template>

<script setup>
// 引入 Vue
import { ref, onMounted } from "vue"; // 响应式与生命周期
// 引入自选组合式
import { useWatchlist } from "@/composables/useWatchlist"; // 自选池

// 实例化
const wl = useWatchlist(); // { items, status, loading, error, refresh, addOne, removeOne, syncAll, syncOne }
const items = wl.items; // 自选列表
const status = wl.status; // 状态快照
const loading = wl.loading; // 加载标志
const error = wl.error; // 错误文本

// 输入框
const inputSymbol = ref(""); // 输入的代码

// 行为封装
function refresh() {
  wl.refresh();
} // 刷新列表
function add() {
  const s = inputSymbol.value.trim();
  if (!s) return;
  wl.addOne(s).then(() => {
    inputSymbol.value = "";
  }); // 添加后清空
}
function removeOne(sym) {
  wl.removeOne(sym);
} // 移除
function syncAll() {
  wl.syncAll();
} // 同步全部
function syncOne(sym) {
  wl.syncOne(sym);
} // 同步单个

// 启动加载
onMounted(() => {
  wl.refresh();
}); // 首次加载
</script>

<style scoped>
/* 标题行布局 */
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-weight: 600;
}
.spacer {
  flex: 1;
}
/* 列表样式 */
.list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #161616;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px;
}
.item .left {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}
.item .code {
  font-weight: 700;
}
.item .st {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #bbb;
}
.item .right {
  display: flex;
  gap: 6px;
}
.empty {
  color: #888;
  text-align: left;
  padding: 8px;
}
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
}
.input {
  flex: 1;
}
.btn {
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 6px;
  padding: 6px 10px;
  color: #ddd;
  cursor: pointer;
}
</style>
