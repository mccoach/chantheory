// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\download.js
// ==============================
// 说明：下载与快照工具
// 变更要点：
// - HTML 快照与背景默认色、是否嵌入数据的“默认选择”统一引用 DEFAULT_EXPORT_SETTINGS；
// - 遵循“默认集中管理”的原则，不再在此文件写死默认值；其余行为保持不变。
// ==============================

import { DEFAULT_EXPORT_SETTINGS } from "@/constants"; // 集中默认：导出设置

/** 触发浏览器下载：基于 dataURL */
export function downloadDataURL(filename, dataUrl) {
  const a = document.createElement("a"); // 动态 a 标签
  a.href = dataUrl; // 绑定数据 URL
  a.download = filename; // 文件名
  a.click(); // 触发下载
}

/** 生成自包含 HTML 快照（ECharts v6 CDN，默认不内嵌原始数据） */
export function saveHTMLSnapshot(filename, option, meta, opts = {}) {
  const includeData =
    typeof opts.includeData === "boolean" // 是否内嵌数据
      ? opts.includeData
      : DEFAULT_EXPORT_SETTINGS.includeDataDefault; // 默认取集中默认
  const bg = opts.background || DEFAULT_EXPORT_SETTINGS.background; // 背景色默认
  const optionCopy = JSON.parse(JSON.stringify(option || {})); // 深拷贝 option

  // 合规模式：不内嵌数据时尽量裁剪 series.data 与 dataset.source
  if (!includeData) {
    try {
      if (Array.isArray(optionCopy.series)) {
        optionCopy.series = optionCopy.series.map((s) => {
          const t = Object.assign({}, s);
          if (Array.isArray(t.data)) t.data = [];
          return t;
        });
      }
      if (optionCopy.dataset && optionCopy.dataset.source) {
        optionCopy.dataset.source = [];
      }
    } catch {
      /* 裁剪失败不阻塞导出 */
    }
  }

  const htmlParts = [
    '<!doctype html><html><head><meta charset="utf-8"><title>Snapshot</title>',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    '<script src="https://cdn.jsdelivr.net/npm/echarts@6/dist/echarts.min.js"></' +
      "script>",
    `<style>html,body,#app{margin:0;height:100%;background:${bg};color:#ddd}</style></head>`,
    '<body><div id="app" style="height:100%"></div>',
    "<script>",
    `const option=${JSON.stringify(optionCopy)};`,
    `const meta=${JSON.stringify(meta || {})};`,
    'const el=document.getElementById("app");',
    'const c=echarts.init(el,null,{renderer:"canvas"});',
    "c.setOption(option);",
    "</" + "script></html>",
  ];
  const html = htmlParts.join("\n");
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 构造导出文件名：包含 symbol、freq、时间戳与扩展名（保留原逻辑） */
export function buildExportFilename(symbol, freq, format) {
  const pad = (n) => String(n).padStart(2, "0");
  const now = new Date();
  const stamp =
    [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join("") +
    "-" +
    [pad(now.getHours()), pad(now.getMinutes()), pad(now.getSeconds())].join(
      ""
    );
  const safeSymbol = String(symbol || "symbol").replace(/[\\/:*?"<>|]/g, "_");
  const safeFreq = String(freq || "freq");
  return `${safeSymbol}_${safeFreq}_${stamp}.${format}`;
}

/** 创建离屏容器：用于 SVG/图片导出，避免侵扰可见 DOM（保留） */
export function createOffscreenContainer(width, height) {
  const el = document.createElement("div");
  el.style.position = "fixed";
  el.style.left = "-99999px";
  el.style.top = "-99999px";
  el.style.width = `${width}px`;
  el.style.height = `${height}px`;
  el.style.overflow = "hidden";
  document.body.appendChild(el);
  return el;
}

/** 销毁离屏容器：释放 DOM（保留） */
export function destroyOffscreenContainer(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}
