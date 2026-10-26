# Demo video — 2:45, shot by shot

**Runtime: exactly 2:45 (165 s).** Hard limit is 3:00 (judges need not watch beyond it); the submission
target is 2:45 so the last line lands before the cut-off. Timecodes below sum to 165 s.

**Filmable from the repository alone.** Every shot is a terminal or the dashboard. There is no hardware
in this build, so nothing is marked `[rig]` — the checklist's "≥ 1 minute of the key application modules
in action" is covered by shots 2–4 (90 s of the envelope, the dashboard and the replay canvas running).

**Spoken word budget.** 295 words over 165 s — 1.8 words/second (counted from the spoken column below). Rehearse to that; if a take runs long,
cut words, not shots.

| # | Timecode | Shot | On screen | Spoken line |
|---|---|---|---|---|
| 1 | `0:00 – 0:15` | Hook | Terminal, `make demo` typed. Title card: *Reflex — the veto layer that keeps receipts* | "A cloud planner proposes a robot's next action. This layer refuses, locally and deterministically — and every refusal keeps its receipt. Here it is, in ten seconds." |
| 2 | `0:15 – 0:45` | The veto, live (`make demo`) | The 10-second timeline scrolling: `ALLOW` frames, then `t= 4.0 s VETO V2_KEEP_OUT_OCCUPIED`, then `interlock relay : opened = True` and the `V1_EMERGENCY_STOP` hold | "Ten seconds at ten hertz. The tool tip advances fifteen millimetres a second. At second four an intruder appears in the keep-out volume. V-two vetoes, the interlock opens, nothing ships — and every later proposal is refused by the interlock rule, so asking again does not restart the machine." |
| 3 | `0:45 – 1:15` | Split-screen control room (dashboard) | http://127.0.0.1:5173 — three columns: scene left, the ten interlocks centre, telemetry and the veto ledger right. Camera holds on the headline bar | "The same decision in the operator view: scene on the left, all ten interlocks in the middle, telemetry and the veto ledger on the right. The headline bar reads one thousand actions planned, four hundred and twenty vetoes enforced, two hundred and forty-eight prevented, zero collisions shipped. The calibration is synthetic, so the badge says simulation — and it stays on screen." |
| 4 | `1:15 – 1:45` | Simulate replay, per ledger row | Click **simulate replay**. Canvas: red path advances and stops at the keep-out edge with the ✕ contact marker; green path stays as a single point. Then `runs/headline_statistics.json` on screen | "Press simulate replay on any row. Red is the planner's action with the envelope off: it enters the keep-out volume at a hundred and fifty millimetres. Green is what shipped: no motion. Across the thousand-action session, two hundred and forty-eight adverse end states were preventable — a hundred and seventy contacts and seventy-eight boundary excursions. Both arms re-derive offline." |
| 5 | `1:45 – 2:10` | Network cut | A terminal POSTing `cloud_reachable: false`; response shows `parameter_set: degraded` and a veto. Overlay: three degraded values | "Cut the network and nothing fails open. The cloud becomes unreachable, the envelope switches to degraded parameters — slower, longer hold, wider swept volume — and it keeps vetoing. Sixty tests pin that a degraded value is never less conservative than its normal one." |
| 6 | `2:10 – 2:30` | What is not done | `LIMITATIONS.md` §3, scrolled slowly; the 0-calls row and the 22-synthetic-values row visible | "What is not done: no hardware, so veto-to-stop latency is unmeasured. No API key, so not one model call is in the ledger. The planner is a library with no endpoint. The limitations file lists each one with its number." |
| 7 | `2:30 – 2:45` | Close | Architecture card: *cloud proposes · edge decides · ledger proves*; then the headline banner | "A safety layer that consults the network is not a safety layer. This one is local, deterministic, and keeps receipts." |

## Pre-flight (do this before recording)

1. `make check` — must end `make check: PASS` and `417 passed`.
2. `cd frontend && npm install` once (the only step that needs the registry), then `make demo`.
3. `make batch` so `runs/headline_statistics.json` exists — the headline bar reads it, and without it
   the bar correctly says *"run `python jobs/batch_1000_eval.py`"* instead of showing zeros.
4. Start from a clean terminal at 120 columns so the ledger line does not wrap mid-number.

## What the voiceover must not claim

- **Not** "248 collisions". The number is real, the word is not: 248 is the sum of 170 geometric
  contacts and 78 boundary excursions, and the JSON field is a total. Say "adverse end states", or say
  the split. The dashboard shows the two figures separately for the same reason.
- **Not** a hardware result. No relay clicked; `interlock_relay_opened` is a decision, not a click.
- **Not** measured veto-to-stop latency or distance — both are `null`.
- **Not** a model running on-device, or any Token Factory latency: zero calls have been recorded.
- **Not** "the replay proves the rig is safe" — it proves what this 2-D model would have done.

Say **simulation** out loud whenever a decision carries `mode=simulation`; the UI renders a permanent
badge, and the video must not contradict its own UI.
