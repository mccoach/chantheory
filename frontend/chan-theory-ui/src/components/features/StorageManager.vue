<!-- src/components/features/StorageManager.vue -->
<!-- ============================== -->
<!-- 说明：历史数据管理容器 -->
<!-- - 本次修改：从频率清理选项中移除 120m。 -->
<!-- ============================== -->
<template>
  <div class="panel-box" style="margin-top: 8px">
    <!-- 标题与刷新 -->
    <div class="row">
      <div class="title">历史数据管理</div>
      <div class="spacer"></div>
      <button class="btn" @click="refreshUsage" :disabled="loading">
        刷新用量
      </button>
    </div>

    <!-- 当前用量 -->
    <div class="row" style="margin-top: 8px; text-align: left">
      <div>
        数据库路径：<code>{{ usage.db_path || "-" }}</code>
      </div>
    </div>
    <div class="row" style="text-align: left">
      <div>数据库大小：{{ prettyBytes(usage.size_bytes || 0) }}</div>
    </div>
    <div class="row" style="text-align: left">
      <div>
        表行数： candles={{ usage.tables?.candles || 0 }}, candles_cache={{
          usage.tables?.candles_cache || 0
        }}, adj_factors={{ usage.tables?.adj_factors || 0 }}, symbol_index={{
          usage.tables?.symbol_index || 0
        }}, symbol_index_summary={{ usage.tables?.symbol_index_summary || 0 }}
      </div>
    </div>

    <!-- 维护操作 -->
    <div class="row" style="margin-top: 8px">
      <button class="btn" @click="doVacuum" :disabled="loading">VACUUM</button>
      <button class="btn" @click="doIntegrity" :disabled="loading">
        完整性检查
      </button>
    </div>

    <!-- 迁移数据库 -->
    <div class="panel" style="margin-top: 8px; text-align: left">
      <div class="subtitle">迁移数据库路径</div>
      <div class="row">
        <input
          class="input"
          v-model="newPath"
          placeholder="输入新的数据库文件路径，如 D:/ChanData/data.sqlite"
        />
        <button
          class="btn"
          @click="migrate"
          :disabled="loading || !newPath.trim()"
        >
          迁移
        </button>
      </div>
      <div class="hint">迁移将复制数据库并校验完整性，成功后自动切换。</div>
    </div>

    <!-- 区间清理 -->
    <div class="panel" style="margin-top: 8px; text-align: left">
      <div class="subtitle">按条件清理</div>
      <div class="row">
        <input
          class="input"
          v-model="clSymbol"
          placeholder="标的代码，如 600519"
        />
        <select
          class="select"
          multiple
          v-model="clFreqs"
          title="选择要清理的频率（可多选）"
        >
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="15m">15m</option>
          <option value="30m">30m</option>
          <option value="60m">60m</option>
          <!-- 移除：120m 已废弃 -->
          <option value="1d">1d</option>
          <option value="1w">1w</option>
          <option value="1M">1M</option>
        </select>
      </div>
      <div class="row">
        <input
          class="input"
          v-model="clStart"
          placeholder="开始时间（毫秒或 YYYY-MM-DD，可空）"
        />
        <input
          class="input"
          v-model="clEnd"
          placeholder="结束时间（毫秒或 YYYY-MM-DD，可空）"
        />
        <button
          class="btn"
          @click="cleanup"
          :disabled="loading || !clSymbol.trim()"
        >
          清理
        </button>
      </div>
      <div class="hint">
        说明：若不填时间窗口，将删除所选频率的整个缓存分区；若填窗口，则仅删除窗口内数据。
      </div>
    </div>

    <!-- 错误显示 -->
    <div v-if="error" class="err">错误：{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useStorageManager } from "@/composables/useStorageManager";

const sm = useStorageManager();
const usage = sm.usage;
const loading = sm.loading;
const error = sm.error;

const newPath = ref("");
const clSymbol = ref("");
const clFreqs = ref(["1m", "60m"]);
const clStart = ref("");
const clEnd = ref("");

function toMs(x) {
  if (!x) return undefined;
  if (!isNaN(Number(x))) return Number(x);
  const t = new Date(x);
  if (!isNaN(t.getTime())) return t.getTime();
  return undefined;
}

function refreshUsage() {
  sm.refreshUsage();
}
async function doVacuum() {
  await sm.doVacuum();
}
async function doIntegrity() {
  await sm.doIntegrity();
}
async function migrate() {
  await sm.migrateDb(newPath.value.trim());
}
async function cleanup() {
  await sm.cleanupRange({
    symbol: clSymbol.value.trim(),
    freqs: clFreqs.value.slice(),
    start_ms: toMs(clStart.value),
    end_ms: toMs(clEnd.value),
  });
}

function prettyBytes(n) {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0,
    x = Number(n || 0);
  while (x >= 1024 && i < u.length - 1) {
    x /= 1024;
    i++;
  }
  return `${x.toFixed(2)} ${u[i]}`;
}

onMounted(() => {
  sm.refreshUsage();
});
</script>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.spacer {
  flex: 1;
}
.title {
  font-weight: 600;
}
.subtitle {
  font-weight: 600;
  margin-bottom: 4px;
}
.hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
}
.input {
  flex: 1;
}
.select {
  min-width: 180px;
  height: 34px;
}
.btn {
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 6px;
  padding: 6px 10px;
  color: #ddd;
  cursor: pointer;
}
.panel {
  background: #161616;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px;
}
code {
  background: #0f0f0f;
  border: 1px solid #333;
  padding: 2px 4px;
  border-radius: 4px;
}
</style>
