import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    // The FastAPI application serves the SPA from this directory in every
    // environment.  Keeping the Vite output aligned with that contract makes
    // a local or Docker build immediately usable at /admin-v2 and
    // /test-api/admin-v2 instead of leaving the route with an empty shell.
    outDir: '../static/admin-v2',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': {
        target: process.env.ADMIN_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
