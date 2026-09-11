import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only proxy so the app can mint tokens from a local function without CORS games.
// In production the same path is served by the Netlify function (see netlify/functions/token.ts).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5199,
    proxy: {
      '/api/token': {
        target: process.env.TOKEN_ORIGIN || 'http://127.0.0.1:8888',
        changeOrigin: true,
      },
    },
  },
  build: { outDir: 'dist', sourcemap: false, target: 'es2022' },
})
