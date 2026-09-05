import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  // Only these non-secret settings are loaded from the repository root.
  const env = loadEnv(mode, '..', 'AITHENA_')
  const port = (key: string, fallback: string) => {
    const raw = process.env[key] || env[key] || fallback
    if (!/^\d+$/.test(raw) || Number(raw) < 1 || Number(raw) > 65535) throw new Error(`${key} must be an integer between 1 and 65535.`)
    return Number(raw)
  }
  const apiPort = port('AITHENA_API_PORT', '8000')
  const webPort = port('AITHENA_WEB_PORT', '3000')
  if (apiPort === webPort) throw new Error('API and web ports must be distinct.')
  return {
    plugins: [react(), tailwindcss()],
    server: { host: '127.0.0.1', port: webPort, strictPort: true, proxy: { '/api': `http://127.0.0.1:${apiPort}` } },
    preview: { host: '127.0.0.1', port: webPort, strictPort: true, proxy: { '/api': `http://127.0.0.1:${apiPort}` } },
  }
})
