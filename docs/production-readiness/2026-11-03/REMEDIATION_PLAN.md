# reflex-physical-ai — remediation plan

All steps below are future work, not executed. Preserve the synthetic-only boundary; no hardware connection or actuation is authorized by this review. Named paths exist in the snapshot unless marked proposed.

## Phase 0 — baseline and safety scope

Entry: pinned prototype and F01–F07. Exit: reproducible baseline and a written no-motion safety boundary.

### T01 — Baseline and rig-specific safety case (F01; prerequisite for all physical work)

Prerequisites: owner, qualified safety engineer, intended deployment and rig selection. Paths: `README.md`, `backend/app/envelope/core.py`, `backend/app/envelope/rules.py`, `data/calibration/rig-limits.json`.
1. Record baseline SHA, existing CI results, fixtures and the split between synthetic geometry and real-world claims; review calibration provenance without treating placeholder values as measurements.
2. Map proposed sensor-to-controller paths, every bypass, independent stop circuitry, power-loss behavior and human supervision; record unknowns as blockers.
3. Define named perception inputs, detectable classes, false-negative/latency requirements and measured rig limits; require model outputs to remain advisory, never the authority for motion.

Deliverable: reviewed hazard analysis, safety boundary and synthetic baseline. Verification: independent engineer reviews simulated stale/unknown sensor, lost network and bypass cases against documented expected outcomes; any physical trials need separate authorization and a qualified supervised protocol.
- [ ] Synthetic results and perception limitations cannot be presented as real-world validation.
- [ ] Owner approves safety responsibilities and no-motion boundary.

## Phase 1 — correctness, security and automation

Entry: T01 baseline. Exit: independent negative tests protect the agreed boundaries.

### T02 — Ingress and readiness (F02, F03; preventive security)

Prerequisites: T01, owner-approved network topology and identity model. Paths: `backend/app/main.py`, `backend/tests/test_app.py`, `jobs/Dockerfile`.
1. Choose private binding/ingress and separate authenticated evaluation, replay and operator permissions; document any upstream controls.
2. Keep liveness separate from proposed readiness; verify ruleset and ledger availability without suggesting readiness grants physical authority.
3. Add boundary tests for unauthorized and cross-role calls, malformed/model-injected proposals, missing calibration and failed ledger writes; review error redaction and resource limits.

Deliverable: boundary policy, implementation and regression suite. Verification: independent requests exercise the actual ingress; deliberately remove authentication or falsify readiness and confirm corresponding negative tests fail.
- [ ] Unauthorized callers cannot evaluate or access restricted telemetry.
- [ ] Unavailable dependencies cannot be mistaken for readiness or permission to move.

### T03 — Replay completeness and provenance (F05, F07)

Prerequisites: T01 and owner decision on verified versus arbitrary replay. Paths: `backend/app/envelope/__main__.py`, `backend/app/main.py`, `backend/app/decision_ledger.py`, `backend/tests/test_replay.py`.
1. Define explicit outcomes for empty, skipped, stale, mismatched and fully replayed records; distinguish strict verification from an explicitly partial diagnostic mode.
2. Design provenance binding among stored decision, rule/calibration version and replay, or label caller-supplied records unverified simulation.
3. Add independent fixtures for zero replayed, missing inputs, stale versions, modified decision, missing ledger entry and write failure; preserve valid synthetic replay.

Deliverable: completeness contract and regression tests. Verification: deliberately restore the current success-on-skips behavior and show the strict negative test fails; independently compare stored and returned provenance.
- [ ] Strict verification reports incomplete and zero-record inputs as non-success.
- [ ] Arbitrary simulation is not represented as verified ledger evidence.

### T04 — Perception and UI claims (F06; preventive)

Prerequisites: T01 and T03. Paths: `frontend/src/App.tsx`, `frontend/src/main.tsx`, `backend/app/envelope/rules.py`.
1. Trace every rendered outcome and replay label; replace unobserved actuator assertions with simulation/decision wording.
2. Define unavailable, unknown and stale perception as distinct from a verified clear signal; do not infer recognition from supplied boolean flags or a model-returned box.
3. Exercise the served dashboard with keyboard and screen reader, narrow viewports, contrast checks, missing data and both recorded and live API modes.

Deliverable: capability wording and accessible status behavior. Verification: inspect the built version in a browser; deliberately remove a simulated-state label and confirm the UI regression test detects it.
- [ ] No rendered outcome claims an observed physical stop without evidence.
- [ ] Veto and unavailable states are conveyed without color alone.

## Phase 2 — deployment, recovery and independent acceptance

Entry: T02–T04 complete. Exit: reproducible release and observed recovery, still simulation-only unless separately authorized.

### T05 — Release, data protection and recovery (F04; preventive)

Prerequisites: T02–T04, owner-approved platform, credentials and retention policy. Paths: `jobs/Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/deploy-pages.yml`, `backend/app/decision_ledger.py`.
1. Verify and pin base-image digest and workflow actions, review locked dependencies and define artifact provenance; do not weaken existing gates.
2. Classify inline sensor records, apply least-privilege access, retention and secret-redaction rules, and specify protected backup storage and separate credentials.
3. In an approved non-motion environment, deploy a versioned artifact, restore a backup and compare records and versions; perform and observe rollback to the previous artifact.

Deliverable: release manifest, restore evidence and rollback record. Verification: independently inspect deployed artifact/version, restored records and rollback; test missing, tampered and unauthorized backup access.
- [ ] Recovery is observed rather than inferred from backup creation.
- [ ] Deployment, data retention and rollback are owner-approved.

## Dependencies and acceptance

| Task | Requires | Output gate |
|---|---|---|
| T01 | Owner and safety engineer | Baseline and no-motion scope |
| T02, T03 | T01 and respective owner decisions | Boundary and replay regressions |
| T04 | T01, T03 | Honest accessible UI |
| T05 | T02, T03, T04 | Release and observed restore |

- [ ] Independent reviewer checks actual negative-test failures, not only passing counts.
- [ ] Security, evidence provenance and synthetic labels are reviewed against the deployed artifact.
- [ ] Release is reversible, and any physical testing or change of safety boundary has separate owner and qualified safety approval.

Rollback means restoring the last approved artifact and configuration, then verifying its identity and service behavior; never roll back physical safeguards or weaken thresholds to restore service. CI success alone is not certification or permission to actuate.
