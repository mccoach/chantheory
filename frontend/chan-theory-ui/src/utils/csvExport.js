// src/utils/csvExport.js
// ==============================
// 说明：CSV 导出工具（浏览器下载）
// 职责：
//   - 生成 CSV 文本（含转义）
//   - 使用 UTF-8 BOM（Excel 打开中文不乱码）
//   - 触发浏览器下载
// ==============================

function pad2(n) {
    return String(n).padStart(2, "0");
}

export function buildTimestampForFilename(d = new Date()) {
    const Y = d.getFullYear();
    const M = pad2(d.getMonth() + 1);
    const D = pad2(d.getDate());
    const h = pad2(d.getHours());
    const m = pad2(d.getMinutes());
    const s = pad2(d.getSeconds());
    return `${Y}${M}${D}-${h}${m}${s}`;
}

function escapeCsvCell(v) {
    if (v == null) return "";
    const s = String(v);

    const needQuote =
        s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r");

    if (!needQuote) return s;

    // 双引号转义：""（CSV 标准）
    const escaped = s.replace(/"/g, '""');
    return `"${escaped}"`;
}

export function toCsvText({ header, rows }) {
    const head = Array.isArray(header) ? header : [];
    const body = Array.isArray(rows) ? rows : [];

    const lines = [];
    if (head.length) {
        lines.push(head.map(escapeCsvCell).join(","));
    }

    for (const r of body) {
        const arr = Array.isArray(r) ? r : [];
        lines.push(arr.map(escapeCsvCell).join(","));
    }

    return lines.join("\r\n");
}

export function downloadTextFile({ filename, text, mime = "text/csv;charset=utf-8" }) {
    const name = String(filename || "download.csv");
    const content = String(text ?? "");

    // UTF-8 BOM（Excel 友好）
    const BOM = "\uFEFF";
    const blob = new Blob([BOM + content], { type: mime });

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = name;

    document.body.appendChild(a);
    a.click();

    // 清理
    setTimeout(() => {
        try {
            document.body.removeChild(a);
        } catch { }
        try {
            URL.revokeObjectURL(url);
        } catch { }
    }, 0);
}
