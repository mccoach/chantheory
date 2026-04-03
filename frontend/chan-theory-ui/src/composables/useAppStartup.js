// src/composables/useAppStartup.js
// ==============================
// V1.10 - 应用级启动器（local-import 候选刷新预热异步尾触发）
// ==============================

import { waitBackendAlive } from "@/utils/backendReady";
import { useEventStream } from "@/composables/useEventStream";
import { useWatchlist } from "@/composables/useWatchlist";
import { useLocalImportController } from "@/composables/localImport";
import { useFoundationDataCenter } from "@/composables/useFoundationDataCenter";
import { useCurrentSymbolData } from "@/composables/useCurrentSymbolData";

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

  async function initFoundationData() {
    try {
      const fd = useFoundationDataCenter();
      fd.ensureSseSubscription();

      await fd.refreshTaskStatusSnapshot();

      const r1 = await fd.runOne("trade_calendar");
      if (r1?.ok) console.log(`${nowTs()} [App] trade_calendar-ready`);
      else console.warn(`${nowTs()} [App] trade_calendar-not-ready`);

      const r2 = await fd.runOne("symbol_index");
      if (r2?.ok) console.log(`${nowTs()} [App] symbol_index-ready`);
      else console.warn(`${nowTs()} [App] symbol_index-not-ready`);

      const r3 = await fd.runOne("profile_snapshot");
      if (r3?.ok) console.log(`${nowTs()} [App] profile_snapshot-ready`);
      else console.warn(`${nowTs()} [App] profile_snapshot-not-ready`);

      const r4 = await fd.runOne("factor_events_snapshot");
      if (r4?.ok) console.log(`${nowTs()} [App] factor_events_snapshot-ready`);
      else console.warn(`${nowTs()} [App] factor_events_snapshot-not-ready`);
    } catch (e) {
      console.error(`${nowTs()} [App] foundation-data-init-failed`, e);
    }
  }

  async function restoreLastSymbolIdentityAndLoad() {
    try {
      const id = settings.getLastSymbolIdentity
        ? settings.getLastSymbolIdentity()
        : {
            symbol: settings.preferences.lastSymbol || "",
            market: settings.preferences.lastMarket || "",
          };

      if (!id?.symbol || !id?.market) {
        console.warn(`${nowTs()} [App] no-last-symbol-identity`);
        return;
      }

      const currentView = useCurrentSymbolData();
      await currentView.prepare({
        symbol: id.symbol,
        market: id.market,
        freq: settings.preferences.freq || "1d",
        adjust: settings.preferences.adjust || "none",
        force_refresh: false,
      });

      vm.setSymbolIdentity({
        symbol: id.symbol,
        market: id.market,
      });
      vm.setFreq(settings.preferences.freq || "1d");
      vm.setAdjust(settings.preferences.adjust || "none");
      await vm.reload({ with_profile: true });
    } catch (e) {
      console.error(`${nowTs()} [App] restore-last-symbol-identity-failed`, e);
    }
  }

  async function loadWatchlist() {
    try {
      const wl = useWatchlist();
      wl.loadFromCache();
      await wl.refresh();
    } catch (e) {
      console.error(`${nowTs()} [App] watchlist-load-failed`, e);
    }
  }

  async function warmupLocalImportBase() {
    try {
      const ctl = useLocalImportController();
      await ctl.initialize();
      console.log(`${nowTs()} [App] local_import-base-warmup-ready`);
    } catch (e) {
      console.error(`${nowTs()} [App] local_import-base-warmup-failed`, e);
    }
  }

  function triggerLocalImportCandidateRefreshTail() {
    try {
      const ctl = useLocalImportController();

      Promise.resolve()
        .then(() => ctl.refreshCandidates())
        .then((r) => {
          if (r?.ok) {
            console.log(`${nowTs()} [App] local_import-candidates-refreshed`);
          } else {
            console.warn(
              `${nowTs()} [App] local_import-candidates-refresh-failed`,
              r?.message || ""
            );
          }
        })
        .catch((e) => {
          console.error(`${nowTs()} [App] local_import-candidates-refresh-failed`, e);
        });
    } catch (e) {
      console.error(`${nowTs()} [App] local_import-candidates-refresh-failed`, e);
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

    await initFoundationData();
    await restoreLastSymbolIdentityAndLoad();
    await loadWatchlist();
    await warmupLocalImportBase();

    console.log(`${nowTs()} [App] app-started`);

    // 启动链最后异步触发，不阻塞启动完成
    triggerLocalImportCandidateRefreshTail();
  }

  function startApp() {
    if (_startupPromise) return _startupPromise;
    _startupPromise = realStartup();
    return _startupPromise;
  }

  return { startApp };
}
