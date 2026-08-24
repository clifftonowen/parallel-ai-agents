import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Learner frontend, separate from the benchmarking dashboard (5273).
// Ports sit off the Vite/uvicorn defaults because those commonly collide with
// other projects on the same machine, and the collision is quiet: Vite shifts to
// the next free port while /api keeps proxying to whatever already owns 8000.
// strictPort makes it fail loudly instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5274,
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
