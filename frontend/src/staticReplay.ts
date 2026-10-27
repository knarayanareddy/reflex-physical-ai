/**
 * Static replay: the dashboard with no backend.
 *
 * On GitHub Pages there is no FastAPI process, no ledger and no `POST /v1/envelope/evaluate`. Rather
 * than let the browser decide anything — which would make the page a puppet show instead of a
 * window onto the envelope — the site ships a *recording*: `jobs/export_static_replay.py` runs the
 * real 10-second session through `app.envelope.evaluate`, `app.decision_ledger.record_decision` and
 * `app.replay.compare`, and writes every payload those functions returned into `bundle.json`.
 *
 * This module loads that file and nothing else. It decides nothing, clamps nothing and simulates
 * nothing: scrubbing the timeline moves through decisions that were already made on a build machine.
 *
 * The build that carries the bundle is produced with `npm run build -- --mode pages`; `MODE` is how
 * the rest of the app tells the two deployments apart (`vite.config.ts` uses the same signal for the
 * `/reflex-physical-ai/` base path).
 */

import type {
  Decision,
  EnvelopeInfo,
  HeadlineStatistics,
  ReplayComparison,
} from './types'

/** True in the GitHub Pages build, false for `npm run dev` and `make demo`. */
export const STATIC_REPLAY = import.meta.env.MODE === 'pages'

export interface StaticFrame {
  index: number
  t_s: number
  x_mm: number
  y_mm: number
  keep_out_occupied: boolean
  decision_id: string
  decided_at: string
}

export interface StaticCheck {
  claim: string
  evidence: string
}

export interface StaticSession {
  seconds: number
  hz: number
  start_x_mm: number
  speed_mm_s: number
  target_x_mm: number
  intrusion_at_s: number
  frames: number
  synthetic: boolean
  hardware: boolean
  model_calls: number
}

export interface StaticBundle {
  schema: string
  generated_by: string
  source: string
  session: StaticSession
  info: EnvelopeInfo
  headline: HeadlineStatistics | null
  frames: StaticFrame[]
  decisions: Decision[]
  replays: Record<string, ReplayComparison>
  checks: StaticCheck[]
}

export type BundleResult = { ok: true; value: StaticBundle } | { ok: false; error: string }

const SCHEMA = 'reflex.static_replay/1'

let cached: Promise<BundleResult> | null = null

/**
 * Load `replay/bundle.json` once per page load.
 *
 * The URL is built from `import.meta.env.BASE_URL`, so the same code works at `/` (a local preview)
 * and at `/reflex-physical-ai/` (Pages). An absolute `/replay/bundle.json` would 404 on Pages, which
 * is exactly the failure a static deploy discovers last.
 */
export function loadBundle(): Promise<BundleResult> {
  if (cached) return cached
  cached = (async (): Promise<BundleResult> => {
    const url = `${import.meta.env.BASE_URL}replay/bundle.json`
    try {
      const response = await fetch(url, { headers: { accept: 'application/json' } })
      if (!response.ok) {
        return {
          ok: false,
          error:
            `${response.status} ${response.statusText} for ${url}. ` +
            'The bundle is built by `make pages-data`; a Pages deploy without it has nothing to replay.',
        }
      }
      const body = (await response.json()) as StaticBundle
      return check(body, url)
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : String(cause)
      return { ok: false, error: `${reason} (${url})` }
    }
  })()
  return cached
}

/**
 * Refuse a bundle that cannot support what the page will claim.
 *
 * A truncated or half-written file must produce an error state, not a timeline that stops at frame
 * 60 and a headline bar that quietly renders different numbers. These are the same invariants
 * `jobs/export_static_replay.py --check` enforces at build time, restated where the data is consumed.
 */
function check(body: StaticBundle, url: string): BundleResult {
  if (body?.schema !== SCHEMA) {
    return { ok: false, error: `${url} has schema ${String(body?.schema)}, expected ${SCHEMA}` }
  }
  const frames = body.frames ?? []
  const decisions = body.decisions ?? []
  const replays = body.replays ?? {}
  if (frames.length === 0 || frames.length !== decisions.length) {
    return {
      ok: false,
      error: `${url}: ${frames.length} frames but ${decisions.length} decisions — refusing to replay it`,
    }
  }
  const missing = decisions.filter((decision) => !replays[decision.decision_id])
  if (missing.length > 0) {
    return {
      ok: false,
      error: `${url}: ${missing.length} decision(s) have no two-arm replay — refusing to draw a partial session`,
    }
  }
  return { ok: true, value: body }
}

/** Index of the first refusal in the session, or -1 for a session that never refused anything. */
export function firstVetoIndex(bundle: StaticBundle): number {
  return bundle.decisions.findIndex((decision) => decision.outcome === 'VETO')
}

/** Query-parameter deep link, so a screenshot or a video take can start on a specific frame. */
export function initialStep(bundle: StaticBundle): number {
  const raw = new URLSearchParams(window.location.search).get('step')
  const parsed = raw === null ? Number.NaN : Number.parseInt(raw, 10)
  if (Number.isFinite(parsed) && parsed >= 0 && parsed < bundle.decisions.length) return parsed
  const autoplay = new URLSearchParams(window.location.search).get('autoplay')
  return autoplay === null ? firstVetoIndex(bundle) : 0
}

/** True when the page was opened with `?autoplay=1` (used by `scripts/record-demo.ts`). */
export function wantsAutoplay(): boolean {
  return new URLSearchParams(window.location.search).get('autoplay') !== null
}
