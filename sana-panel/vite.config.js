import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const panelDir = dirname(fileURLToPath(import.meta.url))
const nodeModules = resolve(panelDir, 'node_modules')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: /^react\/jsx-runtime$/,
        replacement: resolve(nodeModules, 'react/jsx-runtime.js'),
      },
      {
        find: /^react\/jsx-dev-runtime$/,
        replacement: resolve(nodeModules, 'react/jsx-dev-runtime.js'),
      },
      {
        find: /^react$/,
        replacement: resolve(nodeModules, 'react/index.js'),
      },
      {
        find: /^react-leaflet$/,
        replacement: resolve(nodeModules, 'react-leaflet/lib/index.js'),
      },
      {
        find: /^leaflet\/(.*)$/,
        replacement: resolve(nodeModules, 'leaflet/$1'),
      },
      {
        find: /^leaflet$/,
        replacement: resolve(nodeModules, 'leaflet/dist/leaflet-src.js'),
      },
    ],
  },
  server: {
    host: '0.0.0.0',
    fs: {
      allow: [resolve(panelDir, '..')],
    },
  },
})