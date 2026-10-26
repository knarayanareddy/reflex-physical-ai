# Limitations & honest failure modes — Reflex

> **Read this before relying on any output from this repository.**
>
> This project is built around honesty about its own operating boundaries. In a safety context, knowing
> when a system cannot make a determination is worth more than a confident wrong answer.

**Current state: Phase 4 of 5 (2026-10-26).** The contracts, the deterministic envelope, the planner
library, the operator dashboard, the 1,000-action batch and the verifiable replay pack exist and are
tested. The hardware, the measured calibration and the cloud job runner do not. Nothing here has been
used to control a machine, and **every limit the envelope enforces is a placeholder** — see §3.

---

## 1. What this is not

- **Not a certified safety system.** It is a research prototype demonstrating an auditable deterministic
  veto layer. It is not a substitute for a safety-rated controller, a risk assessment under ISO 12100 /
  ISO 13849, or a qualified functional-safety engineer.
- **Not a guarantee of no harm.** No test in this repository has been run against a moving machine,
  because no machine has been wired up. The `collisions_in_shipped == 0` field in the contract is a
  *required invariant*, and the "0 collisions shipped" headline is **a result in a simulator**, not a
  hardware observation.
- **Not a demonstration that a machine stops in time.** The ledger records an *intended* interlock
  action (`interlock_relay_opened`). No relay, no brake and no drive is connected, so veto-to-stop
  latency and distance are unmeasured and `null` in every record.
- **No trademark affiliation.** All references to NVIDIA, Nebius, Nemotron or Cosmos are descriptive of
  the tooling used or intended.

---

## 2. The simulator: single-axis, 2-D, positions only

The counterfactual is a **2-D swept-volume model at the recorded end-effector height**. It evaluates
**single-axis translational motion of the tool tip** — a straight line from the current position to the
target, sampled every 2 mm in the x-y plane at the z the snapshot reports.

It is **not a 6-DoF rigid-body contact dynamics simulation** and does not replace one. Concretely, it
cannot represent:

| Missing | Consequence |
|---|---|
| Rotation (3 rotational DoF) | A tool that is thin end-on but wide side-on is modelled as a point; orientation-dependent collisions are invisible |
| z motion within a move | The tool tip's height is held at its starting value; a diagonal descent through an obstacle looks like a straight line in x-y |
| Contact forces, compliance, friction | "Collided" means *the swept segment entered the volume*. Whether that would have been a 2 N tap or a 400 N crush is not modelled |
| Velocity, acceleration and stopping time | The model stops the path at the volume boundary; it does not ask whether the machine could have stopped before it |
| Multi-body geometry (fixtures, cables, the workpiece) | Only the keep-out volume and snapshotted obstacles are obstacles |
| Anything the sensors did not report | The model believes `keep_out_occupied=false` exactly as much as the envelope does |

A displacement-based model answers one question — *"would this motion have entered a region we said was
forbidden?"* — and that is the question the veto asks. Claiming more would be false precision. Anything
about forces, timing or 3-D clearance needs a dynamics engine, a full pose stream and a measured rig.

The same caveat is in the artifact itself: every `ReplayResult` carries `simulator`, `sim_version` and
`metrics.notes`, and `runs/headline_statistics.json` carries the sentence *"The 2-D swept-volume model
covers position in x-y at the recorded end-effector z. It is not contact dynamics and it is not a
physics engine."*

### What the 1,000-action session actually produced

Vetoes, by the rule that fired (sums to the 420 in the README):

| Rule | Vetoes | What the world looked like |
|---|---:|---|
| `V2_KEEP_OUT_OCCUPIED` | **120** | an object inside the marked keep-out volume |
| `V10_HUMAN_PRESENCE` | **80** | a human in the cell |
| `V9_PLAN_MALFORMED` | **70** | no target pose, unknown kind, expired TTL, or a limit request above the ceiling |
| `V6_COLLISION_PREDICTED` | **50** | an obstacle inside the swept corridor |
| `V4_FORCE_LIMIT` | **50** | force estimate over the limit |
| `V7_SENSOR_STALE` | **40** | camera or encoder stopped delivering |
| `V1_EMERGENCY_STOP` | **10** | e-stop asserted, or the interlock relay already open |
| **Total** | **420** | |

The 248 "collisions prevented" split as **170 contacts** (`V2` 120 + `V6` 50 — the envelope-off arm
entered the keep-out volume or an obstacle) and **78 boundary excursions** (`V5` clamps whose
envelope-off arm left the allowed workspace). A boundary excursion is not a contact, which is why the
dashboard prints the two numbers separately and the JSON reports `prevented.collisions` and
`prevented.boundary_excursions` as distinct fields.

The remaining **250 of the 420 vetoes have no geometric counterfactual at all** — force, staleness,
malformed plans, e-stop and presence-without-localisation stop the machine without anything for a 2-D
model to show. They are reported by rule under `decisions_without_geometric_counterfactual` and are
**never counted as prevented collisions**. Any figure that adds them to the 248 is wrong.

---

## 3. What does not work yet, with numbers

| Area | Measured reality (2026-10-26) | What it would take |
|---|---|---|
| Veto rules implemented | **10 of 10**, pure functions in `backend/app/envelope/rules.py` | — |
| Envelope **values** | **22 of 22 are `synthetic`.** `data/calibration/rig-limits.json` has provenance `synthetic`, so every decision is forced to `mode=simulation` | Rig calibration (D-T06); `make params-strict` becomes the gate |
| Contract placeholders | The taxonomy still carries `TODO_MEASURE` text; the envelope never reads it (values come from calibration) | Delete them once a measured profile exists |
| Rule fixtures | **20 of 20** (each rule's trigger and its near miss), checked by `make fixtures` | — |
| Determinism | **500 generated snapshots**, two passes, byte-identical; plus key-order, concurrency, fresh-interpreter and JSON round-trip checks | — |
| Two-arm replay | **2,000 contract-valid `ReplayResult` records** for the 1,000-action session; 34 for the fixture corpus | — |
| Replay pack | **Verifies offline**: 1,000 decisions and 2,000 records re-derived, 0 shipped collisions | Executing it inside a Token Factory Sandbox: no SDK call exists (`TODO_VERIFY(sandbox-sdk)`) |
| Cloud planner | **Library only** (`app/plan/ultra.py`, 38 tests). No endpoint, CLI or dashboard path invokes it | An API route that plans and routes through the envelope |
| Token Factory calls | **0.** No key in the build environment; no telemetry line exists | A key + the route above; `runs/ledger.jsonl` then carries tokens, latency and cost per call |
| Dashboard | **Exists** (React + Vite). Verified by typecheck, production build and jsdom rendering of the real components against the live API — **not** in a browser at multiple widths | A browser pass on the demo machine, including a phone width |
| Hardware | **Nothing wired.** No relay, no limit switches, no camera, no measurement | D-T01 (go/no-go), D-T16, D-T17 |
| Veto-to-stop latency / distance | **Not measured** — the fields exist in the contract and are `null` everywhere | High-fps capture + relay timing |
| Tests | **417 tests, 0 failures** (`make check`) | — |

### What "synthetic" means here, precisely

Every number in `data/calibration/rig-limits.json` was chosen so the fixtures have a clear margin; none
was measured. The loader enforces the consequence rather than trusting a label: a profile whose
`provenance` is not `measurement` sets `mode=simulation` on **every** decision it produces, and
`tests/test_envelope_params.py::test_provenance_decides_the_mode_not_the_request` asserts that no caller
can ask for `normal` and get it back.

The 22 numbers are individually traceable: each has a `kind: synthetic` entry and a note saying what to
measure instead. `python scripts/check_param_provenance.py --strict` is red today, by design.

---

## 4. Known failure modes and mitigations

| # | Failure mode | Root cause | Mitigation in this design |
|---|---|---|---|
| 1 | **Sensor occlusion or uncalibrated camera** | Frame-differencing cannot see through a shadow, a reflection or a dirty lens | Two independent detectors (switch + frame diff); a *missing* detector is a veto, not an absence of evidence |
| 2 | **A false positive stops the cell** | Keep-out detection is lighting-dependent | The demo prints the decision latency per run; the false-positive rate is unmeasured and is listed above as such |
| 3 | **Stale data acted on as if fresh** | A sensor loop that stalls silently looks identical to a quiet workspace | V7 vetoes on age; the stale window is derived from a measured p99 interval, not guessed |
| 4 | **Planner emits a malformed or expired action** | LLM structured output is untrusted input | V9 rejects schema failures, unmet preconditions, `ttl_ms` expiry and limit requests above the ceiling |
| 5 | **Cloud outage** | Any network-dependent safety layer has a network-shaped failure mode | V8 degrades to stricter parameters and keeps operating; 60 tests pin that it never fails open |
| 6 | **A model claims the workspace is clear when it is not** | Vision models hallucinate | Perception is advisory: its claims may add evidence, never clear a veto |
| 7 | **Parameter values that are theatre** | Copying limits from a datasheet or a paper instead of measuring the rig | Every numeric parameter must trace to a measurement; `scripts/validate_taxonomy.py` fails on undeclared or wrongly-directed values |
| 8 | **The ledger silently loses records** | Non-atomic writes; a path that depends on install mode | Atomic append + `fsync`, explicit `REFLEX_LEDGER_PATH`, dedupe by `id`; durability test outstanding (D-T13) |
| 9 | **A test writes fiction into the evidence** | A test that logs to the repository's real `runs/ledger.jsonl` looks exactly like a model call that happened | Fixed in this ticket: the planner's abstention test now disables telemetry; `runs/` is git-ignored so no fixture line can be committed |

---

## 5. Coverage boundaries

| Dimension | Supported / evaluated | Out of scope |
|---|---|---|
| **Actuator** | One fixed-base, single-axis pusher or a small cartesian cell | Multi-arm coordination, mobile bases, SLAM, legged locomotion |
| **Motion model** | Straight-line tool-tip translation in x-y at a fixed z, 2 mm sampling | 6-DoF rigid-body dynamics, contact forces, rotation, compliance |
| **Sensing** | Coarse occupancy (switch / frame diff / depth), limit switches, encoder position | Full scene reconstruction; object pose estimation at production accuracy |
| **Force** | An *estimate* derived from stall current (labelled an estimate everywhere) | Calibrated force/torque sensing unless a load cell is fitted |
| **Modes** | `normal`, `degraded` (stricter parameters), `simulation` (permanent badge) | Autonomous mode switching without operator visibility |
| **Evidence** | Deterministic rule trace + two-arm replay in a simplified simulator + a pack that re-derives offline | Certification evidence, formal verification, MTBF statistics |

---

## 6. Honesty rules enforced by tooling

1. **A simulation result can never be presented as a hardware result.** The contract's `mode` field, the
   dashboard's permanent SIMULATION badge and the `source` string in `runs/headline_statistics.json`
   exist for this.
2. **A VETO always ships a no-op** — a veto with a real shipped action fails schema validation.
3. **A clamp is a partial refusal**, not a success: `ALLOW_CLAMPED` must record the before/after.
4. **`collisions_in_shipped` must be 0**; the contract rejects any other value rather than reporting it,
   and `jobs/batch_1000_eval.py` exits non-zero if a single action ships a collision.
5. **Unmeasured numbers are labelled.** `TODO_MEASURE` is not a placeholder to be quietly deleted; it is
   a debt that `scripts/validate_taxonomy.py --strict` fails on.
6. **A refusal without a witness is reported, not counted.** 250 of the 420 vetoes in the session have
   no geometric counterfactual; they are listed by rule and excluded from the 248.
