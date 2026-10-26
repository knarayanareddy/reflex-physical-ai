# TASK REPORT — D-T27-PACKAGE

**ID:** D-T27-PACKAGE · **Title:** Inject headline numbers into README, finalize LIMITATIONS, verify offline demo
**Phase:** 4–5 (packaging & ship) · **Owner:** lead-agent · **Dependency:** PR #3 merged (`308e7a1`)
**Date:** 2026-10-26 · **Deadline:** 2026-10-30 18:00 CET

---

## WHAT

### 1. `README.md` — rewritten around measured numbers (275 lines, was 163)

- **Headline banner** exactly as ticketed, plus a provenance table that names the JSON field behind every
  figure: `1,000 Actions Planned · 420 Vetoes Enforced · 248 Collisions Prevented · 0 Collisions Shipped`
  (`runs/headline_statistics.json` → `headline.*`), with the 248 split into **170 contacts + 78 boundary
  excursions** three lines later.
- **Status table** replaced. The old one said "Phase 2 of 5", "Dashboard — Not started", "Cloud planner —
  Not started", "254 tests" and `make batch` "**Does not exist**". It now lists 15 components with the
  command that proves each one, including the four that are *not* done (measured calibration, Token
  Factory call, serverless runner, hardware).
- **Model tiering matrix** with a measured edge row (p50 116 µs / p95 162 µs / max 239 µs over 100
  decisions from `make demo`; 2.86 ms per action including both replay arms from `make batch`; $0.00 per
  decision) and an explicitly **NOT MEASURED** cloud row, with the two reasons and the way to fill it.
- **Four judging sections**: `### Technological Implementation (25%)`, `### Design (25%)`,
  `### Potential Impact (25%)`, `### Quality of the Idea (25%)` — each backed by commands/tests and each
  ending with a "what is missing" line, so no adjective stands without a number.
- The invented hook numbers ("1,240 actions planned · 37 vetoed · 37 simulated") are gone; the hook now
  points at the 1,000-action session.

### 2. `LIMITATIONS.md` — the simulator section and the veto arithmetic (159 lines, was 92)

- **New §2 "The simulator: single-axis, 2-D, positions only."** States plainly that it evaluates
  single-axis translational motion of the tool tip in x-y at a fixed z with 2 mm sampling, and does not
  replace 6-DoF rigid-body contact dynamics; a table lists what that excludes (rotation, z motion,
  contact forces/compliance, stopping time, multi-body geometry) and what each omission costs.
- **The 420 breakdown** as a table that sums correctly: V2 120, V10 80, V9 70, V6 50, V4 50, V7 40, V1 10.
- **The 248 split**: 170 contacts (V2 120 + V6 50) + 78 boundary excursions (V5 clamps), and the explicit
  statement that the remaining **250 of the 420 have no geometric counterfactual** and are never counted
  as prevented.
- §3 refreshed from the current artifacts (417 tests / 0 failures, 2,000 replay records, dashboard exists
  with the caveat that it is verified by typecheck + build + jsdom, not in a browser).

### 3. `jobs/offline_demo.py` — the 10-second offline demo (new, 730 lines)

`make demo` used to be a bare `uvicorn` process. It now runs the session the ticket asks for:

- 100 proposals at 10 Hz, tool tip 10 mm → 70 mm at 15 mm/s, target 200 mm (inside the keep-out volume);
- at **t = 4.0 s** an intruder appears → **V2 vetoes**, `interlock_relay_opened = true`, `shipped_action`
  is `null`;
- every later proposal is refused by **V1** (relay open), so the demo shows that *asking again does not
  restart the machine* — a property the ticket did not ask for and the envelope provides;
- all 100 decisions go through the real `evaluate` and the real `record_decision` into
  `runs/demo-veto-ledger.jsonl`, and the **veto line is printed verbatim**;
- both replay arms are computed for all 100 decisions, so "0 shipped collisions" is measured in the demo
  and not asserted;
- six checks run before any green banner (`DEMO PASS`); any failure prints `DEMO FAIL` and exits 1;
- `--serve` starts uvicorn + vite and proves both answer (`/health`, `/v1/envelope/info`,
  `/v1/envelope/evaluate` returning **the same decision id as in-process**, `UI /`, and the dashboard's
  `/stats/headline.json`); `--check` does the same and exits; `--no-ui` is the API-only path.

### 4. `Makefile` — `demo`, `demo-check`, `serve`

`demo` = the 10-second session then both servers; `demo-check` = same checks, exits 0, leaves nothing
running (useful in CI and before recording); `serve` keeps the old behaviour (API only). Help text updated: nothing in the
Makefile needs a network.

### 5. `backend/tests/test_offline_demo.py` — 14 tests (new)

Session shape, freeze-at-veto, V2 + interlock, **the latch**, `mode=simulation`, ledger validity per
frame, one-JSON-object-per-line, snapshot+trace in the veto line, the counterfactual contact at 150 mm,
0 shipped collisions, determinism across two runs, **and two failure paths**: a session with no intrusion
must be refused, and a session whose off-arm never collides must be refused (the demo will not claim a
prevention it cannot show). A subprocess test runs `--check --no-ui` end to end and asserts exit 0, the
`DEMO PASS` and `DEMO CHECK PASS` lines, and the API/in-process decision-id equality.

### 6. `video/script.md` — exactly 2:45

Seven shots, timecodes summing to **165 s**, 295 spoken words (1.8 words/s, counted from the script).
Shot 3 is the split-screen control room; shot 4 is the per-row replay animation and states **248
adverse end-states = 170 contacts + 78 boundary excursions**. No shot needs hardware, so the ≥1 minute of
"key application modules in action" is covered by shots 2–4 (90 s). A "must not claim" list forbids
"248 collisions", a hardware result, measured veto-to-stop, and any Token Factory latency.

### 7. Two small corrections found by this ticket

- `backend/tests/test_plan.py`: the abstention test wrote a **fixture model call** into the repository's
  real `runs/ledger.jsonl` (1200 prompt tokens, $0.00, `plan_abstain`). A judge reading that file would
  believe a model call happened. It now uses the existing `no_telemetry` fixture; the stray file was
  deleted. Logged in `docs/DISCREPANCIES.md`.
- `.github/workflows/ci.yml`: the header claimed `frontend/` has "no entry point" and `npm run build`
  exits 1. It has a dashboard and builds cleanly. Comment corrected; the job itself is a separate ticket.

---

## VERIFIED

### The ticket's VERIFY command

```
$ cd backend && uv run --extra dev pytest tests/ -v
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-9.1.1, pluggy-1.7.0 -- /home/user/reflex-physical-ai/backend/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/user/reflex-physical-ai/backend
configfile: pyproject.toml
plugins: asyncio-1.4.1, anyio-4.15.1
...
tests/test_taxonomy.py::test_v8_switches_to_degraded_faster_than_normal PASSED [ 99%]
tests/test_taxonomy.py::test_strictness_direction_is_defined_for_every_parameter PASSED [100%]

============================= 417 passed in 14.65s =============================
```

Acceptance asked for "403+ tests cleanly": **417 passed, 0 failed, 0 skipped, 0 xfail**. 403 were there
before this ticket; the 14 new ones are in `tests/test_offline_demo.py`.

### `make check`

```
$ make check
cd backend && uv run --extra dev ruff check app tests ../scripts      -> All checks passed!
cd backend && uv run --extra dev ruff format --check app tests ../scripts -> 45 files already formatted
cd backend && uv run --extra dev mypy app                             -> Success: no issues found in 21 source files
cd backend && uv run --extra dev python ../scripts/validate_schema.py  -> PASS - schema, $refs, 10 taxonomy rules ...
cd backend && uv run --extra dev python ../scripts/validate_taxonomy.py -> PASS - 10 rules, total priority order ...
cd backend && uv run --extra dev python ../scripts/check_param_provenance.py -> PLACEHOLDER - 22 value(s) are synthetic
cd backend && uv run --extra dev python ../scripts/make_fixtures.py --check -> PASS - 20 fixtures match the implementation
cd backend && uv run --extra dev pytest tests/ -q                      -> 417 passed in 14.67s

make check: PASS — lint, types, contracts, taxonomy, calibration, fixtures and tests are green
```

### `make demo` → `jobs/offline_demo.py --check` (the whole path, including the UI)

```
$ cd backend && python ../jobs/offline_demo.py --check
==============================================================================
Reflex — offline demo
SYNTHETIC SESSION · mode=simulation · no hardware, no camera, no model, no network
10.0 s at 10 Hz · 100 proposals · velocity ceiling 60 mm/s · target x=200 mm
==============================================================================

timeline
  t= 0.0 s  x=  10.0 mm  ALLOW
  t= 1.0 s  x=  25.0 mm  ALLOW
  t= 2.0 s  x=  40.0 mm  ALLOW
  t= 3.0 s  x=  55.0 mm  ALLOW
  t= 3.8 s  x=  67.0 mm  ALLOW
  t= 3.9 s  x=  68.5 mm  ALLOW
  t= 4.0 s  x=  70.0 mm  VETO          V2_KEEP_OUT_OCCUPIED    <-- intruder inside the keep-out volume
  t= 4.1 s  x=  70.0 mm  VETO          V1_EMERGENCY_STOP
  t= 4.2 s  x=  70.0 mm  VETO          V1_EMERGENCY_STOP
  ...
  t= 9.0 s  x=  70.0 mm  VETO          V1_EMERGENCY_STOP

the veto
  rule            : V2_KEEP_OUT_OCCUPIED
  decided_at      : 2026-10-26T12:00:04.000Z
  mode            : simulation  (parameter set: normal)
  intended action : {"expected_end_state": {"block": "at_target"}, "force_limit": 8.0, ... "target_pose": {"frame": "world", "x": 200.0, ...}, "ttl_ms": 500, "velocity_limit": 15.0}
  shipped action  : None
  interlock relay : opened = True
  decision id     : d_707299c9deb8847a57a014a9

motion
  travelled before the veto : 60.0 mm in 4.0 s
  travelled after the veto  : 0.0 mm over 59 frames (5.9 s)

the ledger line
  {"buffered_locally":false,"clamp_applied":null,"decided_at":"2026-10-26T12:00:04.000Z","decision_id":"d_707299c9deb8847a57a014a9", … ,"interlock_relay_opened":true,"latency_us":118.803,"mode":"simulation","outcome":"VETO","parameter_set":"normal","proposal_id":"p_000040", … ,"rule_id":"V2_KEEP_OUT_OCCUPIED","rule_trace":[…],"sensor_snapshot_inline":{…},"shipped_action":null,"snapshot_id":"s_000040"}

  file: demo-veto-ledger.jsonl — 100 records, one JSON object per line

the counterfactual (both arms, same decision)
  envelope OFF : collided with keep_out_volume at t=5333 ms, contact (150.0, 0.0) mm
  envelope ON  : completed, 0.0 mm travelled (1 trajectory point)
  prevented    : True

envelope latency (measured, this run)
  p50 118 µs · p95 163 µs · max 196 µs over 100 decisions · wall 346 ms

checks
  PASS  every frame evaluated              100 decisions for 100 frames
  PASS  first refusal is V2                V2_KEEP_OUT_OCCUPIED at 4.0 s
  PASS  interlock opened                   interlock_relay_opened=true, relay is now open
  PASS  the interlock latches              59 later proposals all refused, none shipped
  PASS  no collision under the envelope    0 of 100 replayed decisions collided
  PASS  the refusal prevented a collision  off: collided at (150.0, 0.0) mm · on: completed

DEMO PASS — 6/6 checks, 0 collisions shipped

serving (Ctrl-C to stop)
  API  http://127.0.0.1:8000/health
  UI   http://127.0.0.1:5173/
  PASS  API /health                200 ok
  PASS  API /v1/envelope/info      10 rules, profile sim_reference_v0
  PASS  API /v1/envelope/evaluate  same V2_KEEP_OUT_OCCUPIED decision as in-process
  PASS  UI /                       200, mount point present
  PASS  UI /stats/headline.json    200 · 1000 actions · 0 shipped

DEMO CHECK PASS — session, ledger, API and UI all answered; servers stopped
```

(One line elided above for width — the veto ledger line — marked with `…`; the other 12 fields are
verbatim. The latency line differs on every run by design.)

`--serve` was also run and terminated with SIGTERM: it printed `stopping…` and left no listener on :8000
or :5173 (`ss -ltn` → empty), which is why the demo installs a SIGTERM handler that runs the same
cleanup as Ctrl-C.

### The demo's own tests

```
$ cd backend && uv run --extra dev pytest tests/test_offline_demo.py -v
tests/test_offline_demo.py::test_the_session_is_ten_seconds_at_ten_hertz PASSED [  7%]
tests/test_offline_demo.py::test_the_tool_tip_advances_then_freezes_at_the_veto PASSED [ 14%]
tests/test_offline_demo.py::test_the_keep_out_intrusion_trips_v2_and_opens_the_interlock PASSED [ 21%]
tests/test_offline_demo.py::test_the_interlock_latches_so_the_next_proposal_is_refused_by_v1 PASSED [ 28%]
tests/test_offline_demo.py::test_the_session_is_stamped_simulation PASSED [ 35%]
tests/test_offline_demo.py::test_the_ledger_holds_one_valid_record_per_frame PASSED [ 42%]
tests/test_offline_demo.py::test_the_ledger_line_is_one_json_object_per_line PASSED [ 50%]
tests/test_offline_demo.py::test_the_veto_line_carries_its_own_snapshot_and_trace PASSED [ 57%]
tests/test_offline_demo.py::test_the_counterfactual_collides_where_the_envelope_stops PASSED [ 64%]
tests/test_offline_demo.py::test_no_decision_in_the_session_collides_under_the_envelope PASSED [ 71%]
tests/test_offline_demo.py::test_the_demo_is_deterministic PASSED        [ 78%]
tests/test_offline_demo.py::test_a_session_that_never_intrudes_is_refused PASSED [ 85%]
tests/test_offline_demo.py::test_a_session_whose_counterfactual_never_collides_is_refused PASSED [ 92%]
tests/test_offline_demo.py::test_the_check_mode_serves_the_api_and_probes_it PASSED [100%]

============================== 14 passed in 3.24s ==============================
```

### The headline numbers in the README are the committed artifact

```
$ python3 -c "import json; d=json.load(open('runs/headline_statistics.json')); print(d['headline'], d['prevented']['total'], d['prevented']['collisions'], d['prevented']['boundary_excursions'])"
{'actions_planned': 1000, 'vetoes_enforced': 420, 'collisions_shipped_under_envelope': 0, 'collisions_prevented': 248} 248 170 78
```

### The video script's runtime and word count

```
$ python3 - <<'PY'   # parse the table: timecodes and spoken words
...
`0:00 – 0:15`   15s   26 words  104.0 wpm
`0:15 – 0:45`   30s   48 words   96.0 wpm
`0:45 – 1:15`   30s   61 words  122.0 wpm
`1:15 – 1:45`   30s   58 words  116.0 wpm
`1:45 – 2:10`   25s   42 words  100.8 wpm
`2:10 – 2:30`   20s   40 words  120.0 wpm
`2:30 – 2:45`   15s   20 words   80.0 wpm
total: 165 s = 2:45 | words: 295 | wpm: 107.3
```

### README: no unbacked adjectives, no placeholder tags

```
$ grep -n -iE "\b(simple|easy|fast|powerful|robust|reliable|secure|comprehensive|advanced|modern|beautiful|elegant|scalable|production-ready|enterprise|novel|unique|innovative)\b" README.md
161:  exception, and abstention is a first-class result (38 tests).

$ grep -n -i "TODO\|TBD\|XXX\|lorem\|placeholder\|coming soon" README.md
(no output)
```

The single hit is `first-class`, and it is followed by the count of tests that pin it. Words like
"deterministic" and "pure" appear next to the test that proves them (`make verify-envelope`,
`test_envelope_purity.py`); "measured" appears only on figures copied from
`runs/headline_statistics.json`.

---

## COSTS

**Zero model calls, zero tokens.** No `NEBIUS_API_KEY` exists in this environment, so nothing was sent to
Token Factory while building or verifying this ticket. `runs/ledger.jsonl` does not exist (and a test that
used to create it has been fixed — see WHAT §7). This is also why the tiering matrix's cloud row is
empty: the delta the ticket asked for has no second operand.

## TODO_VERIFY

| # | Unconfirmed fact | Where to confirm | Owner |
|---|---|---|---|
| 1 | Ultra/Super/Nano/Cosmos **model IDs** (`nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-nano`, `nvidia/cosmos-reason-2`) are pinned in `config.py` and quoted in the README; never checked against the live list | `GET {base_url}/models` with a key | lead-agent |
| 2 | **Ultra planner latency and cost** — the tiering delta. Not measured, published as NOT MEASURED | One `UltraPlanner.plan(...)` call with a key writes `latency_ms`/`cost_usd` to `runs/ledger.jsonl` | lead-agent |
| 3 | **Token Factory JSON / structured-output mode** — the planner sends plain `chat.completions.create` and parses text | `docs.tokenfactory.nebius.com/ai-models-inference/json` (unreachable here) | backend-agent |
| 4 | **Sandbox SDK** — the pack is verified locally with the network disabled; no `create_sandbox` call exists | `docs.tokenfactory.nebius.com/sandboxes/sdk/python_sdk/*` | backend-agent |

All four are also rows in `docs/DISCREPANCIES.md` with owners.

## DEVIATIONS

1. **The tiering matrix publishes one measured row, not two.** SPEC asked for the *exact* Ultra latency
   and the cost delta; there is no key, no call and no CLI, so the cloud row is `NOT MEASURED` with the
   method to fill it. The alternative was a number nobody measured.
2. **The 248 is split wherever it appears.** The banner keeps the ticket's wording because it matches the
   JSON field name, but the README's next three lines, the dashboard, LIMITATIONS §2 and the video script
   all separate 170 contacts from 78 boundary excursions.
3. **The veto breakdown lists seven rules, not four.** The four named in the ticket sum to 320; the table
   in LIMITATIONS sums to the 420 it claims to decompose.
4. **`make demo` grew a job file.** SPEC §3 requires a 10-second session, an interlock event and a ledger
   line; a bare `uvicorn` cannot produce them. `jobs/offline_demo.py` is the smallest thing that can, and
   `make serve` keeps the old behaviour for anyone who just wants the API.
5. **`backend/tests/test_plan.py` was touched** (one fixture argument) to stop a test writing a fake
   model call into `runs/ledger.jsonl`. Out of the deliverable list, inside the acceptance ("zero
   unbacked claims"): a fabricated ledger line is exactly the kind of evidence this ticket is meant to
   clean up.
6. **`frontend/package-lock.json` is committed.** No dependency was added — `package.json` is unchanged —
   but the demo now depends on the dashboard being installable, and a lockfile is what makes
   `npm install` reproducible for a judge.
7. **README was rewritten rather than patched.** Roughly half its status rows were false in both
   directions (it claimed a missing dashboard and an existing `make check` that ran 254 tests). Patching
   them individually would have left the surrounding framing ("Phase 2 of 5") lying.
8. **`.github/workflows/ci.yml` received a comment fix only.** A frontend build job is the right follow-up
   but would have widened the ticket into CI work at deadline; it is `NOT_DONE` #5.

## NOT_DONE

1. **No Token Factory call exists**, so (a) the tiering matrix has no cloud latency/cost, and (b) the
   submission filter "project runs on Token Factory at runtime" is **not** satisfied by this build. The
   README says so in two places rather than implying otherwise.
2. **`make demo` is offline only after one network step.** `npm install` (registry) is needed once to
   create `frontend/node_modules`; without it the demo serves the API, prints
   `UI not served: …`, and still passes its session. The README states this before the quickstart.
3. **No hardware.** The interlock is a recorded decision (`interlock_relay_opened`), not a relay; veto-to-
   stop latency and distance remain `null`; the "0 collisions shipped" result is a simulator result.
4. **The replay pack has never run inside a Token Factory Sandbox** — only locally with the network
   disabled by test.
5. **CI has no frontend job**, so a broken dashboard would not fail the build; it is verified locally
   (tsc, vite build, jsdom).
6. **The video is a script, not a recording.** There is no camera, no rig and no screen recorder in this
   environment; the shot list is filmable as written.
7. **No usability or accessibility testing.** The dashboard is verified by typecheck, production build and
   jsdom rendering against the live API — not in a browser, and not at a phone width.

## NEXT

**Serve the planner: `POST /v1/plan`.** Call `UltraPlanner.plan(goal, scene)` from the API, route each
proposal through `evaluate`, write the telemetry line, and return the proposals plus their decisions. One
endpoint turns "the cloud proposes" from a paragraph into the running system, fills both empty cells in
the tiering matrix, puts a real call in `runs/ledger.jsonl`, and satisfies the submission's Token Factory
runtime requirement. Everything it needs already exists and is tested; only the route is missing.
