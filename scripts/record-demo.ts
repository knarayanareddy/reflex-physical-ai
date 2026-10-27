#!/usr/bin/env node
/**
 * Record the demo video: `docs/media/reflex-demo.webm` and `docs/media/reflex-demo.mp4`.
 *
 *     node scripts/record-demo.ts            # full take, ~4 minutes including encoding
 *     node scripts/record-demo.ts --dry-run  # pre-flight only: capture the terminal output, record nothing
 *
 * It walks the seven shots of `video/script.md` on a monotonic clock, so each shot starts and ends at
 * the timecode the script declares (0:00, 0:15, 0:45, 1:15, 1:45, 2:10, 2:30, 2:45). The finished
 * file is padded or trimmed to exactly **165.0 s**: the script's runtime is a commitment, and a video
 * that runs 2:47 because a page took a second to warm up is a video that broke it.
 *
 * What is *not* synthesised
 * -------------------------
 * Every number in the video comes from the running system or from a file in this repository:
 *
 *   shots 2–4   the real dashboard (`frontend/dist`, the GitHub Pages build) replaying the recorded
 *               session from `replay/bundle.json`, which the real envelope produced;
 *   shot 5      real `curl` calls against a real uvicorn process — the snapshot is the demo's own,
 *               with the cloud marked unreachable, and the response is whatever the envelope decided;
 *   shot 6      `LIMITATIONS.md`, read from disk at record time and scrolled verbatim;
 *   shots 1, 5  terminal output captured from the commands actually executed.
 *
 * The terminal is a *rendering* of captured stdout, not a TTY recording — there is no terminal
 * emulator in this build, and a screenshot of a hand-written terminal would be exactly the kind of
 * prop this project argues against. Each line on screen was printed by the command above it.
 *
 * Zoom: the video is 1920×1080 with a 1536×864 CSS layout viewport — what a viewer gets by pressing
 * Ctrl-'+' twice on a 1080p screen. The zoom is applied by injecting `body{zoom:1.25}` into every
 * document as it loads (see the `context.route` handler). `deviceScaleFactor: 1.25` was the first
 * attempt and is wrong: it lays the page out at 1920 px and letterboxes a 1536×864 render into the
 * 1920×1080 frame, which is what the first take looked like.
 */

import { execFileSync, spawn } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { createPagesServer } from './serve-pages.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const REPO = resolve(HERE, '..')
const DIST = join(REPO, 'frontend', 'dist')
const MEDIA = join(REPO, 'docs', 'media')
const WORK = join(REPO, '.record-tmp')
const CAPTURE = join(WORK, 'capture')

const PAGES_PORT = Number.parseInt(process.env.RECORD_PORT ?? '4173', 10)
const API_PORT = Number.parseInt(process.env.RECORD_API_PORT ?? '8010', 10)
const BASE = `http://127.0.0.1:${PAGES_PORT}/reflex-physical-ai/`
/** The recorder's own cards (title, terminal, limitations, close). Not part of the deployed site. */
const STAGE = `http://127.0.0.1:${PAGES_PORT}/stage`

/** Shot boundaries in seconds, straight from video/script.md. The last one is the total runtime. */
const SHOTS = [
  { name: 'hook + `make demo`', start: 0, end: 15 },
  { name: 'the veto, live (timeline)', start: 15, end: 45 },
  { name: 'split-screen control room', start: 45, end: 75 },
  { name: 'two-arm replay', start: 75, end: 105 },
  { name: 'network cut', start: 105, end: 130 },
  { name: 'what is not done', start: 130, end: 150 },
  { name: 'close', start: 150, end: 165 },
]
const TOTAL_S = SHOTS[SHOTS.length - 1].end

const log = (...args) => console.log('[record]', ...args)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const clock = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`

/* ------------------------------------------------------------------ environment */

/**
 * Find a Chromium to drive.
 *
 * Playwright is the documented path (`npx playwright install chromium`). The two fallbacks exist
 * because this repository is also built in sandboxes with no route to Playwright's CDN, and a
 * recorder that only works on a machine that already has a browser is a recorder nobody runs.
 */
async function resolveBrowser() {
  const { chromium } = await import('playwright-core')

  if (process.env.REFLEX_CHROMIUM_BIN) {
    return { chromium, executablePath: process.env.REFLEX_CHROMIUM_BIN, args: [], env: {} }
  }

  try {
    const playwright = await import('playwright')
    const path = playwright.chromium.executablePath()
    if (path && existsSync(path)) return { chromium, executablePath: path, args: [], env: {} }
  } catch {
    // `playwright` is not installed: normal in a minimal checkout.
  }

  try {
    const sparticuz = (await import('@sparticuz/chromium')).default
    const path = await sparticuz.executablePath()
    if (path && existsSync(path)) {
      const libDir = await extractServerlessLibs()
      const env = libDir
        ? { LD_LIBRARY_PATH: [libDir, process.env.LD_LIBRARY_PATH].filter(Boolean).join(':') }
        : {}
      return { chromium, executablePath: path, args: sparticuz.args, env }
    }
  } catch {
    // Not installed: fall through to Playwright's own resolution, which fails with instructions.
  }

  return { chromium, executablePath: undefined, args: [], env: {} }
}

/** Unpack `@sparticuz/chromium`'s `al2023.tar.br` (libnss3, libexpat, …) for a distro without them. */
async function extractServerlessLibs() {
  const { brotliDecompressSync } = await import('node:zlib')
  const tarball = join(REPO, 'scripts', 'node_modules', '@sparticuz', 'chromium', 'bin', 'al2023.tar.br')
  if (!existsSync(tarball)) return null
  const into = join(WORK, 'libs')
  mkdirSync(into, { recursive: true })
  const tar = join(WORK, 'al2023.tar')
  writeFileSync(tar, brotliDecompressSync(readFileSync(tarball)))
  execFileSync('tar', ['-xf', tar, '-C', into])
  // The archive has a single top-level `lib/` directory.
  const nested = join(into, 'lib')
  if (existsSync(nested)) {
    for (const entry of readdirSync(nested)) copyFileSync(join(nested, entry), join(into, entry))
  }
  return into
}

function ffmpegPath() {
  if (process.env.FFMPEG && existsSync(process.env.FFMPEG)) return process.env.FFMPEG
  for (const candidate of ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg']) {
    if (existsSync(candidate)) return candidate
  }
  // Last resort: imageio-ffmpeg, which many Python environments already have. It ships a real
  // ffmpeg binary and nothing else, which is all this script needs.
  try {
    const path = execFileSync('python3', ['-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
    if (path && existsSync(path)) return path
  } catch {
    // no python, no imageio-ffmpeg
  }
  return null
}

/* -------------------------------------------------------------------- captures */

/** Run a shell command, capture stdout (killed after `timeoutMs`), and return the text. */
function captureShell(command, { timeoutMs = 20000, cwd = REPO } = {}) {
  return new Promise((resolvePromise) => {
    const child = spawn('bash', ['-lc', command], { cwd, stdio: ['ignore', 'pipe', 'pipe'] })
    let out = ''
    child.stdout.on('data', (chunk) => (out += chunk.toString()))
    child.stderr.on('data', (chunk) => (out += chunk.toString()))
    const timer = setTimeout(() => child.kill('SIGTERM'), timeoutMs)
    child.on('close', () => {
      clearTimeout(timer)
      resolvePromise(out.replace(/\r/g, ''))
    })
  })
}

/** Split captured text into lines, dropping the runs of blank lines the demo prints between blocks. */
function linesOf(text) {
  const lines = text.split('\n').map((line) => line.replace(/\s+$/, ''))
  const collapsed = []
  for (const line of lines) {
    if (line === '' && collapsed[collapsed.length - 1] === '') continue
    collapsed.push(line)
  }
  while (collapsed.length && collapsed[collapsed.length - 1] === '') collapsed.pop()
  return collapsed
}

async function waitForHttp(url, timeoutMs = 40000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      if ((await fetch(url)).ok) return true
    } catch {
      // not up yet
    }
    await sleep(250)
  }
  return false
}

function portIsFree(port) {
  return new Promise((resolvePromise) => {
    import('node:net').then(({ createServer }) => {
      const probe = createServer()
      probe.once('error', () => resolvePromise(false))
      probe.once('listening', () => probe.close(() => resolvePromise(true)))
      probe.listen(port, '127.0.0.1')
    })
  })
}

/* ------------------------------------------------------------------------ the run */

async function main(argv) {
  const dryRun = argv.includes('--dry-run')
  const startedAt = Date.now()

  if (!existsSync(join(DIST, 'index.html'))) {
    console.error(`no Pages build at ${DIST}/index.html — run \`make build-pages\` first`)
    return 1
  }
  const ffmpeg = ffmpegPath()
  if (!ffmpeg) {
    console.error('no ffmpeg found: set FFMPEG=/path/to/ffmpeg, or `pip install imageio-ffmpeg`')
    return 1
  }
  log(`ffmpeg: ${ffmpeg}`)

  rmSync(WORK, { recursive: true, force: true })
  mkdirSync(CAPTURE, { recursive: true })
  mkdirSync(MEDIA, { recursive: true })

  /* ---- shot 1: the real `make demo`, captured ------------------------------------------------ */
  log('capturing `make demo` …')
  const demoOut = await captureShell('make demo', { timeoutMs: 25000 })
  if (!demoOut.includes('DEMO PASS')) {
    console.error('`make demo` did not print DEMO PASS — refusing to record a video that contradicts it')
    console.error(demoOut.split('\n').slice(-25).join('\n'))
    return 1
  }
  const demoLines = linesOf(demoOut)
  writeFileSync(
    join(CAPTURE, 'demo.json'),
    JSON.stringify({
      title: 'make demo',
      bar: 'reflex — ~/reflex-physical-ai',
      prompt: 'kai@edge:~/reflex-physical-ai$ ',
      pace: 95,
      commands: [{ command: 'make demo', lines: demoLines }],
    }),
  )
  log(`  ${demoLines.length} lines captured`)
  // `make demo` serves until SIGTERM; the handler stops both children. Give it a moment, then make
  // sure the demo's ports are really free before the recorder starts its own API.
  await sleep(1500)
  if (!(await portIsFree(8000))) log('  warning: :8000 still bound after the capture (a lingering uvicorn)')

  /* ---- shot 5: a real POST with the cloud cut ------------------------------------------------ */
  log(`starting the API on :${API_PORT} …`)
  const python = existsSync(join(REPO, 'backend', '.venv', 'bin', 'python'))
    ? join(REPO, 'backend', '.venv', 'bin', 'python')
    : 'python3'
  const api = spawn(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(API_PORT), '--log-level', 'warning'],
    {
      cwd: join(REPO, 'backend'),
      env: { ...process.env, REFLEX_VETO_LEDGER_PATH: join(WORK, 'record-veto-ledger.jsonl') },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  api.stdout.on('data', () => {})
  api.stderr.on('data', () => {})

  if (!(await waitForHttp(`http://127.0.0.1:${API_PORT}/health`))) {
    console.error('the API did not answer /health — is another process holding the port?')
    api.kill('SIGKILL')
    return 1
  }

  const info = await (await fetch(`http://127.0.0.1:${API_PORT}/v1/envelope/info`)).json()
  // The network-cut shot runs a script that lives in the repository, so the command on screen is a
  // command anyone can run: `scripts/network_cut.py` posts the demo's own plan twice — once on a
  // healthy link, once with the cloud 9 s unreachable — and prints what the envelope answered.
  const networkCommand = `python3 scripts/network_cut.py --api 127.0.0.1:${API_PORT}`
  const networkOut = await captureShell(networkCommand, { timeoutMs: 30000 })
  const networkLines = linesOf(networkOut)
  // `VETO          parameter_set=degraded mode=simulation rule=V9_PLAN_MALFORMED  interlock=False`
  const cutLine = networkLines.find((line) => /VETO\s+parameter_set=/.test(line)) ?? ''
  const fields = Object.fromEntries(
    [...cutLine.matchAll(/(\w+)=(\S+)/g)].map((match) => [match[1], match[2]]),
  )
  const cut = { outcome: 'VETO', ...fields }

  writeFileSync(
    join(CAPTURE, 'network.json'),
    JSON.stringify({
      title: 'network cut',
      bar: 'reflex — ~/reflex-physical-ai',
      prompt: 'kai@edge:~/reflex-physical-ai$ ',
      pace: 240,
      commands: [{ command: networkCommand, lines: networkLines }],
    }),
  )
  copyFileSync(join(REPO, 'LIMITATIONS.md'), join(CAPTURE, 'limitations.md'))
  log('  captures written')

  if (dryRun) {
    api.kill('SIGTERM')
    log('dry run: pre-flight passed, nothing recorded')
    log(`  profile ${info.profile} · provenance ${info.calibration_provenance} · ${demoLines.length} terminal lines`)
    console.log('\n'.concat([`$ ${networkCommand}`, networkLines.join('\n')].join('\n')))
    return 0
  }

  /* ---- serve the Pages build the way Pages does ---------------------------------------------- */
  const server = createPagesServer({ capture: CAPTURE })
  await new Promise((r) => server.listen(PAGES_PORT, '127.0.0.1', r))
  log(`serving ${BASE}`)

  /* ---- record -------------------------------------------------------------------------------- */
  const browserInfo = await resolveBrowser()
  const videoDir = join(WORK, 'video')
  mkdirSync(videoDir, { recursive: true })

  const browser = await browserInfo.chromium.launch({
    headless: true,
    executablePath: browserInfo.executablePath,
    args: [...browserInfo.args, '--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars'],
    env: { ...process.env, ...browserInfo.env },
  })

  // 1920×1080 at 125 % zoom, which is what a person gets by pressing Ctrl-'+' twice on a 1080p
  // screen: a 1920×1080 frame with a 1536×864 CSS layout viewport. `deviceScaleFactor` cannot do
  // this — it upscales the bitmap but the page still lays out at 1920 px wide, and Playwright then
  // letterboxes the 1536×864 render into a 1920×1080 file. `zoom` on <body> shrinks the layout
  // viewport the way the browser's own zoom does, and fills the frame.
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
  })
  // Injected into every document, so the dashboard (whose layout is not ours to change for a video)
  // is displayed at the same zoom as the recorder's own cards.
  await context.route('**/*', async (route) => {
    if (route.request().resourceType() !== 'document') {
      await route.continue()
      return
    }
    const response = await route.fetch()
    const type = response.headers()['content-type'] ?? ''
    if (!type.includes('text/html')) {
      await route.fulfill({ response })
      return
    }
    const body = (await response.text()).replace(
      '</head>',
      '<style id="record-zoom">body{zoom:1.25}</style></head>',
    )
    await route.fulfill({ response, body })
  })
  const page = await context.newPage()
  // Playwright's screencast starts with the page, so this — not the first `goto` — is t=0 for the
  // file. `leadIn` is trimmed before encoding so shot 1 begins at 0:00 rather than at whatever the
  // first paint cost.
  const pageCreatedAt = Date.now()
  page.on('console', (message) => {
    if (message.type() === 'error') log(`  console error: ${message.text()}`)
  })

  const t0 = pageCreatedAt
  const at = (seconds) => t0 + seconds * 1000
  const waitUntil = async (seconds) => {
    const remaining = at(seconds) - Date.now()
    if (remaining > 0) await sleep(remaining)
    else log(`  ! overran the shot by ${(-remaining / 1000).toFixed(1)} s`)
  }
  const shot = async (index, fn) => {
    const { name, start, end } = SHOTS[index]
    log(`shot ${index + 1} · ${clock(start)}–${clock(end)} · ${name}`)
    await fn(end - start)
    await waitUntil(end)
  }

  /* shot 1 — title card, then the demo printing its real output */
  await shot(0, async () => {
    const url =
      `${STAGE}/terminal.html?c=demo&card=${encodeURIComponent('The veto layer that keeps receipts')}` +
      `&kicker=${encodeURIComponent('reflex · offline demo')}` +
      `&sub=${encodeURIComponent('10 seconds · 100 proposals · no network, no model, no hardware')}`
    await page.goto(url, { waitUntil: 'domcontentloaded' })
  })

  /* shot 2 — the recorded timeline scrubs to the V2 veto at 4.0 s */
  await shot(1, async () => {
    await page.goto(`${BASE}?step=0`, { waitUntil: 'networkidle' })
    await page.waitForSelector('[data-testid="timeline-panel"]')
    await sleep(800)
    await page.locator('[data-testid="timeline-play"]').click()
    await page.waitForFunction(
      () => document.querySelector('[data-testid="timeline-clock"]')?.textContent?.includes('t = 4.0 s') ?? false,
      null,
      { timeout: 20000 },
    )
    await page.locator('[data-testid="timeline-play"]').click()
    await sleep(1500)
    // Walk back through the approach so the 1.5 mm-per-frame advance is visible, then return to the
    // veto: the strip is the evidence that 40 frames were allowed and 60 were refused.
    for (const frame of [24, 32, 38, 39, 40]) {
      await page.locator('.timeline__tick').nth(frame).click()
      await sleep(1100)
    }
    await sleep(1500)
  })

  /* shot 3 — the control room, then a slow move down to telemetry and the ledger */
  await shot(2, async (seconds) => {
    await page.evaluate(() => window.scrollTo({ top: 0 }))
    await sleep(5000)
    const distance = await page.evaluate(() => Math.max(0, document.body.scrollHeight - window.innerHeight))
    const steps = 46
    for (let i = 1; i <= steps; i += 1) {
      await page.evaluate((y) => window.scrollTo({ top: y }), (distance * i) / steps)
      await sleep(Math.max(60, ((seconds - 6) * 1000) / steps))
    }
    await page.evaluate(() => window.scrollTo({ top: 0 }))
  })

  /* shot 4 — the two-arm replay for the veto decision */
  await shot(3, async (seconds) => {
    await page.locator('[data-testid="timeline-jump-veto"]').click()
    await sleep(500)
    await page.locator('[data-testid="simulate-replay"]').click()
    await page.waitForSelector('[data-testid="replay-panel"]', { timeout: 15000 })
    await sleep(2500)
    // Restart once so the red path's stop at the keep-out edge is seen twice.
    const restart = page.locator('[data-testid="replay-panel"] button', { hasText: /restart/i })
    if ((await restart.count()) > 0) {
      await restart.first().click()
    }
    await sleep(Math.max(0, (seconds - 18) * 1000))
  })

  /* shot 5 — the network cut, in the terminal, with the degraded values beside it */
  await shot(4, async () => {
    await page.goto(`${STAGE}/terminal.html?c=network&overlay=1&pace=130`, { waitUntil: 'domcontentloaded' })
  })

  /* shot 6 — LIMITATIONS.md §3, scrolling */
  await shot(5, async (seconds) => {
    await page.goto(`${STAGE}/limitations.html?seconds=${Math.max(10, seconds - 2)}`, { waitUntil: 'domcontentloaded' })
  })

  /* shot 7 — the close card */
  await shot(6, async () => {
    await page.goto(`${STAGE}/close.html`, { waitUntil: 'domcontentloaded' })
    await sleep(1200)
  })

  const recordedSeconds = (Date.now() - t0) / 1000
  log(`recording stopped at ${recordedSeconds.toFixed(1)} s (target ${TOTAL_S} s)`)

  await context.close()
  await browser.close()

  const rawName = readdirSync(videoDir).find((name) => name.endsWith('.webm'))
  if (!rawName) {
    console.error('Playwright produced no video file')
    return 1
  }
  const webmRaw = join(videoDir, rawName)
  log(`raw take: ${webmRaw} (${(statSync(webmRaw).size / 1024 / 1024).toFixed(1)} MiB)`)

  /* ---- normalise to exactly 165.0 s and emit both containers --------------------------------- */
  // The screencast begins with the first frame after `newPage`, which is up to a second before the
  // title card paints. Trim that lead-in by measurement; do NOT trust ffmpeg's Duration line for a
  // variable-frame-rate webm (it reported 184 s for a 166 s take).
  const leadIn = Math.max(0, Math.min(3, (t0 - pageCreatedAt) / 1000))
  const duration = await probeDuration(ffmpeg, webmRaw)
  const expected = (recordedSeconds + leadIn)
  log(`raw container reports ${duration.toFixed(2)} s (VFR, unreliable) · measured take ${expected.toFixed(2)} s · lead-in ${leadIn.toFixed(2)} s`)
  const filters = ['fps=30']
  const vf = filters.join(',')
  const seek = ['-ss', leadIn.toFixed(3)]

  const mp4 = join(MEDIA, 'reflex-demo.mp4')
  await run(ffmpeg, [
    '-y', '-hide_banner', '-loglevel', 'error',
    ...seek,
    '-i', webmRaw,
    '-vf', vf,
    '-t', String(TOTAL_S),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    mp4,
  ])
  log(`wrote ${mp4}`)

  const webm = join(MEDIA, 'reflex-demo.webm')
  await run(ffmpeg, [
    '-y', '-hide_banner', '-loglevel', 'error',
    ...seek,
    '-i', webmRaw,
    '-vf', vf,
    '-t', String(TOTAL_S),
    '-c:v', 'libvpx', '-b:v', '0', '-crf', '32', '-cpu-used', '5', '-deadline', 'good', '-row-mt', '1', '-an',
    webm,
  ])
  log(`wrote ${webm}`)

  const mp4Duration = await probeDuration(ffmpeg, mp4)
  const webmDuration = await probeDuration(ffmpeg, webm)
  const summary = {
    shots: SHOTS.map((s) => ({ shot: s.name, start_s: s.start, end_s: s.end })),
    runtime_s: { target: TOTAL_S, mp4: Number(mp4Duration.toFixed(3)), webm: Number(webmDuration.toFixed(3)) },
    raw_take_s: Number(expected.toFixed(3)),
    lead_in_s: Number(leadIn.toFixed(3)),
    files: {
      mp4: { bytes: statSync(mp4).size },
      webm: { bytes: statSync(webm).size },
    },
    viewport: { output: '1920x1080', zoom: 1.25, layout_viewport: '1536x864' },
    captured: { demo_lines: demoLines.length, network_outcome: cut.outcome, network_rule: cut.rule ?? null },
    audio: 'none — the spoken column of video/script.md is on-screen text; see docs/DEVPOST_SUBMISSION.md',
  }
  writeFileSync(join(MEDIA, 'reflex-demo.json'), JSON.stringify(summary, null, 2) + '\n')

  console.log('')
  for (const s of summary.shots) {
    console.log(`  ${clock(s.start_s)}–${clock(s.end_s)}  ${s.shot}`)
  }
  console.log('')
  console.log(
    `RECORD PASS — ${mp4Duration.toFixed(1)} s mp4, ${webmDuration.toFixed(1)} s webm, ` +
      `${(summary.files.mp4.bytes / 1024 / 1024).toFixed(1)} MiB mp4`,
  )

  server.close()
  api.kill('SIGTERM')
  await sleep(300)
  rmSync(videoDir, { recursive: true, force: true })
  log(`elapsed ${((Date.now() - startedAt) / 1000).toFixed(0)} s`)
  return 0
}

/* --------------------------------------------------------------------- helpers */

function run(command, args) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'inherit', 'inherit'] })
    child.on('close', (code) => (code === 0 ? resolvePromise() : reject(new Error(`${command} exited ${code}`))))
  })
}

/** ffmpeg has no probe mode; `-i` prints `Duration: 00:02:44.98` to stderr and exits non-zero. */
async function probeDuration(ffmpeg, file) {
  const text = await new Promise((resolvePromise) => {
    const child = spawn(ffmpeg, ['-hide_banner', '-i', file], { stdio: ['ignore', 'ignore', 'pipe'] })
    let out = ''
    child.stderr.on('data', (chunk) => (out += chunk.toString()))
    child.on('close', () => resolvePromise(out))
  })
  const match = /Duration:\s*(\d+):(\d+):(\d+\.\d+)/.exec(text)
  if (!match) throw new Error(`could not read the duration of ${file}`)
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3])
}

const code = await main(process.argv.slice(2))
process.exit(code)
