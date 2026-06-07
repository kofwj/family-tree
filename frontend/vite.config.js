import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/node_modules/vue') || id.includes('/node_modules/@vue/') || id.includes('/node_modules/vue-router/')) return 'vendor-vue'
          if (id.includes('/node_modules/element-plus/') || id.includes('/node_modules/@element-plus/')) return 'vendor-element-plus'
          if (id.includes('/node_modules/@floating-ui/') || id.includes('/node_modules/@popperjs/') || id.includes('/node_modules/@vueuse/')) return 'vendor-element-plus'
          if (id.includes('/node_modules/async-validator/') || id.includes('/node_modules/dayjs/')) return 'vendor-element-plus'
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
