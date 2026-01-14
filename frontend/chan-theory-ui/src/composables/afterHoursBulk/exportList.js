// src/composables/afterHoursBulk/exportList.js
// ==============================
// AfterHoursBulk 模块：导出 CSV（纯函数）
// - 复用 utils/csvExport，不与 UI 耦合
// ==============================

import { buildTimestampForFilename, toCsvText, downloadTextFile } from "@/utils/csvExport";

function asStr(x) {
  return String(x == null ? "" : x);
}

export function exportSelectedSymbolsToCsv({ rows, isStarredSet }) {
  const list = Array.isArray(rows) ? rows : [];
  const star = isStarredSet instanceof Set ? isStarredSet : new Set();

  if (!list.length) {
    return { ok: false, message: "当前未选中任何标的" };
  }

  const header = ["starred", "symbol", "name", "market", "class", "type", "listing_date", "updated_at"];

  const outRows = list.map((it) => {
    const sym = asStr(it?.symbol).trim();
    const starred = star.has(sym) ? 1 : 0;

    const listingDate = it?.listingDate ?? it?.listing_date ?? "";
    const updatedAt = it?.updatedAt ?? it?.updated_at ?? "";

    return [
      starred,
      sym,
      it?.name ?? "",
      it?.market ?? "",
      it?.class ?? "",
      it?.type ?? "",
      listingDate,
      updatedAt,
    ];
  });

  const csv = toCsvText({ header, rows: outRows });
  const fname = `symbols-export-${buildTimestampForFilename()}.csv`;
  downloadTextFile({ filename: fname, text: csv });

  return { ok: true, message: "" };
}
