import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The single front-end. It used to be two apps on 5273 and 5274; the learner
// pages and the benchmark dashboard now share one router, so there is one port.
//
// 5273 rather than Vite's 5173 because the defaults collide with other projects
// on this machine, and the collision is quiet: Vite shifts to the next free port
// while /api keeps proxying to whatever already owns the old one. strictPort
// turns that into a loud failure instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5273,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8010",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
