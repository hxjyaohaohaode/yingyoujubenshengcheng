import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes(`${path.sep}node_modules${path.sep}react${path.sep}`) || id.includes('react-dom') || id.includes('react-router')) {
            return 'vendor-react'
          }
          if (id.includes('@tanstack')) {
            return 'vendor-query'
          }
          if (id.includes('recharts') || id.includes(`${path.sep}d3${path.sep}`) || id.includes('victory-vendor')) {
            return 'vendor-charts'
          }
          if (id.includes('@xyflow')) {
            return 'vendor-flow'
          }
          if (id.includes('antd') || id.includes('@ant-design') || id.includes('rc-')) {
            return 'vendor-antd'
          }
          return undefined
        },
      },
    },
  },
})
