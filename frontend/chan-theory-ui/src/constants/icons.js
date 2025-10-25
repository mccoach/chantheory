// src/constants/icons.js
// ==============================
// 说明：可复用的 UI 图标 SVG 常量。
// - 职责：集中管理高质量的、带样式的 SVG 字符串，供各组件通过 v-html 渲染。
// - 设计：每个 SVG 都包含完整的 <defs> 和样式，确保独立渲染时效果一致。
//         渐变ID使用唯一值（如 gcx, gset）避免在同一页面渲染时冲突。
// ==============================

/**
 * 精致的关闭按钮 (×)
 */
export const CLOSE_ICON_SVG = `
<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
  <defs>
    <linearGradient id="gcx" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3a3a3a" />
      <stop offset="1" stop-color="#242424" />
    </linearGradient>
  </defs>
  <rect x="2.5" y="2.5" rx="6" ry="6" width="19" height="19" fill="url(#gcx)" stroke="#8b8b8b" stroke-width="1" />
  <path d="M8 8 L16 16" stroke="#e6e6e6" stroke-width="1.8" stroke-linecap="round" />
  <path d="M16 8 L8 16" stroke="#e6e6e6" stroke-width="1.8" stroke-linecap="round" />
</svg>
`;

/**
 * 精致的设置按钮 (⚙️)
 */
export const SETTINGS_ICON_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
  <defs>
    <linearGradient id="gset" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3a3a3a" />
      <stop offset="1" stop-color="#242424" />
    </linearGradient>
  </defs>
  <rect x="2.5" y="2.5" rx="6" ry="6" width="19" height="19" fill="url(#gset)" stroke="#8b8b8b" stroke-width="1" />
  <g transform="translate(12,12) scale(0.072) translate(-100,-100)">
    <path fill="#f5f5f5" fill-rule="evenodd" d="
      M 157.956 84.471
      L 188.633 84.372
      A 90 90 0 0 1 188.633 115.628
      L 157.956 115.529
      A 60 60 0 0 1 142.426 142.426
      L 157.851 168.944
      A 90 90 0 0 1 130.782 184.572
      L 115.529 157.956
      A 60 60 0 0 1 84.471 157.956
      L 69.218 184.572
      A 90 90 0 0 1 42.149 168.944
      L 57.574 142.426
      A 60 60 0 0 1 42.044 115.529
      L 11.368 115.628
      A 90 90 0 0 1 11.368 84.372
      L 42.044 84.471
      A 60 60 0 0 1 57.574 57.574
      L 42.149 31.056
      A 90 90 0 0 1 69.218 15.428
      L 84.471 42.044
      A 60 60 0 0 1 115.529 42.044
      L 130.782 15.428
      A 90 90 0 0 1 157.851 31.056
      L 142.426 57.574
      A 60 60 0 0 1 157.956 84.471
      Z
      M 100 68.32
      A 31.68 31.68 0 1 0 100 131.68
      A 31.68 31.68 0 1 0 100 68.32
      Z
    "/>
  </g>
</svg>
`;
