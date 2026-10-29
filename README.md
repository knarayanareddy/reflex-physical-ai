# Reflex — a deterministic veto layer for robot actions, with receipts

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-2ea44f?style=for-the-badge)](https://knarayanareddy.github.io/reflex-physical-ai/)
[![Submission Status](https://img.shields.io/badge/Submission-READY-success?style=for-the-badge)](docs/DEVPOST_SUBMISSION.md)

**▶ [Open the live demo](https://knarayanareddy.github.io/reflex-physical-ai/)** — the dashboard, in a
browser, with nothing installed. It replays a 10-second session recorded from the real envelope: scrub
to frame 41 for the veto, then press **simulate replay** for the two-arm counterfactual.

> A cloud planner proposes; a local, deterministic envelope refuses. Every refusal is written to a
> ledger with the sensor state that caused it, and replayed twice — once with the envelope off, once
> with it on — so the record shows what the refusal prevented instead of asserting that it mattered.

**Measured, on 1,000 synthetic actions (2026-10-26):**

> ### 1,000 Actions Planned · 420 Vetoes Enforced · 248 Prevented (170 contacts + 78 boundary excursions) · 0 Shipped

| Number | Value | Where it comes from |
|---|---:|---|
| Actions planned | **1,000** | `runs/headline_statistics.json` → `headline.actions_planned` |
| Vetoes enforced | **420** | `headline.vetoes_enforced` (= `VETO` decisions) |
| Collisions prevented | **248** | `headline.collisions_prevented` = **170** geometric contacts + **78** boundary excursions |
| Collisions shipped | **0** | `headline.collisions_shipped_under_envelope`; the job exits non-zero if this is not 0 |
| Allowed / allowed-clamped / vetoed | 450 / 130 / 420 | `decisions` |
| Session run time | 2.86 s for all 1,000 actions *including* both replay arms | `acceptance.elapsed_ms` |

Regenerate the table with `make batch` (≈3 s, no network); the latency figures in the tiering table
below come from `make demo` and `make batch`. Every statistic on this page is computed by a command
you can run; nothing here is copied from prose. A regenerated `runs/headline_statistics.json` differs
from the committed one in exactly two fields — `acceptance.elapsed_ms` and `sandbox_pack.pack_sha256` —
because both measure the run rather than the session (`reports/D-T20-T21.TASK_REPORT.md` describes the two digests).

**What "248" is.** The JSON's `collisions_prevented` is `prevented.total`: 170 actions whose
envelope-off arm entered the keep-out volume or an obstacle, plus 78 clamped joint-limit actions whose
envelope-off arm would have left the allowed workspace. The dashboard prints the two figures
separately — **170 collisions, 78 boundary excursions** — because adding a boundary excursion to a
collision count would overstate the result by 46%. The banner above states the split rather than the
field name: `collisions_prevented` is the JSON's key, not a description of what it counts.

**What this is not.** The session is **synthetic**: `runs/headline_statistics.json` says so in its
`source` field, and every decision is stamped `mode=simulation`. No hardware ran, no camera existed,
no model was called. The "collisions" are swept-volume intersections in a 2-D model, not contact
dynamics — see [LIMITATIONS.md](LIMITATIONS.md) §2.

**Live, no install:** <https://knarayanareddy.github.io/reflex-physical-ai/> — the recorded
10-second session, replayed in the browser with no backend. The page says so in its header
(`replay/bundle.json · recorded, not live`) because the browser is not allowed to decide: every frame
it scrubs through was produced by `app.envelope.evaluate` at build time. **Video:** 2:45, seven shots,
in `docs/media/reflex-demo.mp4` — regenerated from `video/script.md` by `node scripts/record-demo.ts`.

[![CI](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/ci.yml)
[![Deploy Pages](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/deploy-pages.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Track](https://img.shields.io/badge/Track-Physical-green.svg)](docs/SUBMISSION-CHECKLIST.md)

---

## What exists today, and what does not

**Phase 4 of 5.** The safety layer, the planner library, the dashboard and the batch/replay lane are
built and tested; the hardware and the cloud job runner are not.

| Component | Status | Evidence (run it) |
|---|---|---|
| Frozen contracts + 10-rule taxonomy | **Done** | `make schema`, `make taxonomy` |
| Deterministic envelope V1–V10, two modes | **Done (synthetic parameters)** | `make verify-envelope` — 10 rules, purity, 500-snapshot determinism, 20 fixtures |
| Veto ledger (every decision, validated, fsync'd) | **Done** | `backend/tests/test_decision_ledger.py` |
| Two-arm replay | **Done** | `make replay` → 34 `ReplayResult` records, 3 geometric counterfactuals |
| 1,000-action session + headline statistics | **Done** | `make batch` → `runs/headline_statistics.json` |
| Verifiable replay pack (network-off) | **Done** | `python -m app.sandbox.replay_pack verify ../runs/replay_pack` |
| 10-second offline demo (V2 veto, interlock, ledger line) | **Done** | `make demo` |
| Operator dashboard (headline bar, ledger, replay canvas) | **Done** | `make demo` → http://127.0.0.1:5173/ |
| Static dashboard with no backend (GitHub Pages) | **Done** | <https://knarayanareddy.github.io/reflex-physical-ai/> — replays the recorded session; `make pages-check` validates the bundle |
| Demo video, 2:45, seven shots | **Done** | `docs/media/reflex-demo.mp4`; regenerate with `node scripts/record-demo.ts` |
| Ultra planner (library, 38 tests) | **Done — not served** | `backend/app/plan/ultra.py`; no endpoint calls it yet |
| Cloud planner reachable from the API | **Not started** | nowhere to call it from |
| Measured calibration (22 values) | **Not started** — all `synthetic` | `make params` prints 22/22 synthetic; `make params-strict` fails until a rig is measured |
| Token Factory call in the ledger | **0 calls** | `runs/ledger.jsonl` is absent until a key exists |
| Nebius Serverless Job runner | **Not started** | the batch job runs locally |
| Hardware, interlock relay, measured veto-to-stop | **Not started** | no wiring, no measurement |
| Replay pack executed inside a Token Factory Sandbox | **Not started** | `sandbox-plan` prints the disabled-network steps; no SDK call exists (logged in `docs/DISCREPANCIES.md`) |

---

## Run it in two minutes (no API key, no network)

```bash
git clone https://github.com/knarayanareddy/reflex-physical-ai.git
cd reflex-physical-ai

make check   # lint, types, contracts, taxonomy, calibration, fixtures, 431 tests (~17 s)
make demo    # 10-second simulated session, then API on :8000 and dashboard on :5173
```

`make check` needs [uv](https://docs.astral.sh/uv/) and Python 3.11+. `make demo` needs Node 18+ for
the dashboard; if `frontend/node_modules` is missing the demo prints the one command that installs it
(`cd frontend && npm install`, the only step that needs the registry) and serves the API anyway.

**No install at all?** Open <https://knarayanareddy.github.io/reflex-physical-ai/>. That build has no
backend: it replays `replay/bundle.json`, recorded at build time by running the real session through
the real envelope. Scrub the timeline to frame 41 to see the veto, and press **simulate replay** for
the two-arm counterfactual. The page cannot evaluate a new proposal, and says so.

What `make demo` prints, in order (verbatim except the latency line, which is measured per run):

```
t= 3.9 s  x=  68.5 mm  ALLOW
t= 4.0 s  x=  70.0 mm  VETO          V2_KEEP_OUT_OCCUPIED    <-- intruder inside the keep-out volume
t= 4.1 s  x=  70.0 mm  VETO          V1_EMERGENCY_STOP
...
  interlock relay : opened = True
  envelope OFF : collided with keep_out_volume at t=5333 ms, contact (150.0, 0.0) mm
  envelope ON  : completed, 0.0 mm travelled (1 trajectory point)
  PASS  the interlock latches              59 later proposals all refused, none shipped
DEMO PASS — 6/6 checks, 0 collisions shipped
```

It serves the same story over HTTP and checks both servers before declaring PASS:
`API /v1/envelope/evaluate → same V2_KEEP_OUT_OCCUPIED decision as in-process`,
`UI / → 200, mount point present`, `UI /stats/headline.json → 200 · 1000 actions · 0 shipped`.
Use `make demo-check` for the same checks without leaving a server running.

---

## Every command

| Command | Needs a key? | What it actually does |
|---|:---:|---|
| `make check` | No | Everything CI runs: ruff, mypy, `$ref` resolution, every schema law, taxonomy strictness, calibration invariants, 20 fixtures, 431 tests (430 + 1 bundle-dependent) |
| `make demo` | No | The 10-second session (V2 veto → interlock → ledger line → both replay arms), then serves API :8000 and dashboard :5173 |
| `make demo-check` | No | The same session and HTTP probes, then exits 0 and stops the servers |
| `make sample` | No | The contract and ledger fixture tests only |
| `make verify-envelope` | No | Import-graph purity, 500-snapshot determinism, 20 rule fixtures, calibration invariants |
| `make replay` | No | Replays the fixture corpus through both arms into `runs/replay/` |
| `make batch` | No | 1,000-action session, both arms per action, `runs/headline_statistics.json`, and a verifiable pack in `runs/replay_pack/` |
| `python scripts/network_cut.py` | No | Posts the demo's plan twice — cloud reachable, then 9 s unreachable — and fails unless it is allowed then refused |
| `make params` | No | Prints every normal→degraded value and fails if a degraded value is less conservative |
| `make serve` | No | The API alone on :8000 |
| `make build-pages` | No | Records the 10-second session to `replay/bundle.json`, then builds the static site (base `/reflex-physical-ai/`) |
| `make pages-serve` | No | Serves that build under `/reflex-physical-ai/`, the way GitHub Pages does |
| `make pages-check` | No | Re-validates the generated bundle's seven invariants without rewriting it |
| `node scripts/record-demo.ts` | No | Records the 2:45 video from `video/script.md` into `docs/media/` (needs Playwright + ffmpeg) |

---

## Model tiering: what is measured, what is not

The architecture splits work by latency budget and by failure mode: the cloud may *propose*, the edge
*must* decide. The table below publishes what that costs — and leaves the unmeasured cells empty
rather than estimating them.

| Tier | Runs | Model (as pinned in `backend/app/config.py`) | Latency | Cost |
|---|---|---|---|---|
| Cloud planner | Proposal generation | `nvidia/Nemotron-3-Ultra-550b-a55b` | **NOT MEASURED** | **NOT MEASURED** |
| Edge envelope | V1–V10 evaluation | none — deterministic Python, stdlib only | **p50 116 µs · p95 162 µs · max 239 µs** over 100 decisions (`make demo`, one run on the build machine); 2.86 ms per action including both replay arms over 1,000 actions (`make batch`) | **$0.00 per decision** — zero API calls; the decision path has no network client (asserted by `tests/test_envelope_purity.py`) |
| Edge, other | Not wired | `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-nano`, `nvidia/cosmos-reason-2` | — | — |

**Why the cloud row is empty.** Two reasons, both checkable in this repo: (1) no `NEBIUS_API_KEY`
exists in the build environment, so no call was ever made; (2) the planner is a library
(`UltraPlanner.plan`) with no CLI or HTTP endpoint, so there is nothing for a reader to invoke either.
`runs/ledger.jsonl` — the telemetry ledger that records one line per model call with `prompt_tokens`,
`completion_tokens`, `latency_ms` and `cost_usd` — does not exist. The latency delta the tiering
question asks for therefore has no second operand, and publishing one would be invention.

To fill it: set `NEBIUS_API_KEY`, call `UltraPlanner(...).plan(goal, scene)` once; it appends a line to
`runs/ledger.jsonl` and the two cells become measurable. The model IDs above are pinned in config and
have **not** been checked against the live `/models` list (logged in `docs/DISCREPANCIES.md`).

---

## How this maps to the four judging criteria

### Technological Implementation (25%)

- **A pure envelope.** Ten rules, a total priority order, two parameter sets, `stdlib` only — a test
  walks the import graph and fails the build if an HTTP client, `socket`, or model SDK appears in the
  decision path (`backend/tests/test_envelope_purity.py`). Determinism is tested across 500 generated
  snapshots, key order, concurrency, fresh interpreters and JSON round-trips.
- **An audit trail that is validated, not printed.** Every decision is checked against
  `$defs/EnvelopeDecision` before it is appended, with `fsync`
  (`backend/app/decision_ledger.py`, 11 tests).
- **A counterfactual that re-runs.** Each decision is simulated twice — `envelope_off` executes the
  planner's action, `envelope_on` executes what shipped — producing 2,000 contract-valid
  `ReplayResult` records for the 1,000-action session.
- **An artifact that re-derives offline.** `app/sandbox/replay_pack.py` packages decisions + replays +
  a manifest; `verify` re-executes all 2,000 records instead of trusting hashes, and a test replaces
  `socket.socket` with a raiser to prove it needs no network.
- **A planner that cannot smuggle a verdict.** `app/plan/ultra.py` treats model output as untrusted
  input: ids and timestamps are stamped by code, a malformed plan becomes a V9 veto rather than an
  exception, and abstention is a first-class result (38 tests).
- **What is missing:** no hardware, no measured calibration (22/22 values synthetic), the planner is
  not served, and no Nebius Serverless Job has been submitted.

### Design (25%)

- **One screen, verdict first.** The operator view is three columns: scene (where the tool tip is
  going), interlock list (V1–V10 with live pass/fail), telemetry and veto ledger. The headline bar sits
  above all of it, and every ledger row can open its own two-arm replay on a canvas — red path
  collides, green path stops — with a play/pause control and the contact point marked.
- **The software says when it does not know.** A missing calibration profile forces `mode=simulation`
  and a permanent badge; a missing statistics file renders *"run `python jobs/batch_1000_eval.py`"*
  instead of zeros; an API failure renders as an error, not as an empty table.
- **Colour is never the only signal.** VETO / ALLOW / ALLOW_CLAMPED each carry a word and a colour, and
  the badges are readable in greyscale.
- **What is missing:** no usability testing, no accessibility audit, and the layout has only been
  rendered at one desktop width (verified with jsdom, not a browser — see LIMITATIONS).

### Potential Impact (25%)

- **The artefact people actually ask for is the refusal record.** A small integrator can show a client
  or an insurer what the cell declined to do, with the sensor state that caused it and a replay of the
  counterfactual — not a log line that says "stopped".
- **The numbers are already here.** 420 refusals in a 1,000-action session that mixes 450 nominal
  actions with 550 adversarial ones, 248 adverse end-states shown to be preventable, 0 shipped
  collisions, and a 2.9 s batch that fits a CI job. The same code runs unchanged at 50 actions or 100,000.
- **The cheapest safety upgrade is local.** The envelope is a library with no service dependency: no
  network, no model, no queue. A 120 µs decision fits a 10 Hz control loop with three orders of
  magnitude to spare.
- **What is missing:** no practitioner interview is recorded in this repository, and the impact claim
  is therefore a design argument, not a validated one.

### Quality of the Idea (25%)

- **Three claims, each with a test.** (1) Veto authority must be local and unpersuadable — pinned by
  the purity test and the two parameter sets. (2) The valuable record is the ledger of refusals —
  pinned by the ledger contract and the 2,000 replay records. (3) The edge/cloud split is a *safety*
  property, not a cost optimisation — pinned by 60 network-outage tests showing the rig keeps operating
  under strictly more conservative parameters and never fails open.
- **The refusal is the product.** Every robotic demo shows the robot doing the thing. This one shows
  the machine *not* doing it, why, and what would have happened — which is what an audit asks for.
- **Honesty as a mechanism, not a disclaimer.** Unmeasured numbers are labelled, synthetic parameters
  force `mode=simulation`, archives that cannot be re-derived are rejected, and the batch job exits
  non-zero if a single action ships a collision.
- **What is missing:** the idea is close to what a safety-rated PLC already does; this is a software
  analogue for teams that do not have one, not a replacement for one. It is not certified, and the
  README says so on the first screen.

---

## The problem

**Persona — Kai, 29.** A robotics integrator deploying a small pick-and-place or dispensing cell for a
client. She has a model that plans motions. She has an e-stop. She has **no auditable middle layer**:
no record of near-misses, and no way to show a client or an insurer that the safety logic is
deterministic and cannot be talked out of a decision by a prompt.

> *"I can plan a robot's next action in two seconds. I can't tell anyone, after the fact, what it
> wanted to do that I stopped it from doing — or prove the thing that stopped it can't be talked out of
> it."*

---

## Three design decisions this project is built on

1. **Veto authority is local and non-negotiable.** The envelope is pure deterministic Python with no
   LLM or HTTP client in its import graph. `make verify-envelope` walks the graph and fails if one
   appears. In this build the interlock is a *decision* (`interlock_relay_opened`) recorded in the
   ledger; the relay itself is not wired — see [LIMITATIONS.md](LIMITATIONS.md) §2.
2. **The valuable artifact is the veto ledger, not the successful action.** One decision per
   evaluation: sensor state, firing rule, full rule trace, intended action, and both replay arms.
3. **Edge and cloud do different jobs, and the split is a safety property.** Cut the network and the
   rig keeps operating under stricter degraded parameters with a longer hold, a tighter velocity
   ceiling and a doubled swept-volume inflation. 60 tests pin that it never fails open.

---

## Repository map

```
├── schemas/core-schemas.json      frozen contracts; every stated law has a test
├── data/veto-taxonomy.json        the 10 veto rules, both parameter sets, rationales
├── data/calibration/rig-limits.json  parameter values + provenance (synthetic today)
├── data/fixtures/snapshots/       20 cases: each rule's trigger and its near miss
├── backend/app/
│   ├── envelope/                  the deterministic V1–V10 envelope (stdlib only)
│   ├── decision_ledger.py         the veto ledger: one EnvelopeDecision per evaluation
│   ├── replay.py                  two-arm swept-volume replay (2 mm steps)
│   ├── plan/ultra.py              cloud planner: untrusted output -> typed proposals
│   ├── sandbox/replay_pack.py     build/verify a pack that re-derives offline
│   ├── gate/gate.py               evidence-quote checker (not the envelope)
│   └── main.py                    /health, /v1/info, /v1/envelope/{info,evaluate}
├── backend/tests/                 431 tests across 18 files
├── frontend/
│   ├── src/App.tsx                dashboard + static timeline (three columns, replay canvas)
│   ├── src/staticReplay.ts        the Pages build's only data source: the recorded session
│   └── public/replay/             generated by `make pages-data` (gitignored)
├── jobs/
│   ├── offline_demo.py            the 10-second demo (`make demo`)
│   ├── batch_1000_eval.py         the 1,000-action session (`make batch`)
│   ├── export_static_replay.py    records the session for the static site (`make pages-data`)
│   └── replay_all.py              fixture corpus through both arms (`make replay`)
├── scripts/
│   ├── network_cut.py             the video's shot 5, runnable: allow → refused after the cut
│   ├── record-demo.ts             records docs/media/reflex-demo.{mp4,webm} from video/script.md
│   ├── serve-pages.mjs            serves the Pages build under its real sub-path
│   └── stage/                     the recorder's title, terminal, limitations and close cards
├── docs/media/                    the 2:45 demo video + a JSON summary of the take
├── docs/DEVPOST_{SUBMISSION,FEEDBACK}.md  the submission text, and what the form got wrong
├── reports/                       one TASK_REPORT per ticket: claims, pasted output, NOT_DONE
└── docs/                          protocol, discrepancies, judging rubric, submission checklist
```

## Limits

[LIMITATIONS.md](LIMITATIONS.md) is the honest list: synthetic parameters, a 2-D single-axis
simulator that is not contact dynamics, no hardware, no measured veto-to-stop latency, no model call
recorded, and the exact numbers for each. Read it before quoting anything above.

Two limits are specific to the publishing work and worth naming here: the Pages site is a
**recording**, so it cannot answer a proposal it was not built with; and the video has **no voiceover
track** — `video/script.md` is the narrated shot list, and the recorded take carries its spoken column
as on-screen text.

Corrections of earlier documentation errors, and every open verification item with an owner, are in
[docs/DISCREPANCIES.md](docs/DISCREPANCIES.md).

## Licence

Apache License 2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
