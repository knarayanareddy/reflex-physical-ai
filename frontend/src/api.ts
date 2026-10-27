/**
 * The dashboard's only door to data — and, in the static build, its only door to the *recording*.
 *
 * Live mode talks to the API over same-origin relative URLs: the browser talks to whatever served
 * this page, and the dev server forwards `/v1` to the backend. Hard-coding `localhost:8000` here
 * would work on a laptop and fail for every other viewer of the same page.
 *
 * Static mode (GitHub Pages) answers the same functions from `replay/bundle.json`, which was produced
 * by running the real session through the real envelope. The signature is identical on purpose: the
 * UI cannot accidentally tell whether a decision came back from FastAPI or from the bundle, and it has
 * no code path in which the browser decides an outcome for itself.
 *
 * Failures are returned, not thrown: the UI has to render the reason (an unreachable API, a 422 with
 * contract problems, a missing bundle) instead of an empty screen that looks like a healthy system.
 */

import { STATIC_REPLAY, loadBundle } from './staticReplay'
import type { Decision, EnvelopeInfo, Fixture, HeadlineStatistics, ReplayComparison } from './types'

export type Result<T> = { ok: true; value: T } | { ok: false; error: string }

async function readError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      return typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
    return JSON.stringify(body)
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

async function getJson<T>(path: string): Promise<Result<T>> {
  try {
    const response = await fetch(path, { headers: { accept: 'application/json' } })
    if (!response.ok) return { ok: false, error: await readError(response) }
    return { ok: true, value: (await response.json()) as T }
  } catch (cause) {
    return { ok: false, error: cause instanceof Error ? cause.message : String(cause) }
  }
}

async function postJson<T>(path: string, body: unknown): Promise<Result<T>> {
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) return { ok: false, error: await readError(response) }
    return { ok: true, value: (await response.json()) as T }
  } catch (cause) {
    return { ok: false, error: cause instanceof Error ? cause.message : String(cause) }
  }
}

export async function fetchEnvelopeInfo(): Promise<Result<EnvelopeInfo>> {
  if (STATIC_REPLAY) {
    const bundle = await loadBundle()
    return bundle.ok ? { ok: true, value: bundle.value.info } : bundle
  }
  return getJson<EnvelopeInfo>('/v1/envelope/info')
}

/** Names of the committed fixture corpus, served by the dev server's `/fixtures/` bridge. */
export function fetchFixtureNames(): Promise<Result<string[]>> {
  // The static build has no fixture bridge and no endpoint to evaluate one against, so it reports an
  // empty corpus instead of a network error the UI would render as a broken backend.
  if (STATIC_REPLAY) return Promise.resolve({ ok: true, value: [] })
  return getJson<string[]>('/fixtures/')
}

export function fetchFixture(name: string): Promise<Result<Fixture>> {
  if (STATIC_REPLAY) {
    return Promise.resolve({ ok: false, error: 'static replay: the fixtures are not served on Pages' })
  }
  return getJson<Fixture>(`/fixtures/${encodeURIComponent(name)}`)
}

/**
 * Evaluate one proposal through the real envelope. This is the only thing on the page that can
 * produce a decision: nothing here computes an outcome, clamps a value or guesses a veto.
 */
export function evaluateRequest(fixture: Fixture): Promise<Result<Decision>> {
  if (STATIC_REPLAY) {
    return Promise.resolve({
      ok: false,
      error:
        'static replay: this page holds a recording, not an envelope. Evaluate against the local ' +
        'API (`make demo`) — the browser is not allowed to decide.',
    })
  }
  return postJson<Decision>('/v1/envelope/evaluate', {
    snapshot: fixture.snapshot,
    proposal: fixture.proposal,
    requested_mode: fixture.requested_mode,
  })
}

/** The batch job's headline numbers. Absent until `python jobs/batch_1000_eval.py` has run. */
export async function fetchHeadlineStatistics(): Promise<Result<HeadlineStatistics>> {
  if (STATIC_REPLAY) {
    const bundle = await loadBundle()
    if (!bundle.ok) return bundle
    // `null` in the bundle means the build machine had no statistics file. Say so; never send zeros.
    return bundle.value.headline
      ? { ok: true, value: bundle.value.headline }
      : { ok: false, error: 'the static bundle was built without runs/headline_statistics.json' }
  }
  return getJson<HeadlineStatistics>('/stats/headline.json')
}

export async function fetchReplay(decision: Decision): Promise<Result<ReplayComparison>> {
  if (STATIC_REPLAY) {
    const bundle = await loadBundle()
    if (!bundle.ok) return bundle
    const recorded = bundle.value.replays[decision.decision_id]
    return recorded
      ? { ok: true, value: recorded }
      : { ok: false, error: `no recorded replay for decision ${decision.decision_id}` }
  }
  return postJson<ReplayComparison>('/v1/replay', { decision })
}
