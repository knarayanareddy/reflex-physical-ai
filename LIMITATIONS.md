# Limitations & Honest Failure Modes — Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI

> **Read this before relying on any output from this repository.**
>
> This project is designed around **honesty about its own operating boundaries**. In mission-critical workflows, knowing when a system cannot make a determination is more valuable than a confident hallucination.

---

## 1. Explicit Disclaimers: What This Is NOT
- **Not a Legal Authority or Certification Body:** Outputs represent automated pre-flight evaluations based on public datasets at a specific timestamp; they do not constitute formal legal counsel, regulatory approval, or certified safety compliance.
- **No Trademark Affiliation:** All references to official statutes, regulatory agencies, or industry standards are for descriptive alignment only.
- **Not Fail-Safe Without Human Oversight:** High-stakes verdicts require review by qualified human specialists.

---

## 2. Boundary & Coverage Matrix

| Domain Dimension | Supported / Evaluated | Currently Out of Scope |
|---|---|---|
| **Input Modality** | High-resolution structured digital inputs & standard image formats | Corrupted, occluded, or uncalibrated inputs |
| **Data Recency** | Grounded in current frozen rule tables & live Tavily verification | Jurisdictions or rules not yet codified in the registry |
| **Autonomous Action** | Advisory alerts, compliance packs, and safety vetoes | Direct unmonitored legal filing or physical actuation |

---

## 3. Real-World Failure Modes & Mitigations

| # | Known Failure Mode | Underlying Root Cause | Architectural Mitigation |
|---|---|---|---|
| 1 | **Ambiguous or Thin Evidence** | Input text or image lacks requisite metadata | The gate outputs `UNDETERMINED` instead of guessing |
| 2 | **Upstream Format Drift** | Marketplace or regulatory portal changes HTML/DOM | System falls back to cached golden fixtures and alerts operator |
| 3 | **Out-of-Vocabulary Assertion** | Model emits a condition or clause not in the frozen table | Gate validator drops ungrounded assertion with a logged warning |
| 4 | **Network Disruption** | Cloud endpoint latency or rate limit | Token Factory Sandbox operates offline with network disabled |
