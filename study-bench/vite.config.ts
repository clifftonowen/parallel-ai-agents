import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Learner frontend, separate from the benchmarking dashboard.
// Runs on 5174 so it can sit beside dashboard2 (5173); proxies /api to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
