import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Benchmarking dashboard. Ports are deliberately off the Vite/uvicorn defaults
// (5173/8000) because those commonly collide with other projects running on the
// same machine -- and a collision is quiet: Vite shifts to the next free port
// while /api keeps proxying to whatever already owns 8000.
//
// strictPort makes that failure loud instead: better to refuse to start than to
// come up on a port the proxy config does not match.
export default defineConfig({
  server: {
    port: 5273,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8010',
        rewrite: (path) => path.replace(/^\/api/, ''),
        changeOrigin: true,
      },
    },
  },
  plugins: [react()],
})
