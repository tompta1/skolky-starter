import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: process.env.BASE_PATH ?? '/',
  plugins: [react()],
  optimizeDeps: {
    exclude: ['maplibre-gl'],
    esbuildOptions: { target: 'esnext' },
  },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'node',
    include: ['src/__tests__/**/*.test.ts'],
  },
})
