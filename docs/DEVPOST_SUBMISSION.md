# Reflex — Devpost submission

**Live demo:** <https://knarayanareddy.github.io/reflex-physical-ai/>
**Video:** `docs/media/reflex-demo.mp4` (2:45)
**Repository:** <https://github.com/knarayanareddy/reflex-physical-ai>

Everything below is checkable from the repository. Where a figure is not measured, the row says so
instead of estimating — the same rule the README and `LIMITATIONS.md` follow.

---

## What it is

A robot's cloud planner proposes an action. Before that action reaches an actuator, a **deterministic
edge safety envelope** decides whether it ships: ten interlocks (V1–V10), a normal and a degraded
parameter set, and an append-only ledger that records every decision — including the ones that refuse.

The claim the project makes is not "our model is safe". It is narrower and testable: **the layer that
refuses is local, deterministic and auditable, and it keeps receipts.** The model may propose
anything; the envelope decides, and its decision is a pure function of the snapshot, the proposal and
the calibration — no network, no clock, no model in the path.

## Why it matters

A safety interlock that needs the cloud to answer is not an interlock. The interesting failure is not
"the model is wrong", it is "the model is right and the link is down, or the plan is 300 ms stale, or
an intruder walked into the cell". Those are the cases the envelope exists for, and they are the cases
it is tested against — including a network cut that turns an `ALLOW` into a `VETO` in the same
session (video 1:45–2:10).

## What is demonstrated

| | Where | What it shows |
|---|---|---|
| 10-second session | `make demo` · video 0:15–0:45 | 100 proposals at 10 Hz, the tool tip advancing 10 → 70 mm, an intruder at t=4.0 s, `VETO V2_KEEP_OUT_OCCUPIED`, the interlock latching so all 59 later proposals are refused by V1 |
| Operator dashboard | `make demo` → `:5173` · video 0:45–1:15 | Scene, all ten interlocks with the value each rule used, telemetry and the ledger |
| Two-arm replay | dashboard → **simulate replay** · video 1:15–1:45 | The same decision with the envelope off (collides with the keep-out volume at 150.0 mm) and on (0.0 mm travelled) |
| Network cut | `scripts/network_cut.py` · video 1:45–2:10 | The same plan, allowed under normal parameters, refused under degraded ones — the TTL ceiling tightened before the plan arrived |
| Static site | <https://knarayanareddy.github.io/reflex-physical-ai/> | The recorded session replayed in the browser with **no backend**, scrubbable frame by frame |

## The numbers

From `runs/headline_statistics.json` (1,000 actions, seed 20261026), reproduced by `make batch`:

| Figure | Value |
|---|---|
| Actions planned | **1,000** |
| Hard vetoes enforced | **420** |
| Adverse end states prevented in sim | **248** = **170** contacts + **78** boundary excursions |
| Collisions shipped under the envelope | **0** |
| Envelope latency | p50 116 µs · p95 162 µs · max 239 µs (one run, build machine) |
| Session wall time | 2.86 s |

**248 is not "248 collisions".** It is the total the JSON field `prevented.total` holds: 170 swept
segments entered the keep-out volume or an obstacle under envelope-off, and 78 clamped plans would
have left the allowed workspace. The dashboard shows the two figures separately for that reason, and
the video's closing card states the split.

## How it is built

- **`backend/app/envelope/`** — pure decision functions. V1–V10 are pure; the loader refuses a
  calibration profile whose degraded values are not strictly more conservative than its normal ones.
- **`backend/app/replay.py`** — a 2-D swept-volume simulator at the recorded end-effector z. It is
  explicitly *not* contact dynamics (see `LIMITATIONS.md` §2).
- **`backend/app/plan/`** — the Ultra planner, 38 tests, **library only**: no endpoint invokes it yet.
- **`frontend/`** — React + Vite dashboard, three columns, no client-side decision logic.
- **`jobs/`** — the demo, the 1,000-action batch, the static-replay export.
- **`scripts/`** — contract validators, the Pages server, the video recorder.

## What is not done — the honest list

Reproduced from `LIMITATIONS.md` §3; every row has a number.

- **No hardware.** Nothing is wired: no relay, no limit switches, no camera. Veto-to-stop latency and
  distance are `null` in the contract and are **not measured**.
- **Zero Token Factory calls.** No API key exists in this build; `runs/ledger.jsonl` does not exist.
  The submission's "runs on Token Factory at runtime" filter is therefore **unmet**, and the model
  tiering matrix in the README marks the cloud row `NOT MEASURED`.
- **The planner is not wired to the envelope.** `POST /v1/plan` does not exist; the planner is a
  library with tests.
- **All 22 calibration values are `synthetic`.** Every decision is stamped `mode=simulation`; the
  dashboard shows a permanent badge and the video says it out loud.
- **No measured Sandbox run.** The replay pack verifies offline (`pack verified`), but no SDK call
  exists to execute it inside a Token Factory Sandbox (`TODO_VERIFY(sandbox-sdk)`).
- **The video is generated, not filmed.** It is a Playwright screencast of the real build at
  1920×1080 with 125 % page zoom; the terminal lines are captured stdout of the commands shown, not a
  TTY recording. There is no voiceover track — the script's spoken column is delivered as on-screen
  content, and `video/script.md` remains the shot list for a narrated take.

## Judging criteria, in the project's own terms

| Criterion | Where to look |
|---|---|
| **Technical depth** | Ten interlocks with per-rule traces; purity, determinism (500 snapshots, byte-identical), concurrency and fresh-interpreter tests; a two-arm counterfactual for every decision |
| **Use of Token Factory** | *Not met at runtime.* The integration surface exists (`app/tf/`), the ledger format does too, and the tiering matrix shows where the numbers would land — but no call has been made, so no number is claimed |
| **Real-world usefulness** | The refusal path is the product: an occupied keep-out volume, a stale camera, an unreachable cloud. Each is a committed fixture with a near-miss twin |
| **Originality** | The receipt. Every decision is a validated record; the demo's ledger line is the demo |
| **Completeness** | 431 tests, `make check` green, a static site anyone can open, a 2:45 video, and a limitations file that lists what does not work |

## Reproduce it

```bash
git clone https://github.com/knarayanareddy/reflex-physical-ai && cd reflex-physical-ai
cd backend && uv sync --extra dev && cd ..
make check          # 431 tests, lint, types, contracts, calibration
make demo           # 10-second session, then API + dashboard on :8000 / :5173
make build-pages    # static site into frontend/dist (base /reflex-physical-ai/)
make pages-serve    # serve it the way Pages does, on :4173
node scripts/record-demo.ts   # re-record the video from video/script.md
```

`make demo` and `make check` need no API key and no network. Only the first `npm install` does.
