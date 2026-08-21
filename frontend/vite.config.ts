import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev server proxies /api to the FastAPI backend. Production build lands in dist/,
// which FastAPI serves directly (see backend/app/api.py).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist', emptyOutDir: true },
})
