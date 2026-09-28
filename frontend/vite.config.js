import { defineConfig } from 'vite';

// D-007 交付形态：
//   开发 —— Vite dev server + proxy 转发 /ws、/api 到后端（免 CORS，各人热更新）
//   交付 —— npm run build 产物落在 frontend/dist，由 FastAPI StaticFiles 托管
//          （backend/config.yaml: frontend.dist = ../frontend/dist，即这里的 outDir）
const BACKEND = process.env.XIAOQI_BACKEND || 'http://127.0.0.1:8000';

export default defineConfig({
  server: {
    host: '0.0.0.0', // 局域网可见：M3-5 要真手机访问
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // three 整包约 760KB（gzip 192KB），属正常体积。
    // M3 接入 glTF 模型与动画后再评估 code-split，暂时抬高告警线避免噪音。
    chunkSizeWarningLimit: 900,
  },
});
