# Limitations & honest failure modes — Reflex

> **Read this before relying on any output from this repository.**
>
> This project is built around honesty about its own operating boundaries. In a safety context, knowing when
> a system cannot make a determination is worth more than a confident wrong answer.

**Current state: Phase 1 of 5.** The contracts and the harness exist; the envelope, the replays, the
dashboard and the hardware do not. Nothing here has been used to control a machine.

---

## 1. What this is not

- **Not a certified safety system.** It is a research prototype demonstrating an auditable deterministic
  veto layer. It is not a substitute for a safety-rated controller, a risk assessment under
  ISO 12100 / ISO 13849, or a qualified functional-safety engineer.
- **Not a guarantee of no harm.** No test in this repository has been run against a moving machine,
  because no machine has been wired up yet. The `collisions_in_shipped == 0` field in the contract is a
  *required invariant*, not a measured result.
- **No trademark affiliation.** All references to NVIDIA, Nebius, Nemotron or Cosmos are descriptive of the
  tooling used or intended.

---

## 2. What does not work yet, with numbers

| Area | Measured reality (2026-10-26) | What it would take |
|---|---|---|
| Veto rules implemented | **0 of 10.** The taxonomy is a contract; there is no evaluator | Phase B: `backend/app/envelope/` |
| Envelope parameters | **12 of ~26 values are the literal string `TODO_MEASURE`**; 6 more are `TODO_MEASURE × k` | Rig calibration (D-T06) → `data/calibration/rig-limits.json` |
| Rule fixtures | **0 of 10** named fixtures exist (`data/fixtures/snapshots/*.json`) | One positive and one negative fixture per rule |
| Planner / perception | **No client.** `openai` is installed and unused | Phase B |
| Replay + Serverless Job | **Missing.** `jobs/replay_all.py` does not exist; the folder holds a Dockerfile | Phase B |
| Dashboard | **Missing.** `frontend/` is a 21-line design-token file; `npm run build` exits 1 | Phase C |
| Hardware | **Nothing wired.** No relay, no limit switches, no camera, no measurement | D-T01 (go/no-go), D-T16, D-T17 |
| Veto-to-stop latency / distance | **Not measured** — the fields exist in the contract and are null everywhere | High-fps capture + relay timing |
| Test count | **85 tests, 3 expected failures** (the gate's known gaps) | — |

---

## 3. Known failure modes and mitigations

| # | Failure mode | Root cause | Mitigation in this design |
|---|---|---|---|
| 1 | **Sensor occlusion or uncalibrated camera** | Frame-differencing cannot see through a shadow, a reflection or a dirty lens | Two independent detectors (switch + frame diff); a *missing* detector is a veto, not an absence of evidence |
| 2 | **False positive stops the cell** | Keep-out detection is lighting-dependent | Report the measured rate honestly; tune in D-T24; prefer a slower reliable demo to a fast flaky one |
| 3 | **Stale data acted on as if fresh** | A sensor loop that stalls silently looks identical to a quiet workspace | V7 vetoes on age; the stale window is derived from a measured p99 interval, not guessed |
| 4 | **Planner emits a malformed or expired action** | LLM structured output is untrusted input | V9 rejects schema failures, unmet preconditions, `ttl_ms` expiry and limit requests above the ceiling |
| 5 | **Cloud outage** | Any network-dependent safety layer has a network-shaped failure mode | V8 degrades to stricter parameters and keeps operating; **the envelope never fails open** |
| 6 | **A model claims the workspace is clear when it is not** | Vision models hallucinate | Perception is advisory: its claims may add evidence, never clear a veto. Asserted by a test (`D-T14`, Phase B) |
| 7 | **Parameter values that are theatre** | Copying limits from a datasheet or a paper instead of measuring the rig | Every numeric parameter must trace to a measurement; `scripts/validate_taxonomy.py` fails on undeclared or wrongly-directed values |
| 8 | **The ledger silently loses records** | Non-atomic writes; a path that depends on install mode | Atomic append + `fsync`, explicit `REFLEX_LEDGER_PATH`, dedupe `id`; durability test outstanding (D-T13) |

---

## 4. Coverage boundaries

| Dimension | Supported / evaluated | Out of scope |
|---|---|---|
| **Actuator** | One fixed-base, single-axis pusher or a small cartesian cell | Multi-arm coordination, mobile bases, SLAM, legged locomotion |
| **Sensing** | Coarse occupancy (switch / frame diff / depth), limit switches, encoder position | Full scene reconstruction; object pose estimation at production accuracy |
| **Force** | An *estimate* derived from stall current (labelled an estimate everywhere) | Calibrated force/torque sensing unless a load cell is fitted |
| **Modes** | `normal`, `degraded` (stricter parameters), `simulation` (permanent badge) | Autonomous mode switching without operator visibility |
| **Evidence** | Deterministic rule trace + replay in a simplified simulator | Certification evidence, formal verification, MTBF statistics |

---

## 5. Honesty rules enforced by tooling

1. **A simulation result can never be presented as a hardware result.** The contract's `mode` field and the
   dashboard's permanent SIMULATION badge exist for this.
2. **A VETO always ships a no-op** — a veto with a real shipped action fails schema validation.
3. **A clamp is a partial refusal**, not a success: `ALLOW_CLAMPED` must record the before/after.
4. **`collisions_in_shipped` must be 0**; the contract rejects any other value rather than reporting it.
5. **Unmeasured numbers are labelled.** `TODO_MEASURE` is not a placeholder to be quietly deleted; it is a
   debt that `scripts/validate_taxonomy.py --strict` fails on.
