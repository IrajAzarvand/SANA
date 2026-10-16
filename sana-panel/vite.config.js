import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const panelDir = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  server: {
    // sana-map is a sibling root-level module shared by the panel.
    fs: { allow: [resolve(panelDir, '..')] },
  },
})