/**
 * The wire shapes this dashboard consumes, transcribed from the frozen contracts in
 * `schemas/core-schemas.json` ($defs/SensorSnapshot, $defs/ActionProposal, $defs/EnvelopeDecision)
 * and from the response of `GET /v1/envelope/info`.
 *
 * Deliberately not exhaustive: only the fields the UI actually reads are listed, so a field that
 * disappears from the API breaks the type-check here instead of rendering as `undefined` on a
 * safety screen. Nothing in this file is generated, and nothing here is a safety authority — the
 * envelope decides; this only displays.
 */

export type Outcome = 'ALLOW' | 'ALLOW_CLAMPED' | 'VETO'

export type RuleResult =
  | 'PASS'
  | 'VETO'
  | 'CLAMP'
  | 'DEGRADE'
  | 'SKIPPED_MODE'
  | 'SENSOR_MISSING'
  | 'SENSOR_STALE'

export type Severity = 'hard_stop' | 'clamp' | 'degrade' | 'reject'

export interface Pose {
  x: number
  y: number
  z: number
  frame?: string
}

export interface ActionProposal {
  proposal_id: string
  plan_id: string | null
  kind: string
  target_pose: Pose
  velocity_limit: number | null
  force_limit: number | null
  ttl_ms: number
  issued_at: string
  source: string
  is_noop?: boolean
}

export interface EndEffector {
  x: number
  y: number
  z: number
  age_ms: number
  velocity_mm_s?: number | null
}

export interface Network {
  cloud_reachable: boolean
  last_cloud_ok_ms_ago: number | null
  rtt_ms_p99: number | null
}

export interface SensorSnapshot {
  snapshot_id: string
  ts_mono_ms: number
  ts_wall: string
  camera: { age_ms: number; fps_measured?: number | null; frame_idx?: number } | null
  end_effector: EndEffector
  limit_switches?: { min?: boolean; max?: boolean; age_ms?: number }
  keep_out_occupied: boolean
  keep_out_evidence?: { method: string; confidence?: number | null } | null
  force_estimate?: number | null
  force_estimate_method?: string | null
  relay_state: boolean
  e_stop_asserted?: boolean
  network: Network
  device: { device_id: string; firmware_version?: string; temp_c?: number; cpu_pct?: number }
}

export interface RuleTraceEntry {
  rule_id: string
  result: RuleResult
  parameter_set_used: 'normal' | 'degraded' | null
  detail: string | null
}

export interface Decision {
  decision_id: string
  proposal_id: string
  snapshot_id: string
  outcome: Outcome
  rule_id: string | null
  rules_evaluated: string[]
  rule_trace: RuleTraceEntry[]
  first_veto_index: number | null
  intended_action: ActionProposal | null
  intended_action_raw: unknown
  shipped_action: ActionProposal | null
  /** Before/after for every clamp, so a partial refusal is visible rather than inferred. */
  clamp_applied: {
    rule_id: string
    velocity?: [number, number]
    target_pose?: Record<string, unknown> | null
  } | null
  mode: 'normal' | 'degraded' | 'simulation'
  parameter_set: 'normal' | 'degraded'
  interlock_relay_opened: boolean
  relay_click_ts_wall: string | null
  veto_to_stop_latency_ms: number | null
  veto_to_stop_distance_mm: number | null
  latency_us: number
  envelope_version: string
  determinism_hash: string
  decided_at: string
  device_id: string
  buffered_locally: boolean
  sensor_snapshot_inline: SensorSnapshot | null
}

export interface EnvelopeRule {
  rule_id: string
  priority: number
  severity: Severity
  applies_to_modes: string[]
  parameters: {
    normal: Record<string, unknown>
    degraded: Record<string, unknown>
  }
}

export interface Rig {
  actuator: string
  axis: string
  travel_mm: [number, number]
  interlock: string
  keep_out_volume: { x: [number, number]; y: [number, number] }
  sensors: string[]
}

export interface EnvelopeInfo {
  envelope_version: string
  profile: string
  calibration_provenance: string
  measured: boolean
  simulation_badge_required: boolean
  rig: Rig
  rules: EnvelopeRule[]
  veto_ledger_path: string
}

/** A fixture file as committed under `data/fixtures/snapshots/`. */
export interface Fixture {
  case_id: string
  description: string
  requested_mode: 'normal' | 'degraded' | 'simulation'
  expect: { outcome: string; rule_id: string | null }
  snapshot: SensorSnapshot
  proposal: ActionProposal
}

/** One arm of a two-arm replay, transcribed from `$defs/ReplayResult`. */
export interface ReplayResult {
  replay_id: string
  decision_id: string
  arm: 'envelope_off' | 'envelope_on'
  simulator: string
  sim_version: string
  ran_at: string
  seed: number
  outcome: 'completed' | 'collided' | 'out_of_bounds'
  collision: {
    with: string
    at_t_ms: number
    penetration_mm: number | null
    contact_point: { x: number; y: number }
  } | null
  trajectory_sha256: string
  /** [x_mm, y_mm, t_ms] samples, at the simulator's fixed 2 mm step. */
  trajectory_points: [number, number, number][]
  still_image_path: string | null
  metrics: {
    distance_mm: number
    duration_ms: number
    clearance_mm: number | null
    notes: string
  }
}

export interface ReplayComparison {
  decision_id: string | null
  rule_id: string | null
  outcome: Outcome
  envelope_off: ReplayResult
  envelope_on: ReplayResult
  collision_prevented: boolean
  geometry_check: boolean
}

/** `runs/headline_statistics.json`, written by `jobs/batch_1000_eval.py`. */
export interface HeadlineStatistics {
  schema: string
  generated_by: string
  source: string
  session: {
    seed: number
    actions: number
    families: Record<string, number>
    sha256: string
    cadence_hz: number
  }
  headline: {
    actions_planned: number
    vetoes_enforced: number
    collisions_shipped_under_envelope: number
    collisions_prevented: number
  }
  prevented: {
    total: number
    collisions: number
    boundary_excursions: number
    by_rule: Record<string, number>
  }
  vetoes: {
    total: number
    by_rule: Record<string, number>
  }
  decisions: Record<string, number>
  /** Refusals and clamps the 2-D model cannot witness, by rule. Includes V3/V5 clamps, so it is
   *  not a veto count and deliberately does not live under `vetoes`. */
  decisions_without_geometric_counterfactual: Record<string, number>
  shipped: { collisions: number; boundary_excursions: number }
  determinism: {
    envelope_version: string
    profile: string
    calibration_provenance: string
    session_reproducible: boolean
  }
  acceptance: {
    elapsed_ms: number
    under_15_seconds: boolean
    zero_shipped_collisions: boolean
  }
  environment: Record<string, string>
  caveats: string[]
  sandbox_pack?: {
    schema: string
    pack_sha256: string
    content_sha256: string
    counts: Record<string, number>
    network_required: boolean
    verified: boolean
    verify_command: string
  }
}
