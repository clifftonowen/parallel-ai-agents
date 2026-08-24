import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The single front-end. It used to be two apps on 5273 and 5274; the learner
// pages and the benchmark dashboard now share one router, so there is one port.
//
// 5273 rather than Vite's 5173 because the defaults collide with other projects
// on this machine, and the collision is quiet: Vite shifts to the next free port
// while /api keeps proxying to whatever already owns the old one. strictPort
// turns that into a loud failure instead.
const WEB_PORT = Number(process.env.WEB_PORT ?? 5273);

// scripts/dev_api.mjs already honours API_PORT, but its own error message had to
// tell you to come and edit this file by hand when you used it. Reading the same
// variable here closes that gap, so `API_PORT=8011 npm run dev` works end to end
// when something else has taken 8010.
const API_PORT = Number(process.env.API_PORT ?? 8010);

export default defineConfig({
  plugins: [react()],
  server: {
    port: WEB_PORT,
    strictPort: true,
    proxy: {
      // Backend routes are unprefixed, so the /api prefix is stripped here.
      // Deployed, VITE_API_BASE points at the backend origin root with no
      // /api suffix — getting that wrong is a uniform 404 against a healthy
      // backend.
      "/api": {
        target: `http://localhost:${API_PORT}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
