#!/usr/bin/env node
/**
 * Serve the GitHub Pages build exactly as Pages serves it — under `/reflex-physical-ai/`.
 *
 * Why this exists rather than `npx vite preview`: a project page is not served from the domain root,
 * and the single most common Pages failure is a build that works at `http://localhost:4173/` and
 * 404s at `https://<user>.github.io/reflex-physical-ai/`. This server reproduces the sub-path, so
 * `make pages-serve` is a real dress rehearsal: if the bundle, the assets or the base path are wrong,
 * it fails here instead of on the deployed site.
 *
 * Two extra mounts, both for `scripts/record-demo.ts`:
 *   /stage/    the video's title, terminal and close cards (static HTML, part of the repository)
 *   /capture/  files the recorder wrote at run time (real command output, the real LIMITATIONS.md)
 *
 * No dependencies: node:http and node:fs only, so it runs in a fresh checkout.
 */

import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import { extname, join, normalize, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const REPO = resolve(HERE, '..')
const DIST = join(REPO, 'frontend', 'dist')
const STAGE = join(HERE, 'stage')

const BASE = '/reflex-physical-ai/'
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4',
}

/** Resolve a URL path inside `root`, refusing anything that escapes it. */
function safeJoin(root, relative) {
  const cleaned = normalize(decodeURIComponent(relative)).replace(/^([/\\])+/, '')
  const target = join(root, cleaned)
  return target === root || target.startsWith(root + sep) ? target : null
}

function send(response, status, body, type = 'text/plain; charset=utf-8') {
  response.writeHead(status, { 'content-type': type, 'cache-control': 'no-store' })
  response.end(body)
}

function sendFile(request, response, file) {
  const type = TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream'
  const size = statSync(file).size
  // Range support: Chromium will not play a <video> without it, and the recorder plays one back when
  // it verifies the take.
  const range = request.headers.range
  if (range?.startsWith('bytes=')) {
    const [startText, endText] = range.slice(6).split('-')
    const start = Number.parseInt(startText, 10) || 0
    const end = endText ? Math.min(Number.parseInt(endText, 10), size - 1) : size - 1
    response.writeHead(206, {
      'content-type': type,
      'content-length': end - start + 1,
      'content-range': `bytes ${start}-${end}/${size}`,
      'accept-ranges': 'bytes',
      'cache-control': 'no-store',
    })
    createReadStream(file, { start, end }).pipe(response)
    return
  }
  response.writeHead(200, {
    'content-type': type,
    'content-length': size,
    'accept-ranges': 'bytes',
    'cache-control': 'no-store',
  })
  createReadStream(file).pipe(response)
}

export function createPagesServer({ dist = DIST, stage = STAGE, capture = null, root = false } = {}) {
  return createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://localhost')
    const pathname = url.pathname

    if (root && pathname === '/') {
      response.writeHead(302, { location: BASE })
      response.end()
      return
    }

    const mounts = [
      { prefix: '/stage/', root: stage },
      { prefix: '/capture/', root: capture },
      { prefix: BASE, root: dist },
    ]

    for (const mount of mounts) {
      if (!mount.root || !pathname.startsWith(mount.prefix)) continue
      let relative = pathname.slice(mount.prefix.length)
      if (relative === '' || relative.endsWith('/')) relative += 'index.html'
      const file = safeJoin(mount.root, relative)
      if (!file) {
        send(response, 400, '{"error":"bad path"}', TYPES['.json'])
        return
      }
      if (existsSync(file) && statSync(file).isFile()) {
        sendFile(request, response, file)
        return
      }
      // A Pages site is a static site: an unknown path is a 404, not an index fallback. Saying so is
      // the point — a silent SPA fallback would mask a real missing asset in the deployed build.
      send(response, 404, `404 ${pathname} — not in the build`, TYPES['.txt'])
      return
    }

    send(response, 404, `404 ${pathname} — Pages serves this site under ${BASE}`, TYPES['.txt'])
  })
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  const port = Number.parseInt(process.env.PORT ?? '4173', 10)
  const host = process.env.HOST ?? '0.0.0.0'
  if (!existsSync(join(DIST, 'index.html'))) {
    console.error(`no build at ${DIST}/index.html — run \`make build-pages\` first`)
    process.exit(1)
  }
  createPagesServer({ root: true }).listen(port, host, () => {
    console.log(`Pages preview: http://localhost:${port}${BASE}`)
    console.log(`serving        ${DIST}`)
    console.log('press Ctrl-C to stop')
  })
}
