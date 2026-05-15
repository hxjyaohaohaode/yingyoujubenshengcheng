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
        target: `http://127.0.0.1:${process.env.VITE_BACKEND_PORT || '8000'}`,
        changeOrigin: true,
        timeout: 120000,
        proxyTimeout: 120000,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.warn('[vite proxy] error:', err.message)
          })
          proxy.on('proxyReq', (proxyReq, req) => {
            if (req.url?.includes('/stream') || req.url?.includes('/sse')) {
              proxyReq.setHeader('Accept', 'text/event-stream')
              proxyReq.setHeader('Cache-Control', 'no-cache')
            }
          })
          proxy.on('proxyRes', (proxyRes, req) => {
            const ct = proxyRes.headers['content-type'] || ''
            if (ct.includes('text/event-stream') || req.url?.includes('/stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform'
              proxyRes.headers['x-accel-buffering'] = 'no'
              proxyRes.headers['connection'] = 'keep-alive'
              delete proxyRes.headers['content-length']
            }
          })
        },
      },
      '/ws': {
        target: 'ws://127.0.0.1:8001',
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