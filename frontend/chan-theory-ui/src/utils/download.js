// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\download.js
// ==============================
// 说明：下载与快照工具（更新：ECharts v6 CDN，默认合规模式不内嵌原始数据）
// - downloadDataURL(filename, dataUrl): 触发浏览器下载
// - saveHTMLSnapshot(filename, option, meta, opts?): 生成自包含 HTML 快照
//   - opts.includeData = false（默认合规，不内嵌原始数据数组）
//   - 如需复现实验，可传 { includeData: true } 开启
// - buildExportFilename / createOffscreenContainer / destroyOffscreenContainer：与原实现一致
// ==============================

/** 触发浏览器下载：基于 dataURL */
export function downloadDataURL(filename, dataUrl) {
  // 创建一个临时的 a 标签用于下载
  const a = document.createElement("a"); // 动态创建
  a.href = dataUrl; // 绑定数据 URL
  a.download = filename; // 文件名
  a.click(); // 触发点击
}

/** 生成自包含 HTML 快照（ECharts v6 CDN，默认不内嵌原始数据数组） */
export function saveHTMLSnapshot(filename, option, meta, opts = {}) {
  // 解析选项
  const includeData = !!opts.includeData; // 是否包含原始数据
  const bg = opts.background || "#111"; // 背景色
  // 安全复制 option：避免直接引用原对象（可选）
  const optionCopy = JSON.parse(JSON.stringify(option || {})); // 深拷贝
  // 若不包含数据，尽量裁剪大数组（candlestick/line/bar 的 data），保留结构可渲染空框
  if (!includeData) {
    try {
      if (Array.isArray(optionCopy.series)) {
        optionCopy.series = optionCopy.series.map((s) => {
          const t = Object.assign({}, s); // 克隆
          if (Array.isArray(t.data)) t.data = []; // 清空数据数组
          return t; // 返回
        });
      }
      if (optionCopy.dataset && optionCopy.dataset.source) {
        optionCopy.dataset.source = []; // 清空 dataset 数据
      }
    } catch (e) {
      // 容错：裁剪失败不影响导出
    }
  }
  // HTML 片段（ECharts v6）
  const htmlParts = [
    '<!doctype html><html><head><meta charset="utf-8"><title>Snapshot</title>', // 文档头
    '<meta name="viewport" content="width=device-width, initial-scale=1">', // 视口
    // 使用 ECharts v6 CDN（与项目版本一致）
    '<script src="https://cdn.jsdelivr.net/npm/echarts@6/dist/echarts.min.js"></' +
      "script>",
    `<style>html,body,#app{margin:0;height:100%;background:${bg};color:#ddd}</style></head>`, // 简易样式
    '<body><div id="app" style="height:100%"></div>', // 容器
    "<script>", // 内联脚本起始
    `const option=${JSON.stringify(optionCopy)};`, // 写入（可能为空数据）
    `const meta=${JSON.stringify(meta || {})};`, // 元信息（可用于页角显示）
    'const el=document.getElementById("app");', // 容器
    'const c=echarts.init(el,null,{renderer:"canvas"});', // 初始化
    "c.setOption(option);", // 渲染
    "</" + "script></html>", // 结束脚本与文档
  ]; // 片段数组
  // 合并并下载
  const html = htmlParts.join("\n"); // 合并
  const blob = new Blob([html], { type: "text/html" }); // Blob
  const url = URL.createObjectURL(blob); // 临时 URL
  const a = document.createElement("a"); // 下载链接
  a.href = url; // 指向 URL
  a.download = filename; // 文件名
  a.click(); // 下载
  URL.revokeObjectURL(url); // 释放
}

/** 构造导出文件名：包含 symbol、freq、时间戳与扩展名 */
export function buildExportFilename(symbol, freq, format) {
  // 填充函数：将数字补足两位
  const pad = (n) => String(n).padStart(2, "0"); // 左侧补零
  const now = new Date(); // 当前时间
  // 生成时间戳：YYYYMMDD-HHmmss
  const stamp =
    [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join("") +
    "-" +
    [pad(now.getHours()), pad(now.getMinutes()), pad(now.getSeconds())].join(
      ""
    );
  // 清理 symbol 中可能的非法文件名字符
  const safeSymbol = String(symbol || "symbol").replace(/[\\/:*?"<>|]/g, "_"); // 替换非法字符
  const safeFreq = String(freq || "freq"); // 频率文本
  return `${safeSymbol}_${safeFreq}_${stamp}.${format}`; // 拼接最终文件名
}

/** 创建离屏容器：用于 SVG/图片导出，避免侵扰可见 DOM */
export function createOffscreenContainer(width, height) {
  // 创建一个 div 作为离屏渲染容器
  const el = document.createElement("div"); // 新建元素
  // 设置样式：不可见、移出视口且不占用布局
  el.style.position = "fixed"; // 固定定位
  el.style.left = "-99999px"; // 移出屏幕
  el.style.top = "-99999px"; // 移出屏幕
  el.style.width = `${width}px`; // 指定宽度
  el.style.height = `${height}px`; // 指定高度
  el.style.overflow = "hidden"; // 隐藏溢出
  document.body.appendChild(el); // 插入文档
  return el; // 返回容器引用
}

/** 销毁离屏容器：释放 DOM */
export function destroyOffscreenContainer(el) {
  // 如果传入的元素存在且在文档中，移除之
  if (el && el.parentNode) {
    el.parentNode.removeChild(el); // 从父节点移除
  }
}
