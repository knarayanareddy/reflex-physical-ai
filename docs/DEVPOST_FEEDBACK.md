# Devpost submission — feedback on the form

Written while filling in the actual submission, so it is about the *process* rather than the project.
Each item is something that cost time or would have caused a wrong answer, with the workaround used.

**Deadline context:** submission closes Fri 2026-10-30 17:00 UTC (18:00 CET). Repository state at the
time of writing: `main` at `d74492b`, 431 tests, `make check` green.

---

## 1. "Runs on Token Factory at runtime" vs. a build with no key

**The problem.** The eligibility filter asks whether the project runs on Token Factory. This build
makes **zero** model calls: no `NEBIUS_API_KEY` exists in the environment, so `runs/ledger.jsonl` was
never created. The integration code and the telemetry-ledger format exist, and the planner is tested,
but nothing in the runtime path calls a model. The honest answer to that filter is therefore *no* —
even though the project is, in every other sense, built for that runtime.

**Why it is easy to get wrong.** It is tempting to tick the box because the *intent* was there ("the
planner would call Ultra"). That would be a fabricated result, and the whole project is an argument
against fabricated results. The submission states the gap explicitly, in the criteria table and in
`LIMITATIONS.md` §3.

**What would fix it.** `POST /v1/plan` (planner → evaluate → telemetry) is the single ticket that
closes it, and it would fill both `NOT MEASURED` cells in the README's tiering matrix. Until then the
row stays empty.

**Suggestion for the organisers.** If a project's integration is real but unkeyed, say whether that
disqualifies it, or whether a recorded fixture call is acceptable. "We could not obtain a key" is a
different situation from "we did not build it", and the form does not distinguish them.

---

## 2. Video: "2–3 minutes", and what a 2:45 target costs

**The problem.** A hard 3:00 limit with a soft 2–3 minute expectation rewards a script that ends at
2:45, which is what `video/script.md` targets. Getting a *recorded* file to land there is not the same
as writing a 165-second script: the first take ran 166 s of wall clock and the container reported
**184 s** because the screencast is variable-frame-rate. Padding or trimming on the container's
duration silently produces a 2:44 or a 3:04.

**Workaround.** The recorder measures shot boundaries on a monotonic clock, trims a measured lead-in,
and re-encodes with `fps=30` before writing either container, so the output is 165.0 s by construction
instead of by hope.

**Suggestion.** State whether "under 3:00" is enforced, and whether uploads are re-encoded. It changes
whether a 2:59 file is safe.

---

## 3. "≥ 1 minute of the key modules in action"

**The problem.** The checklist asks for footage of the application modules running. With no hardware,
"the modules" are an API and a dashboard. It is not obvious whether a terminal running the demo counts,
or whether a judge expects a physical rig.

**Workaround.** Shots 2–4 (90 s) are the envelope deciding in real time — the timeline, the dashboard
and the replay canvas — and the terminal shots show `make demo` printing the six checks it actually
ran. If a judge wants "the code", `backend/app/envelope/` is on screen as the rule trace for every
interlock.

**Suggestion.** One sentence in the form: "terminal + local UI is acceptable for software-only
submissions" would remove the guess.

---

## 4. The static demo needs explaining, or it looks like a lie

**The problem.** The GitHub Pages site has no backend. A dashboard that shows decisions with no server
behind it looks, at a glance, like a mock-up.

**What the project does about it.** The page fetches `replay/bundle.json`, which was produced by
running the real 10-second session through the real envelope at build time; the header chip reads
`replay/bundle.json · recorded, not live`, and the six build-time checks are printed under the
timeline. The browser is never allowed to decide anything.

**Suggestion for the form.** A field for "if this demo is static, where does the data come from"
would make this distinction visible, instead of leaving it to each project to explain in prose.

---

## 5. Judging criteria reward numbers, which rewards inventing them

**Observation, not a complaint about the form.** The criteria (impact, depth, use of the platform)
are naturally answered with figures. The cheapest way to answer them well is to estimate: "~70 ms
model latency", "~$0.002 per decision". This project refuses that — the tiering matrix has a
`NOT MEASURED` row with the two reasons and the steps to fill it — and it is worth saying that this
choice makes the submission look *weaker* on a skim.

If the organisers want honesty to be competitive, a rubric line like "unmeasured claims are marked as
such" would do more for submission quality than any amount of emphasis on scale.

---

## 6. Practical: what the submission needs that the repository did not have

| Need | Before | After |
|---|---|---|
| A URL a judge can open | nothing deployed | GitHub Pages workflow + static replay bundle |
| A video file | `video/script.md` only | `docs/media/reflex-demo.mp4` / `.webm`, regenerable via `node scripts/record-demo.ts` |
| A frontend CI gate | Python only (D-T27 NOT_DONE #5) | `frontend` job: typecheck, both builds, bundle invariants |
| A one-command replay check | — | `make pages-check` |

The Pages deploy is the item that changed the submission most: a judge can now open the dashboard
without cloning anything, and the recording they see is regenerated on every deploy from the code in
the repository — so the site cannot drift from the envelope it claims to demonstrate.
