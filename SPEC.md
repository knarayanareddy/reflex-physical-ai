# SPEC — "Reflex": a physical actuator whose safety layer has veto authority and never touches the network

**Idea D · Track: Physical AI ($10,000 + 4× Jetson Orin Nano)**
**Also eligible: Best Apps and Agents, Best Use of Tavily (weakly)**
**Version:** 1.0 · 26 Oct 2026 · **Build window:** Sun 26 Oct → Thu 30 Oct 2026, 19:00 CEST
**Role in the portfolio:** the **highest-variance** play. Only build it if hardware is physically in hand tonight.

> **READ THIS FIRST — the go/no-go gate.**
> Idea D is only viable if, **tonight (Sun 26 Oct)**, you have at least Tier 2 hardware in hand — see
> `data/hardware-tiers.md`. If you are ordering parts, the parts will not arrive before the deadline, and a
> Physical AI submission without hardware footage is not eligible in any meaningful sense: the track requires
> **≥1 minute of video showing the hardware or modules in use**, and that footage *is* the moat.
> **If you do not have hardware tonight → build Idea A.** Do not spend Sunday negotiating with yourself about this.

> Read `_shared/agent-delegation-protocol.md` before dispatching any ticket.

---

## 1. Executive brief

### The field you are entering is nearly empty
Of **833** public repos referencing this hackathon, **~34 (≈4%)** touch robotics/physical AI — against ~95
fact-checkers, ~91 coding agents and ~83 personal-AI tools. Yet Physical AI carries **25% of the track prizes**
(one of four $10,000 track awards plus **4× Jetson Orin Nano**) and **3 of the 6 judges** are NVIDIA physical-AI,
robotics or Jetson people: Johnny Nunez, Aditya and Selena Williams. In the judges' video Johnny asked, on the
record, for *"local models running to apply on physical AI."*

A thin field with a third of the panel and a quarter of the prizes is the best expected-value position available.
It is also the highest-variance one, because you cannot fake hardware.

### One-sentence pain
> *"I can get a model to plan a robot's next action in two seconds. I cannot get anyone to tell me, after the
> fact, what it wanted to do that I stopped it from doing — or prove that the thing which stopped it can't be
> talked out of it."*

### Persona
**Kai**, 29, a robotics/automation engineer deploying a small pick-and-place or dispensing cell for a client.
She has a model that plans motions. She has an e-stop. She has **no auditable middle layer**, no record of
near-misses, and no way to show a client or an insurer that the safety logic is deterministic and cannot be
overridden by a prompt.

### The 30-second hook
> Split screen, single continuous take, real hardware in frame.
> Left: a live webcam of the rig — a servo-driven pusher, a small object, a marked **keep-out volume**, a red
> e-stop relay module. Right: a terminal streaming the planner's intended action, the envelope's decision, and
> the actuator's actual motion.
> The planner proposes pushing the object toward a target. Mid-stroke, a second object (a hand, or a test block)
> enters the keep-out volume. **The envelope vetoes within one frame**, the actuator stops, the relay clicks, and
> a line lands in `runs/veto-ledger.jsonl`.
> Cut to the **Serverless Job replay**: the same vetoed action, re-executed in simulation with the envelope
> disabled, shows the collision that would have happened — next to the envelope-on run, which doesn't.
> On screen: **"1,240 actions planned · 37 vetoed · 37 simulated · 0 collisions shipped."**

### One takeaway
**A safety layer that consults the network is not a safety layer. This one is local, deterministic, has hard veto
authority over the actuator, and produces an audit trail of every action it refused — each one replayed in
simulation to show what it prevented.**

### The named insider insights (say all three in the video)
> **1. Veto authority must be local and non-negotiable.** If the safety check requires a round-trip to a cloud
> model, it has a network-dependent failure mode and a latency floor. A model can also be *persuaded*. So the
> envelope here is **pure deterministic code on the edge device that never imports an LLM client**, holds a
> hardware-level interlock (a relay in the actuator's power path, not a software flag), and cannot be disabled by
> any prompt, any API response, or any configuration the planner controls. A test asserts the module imports no
> network client at all.
>
> **2. The valuable artifact is not the successful action — it is the veto ledger.** Every physical-AI demo shows
> the robot doing the thing. Almost none shows what the system *refused* to do. A ledger of vetoed actions, each
> with the sensor state, the rule that fired, the intended action, and a **simulation of what would have
> happened**, is a genuinely novel artifact and it is the thing an auditor, a client or an insurer would actually
> ask for.
>
> **3. Edge and cloud do different jobs, and the split is a safety property, not a cost optimisation.** The cloud
> (Nemotron Ultra planning, Cosmos Reason visual reasoning, optionally Isaac GR00T) proposes. The edge decides.
> Making that split *load-bearing for safety* rather than for latency or cost is the architectural claim, and the
> network-outage test proves it: **cut the network and the rig keeps operating safely under degraded, more
> conservative envelope parameters — it does not fail open.**

### Why this wins against this specific field
- **~34 competitors, 3 physical-AI judges, 25% of track prizes.** Best expected value in the portfolio.
- **Hardware footage is an unforgeable moat.** Nobody can produce it without the hardware.
- **Johnny asked for local models on physical AI, on the record.** Delivering a small model running *on the edge
  device* answers a judge's stated want directly — the same move Nota AI made in Seoul by tying its output to
  NVIDIA's own roadmap.
- **The Cloud/Edge split the track text asks about is answered structurally**, not rhetorically: the split is the
  safety architecture.
- **NVIDIA-native surfaces**: Cosmos Reason for visual reasoning, Isaac GR00T as the stretch, Jetson as the
  runtime, Serverless Jobs for the simulation replay lane, Token Factory Sandboxes for reproducible replay runs.
- The **veto ledger + simulation replay** is an eval-and-observability story in a track where almost nobody has
  one. It maps onto the Assay submission that the judges liked (robot-demo-data QA) while being a build, not a
  dashboard.

### Honest risk statement
This is the **highest-variance** option in the portfolio. If the hardware misbehaves on Wednesday you have no
fallback demo. Mitigations are built into the plan: a **software-simulation mode** is a first-class deliverable
(D-T05), not an afterthought, so that even total hardware failure still produces a complete, filmable system —
though you would then be competing without the footage advantage, which is exactly why the go/no-go gate at the
top of this file exists.

---

## 2. Success criteria mapped to the four judging criteria

| Criterion | How Reflex earns it | Measurable target |
|---|---|---|
| **Technological Implementation (25%)** | Small model **on the edge device** (answers Johnny directly); Nemotron Ultra planning in the cloud; Cosmos Reason visual reasoning; **Serverless Job** simulation replay of every veto; Token Factory Sandbox for reproducible replays; a complete ledger spanning edge + cloud | ≥1,000 planned actions; **every** veto replayed in simulation; edge inference p95 latency published; ledger covers ≥95% of calls |
| **Design (25%)** | The split-screen operator view: camera + planner intent + envelope decision + actuator state, in one continuous take; a veto-ledger UI where each row expands to sensor state, rule, and a before/after simulation still; the relay click is audible in the video | A non-roboticist understands the veto within 10 s of watching; every veto row expands to a simulation result |
| **Potential Impact (25%)** | An auditable safety layer is a real deployment blocker for small automation integrators; the veto ledger is the artifact a client/insurer asks for; generalises to any bounded-workspace cell | ≥1 real conversation with an automation/robotics practitioner; the ledger format documented as reusable; simulation-replay methodology published |
| **Quality of the Idea (25%)** | Three named insights; **fail-safe under network outage demonstrated on camera**; the deterministic envelope provably has no LLM in its import graph; abstention (refuse-to-move) as a first-class outcome | The network-cut test filmed; the no-LLM-import test in CI; ≥3 distinct veto reasons exercised |

**Track-specific requirements (Physical AI):**
- [x] **≥1 minute of video showing hardware or modules in use** — the whole submission is built around this
- [x] **No demo URL required** — you still deploy the dashboard, because judges who *can* click, will
- [x] Cloud/Edge split explicitly explained — it is the safety architecture

---

## 3. Architecture

```
                        ┌──────────────── CLOUD (Nebius) ────────────────┐
                        │                                                │
  operator goal ───────►│  P1 PLAN      Nemotron 3 Ultra                 │
  "move the block to B" │     goal → ordered action proposals (structured│
                        │     output), each with preconditions and an    │
                        │     expected end state                         │
                        │                                                │
  camera frames ───────►│  P2 PERCEIVE  Cosmos Reason (visual reasoning) │
  (batched, ~2 fps)     │     scene description, object poses, anomaly   │
                        │     flags. ADVISORY ONLY — see the law below.  │
                        │                                                │
                        │  (stretch) Isaac GR00T policy for the motion    │
                        └───────────────┬────────────────────────────────┘
                                        │  proposed action (JSON, signed with a plan_id)
                                        ▼
┌──────────────────────── EDGE DEVICE (Jetson Orin Nano / Pi 5) ────────────────────────┐
│                                                                                        │
│  E1 LOCAL MODEL      a small NVIDIA open model runs ON THE DEVICE                      │
│                      (Tier-1/2: a small VLM or Parakeet-class ASR for voice goals;       │
│                       Tier-3: a tiny classifier or none — see data/hardware-tiers.md)    │
│                      → answers Johnny's stated want: local models on physical AI         │
│                                                                                        │
│  E2 STATE ESTIMATE   sensor fusion → world state at ≥10 Hz                             │
│                      camera frame diff / depth / limit switches / encoder position       │
│                      → object positions, end-effector position, keep-out occupancy        │
│                                                                                        │
│  E3 SAFETY ENVELOPE  ◄── PURE DETERMINISTIC CODE. NO LLM. NO NETWORK. NO IMPORTS. ──►  │
│      ┌─────────────────────────────────────────────────────────────────────────────┐   │
│      │ veto_taxonomy.json → rules evaluated in PRIORITY order, first veto wins:     │   │
│      │   V1 EMERGENCY_STOP       relay asserted / e-stop pressed  → HARD STOP        │   │
│      │   V2 KEEP_OUT_OCCUPIED    object in the keep-out volume     → HARD STOP       │   │
│      │   V3 VELOCITY_LIMIT       commanded speed > limit for mode  → CLAMP or STOP   │   │
│      │   V4 FORCE_LIMIT          measured/estimated force > limit  → HARD STOP       │   │
│      │   V5 WORKSPACE_BOUND      commanded pose outside envelope   → CLAMP to bound  │   │
│      │   V6 COLLISION_PREDICTED  swept volume intersects an object → HARD STOP       │   │
│      │   V7 SENSOR_STALE         no fresh sensor data > N ms       → FAIL SAFE       │   │
│      │   V8 NETWORK_DEGRADED     cloud unreachable > N ms          → DEGRADE (below) │   │
│      │   V9 PLAN_MALFORMED       action fails schema/preconditions → REJECT          │   │
│      │  V10 HUMAN_PRESENCE       hand/person in the cell           → HARD STOP       │   │
│      │  each decision → VetoDecision{reason, rule_id, sensor_snapshot,                 │   │
│      │                                  intended_action, shipped_action, ts, hash}     │   │
│      │  DETERMINISTIC: same sensor snapshot + same action → same decision, asserted    │   │
│      └─────────────────────────────────────────────────────────────────────────────┘   │
│      │                                                                                 │
│      │  V8 NETWORK_DEGRADED is INSIGHT #3 made testable: the envelope NEVER fails open. │
│      │  Cloud unreachable → switch to a stricter parameter set (lower velocity limit,   │
│      │  smaller allowed workspace, no multi-step plans, local model only) and keep      │
│      │  operating. Degraded mode is a MODE, not an error.                               │
│      ▼                                                                                 │
│  E4 EXECUTE          actuator driver. The hardware interlock relay sits IN THE POWER     │
│                      PATH — a veto opens the relay, so a software bug cannot command      │
│                      motion. This is the physical embodiment of "hard veto authority".   │
│                                                                                        │
│  E5 EDGE TELEMETRY   every decision appended to a local ring buffer, shipped to the      │
│                      cloud ledger when connectivity exists, retained locally when not    │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         ▼
┌─────────────────────────── CLOUD: OBSERVE & PROVE ───────────────────────────┐
│  C1 LEDGER          runs/veto-ledger.jsonl — one line per envelope decision,   │
│                     veto or allow, with sensor snapshot + hashes               │
│  C2 SIMULATION      Nebius SERVERLESS JOB: replay EVERY vetoed action twice —  │
│     REPLAY          envelope_on and envelope_off — in a simulator, and record   │
│                     whether the envelope_off run collides.                      │
│                     THIS IS THE PROOF THAT THE VETO PREVENTED SOMETHING REAL.   │
│  C3 TOKEN FACTORY   each replay runs in a SANDBOX with a pinned image so the    │
│     SANDBOX         result is reproducible; branching gives the two arms from   │
│                     one immutable image.                                        │
│  C4 DASHBOARD       operator view + veto ledger + replay results + cost/latency │
└───────────────────────────────────────────────────────────────────────────────┘
```

### THE LAW (asserted in tests, enforced in code review)
> **The safety envelope module must not import, instantiate, or transitively depend on any LLM client, HTTP
> client or network I/O. A CI test walks the import graph of `edge/envelope/` and fails the build if any network
> or model symbol appears. The hardware interlock must be in the actuator's power path, not a software flag.
> Cosmos Reason and the cloud planner are ADVISORY: the envelope may reject anything they say, and nothing they
> say can widen the envelope.**

That law is the whole idea, and it is testable. Judges can run `make verify-envelope` and see it pass.

### Component justification (cut anything that fails)

| Component | Serves the hook? | Verdict |
|---|---|---|
| Deterministic envelope with hardware interlock | **Yes — it IS the product** | Keep |
| Veto ledger | **Yes — insight #2** | Keep |
| Simulation replay of every veto (Job) | **Yes — it proves the veto mattered** | Keep |
| Network-degraded fail-safe mode | **Yes — insight #3, and it's filmable** | Keep |
| Small model running on the edge device | **Yes — answers a judge's stated want** | Keep |
| Nemotron Ultra planning (cloud) | Yes — the Cloud half of the required split | Keep |
| Cosmos Reason visual reasoning | Yes — NVIDIA-native, and the "advisory only" framing is the insight | Keep |
| Split-screen operator UI | Yes — the Design score | Keep |
| Isaac GR00T policy | Only if the base system is done by Tue | **Stretch** |
| Multi-arm / multi-actuator coordination | No | **CUT** |
| Autonomous navigation / SLAM | No | **CUT** |
| A mobile robot base | No — a fixed cell is more controllable and more filmable | **CUT** |
| Voice control | Only if ASR is free on-device and time allows | **Stretch** |
| Teleoperation UI | No | **CUT** |

### Rig definition (the minimum viable, Tier 3)
A **fixed-base pusher rig**: one servo or stepper driving a pusher along a linear rail, a small object to move,
a webcam or USB microscope watching the workspace, a **marked keep-out volume** (a taped region plus a
second object used as the intruder), limit switches at both ends, and a **relay module in the actuator's power
path** driven by the envelope. Total parts ≈ €40–80 if you already own a microcontroller. That is enough to
demonstrate every one of the ten veto rules and to film the whole story. See `data/hardware-tiers.md`.

---

## 4. Data model

Authoritative prose here; machine-checkable contract in `schemas/core-schemas.json`; the rule vocabulary is frozen
in `data/veto-taxonomy.json`.

### 4.1 `PlanRequest` / `ActionProposal`
`request {id, goal, workspace_id, mode ∈ {normal, degraded, simulation}, operator_id}`
`ActionProposal {proposal_id, plan_id, kind ∈ {move_to, push, grasp, release, home, wait}, target_pose,
velocity_limit, force_limit, preconditions[], expected_end_state, source ∈ {cloud_ultra, cloud_gr00t,
edge_local, hardcoded_sequence}, issued_at, ttl_ms, signature}`
> `ttl_ms` matters: a stale proposal must not be executable. **V9 rejects an expired proposal.** That is a real
> safety property most demos do not have, and it is one line of code.

### 4.2 `SensorSnapshot`
`{snapshot_id, ts_mono_ms, ts_wall, camera {frame_sha256, frame_idx, age_ms}, end_effector {x,y,z, encoder_raw},
limit_switches {min,max}, keep_out_occupied (bool), keep_out_evidence {method ∈ {frame_diff, depth, classifier,
switch}, blob_bbox, confidence}, intruder_present (bool), force_estimate (float|null), relay_state (bool),
network {cloud_reachable, last_cloud_ok_ms_ago}, device {temp_c, cpu_pct}}`

### 4.3 `EnvelopeDecision` — the central object
```
{ "decision_id":"d_…", "proposal_id":"p_…", "snapshot_id":"s_…",
  "outcome": "ALLOW" | "ALLOW_CLAMPED" | "VETO",
  "rule_id": "V2_KEEP_OUT_OCCUPIED",        // null when ALLOW with no rule firing
  "rules_evaluated": ["V1",…,"V10"],         // full evaluation trace — shows the priority order
  "first_veto_index": 1,
  "intended_action": { …ActionProposal… },   // what the planner wanted
  "shipped_action": { …ActionProposal… },    // what actually went to the actuator (may be clamped)
  "clamp_applied": {"velocity": [120.0, 40.0]} | null,
  "sensor_snapshot": { …inline or by id… },
  "mode": "normal" | "degraded" | "simulation",
  "latency_us": 187,                          // envelope evaluation time — must be sub-millisecond-scale
  "envelope_version": "sha256:…",             // hash of veto-taxonomy.json + envelope code version
  "determinism_hash": "sha256:…",             // hash of (snapshot, intended_action, envelope_version)
  "decided_at": "…", "device_id": "…", "firmware_version": "…" }
```

### 4.4 `ReplayResult` (C2)
`{replay_id, decision_id, arm ∈ {envelope_on, envelope_off}, simulator, sim_version, sandbox_image_uuid,
sandbox_operation_id, ran_at, outcome ∈ {completed, collided, out_of_bounds, force_exceeded, timeout},
collision {with, at_t_ms, penetration_mm}|null, trajectory_sha256, metrics {path_length, max_velocity,
max_force, time_to_complete_ms}, cost, ledger_id}`

> **The headline statistic is the pair**: of N vetoed actions, M produced a collision in the `envelope_off` arm
> and 0 in the `envelope_on` arm. If some vetoed actions produce *no* collision in the `envelope_off` arm,
> **report that honestly** — it means the envelope was conservative on those, and the conservative-fraction
> number is itself interesting ("the envelope is conservative on 22% of vetoes; those are the cost of
> determinism").

### 4.5 `SessionRun`
`{run_id, mode, started_at, ended_at, device, hardware_tier, actions_planned, actions_allowed,
actions_clamped, actions_vetoed, vetoes_by_rule{}, degraded_mode_entered (bool), network_outages (int),
collisions_in_shipped (int — MUST be 0), total_cost_usd, edge_latency_ms {p50,p95},
cloud_latency_ms {p50,p95}, video_clip_ids[]}`

### 4.6 `Rule` (`data/veto-taxonomy.json`)
`{rule_id, name, priority, severity ∈ {hard_stop, clamp, degrade, reject}, applies_to_modes[],
parameters {…}, parameter_set_normal {…}, parameter_set_degraded {…}, requires_sensors[],
sensor_staleness_ms, rationale, test_fixture, false_positive_risk, tuning_note}`
> **Two parameter sets per rule is the mechanism for insight #3.** Degraded mode is not a different code path —
> it is the same rules with stricter numbers. That is much easier to defend as "still deterministic" than a
> branch, and it is easy to test.

---

## 5. Model & platform usage matrix

| Model / feature | Where | Job | Why |
|---|---|---|---|
| **A small NVIDIA open model ON THE EDGE DEVICE** | E1 | Local goal parsing / a small VLM scene check / Parakeet-class ASR for a voice goal | **Directly answers Johnny's on-record ask for local models on physical AI.** Which model depends on the tier — see `data/hardware-tiers.md` |
| Nemotron 3 **Ultra** (Token Factory) | P1 | Goal → ordered `ActionProposal`s with preconditions, via structured output | Genuinely hard planning; the track text names Ultra for "genuinely hard problems" |
| Nemotron 3 **Nano** (Token Factory) | P1 fallback, edge-side when degraded | Cheap single-step proposals when Ultra is unavailable | Makes the degraded mode *functional*, not just safe |
| **Cosmos Reason** | P2 | Visual reasoning over batched frames: scene description, object poses, anomaly flags | NVIDIA-native, and the right tool for the job. **Advisory only — the envelope may overrule it, and that is the point** |
| **Isaac GR00T** | stretch | A learned policy for the motion primitive | Only if the base system is finished by Tuesday |
| **Serverless Job** | C2 | Batch replay of every vetoed action, both arms | The track text explicitly encourages Jobs for "batch inference, evaluation, and simulation" |
| **Token Factory Sandboxes + branching** | C3 | One immutable image → `envelope_on` / `envelope_off` branches per replay | Reproducible proof; "run alternatives from one image, select a verified result" is literally this |
| **Serverless Endpoint** | C4 | Host the dashboard API | Public URL; no demo URL required but judges will click |
| **Structured output / JSON** | P1, P2 | Schema-valid action proposals | Malformed proposals are caught by V9 before they reach hardware |
| **Cached Tokens** | P1 | The workspace description and envelope parameter summary repeat every plan | Measure the saving |
| **Tavily** (optional, weak fit) | docs | Fetch current simulator/JetPack version info at build time | Only include if genuinely used; do not bolt it on |
| Ledger (`runs/ledger.jsonl`) | everywhere | Per `_shared/platform-capabilities.md §8` | Edge decisions get `runner="edge_device"` |

---

## 6. The envelope — pseudocode

```python
# edge/envelope/envelope.py
# ⚠ THE LAW: this module MUST NOT import any LLM client, HTTP client, or network I/O.
#   CI test tests/test_envelope_purity.py walks the import graph and fails the build otherwise.
#   Deterministic: same (snapshot, intended_action, envelope_version) → same decision, asserted by hash.

def decide(snapshot: SensorSnapshot, action: ActionProposal, rules: list[Rule], mode: str) -> EnvelopeDecision:
    params = "parameter_set_degraded" if mode == "degraded" else "parameter_set_normal"
    evaluated, first_veto, shipped = [], None, deepcopy(action)

    for rule in sorted(rules, key=lambda r: r.priority):        # priority order; FIRST veto wins
        if mode not in rule.applies_to_modes:
            continue
        if not all(hasattr(snapshot, s) for s in rule.requires_sensors):
            # A rule whose sensors are missing FAILS SAFE. Never skip a safety rule silently.
            evaluated.append((rule.rule_id, "SENSOR_MISSING→VETO")); first_veto = first_veto or rule; continue
        if sensor_age(snapshot, rule) > rule.sensor_staleness_ms:
            evaluated.append((rule.rule_id, "SENSOR_STALE→VETO")); first_veto = first_veto or rule; continue

        p = getattr(rule, params)
        verdict, clamp = rule.evaluate(snapshot, shipped, p)     # pure function of its inputs
        evaluated.append((rule.rule_id, verdict))

        if verdict == "VETO":
            first_veto = first_veto or rule
            if rule.severity == "clamp":                          # V3/V5 clamp instead of stopping
                shipped = clamp_action(shipped, clamp); continue
            break                                                 # hard_stop / reject: stop evaluating
    if first_veto is None:
        outcome = "ALLOW_CLAMPED" if shipped != action else "ALLOW"
    else:
        outcome = "VETO"; shipped = null_action()                 # a real no-op, not the clamped action

    d = EnvelopeDecision(decision_id=uid(), proposal_id=action.proposal_id, snapshot_id=snapshot.snapshot_id,
        outcome=outcome, rule_id=first_veto.rule_id if first_veto else None,
        rules_evaluated=[e[0] for e in evaluated], rule_trace=evaluated,
        first_veto_index=index_of(evaluated, first_veto),
        intended_action=action, shipped_action=shipped,
        clamp_applied=diff(action, shipped), mode=mode,
        latency_us=elapsed_us(), envelope_version=ENVELOPE_VERSION,
        determinism_hash=sha256_canonical(snapshot, action, ENVELOPE_VERSION),
        decided_at=now(), device_id=DEVICE_ID, firmware_version=FW)
    emit_to_ring_buffer(d)                                        # local first; ship to cloud when possible
    if outcome == "VETO" and first_veto.severity == "hard_stop":
        open_interlock_relay()                                    # HARDWARE. Not a software flag.
    return d
```

**Two properties to demonstrate on camera:**
1. `tests/test_envelope_purity.py` — walk the import graph, assert zero network/LLM symbols. Run it live.
2. `tests/test_envelope_determinism.py` — replay 500 recorded snapshots twice, assert identical
   `determinism_hash` on all 500. This is the auditability claim, and it is cheap to prove.

---

## 7. Repository layout

```
edge/          firmware + envelope (Python or C++; Python for speed of build, C++ only if latency demands)
  edge/envelope/{envelope.py,rules.py,interlock.py,ring_buffer.py}   ← THE LAW applies to this package
  edge/sensors/{camera.py,encoder.py,switches.py,fusion.py}
  edge/actuate/{driver.py,relay.py}
  edge/local_model/{loader.py,infer.py}                              ← E1, the on-device model
  edge/main.py  edge/config/{normal.json,degraded.json}
cloud/         planner + perceive + ledger + replay
  cloud/plan/{ultra.py,prompts/plan.md,proposals.py}
  cloud/perceive/{cosmos_reason.py,batching.py}
  cloud/ledger/{ingest.py,query.py}
  cloud/replay/{sim_client.py,dispatch_job.py}
sim/           the simulator used for replay (pick ONE and justify it in docs/SIMULATOR-CHOICE.md)
jobs/          Dockerfile + replay_all.py  (Nebius Serverless Job)
sandbox/       image/{Dockerfile,replay.py} + branching scripts
dashboard/     Vite + React: split-screen operator view, veto ledger, replay results
data/          veto-taxonomy.json, hardware-tiers.md, fixtures/snapshots/*.json, calibration/
runs/          veto-ledger.jsonl, ledger.jsonl, replays/, artifacts/, reports/
tests/         incl. test_envelope_purity.py, test_envelope_determinism.py, test_network_outage.py
docs/          DECISIONS.md, SIMULATOR-CHOICE.md, HARDWARE-BILL.md, EVAL.md, LIMITATIONS.md, SAFETY-CASE.md
```

---

## 8. Phase plan & exit criteria

| Phase | Window | Exit criterion |
|---|---|---|
| **0** | Sun 26 Oct → 23:00 | **GO/NO-GO on hardware decided and recorded**; rig on the bench and moving under manual control; bill of materials photographed; envelope taxonomy v0; the simulator chosen; repo + CI + licence |
| **1** | Sun 23:00 → Mon 09:00 | Schemas frozen; `veto-taxonomy.json` validated; **envelope purity + determinism tests green**; ledger live (edge ring buffer + cloud ingest); simulator replays a recorded trajectory |
| **2** | Mon → 23:00 | **G2: a real cloud-planned action moves the real actuator, and a real intruder in the keep-out volume vetoes it, with the relay clicking and a ledger line written.** Film it. This is the single most important moment in the project |
| **3** | Tue 28 Oct | Edge local model running on-device; Cosmos Reason advisory pass; ≥1,000 planned actions logged; **every veto replayed in both arms via a Serverless Job**; the network-outage degraded mode demonstrated and filmed; ≥1 practitioner conversation |
| **4** | Wed 29 Oct 08:00–16:00 | **FEATURE FREEZE.** Dashboard: split-screen view + veto ledger + replay results; deployed; latency/cost numbers real; SAFETY-CASE.md and LIMITATIONS.md written |
| **5** | Wed 16:00 → Thu 30 Oct 18:00 | Video ≤2:50 with **≥1:00 of hardware footage**; README; Devpost copy + feedback; **SUBMITTED** |

---

## 9. Task tickets

### Phase 0 — Commit & de-risk (Sun 26 Oct)

```
ID: D-T01  TITLE: GO/NO-GO hardware decision (HUMAN — do this FIRST, before anything else)
PHASE: 0  OWNER: human  DEPENDS_ON: —  BLOCKS: ALL
DELIVERABLE: docs/DECISIONS.md entry "D-T01 go/no-go" ; photos in docs/img/hardware/
SPEC: Inventory what is physically in hand TONIGHT against data/hardware-tiers.md. Decide the tier. If the best
      available tier is Tier 4 (no hardware), STOP and switch to Idea A — record that decision and move on
      without regret. If Tier 1–3, record the exact tier, the parts list with prices, and photograph everything
      on the bench.
      Then: make the actuator move under manual control (a script, a button, anything). Do not proceed to any
      other ticket until the hardware moves. Hardware that has never moved on day one does not move on day four.
ACCEPTANCE: a DECISIONS.md entry naming the tier with a photo; a committed script that moves the actuator;
            a parts list with prices in docs/HARDWARE-BILL.md.
KILL CRITERION: no actuator movement by Sun 22:00 → switch to Idea A. Do not negotiate with this.
```

```
ID: D-T02  TITLE: Bootstrap repo, licence, CI, Makefile, two-target build
PHASE: 0  OWNER: devops-agent DEPENDS_ON: D-T01  BLOCKS: all
SPEC: As A-T01, plus a **two-target build**: `make edge` (runs on the device, minimal deps) and `make cloud`
      (runs anywhere). CI must run the envelope tests on every push. `make verify-envelope` runs the purity and
      determinism tests and prints a one-line PASS — this is the command you show in the video.
ACCEPTANCE: `make check` green from a clean clone on a laptop with no hardware attached (simulation mode);
            `make verify-envelope` prints PASS.
```

```
ID: D-T03  TITLE: Freeze the veto taxonomy (v0)
PHASE: 0  OWNER: safety-agent + human DEPENDS_ON: D-T01  BLOCKS: D-T07, D-T09
DELIVERABLE: data/veto-taxonomy.json (populate it) ; docs/SAFETY-CASE.md (start it)
SPEC: All ten rules V1–V10 from SPEC §3 with, per rule: priority, severity, applies_to_modes, requires_sensors,
      sensor_staleness_ms, BOTH parameter sets (normal and degraded), rationale, a named test fixture, a
      false-positive-risk note and a tuning note. Write the rationale as if for an auditor: why this rule, why
      these numbers, what happens if it is wrong in each direction.
      ⚠️ Parameter values must be derived from YOUR rig's measured limits (D-T06), not copied from a paper.
      Record the derivation. A velocity limit that has no measured basis is theatre.
ACCEPTANCE: 10 rules; each has both parameter sets, a rationale ≥2 sentences, a named fixture and a
            false-positive note; the priority order is total and unambiguous.
VERIFY: python scripts/validate_taxonomy.py --strict
```

```
ID: D-T04  TITLE: Choose and justify the simulator (ONE, not three)
PHASE: 0  OWNER: sim-agent + human DEPENDS_ON: D-T01  BLOCKS: D-T12
DELIVERABLE: docs/SIMULATOR-CHOICE.md ; sim/client.py (stub)
SPEC: The replay lane needs a simulator that can: load your rig's geometry, place an intruder, execute an
      ActionProposal, and report whether a collision occurred. Choose ONE and justify it in ≤1 page: setup time,
      determinism/reproducibility, headless operation (it must run in a Serverless Job and in a Sandbox), licence,
      and whether it can import your rig description without a lot of glue.
      A simple, honest option: **write your own 2D/2.5D swept-volume collision simulator** in ~200 lines of
      numpy for the pusher rig. For a single-axis pusher this is entirely adequate, fully deterministic, has zero
      dependencies, runs in a Sandbox in milliseconds, and you can explain every line of it. A heavyweight
      physics engine you cannot get running headless by Tuesday is worth nothing.
      **Default recommendation: build the small in-house simulator, and note in docs/SIMULATOR-CHOICE.md which
      industrial simulator you would use for a real cell and why you didn't have time.** That honesty reads as
      engineering judgement, not as a gap.
ACCEPTANCE: docs/SIMULATOR-CHOICE.md ≤1 page with the decision, the alternatives considered, and the trade-offs;
            a headless run reproduces a collision from a recorded snapshot.
VERIFY: cd sim && python -m sim.replay --fixture data/fixtures/snapshots/veto_v2.json --assert-collision
```

```
ID: D-T05  TITLE: Simulation mode as a first-class target (NOT a fallback)
PHASE: 0  OWNER: sim-agent DEPENDS_ON: D-T02, D-T04  BLOCKS: D-T09, D-T13
SPEC: A `--mode simulation` flag that swaps the sensor and actuator drivers for simulated ones with identical
      interfaces, so the ENTIRE pipeline — planner, envelope, ledger, replay, dashboard — runs with no hardware.
      This is what CI runs, what `make demo` runs, and what a judge runs. It also means hardware failure on
      Wednesday does not destroy the submission (though it does destroy the footage advantage).
ACCEPTANCE: `make demo` runs the full pipeline in simulation on a laptop with no device attached and produces a
            ledger, a veto and a replay; CI runs it on every push.
VERIFY: make demo && jq -s 'map(select(.outcome=="VETO")) | length' runs/veto-ledger.jsonl
```

```
ID: D-T06  TITLE: Rig bring-up + measure the real limits
PHASE: 0  OWNER: hardware-agent + human DEPENDS_ON: D-T01  BLOCKS: D-T03, D-T10
DELIVERABLE: scripts/measure_limits.py ; data/calibration/rig-limits.json ; docs/HARDWARE-BILL.md ; photos
SPEC: Measure, and record with the method used: max safe velocity (mm/s) at several command levels; end-effector
      repeatability (mm) over 20 cycles; travel limits from the switches; the relay's switching time (measure it
      with a scope if you have one, otherwise with a high-fps camera and say which); sensor frame rate and its
      jitter; the keep-out volume's physical dimensions; the force at which the pusher stalls.
      **These numbers become the envelope's parameters.** Every parameter in veto-taxonomy.json must trace to a
      measurement in rig-limits.json — a CI test checks the linkage.
ACCEPTANCE: all seven measurements recorded with method and raw data; rig-limits.json validated; every envelope
            parameter traces to a measurement (scripted check).
VERIFY: python scripts/check_param_provenance.py
```

```
ID: D-T07  TITLE: Credits + catalog snapshot + edge-device capability check
PHASE: 0  OWNER: backend-agent DEPENDS_ON: D-T02  BLOCKS: D-T11, D-T14
SPEC: As A-T02, PLUS: determine exactly which NVIDIA open model can run on your edge device within its memory
      and thermal budget. Record device, model, quantisation, tokens/s or frames/s, and peak memory. **This is
      the evidence for the "local models on physical AI" claim and it must be a real measured number, not a
      hope.** Also confirm Cosmos Reason availability and its input format (frame batching, image limits).
ACCEPTANCE: catalog snapshot committed; an edge model chosen and benchmarked with a real number recorded;
            Cosmos Reason confirmed callable with a sample frame batch.
VERIFY: jq -r '.[] | select(.id|test("cosmos|gr00t|nemotron";"i")) | .id' data/model-catalog.snapshot.json
```

```
ID: D-T08  TITLE: Design system — "control room"
PHASE: 0  OWNER: frontend-agent DEPENDS_ON: D-T02  BLOCKS: D-T21
CONTEXT: _shared/judging-rubric.md §3
DELIVERABLE: dashboard/src/tokens.css ; dashboard/src/components/primitives.tsx ; docs/DESIGN.md
SPEC: Metaphor = an industrial control room / a machine operator's HMI. Dark slate #101418 base, panel #171C22,
      hairline #2A323B, text #E6E9EC, muted #8B959E. Semantic: ALLOW #3DD68C, CLAMP #F2C14E, **VETO #FF4D3D**,
      DEGRADED #7AA2F7, IDLE #6B7280. Type: a monospace face for ALL telemetry, timestamps, decision ids, rule
      ids, hashes, velocities and forces — telemetry must look like telemetry; a neutral sans for prose.
      A thin 2px accent bar per panel state. Sharp corners (2px radius). No gradients. No glow.
      Primitives: SplitScreenStage (camera left, telemetry right, in one continuous frame — the video's hero
      shot), TelemetryStrip (10 Hz, mono, rolling), DecisionRow (outcome chip + rule id + latency + expand),
      VetoLedgerTable (sortable, filterable by rule, expandable to the sensor snapshot AND the replay result),
      ReplayCompare (two simulation stills side by side: envelope_off collided / envelope_on clean),
      InterlockIndicator (relay state, with the physical click timestamped), ModeBadge (NORMAL/DEGRADED/
      SIMULATION — visually unmistakable, because confusing simulation with real hardware is the one thing this
      project must never do), LatencyHistogram, CostPanel, StopButton (always visible, always enabled).
      FORBIDDEN: purple→pink gradients; glassmorphism; emoji iconography; a glowing "AI brain" visual; anything
      that makes a safety system look decorative; rendering simulation output without a SIMULATION badge.
ACCEPTANCE: docs/DESIGN.md explains the metaphor; DecisionRow's four outcome states are distinguishable in
            greyscale and under deuteranopia simulation; ModeBadge is impossible to miss; a screenshot committed.
VERIFY: cd dashboard && npm run build && npx tsc --noEmit
```

### Phase 1 — Contracts

```
ID: D-T09  TITLE: Freeze core schemas
PHASE: 1  OWNER: backend-agent DEPENDS_ON: D-T03, D-T05  BLOCKS: all
DELIVERABLE: schemas/core-schemas.json ; cloud/models.py ; edge/models.py ; tests/test_schemas.py
SPEC: Transcribe SPEC §4 into JSON Schema + Pydantic v2. ONE definition shared by edge and cloud (the edge gets
      a generated subset — do not hand-maintain two). Integrity assertions that MUST fail validation:
      an EnvelopeDecision with outcome=VETO and a non-null shipped_action;
      an EnvelopeDecision with outcome=ALLOW and rule_id set to a hard_stop rule;
      an ActionProposal with a missing or expired ttl_ms;
      a SensorSnapshot with keep_out_occupied=true and no keep_out_evidence;
      a ReplayResult with arm=envelope_off and no collision field (must be explicit, either null or an object);
      a Rule with only one parameter set.
ACCEPTANCE: all fixtures validate; all six integrity assertions have a failing-input test.
VERIFY: cd cloud && uv run pytest tests/test_schemas.py -q
```

```
ID: D-T10  TITLE: THE ENVELOPE — purity, determinism, priority order  ← the heart of the project
PHASE: 1  OWNER: safety-agent DEPENDS_ON: D-T03, D-T06, D-T09  BLOCKS: D-T13, G2
DELIVERABLE: edge/envelope/{envelope.py,rules.py,interlock.py,ring_buffer.py} ;
             tests/{test_envelope_purity.py,test_envelope_determinism.py,test_envelope_priority.py,
                    test_rules_v1_v10.py}
SPEC: Implement SPEC §6 exactly. Then the three tests that make this project credible:
      (1) **PURITY** — walk the transitive import graph of `edge/envelope/`. Assert that no module in it imports
          or references any LLM client, HTTP client, socket, or network symbol. Fail the build with the exact
          offending import path printed. Also grep the source for forbidden tokens (http, requests, socket,
          openai, nemotron, urllib, aiohttp, websocket) and fail on any hit outside a comment whitelist.
      (2) **DETERMINISM** — replay 500 recorded SensorSnapshots twice in separate processes and assert byte-
          identical determinism_hash on all 500. Also assert zero wall-clock dependence (no `time.time()` in a
          decision path — monotonic timestamps are recorded but never used as inputs).
      (3) **PRIORITY** — construct snapshots where two rules would fire simultaneously and assert the
          lower-numbered rule wins, for every pair in the taxonomy.
      Then one unit test per rule V1–V10 using the fixture named in the taxonomy, covering both fires-correctly
      and does-not-fire-on-clean-input. **A rule that fires on clean input is a false positive and will make the
      demo look broken — test the negative case as hard as the positive.**
ACCEPTANCE: all three property tests green; 10/10 rules pass positive AND negative fixtures; envelope p95
            decision latency <1 ms on the edge device (record the real number); `make verify-envelope` prints PASS.
VERIFY: make verify-envelope && cd edge && python -m pytest tests/ -q
```

```
ID: D-T11  TITLE: Cloud planner — Nemotron Ultra → ActionProposal
PHASE: 1  OWNER: backend-agent DEPENDS_ON: D-T07, D-T09  BLOCKS: D-T13
DELIVERABLE: cloud/plan/{ultra.py,proposals.py,prompts/plan.md} ; tests/test_plan.py
SPEC: Goal → ordered ActionProposal[] via structured output. Each proposal carries preconditions, an expected
      end state, a velocity/force limit REQUEST (the envelope may lower it, never raise it), a plan_id, an
      issued_at and a ttl_ms. Schema-validate every proposal; a malformed one is a V9 rejection and is logged.
      The prompt MUST tell the model that its proposals are advisory and that a safety envelope will evaluate
      them — and MUST NOT tell it the envelope's parameters (a planner that knows the limits will plan to them,
      which defeats the demonstration). Record that choice in DECISIONS.md; it is a genuinely interesting
      design decision and a good talking point.
ACCEPTANCE: 10 goals produce valid proposal sequences; a deliberately malformed model output produces a V9
            rejection with a ledger line; no proposal can raise a limit above the envelope's ceiling (test it).
VERIFY: cd cloud && uv run pytest tests/test_plan.py -q
```

```
ID: D-T12  TITLE: Simulation replay engine
PHASE: 1  OWNER: sim-agent DEPENDS_ON: D-T04, D-T09  BLOCKS: D-T19
DELIVERABLE: sim/{replay.py,rig.py,collision.py} ; tests/test_replay.py
SPEC: Load the rig geometry from data/calibration/rig-limits.json, place the intruder from a SensorSnapshot,
      execute an ActionProposal step by step, and report outcome ∈ {completed, collided, out_of_bounds,
      force_exceeded, timeout} with collision details. Deterministic and seedable. Must run headless with zero
      GUI, inside a Serverless Job and inside a Sandbox. Emit a trajectory sha256 and a renderable still per run
      (a simple 2D plot is fine and reads clearly on video).
ACCEPTANCE: replays the 10 rule fixtures; the V2 keep-out fixture collides with the envelope off and completes
            with it on; identical inputs produce identical trajectory_sha256 across processes; runs headless.
VERIFY: cd sim && python -m pytest tests/ -q && python -m sim.replay --fixture data/fixtures/snapshots/veto_v2.json --both-arms
```

```
ID: D-T13  TITLE: Ledger — edge ring buffer + cloud ingest
PHASE: 1  OWNER: backend-agent DEPENDS_ON: D-T09, D-T10  BLOCKS: D-T19, D-T22
DELIVERABLE: edge/envelope/ring_buffer.py ; cloud/ledger/{ingest.py,query.py} ; tests/test_ledger.py
SPEC: The edge writes every EnvelopeDecision to a **local append-only ring buffer first** (so a network outage
      loses nothing) and ships to the cloud ledger when connectivity exists. On reconnect, back-fill in order with
      dedup by decision_id. Cloud ledger = `runs/veto-ledger.jsonl` plus the standard `runs/ledger.jsonl` for
      model calls. Provide `GET /api/vetoes?rule=&mode=&since=` and `GET /api/sessions/{id}`.
      **The buffer-then-ship design is itself part of insight #3 and worth saying out loud:** the safety record
      must not depend on the network that the safety layer must not depend on.
ACCEPTANCE: killing the network for 30 s mid-run loses ZERO decisions (test it: buffer locally, reconnect, assert
            the count matches); dedup works on a forced double-ship; the API returns filtered vetoes.
VERIFY: cd cloud && uv run pytest tests/test_ledger.py -q && jq -s length runs/veto-ledger.jsonl
```

### Phase 2 — Spine (Mon 27 Oct) → GATE G2

```
ID: D-T14  TITLE: Cosmos Reason advisory perception (P2)
PHASE: 2  OWNER: backend-agent DEPENDS_ON: D-T07, D-T09  BLOCKS: D-T16
DELIVERABLE: cloud/perceive/{cosmos_reason.py,batching.py} ; tests/test_perceive.py
SPEC: Batch camera frames (~2 fps, not per-frame — cost and latency both matter and batching is the honest
      engineering choice) → scene description, object poses, anomaly flags. Output is ADVISORY: it may add
      evidence to a SensorSnapshot's keep_out_evidence with method="classifier", but **it may never clear a veto
      and never widen the envelope.** Enforce that in code: the envelope reads only the deterministic sensor
      fields, and a test asserts that a Cosmos Reason response claiming "workspace clear" cannot change a V2
      decision when the frame-diff sensor says occupied.
      **That test is the single most persuasive thing in this project.** It demonstrates, mechanically, that a
      large model cannot talk a safety layer out of stopping. Put it in the video.
ACCEPTANCE: perception returns structured scene state; the "model cannot clear a veto" test passes; batching
            reduces calls ≥5× vs per-frame with the cost delta recorded.
VERIFY: cd cloud && uv run pytest tests/test_perceive.py -q --assert-model-cannot-clear-veto
```

```
ID: D-T15  TITLE: Edge sensor fusion (E2)
PHASE: 2  OWNER: edge-agent DEPENDS_ON: D-T06, D-T09  BLOCKS: D-T16
DELIVERABLE: edge/sensors/{camera.py,encoder.py,switches.py,fusion.py} ; tests/test_sensors.py
SPEC: Produce a SensorSnapshot at ≥10 Hz. Keep-out occupancy from the cheapest reliable method available at your
      tier: frame differencing inside the marked keep-out region (works with one webcam and is beautifully
      explainable), or depth thresholding, or a physical switch/beam. Record the method in keep_out_evidence.
      Timestamp everything monotonically. **Publish the sensor staleness distribution** — it is the input to
      V7's staleness parameter and shows you derived the number rather than guessed it.
ACCEPTANCE: ≥10 Hz sustained over 5 minutes; keep-out detection works with the real intruder object at the real
            lighting; false-positive rate over a 5-minute empty-workspace run recorded (target <1%); staleness
            p99 recorded and V7's parameter set above it with margin.
VERIFY: cd edge && python -m edge.sensors.bench --seconds 300 --report
```

```
ID: D-T16  TITLE: Actuator driver + hardware interlock relay (E4)  ← the physical proof
PHASE: 2  OWNER: edge-agent + human DEPENDS_ON: D-T06, D-T10  BLOCKS: G2
DELIVERABLE: edge/actuate/{driver.py,relay.py} ; scripts/test_interlock.py ; a filmed close-up
SPEC: Drive the actuator. Put the relay **in the actuator's power path** so that a veto physically removes the
      ability to move — not a software flag that a bug could bypass. Measure and record the relay's switching
      time and the total stop distance from veto to motion ceasing (VETO-TO-STOP LATENCY AND DISTANCE — these two
      numbers are the core safety metrics and almost nobody publishes them).
      Film a close-up of the relay clicking. **The audible click is worth more than any slide.** It is physical
      proof that the veto has hardware authority, and it will be the most memorable two seconds of your video.
ACCEPTANCE: the actuator moves; a veto stops it via the relay; veto-to-stop latency and distance measured and
            recorded; the relay click is filmed in close-up; a test proves motion is impossible with the relay
            open even when the driver is commanded directly (bypass the software and try).
VERIFY: python scripts/test_interlock.py --force-command-while-relay-open --assert-no-motion
```

```
ID: D-T17  TITLE: End-to-end on hardware — G2
PHASE: 2  OWNER: human + edge-agent DEPENDS_ON: D-T11, D-T14, D-T15, D-T16  BLOCKS: G2, D-T19
SPEC: **The single most important moment in this project.** Wire it all: a goal goes to Ultra, proposals come
      back, the edge executes, an intruder enters the keep-out volume, the envelope vetoes, the relay clicks, the
      actuator stops, and a line lands in the ledger. Then do it again five times in a row to prove it is not luck.
      **FILM IT the first time it works, with both screens and the hardware in one continuous shot.** That clip
      is the video's spine and you do not want to be re-staging it on Wednesday.
ACCEPTANCE: 5 consecutive successful veto demonstrations on real hardware; filmed in one continuous take with the
            hardware, the telemetry and the ledger visible; 5 ledger lines with matching decision ids on screen
            and in the file.
VERIFY: jq -s 'map(select(.outcome=="VETO")) | length' runs/veto-ledger.jsonl   # ≥5 new
KILL CRITERION: not working by Mon 22:00 → the submission becomes simulation-only. Decide then whether to
                continue with D or switch to A. Do not drift into Wednesday hoping.
```

```
ID: D-T18  TITLE: Edge local model (E1) — the "local models on physical AI" deliverable
PHASE: 2  OWNER: edge-agent DEPENDS_ON: D-T07, D-T15  BLOCKS: D-T22
DELIVERABLE: edge/local_model/{loader.py,infer.py} ; docs/EDGE-MODEL.md ; a benchmark table
SPEC: Run a small NVIDIA open model **on the edge device** and give it a real job in the pipeline — not a
      decorative one. Options by tier (see data/hardware-tiers.md): parse a spoken or typed goal locally;
      classify keep-out occupancy as a second, independent witness alongside frame differencing (agreement
      between two independent detectors is a nice safety argument); or describe the scene for the operator UI at
      low rate. Benchmark it honestly: tokens/s or frames/s, peak memory, power draw if measurable, and the
      thermal behaviour over a 10-minute run.
      **If the local model's output is used as a safety witness, it must be treated as advisory and can only make
      the envelope MORE conservative, never less.** Same law as Cosmos Reason.
ACCEPTANCE: the model runs on-device with a published real benchmark; it has a defined job whose removal would
            degrade the system; docs/EDGE-MODEL.md records device, model, quantisation, memory, thermal behaviour
            over 10 minutes, and the measured throughput.
VERIFY: cd edge && python -m edge.local_model.bench --minutes 10 --report docs/EDGE-MODEL.md
```

### Phase 3 — Proof (Tue 28 Oct)

```
ID: D-T19  TITLE: THE NETWORK-OUTAGE TEST — degraded mode, fail-safe not fail-open  ← insight #3
PHASE: 3  OWNER: edge-agent + human DEPENDS_ON: D-T10, D-T13, D-T17  BLOCKS: D-T22
DELIVERABLE: scripts/network_outage_test.py ; tests/test_network_outage.py ; a filmed take
SPEC: Physically disconnect the network (pull the cable / disable wifi — do it visibly, on camera). Assert:
      (1) the rig CONTINUES to operate safely using the local model and the stricter degraded parameter set;
      (2) the envelope's decisions in degraded mode are strictly more conservative — a scripted diff of the two
          parameter sets proves every degraded value is ≤ its normal counterpart for limits and ≥ for margins;
      (3) V8 fires and ModeBadge switches to DEGRADED;
      (4) ZERO decisions are lost — they buffer locally and back-fill on reconnect (D-T13);
      (5) nothing fails open: no action is allowed that normal mode would have vetoed.
      **This is the test that separates a safety architecture from a safety vibe.** Film the cable being pulled.
ACCEPTANCE: all five assertions pass on real hardware; filmed with the cable pull visible; the parameter-set diff
            committed showing degraded ⊆ stricter; zero lost decisions across a 60 s outage.
VERIFY: python scripts/network_outage_test.py --duration 60 --assert-no-fail-open --report
```

```
ID: D-T20  TITLE: Veto replay at scale as a Nebius Serverless Job  ← the headline evidence
PHASE: 3  OWNER: devops-agent DEPENDS_ON: D-T12, D-T13  BLOCKS: D-T21, D-T22
DELIVERABLE: jobs/{Dockerfile,replay_all.py} ; runs/reports/replay-summary.json ; docs/EVAL.md
SPEC: Submit a **Serverless Job** that takes every vetoed decision in the ledger and replays it in BOTH arms
      (`envelope_on`, `envelope_off`) in the simulator. Report per rule: n vetoes, n collisions in the off arm,
      n collisions in the on arm (**must be 0**), mean penetration depth prevented, and the conservative fraction
      (vetoes where the off arm also completed cleanly — report this honestly as the cost of determinism).
      Run ≥1,000 planned actions first so the veto count is meaningful (target ≥30 vetoes, ≥3 distinct rules).
      Report n_completed and n_failed separately. Never pad.
ACCEPTANCE: the Job completes; every veto in the ledger has two ReplayResults; 0 collisions in the on arm;
            per-rule table published with the conservative fraction stated; total cost logged.
VERIFY: jq '.summary' runs/reports/replay-summary.json
FALLBACK: run replay_all.py locally as a long process; record runner="local_process" honestly.
```

```
ID: D-T21  TITLE: Token Factory Sandbox branching for reproducible replays
PHASE: 3  OWNER: sandbox-agent DEPENDS_ON: D-T12, D-T20  BLOCKS: D-T22
DELIVERABLE: sandbox/image/{Dockerfile,replay.py} ; scripts/sandbox_branch_replay.py ; tests/test_sandbox.py
SPEC: One immutable image containing the simulator, the rig description, the taxonomy version and the recorded
      snapshots. Branch it twice per decision — `envelope_on` and `envelope_off` — so both arms come from
      byte-identical images. This is exactly the platform feature's stated purpose ("run alternatives from one
      image, select a verified result") and using it for a *safety proof* rather than a code-fix comparison is a
      fresh application worth calling out in the README. Pin and publish the image UUID.
      Retain the sandbox for each headline replay, record the operation id, and expose it in the dashboard so a
      judge can see the replay is reproducible rather than asserted.
ACCEPTANCE: both arms run from one pinned image UUID; a re-run of the same decision in a fresh sandbox produces
            an identical trajectory_sha256; image UUID and operation ids recorded and shown in the UI.
VERIFY: python scripts/sandbox_branch_replay.py --decision <id> --assert-identical-on-rerun
```

```
ID: D-T22  TITLE: The 1,000-action session + the headline statistics
PHASE: 3  OWNER: eval-agent DEPENDS_ON: D-T17, D-T19, D-T20  BLOCKS: D-T26, D-T28
DELIVERABLE: scripts/run_session.py ; runs/reports/session-summary.json ; docs/EVAL.md
SPEC: Run a scripted but varied session producing ≥1,000 planned actions across ≥3 scenarios (normal operation,
      repeated intrusions, a network outage period), exercising ≥5 distinct veto rules. Compute and publish:
      actions planned / allowed / clamped / vetoed; vetoes by rule; **veto-to-stop latency p50/p95 (ms) and
      distance (mm)**; envelope decision latency p50/p95 (µs); collisions in shipped actions (**must be 0**);
      replay collisions envelope_off vs envelope_on; the conservative fraction; degraded-mode duration and
      behaviour; edge and cloud latency separately; total cost and cost per 1,000 actions; false-positive rate.
      **These are the numbers that make this a piece of engineering rather than a demo.** Publish the table in
      the README with a one-line interpretation of each.
ACCEPTANCE: ≥1,000 actions; ≥5 distinct rules exercised; 0 collisions shipped; every metric above published with
            a real value; the session is reproducible from the committed scenario script.
VERIFY: jq '.summary' runs/reports/session-summary.json
```

```
ID: D-T23  TITLE: Talk to 1 real practitioner (HUMAN TASK)
PHASE: 3  OWNER: human DEPENDS_ON: D-T17  BLOCKS: D-T26, D-T28
SPEC: Find one person who deploys or maintains industrial automation — a robotics integrator, a controls
      engineer, a university robotics lab, a maker who runs a CNC or a 3D printer farm, or a machine-safety
      consultant. Show them the rig and the veto ledger. Ask:
        1. What do you actually have today between "the model/PLC says go" and "the machine moves"?
        2. When something nearly went wrong, what record did you have afterwards? Could you show it to a client
           or an insurer?
        3. Would a per-decision audit log with a simulation of the prevented outcome be useful? To whom?
        4. What is the standard you'd be measured against (ISO 10218, ISO/TS 15066, the Machinery Directive,
           a CE marking process)? Where would this fit or fail?
        5. What would make you not trust this?
      Record a 20-second clip or a quotable sentence + first name and role, with permission. Write
      reports/D-T23.INTERVIEWS.md. **Ask the standards question specifically** — the answer will sharpen
      LIMITATIONS.md enormously and gives you an insider detail nobody else will have.
ACCEPTANCE: ≥1 conversation documented; ≥1 usable quote or clip with permission; ≥1 change to the taxonomy,
            SAFETY-CASE.md or LIMITATIONS.md logged in DECISIONS.md; the relevant standards named in LIMITATIONS.
```

```
ID: D-T24  TITLE: False-positive and tuning study
PHASE: 3  OWNER: eval-agent DEPENDS_ON: D-T15, D-T22  BLOCKS: D-T26
SPEC: Run the rig for ≥10 minutes with an EMPTY workspace and ≥10 minutes with normal operation and no intruder.
      Count spurious vetoes per rule. A safety system that vetoes constantly is unusable, and reporting the
      false-positive rate honestly is what makes the true-positive claims believable. Then tune the two
      parameters with the worst false-positive rates, record before/after in DECISIONS.md, and re-measure.
ACCEPTANCE: false-positive rate per rule published for both runs; ≥2 parameters tuned with before/after recorded;
            the overall false-positive rate after tuning stated (target <2% of actions).
VERIFY: python scripts/false_positive_study.py --report docs/EVAL.md
```

```
ID: D-T25  TITLE: Ledger aggregates + cost/latency report
PHASE: 3  OWNER: backend-agent DEPENDS_ON: D-T13, D-T22  BLOCKS: D-T28
SPEC: As A-T33: totals, per-model and per-stage cost, p50/p95 latency **split edge vs cloud** (the split is the
      architecture, so the latency table must show it), failure counts, Cosmos Reason batching savings, cached
      token savings, the all-Ultra counterfactual, and the cost per 1,000 actions. Publish with interpretation.
ACCEPTANCE: docs/MODEL-USAGE.md has real numbers incl. the edge/cloud latency split and the counterfactual;
            GET /api/ledger/summary returns the same JSON.
VERIFY: python scripts/ledger_report.py --markdown > docs/MODEL-USAGE.md
```

```
ID: D-T26  TITLE: SAFETY-CASE.md — the auditor's document  ← differentiator
PHASE: 3  OWNER: safety-agent + human DEPENDS_ON: D-T10, D-T19, D-T22, D-T23  BLOCKS: D-T28
DELIVERABLE: docs/SAFETY-CASE.md
SPEC: Write the document a real deployment would need, honestly scoped to what you actually did: the hazard list
      for THIS rig; the envelope rules mapped to hazards; the parameter provenance (every number → a measurement
      in rig-limits.json); the purity argument (no LLM/network in the import graph, with the test name); the
      determinism argument (500-replay hash identity); the fail-safe argument (network outage test, degraded
      parameters strictly stricter, buffer-then-ship); the hardware interlock argument (relay in the power path,
      bypass test); the verification evidence (replay arms, false-positive study, session statistics); the
      residual risks and what is NOT covered; and the explicit statement that **this is a research prototype and
      not a certified safety system, and does not constitute compliance with any standard.**
      Name the standards a real system would have to meet (asked in D-T23) and say plainly that you have not
      pursued certification. **That sentence is what makes the rest of the document credible.**
ACCEPTANCE: every envelope parameter traces to a measurement; every claim traces to a test or a report file;
            the residual-risk section names ≥5 things this does NOT protect against; the non-certification
            statement appears in the first paragraph and in LIMITATIONS.md and in the video.
```

```
ID: D-T27  TITLE: STRETCH — Isaac GR00T policy (only if D-T22 is DONE)
PHASE: 3  OWNER: sim-agent DEPENDS_ON: D-T22  BLOCKS: —
SPEC: Only attempt if the base system is complete and stable by Tue 12:00. Replace the cloud planner's motion
      primitive with a GR00T-derived policy for the push action, keeping the envelope EXACTLY as it is. The
      interesting result is whether the veto rate changes when a learned policy proposes instead of an LLM —
      if it does, that is a finding worth a paragraph. If it does not work in 3 hours, drop it and say so in
      Next Steps. Do not let this endanger the base submission.
ACCEPTANCE: either a working policy with a recorded veto-rate comparison, or a DECISIONS.md entry recording the
            attempt, what blocked it, and the time spent.
TIMEBOX: 3 hours, hard.
```

### Phase 4 — Polish (Wed 29 Oct) — FEATURE FREEZE

```
ID: D-T28  TITLE: Dashboard — split-screen stage, veto ledger, replay compare
PHASE: 4  OWNER: frontend-agent DEPENDS_ON: D-T08, D-T20, D-T22, D-T26  BLOCKS: G4
SPEC: Three views.
      (1) **OPERATOR** — SplitScreenStage: live camera left, rolling telemetry right (mono, 10 Hz), ModeBadge
          top-left, InterlockIndicator with the last relay-click timestamp, StopButton always visible and always
          enabled, and the current proposal's intended vs shipped action side by side so a clamp is visible.
      (2) **VETO LEDGER** — every decision, sortable and filterable by rule/mode/outcome, each row expanding to
          the sensor snapshot, the full rule evaluation trace (which rules were considered and in what order —
          this trace is a genuinely novel UI element and shows the priority logic working), the intended vs
          shipped action, and the ReplayCompare stills (envelope_off collided / envelope_on clean) with the
          Sandbox operation id.
      (3) **EVIDENCE** — the session statistics table, the per-rule replay table with the conservative fraction,
          the latency histograms (edge and cloud separately), the cost panel with the counterfactual, and links
          to SAFETY-CASE.md and LIMITATIONS.md.
      A **SIMULATION badge must be permanently visible whenever mode=simulation.** Never let a viewer confuse a
      simulated run with hardware.
ACCEPTANCE: a non-roboticist understands what a veto is within 10 s of watching (test on 2 people); every ledger
            row expands to a replay result; the SIMULATION badge is impossible to miss; works at 1280 and 1920.
```

```
ID: D-T29  TITLE: Empty / loading / error / degraded / disconnected states
PHASE: 4  OWNER: frontend-agent DEPENDS_ON: D-T28  BLOCKS: G4
SPEC: Eight designed states: idle (rig at home, envelope armed); planning (cloud latency visible); executing
      (telemetry rolling); CLAMPED (visually distinct from ALLOW — a clamp is a partial refusal and must not read
      as success); VETOED (the relay indicator, the rule, the reason); DEGRADED (network down, stricter
      parameters, and WHICH parameters changed — show the diff); device disconnected (the edge is unreachable —
      calm, with the last known state and its age); error with retry. Never a raw stack trace.
ACCEPTANCE: 8 states each with a designed component and a screenshot in docs/img/states/; the DEGRADED state
            shows the parameter diff.
```

```
ID: D-T30  TITLE: Deploy the dashboard (Serverless Endpoint + static host)
PHASE: 4  OWNER: devops-agent DEPENDS_ON: D-T28, D-T29  BLOCKS: G4, G5
SPEC: Physical AI needs no demo URL, but deploy anyway — judges who can click, will, and a live ledger of a
      recorded session is compelling. Containerise the cloud API as a **Nebius Serverless Endpoint**; the
      dashboard to a free static host. The deployed instance runs against the **recorded session** (a replay of
      the real ledger) plus live simulation mode, so it does not depend on hardware being powered during judging.
      Say clearly in the UI which mode it is in.
ACCEPTANCE: works from a fresh incognito window; the recorded session replays with real ledger data; SIMULATION
            / REPLAY badges correct; no localhost in the bundle.
VERIFY: grep -rn "localhost\|127.0.0.1" dashboard/dist || echo clean; curl -s $DEMO/healthz
```

```
ID: D-T31  TITLE: Accessibility pass
PHASE: 4  OWNER: frontend-agent DEPENDS_ON: D-T29  BLOCKS: G4
SPEC: Outcome chips distinguishable in greyscale and under deuteranopia simulation, with text labels never
      colour alone; the telemetry strip has an aria-live summary of the latest decision rather than requiring
      the user to watch a 10 Hz feed; the camera view has a text scene description (which Cosmos Reason already
      produces — reuse it, and say so); full keyboard nav with visible focus; the StopButton is reachable by
      keyboard in ≤2 presses from anywhere; contrast ≥4.5:1; prefers-reduced-motion stops the telemetry animation.
      Then add an accessibility line to the video script and a paragraph to README + Next Steps.
ACCEPTANCE: axe-core reports 0 critical/serious violations; the StopButton is ≤2 keypresses away everywhere;
            colour-blind simulation screenshots committed; the telemetry has a screen-reader summary.
VERIFY: cd dashboard && npx @axe-core/cli http://localhost:5173 --exit
```

```
ID: D-T32  TITLE: Durability hardening + judge runbook
PHASE: 4  OWNER: devops-agent DEPENDS_ON: D-T30  BLOCKS: G5
SPEC: The deployed dashboard must NOT depend on hardware being powered, on a specific device being online, or on
      any external service. It replays a recorded session from committed data. Pin every version including the
      edge firmware and the simulator. Reserve ≥$10 credits. docs/JUDGE-RUNBOOK.md with: how to watch the video,
      how to run `make demo` in simulation with no hardware and no API key, how to run `make verify-envelope`,
      and how to browse the committed ledger. Hourly uptime ping. Video public. Repo public.
ACCEPTANCE: `make demo` works on a clean clone with no hardware and no API key; `make verify-envelope` passes;
            a non-teammate follows the runbook successfully; ≥$10 credits confirmed.
```

```
ID: D-T33  TITLE: LIMITATIONS.md with real failure cases
PHASE: 4  OWNER: content-agent DEPENDS_ON: D-T22, D-T24, D-T26, D-T23  BLOCKS: G5
CONTEXT: _shared/templates/LIMITATIONS.template.md
SPEC: Real numbers and ≥4 concrete failure cases with photos or stills. Must cover: **this is a research
      prototype, not a certified safety system, and does not constitute compliance with any standard** (name the
      standards a real system would meet, from D-T23); the rig is a single-axis pusher, not a general manipulator,
      and the envelope's rules are specific to a bounded workspace with known geometry; the simulator is a
      simplified in-house model, not a validated physics engine, so the replay proves *that the envelope changed
      the outcome*, not the exact real-world consequence; the false-positive rate and what causes it; the sensor
      suite's blind spots (lighting dependence, occlusion, a transparent intruder); the veto-to-stop distance and
      what it implies about the safe operating speed; the conservative fraction; what happens if the relay itself
      fails (and whether you tested that); the edge model's throughput limits; the cost and latency of the cloud
      planner; and the accessibility gaps and plan.
ACCEPTANCE: every claim backed by a number, test name, citation or photo; a sceptical read finds no unbacked
            sentence; the non-certification statement is unmissable.
```

```
ID: D-T34  TITLE: README.md complete
PHASE: 4  OWNER: content-agent DEPENDS_ON: D-T22, D-T25, D-T26  BLOCKS: G5
CONTEXT: _shared/templates/README.template.md
SPEC: First line = the headline stat pair: "1,240 actions planned · 37 vetoed · 37 replayed · 0 collisions
      shipped" (with your real numbers). Then: a GIF or still of the relay-click moment; the one-sentence
      problem; **the three insider insights**; the LAW statement and `make verify-envelope`;
      **the Cloud/Edge split explained explicitly** (required by the track) with the edge/cloud latency table;
      how NVIDIA Nemotron models are used (Ultra planning, Nano degraded fallback, real costs);
      **where Token Factory accelerated the workflow** (Sandbox branching for reproducible two-arm replays,
      cached tokens, structured output); other Nebius services (**Serverless Job for the replay lane**, Serverless
      Endpoint, and which NVIDIA modules: Cosmos Reason, Isaac GR00T if attempted); the edge local model with its
      real benchmark; the hardware bill with prices and a photo; the replay table with the conservative fraction;
      a 5-minute quickstart running `make demo` in simulation with no hardware and no API key; SAFETY-CASE.md
      and LIMITATIONS.md links; the non-certification statement; licence.
ACCEPTANCE: clean clone + `make demo` works with no hardware and no key; `make verify-envelope` passes; all
            required highlight areas present with real numbers; the hardware photo and bill are in the README.
VERIFY: git clone <url> /tmp/r && cd /tmp/r && make demo && make verify-envelope
```

```
ID: D-T35  TITLE: docs/ — DECISIONS, DISCREPANCIES, HARDWARE-BILL, SIMULATOR-CHOICE, EDGE-MODEL, EVAL, MODEL-USAGE
PHASE: 4  OWNER: content-agent DEPENDS_ON: D-T25  BLOCKS: G5
SPEC: DECISIONS.md ≥15 entries (include: why the planner is not told the envelope parameters; why an in-house
      simulator; why the relay is in the power path; why degraded mode reuses the same rules with stricter
      numbers). DISCREPANCIES.md ≥3 — hardware vs datasheet discrepancies are rich, authentic material here
      (a servo's real stall current vs its spec, a relay's real switching time vs its datasheet, a camera's real
      frame rate vs its claimed one) and they make excellent Devpost feedback content.
ACCEPTANCE: all seven docs present and internally consistent; every number in them matches the reports.
```

### Phase 5 — Package (Wed 16:00 → Thu 30 Oct 18:00)

```
ID: D-T36  TITLE: Video script + shot list (≤2:50, ≥1:00 hardware footage)
PHASE: 5  OWNER: content-agent + human DEPENDS_ON: G4  BLOCKS: D-T37
CONTEXT: _shared/templates/video-script.template.md ; docs/HOOK.md
SPEC: **The track requires ≥1 minute of video showing the hardware or modules in use. Budget 1:30 of hardware
      footage to be safe, and make it continuous and unbroken — a jump cut during the veto destroys the proof.**
  0:00–0:15  THE PROBLEM. Kai's sentence. On screen: the field stat — "~34 of 833 public submissions touch
             physical AI, and almost none show what the system refused to do."
  0:15–0:35  THE RIG, in one continuous shot: the rail, the pusher, the object, the taped keep-out volume, the
             relay module. Point at each. Say what it costs (the €40–80 number is a credibility signal).
  0:35–1:15  **THE VETO, live and unbroken.** Split screen: camera left, telemetry right. A goal goes to Ultra;
             proposals stream; the actuator moves; a hand (or the test block) enters the keep-out volume; the
             envelope vetoes within one frame; **the relay CLICKS — cut to the close-up so it is audible**; the
             pusher stops; a ledger line appears. Caption: "No network. No model. Pure deterministic code with
             hardware authority."
  1:15–1:35  THE LAW, proven on camera: run `make verify-envelope` and show PASS. Then run the test that shows a
             Cosmos Reason response saying "workspace clear" CANNOT clear a veto. Caption: "A large model cannot
             talk this out of stopping."
  1:35–2:00  THE PROOF: the Serverless Job replay. ReplayCompare — envelope_off collides, envelope_on clean, same
             image, same seed. Then the numbers: N vetoed, N replayed, 0 collisions shipped, and the conservative
             fraction stated honestly.
  2:00–2:20  **INSIGHT #3, filmed: pull the network cable.** ModeBadge flips to DEGRADED, the parameter diff
             appears, the rig keeps working under stricter limits, and the ledger shows zero lost decisions.
             Caption: "It fails safe, not open."
  2:20–2:40  How it works: the architecture; name the tiers and the split; the **local model running on the
             device** with its real throughput number (this is Johnny's stated ask); Cosmos Reason advisory;
             Serverless Job; Sandbox branching; the ledger.
  2:40–2:50  LIMITATIONS out loud: **research prototype, not a certified safety system**; single-axis rig;
             simplified simulator; false-positive rate. Next steps: certification path, a real manipulator, more
             rules. Close on the takeaway.
  RULES: no copyrighted music; the audible relay click is your own hardware, not a sound effect; if any footage
         is simulated it MUST carry the SIMULATION badge on screen; public YouTube; captions on.
ACCEPTANCE: reads aloud ≤2:50; **≥1:00 of hardware footage, with the veto take continuous and unbroken**; every
            shot numbered with an owner; the non-certification line is spoken.
```

```
ID: D-T37  TITLE: Shoot and edit the video
PHASE: 5  OWNER: human DEPENDS_ON: D-T36  BLOCKS: G5
SPEC: Shoot the veto sequence MANY times and use the best continuous take. Lock the camera; light the workspace
      evenly; get a separate close-up of the relay for the click cut; record the telemetry screen at native
      resolution, not by filming it. Upload PUBLIC. Verify ≤2:59, that the link works logged-out, and — critically
      — **count the hardware footage and confirm it exceeds 1:00.**
ACCEPTANCE: public URL; ≤3:00; ≥1:00 hardware footage verified by timing the clips; the veto take is unbroken;
            the relay click is audible; captions present.
KILL CRITERION: not shot by Wed 20:00 → cut to 90 s: rig → veto → relay click → replay compare → cable pull →
                limitations. The veto and the cable pull are the two shots that cannot be cut.
```

```
ID: D-T38  TITLE: Devpost submission copy
PHASE: 5  OWNER: content-agent DEPENDS_ON: D-T34  BLOCKS: G5
SPEC: Title; tagline ≤80 chars; Inspiration (Kai + the auditability gap); What it does; How we built it —
      **the Cloud/Edge split explained explicitly, as the track requires**; Nemotron Ultra planning + Nano
      degraded fallback with real costs; **a local NVIDIA open model running on the edge device with its measured
      throughput**; Cosmos Reason as advisory perception; **Nebius Serverless Job for the two-arm replay lane**;
      Token Factory Sandbox branching for byte-identical arms; cached tokens; structured output; the ledger.
      Challenges (≥3, specific: keeping the envelope free of network dependencies while the rest of the system
      is networked; deriving real parameters from a cheap rig; sensor false positives under changing light;
      getting headless deterministic simulation into a Job). Accomplishments (the headline stat pair; the
      purity and determinism tests; the network-outage result; the conservative fraction). What we learned (the
      three insights + one hardware learning from DISCREPANCIES.md). What's next (certification path, a real
      manipulator, more rules, GR00T). Built-with tags. Every number must match the README.
ACCEPTANCE: all sections present; **the Cloud/Edge split is explicitly addressed**; the hardware footage duration
            is stated; no number disagrees with the README; the non-certification statement appears.
```

```
ID: D-T39  TITLE: Devpost feedback section (10 × $100 + swag)
PHASE: 5  OWNER: human DEPENDS_ON: docs/DISCREPANCIES.md BLOCKS: G5
CONTEXT: _shared/templates/devpost-feedback.template.md
SPEC: ≥400 words, ≥6 specific points, ≥4 with numbers or doc URLs, ≥1 concrete feature request. Material unique
      to this project and genuinely useful to the sponsors: running a **Serverless Job** for a simulation replay
      lane — what worked, what the container/image limits were, whether GPU access in a Job was available and how
      it was requested; using **Sandbox branching** for two byte-identical arms of a safety proof rather than for
      code alternatives (a novel use worth surfacing to Nebius); **Cosmos Reason** frame-batching limits and cost
      per batch; deploying an edge/cloud split where the edge is a physical device that cannot be reached from
      the platform — what would make that easier (an ingestion endpoint? device identity? offline-buffer
      support?); the latency observed from the EU to Token Factory for a control loop, with numbers; whether
      cached tokens helped a repeated workspace description.
ACCEPTANCE: specific, technical, constructive; ≥4 numbers; includes the edge-device-ingestion observation, which
            is a real gap a physical-AI-focused sponsor would want to hear about.
```

```
ID: D-T40  TITLE: Final verification sweep + SUBMIT
PHASE: 5  OWNER: human + eval-agent DEPENDS_ON: all BLOCKS: —
SPEC: (1) clean clone → `make demo` in simulation, no hardware, no key → works; (2) `make verify-envelope` → PASS;
      (3) fresh incognito → dashboard → recorded session replays with a SIMULATION/REPLAY badge;
      (4) **video public, ≤3:00, and ≥1:00 of hardware footage verified by timing**;
      (5) LICENSE at repo root; (6) every number identical across README / Devpost / video / SAFETY-CASE;
      (7) ≥$10 credits left; (8) uptime ping running; (9) the hardware bill and photos are in the README;
      (10) SAFETY-CASE.md and LIMITATIONS.md present with the non-certification statement in both;
      (11) the veto-ledger file is committed with the real session data; (12) feedback written;
      (13) the Devpost submission explicitly addresses the Cloud/Edge split and states the hardware footage
      duration.
      Then submit. Screenshot the confirmation. Email every teammate.
ACCEPTANCE: all 13 checked in reports/D-T40.FINAL.md with evidence; submitted by Thu 29 Oct 18:00 CEST.
```

---

## 10. Test & verification plan

| Layer | What |
|---|---|
| **Envelope purity** | Import-graph walk: zero network/LLM symbols in `edge/envelope/`; forbidden-token grep. `make verify-envelope` |
| **Envelope determinism** | 500 recorded snapshots replayed twice in separate processes → byte-identical `determinism_hash`; no wall-clock input to a decision |
| **Envelope priority** | Every simultaneous-fire rule pair resolves to the lower-numbered rule |
| Rules V1–V10 | Positive AND negative fixture per rule (a rule that fires on clean input is a false positive) |
| Contract | The six integrity assertions in D-T09 |
| Parameter provenance | Every taxonomy parameter traces to a measurement in `rig-limits.json` |
| Sensor | ≥10 Hz over 5 min; staleness p99; false-positive rate over an empty-workspace run |
| Interlock | Motion impossible with the relay open even when the driver is commanded directly |
| **Model cannot clear a veto** | A Cosmos Reason "workspace clear" response cannot change a V2 decision (D-T14) — the most persuasive test in the project |
| Ledger durability | A 60 s network outage loses ZERO decisions; dedup on forced double-ship |
| **Network outage** | Degraded mode is strictly more conservative (parameter diff); no fail-open; ModeBadge flips |
| Simulator | Deterministic across processes; headless; the V2 fixture collides off-arm and completes on-arm |
| Replay at scale | Every veto has two arms; 0 collisions on-arm; per-rule table with the conservative fraction |
| Sandbox | Both arms from one pinned image UUID; a re-run reproduces `trajectory_sha256` |
| Session | ≥1,000 actions; ≥5 rules exercised; 0 collisions shipped; veto-to-stop latency and distance recorded |
| False positives | ≥10 min empty + ≥10 min normal; per-rule rates; ≥2 parameters tuned with before/after |
| Simulation mode | `make demo` on a clean clone with no hardware and no API key |
| Accessibility | axe-core 0 critical/serious; StopButton ≤2 keypresses; greyscale + deuteranopia |

---

## 11. Design system summary (full brief in D-T08)

**Metaphor:** an industrial control room HMI. Dark slate panels, hairline borders, sharp corners, **everything
numeric in monospace**. No glow, no gradients, nothing decorative — a safety system that looks like a toy will
not be believed.

Two rules above all others:
1. **A SIMULATION/REPLAY badge is permanently visible whenever the data is not from live hardware.** Confusing
   the two would be the single worst failure this project could commit.
2. **VETO, CLAMP and ALLOW are distinguishable in greyscale and under deuteranopia simulation, with text labels,
   never colour alone.** A clamp is a partial refusal and must not read as success.

The hero component is `ReplayCompare`: two simulation stills side by side — `envelope_off` collided,
`envelope_on` clean — from one byte-identical image. It is the whole argument in one frame.

---

## 12. Risk register & pivots

| # | Risk | Likelihood | Detection | Mitigation | Pivot |
|---|---|---|---|---|---|
| R1 | **No hardware in hand** | **Decisive** | **D-T01, Sun night** | The go/no-go gate at the top of this file | **Switch to Idea A. Do not negotiate** |
| R2 | Hardware never works reliably | Med–High | D-T17, Mon 22:00 | Simulation mode is first-class (D-T05); buy a second cheap servo; keep the rig single-axis | Simulation-only submission — loses the footage moat; consider switching to A |
| R3 | Not enough hardware footage (<1 min) | Med | D-T37 | Budget 1:30; shoot the veto take many times; keep the camera locked | Extend with rig close-ups and the relay click; still ≥1:00 |
| R4 | The relay click doesn't happen on camera | Low | D-T16 | A separate close-up shot; a audible mechanical relay (not a solid-state one) | Cut to the telemetry + interlock indicator; weaker but survivable |
| R5 | Simulator not headless / not deterministic | Med | D-T04, D-T12 | Build the small in-house swept-volume simulator (default recommendation) | In-house simulator only; document the industrial choice you'd make |
| R6 | Envelope latency too high on the device | Low | D-T10 | Profile; move the hot path to numpy/C; reduce snapshot rate to the minimum safe value | Report the real number and the safe operating speed it implies |
| R7 | Cosmos Reason unavailable or unsuitable | Med | D-T07 | It is advisory by design — the system works without it | Drop P2; use frame differencing only; note it in LIMITATIONS |
| R8 | GR00T consumes the schedule | **High if attempted** | D-T27 | **3-hour hard timebox; only after D-T22 is DONE** | Drop it; record the attempt in DECISIONS.md and Next Steps |
| R9 | Claims read as over-reaching on safety | **Med–High** | D-T26, D-T33 | SAFETY-CASE.md + the non-certification statement in the first paragraph of the README, in the video, and in LIMITATIONS | Narrow every claim to "a research prototype demonstrating an auditable deterministic veto layer" |
| R10 | False positives make the demo look broken | Med | D-T24 | Tune the two worst parameters; test negative cases as hard as positive; report the rate honestly | Widen the keep-out volume and slow the rig — a slower, reliable demo beats a fast, flaky one |
| R11 | Credits exhausted by 1,000-action sessions | Low | Ledger budget guard | Batch Cosmos Reason at ~2 fps; Nano fallback in degraded mode; cache the workspace description | Reduce to 500 actions and report n honestly |
| R12 | Scope creep (mobile base, multi-arm, SLAM, voice) | **High** | Every gate | Component table §3; feature freeze at Phase 4; a fixed single-axis cell is MORE filmable | Cut to the hook |

---

## 13. Team allocation

| Person | Lanes | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|---|---|
| **P1 — edge/safety** | envelope, sensors, actuator | D-T01, D-T03, D-T06 | **D-T10**, D-T15 | D-T16, **D-T17** | **D-T19**, D-T24 | D-T32 | D-T37 (rig shots) |
| **P2 — cloud/models** | planner, perception, edge model | D-T07 | D-T11, D-T13 | D-T14, D-T18 | D-T25, D-T27 | D-T30 | D-T38 |
| **P3 — sim/replay** | simulator, jobs, sandbox | D-T04 | D-T12 | — | **D-T20**, D-T21, D-T22 | D-T28 (ReplayCompare) | D-T37 (edit) |
| **P4 — frontend/content/human** | dashboard, docs, interviews | D-T02, D-T05, D-T08 | D-T09 | — | D-T23, D-T26 | D-T28, D-T29, D-T31, D-T33, D-T34, D-T35 | D-T36, D-T39, D-T40 |

**Critical path:** D-T01 → D-T03/D-T06 → **D-T10** → D-T16 → **D-T17 (G2, filmed)** → D-T19 → D-T20 → D-T22 →
D-T26 → D-T34 → D-T36 → D-T37 → submit.
**D-T01 is the whole project. Decide it before you read anything else.**

---

## 14. Definition of Done — project level

- [ ] **D-T01 go/no-go decided and recorded; the tier is named with a photo and a parts bill**
- [ ] All tickets DONE or explicitly parked with a reason in `docs/DECISIONS.md`
- [ ] `make check` green from a clean clone; **`make demo` works with no hardware and no API key**
- [ ] **`make verify-envelope` PASSES — purity (no network/LLM in the import graph) and determinism (500-replay hash identity)**
- [ ] All ten rules V1–V10 implemented, each with positive and negative fixtures
- [ ] Every envelope parameter traces to a measurement in `data/calibration/rig-limits.json`
- [ ] The hardware interlock is in the actuator's power path, with a bypass test proving motion is impossible when open
- [ ] **Veto-to-stop latency and distance measured and published**
- [ ] ≥1,000 planned actions logged; ≥30 vetoes; ≥5 distinct rules exercised; **0 collisions shipped**
- [ ] **Every veto replayed in BOTH arms via a Nebius Serverless Job; 0 collisions on-arm; the conservative fraction reported honestly**
- [ ] Both arms run from one pinned Token Factory Sandbox image UUID; a re-run reproduces `trajectory_sha256`
- [ ] A local NVIDIA open model runs **on the edge device** with a published real benchmark
- [ ] **The "a model cannot clear a veto" test passes**
- [ ] **The network-outage test passes on real hardware and is filmed: degraded mode strictly more conservative, zero lost decisions, no fail-open**
- [ ] False-positive study published; ≥2 parameters tuned with before/after recorded
- [ ] `docs/SAFETY-CASE.md` complete, with the non-certification statement in the first paragraph
- [ ] ≥1 practitioner conversation; ≥1 quote with permission; the relevant standards named in LIMITATIONS
- [ ] Ledger covers ≥95% of calls; edge and cloud latency reported separately; the all-Ultra counterfactual published
- [ ] Dashboard deployed; SIMULATION/REPLAY badges always correct; StopButton ≤2 keypresses away
- [ ] Accessibility audited and called out in the video
- [ ] **Video public, ≤3:00, with ≥1:00 of hardware footage verified by timing, and the veto take unbroken**
- [ ] `LICENSE` at repo root; repo public; uptime ping running; ≥$10 credits reserved
- [ ] `docs/JUDGE-RUNBOOK.md` followed by a non-teammate
- [ ] Devpost copy explicitly addresses the Cloud/Edge split and states the hardware footage duration
- [ ] Devpost feedback written with ≥4 numbers, incl. the edge-device-ingestion observation
- [ ] **Submitted by Thu 29 Oct 18:00 CEST**
