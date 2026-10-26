# devpost-feedback.template.md — the $100 prize nobody competes for

**Used by:** A-T50 / B-T42 / C-T43 / D-T39. Copy, fill every `<…>`, delete this header.

> **The prize.** Devpost ran **10 × $100 "Most Valuable Feedback"** awards plus swag. It is the least contested
> prize in the entire hackathon: almost every participant spends their last hour on the video and the README, and
> nobody spends it on a thoughtful write-up about the platform. Ten winners out of ~27,700 participants, from a
> pool of perhaps a few dozen serious entries. **Expected value per hour spent is the highest of anything in this
> package.**
>
> **Who reads it.** The people who built Token Factory, Sandboxes, Serverless, and the Tavily integration. They
> read these looking for: what confused you, what broke, what you wished existed, and what you would tell a
> friend. They are not looking for praise.
>
> **What wins.** Specificity with numbers. "The Sandbox documentation's networking section doesn't say whether
> guest networking can be disabled per-operation or only per-image — I tested it, it is per-operation, and here is
> the snippet" beats "great platform, loved the sandboxes" by an enormous margin. A bug report with a reproduction
> is worth more than three feature requests.

---

## The standard: every entry must pass this test

> Could a Nebius or Tavily engineer act on this **today**, without asking you a clarifying question?

If not, add the version, the endpoint, the request, the response, the timestamp and the doc URL — or cut it.

**Targets:** ≥400 words · **≥6 distinct points** · **≥4 with a number, a quoted doc URL, or a code snippet** ·
**≥1 concrete feature request with a use case** · ≥1 thing you got wrong that turned out to be your fault (this
one is counter-intuitive but it establishes that you read carefully, and it makes the rest credible).

---

## The structure

```markdown
# Feedback — <Project Name> (<track>)

**Built with:** <exact model catalog ids you used> · Token Factory <Sandboxes / Serverless Endpoint / Serverless
Job / cached tokens / structured output — name the ones you actually used> · <Tavily> · <NVIDIA modules>
**Where:** <your region/country> · **When:** <dates> · **Spend:** $<total> across <n> calls
**Repo:** <url> · **Contact:** <email/handle, if you want them to be able to follow up>

One paragraph of context: what you built, at what scale, and what your workload actually looked like. Two or three
sentences. Then the points.

---

## 1. What worked, specifically — and why it mattered

<2–3 points. Not flattery: mechanism. "X let me do Y, which would otherwise have cost Z hours/dollars." Name the
feature by its documented name and link the doc page you used. If a feature was the reason a submission was
possible at all, say so plainly — that is the most useful signal a sponsor can get.>

- **<Feature>** — <what it let you do>, <the number>. <The doc page you worked from, with its URL.>

## 2. Documentation gaps I hit

<The highest-value category. For each: the exact page URL, what you were trying to do, what the page did not say,
what you did instead, and how you found the answer. If you found the answer by experiment, say what the experiment
was — that turns a complaint into a contribution.>

- **<Page URL>** — I was trying to <goal>. The page does not say <the specific missing fact>. I found out by
  <experiment / forum / reading source>, and the answer was <answer>. Suggested addition: <one sentence they could
  paste in>.

## 3. Things that broke, or behaved surprisingly

<For each: what you ran, what you expected, what happened, the exact error or response, and whether it was
reproducible. Include the request id / operation id / timestamp if you have one. **Include at least one where the
fault turned out to be yours** and say what the confusing part was — that is a documentation bug even when the
behaviour is correct.>

- **<Area>** — ran <command/snippet>, expected <X>, got <Y> (<exact error>). Reproducible: <yes/no, n of m times>.
  Request/operation id: <…>. <Turned out to be my fault because <…> — but the part that cost me <n> minutes was
  <the specific confusing signal>.>

## 4. Numbers you might want

<Platform teams rarely get real workload data from a hackathon. Give them yours. This section alone can be the
difference between "nice feedback" and "actually useful".>

| Metric | Value |
|---|---|
| Total spend | $<x> across <n> calls |
| Tokens | <n> prompt / <n> completion / <n> cached <— image tokens separately if vision> |
| All-largest-model counterfactual | $<y> (<n>× more) |
| Cached-token saving | <n>% on <which stage> |
| Latency p50 / p95 | <n> ms / <n> ms <— split edge vs cloud if relevant> |
| Time from my region (<city>) to the endpoint | <n> ms p50, <n> ms p99, measured over <n> calls |
| Sandbox: image build time / cold start / per-operation time | <n> s / <n> s / <n> s |
| Serverless Job: n items / wall time / cost | <n> / <n> min / $<x> |
| Tavily: calls / % results used / % rejected and why | <n> / <n>% / <n>% (<reasons>) |
| Cost per unit of my actual output | $<x> per <listing / board / answer / 1,000 actions> |
| Failure rate by class | <table> |

## 5. What I wished existed

<The feature-request section. For each: the use case FIRST, then the request, then why the workaround was
insufficient. A request without a use case gets filed and forgotten; a request with a concrete scenario gets
built.>

- **Use case:** <what I was trying to do, in the project's terms>. **Workaround:** <what I did instead, and what it
  cost me — lines of code, hours, dollars, or a capability I had to drop>. **Request:** <the specific thing, named
  as an API surface or a UI element, not as a vibe>.

## 6. Non-English / international notes  ← almost nobody submits these

<If you worked in a language other than English, this is genuinely novel signal for both Nebius (Amsterdam-based,
European market) and Tavily (whose search quality on non-English government and technical sources is a real
question). Be specific: which language, which query, what came back, what you expected.>

- <Language> queries against <Tavily / a model> behaved <how>. Example query: "<verbatim>". Results: <n returned,
  n usable, what the failures looked like>. <What would have helped: a language parameter, a region hint, better
  source coverage for <country>'s government publishers, …>

## 7. One thing I would tell a friend starting tomorrow

<Three or four sentences. The single most useful piece of advice you have. This is the part a platform team can
turn into documentation, an onboarding email, or a cookbook page — which is exactly what makes it "most valuable".>

---

**Thanks / sign-off**, <name>, <what you do>, <city>.
```

---

## Material each idea has that is genuinely rare

Do not write generic feedback. Each of these projects produces observations that almost no other entrant can
make — that is the whole edge.

### Idea A — RedFlag (EU product safety, marketplace listings)
- Fetching and hashing a **public EU dataset** (Safety Gate) at build time: what the retrieval ergonomics were,
  rate limits, whether Object Storage made the corpus durable through judging.
- **Structured output** against a schema with nested citation objects — where the model deviated, how often, and
  what validation caught.
- Using **Sandbox branching** for a *measurement* (gate-on vs gate-off over the same cases) rather than for
  comparing code fixes — a novel use of the feature worth surfacing.
- Disabling **guest networking** in a Sandbox to prove an artifact cites only held data: what the docs did and did
  not say about the scope of that setting.
- **Cached tokens** on a repeated legal preamble: the measured saving, and whether the cache-hit conditions were
  clearly documented.

### Idea B — JointCheck (solder inspection, vision)
- **Image tokens**: how they were billed, how they were surfaced in the response, and whether it was possible to
  see them separately from text tokens at all. If it was not, that is a concrete, actionable request — cost
  visibility for vision workloads.
- Sending **cropped ROIs** rather than full frames: the latency and cost delta, measured.
- A small model used as a **constrained classifier** over a frozen 24-code vocabulary: how well structured output
  held the constraint, and how often out-of-vocabulary codes appeared.
- Whether a **LoRA fine-tune + merge** path was realistically achievable in four days, and what blocked it.
- Sandbox image size limits with **WeasyPrint** and its system dependencies — a very common, very specific pain.

### Idea C — GridQueue (Dutch grid congestion, live document retrieval)
- **Tavily on non-English government queries** (§6 above). This is the single most valuable observation available
  to a Tavily-owned bonus prize: Dutch-language discovery against grid operators' and regulators' publications,
  how many results were usable, and what the failure modes looked like.
- **Long-document context**: feeding whole registers into one call. The observed context limits per model, the
  competitor-reported 16,000-token *output* limit and its effect on multi-document extraction, and how chunking
  interacted with citation accuracy.
- Whether **chunk-level caching** is possible for a document corpus (repeated framework-decision preamble) — a
  concrete request with a real measured cost behind it.
- **Publisher URL rot**: whether an Object Storage + Serverless Endpoint combination made a December-durable demo
  easy, with the actual steps and the actual cost.
- Rate limits and politeness under a **200-area sweep** in a Serverless Job.

### Idea D — Reflex (physical AI, edge + cloud)
- **The edge-device gap** (§5 above, and the strongest point available): a physical device that the platform
  cannot reach. What would make an edge→cloud safety ledger easy — an ingestion endpoint? device identity?
  offline-buffer/back-fill support? signed decision records? For a sponsor pushing physical AI, this is exactly the
  feedback they need and almost nobody will give it.
- **Serverless Job for a simulation replay lane**: container/image limits, whether GPU access was available in a
  Job and how it was requested, wall-time behaviour, cost per replay.
- **Sandbox branching for two byte-identical arms of a safety proof** rather than for code alternatives — a
  genuinely fresh application of the feature.
- **Cosmos Reason** frame-batching limits and cost per batch; what the input format did and did not allow.
- **Control-loop latency from the EU to Token Factory**, with real p50/p99 numbers over n calls — data a platform
  team cannot easily get otherwise.

---

## Preflight

- [ ] ≥400 words, ≥6 distinct points, ≥4 with a number / doc URL / code snippet
- [ ] ≥1 concrete feature request with a **use case first**
- [ ] ≥1 point where the fault was yours, and what specifically was confusing
- [ ] Every doc reference is a real URL you actually visited, not a reconstructed one
- [ ] Exact model catalog ids, exact versions, exact endpoints, request/operation ids where you have them
- [ ] A real numbers table (§4) with your measured values
- [ ] The non-English / international section, if applicable — this is rare signal, do not skip it
- [ ] No flattery without a mechanism; no complaint without a reproduction
- [ ] Contact details included if you want a follow-up (swag and credits both come this way)
- [ ] Posted **before** the deadline, in the place the rules specify (check `/rules` — feedback submissions are
      often a separate form or a comment thread, not part of the project submission)
- [ ] Cross-checked: every number here matches the README, the Devpost copy and the video
