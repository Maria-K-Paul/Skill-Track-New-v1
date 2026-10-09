import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Like production (render.yaml), the site calls /api/* on its own address and that is forwarded to the API with
// /api removed. Same-site requests let the browser keep the httpOnly refresh cookie.
const apiProxy = {
  '/api': {
    target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
})
