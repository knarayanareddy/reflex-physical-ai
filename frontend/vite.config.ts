import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/** The one place the dashboard may read scenario inputs from. Single source of truth: the
 *  repository's committed fixture corpus. Copied into the frontend it would drift, and a
 *  dashboard that evaluates stale fixtures is worse than one that says it cannot load them. */
const FIXTURE_DIR = fileURLToPath(new URL('../data/fixtures/snapshots', import.meta.url))

/**
 * Serves the committed fixtures read-only at `/fixtures/`.
 *
 * Why a dev-server middleware instead of a new HTTP endpoint: adding an endpoint would mean
 * touching the backend for a UI concern, and this ticket's backend surface is fixed. Why not a
 * copy under `public/`: a duplicated corpus silently diverges from the one the tests use.
 *
 * Scope: dev server only. `npm run build` produces no fixture bridge, and the UI then says so
 * rather than inventing a corpus (`fixturesUnavailable` in App.tsx).
 */
function fixtureBridge(): Plugin {
  return {
    name: 'reflex-fixture-bridge',
    configureServer(server) {
      server.middlewares.use('/fixtures/', (request, response) => {
        const name = decodeURIComponent((request.url ?? '/').split('?')[0]).replace(/^\//, '')

        if (!name) {
          const names = readdirSync(FIXTURE_DIR)
            .filter((entry) => entry.endsWith('.json'))
            .sort()
          response.setHeader('content-type', 'application/json')
          response.end(JSON.stringify(names))
          return
        }

        // Allow-list the shape instead of trusting the path: `..%2f` never reaches the fs.
        if (!/^[A-Za-z0-9_-]+\.json$/.test(name)) {
          response.statusCode = 400
          response.end('{"error":"bad fixture name"}')
          return
        }

        const file = resolve(FIXTURE_DIR, name)
        if (!file.startsWith(FIXTURE_DIR + sep) || !existsSync(file)) {
          response.statusCode = 404
          response.end('{"error":"fixture not found"}')
          return
        }

        response.setHeader('content-type', 'application/json')
        response.end(readFileSync(file, 'utf8'))
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), fixtureBridge()],
  server: {
    // The preview host is not localhost; bind all interfaces and accept the proxied Host.
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      // Same-origin in the browser; the dev server forwards to the API. Never hard-code the
      // API host into client code.
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
