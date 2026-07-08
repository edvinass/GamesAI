import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

const apiTarget = process.env.VITE_API_PROXY || 'http://localhost:8000'
const wsTarget = apiTarget.replace(/^http/, 'ws')

const katagoModelProxy = {
  target: 'https://github.com/lightvector/KataGo/releases/download/v1.13.2-kata9x9',
  changeOrigin: true,
  rewrite: () => '/kata9x9-b18c384nbt-20231025.bin.gz',
}

const coopHeaders = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    headers: coopHeaders,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
      '/models/kata9x9.bin.gz': katagoModelProxy,
    },
  },
  preview: {
    headers: coopHeaders,
    proxy: {
      '/models/kata9x9.bin.gz': katagoModelProxy,
    },
  },
})
