# Architectural Decision Record — Reflex

Decisions that change the contract, the architecture or the claim. Newest last.
A decision is recorded when it is made, not when it is finished. If a ticket is
parked or killed, it is recorded here with the reason.

| Date | Decision | Rationale | Alternatives considered | Owner |
|---|---|---|---|---|
| 2026-10-26 | Repo bootstrap & contract freeze (D-T09) | Phase 0 launch: one schema shared by edge and cloud, frozen before implementation so the envelope and the ledger cannot drift | Hand-maintained Python models per component (rejected: two sources of truth) | Lead |
| 2026-10-26 | Repo layout is `backend/app` + `frontend/`, not the `edge/ cloud/ sim/` tree in `SPEC.md` §7 | Keep one importable package and one test runner for a four-day build; the layout in the SPEC predates the scaffold. `SPEC.md` §7 is the authoritative *target* for Phase B (the envelope moves to `backend/app/envelope/`) | Renaming to the SPEC tree now (rejected: churn with no behavioural gain) | Lead |
| 2026-10-26 | Contract repaired rather than re-frozen: VETO `shipped_action` branch fixed, `ALLOW_CLAMPED` clamp made mandatory, local `LedgerLine` definition replaces a dangling cross-project `$ref` | The frozen contract rejected its own canonical VETO record and left two of its own laws unenforced; the `schema_version` stays `1.0.0` because no implemented consumer existed yet | Version-bump to 1.1.0 (rejected: there are no consumers to migrate) | Lead |
| 2026-10-26 | `Citation` removed from the contract | It was an unused `$ref` into another project's schema; nothing referenced it | Defining a local `Citation` (rejected: no requirement in SPEC §4) | Lead |
| 2026-10-26 | Rule schema gains `degraded_strictness_exemption` | Some rules are binary and already at maximum conservatism (V1); the strictness law needs a way to say so *with a reason* rather than silently exempting them | Allowing equal values everywhere (rejected: destroys the insight #3 test) | Lead |
| 2026-10-26 | `sensor_staleness_ms: 0` means "not applicable", and such a rule must not declare `requires_sensors` | V9 validates a proposal and needs no sensor; V7 computes freshness from the snapshot's own `age_ms`, so a second window would double-count | Forcing a non-zero value on both rules (rejected: invents a number with no meaning) | Lead |
| 2026-10-26 | Telemetry ledger path is explicit (`REFLEX_LEDGER_PATH`), not derived from `__file__` | The derived path silently resolved into `site-packages`/`/app` depending on install mode; the audit record must not move | Keeping the derived path (rejected: unreproducible across deployments) | Lead |
| 2026-10-26 | `NEBIUS_API_KEY` no longer defaults to `"mock-key"` | A missing key must be visible at startup, not at the first model call | Keeping a fake default (rejected: misconfiguration hides behind a green health check) | Lead |
| — | **D-T01 hardware go/no-go: NOT YET RECORDED** | The SPEC makes this the project's decisive gate (tier, parts bill, photo, first actuator movement). It cannot be inferred from code and must not be filled in on someone else's behalf | — | Human (unassigned) |
