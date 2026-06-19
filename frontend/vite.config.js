import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/node_modules/vue/') || id.includes('/node_modules/@vue/') || id.includes('/node_modules/vue-router/')) return 'vendor-vue'
          if (id.includes('/node_modules/echarts/') || id.includes('/node_modules/zrender/')) return 'vendor-echarts'
          if (id.includes('/node_modules/leaflet/')) return 'vendor-leaflet'
          if (id.includes('/node_modules/@vue-flow/') || id.includes('/node_modules/dagre/')) return 'vendor-tree'
          if (id.includes('/node_modules/axios/')) return 'vendor-axios'
          return 'vendor'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
      },
    },
  },
})
