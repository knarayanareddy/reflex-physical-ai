# Architecture & Dataflow — Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI

```mermaid
flowchart TD
    Input["Input (URL / Photo / Demand Query)"] --> S1["Stage 1: Ingestion & Extraction (Nemotron Nano)"]
    S1 --> S2["Stage 2: Deterministic Schema Validation"]
    S2 --> S3["Stage 3: Deep Reasoning (Nemotron Ultra)"]
    S3 --> S4["Stage 4: Tri-State Deterministic Gate"]
    
    subgraph Gate ["Deterministic Security & Integrity Gate"]
        S4 -->|Pass| V_Pass["PASS: Output Actionable Artifact"]
        S4 -->|Violation| V_Fail["FAIL: Detailed Blocking Report"]
        S4 -->|Insufficient Info| V_Undet["UNDETERMINED: Human Inspection"]
    end
    
    V_Pass --> S5["Stage 5: Token Factory Sandbox Verification (Network Disabled)"]
    S5 --> Ledger["Append to runs/ledger.jsonl (Tokens, Latency, Cost)"]
```

---

## Key Subsystems

1. **Deterministic Gate (`backend/app/gate/`):**
   - Pure Python / zero-LLM decision logic.
   - Evaluates outputs strictly against frozen rule tables (`data/`).
   - If statutory citations, geometric metrics, or coordinates cannot be anchored to raw input spans, the output is dropped.

2. **Isolated Sandbox Verification (`backend/app/sandbox/`):**
   - Generated compliance reports and artifacts are compiled and hash-verified inside Nebius Token Factory Sandboxes.
   - Guest networking is disabled to mathematically guarantee no external data leakage.

3. **Instrumentation & Telemetry Ledger (`backend/app/tf/ledger.py`):**
   - Records granular token metrics (prompt, completion, cached token hits), latency, model ID, and estimated dollar costs per stage.
   - Computes counterfactual cost comparisons against single-model baselines.
