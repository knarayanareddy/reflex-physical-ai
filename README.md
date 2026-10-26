# Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI

> **Cloud planner proposes robotic actions. A local, network-free, deterministic envelope holds hard veto
> authority. Every refusal is written down, and every refusal is replayed in simulation to show what it
> prevented.**

[![CI](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Track](https://img.shields.io/badge/Track-Physical-green.svg)](docs/SUBMISSION-CHECKLIST.md)

**Target:** Nebius × NVIDIA Global AI Hackathon — Physical AI track.

---

## ⚠️ Build status — read this before the quickstart

This repository is at **Phase 2 of 5**: the contracts and the deterministic envelope exist and are
tested; the planner, the dashboard and the hardware rig **do not**. The honest summary:

| Component | Status | Evidence |
|---|---|---|
| Frozen contracts (`schemas/`, `data/veto-taxonomy.json`) | **Done** | `make schema`, `make taxonomy` |
| Contract laws as executable tests | **Done** | `backend/tests/test_schema_laws.py` |
| Config, telemetry ledger, HTTP provenance surface | **Done** | `backend/app/`, `make demo` |
| Deterministic envelope V1–V10 | **Done (synthetic parameters)** | `make verify-envelope`: purity, 500-snapshot determinism, 20 fixtures |
| Calibration profile for the rig | **Placeholder** | `data/calibration/rig-limits.json` — every value is synthetic, which forces `mode=simulation` |
| Two-arm replay (local) | **Done** | `make replay` → 34 contract-valid `ReplayResult` records, 3 geometric counterfactuals |
| Replay as a Nebius Serverless Job | **Not started** | the job runner is local; the arithmetic is the same |
| Cloud planner / Cosmos Reason perception | **Not started** | no client exists |
| Dashboard | **Not started** | `frontend/` is a design-token file |
| Hardware rig, interlock, measured veto-to-stop | **Not started** | no wiring, no measurement |

Everything below is written to describe what this repository is *for* and what it *will* prove. Where a
capability does not exist yet, it says so. The full engineering review — including every defect found and
the fix plan — is in [`REVIEW.md`](REVIEW.md); corrections of earlier documentation errors are logged in
[`docs/DISCREPANCIES.md`](docs/DISCREPANCIES.md).

---

## ⚡ Try it in two minutes (no API key, no hardware)

```bash
git clone https://github.com/knarayanareddy/reflex-physical-ai.git
cd reflex-physical-ai

make check     # lint + types + contract laws + taxonomy + tests  (~1 min on a laptop)
make demo      # serves the API on :8000; then curl localhost:8000/health
```

`make check` needs [uv](https://docs.astral.sh/uv/) and Python 3.11+. It installs into `backend/.venv`.

| Command | Needs a key? | What it actually does today |
|---|:---:|---|
| `make sample` | No | Runs the contract and ledger fixture tests offline |
| `make check` | No | Everything CI runs: ruff, mypy, `$ref` resolution, every schema law, taxonomy strictness, pytest |
| `make demo` | No | Serves `/health` and `/v1/info` on :8000 (reports the contract version, the taxonomy digest and pinned model IDs) |
| `make verify-envelope` | No | Purity (no `httpx`/`openai`/`socket` import in the decision path), 500-snapshot determinism, 20 rule fixtures, calibration invariants |
| `make replay` | No | Replays the fixture corpus through both arms and writes `ReplayResult` records to `runs/replay/` |
| `make params` | No | Prints every normal→degraded value and fails if any degraded value is less conservative |
| `make batch` | No | Runs the 1,000-action synthetic session through the envelope and both replay arms; writes `runs/headline_statistics.json` and a verifiable pack in `runs/replay_pack/`. Local process; the Nebius Serverless runner is still Phase C |

With a key (only needed once the planner exists):

```bash
cp .env.example .env      # add NEBIUS_API_KEY
```

---

## 🎯 The problem

**Persona — Kai, 29.** A robotics integrator deploying a small pick-and-place or dispensing cell for a
client. She has a model that plans motions. She has an e-stop. She has **no auditable middle layer**: no
record of near-misses, and no way to show a client or an insurer that the safety logic is deterministic and
cannot be talked out of a decision by a prompt.

**The pain, in her words:**

> *"I can get a model to plan a robot's next action in two seconds. I cannot get anyone to tell me, after
> the fact, what it wanted to do that I stopped it from doing — or prove that the thing which stopped it
> can't be talked out of it."*

**The 30-second hook.** Split screen, real hardware. Left: a servo-driven pusher, a block, a taped
keep-out volume, a relay module. Right: a terminal streaming the planner's intended action, the envelope's
decision and the actuator's state. The planner proposes a push; a second object enters the keep-out
volume; the envelope vetoes within a frame; the actuator stops, the relay clicks, a line lands in the veto
ledger. Cut to the replay: the same vetoed action re-run with the envelope **off** collides, with it **on**
it does not. On screen: *"1,240 actions planned · 37 vetoed · 37 simulated · 0 collisions shipped."*

---

## 🧠 The three insights this project is built on

1. **Veto authority must be local and non-negotiable.** A safety check that needs a network round-trip has
   a network-shaped failure mode and a latency floor — and a model can be *persuaded*. The envelope is
   pure deterministic code with **no LLM or HTTP client in its import graph**, holding a hardware interlock
   (a relay in the actuator's power path, not a software flag). A CI test walks the import graph and fails
   the build otherwise (`make verify-envelope`).
2. **The valuable artifact is the veto ledger, not the successful action.** Every physical-AI demo shows
   the robot doing the thing. Almost none shows what the system *refused* to do. A record of every refusal —
   sensor state, firing rule, intended action, full rule trace, and a simulation of what would have
   happened — is what an auditor, a client or an insurer actually asks for.
3. **Edge and cloud do different jobs, and the split is a safety property, not a cost optimisation.**
   The cloud proposes. The edge decides. Making that split load-bearing for *safety* is the architectural
   claim, and the network-outage test proves it: cut the network and the rig keeps operating under
   **stricter** degraded parameters. It does not fail open.

---

## 🏗️ What is actually here

```
├── REVIEW.md                     <- end-to-end engineering review: findings, evidence, fix plan
├── SPEC.md                       <- full engineering specification and 40 tickets (the plan)
├── ARCHITECTURE.md               <- target dataflow + what exists today
├── LIMITATIONS.md                <- what does not work, with numbers
├── schemas/core-schemas.json     <- frozen contracts; every stated law has a test
├── data/veto-taxonomy.json       <- the 10 veto rules, both parameter sets, rationales
├── scripts/validate_schema.py    <- meta-validation, $ref resolution, rule conformance
├── scripts/validate_taxonomy.py  <- structure, priority total order, degraded-mode strictness
├── data/calibration/rig-limits.json <- parameter values + provenance (synthetic today)
├── data/fixtures/snapshots/       <- 20 cases: each rule's trigger and its near miss
├── backend/app/
│   ├── config.py                 <- settings from env / .env (no fake key defaults)
│   ├── main.py                   <- /health, /v1/info, /v1/envelope/{info,evaluate}
│   ├── storage.py                <- fsync'd append-only JSONL, shared by both ledgers
│   ├── contracts.py              <- jsonschema boundary validation (kept OUT of the envelope)
│   ├── decision_ledger.py        <- the veto ledger: one EnvelopeDecision per evaluation
│   ├── replay.py                 <- two-arm swept-volume replay
│   ├── version.py                <- contract + taxonomy provenance
│   ├── tf/ledger.py              <- append-only telemetry, validated, fsync'd
│   ├── gate/gate.py              <- evidence-quote checker (NOT the envelope)
│   └── envelope/                 <- the deterministic V1-V10 envelope (stdlib only)
├── backend/tests/                <- 254 tests: schema laws, envelope, replay, ledger, app, gate
├── frontend/src/tokens.css       <- design tokens only; no application yet
├── jobs/replay_all.py            <- local replay lane, writes contract-valid ReplayResults
└── jobs/Dockerfile               <- API image, non-root, lockfile-frozen
```

---

## 🧪 How this maps to the four judging criteria

| Criterion (25% each) | What this submission will show | Where to look |
|---|---|---|
| **Technological Implementation** | A pure, network-free V1–V10 envelope with a content-addressed audit trail; a 500-snapshot determinism proof and an import-graph purity test; two-arm replay of every veto; a small NVIDIA model on the edge and Nemotron Ultra in the cloud (planned); a cost/latency ledger | `backend/app/envelope/`, `backend/tests/test_envelope_*.py`, `jobs/`, `runs/` |
| **Design** | A split-screen operator view where the verdict and the safe action are above the fold and the evidence collapses underneath; VETO / CLAMP / ALLOW distinguishable in greyscale and under deuteranopia, with text labels | `frontend/src/tokens.css`, later `frontend/src/` |
| **Potential Impact** | An auditable safety layer for small integrators; the veto-ledger format documented as reusable; ≥1 real practitioner conversation | `docs/`, `LIMITATIONS.md` |
| **Quality of the Idea** | Three named insights; abstention as a first-class outcome; the no-LLM-import test; a fail-safe network test that is filmable | `backend/tests/`, this README |

**Honest scoring position:** technological implementation is now **strong on the safety layer** — the
envelope is pure, deterministic, contract-checked and replayable — and still **weak on the product**: no
planner, no dashboard, no measured rig, and every limit in the calibration file is a placeholder, which is
why every decision is stamped `mode=simulation`. The criteria are equally weighted, and a repo whose README overclaims loses credibility with a
panel that has said on the record that it rewards candour about what is unfinished
(see [`docs/JUDGING-RUBRIC.md`](docs/JUDGING-RUBRIC.md)).

---

## 🛡️ Licence

Apache License 2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
