// E:\AppProject\ChanTheory\frontend\chan-theory-ui\vite.config.js
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

export default defineConfig({
  plugins: [
    vue(),
    // NEW: 开发中间件，打印 /api 请求（终端可见）
    {
      name: "trace-api-middleware", // NEW
      configureServer(server) { // NEW
        server.middlewares.use((req, _res, next) => { // NEW
          try { // NEW
            if (req.url && req.url.startsWith("/api")) { // NEW
              console.log(`[${Date.now()}][frontend/vite.config.js] dev-proxy incoming ${req.method} ${req.url}`); // NEW
            } // NEW
          } catch {} // NEW
          next(); // NEW
        }); // NEW
      }, // NEW
    }, // NEW
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    open: true,
    host: "localhost",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p,
      },
    },
  },
});
