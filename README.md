# Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI

> **Cloud VLM proposes robotic actions; an on-device local model and deterministic envelope hold hard veto authority over keep-out volumes and force limits; every veto is replayed in Nebius Serverless simulation as an auditable counterfactual.**
>
> **Headline impact:** `4% of field in Physical AI · 10 deterministic veto rules · 0 unmonitored actuators`

[![CI](https://github.com/knarayanareddy/reflex-physical-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/knarayanareddy/reflex-physical-ai/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Track](https://img.shields.io/badge/Track-Physical-green.svg)](docs/SUBMISSION-CHECKLIST.md)

**Target Award:** Nebius × NVIDIA Global AI Hackathon — Physical AI

---

## ⚡ Try it in 5 minutes (No API key needed)

```bash
git clone https://github.com/knarayanareddy/reflex-physical-ai.git
cd reflex-physical-ai

# 1. Run offline verification against cached fixtures (no key, no cost, deterministic)
make sample

# 2. Run full test suite & schema check
make check
```

With a Nebius Token Factory API key:
```bash
export NEBIUS_API_KEY="your-token-factory-key"
export TAVILY_API_KEY="your-tavily-key"   # optional / bonus track
make demo
```

| Command | Needs Key? | What it proves |
|---|:---:|---|
| `make sample` | No | Full end-to-end pipeline operates offline against golden fixtures |
| `make check` | No | Code quality, Pydantic/JSON schema integrity, and gate rules pass |
| `make demo` | Yes | Real-time inference through Nebius Token Factory and deterministic gate |
| `make batch` | Yes | Nebius Serverless Job batch processing for empirical evaluation study |

---

## 🎯 The Problem & The Persona

### Persona
**Autonomous robotics developer deploying manipulators in human-collaborative spaces. Needs VLM task generalization without risking human injury or mechanical collisions.**

### The Pain
Users cannot afford probabilistic LLM hallucinations or opaque compliance rejections. In critical decision paths, an AI tool must provide **citable evidence, hard deterministic safety/compliance gates, and formal abstention (`UNDETERMINED`)** when confidence is low.

---

## 🧠 The Four Judging Criteria Addressed

### 1. Technological Implementation (25%)
- **Multi-Tiered Model Routing:**
  - `nvidia/Nemotron-3-Ultra-550b-a55b`: Deep reasoning, legal/standard applicability, complex arbitration.
  - `nvidia/nemotron-3-super-120b-a12b`: Intermediate high-throughput semantic evaluation.
  - `nvidia/nemotron-3-nano`: Low-latency deterministic structured extraction.
- **Nebius Token Factory Sandboxes:**
  - Artifacts are verified inside isolated containers with **guest networking disabled** to prove zero data exfiltration and zero reliance on ungrounded web lookups.
  - Sandbox **branching** is utilized to perform A/B counterfactual evaluation (gate-on vs gate-off).
- **Cost & Latency Ledger:** Every request appends to `runs/ledger.jsonl`, documenting exact prompt tokens, completion tokens, cached token savings, and execution latency.

### 2. Design (25%)
- **Immediate Value (< 30s to Aha):** High-priority verdict and action buttons displayed above the fold; supporting regulatory or telemetry evidence collapsed below.
- **Custom Design System:** Built on custom design tokens in `frontend/src/tokens.css` (no stock purple-gradient AI themes).
- **Accessibility & Control:** Full keyboard navigation, ARIA semantics, and explicit progress states with cancel/stop controls.

### 3. Potential Impact (25%)
- **Original Empirical Research:** Running a batch study over real-world data (via Nebius Serverless Jobs) to publish concrete aggregate statistics.
- **Customer Grounded:** Designed to address verified industry bottlenecks (e.g. 560 regulatory marketplace delisting orders, 20–30% electronics rework costs, or grid queue delays).

### 4. Quality of the Idea (25%)
- **Non-Obvious Domain Insight:** Addresses systemic problems rather than building a generic LLM wrapper.
- **Tri-State Deterministic Gating:** Employs code-level invariants (`PASS`, `FAIL`, `UNDETERMINED`). If an assertion lacks verbatim source support, the gate automatically downgrades to `UNDETERMINED`.

---

## 📁 Repository Layout

```
├── LICENSE                         <- Apache 2.0 open-source licence
├── README.md                       <- Project overview & judging evidence
├── LIMITATIONS.md                  <- Honest failure modes & coverage boundaries
├── ARCHITECTURE.md                 <- System dataflow & gate mechanics
├── SPEC.md                         <- Comprehensive engineering specification & tickets
├── Makefile                        <- Standard command targets (sample, check, demo)
├── schemas/
│   └── core-schemas.json           <- Frozen JSON schema contracts
├── data/                           <- Rule tables, taxonomies, and fixtures
├── docs/                           <- Protocols, rubric walkthrough, platform guide
│   ├── AGENT-DELEGATION-PROTOCOL.md
│   ├── JUDGING-RUBRIC.md
│   └── PLATFORM-CAPABILITIES.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                 <- FastAPI application
│   │   ├── tf/                     <- Token Factory client & telemetry ledger
│   │   └── gate/                   <- Deterministic tri-state gate
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/tokens.css              <- Custom design system
├── jobs/                           <- Serverless batch jobs
└── runs/
    └── sample_ledger.jsonl         <- Instrumentation ledger
```

---

## 🛡️ License
Distributed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.
