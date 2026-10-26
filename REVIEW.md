# End-to-End Repository Review — `reflex-physical-ai`

**Reviewed:** 2026-10-26 · branch `arena/1c486180-reflex-physical-ai` @ `ebb0847` (single commit on `main`)
**Scope:** every tracked file (39), all documented commands, the JSON contracts, the Python package, the frontend package, deployment manifests, CI, and doc/claim accuracy.
**Method:** static reading + **actually executing** the documented workflows (`make sample`, `make check`, `make demo`, `uv build`, `uv lock --check`, `pip install`, `npm install/build/dev`, schema validation of real instances, ledger/gate exercises). Nothing was taken on trust from the docs. A full command log is in [§11](#11-verification-log).
**Changes made by this review:** this file, plus the Phase A remediation below (see §10).

---

## 0. Remediation status

**Phase A applied on 2026-10-26** (commit "Phase A: unblock the build, enforce the contract, make CI real").
**Phase B applied on 2026-10-26**: the deterministic envelope, the calibration file, the fixture corpus and
the replay lane now exist and are tested (254 tests).
Findings are marked here so this document does not go stale: `fixed` = the defect is gone and a test guards
it; `partial` = the highest-risk half is addressed and the rest is ticketed; `open` = unchanged.

| ID | Status | What changed |
|---|---|---|
| R-01 import blocker | **fixed** | `app/__init__.py` rewritten; `tests/test_app.py` and a CI smoke step now import the app |
| R-02 schema rejects its own VETO | **fixed** | `type: object` + `required: [is_noop]` on the no-op branch; `ALLOW_CLAMPED` must carry a before/after; every stated law is an executable fixture (`tests/test_schema_laws.py`) |
| R-03 foreign `$ref`s | **fixed** | Local `LedgerLine`; unused `Citation` removed; `tests/test_schema_meta.py` fails on any non-local `$ref` |
| R-04 demo path does not exist | **fixed** | README rewritten against measured behaviour; `make batch` row removed; `make sample`/`check`/`demo` now do what they say |
| R-05 licence not detected | **fixed** | Canonical Apache-2.0 (sections 1–9 + appendix) restored; `NOTICE` added; `License-Expression: Apache-2.0` in wheel metadata (GitHub should now detect it) |
| R-06 three state vocabularies | **partial** | The envelope's trace vocabulary is now a subset of the contract's (`DEGRADE` was added to `EnvelopeDecision.rule_trace[].result`, which could not previously record a degradation). The gate's `PASS`/`FAIL`/`UNDETERMINED` still differs and is Phase C |
| R-07 gate is not a gate | **open** | Characterised in `tests/test_gate.py` with three `xfail(strict=True)` tests that will fail once fixed |
| R-08 taxonomy unexecutable | **fixed** | The envelope reads values only from `data/calibration/rig-limits.json`; `check_param_provenance.py`, `diff_parameter_sets.py` and `make_fixtures.py` all exist and run in CI; 20 fixtures replace the 10 that were named but absent. The `TODO_MEASURE` text stays in the taxonomy as a visible contract placeholder, and the loader never reads it |
| R-09 degraded not stricter | **fixed** | `V1` declares a justified exemption; `V8.window_ms` is 1000 vs 2000; the validator enforces a declared direction for every parameter and rejects wrong-way multipliers |
| R-10 ledger sample not JSON | **fixed** | Valid, schema-checked, marked SYNTHETIC; `LedgerLine` now local and enforced |
| R-11 ledger path | **fixed** | `REFLEX_LEDGER_PATH` / settings, never derived from `__file__`; fsync'd append; `id` on every line; tests cover both |
| R-12 `.env` ignored | **fixed** | `SettingsConfigDict(env_file=…)`; `mock-key` default removed; `.env.example` matches `Settings` |
| R-13 Dockerfile | **partial** | Rewritten: root-context build, `uv sync --frozen`, non-root user, healthcheck, volume for the ledger. Not built — no Docker in this environment, and the base image is tag-pinned, not digest-pinned |
| R-14 pyproject incomplete | **fixed** | `build-system`, `license = "Apache-2.0"`, explicit packages, ruff/mypy config, `backend/README.md` |
| R-15 fake Makefile targets | **fixed** | `lint`/`format`/`typecheck`/`schema`/`taxonomy` are real; `verify-envelope` now runs the purity, determinism, rule, calibration, fixture and replay suites, plus `python -m app.envelope verify`; `make replay` and `make params` added |
| R-16 frontend unbuildable | **open** | Phase C; stated plainly in the README status table |
| R-17 zero CI | **fixed** | `.github/workflows/ci.yml` runs lint, types, contracts, taxonomy, tests and an app smoke test |
| R-18 placebo tests | **fixed** | 254 tests (251 passing, 3 expected failures) replacing the single vacuous assertion; the new envelope suites include a test that proves the purity checker catches violations |
| R-19 prose assertions | **fixed** | Assertion list is executed, and a coverage test fails if a stated assertion has no fixture |
| R-20 cross-project residue | **partial** | README, LIMITATIONS, ARCHITECTURE and the video script rewritten for the physical-AI domain; `docs/AGENT-DELEGATION-PROTOCOL.md` (A-T07 example), `docs/templates/*` and `data/competitor-subset.csv` still carry it |
| R-21 two layouts | **partial** | `docs/DECISIONS.md` records `backend/` + `frontend/` as the layout and `backend/app/envelope/` as the Phase B home; `SPEC.md` §7 is unchanged |
| R-22 dates | **partial** | Deadline corrected to 18:00 CET; `SPEC.md` day-of-week errors remain |
| R-23 no recorded decisions | **fixed** | `docs/DECISIONS.md` has real entries and records D-T01 as **not recorded** rather than inventing one |
| R-24 dependency padding | **partial** | `duckdb`, `jinja2`, `markupsafe` removed and `uv.lock` regenerated (46 packages); `openai`/`httpx` are kept for the Phase B planner |

**Still true after Phase B:** there is no planner, no dashboard, no hardware and no measured number. The
envelope is real and tested, but every limit it enforces is a placeholder, which is why it stamps
`mode=simulation` on every decision. The replay lane runs locally, not as a Nebius Serverless Job, and its
simulator is a 2-D swept volume that cannot see force, staleness or trust. The project remains roughly
18–30 engineering hours from its own claims. Nothing in this file should be read as saying otherwise.

---

## 1. Verdict

> **This is a Phase-0/Phase-1 scaffold with an excellent specification sitting on top of ~106 lines of stub code.** The planning artifacts are unusually strong; the product they describe does not exist yet, and the README markets it as though it does.

| Dimension | Grade | One-line reason |
|---|---|---|
| Specification & strategy docs (`SPEC.md`, `docs/`, top-level docs) | **A−** | 3,053 lines of genuinely sharp, judge-aware planning (incl. `README`/`ARCHITECTURE`/`LIMITATIONS`; 3,065 with `video/script.md`). Dated and partly cross-project-contaminated, but the thinking is good. |
| Contract design (`schemas/core-schemas.json`, `data/veto-taxonomy.json`) | **B−** | Thoughtful, law-bearing design — but the central object **rejects its own canonical VETO record**, two stated laws are unenforced, and two `$ref`s point into another project. |
| Backend implementation | **F** | 106 LOC of app code across 5 files (+ a 13-line test). The package **cannot be imported** (syntax error). 0 of 10 veto rules, no planner, no replay, no simulator, no ledger writer call site. |
| Test & CI | **F** | One 13-line test that asserts a dict has *some* key. **Zero GitHub workflows.** The CI badge is dead. Green CI is not evidence of a working app. |
| Frontend | **F** | Two files: `package.json` + a 21-line CSS token file. `npm run build` exits 1; `npm run dev` serves a blank page. |
| Packaging / deploy (`jobs/Dockerfile`, `pyproject.toml`) | **D−** | Wheel builds, but the entrypoint crashes; the ledger path resolves outside the repo when installed; image is unpinned, root, and installs without the lockfile. |
| Documentation accuracy (README/LIMITATIONS/ARCHITECTURE vs reality) | **F** | Every "what it proves" row in the README quickstart table is false today. Judges explicitly penalise this (see `docs/JUDGING-RUBRIC.md`). |
| Licensing / eligibility | **C** | Apache-2.0 text is incomplete (Section 9 missing) and GitHub reports the licence as `NOASSERTION`. |

**Bottom line.** The repo is honest *inside* `SPEC.md` ("this is the highest-variance play", "do not proceed until the hardware moves") and dishonest *in the README* ("Try it in 5 minutes", "make sample — full end-to-end pipeline operates offline"). If a judge followed the README tonight they would hit a `SyntaxError` in under a minute. That gap — not the missing features — is the top risk, because `docs/JUDGING-RUBRIC.md` records three judges saying that unbacked claims are the thing they penalise hardest.

If the project continues: **build the vertical slice** (deterministic envelope → decision object → ledger → two-arm replay → minimal UI) and *then* rewrite the README to match. If hardware is not on the bench tonight, the SPEC's own go/no-go gate applies (R1: switch ideas) — see [§10](#10-remediation-plan).

---

## 2. What is actually good (verified, not assumed)

These are real strengths and should survive the rewrite:

1. **The contract is designed like a safety system, not a demo.** `EnvelopeDecision` carries `rule_trace` (full evaluation trace, not just the firing rule), `envelope_version` (sha256 of taxonomy + source), `determinism_hash`, `intended_action` *and* `shipped_action`, `clamp_applied` before/after, `buffered_locally` for the offline case, and measured `veto_to_stop_latency_ms`/`distance_mm`. That is a genuinely good audit object.
2. **The ten-rule taxonomy is complete and structurally valid.** All 10 rules (`V1`–`V10`) validate against `$defs/Rule`; priorities are 1–10 with no gaps or duplicates; every rule lists both parameter sets, a rationale, a fixture name and a false-positive note.
3. **The schema is meta-valid and mostly does enforce its laws.** `Draft202012Validator.check_schema` passes. Tested against real instances, it correctly rejects: VETO with no `rule_id`; ALLOW with a firing rule or a clamp; a missing/zero `ttl_ms`; `keep_out_occupied=true` with null evidence; a rule with only one parameter set; `collisions_in_shipped > 0`; `envelope_off` replay with the collision field omitted. (Two holes remain — [§6](#6-contract-audit--which-laws-are-actually-enforced).)
4. **The competitive claim checks out.** `docs/COMPETITOR-LANDSCAPE.csv` has 833 rows, 34 of which are `physical-ai/robotics` → **4.08%**, matching the "4% of field" headline. This is one of the few numeric claims that survives verification.
5. **No secrets are committed.** A credential scan of all tracked files came back clean.
6. **The dependency lock is real.** `uv lock --check` resolves cleanly and `uv build` produces both sdist and wheel. The packaging skeleton is sane.
7. **The app logic itself is fine.** With `app/__init__.py` fixed in a scratch copy, FastAPI serves `/health`, `/v1/info` and `/docs` with 200s, and `mypy` is clean.

---

## 3. P0 — blocking (fix before anything else)

### R-01 · The Python package cannot be imported
`backend/app/__init__.py` is a single line containing a **literal backslash-n**, not a newline:

```
$ cat -A backend/app/__init__.py
"""App root package."""\n
$ python -c "import app"
SyntaxError: unexpected character after line continuation character
```

This is not cosmetic — it takes down everything downstream:

* `make demo` → `SyntaxError` (exit 2).
* `jobs/Dockerfile` `ENTRYPOINT ["python", "-m", "app.main"]` → same crash inside the image.
* `import app.gate.gate` / `app.tf.ledger` / `app.config` → same crash (submodules execute the package `__init__`).
* `pytest` still passes because the only test never imports the package. That is exactly the "green CI, broken app" failure mode.

**Fix:** write the file with a real newline. **Then add a test that imports `app.main`** so this cannot recur.

> The same literal-`\n` corruption appears in `docs/DECISIONS.md`, `docs/DISCREPANCIES.md` and `runs/sample_ledger.jsonl`. It looks like a generator/write bug, not a one-off.

### R-02 · The frozen contract rejects the canonical VETO decision
The `VETO` conditional in `schemas/core-schemas.json:97` constrains `shipped_action` with:

```json
"oneOf": [ {"type": "null"},
           {"properties": {"is_noop": {"const": true}}} ]
```

The second branch has **no `type: "object"`**, so a `null` instance matches it *vacuously*. `null` therefore matches **both** branches, and `oneOf` (exactly-one) fails:

```
Canonical VETO decision (shipped_action=null) valid? NO
  shipped_action -> None is valid under each of {'properties': {'is_noop': {'const': True}}}, {'type': 'null'}
```

Consequences, all confirmed by execution:

| Instance | Expected | Actual |
|---|---|---|
| `outcome=VETO, shipped_action=null` (the spec's own law) | valid | **rejected** |
| `outcome=VETO, shipped_action=<real action, no is_noop>` | rejected | **accepted** |
| `outcome=ALLOW_CLAMPED, clamp_applied=null` | rejected | **accepted** |
| `outcome=ALLOW_CLAMPED, clamp_applied=<object>` | valid | valid |

So the two headline safety laws — *"a VETO's shipped action is always a no-op"* and *"a clamp without a recorded before/after is invisible"* — are **not enforced**, while the normal representation is **unrepresentable**. Any implementation that validates its decisions will either crash on every veto or be forced to disable validation.

**Fix:** in the VETO branch use `{"type": "object", "required": ["is_noop"], "properties": {"is_noop": {"const": true}}}`; in the `ALLOW_CLAMPED` branch require `clamp_applied` non-null (`{"type": "object"}`) and `rule_id` present. Re-run the ten `integrity_assertions_that_must_fail_validation` in CI as executable fixtures, not as a JSON comment array.

### R-03 · Two `$ref`s point into a different project
`schemas/core-schemas.json:204-205`:

```json
"LedgerLine": {"$ref": "../../A-redflag-eu-product-safety/schemas/core-schemas.json#/$defs/LedgerLine"},
"Citation":   {"$ref": "../../A-redflag-eu-product-safety/schemas/core-schemas.json#/$defs/Citation"}
```

Both are **unresolvable** (`_WrappedReferencingError: Unresolvable`). The ledger line format is therefore undefined, which is why the committed ledger sample could drift without anyone noticing. **Fix:** inline local definitions (and delete the `Citation` type if nothing uses it).

### R-04 · The documented demo path does not exist
The README's "⚡ Try it in 5 minutes" block is the first thing a judge executes. Every row is wrong today:

| Documented | Reality (executed) |
|---|---|
| `make sample` → "Full end-to-end pipeline operates offline against golden fixtures" | Runs a single 13-line test that asserts `"$defs" in schema or "properties" in schema or "$schema" in schema`. No pipeline, no fixtures (`data/fixtures/` does not exist). |
| `make check` → "Code quality, Pydantic/JSON schema integrity, and gate rules pass" | Same single test. There are **no Pydantic models**, no lint step, no type check, no gate test. |
| `make demo` → "Real-time inference through Nebius Token Factory and deterministic gate" | `SyntaxError` before the server starts. There is no Token Factory client and no gate route. |
| `make batch` → "Nebius Serverless Job batch processing" | `make: *** No rule to make target 'batch'` |

The repository contains **0 of the 10 veto rules**, no envelope, no planner, no perception, no simulator, no replay, no dashboard and no ledger call site (`record_telemetry` is defined and never invoked; `data/veto-taxonomy.json` is never read by the code — verified by grep).

**Fix (either one, but choose deliberately):** build the vertical slice, *or* rewrite the README so that "what exists" and "what is planned" are separated, and remove the collapsing runner table. Given that `SPEC.md` says the whole project is a 4-day build starting today, the scaffold itself is defensible — the *marketing* is not.

### R-05 · The Apache-2.0 licence is incomplete and not detected
`LICENSE` stops at section 8: **Section 9 ("Accepting Warranty or Additional Liability") is missing**, and the canonical appendix is replaced by a hand-written `Copyright 2026 Nebius x NVIDIA Global AI Hackathon Team` line. GitHub reports:

```
license: NOASSERTION
```

`docs/SUBMISSION-CHECKLIST.md` explicitly requires an open-source licence visible at the top of the repo, and the README shows an Apache-2.0 badge that does not match what GitHub detects. **Fix:** restore the unmodified canonical Apache-2.0 text (sections 1–9 + appendix), keep the copyright line in `NOTICE`, and add `license = {text = "Apache-2.0"}` to `backend/pyproject.toml`.

---

## 4. P1 — high severity

### 4.1 Contracts & correctness

**R-06 · "Formal abstention (`UNDETERMINED`)" is not representable in the contract.**
The README headline claims *"Tri-State Deterministic Gating: `PASS`, `FAIL`, `UNDETERMINED`"*, and `LIMITATIONS.md` repeats it. But:

* `$defs/Outcome` = `["ALLOW", "ALLOW_CLAMPED", "VETO"]` — **no `UNDETERMINED`**;
* `rule_trace[].result` = `PASS | VETO | CLAMP | SKIPPED_MODE | SENSOR_MISSING | SENSOR_STALE` — a third vocabulary;
* `gate.py` returns `PASS | FAIL | UNDETERMINED` — a fourth.

Three incompatible state machines. The audit object cannot record the abstention the README sells as the differentiator. **Fix:** pick the schema's vocabulary as canonical (`Outcome`), map `UNDETERMINED` onto it explicitly (likely `VETO` + `rule_id` + a `SENSOR_MISSING` trace entry, or add a fourth outcome), and delete the other two vocabularies.

**R-07 · `gate.py` is not a gate.** `DeterministicGate.evaluate(rule_id, assertion, evidence_quote, raw_source)`:

* **ignores `assertion` entirely** — a call with `force_n=99999` returns `PASS` as long as the quote matches;
* never loads `data/veto-taxonomy.json`, so V1–V10, priorities, modes and parameter sets do not exist in code;
* returns `FAIL` when the quote is absent, while the README/LIMITATIONS promise it "downgrades to `UNDETERMINED`" — a direct doc/code contradiction;
* accepts a single space `" "` as a valid evidence quote if the source contains a space, and accepts a one-character quote (`"a"`) — trivially gameable grounding;
* is an *evidence-quote checker*, not a safety envelope; the name overpromises.

**R-08 · The taxonomy cannot be executed even if the gate existed.** Twelve parameters are the literal string `"TODO_MEASURE"` (e.g. `V3 max_velocity_mm_s`, `V5 boundary_margin_mm`, `V7 camera_max_age_ms`, `V6 swept_volume_inflation_mm`). `V1`'s two parameter sets are both `{}`. There is no `data/calibration/rig-limits.json` and no `scripts/` directory, so all four acceptance checks the taxonomy declares (`validate_taxonomy.py`, `check_param_provenance.py`, `diff_parameter_sets.py`) are unexecutable. The ten fixture files the taxonomy names (`data/fixtures/snapshots/veto_v*.json`) do not exist either, so even the promised positive/negative fixtures are absent.

**R-09 · The "degraded is strictly more conservative" invariant is already violated.** `_meta.integrity_warnings` and the SPEC both make strictness a law. Current values:

| Rule | Normal | Degraded | Stricter? |
|---|---|---|---|
| `V1_EMERGENCY_STOP` | `{}` | `{}` | No content at all |
| `V2_KEEP_OUT_OCCUPIED` | `detection_min_confidence: 0.0`, `consecutive_frames_required: 1` | `0.0`, `1` | **Identical** |
| `V8_NETWORK_DEGRADED` | `window_ms: 2000` | `window_ms: 2000` | **Identical** (a degraded network window should be *shorter*) |
| `V3/V4/V5/V6/V7/V9/V10` | numeric or `TODO_MEASURE` | strings like `"TODO_MEASURE × 0.4"` | Not machine-comparable |

**R-10 · `runs/sample_ledger.jsonl` is not JSON.** The file ends with a literal `\n` inside the line (`Extra data: line 1 column 326`), so any `json.loads` over the ledger raises. Its `stage` is `"extract_fields"` — a leftover from the *other* project's pipeline — and there is no `id` field in `record_telemetry`'s output to match the sample's `id`. `runs/veto-ledger.jsonl` (SPEC C1) vs `runs/ledger.jsonl` (README/ARCHITECTURE) naming is also unresolved.

### 4.2 Runtime, packaging & deploy

**R-11 · The ledger path is hardcoded relative to the source tree and is wrong when installed.**
`LEDGER_PATH = Path(__file__).resolve().parents[3] / "runs" / "ledger.jsonl"` resolves to `<repo>/runs/ledger.jsonl` in a `uv run` dev checkout, but to `…/lib/python3.11/runs/ledger.jsonl` when pip-installed (measured) and `/app/runs/ledger.jsonl` in the current Dockerfile — i.e. **the safety record lands in a different place in every deployment mode**, and in the wheel install it writes into the interpreter's library tree. For an audit-first product this is an architectural defect, not a detail. `record_telemetry` also has no `id`, no schema validation, no `fsync`/lock, no dedupe (the SPEC's ledger-durability test requires dedupe on double-ship) and no rotation.

**R-12 · `.env` is never read, and `.env.example` is half-fiction.** `config.py` defines fields as `str = os.getenv(...)` and never sets `model_config = SettingsConfigDict(env_file=…)`. Measured: with a `.env` containing `ENVIRONMENT=production` and running from `backend/`, the app reports `development | mock-key`; only exported environment variables take effect. Additionally `.env.example` documents `MODEL_VISION`, `LOG_LEVEL`, `SANDBOX_NETWORK_DISABLED` and `MOCK_EXTERNAL_CALLS`, none of which exists in `Settings` or anywhere else; the example file sits at the repo root while `make demo` runs in `backend/`. Defaulting `nebius_api_key` to `"mock-key"` also hides misconfiguration instead of failing fast.

**R-13 · `jobs/Dockerfile` is neither buildable-as-documented nor a job.**
`COPY backend/ /app/backend/` requires the **repo root** as build context while the file lives in `jobs/` (no build instructions anywhere). It then `pip install ./backend` — which ignores `uv.lock`, so the image is not reproducible — and the entrypoint starts a **web server**, not the replay/batch job the SPEC describes (`jobs/replay_all.py` does not exist). It also runs as root, uses an unpinned `python:3.12-slim`, has no `HEALTHCHECK`, no `PYTHONUNBUFFERED`, and there is no `.dockerignore`, so a root-context build would ship `backend/.venv` (hundreds of MB).

**R-14 · `backend/pyproject.toml` is under-specified.** `readme = "README.md"` points at `backend/README.md`, which does not exist; there is no `[build-system]`; no `license`; no `[tool.ruff]`/`[tool.mypy]` config; no package/exclude rules. `uv build` and `pip install` happen to succeed, but the metadata is wrong and the packaging behaviour is accidental (setuptools auto-discovery found `app/`).

**R-15 · The Makefile advertises targets it does not have.** `.PHONY` declares `lint` and `format` with no recipes, so `make lint` prints *"Nothing to be done"* and **exits 0** — a false green. `README` references `make batch`; `SPEC` references `make verify-envelope`, `make edge`, `make cloud` — none exist. `make check`'s help text promises lint/typecheck that it never runs.

**R-16 · The frontend cannot build or render.**

```
$ npm run build      # tsc && vite build
tsc: The TypeScript Compiler - Version 5.9.3   → exits 1 (no tsconfig.json)
$ npm run dev        # vite starts …
(!) Could not auto-determine entry point … and there are no explicit optimizeDeps.include patterns.
```

There is no `index.html`, no `vite.config.ts`, no `tsconfig.json`, no `src/main.tsx`, no `App.tsx`, no `tailwind.config.js`/`postcss.config.js` despite Tailwind being a dependency, and no lockfile. `tokens.css` (21 lines) is the entire "custom design system"; the README's claims of "full keyboard navigation, ARIA semantics, cancel/stop controls" and the SPEC's `ReplayCompare` hero component have no implementation.

### 4.3 Tests, CI & verification

**R-17 · There are zero CI workflows on GitHub, and the badge is dead.**
`.github/` does not exist; `gh api repos/knarayanareddy/reflex-physical-ai/actions/workflows` → `total_count: 0`. The CI template was parked at `docs/ci/github-ci.yml` (per the last commit message), so the README badge points at a workflow that has never run. Even if activated, the template only runs `uv run --extra dev pytest tests/ -v` — the single vacuous test — and does not run ruff, mypy, schema validation, `npm build`, or an app import smoke test. It also does not use `uv sync --frozen`, so it can silently rewrite the lock.

**R-18 · The test suite is a placebo.** `backend/tests/test_schemas.py` (13 lines):

```python
with open(schema_path) as f:
    schema = json.load(f)
assert "$defs" in schema or "properties" in schema or "$schema" in schema
print(f"Loaded schema with title: …")
```

It imports `jsonschema` and never uses it (ruff `F401`), never calls `check_schema`, never validates a fixture against any `$defs`, never exercises the gate, ledger or API, and prints instead of asserting. Every one of the SPEC's 18 verification layers is unaddressed: no purity test, no determinism test, no rule fixtures, no interlock test, no "model cannot clear a veto" test, no outage test, no replay test.

**R-19 · Wrong-answer risk in the schema's own test list.** `integrity_assertions_that_must_fail_validation` is a JSON array of prose, so nothing executes it — which is precisely how R-02 survived. Convert to fixtures and loop over them in pytest.

### 4.4 Documentation & process accuracy

**R-20 · The repo is visibly forked from a different project ("A-redflag-eu-product-safety").** Evidence: the two `$ref`s (R-03); `docs/AGENT-DELEGATION-PROTOCOL.md` dispatching `A-T07 / Extract Article 19 fields from a listing` against `ideas/A-redflag-eu-product-safety/...`; `docs/templates/*` marked "Used by A-T38 / B-T38 / C-T38 / D-T34"; legal-domain residue in `ARCHITECTURE.md` ("statutory citations"), `README.md` ("legal/standard applicability", "560 regulatory marketplace delisting orders"), and `LIMITATIONS.md` ("Not a Legal Authority", "marketplace or regulatory portal changes HTML/DOM", "Jurisdictions … not yet codified"). `data/competitor-subset.csv` duplicates 61 rows of `docs/COMPETITOR-LANDSCAPE.csv` with no stated selection rule. None of this is fatal, but it is the kind of thing a judge notices, and it makes the docs read as generic.

**R-21 · Two incompatible repository layouts.** `SPEC.md:370` specifies `edge/`, `cloud/`, `sim/`, `sandbox/`, `dashboard/`, `tests/`; the actual repo is `backend/app/…` + `frontend/`. Every one of the **40 tickets** references paths that do not exist (`edge/envelope/envelope.py`, `cloud/plan/ultra.py`, `sim/client.py`, `tests/test_envelope_purity.py`, `scripts/validate_taxonomy.py`, `data/calibration/rig-limits.json`, `docs/SAFETY-CASE.md`, `docs/SIMULATOR-CHOICE.md`, `docs/HARDWARE-BILL.md`, `docs/EVAL.md`, `docs/JUDGE-RUNBOOK.md`, `data/model-catalog.snapshot.json`, `jobs/replay_all.py`, `_shared/agent-delegation-protocol.md`, `../../judges_transcript.txt`). Consequences: an agent dispatched from the SPEC will create a parallel tree, and the SPEC's "Definition of Done" cannot be checked against the repo.

**R-22 · The dates and deadline are wrong.** 2026-10-26 is a **Monday**, yet the SPEC labels phase 0 "Sun 26 Oct", phase 3 "Tue 28 Oct" (a Wednesday), phase 4 "Wed 29 Oct" (a Thursday) and phase 5 "Thu 30 Oct 18:00" (Thursday is the 29th). The deadline statement is also wrong by an hour: `docs/SUBMISSION-CHECKLIST.md` says "Friday 30 October 2026, 10:00 am PT = 17:00 UTC = **19:00 CEST**", but EU summer time ends on 2026-10-25, so the Netherlands is on **CET** and 17:00 UTC = **18:00 CET**. (The stated Thu-29 18:00 target still leaves ~23 h of buffer, so this is a labelling risk, not a schedule risk.) `SPEC §14` says "submit by Thu 29 Oct" while `SPEC §8` says phase 5 ends Thu 30 Oct; one of them must go.

**R-23 · `docs/DECISIONS.md` records no decisions.** Both `DECISIONS.md` and `DISCREPANCIES.md` are single lines with literal `\n` separators. The SPEC's single most important gate — D-T01, the hardware go/no-go, "the whole project" — has **no recorded outcome, no tier, no BOM, no photo**. `docs/HARDWARE-BILL.md`, required by D-T01's acceptance, does not exist.

---

## 5. P2 — medium / hygiene

| ID | Finding |
|---|---|
| R-24 | **Dependency padding**, which the rubric explicitly penalises ("No dependency padding"): `duckdb`, `openai`, `httpx`, `jinja2` have **0 references** in `backend/app` and `backend/tests`; `numpy` (needed for the in-house swept-volume simulator) is absent. Frontend adds Tailwind and `lucide-react` with no config or usage. |
| R-25 | `ARCHITECTURE.md` documents `backend/app/sandbox/` (does not exist) and ledger "counterfactual cost comparisons against single-model baselines" (no such function); the mermaid pipeline has five stages of which zero are implemented. |
| R-26 | `LIMITATIONS.md` claims "live Tavily verification" and fallback to "cached golden fixtures"; `TAVILY_API_KEY` is read into settings and used nowhere; there are no fixtures and no cache. |
| R-27 | `README.md` "Headline impact: … 0 unmonitored actuators" is unbacked — the repo contains no actuator code, no relay, no GPIO, no serial. |
| R-28 | `backend/app/main.py` has no CORS (the future dashboard will need it), no request models, no error handling, no lifespan, and hardcodes `reload=True`; it also runs the module twice (`python -m app.main` imports `app.main:app` again for reload). |
| R-29 | `config.py` instantiates `Settings()` at import time; no injection seam, no validation that a real API key exists, and pydantic-settings is effectively unused as a loader. |
| R-30 | Ruff reports **17 issues** (13 auto-fixable) across the 5 Python files with default rules; no `[tool.ruff]`/`[tool.mypy]` configuration exists, and `mypy` only passes because almost nothing is annotated. |
| R-31 | `reports/` is empty (`.gitkeep` only); `runs/` proves nothing; no `data/fixtures/snapshots/`, no `data/calibration/`, no `docs/img/hardware/`. |
| R-32 | Repo hygiene: one commit, no PR history, no `NOTICE`, no `CONTRIBUTING`, no `.dockerignore`, no pre-commit, no editorconfig. `uv.lock` is committed (good) while the frontend has no lockfile (bad). |
| R-33 | `SPEC.md §4.1` declares a `PlanRequest` type that does not exist in the contract, and `source`/`kind` enums drift between SPEC (`cloud_gr00t`) and schema (`cosmos_reason`, `hardcoded_sequence`, `retract`). The "six integrity assertions in D-T09" phrase conflicts with the schema's ten. |
| R-34 | The schema declares `"schema_version": "1.0.0"` at the root, which is not a JSON Schema keyword — it validates, but tooling ignores it. Put versioning in `$id` or a `$comment`/`x-` extension, and generate a Python model set from the schema instead of hand-syncing. |
| R-35 | `ActionProposal.proposal_id`/`plan_id`/`decision_id` patterns are prefix-anchored only (`^p_`), so `p_1junk` passes; `keep_out_evidence` allows `{ "method": "none" }` with `keep_out_occupied=true`. |
| R-36 | `.gitignore` contains `data/corpus/*.duckdb`, `data/corpus/*.pdf`, `data/corpus/safety_gate_cache/` — directories from the other project that do not exist here. |

---

## 6. Contract audit — which laws are actually enforced

Executed against `schemas/core-schemas.json` with `Draft202012Validator`. This is the table I would want on the wall before writing any envelope code.

| # | `integrity_assertions_that_must_fail_validation` | Enforced? |
|---|---|---|
| 1 | VETO + non-null, non-noop `shipped_action` | **No** — accepted unless `is_noop` is present (branch lacks `required`/`type`) |
| 2 | VETO + `rule_id=null` | Yes |
| 3 | ALLOW + `rule_id` set | Yes |
| 4 | ALLOW_CLAMPED + `clamp_applied=null` | **No** — keys are only required, not non-null |
| 5 | `ttl_ms` missing or ≤ 0 | Yes |
| 6 | `keep_out_occupied=true` + `keep_out_evidence=null` | Yes |
| 7 | `envelope_off` + collision field omitted | Yes |
| 8 | Rule with only one parameter set | Yes |
| 9 | Degraded less conservative than normal | **Not schema-checkable** — and the script that should check it does not exist |
| 10 | `SessionRun.collisions_in_shipped > 0` | Yes |

Additional gaps found by probing beyond the list:

* `outcome=VETO, shipped_action=null` → **rejected** (R-02) — the single most important record shape is invalid.
* `outcome=envelope_on, replay outcome=collided` → **accepted**; the "0 collisions on-arm" law is only enforced on the aggregate `SessionRun.replay.collisions_envelope_on`, never on the individual `ReplayResult`.
* `ReplayResult.outcome=collided` with `collision=null` → **accepted**; "we collided but don't know with what" is representable.
* `SessionRun.counts` need not add up (`actions_planned=10, actions_allowed=99` → accepted).
* `outcome=ALLOW_CLAMPED` + `rule_id` present but `clamp_applied` with no `velocity` → accepted (the before/after is optional within the object).
* `rule_trace` is not cross-checked against `outcome`/`rule_id`/`first_veto_index` (a VETO may have no `VETO` entry in its own trace).

---

## 7. Claim → evidence matrix

| Claim (README / ARCHITECTURE / LIMITATIONS) | Evidence | Status |
|---|---|---|
| "Cloud VLM proposes; on-device model + deterministic envelope hold veto authority" | no model client, no envelope, no device code | **False** |
| "10 deterministic veto rules" | 10 rules exist as JSON; 0 implemented; 12 parameters are `TODO_MEASURE` | **False as implemented** |
| "Multi-tiered model routing (Ultra / Super / Nano)" | no Token Factory client; `openai` dependency unused | **False** |
| "Token Factory Sandboxes with guest networking disabled" | `backend/app/sandbox/` missing; `SANDBOX_NETWORK_DISABLED` unused | **False** |
| "Sandbox branching for A/B counterfactual evaluation" | nothing | **False** |
| "Every request appends to `runs/ledger.jsonl`" | `record_telemetry` never called; sample file invalid JSON | **False** |
| "Counterfactual cost comparisons vs single-model baselines" | no function | **False** |
| "Formal abstention (`UNDETERMINED`)" | absent from `Outcome` enum | **False** |
| "Custom design system, full keyboard nav, ARIA, cancel/stop" | 21 lines of CSS; no app | **False** |
| "`make sample` runs the end-to-end pipeline" | runs one vacuous test | **False** |
| "`make demo` works with no hardware and no API key" (SPEC §14) | `SyntaxError`; no simulation mode | **False** |
| "`make check` covers lint, types, schema, gate" | 1 test, none of those | **False** |
| "Apache-2.0" | incomplete text; GitHub `NOASSERTION` | **Partial** |
| "~4% of field is Physical AI" | 34 / 833 rows in the committed CSV = 4.08% | **True** |
| "No secrets committed" | credential scan clean | **True** |
| "Schema contracts are frozen and enforce the laws" | meta-valid; 7 of 10 laws enforced, 2 holes, 1 law not schema-checkable; 1 unrepresentable record | **Partial** |

---

## 8. Security & safety review

* **Secrets:** none committed. `.env` is correctly ignored. `README` only shows placeholder exports. Good.
* **Misconfiguration risk:** defaulting `nebius_api_key` to `"mock-key"` means a deployment with no key looks healthy at `/health` and fails only at the first real call — which does not exist yet. Prefer `Field(...)` with a startup check in non-dev environments.
* **Image hygiene:** root user, unpinned base image, no digest, no `HEALTHCHECK`, no `.dockerignore`, no lockfile in the install (`pip install ./backend` ignores `uv.lock`). The same bytes are not guaranteed to run twice — which directly contradicts the project's "reproducible replay" thesis.
* **API surface:** `/docs` and `/openapi.json` are public (fine for a hackathon, worth a note), no auth (fine: read-only endpoints), no CORS (will bite the dashboard), no rate limiting (fine).
* **Audit-trail integrity (the product's core promise):** the ledger path varies by deployment ([R-11](#42-runtime-packaging--deploy)), writes are non-atomic and unvalidated, and there is no dedupe. A safety record that can land in three different directories and cannot be schema-validated is not yet audit-grade. This deserves a dedicated ticket: *"the ledger is the product"*.
* **Physical-safety claims:** none of the hardware claims (relay in the power path, veto-to-stop latency/distance, interlock bypass test) have any code, wiring documentation, photo, or measurement. Per the SPEC's own risk register (R9) and the judges' recorded preferences, these must either be implemented and measured or explicitly downgraded to "design, not built".

---

## 9. Coverage vs. the plan

| Artifact | Planned | Present |
|---|---|---|
| Tickets | 40 (`D-T01`…`D-T40`) | 0 marked done; D-T01 (the go/no-go) unrecorded |
| Veto rules | 10 | 0 implemented, 10 specified |
| Python source | edge + cloud + sim + jobs + sandbox | 106 LOC in 5 files (+ 13-line test) |
| Tests | 18 verification layers | 1 vacuous test |
| CI workflows | "CI must run the envelope tests on every push" (D-T02) | 0 |
| Docs | ~3,000 lines | present and high quality |
| Frontend | split-screen operator view + veto ledger + `ReplayCompare` | design tokens only |
| Ledger | edge ring buffer + cloud ingest + dedupe | 1 helper, never called |

**Reading of the situation:** the repo is roughly **24–36 focused engineering hours behind its own README**. That is recoverable inside the four-day window *only if* the vertical slice starts now and the docs stop growing. (Docs and process text: 3,053 lines. App code: 106. The ratio is the problem.)

---

## 10. Remediation plan

### Phase A — 60 minutes, unblocks everything

1. Rewrite `backend/app/__init__.py` with a real docstring + newline.
2. Add `backend/tests/test_app.py`: import `app.main`, `TestClient`, assert `/health` 200 and `/v1/info` 200. Add to `make check`.
3. Fix the schema's `VETO` (`type: object`, `required: ["is_noop"]`) and `ALLOW_CLAMPED` (non-null clamp) branches; convert the ten integrity assertions into pytest fixtures.
4. Replace the two `../../A-redflag…` `$ref`s with local definitions (or delete `Citation`).
5. Repair the literal-`\n` files (`DECISIONS.md`, `DISCREPANCIES.md`, `sample_ledger.jsonl`) and decide the ledger filename (`runs/ledger.jsonl` vs `runs/veto-ledger.jsonl`).
6. Restore canonical Apache-2.0; add `NOTICE` + `license` metadata.
7. Make `make lint`/`make format` real (or delete them from `.PHONY` and the help text); remove `make batch` from the README until it exists.

**Acceptance:** `make demo` starts a server with no key; `curl /health` → 200; all schema fixtures pass; `make check` runs ≥ 5 meaningful tests.

### Phase B — Day 1, the vertical slice (this is the product)

8. Create `backend/app/envelope/` as a pure module (no `httpx`, `openai`, `socket`, `requests` imports): load the taxonomy, evaluate V1–V10 in priority order, first-veto-wins, normal/degraded parameter selection, clamp semantics, `determinism_hash` over the canonicalised `(snapshot, action, envelope_version)`.
9. Add `data/calibration/rig-limits.json` + `scripts/check_param_provenance.py` + `scripts/diff_parameter_sets.py`; replace every `TODO_MEASURE`; make degraded strictly stricter and enforce it in CI.
10. Generate Pydantic models from the schema (`datamodel-code-generator`) or hand-write them, and validate **every** emitted decision before it is written. Add `POST /v1/envelope/evaluate`.
11. Ledger: environment-configurable path, atomic append with `fsync`, monotonic `id`, schema validation, dedupe key. Add the `all-Ultra` counterfactual summary the ARCHITECTURE promises.
12. Tests: per-rule positive + negative fixtures; purity test (AST/import-graph walk); determinism test (500 snapshots, two processes, byte-identical hashes); "a model cannot clear a veto" test; outage/degraded test.

**Acceptance:** `make verify-envelope` prints PASS; 10 rules × 2 fixtures green; a decision for a V2 veto validates against the schema; `runs/ledger.jsonl` parses and every line validates.

### Phase C — Day 1–2, proof & UI

13. In-house 2.5D swept-volume simulator (~200 lines, `numpy`); replay runner with `envelope_on`/`envelope_off` arms from identical inputs; emit `ReplayResult` per arm and a `SessionRun` aggregate.
14. Rebuild the frontend from a real scaffold: `index.html`, `vite.config.ts`, `tsconfig.json`, `src/main.tsx`, `App.tsx`, Tailwind/PostCSS config, lockfile. Verdict + action above the fold; `rule_trace` table expandable below; `ReplayCompare` stills; permanent SIMULATION badge; StopButton ≤ 2 keypresses; text labels, not colour alone.
15. Activate CI at `.github/workflows/ci.yml`: `uv sync --frozen --extra dev`, ruff, mypy, pytest, schema-fixture validation, taxonomy checks, `npm ci && npm run build`. Fix or remove the README badge.

**Acceptance:** `npm run build` exits 0 and the preview renders; a veto produces two replay arms and one ledger line; CI is green and actually imports the app.

### Phase D — Day 2–3, evidence & honesty

16. Hardware (or the explicit simulation-only fallback): relay-in-power-path wiring, bypass test, veto-to-stop latency/distance, 1,000-action session, false-positive study, two tuned parameters.
17. De-templating pass: remove the legal-domain residue, the `A-redflag` references, the `A/B/C-T##` template IDs, the duplicate competitor CSV, and reconcile `SPEC.md §7` with the actual tree (or rewrite the layout section).
18. Rewrite README/LIMITATIONS/ARCHITECTURE to match what exists, with numbers and test names. Fix the dates/day-of-week and the CET/CEST deadline. Fill `DECISIONS.md` (starting with D-T01) and `DISCREPANCIES.md`.

**If hardware is not in hand tonight**, the SPEC's own rule applies (R1 / D-T01 kill criterion): switch to Idea A. Do not ship a Physical AI entry claiming a rig that does not exist — the track requires ≥ 1 minute of hardware footage, and the judges have said on the record that unbacked claims are what they punish.

---

## 11. Verification log

Environment: Python 3.11.2, uv (latest), Node 22/npm, pytest 9.1.1, jsonschema 4.26, FastAPI 0.162, pydantic 2.14. Dependencies installed in throwaway venvs outside the repo; the workspace was cleaned afterwards.

| # | Command | Result |
|---|---|---|
| 1 | `python -m compileall backend/app backend/tests` | `SyntaxError` in `app/__init__.py` |
| 2 | `python -c "import app"` (editable **and** wheel install) | `SyntaxError` in both |
| 3 | `make sample` | 1 passed (`test_core_schemas_validity`) |
| 4 | `make check` / `pytest -v` | 1 passed |
| 5 | `make demo` | `SyntaxError`, exit 2 |
| 6 | `make lint` | "Nothing to be done", exit 0 |
| 7 | `make batch` | "No rule to make target 'batch'" |
| 8 | `uv build` / `uv lock --check` | wheel + sdist built; lock resolves (48 pkgs) |
| 9 | `pip install ./backend` + `python -m app.main` | installs; import fails |
| 10 | `ruff check backend/` | 17 errors (13 fixable); `mypy app` fails on the syntax error, clean once fixed |
| 11 | `Draft202012Validator.check_schema(schema)` | OK |
| 12 | 10 taxonomy rules vs `$defs/Rule` | all 10 valid |
| 13 | 10 integrity assertions as instances | 7 enforced / 2 not / 1 not schema-checkable; canonical VETO rejected; 3 extra gaps found |
| 14 | `json.loads` over `runs/sample_ledger.jsonl` | `Extra data: line 1 column 326` |
| 15 | `npm install && npm run build` | exit 1 (tsc help output) |
| 16 | `npm run dev` | Vite starts, no entry point; blank page |
| 17 | `gh api …/actions/workflows` | `total_count: 0` |
| 18 | `gh api repos/… --jq .license.spdx_id` | `NOASSERTION` |
| 19 | `.env` loading test (`ENVIRONMENT=production`) | ignored → `development` / `mock-key` |
| 20 | Ledger path, installed mode | `…/lib/python3.11/runs/ledger.jsonl` |
| 21 | Competitor CSV row count | 833 rows, 34 physical-ai → 4.08% |
| 22 | Credential scan of tracked files | clean |
| 23 | `zoneinfo` deadline check | 10:00 PT → 17:00 UTC → 18:00 CET, not 19:00 CEST |

---

## Appendix — reproduce

```bash
# 1. The blocker
python3 -m compileall -q backend/app; python3 -c "import sys; sys.path.insert(0,'backend'); import app"

# 2. The contract bug
pip install jsonschema
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator
S=json.load(open('schemas/core-schemas.json'))
prop={"proposal_id":"p_1","plan_id":"plan_1","kind":"push","target_pose":{"x":1,"y":0,"z":0},
      "velocity_limit":10,"force_limit":5,"preconditions":[],"expected_end_state":{},
      "source":"cloud_ultra","issued_at":"2026-10-26T10:00:00Z","ttl_ms":100}
dec={"decision_id":"d_1","proposal_id":"p_1","snapshot_id":"s_1","outcome":"VETO",
     "rule_id":"V2_KEEP_OUT_OCCUPIED","rules_evaluated":["V2_KEEP_OUT_OCCUPIED"],
     "rule_trace":[{"rule_id":"V2_KEEP_OUT_OCCUPIED","result":"VETO"}],
     "intended_action":prop,"shipped_action":None,"mode":"normal","latency_us":10,
     "envelope_version":"sha256:abc","determinism_hash":"abc",
     "decided_at":"2026-10-26T10:00:00Z","device_id":"dev"}
v=Draft202012Validator({"$schema":"https://json-schema.org/draft/2020-12/schema",
                        "$ref":"#/$defs/EnvelopeDecision","$defs":S["$defs"]})
print("valid?" , not list(v.iter_errors(dec)))   # → False
PY

# 3. The docs' own commands
make sample && make check
make demo        # SyntaxError
make batch       # no such target

# 4. CI & licence, from the published repo
gh api repos/knarayanareddy/reflex-physical-ai/actions/workflows   # total_count: 0
gh api repos/knarayanareddy/reflex-physical-ai --jq .license.spdx_id  # NOASSERTION
```
