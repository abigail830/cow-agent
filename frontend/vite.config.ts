import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vite'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

/** Copy udoc worker + WASM into public/ so UDocClient.baseUrl can self-host them. */
function copyUdocAssetsPlugin(): Plugin {
  const copy = () => {
    const pkgRoot = path.join(frontendRoot, 'node_modules', '@docmentis', 'udoc-viewer')
    const outDir = path.join(frontendRoot, 'public', 'udoc')
    const files: Array<[string, string]> = [
      [path.join(pkgRoot, 'dist', 'src', 'worker', 'worker.js'), path.join(outDir, 'worker.js')],
      [path.join(pkgRoot, 'dist', 'src', 'wasm', 'udoc_bg.wasm'), path.join(outDir, 'udoc_bg.wasm')],
    ]
    fs.mkdirSync(outDir, { recursive: true })
    for (const [src, dest] of files) {
      if (!fs.existsSync(src)) {
        throw new Error(`udoc asset missing: ${src} (run npm install in frontend/)`)
      }
      fs.copyFileSync(src, dest)
    }
  }

  return {
    name: 'copy-udoc-assets',
    buildStart() {
      copy()
    },
    configureServer() {
      copy()
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), copyUdocAssetsPlugin()],
  optimizeDeps: {
    exclude: ['@docmentis/udoc-viewer'],
  },
  worker: {
    format: 'es',
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
