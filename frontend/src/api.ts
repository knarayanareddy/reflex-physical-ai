/**
 * The dashboard's only door to the backend.
 *
 * Everything is a same-origin relative URL: the browser talks to whatever served this page, and
 * the dev server forwards `/v1` to the API. Hard-coding `localhost:8000` here would work on a
 * laptop and fail for every other viewer of the same page.
 *
 * Failures are returned, not thrown: the UI has to render the reason (an unreachable API, a 422
 * with contract problems) instead of an empty screen that looks like a healthy system.
 */

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

export function fetchEnvelopeInfo(): Promise<Result<EnvelopeInfo>> {
  return getJson<EnvelopeInfo>('/v1/envelope/info')
}

/** Names of the committed fixture corpus, served by the dev server's `/fixtures/` bridge. */
export function fetchFixtureNames(): Promise<Result<string[]>> {
  return getJson<string[]>('/fixtures/')
}

export function fetchFixture(name: string): Promise<Result<Fixture>> {
  return getJson<Fixture>(`/fixtures/${encodeURIComponent(name)}`)
}

/**
 * Evaluate one proposal through the real envelope. This is the only thing on the page that can
 * produce a decision: nothing here computes an outcome, clamps a value or guesses a veto.
 */
export function evaluateRequest(fixture: Fixture): Promise<Result<Decision>> {
  return postJson<Decision>('/v1/envelope/evaluate', {
    snapshot: fixture.snapshot,
    proposal: fixture.proposal,
    requested_mode: fixture.requested_mode,
  })
}

/** The batch job's headline numbers. Absent until `python jobs/batch_1000_eval.py` has run. */
export function fetchHeadlineStatistics(): Promise<Result<HeadlineStatistics>> {
  return getJson<HeadlineStatistics>('/stats/headline.json')
}

export function fetchReplay(decision: Decision): Promise<Result<ReplayComparison>> {
  return postJson<ReplayComparison>('/v1/replay', { decision })
}
