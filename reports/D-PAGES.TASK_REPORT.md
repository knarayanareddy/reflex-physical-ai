# D-PAGES — GitHub Pages live demo, static replay, and demo-video automation

**Ticket:** "GITHUB PAGES LIVE DEMO & DEMO VIDEO AUTOMATION (REFLEX)"
**Owner:** lead-agent · **Date:** 2026-10-27 · **Branch:** `arena/d932f739-reflex-physical-ai`
**Base:** `d74492b` (merge of PR #4)
**Protocol:** `docs/AGENT-DELEGATION-PROTOCOL.md`, applied strictly.

---

## WHAT was built

### Deliverable 1 — GitHub Pages rendition

| # | Asked for | Built |
|---|---|---|
| 1 | `base: '/reflex-physical-ai/'` in `frontend/vite.config.ts` | Conditional on `--mode pages`. Unconditional would have moved the dev server off `/` and broken `make demo`'s UI probe and every documented URL (DEVIATION 1) |
| 2 | Static client-side replay: load `headline_statistics.json` + `demo-veto-ledger.jsonl`, scrub 100 steps, tip 10→70 mm, intruder at 4.0 s, V2 + interlock + V1 refusals, Envelope OFF (150 mm collision) vs ON (0.0 mm) | A *recording*, not a client-side envelope: `jobs/export_static_replay.py` runs the real session through `app.envelope.evaluate`, `app.decision_ledger.record_decision` and `app.replay.compare`, and writes every payload to `frontend/public/replay/bundle.json`. `frontend/src/staticReplay.ts` + a `TimelinePanel` in `App.tsx` replay it. All seven behaviours verified in a real browser (VERIFIED 3) |
| 3 | `.github/workflows/deploy-pages.yml` with `upload-pages-artifact@v3`, `deploy-pages@v4`, on push to `main` | Yes, plus a `build` job that re-runs the session and fails if any of the seven invariants break, and a post-build assertion that `dist/replay/bundle.json` and `/reflex-physical-ai/assets/` are actually present |
| 4 | `make build-pages` | Yes, and three companions: `pages-data`, `pages-check`, `pages-serve` |

### Deliverable 2 — the 2:45 demo video

| # | Asked for | Built |
|---|---|---|
| 1 | `scripts/record-demo.ts`, Playwright `chromium.launch({headless:true})` + `recordVideo` | Yes. Also supports `--dry-run`, and falls back to `REFLEX_CHROMIUM_BIN` / system Chrome / `@sparticuz/chromium` so it runs outside a laptop with a browser already installed |
| 2 | 1920×1080 at 125% zoom | Yes — **after** the first take exposed that `deviceScaleFactor: 1.25` letterboxes rather than zooms (DEVIATION 4) |
| 3 | The exact seven shots of `video/script.md` | Yes, on a monotonic clock: 0:00/0:15/0:45/1:15/1:45/2:10/2:30/2:45. Frame-by-frame review of the output is in VERIFIED 5 |
| 4 | `docs/media/reflex-demo.mp4` + `.webm` | Yes: 10.2 MiB mp4, 13.6 MiB webm, both 164.8 s (target 165) |
| 5 | `docs/DEVPOST_SUBMISSION.md` + `docs/DEVPOST_FEEDBACK.md` | Yes |

### Also added (needed by the above, or by the ticket's own claims)

- `scripts/network_cut.py` — the shot-5 demonstration as a runnable script. It exits non-zero unless
  the same plan is `ALLOW`/`normal` on a healthy link and `VETO`/`degraded` after a 9 s outage.
- `scripts/serve-pages.mjs` — serves the build under `/reflex-physical-ai/`, the way Pages does.
- `scripts/stage/{terminal,limitations,close}.html` — the recorder's cards. Every number they print is
  read from the bundle or from the running API at record time.
- `backend/tests/test_static_replay.py` — 14 tests.
- A **`frontend` CI job** (D-T27 `NOT_DONE` #5): typecheck, dev build, `make pages-data`,
  `make pages-check`, Pages build.
- `frontend/src/main.tsx` — the missing `tokens.css` import (VERIFIED 1). Without it the dashboard had
  never rendered with its design tokens at all.

---

## VERIFIED (verbatim, as observed)

### 0. `make check`

```
cd backend && uv run --extra dev pytest tests/ -q
........................................................................ [ 50%]
........................................................................ [ 83%]
.......................................................................  [100%]
431 passed in 15.64s

make check: PASS — lint, types, contracts, taxonomy, calibration, fixtures and tests are green
```

431 = 417 (D-T27) + 14 new. `make demo-check` still passes:

```
DEMO PASS — 6/6 checks, 0 collisions shipped
  PASS  API /v1/envelope/evaluate  same V2_KEEP_OUT_OCCUPIED decision as in-process
  PASS  UI /stats/headline.json    200 · 1000 actions · 0 shipped

DEMO CHECK PASS — session, ledger, API and UI all answered; servers stopped
```

### 1. The dashboard had never been styled — `frontend/src/main.tsx`

`app.css` refers to `var(--color-veto)` and 20 other tokens in 799 lines; nothing imported
`tokens.css`. In a browser the result was a white page with an **opaque black** keep-out volume and no
red/green semantics. Verified by pixel-probing the served page before and after the import:

```
before:  keep-out rect computed fill: rgb(0, 0, 0)      range thumb: default
after:   rgba(255,234,0,0.1) over #0F172A              accent-color from --color-veto
```

`tokens.css` itself is unchanged (still design-system-owned): 0 lines edited there.

### 2. `make pages-check` — the published bundle

```
  loaded /home/user/reflex-physical-ai/frontend/public/replay/bundle.json (713 KiB)
  PASS  bundle is complete                         100 frames · 100 decisions
  PASS  every decision has both replay arms        100 comparisons
  PASS  the veto is where the timeline says it is  frame 40 · t=4.0 s · V2_KEEP_OUT_OCCUPIED
  PASS  the tool tip advances 10 → 70 mm           10.0 → 70.0 mm in 4.0 s
  PASS  the interlock latches                      59 later proposals refused
  PASS  nothing collided under the envelope        0 of 100 shipped arms collided
  PASS  the refusal prevented a collision          off: keep_out_volume at (150.0, 0.0) mm · on: completed

STATIC REPLAY CHECK PASS — 7 checks on the published bundle
```

### 3. The Pages build, in a real browser at `/reflex-physical-ai/`

Served by `scripts/serve-pages.mjs` (the same sub-path Pages uses), driven by Chromium:

```json
{
  "clock": "frame 41 / 100 · t = 4.0 s",
  "x": "x = 70.0 mm · y = 0.0 mm",
  "outcome": "VETO V2_KEEP_OUT_OCCUPIED",
  "headline": "1,000 Actions Planned·0 Collisions Shipped·420 Hard Vetoes Enforced·170 Collisions Prevented…",
  "ticks": 100,
  "vetoTicks": 60,
  "connection": "replay/bundle.json · recorded, not live",
  "errors": []
}
replay arms: [
  'COLLIDED ENVELOPE OFF — AS REQUESTED collided with keep_out_volume at 5333.333 ms',
  'COMPLETED ENVELOPE ON — AS SHIPPED did not move'
]
```

`vetoTicks: 60` = 1 (V2 at frame 40) + 59 (V1). `errors: []` — no console errors, no failed requests.

### 4. `scripts/network_cut.py` — the shot-5 claim, as a check

```
POST 127.0.0.1:8010/v1/envelope/evaluate   cloud_reachable=true
  ALLOW         parameter_set=normal   mode=simulation rule=—  interlock=False

POST 127.0.0.1:8010/v1/envelope/evaluate   cloud_reachable=false (stale 9000 ms)
  VETO          parameter_set=degraded mode=simulation rule=V9_PLAN_MALFORMED  interlock=False
  V8_NETWORK_DEGRADED   DEGRADE  cloud unreachable for 9000.0 ms (> 1000.0 ms): stricter parameters in force
  V9_PLAN_MALFORMED     VETO     ttl_ms 3000 exceeds the 2000.0 ms ceiling

NETWORK CUT PASS — the same plan was allowed under normal parameters and refused under degraded ones; nothing failed open
```

### 5. The video

```
RECORD PASS — 164.8 s mp4, 164.8 s webm, 10.2 MiB mp4
```

Frames extracted at 3, 9, 14, 26, 50, 66, 79, 92, 100, 110, 120, 133, 143, 150, 158, 164 s and
inspected individually. What each shot shows, and the defect it replaced:

| t | Shot | Observed |
|---|---|---|
| 0:02 | Title card | "Reflex — offline demo / The veto layer that keeps receipts" |
| 0:12 | Terminal, typed `make demo` | The six PASS lines, `DEMO PASS — 6/6 checks`, the five HTTP probes |
| 0:22 | Timeline before the veto | `frame 25/100 · t=2.4 s`, `x=46.0 mm`, `ALLOW`, tip and target on the scene |
| 0:44 | The veto | `frame 41/100 · t=4.0 s`, `x=70.0 mm`, `VETO V2_KEEP_OUT_OCCUPIED`, interlock open, red intruder marker |
| 1:06 | Control room | Headline bar, ten interlocks, telemetry, the six recorded checks |
| 1:32 | Two-arm replay | `t = 5333/5333 ms`, red dashed path into the volume, ✕ at the contact, `shipped: no motion` **below** the ✕ (was overlapping it) |
| 1:58 | Network cut | The real `network_cut.py` output + five normal→degraded values |
| 2:23 | LIMITATIONS §3 | The real table, rendered as a table: "22 of 22 are synthetic", "0 Token Factory calls" |
| 2:38 | Close | `cloud proposes · edge decides · ledger proves`, 1,000/420/248/0, and `248 = 170 contacts + 78 boundary excursions — not 248 collisions` |

### 6. `frontend` CI job and workflow validity

```
.github/workflows/ci.yml          -> ['check', 'frontend']      | on: ['push', 'pull_request']
.github/workflows/deploy-pages.yml -> ['build', 'deploy']        | on: ['push', 'workflow_dispatch']
```

Parsed with PyYAML; both files load. **Neither has run on GitHub yet** — that is `NOT_DONE` #1.

---

## COSTS

| Item | Value |
|---|---|
| Model / Token Factory calls | **0** (no key exists; unchanged from D-T27) |
| Tokens billed to the project | 0 |
| Wall clock, full video take | 323 s (165 s recording + encode + pre-flight) |
| New dependencies | **0 Python.** `scripts/package.json` adds `playwright-core` as a *dev* dependency of the recording scripts, not of the product or the API |

`playwright-core` is only loaded by `scripts/record-demo.ts`, which nothing in CI or the app imports.

---

## TODO_VERIFY

| Item | Where | How |
|---|---|---|
| **GitHub Pages repository setting** | `deploy-pages.yml` assumes *Settings → Pages → Source: GitHub Actions* | Set it before the first deploy, or the job fails with `Get Pages site failed` |
| **First `deploy-pages` run** | Committed, never executed | `gh run list --workflow deploy-pages.yml` after merge |
| **Playwright CDN** | Unreachable from this build sandbox | `npx playwright install chromium`, or `REFLEX_CHROMIUM_BIN=/path/to/chrome` |
| **Video voiceover** | None recorded; the script's spoken column is on-screen text | Record narration against `video/script.md` |

---

## DEVIATIONS

1. **`base` is conditional on `--mode pages`, not unconditional.** An unconditional
   `/reflex-physical-ai/` moves the dev server off `/`, breaks `make demo`'s UI probe and every URL in
   the docs, for a benefit only one deployment needs. `make demo` keeps `base: '/'`.
2. **The static page replays a recording instead of loading the raw `demo-veto-ledger.jsonl`.** The
   ledger alone cannot show what the page must show: no rule table (`GET /v1/envelope/info`), no
   headline statistics, no two-arm replays (those are `POST /v1/replay` results, not ledger rows).
   Fetching three artifacts and stitching them in the browser would put three formats' worth of
   interpretation in the client. One bundle, produced by the same functions the API calls, keeps the
   browser strictly a renderer. The ledger is **not** lost: `make demo` still writes it, and the
   bundle carries its 100 decisions verbatim.
3. **"1920×1080 at 125% zoom" is implemented as a 1920×1080 viewport with `body{zoom:1.25}`**, not
   `deviceScaleFactor: 1.25`. The latter lays the page out at 1920 CSS px and letterboxes a 1536×864
   render into the 1920×1080 frame — the first take visibly had grey bars on two edges.
4. **The video has no audio track.** The recorder writes `-an`. `video/script.md`'s spoken column is
   delivered as on-screen content for shots 1, 5, 6 and 7, and the closing card carries the claim
   that would otherwise be spoken. A narrated take is `NOT_DONE` #6.
5. **Shot 5's claim was corrected, not just filmed.** `video/script.md` said a network cut keeps
   *vetoing*. On this profile V8 degrades and the envelope still **allows** — a degrade rule is not a
   veto. The shot now shows what actually happens: one plan, allowed under normal parameters, refused
   under degraded ones. The script, the recorded terminal output and the on-screen text all say that.
   Logged in `docs/DISCREPANCIES.md`.
6. **The video's stage pages are HTML with prose written for the video** (`scripts/stage/*.html`).
   Every *number* they print is read at record time from `replay/bundle.json` or from the live API;
   the words are captions. This is disclosed in `docs/DEVPOST_SUBMISSION.md` and in the
   `TODO_VERIFY` table.
7. **`make pages-data` uses the runtime environment, not `--extra dev`.** The export needs `fastapi`,
   `app.envelope` and `app.replay`, none of which need pytest. A CI job that synced without the dev
   extra can still build the site.
8. **`frontend/public/replay/` is gitignored.** It is a build artifact (713 KiB) whose `latency_us`
   values are real measurements that change every run. The deploy workflow and `make build-pages`
   regenerate it; `make pages-check` validates a stale one. Committing it would mean a file whose
   numbers disagree with the next run for no reason.
9. **The `frontend` CI job was added even though the ticket did not ask for it.** The ticket's own
   `deploy-pages.yml` would otherwise publish TypeScript that no CI ever type-checked. It closes
   D-T27 `NOT_DONE` #5.

---

## NOT_DONE

1. **No `deploy-pages` run.** The workflow exists and is validated as YAML; GitHub has never executed
   it. The site URL in the README and Devpost doc is the URL it *will* publish to — until the first
   green deploy, that URL is a promise, not an observation.
2. **The Pages repository setting has not been flipped.** See `TODO_VERIFY`.
3. **The video's shot 5 in `video/script.md` changed the spoken line** (107 → 112 words/minute for the
   whole script, 307 words). If the user wants the original shot-5 wording, the video must be
   re-recorded with a claim the envelope does not support — so the script changed instead.
4. **No narration.** `-an`; see DEVIATION 4.
5. **The recorder has only been run in this sandbox**, against `@sparticuz/chromium` with a hand-built
   ffmpeg. The Playwright-download path (`npx playwright install chromium`) is untested here because
   its CDN is unreachable.
6. **No hardware, no measured latency, no Token Factory call** — unchanged from D-T27, still the
   submission's largest gap (`LIMITATIONS.md` §3, `docs/DEVPOST_SUBMISSION.md`).
7. **`make build-pages` needs Node and npm.** No installer path exists for a machine without them; the
   deploy workflow installs both.

---

## NEXT

`POST /v1/plan` — planner → evaluate → telemetry. It is the one ticket that closes the "runs on Token
Factory at runtime" filter, fills both `NOT MEASURED` cells in the README's tiering matrix, and creates
`runs/ledger.jsonl` for the first time. Everything else on this project's `NOT_DONE` list is either
hardware, which is out of reach, or cosmetic.
