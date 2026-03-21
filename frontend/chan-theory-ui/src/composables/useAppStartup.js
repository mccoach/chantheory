// src/composables/useAppStartup.js
// ==============================
// V1.0 - 应用级启动器（单文件版）
//
// 设计目标：
//   - 启动流程是“应用级行为”，不是“组件级行为”
//   - App 组件即使在开发环境下重新挂载，也不应重复触发参考数据初始化任务
//   - 因此这里将启动流程建模为模块级唯一 Promise
//
// 说明：
//   - 本文件保持单文件，不做伪拆包
//   - 当前阶段它只有一个稳定职责：应用启动编排
// ==============================

import { waitBackendAlive } from "@/utils/backendReady";
import { useEventStream } from "@/composables/useEventStream";
import { useTradeCalendar } from "@/composables/useTradeCalendar";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useProfileSnapshot } from "@/composables/useProfileSnapshot";
import { useWatchlist } from "@/composables/useWatchlist";

let _startupPromise = null;

function nowTs() {
  return new Date().toISOString();
}

export function useAppStartup({ backendReady, settings, vm }) {
  async function ensureSseConnected() {
    const { connect, connected } = useEventStream();
    connect();

    console.log(`${nowTs()} [App] waiting-sse-connection`);
    let retries = 0;
    while (!connected.value && retries < 50) {
      await new Promise((r) => setTimeout(r, 100));
      retries++;
    }

    if (!connected.value) {
      console.error(`${nowTs()} [App] sse-timeout`);
      alert("无法建立实时连接，请刷新页面");
      return { ok: false };
    }

    console.log(`${nowTs()} [App] sse-connected`);
    return { ok: true };
  }

  async function initTradeCalendar() {
    try {
      const tc = useTradeCalendar();
      const r = await tc.ensureReady({ force_fetch: false, timeoutMs: 60000 });
      if (r?.ok) console.log(`${nowTs()} [App] trade_calendar-ready`);
      else console.warn(`${nowTs()} [App] trade_calendar-not-ready`);
    } catch (e) {
      console.error(`${nowTs()} [App] trade_calendar-init-failed`, e);
    }
  }

  async function initReferenceData() {
    try {
      const si = useSymbolIndex();
      const ps = useProfileSnapshot();

      const [indexRes, profileRes] = await Promise.all([
        si.ensureIndexReady({ mode: "startup", timeoutMs: 60000 }),
        ps.ensureReady({ timeoutMs: 60000 }),
      ]);

      if (indexRes?.ok) console.log(`${nowTs()} [App] symbol_index-ready`);
      else console.warn(`${nowTs()} [App] symbol_index-not-ready`);

      if (profileRes?.ok) console.log(`${nowTs()} [App] profile_snapshot-ready`);
      else console.warn(`${nowTs()} [App] profile_snapshot-not-ready`);
    } catch (e) {
      console.error(`${nowTs()} [App] startup-reference-data-init-failed`, e);
    }
  }

  function restoreLastSymbolIdentity() {
    try {
      const id = settings.getLastSymbolIdentity
        ? settings.getLastSymbolIdentity()
        : {
            symbol: settings.preferences.lastSymbol || "",
            market: settings.preferences.lastMarket || "",
          };

      if (id?.symbol && id?.market) {
        vm.setSymbolIdentity({
          symbol: id.symbol,
          market: id.market,
        });
      } else {
        console.warn(`${nowTs()} [App] no-last-symbol-identity`);
      }
    } catch (e) {
      console.error(`${nowTs()} [App] restore-last-symbol-identity-failed`, e);
    }
  }

  async function loadWatchlist() {
    try {
      const wl = useWatchlist();
      await wl.smartLoad();
    } catch (e) {
      console.error(`${nowTs()} [App] watchlist-load-failed`, e);
    }
  }

  async function realStartup() {
    const alive = await waitBackendAlive({ intervalMs: 200 });
    backendReady.value = !!alive;

    if (!backendReady.value) {
      return;
    }

    console.log(`${nowTs()} [App] backend-ready, start-app`);

    const sse = await ensureSseConnected();
    if (!sse.ok) return;

    await initTradeCalendar();
    await initReferenceData();

    // 唯一当前标的加载链：恢复身份 -> useMarketView 内 watch 自动 reload
    restoreLastSymbolIdentity();

    await loadWatchlist();

    console.log(`${nowTs()} [App] app-started`);
  }

  function startApp() {
    if (_startupPromise) return _startupPromise;
    _startupPromise = realStartup();
    return _startupPromise;
  }

  return { startApp };
}
