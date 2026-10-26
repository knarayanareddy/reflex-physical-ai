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
 * The counterfactual control is honest about its scope: it draws the decision's own intended vs
 * shipped action, which is real, and it does not claim a collision — the two-arm geometric replay
 * (`jobs/replay_all.py`) has no HTTP endpoint, so its result cannot be fetched here.
 */

import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { ChevronRight, Radio, ShieldAlert } from 'lucide-react'

import { evaluateRequest, fetchEnvelopeInfo, fetchFixture, fetchFixtureNames } from './api'
import type { Decision, EnvelopeInfo, Outcome, RuleResult, RuleTraceEntry, Severity } from './types'

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

  const selected = selectedIndex === null ? null : (ledger[selectedIndex] ?? null)
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
          <p className="gate__body mono">GET /v1/envelope/info…</p>
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
            The dashboard could not load <code>GET /v1/envelope/info</code>, so it has no rule
            table, no calibration profile and no rig geometry. It will not render a placeholder:
            a safety screen that invents its limits is worse than one that is blank.
          </p>
          <p className="gate__body mono">
            {infoError ?? 'unknown error'}
          </p>
          <p className="gate__body">
            Start the API from the repository root with <code>make demo</code> (uvicorn on :8000),
            then retry. This page talks to the API through a same-origin proxy, so no host or port
            needs to be configured here.
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
      <Header info={info} onRetry={() => void loadInfo()} />

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

          <TelemetryPanel decision={selected} />
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
            overlay={overlay}
          />
        </section>
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------- header */

function Header({ info, onRetry }: { info: EnvelopeInfo; onRetry: () => void }) {
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
        <span className="connection connection--ok" role="status">
          <Radio size={12} aria-hidden />
          <span className="connection__dot" aria-hidden />
          /v1/envelope/info
        </span>
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
          The counterfactual draws this decision's own <span className="mono">intended_action</span>{' '}
          against its <span className="mono">shipped_action</span>. It makes no collision claim: the
          two-arm geometric replay lives in <span className="mono">jobs/replay_all.py</span> and has no
          HTTP endpoint, so its result cannot be fetched here.
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
  overlay,
}: {
  decisions: Decision[]
  selectedIndex: number | null
  onSelect: (index: number) => void
  onCounterfactual: (index: number) => void
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
