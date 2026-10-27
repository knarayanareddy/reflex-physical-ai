/**
 * Operator dashboard for the deterministic edge safety envelope.
 *
 * The screen is an argument, laid out left to right:
 *
 *   SCENE        what the planner asked for and what actually shipped, in millimetres;
 *   INTERLOCKS   V1–V10 in priority order, with the value each rule used and what it said;
 *   LEDGER       the telemetry behind one decision and every decision this page has evaluated.
 *
 * Three rules the code keeps, because a safety screen is the easiest place in a project to lie:
 *
 * 1. **Nothing here decides anything.** Outcome, clamp and veto all arrive from
 *    `POST /v1/envelope/evaluate`. If this file computed an outcome, the dashboard would be a
 *    second, unaudited implementation of the thing it is supposed to be showing.
 * 2. **No invented data.** The rule table comes from `GET /v1/envelope/info`; scenario inputs come
 *    from the committed fixture corpus. If either is unavailable the panel says so and stops.
 * 3. **Simulation is never disguised.** When the calibration profile is synthetic the API says
 *    `simulation_badge_required`, and the badge is rendered in the header *and* on the scene.
 *
 * The counterfactual control draws the decision's own intended vs shipped action, which is real
 * but makes no collision claim. A collision claim needs the two-arm simulator, so the per-row
 * "simulate replay" control posts the decision to `POST /v1/replay` and animates the two
 * trajectories the backend returns. The browser never simulates anything itself: a canvas that
 * computed its own collisions would be a second, unaudited safety model.
 *
 * **Static replay (GitHub Pages).** With `--mode pages` there is no backend, so the page loads
 * `replay/bundle.json` — the recorded output of the real session — and the ledger column becomes a
 * timeline scrubber. Rule 1 is unchanged: the browser still only *replays* decisions that were made
 * by `app.envelope.evaluate`. See `staticReplay.ts` for why the bundle exists instead of a
 * client-side envelope.
 */

import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { ChevronRight, Radio, ShieldAlert } from 'lucide-react'

import {
  evaluateRequest,
  fetchEnvelopeInfo,
  fetchFixture,
  fetchFixtureNames,
  fetchHeadlineStatistics,
  fetchReplay,
} from './api'
import {
  STATIC_REPLAY,
  type StaticBundle,
  firstVetoIndex,
  initialStep,
  loadBundle,
  wantsAutoplay,
} from './staticReplay'
import type {
  Decision,
  EnvelopeInfo,
  HeadlineStatistics,
  Outcome,
  ReplayComparison,
  ReplayResult,
  RuleResult,
  RuleTraceEntry,
  Severity,
} from './types'

/* ------------------------------------------------------------------ tokens */

const OUTCOME_TONE: Record<Outcome, string> = {
  ALLOW: 'chip--allow',
  ALLOW_CLAMPED: 'chip--clamp',
  VETO: 'chip--veto',
}

const RESULT_TONE: Record<RuleResult, string> = {
  PASS: 'chip--muted',
  VETO: 'chip--veto',
  CLAMP: 'chip--clamp',
  DEGRADE: 'chip--degrade',
  SKIPPED_MODE: 'chip--muted',
  SENSOR_MISSING: 'chip--clamp',
  SENSOR_STALE: 'chip--clamp',
}

const RESULT_BORDER: Record<RuleResult, string> = {
  PASS: 'interlock--pass',
  VETO: 'interlock--veto',
  CLAMP: 'interlock--clamp',
  DEGRADE: 'interlock--degrade',
  SKIPPED_MODE: '',
  SENSOR_MISSING: 'interlock--clamp',
  SENSOR_STALE: 'interlock--clamp',
}

const SEVERITY_LABEL: Record<Severity, string> = {
  hard_stop: 'hard stop',
  clamp: 'clamp',
  degrade: 'degrade',
  reject: 'reject',
}

const OUTCOME_SENTENCE: Record<Outcome, string> = {
  ALLOW: 'The proposal shipped unchanged.',
  ALLOW_CLAMPED: 'The proposal shipped, with a limit tightened before it reached the actuator.',
  VETO: 'Nothing shipped. The actuator does not move.',
}

/* ------------------------------------------------------------------ helpers */

function Chip({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`chip ${tone}`}>{children}</span>
}

function shortHash(value: string): string {
  const body = value.startsWith('sha256:') ? value.slice(7) : value
  return body.slice(0, 12)
}

function number(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** `{x: [a, b], y: [a, b], z: [a, b]}` out of a rule's parameter blob, or null. */
function volumeOf(params: Record<string, unknown>): {
  x: [number, number]
  y: [number, number]
  z: [number, number]
} | null {
  const candidate = params.allowed_volume
  if (!candidate || typeof candidate !== 'object') return null
  const record = candidate as Record<string, unknown>
  const axis = (key: string): [number, number] | null => {
    const pair = record[key]
    if (!Array.isArray(pair) || pair.length !== 2) return null
    const low = number(pair[0])
    const high = number(pair[1])
    return low === null || high === null ? null : [low, high]
  }
  const x = axis('x')
  const y = axis('y')
  const z = axis('z')
  return x && y && z ? { x, y, z } : null
}

/** Parameters are rendered as `normal → degraded`, never summarised into one number. */
function formatParam(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(1)
  if (Array.isArray(value)) return `[${value.map((item) => formatParam(item)).join(', ')}]`
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, inner]) => `${key} ${formatParam(inner)}`)
      .join(', ')
  }
  return String(value)
}

function paramKeys(parameters: { normal: Record<string, unknown>; degraded: Record<string, unknown> }): string[] {
  return Array.from(new Set([...Object.keys(parameters.normal), ...Object.keys(parameters.degraded)]))
}

const EMPTY_TRACE: RuleTraceEntry[] = []

/* ---------------------------------------------------------------------- App */

export default function App() {
  const [info, setInfo] = useState<EnvelopeInfo | null>(null)
  const [infoError, setInfoError] = useState<string | null>(null)
  const [loadingInfo, setLoadingInfo] = useState(true)

  const [fixtureNames, setFixtureNames] = useState<string[]>([])
  const [fixtureError, setFixtureError] = useState<string | null>(null)
  const [fixtureName, setFixtureName] = useState<string>('')

  const [stats, setStats] = useState<HeadlineStatistics | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)

  const [replayOf, setReplayOf] = useState<Decision | null>(null)

  // Static replay (GitHub Pages) only: the recorded session and the scrub position. In live mode
  // these stay unused and the page behaves exactly as before.
  const [bundle, setBundle] = useState<StaticBundle | null>(null)
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)

  const [ledger, setLedger] = useState<Decision[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [overlay, setOverlay] = useState<'shipped' | 'intended'>('shipped')
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [runNote, setRunNote] = useState<string>('')

  const loadInfo = useCallback(async () => {
    setLoadingInfo(true)
    const result = await fetchEnvelopeInfo()
    if (result.ok) {
      setInfo(result.value)
      setInfoError(null)
    } else {
      setInfo(null)
      setInfoError(result.error)
    }
    setLoadingInfo(false)
  }, [])

  useEffect(() => {
    void loadInfo()

    if (STATIC_REPLAY) {
      // One fetch, one render: the rule table and the headline numbers travel inside the bundle, so
      // the three live-mode requests below would only produce 404s to display as errors.
      void (async () => {
        const loaded = await loadBundle()
        if (!loaded.ok) return // loadInfo() already surfaced the reason through infoError
        setBundle(loaded.value)
        // The headline bar is the page's central claim; in the static build its numbers travel in
        // the bundle, so the bar must leave its loading state here or it would spin forever.
        if (loaded.value.headline) {
          setStats(loaded.value.headline)
          setStatsError(null)
        } else {
          setStats(null)
          setStatsError('the static bundle was built without runs/headline_statistics.json')
        }
        setStatsLoading(false)
        const start = initialStep(loaded.value)
        setStep(start)
        setPlaying(wantsAutoplay() && start === 0)
      })()
      return
    }

    void (async () => {
      setStatsLoading(true)
      const headline = await fetchHeadlineStatistics()
      if (headline.ok) {
        setStats(headline.value)
        setStatsError(null)
      } else {
        setStats(null)
        setStatsError(headline.error)
      }
      setStatsLoading(false)
    })()
    void (async () => {
      const names = await fetchFixtureNames()
      if (names.ok) {
        setFixtureNames(names.value)
        setFixtureError(null)
        setFixtureName((current) => current || (names.value[0] ?? ''))
      } else {
        setFixtureNames([])
        setFixtureError(names.error)
      }
    })()
  }, [loadInfo])

  // The timeline plays at the session's own cadence (10 Hz), which is what the recording was made
  // at: a faster play would misrepresent how the proposals arrived.
  useEffect(() => {
    if (!playing || !bundle) return
    const period = 1000 / bundle.session.hz
    const handle = window.setInterval(() => {
      setStep((current) => {
        if (current >= bundle.decisions.length - 1) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, period)
    return () => window.clearInterval(handle)
  }, [playing, bundle])

  const run = useCallback(async () => {
    if (!fixtureName) return
    setRunning(true)
    setRunError(null)
    setRunNote('')
    const fixture = await fetchFixture(fixtureName)
    if (!fixture.ok) {
      setRunning(false)
      setRunError(`fixture ${fixtureName}: ${fixture.error}`)
      return
    }
    const decision = await evaluateRequest(fixture.value)
    setRunning(false)
    if (!decision.ok) {
      setRunError(`evaluate: ${decision.error}`)
      return
    }
    setLedger((current) => {
      const next = [decision.value, ...current]
      setSelectedIndex(0)
      return next
    })
    setRunNote(
      `${fixtureName} → ${decision.value.outcome}` +
        (decision.value.rule_id ? ` (${decision.value.rule_id})` : '') +
        ` in ${decision.value.latency_us.toFixed(0)} µs`,
    )
  }, [fixtureName])

  const selected = STATIC_REPLAY
    ? (bundle?.decisions[step] ?? null)
    : selectedIndex === null
      ? null
      : (ledger[selectedIndex] ?? null)
  const trace = selected?.rule_trace ?? EMPTY_TRACE

  const rules = useMemo(
    () => (info ? [...info.rules].sort((a, b) => a.priority - b.priority) : []),
    [info],
  )

  if (loadingInfo && !info && !infoError) {
    return (
      <div className="gate">
        <div className="panel">
          <p className="panel__title">Connecting</p>
          <p className="gate__body mono">
            {STATIC_REPLAY ? 'loading replay/bundle.json…' : 'GET /v1/envelope/info…'}
          </p>
        </div>
      </div>
    )
  }

  if (!info) {
    return (
      <div className="gate">
        <div className="gate__card">
          <h1 className="gate__title">No rule table — nothing to show</h1>
          <p className="gate__body">
            The dashboard could not load{' '}
            {STATIC_REPLAY ? (
              <code>replay/bundle.json</code>
            ) : (
              <code>GET /v1/envelope/info</code>
            )}
            , so it has no rule table, no calibration profile and no rig geometry. It will not render
            a placeholder: a safety screen that invents its limits is worse than one that is blank.
          </p>
          <p className="gate__body mono">
            {infoError ?? 'unknown error'}
          </p>
          <p className="gate__body">
            {STATIC_REPLAY ? (
              <>
                This is the static build, so there is no API to start. The bundle is produced by{' '}
                <code>make pages-data</code> and deployed with the site; without it there is nothing
                to replay.
              </>
            ) : (
              <>
                Start the API from the repository root with <code>make demo</code> (uvicorn on
                :8000), then retry. This page talks to the API through a same-origin proxy, so no
                host or port needs to be configured here.
              </>
            )}
          </p>
          <button className="btn btn--primary" onClick={() => void loadInfo()} type="button">
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="shell">
      <Header info={info} onRetry={() => void loadInfo()} staticMode={STATIC_REPLAY} />

      <HeadlineBar stats={stats} error={statsError} loading={statsLoading} />

      <main className="columns">
        <section className="column" aria-label="Scene and verdict">
          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Scene · intended vs shipped</h2>
              {info.simulation_badge_required && <span className="panel-badge">simulation</span>}
            </div>
            <Scene info={info} decision={selected} overlay={overlay} />
            <p className="scene__caption">
              <span>x-y plane, millimetres, from the rig's own calibration</span>
              <span>keep-out x {formatParam(info.rig.keep_out_volume.x)} mm</span>
              {selected?.sensor_snapshot_inline?.keep_out_occupied && (
                <span className="scene__alarm">
                  keep-out occupied — marker position is schematic, occupancy is what the envelope sees
                </span>
              )}
            </p>
            <Legend />
          </div>

          <VerdictPanel decision={selected} onOverlay={setOverlay} overlay={overlay} />
        </section>

        <section className="column" aria-label="Interlock evaluation">
          <div className="panel" style={{ flex: 1 }}>
            <div className="panel__head">
              <h2 className="panel__title">Interlocks · V1–V10</h2>
              <span className="muted mono" style={{ fontSize: 10 }}>
                evaluated in priority order
              </span>
            </div>
            <div className="interlocks">
              {rules.map((rule) => {
                const entry = trace.find((item) => item.rule_id === rule.rule_id)
                const border = entry ? RESULT_BORDER[entry.result] : ''
                return (
                  <article className={`interlock ${border}`} key={rule.rule_id}>
                    <span className="interlock__id">{rule.rule_id}</span>
                    <span className="interlock__meta">
                      <span>p{rule.priority}</span>
                      <span>{SEVERITY_LABEL[rule.severity] ?? rule.severity}</span>
                    </span>
                    <span>
                      {entry ? (
                        <Chip tone={RESULT_TONE[entry.result]}>{entry.result}</Chip>
                      ) : (
                        <Chip tone="chip--muted">not run</Chip>
                      )}
                    </span>

                    <span className="interlock__params">
                      {paramKeys(rule.parameters).length === 0 ? (
                        <span>structural rule — no numeric parameters</span>
                      ) : (
                        paramKeys(rule.parameters)
                          .slice(0, 4)
                          .map((key) => (
                            <span key={key}>
                              {key}{' '}
                              <span className="muted">
                                {formatParam(rule.parameters.normal[key])} →{' '}
                                {formatParam(rule.parameters.degraded[key])}
                              </span>
                            </span>
                          ))
                      )}
                    </span>

                    {entry?.detail && (
                      <span
                        className={`interlock__detail ${entry.result === 'VETO' ? 'interlock__detail--veto' : ''}`}
                      >
                        {entry.detail}
                      </span>
                    )}
                  </article>
                )
              })}
            </div>
            <p className="panel__note">
              Each pair reads normal → degraded. The trace is the decision's own{' '}
              <span className="mono">rule_trace</span>: every rule is recorded, not only the one that
              fired, so the priority logic is visible rather than inferred.
            </p>
          </div>
        </section>

        <section className="column column--ledger" aria-label="Telemetry and veto ledger">
          {STATIC_REPLAY && (
            <TimelinePanel
              bundle={bundle}
              step={step}
              playing={playing}
              onScrub={(next) => {
                setPlaying(false)
                setStep(next)
              }}
              onTogglePlay={() => setPlaying((current) => !current)}
              onSimulateReplay={() => setReplayOf(bundle?.decisions[step] ?? null)}
            />
          )}

          {!STATIC_REPLAY && (
          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Evaluate a committed fixture</h2>
            </div>
            <div className="controls">
              <div className="controls__row">
                <select
                  aria-label="Fixture"
                  value={fixtureName}
                  disabled={fixtureNames.length === 0 || running}
                  onChange={(event) => setFixtureName(event.target.value)}
                >
                  {fixtureNames.length === 0 && <option value="">no fixtures available</option>}
                  {fixtureNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                <button
                  className="btn btn--primary"
                  type="button"
                  disabled={!fixtureName || running}
                  onClick={() => void run()}
                >
                  {running ? 'evaluating…' : 'evaluate'}
                </button>
              </div>
              {fixtureError && (
                <p className="status-line status-line--error">
                  fixture bridge unavailable ({fixtureError}). The corpus is served by the dev
                  server; run <span className="mono">npm run dev</span>.
                </p>
              )}
              {runError && <p className="status-line status-line--error">{runError}</p>}
              {!runError && runNote && <p className="status-line">{runNote}</p>}
            </div>
            <p className="panel__note">
              Inputs are the repository's committed fixtures (<span className="mono">data/fixtures/snapshots</span>),
              posted unchanged to <span className="mono">POST /v1/envelope/evaluate</span>. The
              envelope decides; this page only displays.
            </p>
          </div>

          )}

          <TelemetryPanel decision={selected} />

          {!STATIC_REPLAY && (
          <LedgerPanel
            decisions={ledger}
            selectedIndex={selectedIndex}
            onSelect={(index) => {
              setSelectedIndex(index)
              setOverlay('shipped')
            }}
            onCounterfactual={(index) => {
              setSelectedIndex(index)
              setOverlay('intended')
            }}
            onSimulateReplay={(index) => {
              setSelectedIndex(index)
              setReplayOf(ledger[index] ?? null)
            }}
            overlay={overlay}
          />
          )}
        </section>
      </main>

      {replayOf && (
        <ReplayPanel
          decision={replayOf}
          keepOut={info.rig.keep_out_volume}
          onClose={() => setReplayOf(null)}
        />
      )}
    </div>
  )
}

/* ---------------------------------------------------------- static timeline */

/**
 * The recorded session, scrubbable — the static build's stand-in for the veto ledger.
 *
 * Every frame is a decision the real envelope made on a build machine: the tool tip advances 1.5 mm
 * per frame, the keep-out intrusion lands at t=4.0 s, V2 vetoes and the interlock latches, and the
 * 59 frames after it are refused by V1. The browser computes none of that — the strip is a
 * recording, and the transport only moves a cursor through it.
 *
 * The two-arm replay is the recorded one too (`app.replay.compare` on that exact decision). Pressing
 * "simulate replay" opens the same canvas the live dashboard opens; the word "simulate" is about the
 * *rig*, which does not exist, not about the browser, which is not allowed to invent a trajectory.
 */
function TimelinePanel({
  bundle,
  step,
  playing,
  onScrub,
  onTogglePlay,
  onSimulateReplay,
}: {
  bundle: StaticBundle | null
  step: number
  playing: boolean
  onScrub: (index: number) => void
  onTogglePlay: () => void
  onSimulateReplay: () => void
}) {
  if (!bundle) {
    return (
      <div className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Timeline · recorded session</h2>
        </div>
        <p className="panel__note mono">loading replay/bundle.json…</p>
      </div>
    )
  }

  const { decisions, frames, session, checks } = bundle
  const frame = frames[step]
  const decision = decisions[step]
  const vetoIndex = firstVetoIndex(bundle)
  const replay = bundle.replays[decision.decision_id]
  const snapshot = decision.sensor_snapshot_inline
  const clamp = decision.clamp_applied

  return (
    <div className="panel" data-testid="timeline-panel">
      <div className="panel__head">
        <h2 className="panel__title">Timeline · recorded session</h2>
        <span className="muted mono" style={{ fontSize: 10 }}>
          {frames.length} frames · {session.hz} Hz · no backend
        </span>
      </div>

      <div className="timeline__transport">
        <button
          className="btn btn--primary"
          type="button"
          onClick={onTogglePlay}
          data-testid="timeline-play"
        >
          {playing ? 'pause' : 'play'}
        </button>
        <button
          className="btn"
          type="button"
          onClick={() => onScrub(Math.max(0, step - 1))}
          title="previous frame"
        >
          ‹ prev
        </button>
        <button
          className="btn"
          type="button"
          onClick={() => onScrub(Math.min(frames.length - 1, step + 1))}
          title="next frame"
        >
          next ›
        </button>
        <button
          className="btn"
          type="button"
          data-testid="timeline-jump-veto"
          disabled={vetoIndex < 0}
          onClick={() => onScrub(vetoIndex)}
          title={vetoIndex < 0 ? 'this session never refused anything' : 'the frame V2 fired'}
        >
          veto
        </button>
        <span className="mono muted timeline__clock" data-testid="timeline-clock">
          frame {step + 1} / {frames.length} · t = {frame.t_s.toFixed(1)} s
        </span>
      </div>

      <input
        className="timeline__range"
        type="range"
        min={0}
        max={frames.length - 1}
        step={1}
        value={step}
        aria-label="Session frame"
        onChange={(event) => onScrub(Number(event.target.value))}
      />

      <div className="timeline__strip" role="group" aria-label="Every frame in the session">
        {frames.map((item, index) => {
          const outcome = decisions[index].outcome
          return (
            <button
              key={item.index}
              type="button"
              className={[
                'timeline__tick',
                `timeline__tick--${outcome.toLowerCase().replace('_', '-')}`,
                index === step ? 'is-current' : '',
                index === vetoIndex ? 'is-veto' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onScrub(index)}
              aria-label={`frame ${index + 1}, ${outcome} at ${item.t_s.toFixed(1)} seconds`}
              title={`t=${item.t_s.toFixed(1)} s · x=${item.x_mm.toFixed(1)} mm · ${outcome}${
                decisions[index].rule_id ? ` ${decisions[index].rule_id}` : ''
              }`}
            />
          )
        })}
      </div>

      <dl className="kv kv--dense timeline__readout">
        <dt>tool tip</dt>
        <dd data-testid="timeline-x">
          x = {frame.x_mm.toFixed(1)} mm · y = {frame.y_mm.toFixed(1)} mm
        </dd>
        <dt>keep-out</dt>
        <dd>
          {frame.keep_out_occupied ? (
            <Chip tone="chip--veto">occupied</Chip>
          ) : (
            <Chip tone="chip--muted">clear</Chip>
          )}
        </dd>
        <dt>outcome</dt>
        <dd data-testid="timeline-outcome">
          <Chip tone={OUTCOME_TONE[decision.outcome]}>{decision.outcome}</Chip>{' '}
          <span className="timeline__rule">{decision.rule_id ?? '—'}</span>
        </dd>
        <dt>interlock</dt>
        <dd>
          {decision.interlock_relay_opened ? 'relay opened by this decision' : snapshot?.relay_state === false ? 'open (latched)' : 'closed'}
        </dd>
        {snapshot && (
          <>
            <dt>cloud</dt>
            <dd>
              {snapshot.network.cloud_reachable ? 'reachable' : 'unreachable'} ·{' '}
              {decision.parameter_set} parameters
            </dd>
          </>
        )}
        {clamp && (
          <>
            <dt>clamped</dt>
            <dd>{clamp.rule_id}</dd>
          </>
        )}
        <dt>latency</dt>
        <dd>{decision.latency_us.toFixed(0)} µs (measured on the build machine)</dd>
      </dl>

      <p className="panel__note">{OUTCOME_SENTENCE[decision.outcome]}</p>

      <div className="timeline__replay">
        <button
          className="btn"
          type="button"
          data-testid="simulate-replay"
          onClick={onSimulateReplay}
          title="Play the recorded two-arm replay: envelope OFF vs envelope ON"
        >
          simulate replay
        </button>
        <span className="mono muted timeline__replay-note">
          {replay
            ? `off: ${replay.envelope_off.outcome} · on: ${replay.envelope_on.outcome}` +
              (replay.envelope_off.collision
                ? ` at (${replay.envelope_off.collision.contact_point.x.toFixed(1)}, ` +
                  `${replay.envelope_off.collision.contact_point.y.toFixed(1)}) mm`
                : '')
            : 'no recorded replay'}
        </span>
      </div>

      <div className="timeline__checks">
        <p className="panel__title" style={{ fontSize: 11 }}>
          what the build checked before publishing this recording
        </p>
        <ul>
          {checks.map((item) => (
            <li key={item.claim}>
              <span className="timeline__check-claim">{item.claim}</span>
              <span className="muted mono">{item.evidence}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="panel__note">
        Recorded by <span className="mono">{bundle.generated_by}</span> from{' '}
        <span className="mono">jobs/offline_demo.py</span>: {session.seconds} s at {session.hz} Hz,{' '}
        {session.model_calls} model calls, {session.hardware ? 'hardware attached' : 'no hardware'}.
        The page replays decisions that were already made; it cannot evaluate a new one.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------- header */

function Header({
  info,
  onRetry,
  staticMode,
}: {
  info: EnvelopeInfo
  onRetry: () => void
  staticMode: boolean
}) {
  return (
    <header className="header">
      <div>
        <h1 className="header__title">Reflex</h1>
        <p className="header__subtitle">
          Deterministic edge safety envelope · the cloud proposes, the edge permits
        </p>
      </div>

      <div className="header__meta">
        <span>
          profile <b>{info.profile}</b>
        </span>
        <span>
          provenance <b>{info.calibration_provenance}</b>
        </span>
        <span title={info.envelope_version}>
          envelope <b>{shortHash(info.envelope_version)}</b>
        </span>
        <span>
          ledger <b>{info.veto_ledger_path}</b>
        </span>
      </div>

      <div className="header__status">
        {info.simulation_badge_required ? (
          <span className="simulation-badge" role="status">
            <ShieldAlert size={14} aria-hidden />
            <span className="simulation-badge__dot" aria-hidden />
            simulation · synthetic calibration, not hardware
          </span>
        ) : (
          <Chip tone="chip--allow">measured profile</Chip>
        )}
        {staticMode ? (
          <span
            className="connection connection--static"
            role="status"
            title="This build ships a recording of the 10-second demo session; there is no API behind it."
          >
            <Radio size={12} aria-hidden />
            <span className="connection__dot" aria-hidden />
            replay/bundle.json · recorded, not live
          </span>
        ) : (
          <span className="connection connection--ok" role="status">
            <Radio size={12} aria-hidden />
            <span className="connection__dot" aria-hidden />
            /v1/envelope/info
          </span>
        )}
        <button className="btn" type="button" onClick={onRetry} title="Reload the rule table">
          reload
        </button>
      </div>
    </header>
  )
}

/* -------------------------------------------------------------------- scene */

interface SceneProps {
  info: EnvelopeInfo
  decision: Decision | null
  overlay: 'shipped' | 'intended'
}

function Scene({ info, decision, overlay }: SceneProps) {
  const snapshot = decision?.sensor_snapshot_inline ?? null
  const shipped = decision?.shipped_action ?? null
  const intended = decision?.intended_action ?? null

  const workspace = info.rules.find((rule) => rule.rule_id === 'V5_WORKSPACE_BOUND')
  const normalVolume = workspace ? volumeOf(workspace.parameters.normal) : null
  const degradedVolume = workspace ? volumeOf(workspace.parameters.degraded) : null

  const keepOut = info.rig.keep_out_volume
  const travel = info.rig.travel_mm

  // Domain: everything the rig can reach, plus a margin, so no geometry is clipped away.
  const xs = [travel[0], travel[1], keepOut.x[0], keepOut.x[1]]
  const ys = [keepOut.y[0], keepOut.y[1]]
  for (const volume of [normalVolume, degradedVolume]) {
    if (!volume) continue
    xs.push(volume.x[0], volume.x[1])
    ys.push(volume.y[0], volume.y[1])
  }
  if (snapshot) xs.push(snapshot.end_effector.x)
  if (snapshot) ys.push(snapshot.end_effector.y)
  for (const pose of [intended?.target_pose, shipped?.target_pose]) {
    if (pose) {
      xs.push(pose.x)
      ys.push(pose.y)
    }
  }

  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const padX = Math.max((maxX - minX) * 0.06, 8)
  const padY = Math.max((maxY - minY) * 0.12, 8)
  const spanX = maxX - minX + padX * 2
  const spanY = maxY - minY + padY * 2

  // 100 units wide, height proportional to the true aspect ratio: millimetres stay square, so a
  // circle at (200, 0) sits where it really sits.
  const width = 100
  const height = (100 * spanY) / spanX
  const sx = (x: number) => ((x - (minX - padX)) / spanX) * width
  const sy = (y: number) => height - ((y - (minY - padY)) / spanY) * height
  const rect = (volume: { x: [number, number]; y: [number, number] }) => ({
    x: sx(volume.x[0]),
    y: sy(volume.y[1]),
    width: sx(volume.x[1]) - sx(volume.x[0]),
    height: sy(volume.y[0]) - sy(volume.y[1]),
  })

  const showIntended = overlay === 'intended'
  const intendedIsVeto = decision?.outcome === 'VETO'
  // Occupancy is a boolean in the contract: the envelope knows the volume is occupied, not where the
  // body is standing. The marker is therefore a schematic at the volume's near edge — the point the
  // envelope-off arm reaches when it collides — and never a measured position.
  const intruder = snapshot?.keep_out_occupied ?? false

  return (
    <div className="scene">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Top-down view of the rail, keep-out volume, allowed workspace, and the intended and shipped targets"
      >
        <rect x={0} y={0} width={width} height={height} fill="none" stroke="var(--color-border)" strokeWidth={1} vectorEffect="non-scaling-stroke" />

        {normalVolume && (
          <rect
            {...rect(normalVolume)}
            fill="none"
            stroke="var(--color-text-muted)"
            strokeWidth={1}
            strokeDasharray="2 2"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {degradedVolume && (
          <rect
            {...rect(degradedVolume)}
            fill="none"
            stroke="var(--color-telemetry)"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
        )}

        <rect
          x={sx(keepOut.x[0])}
          y={sy(keepOut.y[1])}
          width={sx(keepOut.x[1]) - sx(keepOut.x[0])}
          height={sy(keepOut.y[0]) - sy(keepOut.y[1])}
          fill="color-mix(in srgb, var(--color-hazard) 10%, transparent)"
          stroke="var(--color-hazard)"
          strokeWidth={1}
          strokeDasharray="3 2"
          vectorEffect="non-scaling-stroke"
        />

        {intruder && (
          <g>
            <circle cx={sx(keepOut.x[0])} cy={sy(0)} r={4.5} fill="var(--color-veto)" opacity={0.9} />
            <circle
              cx={sx(keepOut.x[0])}
              cy={sy(0)}
              r={7}
              fill="none"
              stroke="var(--color-veto)"
              strokeWidth={1}
              strokeDasharray="2 2"
              vectorEffect="non-scaling-stroke"
            />
            <text
              x={sx(keepOut.x[0]) + 9}
              y={sy(0) - 7}
              fontSize={2.8}
              fill="var(--color-veto)"
              fontFamily="var(--font-mono)"
            >
              intruder · keep-out occupied
            </text>
          </g>
        )}

        {/* The rail: the only axis the actuator drives. */}
        <line
          x1={sx(travel[0])}
          y1={sy(0)}
          x2={sx(travel[1])}
          y2={sy(0)}
          stroke="var(--color-border)"
          strokeWidth={3}
          vectorEffect="non-scaling-stroke"
          aria-hidden
        />

        {snapshot && intended?.target_pose && (
          <line
            x1={sx(snapshot.end_effector.x)}
            y1={sy(snapshot.end_effector.y)}
            x2={sx(intended.target_pose.x)}
            y2={sy(intended.target_pose.y)}
            stroke="var(--color-veto)"
            strokeWidth={showIntended ? 2.5 : 1.5}
            strokeDasharray="3 2"
            opacity={showIntended ? 1 : 0.75}
            vectorEffect="non-scaling-stroke"
          />
        )}
        {snapshot && shipped?.target_pose && (
          <line
            x1={sx(snapshot.end_effector.x)}
            y1={sy(snapshot.end_effector.y)}
            x2={sx(shipped.target_pose.x)}
            y2={sy(shipped.target_pose.y)}
            stroke="var(--color-safe)"
            strokeWidth={showIntended ? 1.5 : 2.5}
            opacity={showIntended ? 0.75 : 1}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {snapshot && (
          <circle
            cx={sx(snapshot.end_effector.x)}
            cy={sy(snapshot.end_effector.y)}
            r={2.2}
            fill="var(--color-text-primary)"
            stroke="var(--color-bg-primary)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {intended?.target_pose && (
          <g stroke="var(--color-veto)" strokeWidth={showIntended || intendedIsVeto ? 2.5 : 1.5} vectorEffect="non-scaling-stroke">
            <line
              x1={sx(intended.target_pose.x) - 2.2}
              y1={sy(intended.target_pose.y) - 2.2}
              x2={sx(intended.target_pose.x) + 2.2}
              y2={sy(intended.target_pose.y) + 2.2}
            />
            <line
              x1={sx(intended.target_pose.x) - 2.2}
              y1={sy(intended.target_pose.y) + 2.2}
              x2={sx(intended.target_pose.x) + 2.2}
              y2={sy(intended.target_pose.y) - 2.2}
            />
          </g>
        )}

        {shipped?.target_pose && (
          <circle
            cx={sx(shipped.target_pose.x)}
            cy={sy(shipped.target_pose.y)}
            r={2.4}
            fill="none"
            stroke="var(--color-safe)"
            strokeWidth={showIntended ? 1.5 : 2.5}
            vectorEffect="non-scaling-stroke"
          />
        )}

        <text x={1} y={height - 1.5} fontSize={2.6} fill="var(--color-text-muted)" fontFamily="var(--font-mono)">
          x {minX.toFixed(0)}…{maxX.toFixed(0)} mm
        </text>
        <text x={1} y={3.2} fontSize={2.6} fill="var(--color-text-muted)" fontFamily="var(--font-mono)">
          y {minY.toFixed(0)}…{maxY.toFixed(0)} mm
        </text>
      </svg>
    </div>
  )
}

function Legend() {
  return (
    <div className="legend">
      <span>
        <i style={{ borderTopColor: 'var(--color-hazard)', borderTopStyle: 'dashed' }} aria-hidden />
        keep-out volume
      </span>
      <span>
        <i style={{ borderTopColor: 'var(--color-telemetry)' }} aria-hidden />
        degraded workspace
      </span>
      <span>
        <i style={{ borderTopColor: 'var(--color-text-muted)', borderTopStyle: 'dashed' }} aria-hidden />
        normal workspace
      </span>
      <span>
        <i style={{ borderTopColor: 'var(--color-veto)', borderTopStyle: 'dashed' }} aria-hidden />
        intended (as requested)
      </span>
      <span>
        <i style={{ borderTopColor: 'var(--color-safe)' }} aria-hidden />
        shipped (after the envelope)
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ verdict */

function VerdictPanel({
  decision,
  overlay,
  onOverlay,
}: {
  decision: Decision | null
  overlay: 'shipped' | 'intended'
  onOverlay: (value: 'shipped' | 'intended') => void
}) {
  if (!decision) {
    return (
      <div className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Verdict</h2>
        </div>
        <p className="panel__note">
          No decision yet. Choose a fixture on the right and press <span className="mono">evaluate</span>{' '}
          — the outcome shown here is whatever the envelope returned, never something this page
          calculated.
        </p>
      </div>
    )
  }

  const requested = decision.intended_action
  const shipped = decision.shipped_action
  const clamp = decision.clamp_applied

  return (
    <div className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Verdict</h2>
        <span className="mono muted" title={decision.decision_id}>
          {decision.decision_id.slice(0, 12)}
        </span>
      </div>

      <div className="verdict">
        <div className="verdict__top">
          <Chip tone={OUTCOME_TONE[decision.outcome]}>{decision.outcome}</Chip>
          {decision.rule_id && <span className="verdict__rule">{decision.rule_id}</span>}
          <Chip tone={decision.mode === 'simulation' ? 'chip--sim' : 'chip--muted'}>
            mode {decision.mode}
          </Chip>
          <Chip tone={decision.parameter_set === 'degraded' ? 'chip--degrade' : 'chip--muted'}>
            {decision.parameter_set} limits
          </Chip>
        </div>

        <p className="panel__note" style={{ margin: 0 }}>
          {OUTCOME_SENTENCE[decision.outcome]}
        </p>

        <dl className="kv kv--dense">
          <dt>requested v</dt>
          <dd>{requested?.velocity_limit ?? '—'} mm/s · {requested?.force_limit ?? '—'} N</dd>
          <dt>shipped v</dt>
          <dd>
            {shipped ? `${shipped.velocity_limit ?? '—'} mm/s · ${shipped.force_limit ?? '—'} N` : 'nothing (veto)'}
          </dd>
          {clamp && (
            <>
              <dt>clamped by</dt>
              <dd>
                {clamp.rule_id}
                {clamp.velocity ? ` · v ${clamp.velocity[0]} → ${clamp.velocity[1]}` : ''}
              </dd>
            </>
          )}
          <dt>relay</dt>
          <dd>
            {decision.interlock_relay_opened ? 'opened by this decision' : 'closed'}
            {decision.relay_click_ts_wall ? ` · click ${decision.relay_click_ts_wall}` : ''}
          </dd>
          <dt>veto→stop</dt>
          <dd>
            {decision.veto_to_stop_latency_ms === null
              ? 'not measured (no hardware)'
              : `${decision.veto_to_stop_latency_ms} ms · ${decision.veto_to_stop_distance_mm ?? '—'} mm`}
          </dd>
        </dl>

        <div className="verdict__top">
          <button
            type="button"
            className={`btn ${overlay === 'shipped' ? 'btn--active' : ''}`}
            onClick={() => onOverlay('shipped')}
          >
            {overlay === 'shipped' ? '◀ shipped view' : 'shipped view'}
          </button>
          <button
            type="button"
            className={`btn ${overlay === 'intended' ? 'btn--active' : ''}`}
            onClick={() => onOverlay('intended')}
          >
            counterfactual: intended
            <ChevronRight size={12} aria-hidden style={{ verticalAlign: 'middle' }} />
          </button>
        </div>
        <p className="counterfactual-note">
          This overlay draws the decision's own <span className="mono">intended_action</span> against
          its <span className="mono">shipped_action</span> and makes no collision claim. For the
          collision, press <span className="mono">simulate replay</span> on a ledger row: that posts
          the decision to <span className="mono">POST /v1/replay</span> and animates the two
          trajectories the backend returned.
        </p>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- telemetry */

function TelemetryPanel({ decision }: { decision: Decision | null }) {
  const snapshot = decision?.sensor_snapshot_inline ?? null

  return (
    <div className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Telemetry</h2>
        {snapshot && <span className="muted mono" style={{ fontSize: 10 }}>{snapshot.device.device_id}</span>}
      </div>

      {!snapshot ? (
        <p className="panel__note">No snapshot selected.</p>
      ) : (
        <dl className="kv kv--dense">
          <dt>snapshot</dt>
          <dd>{snapshot.snapshot_id} · {snapshot.ts_wall}</dd>
          <dt>camera</dt>
          <dd>
            {snapshot.camera ? `${snapshot.camera.age_ms.toFixed(0)} ms old` : 'absent'}
            {snapshot.camera?.fps_measured ? ` · ${snapshot.camera.fps_measured.toFixed(0)} fps` : ''}
          </dd>
          <dt>end effector</dt>
          <dd>
            ({snapshot.end_effector.x.toFixed(1)}, {snapshot.end_effector.y.toFixed(1)},{' '}
            {snapshot.end_effector.z.toFixed(1)}) mm · {snapshot.end_effector.velocity_mm_s ?? '—'} mm/s
          </dd>
          <dt>encoder age</dt>
          <dd>{snapshot.end_effector.age_ms.toFixed(0)} ms</dd>
          <dt>force</dt>
          <dd>
            {snapshot.force_estimate ?? '—'} N
            {snapshot.force_estimate_method ? ` · ${snapshot.force_estimate_method}` : ''}
          </dd>
          <dt>keep-out</dt>
          <dd>
            {snapshot.keep_out_occupied ? 'occupied' : 'clear'}
            {snapshot.keep_out_evidence ? ` · ${snapshot.keep_out_evidence.method}` : ''}
          </dd>
          <dt>relay / e-stop</dt>
          <dd>
            {snapshot.relay_state ? 'closed' : 'open'} / {snapshot.e_stop_asserted ? 'asserted' : 'released'}
          </dd>
          <dt>network</dt>
          <dd>
            {snapshot.network.cloud_reachable ? 'reachable' : 'unreachable'} · last ok{' '}
            {snapshot.network.last_cloud_ok_ms_ago ?? '—'} ms · rtt p99 {snapshot.network.rtt_ms_p99 ?? '—'} ms
          </dd>
        </dl>
      )}

      {decision && (
        <>
          <div className="panel__head" style={{ marginTop: 12 }}>
            <h2 className="panel__title">Decision provenance</h2>
          </div>
          <dl className="kv kv--dense">
            <dt>decided</dt>
            <dd>{decision.decided_at}</dd>
            <dt>envelope latency</dt>
            <dd>{decision.latency_us.toFixed(0)} µs</dd>
            <dt>buffered</dt>
            <dd>{decision.buffered_locally ? 'yes — made without the cloud' : 'no'}</dd>
            <dt title={decision.determinism_hash}>hash</dt>
            <dd title={decision.determinism_hash}>{decision.determinism_hash.slice(0, 24)}…</dd>
            <dt title={decision.envelope_version}>envelope</dt>
            <dd title={decision.envelope_version}>{decision.envelope_version.slice(0, 20)}…</dd>
          </dl>
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------- ledger */

function LedgerPanel({
  decisions,
  selectedIndex,
  onSelect,
  onCounterfactual,
  onSimulateReplay,
  overlay,
}: {
  decisions: Decision[]
  selectedIndex: number | null
  onSelect: (index: number) => void
  onCounterfactual: (index: number) => void
  onSimulateReplay: (index: number) => void
  overlay: 'shipped' | 'intended'
}) {
  return (
    <div className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Veto ledger · this session</h2>
        <span className="muted mono" style={{ fontSize: 10 }}>
          {decisions.length} {decisions.length === 1 ? 'decision' : 'decisions'}
        </span>
      </div>

      {decisions.length === 0 ? (
        <p className="ledger__empty">Every decision you evaluate appears here, newest first.</p>
      ) : (
        <table className="ledger">
          <thead>
            <tr>
              <th scope="col">decided</th>
              <th scope="col">outcome</th>
              <th scope="col">rule</th>
              <th scope="col">limits</th>
              <th scope="col">replay</th>
              <th scope="col" aria-label="counterfactual" />
            </tr>
          </thead>
          <tbody>
            {decisions.map((decision, index) => (
              <tr
                key={`${decision.decision_id}-${index}`}
                className={index === selectedIndex ? 'is-selected' : ''}
                onClick={() => onSelect(index)}
              >
                <td>{decision.decided_at.slice(11, 19)}</td>
                <td>
                  <Chip tone={OUTCOME_TONE[decision.outcome]}>{decision.outcome}</Chip>
                </td>
                <td className="ledger__rule">{decision.rule_id ?? '—'}</td>
                <td className="ledger__rule">{decision.parameter_set}</td>
                <td>
                  <button
                    type="button"
                    className="btn"
                    data-testid="simulate-replay"
                    onClick={(event) => {
                      event.stopPropagation()
                      onSimulateReplay(index)
                    }}
                    title="Play the two-arm replay: envelope OFF vs envelope ON"
                  >
                    simulate replay
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    className={`btn ${overlay === 'intended' && index === selectedIndex ? 'btn--active' : ''}`}
                    onClick={(event) => {
                      event.stopPropagation()
                      onCounterfactual(index)
                    }}
                    title="Show what the planner asked for next to what shipped"
                  >
                    counterfactual
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="panel__note">
        The authoritative record is the backend's append-only ledger at{' '}
        <span className="mono">runs/…</span>; every evaluation above was written to it by{' '}
        <span className="mono">record_decision</span>. This table is the page's own history and
        makes no claim to be the full file.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------ headline bar */

const integer = new Intl.NumberFormat('en-US')

/**
 * The batch job's headline numbers, at the top of the page.
 *
 * The one thing this bar must never do is show zeros when the statistics file is missing:
 * "0 Collisions Shipped" is the project's central claim, and manufacturing it out of an
 * absent file would be the exact failure mode this project exists to criticise. So an absent
 * file produces an instruction, not a number.
 */
function HeadlineBar({
  stats,
  error,
  loading,
}: {
  stats: HeadlineStatistics | null
  error: string | null
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="headline headline--muted" role="status">
        loading headline statistics…
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="headline headline--missing" role="status" data-testid="headline-missing">
        <strong>No headline statistics.</strong>{' '}
        <span>
          Nothing is displayed rather than zeros — run{' '}
          <code>python jobs/batch_1000_eval.py</code> to write{' '}
          <code>runs/headline_statistics.json</code>.
        </span>
        {error ? <span className="headline__error"> ({error})</span> : null}
      </div>
    )
  }

  const { headline, session, acceptance, sandbox_pack } = stats
  const shipped = headline.collisions_shipped_under_envelope
  const prevented = stats.prevented

  return (
    <div className="headline" role="status" data-testid="headline-bar">
      <div className="headline__figures">
        <span className="headline__item">
          <b>{integer.format(headline.actions_planned)}</b> Actions Planned
        </span>
        <span className="headline__dot" aria-hidden>
          ·
        </span>
        <span
          className="headline__item"
          data-tone={shipped === 0 ? 'safe' : 'veto'}
          title="Shipped collisions under the envelope, measured by replaying both arms of all 1,000 actions"
        >
          <b>{integer.format(shipped)}</b> Collisions Shipped
        </span>
        <span className="headline__dot" aria-hidden>
          ·
        </span>
        <span className="headline__item" data-tone="veto">
          <b>{integer.format(headline.vetoes_enforced)}</b> Hard Vetoes Enforced
        </span>
        <span className="headline__dot" aria-hidden>
          ·
        </span>
        <span
          className="headline__item"
          data-tone="telemetry"
          title={
            `${stats.prevented.collisions} swept segments entered the keep-out volume or an ` +
            `obstacle under envelope-off. By rule: ` +
            Object.entries(stats.prevented.by_rule)
              .map(([rule, count]) => `${rule} ${count}`)
              .join(', ') +
            `. Together with the boundary excursions below that is ${prevented.total} adverse ` +
            'end-states the envelope stopped (runs/headline_statistics.json → prevented.total).'
          }
        >
          <b>{integer.format(stats.prevented.collisions)}</b> Collisions Prevented in Sim
        </span>
        <span className="headline__dot" aria-hidden>
          ·
        </span>
        <span
          className="headline__item"
          data-tone="telemetry"
          title={
            'Clamped plans (V5) whose envelope-off arm would have left the allowed workspace. ' +
            'These are not contacts, so they are reported separately instead of being added to ' +
            'the collision count.'
          }
        >
          <b>{integer.format(stats.prevented.boundary_excursions)}</b> Boundary Excursions Avoided
        </span>
      </div>

      <div className="headline__meta">
        <span className="chip chip--sim">synthetic session</span>
        <span title={stats.source}>seed {session.seed}</span>
        <span>
          {integer.format(session.actions)} actions · {acceptance.elapsed_ms.toFixed(0)} ms
        </span>
        {sandbox_pack && (
          <span title={`pack ${sandbox_pack.pack_sha256}\n${sandbox_pack.verify_command}`}>
            pack {sandbox_pack.verified ? 'verified' : 'unverified'} ·{' '}
            {sandbox_pack.content_sha256.slice(0, 10)}…
          </span>
        )}
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- replay overlay */

/**
 * The two-arm replay for one decision, drawn on a canvas.
 *
 * Both trajectories are *recorded results* returned by `POST /v1/replay`: red is what the
 * planner asked for with no safety layer, green is what actually shipped. Nothing is
 * computed here — the browser draws points it was given, which is the only way a collision
 * claim on this page can be worth anything.
 */
function ReplayPanel({
  decision,
  keepOut,
  onClose,
}: {
  decision: Decision
  keepOut: { x: [number, number]; y: [number, number] }
  onClose: () => void
}) {
  const [comparison, setComparison] = useState<ReplayComparison | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setComparison(null)
    setError(null)
    void (async () => {
      const result = await fetchReplay(decision)
      if (!alive) return
      if (result.ok) setComparison(result.value)
      else setError(result.error)
    })()
    return () => {
      alive = false
    }
  }, [decision])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="replay-backdrop" onClick={onClose}>
      <section
        className="replay"
        role="dialog"
        aria-modal="true"
        aria-label="Two-arm replay"
        data-testid="replay-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="replay__head">
          <div>
            <h2 className="panel__title">Two-arm replay</h2>
            <p className="replay__sub mono">
              {decision.rule_id ?? decision.outcome} · {decision.decision_id.slice(0, 14)}
            </p>
          </div>
          <button className="btn" type="button" onClick={onClose}>
            close
          </button>
        </header>

        {error && (
          <p className="status-line status-line--error">
            replay unavailable: {error}. The canvas stays empty rather than animating a
            trajectory the backend did not produce.
          </p>
        )}

        {!comparison && !error && <p className="panel__note mono">POST /v1/replay…</p>}

        {comparison && (
          <>
            <ReplayCanvas comparison={comparison} keepOut={keepOut} />
            <div className="replay__verdicts">
              <ReplayArm arm={comparison.envelope_off} tone="veto" label="envelope OFF — as requested" />
              <ReplayArm arm={comparison.envelope_on} tone="safe" label="envelope ON — as shipped" />
            </div>
            <p className="replay__note">
              {comparison.collision_prevented
                ? 'The unguarded arm fails and the shipped arm does not: this is the collision the envelope prevented.'
                : comparison.envelope_off.outcome === comparison.envelope_on.outcome
                  ? 'Both arms end the same way here — this decision is a limit change, not a prevented collision.'
                  : 'The arms differ, but not in a way this 2-D model can call a collision.'}{' '}
              Simulated by <span className="mono">{comparison.envelope_off.simulator}</span>; positions
              only, no contact dynamics.
            </p>
          </>
        )}
      </section>
    </div>
  )
}

function ReplayArm({ arm, tone, label }: { arm: ReplayResult; tone: 'veto' | 'safe'; label: string }) {
  const verdict =
    arm.outcome === 'collided'
      ? `collided with ${arm.collision?.with ?? 'an obstacle'} at ${arm.collision?.at_t_ms ?? '?'} ms`
      : arm.outcome === 'out_of_bounds'
        ? 'left the allowed workspace'
        : arm.trajectory_points.length <= 1
          ? 'did not move'
          : `completed in ${arm.metrics.duration_ms.toFixed(0)} ms`

  return (
    <div className={`replay__arm replay__arm--${tone}`}>
      <span className={`chip chip--${tone === 'veto' ? 'veto' : 'allow'}`}>{arm.outcome}</span>
      <div>
        <p className="replay__arm-label">{label}</p>
        <p className="replay__arm-verdict mono">{verdict}</p>
      </div>
    </div>
  )
}

/**
 * Plays both trajectories at once: time advances, each arm advances along its own samples.
 * The red arm stops where it fails; the green arm stops where it finishes (or immediately,
 * when the envelope shipped nothing).
 */
function ReplayCanvas({
  comparison,
  keepOut,
}: {
  comparison: ReplayComparison
  keepOut: { x: [number, number]; y: [number, number] }
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [playing, setPlaying] = useState(true)
  const [progress, setProgress] = useState(0)

  const off = comparison.envelope_off
  const on = comparison.envelope_on
  const span = Math.max(off.metrics.duration_ms, on.metrics.duration_ms, 1)

  useEffect(() => {
    setProgress(0)
    setPlaying(true)
  }, [comparison])

  useEffect(() => {
    if (!playing) return
    let frame = 0
    let started: number | null = null
    const durationMs = 2200
    const step = (now: number) => {
      if (started === null) started = now
      const next = Math.min(1, (now - started) / durationMs)
      setProgress(next)
      if (next < 1) frame = requestAnimationFrame(step)
      else setPlaying(false)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [playing, comparison])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    drawReplay(canvas, comparison, keepOut, progress, span)
  }, [comparison, keepOut, progress, span])

  return (
    <div className="replay__canvas-wrap">
      <canvas
        ref={canvasRef}
        className="replay__canvas"
        data-testid="replay-canvas"
        width={720}
        height={360}
        role="img"
        aria-label="Two trajectories: the unguarded intended path and the shipped path"
      />
      <div className="replay__controls">
        <button
          className="btn"
          type="button"
          onClick={() => {
            if (progress >= 1) setProgress(0)
            setPlaying((value) => !value)
          }}
        >
          {playing ? 'pause' : progress >= 1 ? 'replay' : 'play'}
        </button>
        <button
          className="btn"
          type="button"
          onClick={() => {
            setProgress(0)
            setPlaying(true)
          }}
        >
          restart
        </button>
        <span className="mono muted">
          t = {(progress * span).toFixed(0)} / {span.toFixed(0)} ms
        </span>
      </div>
    </div>
  )
}

function drawReplay(
  canvas: HTMLCanvasElement,
  comparison: ReplayComparison,
  keepOut: { x: [number, number]; y: [number, number] },
  progress: number,
  span: number,
): void {
  const context = canvas.getContext('2d')
  if (!context) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const cssWidth = canvas.clientWidth || canvas.width
  const cssHeight = canvas.clientHeight || canvas.height
  if (canvas.width !== Math.round(cssWidth * dpr) || canvas.height !== Math.round(cssHeight * dpr)) {
    canvas.width = Math.round(cssWidth * dpr)
    canvas.height = Math.round(cssHeight * dpr)
  }
  context.setTransform(dpr, 0, 0, dpr, 0, 0)
  context.clearRect(0, 0, cssWidth, cssHeight)

  const off = comparison.envelope_off.trajectory_points
  const on = comparison.envelope_on.trajectory_points
  const xs = [...off, ...on].map(([x]) => x).concat([keepOut.x[0], keepOut.x[1]])
  const ys = [...off, ...on].map(([, y]) => y).concat([keepOut.y[0], keepOut.y[1]])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const pad = 28
  const scale = Math.min(
    (cssWidth - pad * 2) / Math.max(maxX - minX, 1),
    (cssHeight - pad * 2) / Math.max(maxY - minY, 1),
  )
  const offsetX = (cssWidth - (maxX - minX) * scale) / 2
  const offsetY = (cssHeight - (maxY - minY) * scale) / 2
  const px = (x: number) => offsetX + (x - minX) * scale
  const py = (y: number) => cssHeight - (offsetY + (y - minY) * scale)

  const styles = getComputedStyle(document.documentElement)
  const colour = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback

  // The keep-out volume, in hazard yellow: the thing the red arm drives into.
  context.save()
  context.fillStyle = 'rgba(255, 234, 0, 0.10)'
  context.strokeStyle = colour('--color-hazard', '#FFEA00')
  context.setLineDash([5, 4])
  context.lineWidth = 1
  context.fillRect(
    px(keepOut.x[0]),
    py(keepOut.y[1]),
    px(keepOut.x[1]) - px(keepOut.x[0]),
    py(keepOut.y[0]) - py(keepOut.y[1]),
  )
  context.strokeRect(
    px(keepOut.x[0]),
    py(keepOut.y[1]),
    px(keepOut.x[1]) - px(keepOut.x[0]),
    py(keepOut.y[0]) - py(keepOut.y[1]),
  )
  context.restore()

  const drawArm = (
    points: [number, number, number][],
    tint: string,
    duration: number,
    dashed: boolean,
  ) => {
    if (points.length === 0) return
    const elapsed = progress * span
    const cut = duration <= 0 ? points.length : points.filter(([, , t]) => t <= elapsed).length
    const visible = cut === 0 ? points.slice(0, 1) : points.slice(0, cut)

    context.save()
    context.strokeStyle = tint
    context.lineWidth = 2.5
    context.setLineDash(dashed ? [6, 5] : [])
    context.beginPath()
    visible.forEach(([x, y], index) => {
      const sx = px(x)
      const sy = py(y)
      if (index === 0) context.moveTo(sx, sy)
      else context.lineTo(sx, sy)
    })
    context.stroke()
    context.restore()

    const [lastX, lastY] = visible[visible.length - 1]
    context.save()
    context.fillStyle = tint
    context.beginPath()
    context.arc(px(lastX), py(lastY), 4, 0, Math.PI * 2)
    context.fill()
    context.restore()
    return { x: lastX, y: lastY }
  }

  // Green first so a failing red arm stays visible on top.
  const onEnd = drawArm(
    on,
    colour('--color-safe', '#00E676'),
    comparison.envelope_on.metrics.duration_ms,
    false,
  )
  const offEnd = drawArm(
    off,
    colour('--color-veto', '#FF1744'),
    comparison.envelope_off.metrics.duration_ms,
    true,
  )

  // The collision marker appears only when the animation has actually reached the failure.
  const failure = comparison.envelope_off.collision
  if (failure && offEnd && progress * span >= failure.at_t_ms - 1e-6) {
    const cx = px(failure.contact_point.x)
    const cy = py(failure.contact_point.y)
    context.save()
    context.strokeStyle = colour('--color-veto', '#FF1744')
    context.lineWidth = 3
    context.beginPath()
    context.moveTo(cx - 7, cy - 7)
    context.lineTo(cx + 7, cy + 7)
    context.moveTo(cx + 7, cy - 7)
    context.lineTo(cx - 7, cy + 7)
    context.stroke()
    context.restore()
  }
  if (onEnd && on.length <= 1) {
    // Below the marker, not beside it: after a veto both arms share the same point, so a label to
    // the right printed straight through the red ✕ and the keep-out border. The plate keeps it
    // readable over the volume's fill.
    const label = 'shipped: no motion'
    context.save()
    context.font = '12px ui-monospace, monospace'
    const width = context.measureText(label).width
    const x = px(onEnd.x) + 12
    const y = py(onEnd.y) + 18
    context.fillStyle = colour('--color-bg-primary', '#0F172A')
    context.globalAlpha = 0.85
    context.fillRect(x - 4, y - 11, width + 8, 16)
    context.globalAlpha = 1
    context.fillStyle = colour('--color-text-secondary', '#94A3B8')
    context.fillText(label, x, y + 1)
    context.restore()
  }
}
