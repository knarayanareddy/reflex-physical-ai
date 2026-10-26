# Why the replay lane uses an in-house swept-volume model

`$defs/ReplayResult` asks the author to justify the simulator. This is that justification.

## The claim being tested

> A cloud planner proposed an action. The local envelope refused or slowed it. Here is what
> would have happened otherwise.

Two arms, one scene, one simulator:

| Arm | Action replayed | Meaning |
|---|---|---|
| `envelope_off` | `intended_action` | the planner's own numbers, with no safety layer |
| `envelope_on` | `shipped_action` (`None` after a veto) | what the machine actually did |

The difference between the two outcomes is attributable to the envelope **only if** the two
arms share everything else. That requirement drives the choice of simulator far more than
fidelity does.

## What was rejected, and why

**MuJoCo / PyBullet / Gazebo.** A physics engine is the right tool for contact dynamics,
friction cones and force limits — none of which this claim depends on. Adopting one would
add a dependency whose own accuracy becomes a second, undocumented safety case ("trust the
solver"), and whose results are hard to audit line by line. It would also make the replay
non-hermetic: engine version, asset compilation and contact-solver parameters all become
inputs to the proof.

**A learned or cloud-hosted simulator.** Non-deterministic by construction, and the whole
lane exists to demonstrate determinism.

**Rendering a trajectory from the recorded decision and calling it a "replay".** That is an
animation, not a counterfactual. It would show the shipped action and say "no collision" by
construction.

## What was chosen

A swept-volume check in the **x-y plane at the end-effector's z**, sampled every 2 mm:

1. start from the snapshot's recorded `end_effector` pose;
2. move in a straight line to the action's `target_pose`;
3. at each sample, test against (a) the keep-out volume when the snapshot reports it
   occupied, (b) the allowed workspace from the *normal* V5 parameter set, (c) every
   advisory object pose inflated by the end-effector radius.

Roughly 90 lines, no dependencies, deterministic to the last bit. `trajectory_sha256` is
computed over the sampled points at 1 µm / 0.001 ms resolution, so a run that differs by a
nanometre produces a different hash instead of a fuzzy "close enough".

## What it cannot see — stated, not hidden

The job prints the rules that stopped the machine without a spatial witness, and marks them
`no geometric counterfactual`:

| Rule | Why geometry cannot adjudicate it |
|---|---|
| V1 e-stop / interlock | electrical state, not position |
| V3 velocity | it is a clamp, not a stop; both arms complete |
| V4 force | contact force is not modelled (no dynamics) |
| V7 sensor staleness | about time, not space |
| V8 network degraded | about a link |
| V9 plan trust / TTL | about provenance and time |
| V10 human presence | detection may fire without localisation; inventing a position would be fabrication |

For V10 the honest statement is: *the envelope stopped because a person was detected; the
2-D model has no position for them, so no counterfactual is claimed.* A replay lane that
manufactured a position to make the picture prettier would be lying with arithmetic.

## Where a physics engine would be required

The moment the project claims anything about **contact forces**, the swept-volume model is
insufficient and a dynamics engine becomes mandatory, together with a validation suite
against measured data. That is recorded here so the limitation is a decision rather than an
oversight.

## Reproducing it

```bash
make replay          # rebuilds the ledger from the fixture corpus, replays both arms
python jobs/replay_all.py --ledger runs/veto-ledger.jsonl --out runs/replay
```

Every record is validated against `$defs/ReplayResult` before it is written. If a record
does not satisfy the contract, the job exits non-zero rather than saving it.
