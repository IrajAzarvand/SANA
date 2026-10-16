import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const panelDir = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    // The sibling sana-map module shares React with sana-panel.
    alias: [
      { find: /^react\\/jsx-runtime$/, replacement: resolve(panelDir, 'node_modules/react/jsx-runtime.js') },
      { find: /^react\\/jsx-dev-runtime$/, replacement: resolve(panelDir, 'node_modules/react/jsx-dev-runtime.js') },
      { find: /^react$/, replacement: resolve(panelDir, 'node_modules/react/index.js') },
    ],
  },
  server: {
    // sana-map is a sibling root-level module shared by the panel.
    fs: { allow: [resolve(panelDir, '..')] },
  },
})