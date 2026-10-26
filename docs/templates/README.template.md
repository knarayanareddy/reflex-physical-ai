# README.template.md — the judges' first and last impression

**Used by:** A-T38 / B-T38 / C-T38 / D-T34. Copy, fill every `<…>`, delete this header.

> **How a judge actually reads this.** Devpost shows your title, tagline and video first; the README is what they
> open when the video interested them, and it is what they re-open when they are scoring. Budget their attention
> at **90 seconds for the first screen** and **8 minutes for the whole file**. Everything a criterion needs must
> be reachable without scrolling past a wall of prose.
>
> **The three rules that decide most of the score:**
> 1. **Real numbers or nothing.** Every claim gets a number, a test name, a citation or a screenshot. An
>    unbacked adjective costs more than no sentence at all.
> 2. **The four judging criteria must each have a labelled section.** Judges score against four criteria; make it
>    trivially easy for them to find evidence for each one. Use the exact criterion names as headings.
> 3. **Say what does not work.** A README with an honest limitations section reads as engineering. A README
>    without one reads as marketing, and this panel has said on the record that they look for honesty about what
>    has not been done.

---

## The file, in order

```markdown
# <Project Name>

> **<one sentence: what it does, for whom, with the headline number in it>**
>
> <headline statistic — the single most persuasive number you have. Examples:
>  "120 listings screened · 47 would be suppressed · 0 unsupported claims shipped"
>  "1,240 actions planned · 37 vetoed · 37 replayed · 0 collisions shipped"
>  "60 queries · 0 invented dates with the gate on · 11 without it">

**<Disclaimer, one sentence, if your domain needs one.>** — e.g. "Not affiliated with, endorsed by, or certified
against IPC-A-610 or J-STD-001." / "A research prototype, not a certified safety system." / "Not legal advice."
Put it here, not in a footer nobody reaches.

<animated GIF or screenshot of the single most convincing moment. One. Not four.>

[Live demo](<url>) · [Video (<mm:ss>)](<public YouTube url>) · [Limitations](LIMITATIONS.md) ·
[Judge runbook](docs/JUDGE-RUNBOOK.md) · [<Idea-specific: Evidence corpus / Safety case / Eval report>]

---

## Try it in 5 minutes (no API key needed)

```bash
git clone <url> && cd <repo>
make sample        # runs the full pipeline on committed fixtures, offline, no key, no network
```
<what they will see, in one line>. Then, with a Token Factory key:
```bash
export NEBIUS_API_KEY=...
make check         # lint + typecheck + tests
make demo          # live end-to-end on a real input
```

| Command | Needs a key? | Needs hardware? | What it proves |
|---|---|---|---|
| `make sample` | no | no | the whole pipeline runs offline on committed fixtures |
| `make check` | no | no | the test suite passes from a clean clone |
| `make demo` | yes | <yes/no> | a real input produces a real verdict end to end |
| `make verify-<gate/envelope>` | no | no | **the integrity property, on demand** |

---

## The problem

<2–4 sentences in the persona's own words. Use a real quote from a real interview if you have one, attributed as
"interview, <role>, <date>". Then ONE public statistic with a source and a date. Never a statistic without a
source — a judge who checks an unsourced number and finds it wrong stops trusting everything else.>

## What it does

<The 30-second hook, as an actual numbered sequence of what appears on screen. Not a feature list.>
1. <input>
2. <what happens, with the real latency>
3. <the verdict, quoted exactly as it renders>
4. <the artifact they can take away>

## The insight(s) we came in with

<1–3 numbered insights, each ONE sentence, each followed by one sentence of "here is how you can see it in the
build". This is the Quality of the Idea section in disguise — an insider insight that is only asserted is worth
far less than one that is demonstrated by a component.>
1. **<Insight>** — <where it shows up: a component, a test, a number>
2. **<Insight>** — <…>
3. **<Insight>** — <…>

---

## Judging criteria — where the evidence is

### Technological Implementation
**NVIDIA Nemotron models — how each is used and why at that tier:**

| Model / feature | Where | Job | Why this tier, not a bigger one | Real cost |
|---|---|---|---|---|
| Nemotron 3 Nano | <stage> | <job> | <reason> | $<x> / <n> calls |
| Nemotron 3 Super | <stage> | <job> | <reason> | $<x> |
| Nemotron 3 Ultra | <stage> | <job> | <reason — the genuinely hard part> | $<x> |
| Structured output / JSON | <stages> | schema-valid output | makes the gate possible | — |
| Cached Tokens | <stage> | <repeated preamble> | measured saving | −$<x> (<n>%) |
| <Cosmos Reason / Isaac GR00T / Parakeet> | <where> | <job> | <reason> | $<x> |

**Where Nebius Token Factory accelerated the workflow:**
- **Sandboxes** — <what you built/validated in one, with the immutable image UUID. If you used branching: the two
  arms, the n per arm, and the delta. If you disabled guest networking: say so, it is a strong detail.>
- **Serverless Job** — <the batch/eval/simulation lane: n items, wall time, total cost, runner recorded>
- **Serverless Endpoint** — <the deployed API>
- **<Object Storage / Devlab / Inference Observability / post-training>** — <only if genuinely used>
- **Tavily** (if used) — <load-bearing runtime role, not decoration: calls per answer, % results used, what
  happens when it is unavailable>

**Total measured cost:** $<x> across <n> runs (<n> text tokens, <n> image tokens reported separately).
**All-Ultra counterfactual:** $<y> — <n>× more. **Cache-hit rate:** <n>%.
<The full ledger: `runs/ledger.jsonl`, summarised in docs/MODEL-USAGE.md. Coverage: <n>% of model calls.>

**The deterministic gate / safety envelope:**
<2–4 sentences. It is pure Python, it imports no LLM client, and there is a test that proves it. Name the test and
the command. This is the single most differentiated thing in a field that has converged on
"LLM proposes → gate disposes".>
```bash
make verify-<gate|envelope>   # → PASS
```

### Design
<The metaphor in one sentence. Then 3–5 specific decisions and WHY each one, not what it looks like:
"every citation renders as a monospace pill with its retrieval timestamp, because a date you cannot date is not
evidence". Include one screenshot of the hero component and one of an abstention/error state — a project that only
shows its happy path reads as unfinished. Accessibility: state what you audited and what you did about it, with
the axe-core result.>

### Potential Impact
- <The public statistic with source and date>
- <The interview: who, role, what they said, permission given. One real euro/dollar figure beats ten projections>
- <The batch/sweep/study: n, method, and the ONE headline finding, with a link to the methodology>
- <Who exactly would use this next, and what it replaces>

### Quality of the Idea
- <What is genuinely new here, stated plainly, in one sentence — and what is NOT new. Saying "the architecture is
  the same shape as everyone else's; the domain and the evidence are not" is stronger than claiming novelty you
  don't have>
- <The eval: n, double-labelled?, kappa, per-class breakdown, and which classes are INSUFFICIENT>
- <The A/B or control experiment: both arms, n per arm, the delta>
- <The thing you would least like a judge to find — stated by you first, with the number>

---

## Architecture

<An ASCII or SVG diagram. Label every model call with its tier. Mark the gate/envelope as containing no LLM.>

| Stage | Runs on | Model | Deterministic? | Can abstain? |
|---|---|---|---|---|
| S1 … | <edge/cloud> | — | yes | yes |
| S2 … | cloud | Nano | no | yes |
| … | | | | |
| **Gate** | <where> | **none** | **yes — asserted by test** | **yes** |

## The evidence

<Where every number comes from, and how to re-verify it. For data-driven projects: the corpus, the hashes, the
retrieval timestamps, the public listing page. For hardware: the bill of materials with prices and a photo.
Publishing your complete source list is the strongest trust signal available and costs one page.>

| Artifact | Where | How to re-verify |
|---|---|---|
| Ledger | `runs/ledger.jsonl` | `make ledger-report` |
| Eval report | `runs/reports/eval.json` | `python eval/run_eval.py` |
| A/B experiment | `runs/reports/ab-*.json` | `python scripts/ab_*.py --report` |
| <Corpus / veto ledger / replay results> | <path> | <command> |

## Limitations

<3–5 bullets, each with a number. Then a link to LIMITATIONS.md. Do not soften these. This section is read by the
judge who has already decided to like you, and it is what keeps them liking you.>

## What's next

<4–6 concrete items, each with the work it would take. Include the accessibility follow-up and the one thing you
cut for time. "We cut X because Y; it would take Z" reads as judgement. "Future work: make it better" reads as
nothing.>

## Team & process

<Who did what. How many hours. What you built with agents vs by hand — this is an agentic-engineering hackathon
and the delegation story is relevant. Link docs/DECISIONS.md (≥15 entries) and docs/DISCREPANCIES.md (≥3).>

## Data & licences

<Sources with licences. What is redistributed and what is fetched at build time. Any third-party marks named as
text citations only. The project's own licence.>

## Licence

Apache-2.0 — see [LICENSE](LICENSE).
```

---

## Preflight (run before you paste the URL into Devpost)

- [ ] Clean clone → `make sample` works with **no API key** and **no hardware**
- [ ] Clean clone → `make check` green
- [ ] The first screen contains: one sentence, one headline number, one image, four links, and the disclaimer
- [ ] Every number in the README appears identically in the Devpost copy and the video (script the diff)
- [ ] All four judging criteria have a **labelled** section
- [ ] Every statistic has a source and a date; every quote has a named, permissioned speaker
- [ ] The limitations section has ≥3 numbers and is not softened
- [ ] No unbacked adjective survives a sceptical read-aloud
- [ ] No stock phrase ("revolutionary", "seamless", "cutting-edge", "game-changing", "leverage the power of")
- [ ] No emoji in headings; no badge wall; no centred hero
- [ ] `LICENSE` at the repo root; repo public; video public and ≤3:00; demo URL reachable from incognito
- [ ] A non-teammate followed `docs/JUDGE-RUNBOOK.md` successfully
- [ ] ≥$10 of credits left on the account so the demo still works during judging (1–15 Dec)
